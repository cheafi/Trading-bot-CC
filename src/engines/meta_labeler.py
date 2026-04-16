"""
CC — Meta-Labeler Engine
=========================
Given a setup exists, the meta-labeler answers:
  "Should I trade it NOW, at THIS size, in THIS regime,
   in THIS portfolio, with THIS event calendar?"

This is the layer between signal generation and order execution.
It converts a raw signal into a go/no-go + size decision by
evaluating regime fit, portfolio marginal contribution, event
proximity, execution quality, and calibration reliability.

Reference: QuantConnect's modular alpha → portfolio → risk → execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Decision Outputs ────────────────────────────────────────────


class MetaDecision(str, Enum):
    """Final meta-labeler verdict."""

    STRONG_BUY = "STRONG_BUY"
    BUY_SMALL = "BUY_SMALL"
    WATCH = "WATCH"
    NO_TRADE = "NO_TRADE"
    REDUCE = "REDUCE"
    HEDGE = "HEDGE"


@dataclass
class MetaLabel:
    """Output of the meta-labeler for one candidate signal."""

    ticker: str
    decision: MetaDecision = MetaDecision.WATCH
    size_multiplier: float = 1.0  # 0.0 = skip, 0.5 = half, 1.0 = full
    reasons_for: List[str] = field(default_factory=list)
    reasons_against: List[str] = field(default_factory=list)
    vetoes: List[str] = field(default_factory=list)  # hard blocks
    scores: Dict[str, float] = field(default_factory=dict)
    evaluated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "decision": self.decision.value,
            "size_multiplier": round(self.size_multiplier, 2),
            "reasons_for": self.reasons_for,
            "reasons_against": self.reasons_against,
            "vetoes": self.vetoes,
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
            "evaluated_at": self.evaluated_at,
        }


# ─── Context Inputs ──────────────────────────────────────────────


@dataclass
class SignalContext:
    """Everything the meta-labeler needs to evaluate a candidate."""

    ticker: str
    direction: str = "LONG"
    raw_score: float = 50.0
    confidence: float = 0.5
    strategy: str = ""
    regime: str = "unknown"
    regime_fit: float = 0.5
    # Calibration
    calibrated_probability: float = 0.5
    reliability_bucket: str = "uncalibrated"
    reliability_sample_size: int = 0
    uncertainty_width: float = 0.4
    # Portfolio state
    current_gross_exposure_pct: float = 0.0
    current_sector_weight_pct: float = 0.0
    correlation_to_book: float = 0.0
    open_positions: int = 0
    daily_pnl_pct: float = 0.0
    consecutive_losses: int = 0
    # Execution quality
    spread_bps: float = 10.0
    avg_daily_volume: float = 1e6
    session_quality: str = "regular"  # regular / pre / post / off
    # Event proximity
    days_to_earnings: int = 999
    days_to_fomc: int = 999
    days_to_cpi: int = 999
    days_to_nfp: int = 999


# ─── Meta-Labeler ─────────────────────────────────────────────────

# Configurable thresholds
_DEFAULTS = {
    "min_calibrated_prob": 0.45,
    "min_regime_fit": 0.3,
    "max_gross_exposure_pct": 90.0,
    "max_sector_weight_pct": 25.0,
    "max_correlation_to_book": 0.85,
    "max_open_positions": 15,
    "max_consecutive_losses": 5,
    "daily_loss_limit_pct": 3.0,
    "min_reliability_samples": 20,
    "earnings_blackout_days": 2,
    "fomc_blackout_days": 1,
    "spread_kill_bps": 100.0,
    "min_adv": 100_000,
    "strong_buy_threshold": 0.75,
    "buy_small_threshold": 0.55,
}


class MetaLabeler:
    """
    Evaluates whether a raw signal should be traded, at what size,
    given the current regime, portfolio, event calendar, and
    execution environment.

    Outputs MetaLabel with decision + size_multiplier + reasons.
    """

    def __init__(self, **overrides: float):
        self.cfg = {**_DEFAULTS, **overrides}

    def evaluate(self, ctx: SignalContext) -> MetaLabel:
        """Run all checks and produce a meta-label."""
        now = datetime.now(timezone.utc).isoformat()
        label = MetaLabel(ticker=ctx.ticker, evaluated_at=now)
        scores: Dict[str, float] = {}

        # ── Hard vetoes (any one blocks the trade) ────────────

        if ctx.spread_bps > self.cfg["spread_kill_bps"]:
            label.vetoes.append(
                f"spread {ctx.spread_bps:.0f}bps > kill "
                f"switch {self.cfg['spread_kill_bps']:.0f}bps"
            )

        if ctx.avg_daily_volume < self.cfg["min_adv"]:
            label.vetoes.append(
                f"ADV {ctx.avg_daily_volume:,.0f} < min " f"{self.cfg['min_adv']:,.0f}"
            )

        if ctx.days_to_earnings <= self.cfg["earnings_blackout_days"]:
            label.vetoes.append(
                f"earnings in {ctx.days_to_earnings}d "
                f"(blackout {self.cfg['earnings_blackout_days']}d)"
            )

        if ctx.days_to_fomc <= self.cfg["fomc_blackout_days"]:
            label.vetoes.append(f"FOMC in {ctx.days_to_fomc}d")

        if ctx.session_quality == "off":
            label.vetoes.append("market closed")

        if abs(ctx.daily_pnl_pct) >= self.cfg["daily_loss_limit_pct"]:
            label.vetoes.append(
                f"daily loss {ctx.daily_pnl_pct:.1f}% >= "
                f"limit {self.cfg['daily_loss_limit_pct']:.1f}%"
            )

        if ctx.consecutive_losses >= self.cfg["max_consecutive_losses"]:
            label.vetoes.append(f"{ctx.consecutive_losses} consecutive losses")

        if label.vetoes:
            label.decision = MetaDecision.NO_TRADE
            label.size_multiplier = 0.0
            label.reasons_against = label.vetoes.copy()
            label.scores = scores
            return label

        # ── Soft scores (combined into composite) ─────────────

        # 1. Calibrated probability
        cal_p = ctx.calibrated_probability
        scores["calibrated_prob"] = cal_p
        if cal_p >= self.cfg["min_calibrated_prob"]:
            label.reasons_for.append(f"calibrated P(win) = {cal_p:.1%}")
        else:
            label.reasons_against.append(
                f"calibrated P(win) = {cal_p:.1%} "
                f"< min {self.cfg['min_calibrated_prob']:.1%}"
            )

        # 2. Regime fit
        scores["regime_fit"] = ctx.regime_fit
        if ctx.regime_fit >= 0.6:
            label.reasons_for.append(
                f"good regime fit ({ctx.regime}): " f"{ctx.regime_fit:.2f}"
            )
        elif ctx.regime_fit < self.cfg["min_regime_fit"]:
            label.reasons_against.append(f"poor regime fit: {ctx.regime_fit:.2f}")

        # 3. Portfolio marginal contribution
        port_score = 1.0
        if ctx.current_gross_exposure_pct > self.cfg["max_gross_exposure_pct"]:
            label.reasons_against.append(
                f"gross exposure {ctx.current_gross_exposure_pct:.0f}%"
            )
            port_score *= 0.3
        if ctx.current_sector_weight_pct > self.cfg["max_sector_weight_pct"]:
            label.reasons_against.append(
                f"sector weight {ctx.current_sector_weight_pct:.0f}%"
            )
            port_score *= 0.5
        if ctx.correlation_to_book > self.cfg["max_correlation_to_book"]:
            label.reasons_against.append(
                f"high correlation to book: " f"{ctx.correlation_to_book:.2f}"
            )
            port_score *= 0.5
        if ctx.open_positions >= self.cfg["max_open_positions"]:
            label.reasons_against.append(
                f"max positions ({ctx.open_positions}) reached"
            )
            port_score *= 0.0
        scores["portfolio_fit"] = port_score

        # 4. Reliability / sample size
        rel_score = 1.0
        if ctx.reliability_sample_size < self.cfg["min_reliability_samples"]:
            label.reasons_against.append(
                f"only {ctx.reliability_sample_size} calibration "
                f"samples (need {self.cfg['min_reliability_samples']})"
            )
            rel_score = 0.6
        scores["reliability"] = rel_score

        # 5. Uncertainty width penalty
        unc_score = max(0.0, 1.0 - ctx.uncertainty_width)
        scores["uncertainty"] = unc_score
        if ctx.uncertainty_width > 0.5:
            label.reasons_against.append(
                f"wide uncertainty band: " f"\u00b1{ctx.uncertainty_width / 2:.1%}"
            )

        # 6. Execution quality
        exec_score = 1.0
        if ctx.spread_bps > 50:
            exec_score *= 0.7
            label.reasons_against.append(f"wide spread: {ctx.spread_bps:.0f}bps")
        if ctx.session_quality != "regular":
            exec_score *= 0.8
            label.reasons_against.append(f"session: {ctx.session_quality}")
        scores["execution"] = exec_score

        # ── Composite score → decision ────────────────────────

        composite = (
            cal_p * 0.30
            + ctx.regime_fit * 0.20
            + port_score * 0.15
            + rel_score * 0.10
            + unc_score * 0.10
            + exec_score * 0.15
        )
        scores["composite"] = composite

        # Size multiplier: reduce for soft negatives
        size_mult = min(1.0, composite / 0.6)
        size_mult = max(0.0, size_mult)

        # Map composite to decision
        if composite >= self.cfg["strong_buy_threshold"]:
            label.decision = MetaDecision.STRONG_BUY
            label.size_multiplier = min(1.0, size_mult)
        elif composite >= self.cfg["buy_small_threshold"]:
            label.decision = MetaDecision.BUY_SMALL
            label.size_multiplier = min(0.5, size_mult)
        else:
            label.decision = MetaDecision.WATCH
            label.size_multiplier = 0.0
            label.reasons_against.append(
                f"composite {composite:.2f} below "
                f"buy threshold {self.cfg['buy_small_threshold']:.2f}"
            )

        label.scores = scores
        return label


# Module-level singleton
meta_labeler = MetaLabeler()
