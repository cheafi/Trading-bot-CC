"""
Sizing Advisor — Sprint 109
============================
Unified position-sizing recommendation that combines:

  1. PositionSizer       — Kelly / ATR fixed-risk base size (Sprint 50)
  2. ThompsonSizingEngine — RL Beta-distribution multiplier (Sprint 103)
  3. apply_decay_penalty  — staleness penalty (Sprint 108)
  4. Portfolio heat gate  — respect RISK.max_portfolio_heat

Output:
  AdvisedSize dataclass with full audit trail of every adjustment applied.

Usage::

    from src.engines.sizing_advisor import SizingAdvisor

    advisor = SizingAdvisor(equity=100_000, current_heat_pct=0.02)
    result = advisor.advise(
        ticker="AAPL",
        entry_price=175.0,
        stop_price=168.0,
        signal_score=82.0,
        signal_grade="B",
        age_hours=5.0,
        strategy="PULLBACK_TREND",
        regime="BULL",
    )
    print(result.final_size_pct, result.audit_trail)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.risk_limits import RISK

# Lazy imports to avoid circular deps
_MIN_SCORE_TO_SIZE = 50.0  # do not advise sizing for scores below this
_DECAY_SCORE_THRESHOLD = 60.0  # below this score, decay adj is applied at full weight
_MAX_THOMPSON_MULT = 2.0
_MIN_THOMPSON_MULT = 0.25


@dataclass
class AdvisedSize:
    """Full sizing recommendation with audit trail."""

    ticker: str
    # Sizes as fraction of equity (0–1)
    base_size_pct: float  # from PositionSizer (Kelly/ATR)
    thompson_mult: float  # RL multiplier from ThompsonSizingEngine
    decay_adj: float  # reduction factor due to signal staleness [0–1]
    heat_scale: float  # portfolio heat throttle [0–1]
    final_size_pct: float  # base × thompson × decay_adj × heat_scale, capped

    # Dollar / share translation (optional — requires entry price)
    dollar_amount: float
    shares: int
    entry_price: float
    stop_price: float
    risk_per_share: float
    total_risk_usd: float
    risk_pct_of_equity: float

    # Context
    signal_score: float
    signal_grade: str
    age_hours: float
    decay_pct: float  # % confidence decayed at this age
    strategy: str
    regime: str
    method: str  # base sizing method used

    # Sizing OK flag
    size_ok: bool  # False when zero shares or score too low
    zero_reason: str  # non-empty when size_ok=False

    audit_trail: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "base_size_pct": round(self.base_size_pct * 100, 3),
            "thompson_mult": round(self.thompson_mult, 3),
            "decay_adj": round(self.decay_adj, 3),
            "heat_scale": round(self.heat_scale, 3),
            "final_size_pct": round(self.final_size_pct * 100, 3),
            "dollar_amount": round(self.dollar_amount, 2),
            "shares": self.shares,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "risk_per_share": round(self.risk_per_share, 2),
            "total_risk_usd": round(self.total_risk_usd, 2),
            "risk_pct_of_equity": round(self.risk_pct_of_equity * 100, 3),
            "signal_score": self.signal_score,
            "signal_grade": self.signal_grade,
            "age_hours": round(self.age_hours, 2),
            "decay_pct": round(self.decay_pct, 2),
            "strategy": self.strategy,
            "regime": self.regime,
            "method": self.method,
            "size_ok": self.size_ok,
            "zero_reason": self.zero_reason,
            "audit_trail": self.audit_trail,
        }


class SizingAdvisor:
    """
    Multi-layer position sizing advisor.

    Parameters
    ----------
    equity : float
        Total account equity in USD.
    max_risk_pct : float
        Maximum risk per trade as fraction of equity (default 1%).
    max_position_pct : float
        Maximum single position weight (default 10%).
    max_portfolio_heat : float
        Hard portfolio heat ceiling (default from RISK constants).
    current_heat_pct : float
        Current open-risk heat as fraction of equity.
    """

    def __init__(
        self,
        equity: float = 100_000.0,
        max_risk_pct: float = 0.01,
        max_position_pct: float = 0.10,
        max_portfolio_heat: Optional[float] = None,
        current_heat_pct: float = 0.0,
    ):
        self.equity = max(equity, 1.0)
        self.max_risk_pct = max_risk_pct
        self.max_position_pct = max_position_pct
        self.max_portfolio_heat = (
            max_portfolio_heat
            if max_portfolio_heat is not None
            else getattr(RISK, "max_portfolio_heat", 0.06)
        )
        self.current_heat_pct = current_heat_pct

    # ── Public API ──────────────────────────────────────────────────────────

    def advise(
        self,
        ticker: str,
        entry_price: float,
        stop_price: float,
        signal_score: float = 70.0,
        signal_grade: str = "B",
        age_hours: float = 0.0,
        strategy: str = "UNKNOWN",
        regime: str = "UNKNOWN",
        win_rate: Optional[float] = None,
        avg_win_loss_ratio: Optional[float] = None,
    ) -> AdvisedSize:
        """Compute a full advised size with audit trail."""
        audit: List[str] = []
        zero_result = lambda reason: self._zero(
            ticker,
            entry_price,
            stop_price,
            signal_score,
            signal_grade,
            age_hours,
            strategy,
            regime,
            reason,
            audit,
        )

        # ── Guard: minimum score ───────────────────────────────────────────
        if signal_score < _MIN_SCORE_TO_SIZE:
            return zero_result(
                f"Score {signal_score:.0f} below minimum {_MIN_SCORE_TO_SIZE:.0f}"
            )

        # ── Guard: prices ─────────────────────────────────────────────────
        if entry_price <= 0 or stop_price <= 0:
            return zero_result("Invalid entry or stop price")

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share < 0.01:
            return zero_result("Risk per share ≈ 0 (entry ≈ stop)")

        # ── Step 1: Base size (fixed-risk / Kelly) ─────────────────────────
        base_size_pct, method = self._base_size(
            entry_price, risk_per_share, win_rate, avg_win_loss_ratio, audit
        )
        if base_size_pct <= 0:
            return zero_result("Base size computed as 0")

        # ── Step 2: Thompson RL multiplier ─────────────────────────────────
        thompson_mult = self._thompson_mult(strategy, regime, audit)

        # ── Step 3: Decay adjustment ───────────────────────────────────────
        decay_adj, decay_pct = self._decay_adj(
            signal_score, signal_grade, age_hours, audit
        )

        # ── Step 4: Portfolio heat gate ────────────────────────────────────
        heat_scale = self._heat_scale(audit)

        # ── Combine ────────────────────────────────────────────────────────
        raw_final = base_size_pct * thompson_mult * decay_adj * heat_scale
        final_size_pct = min(raw_final, self.max_position_pct)
        if final_size_pct < raw_final:
            audit.append(
                f"Capped at max_position_pct {self.max_position_pct:.0%} "
                f"(raw was {raw_final:.2%})"
            )

        # ── Dollar / share translation ─────────────────────────────────────
        dollar_amount = self.equity * final_size_pct
        shares = int(dollar_amount / entry_price) if entry_price > 0 else 0
        if shares <= 0:
            return zero_result("0 shares after all adjustments")

        dollar_amount = shares * entry_price
        final_size_pct = dollar_amount / self.equity
        total_risk = risk_per_share * shares
        risk_pct = total_risk / self.equity

        # Hard risk-per-trade cap (second pass)
        if risk_pct > self.max_risk_pct:
            shares = int((self.max_risk_pct * self.equity) / risk_per_share)
            if shares <= 0:
                return zero_result("0 shares after risk-per-trade cap")
            dollar_amount = shares * entry_price
            final_size_pct = dollar_amount / self.equity
            total_risk = risk_per_share * shares
            risk_pct = total_risk / self.equity
            audit.append("Shares capped by max-risk-per-trade hard limit")

        audit.append(
            f"Final: {shares} shares @ ${entry_price:.2f} = "
            f"${dollar_amount:,.0f} ({final_size_pct:.2%} equity, "
            f"${total_risk:.0f} risk)"
        )

        return AdvisedSize(
            ticker=ticker,
            base_size_pct=base_size_pct,
            thompson_mult=thompson_mult,
            decay_adj=decay_adj,
            heat_scale=heat_scale,
            final_size_pct=final_size_pct,
            dollar_amount=round(dollar_amount, 2),
            shares=shares,
            entry_price=entry_price,
            stop_price=stop_price,
            risk_per_share=round(risk_per_share, 2),
            total_risk_usd=round(total_risk, 2),
            risk_pct_of_equity=round(risk_pct, 4),
            signal_score=signal_score,
            signal_grade=signal_grade,
            age_hours=age_hours,
            decay_pct=round(decay_pct, 2),
            strategy=strategy,
            regime=regime,
            method=method,
            size_ok=True,
            zero_reason="",
            audit_trail=audit,
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _base_size(
        self,
        entry_price: float,
        risk_per_share: float,
        win_rate: Optional[float],
        avg_win_loss_ratio: Optional[float],
        audit: List[str],
    ):
        """Return (base_size_pct, method_name)."""
        if win_rate is not None and avg_win_loss_ratio is not None:
            # Half-Kelly
            p, b = max(0.0, min(1.0, win_rate)), max(0.01, avg_win_loss_ratio)
            q = 1 - p
            full_kelly = (p * b - q) / b
            kelly_frac = max(0.0, full_kelly / 2)
            audit.append(f"Half-Kelly: {kelly_frac:.2%} (win_rate={p:.0%}, rr={b:.2f})")
            return min(kelly_frac, self.max_position_pct), "half_kelly"

        # Fixed-risk: risk max_risk_pct of equity
        # base = dollar_risk / (risk_per_share * shares_per_dollar)
        # = max_risk_pct (as fraction of equity)
        # expressed as position pct = max_risk_pct * (entry / risk_per_share)
        shares_for_1pct_risk = (self.max_risk_pct * self.equity) / risk_per_share
        dollar_for_those_shares = shares_for_1pct_risk * entry_price
        size_pct = dollar_for_those_shares / self.equity
        size_pct = min(size_pct, self.max_position_pct)
        audit.append(
            f"Fixed-risk base: {size_pct:.2%} "
            f"(risk_per_share=${risk_per_share:.2f})"
        )
        return size_pct, "fixed_risk"

    def _thompson_mult(self, strategy: str, regime: str, audit: List[str]) -> float:
        """Sample Thompson RL multiplier; fall back to 1.0 on any error."""
        try:
            from src.engines.thompson_sizing import get_thompson_engine

            engine = get_thompson_engine()
            mult = engine.sample(strategy, regime)
            mult = max(_MIN_THOMPSON_MULT, min(_MAX_THOMPSON_MULT, mult))
            audit.append(f"Thompson [{strategy}/{regime}]: ×{mult:.3f}")
            return mult
        except Exception as exc:  # noqa: BLE001
            audit.append(f"Thompson unavailable ({exc}), ×1.0")
            return 1.0

    def _decay_adj(
        self,
        signal_score: float,
        signal_grade: str,
        age_hours: float,
        audit: List[str],
    ):
        """Return (adj_factor, decay_pct).  adj_factor ∈ [0.5, 1.0]."""
        try:
            from src.engines.signal_decay import apply_decay_penalty, DECAY_SCHEDULE

            half_life = DECAY_SCHEDULE.get(signal_grade, 16.0)
            decay_frac = 1 - math.exp(-math.log(2) * age_hours / half_life)
            decay_pct = decay_frac * 100.0

            # adj: at decay_frac=0 → 1.0; at decay_frac=1 → 0.5
            # Linear blend: reduces size by up to 50% for fully decayed signals
            adj = max(0.5, 1.0 - decay_frac * 0.5)

            if decay_frac > 0.25:
                audit.append(
                    f"Decay [{signal_grade}, {age_hours:.1f}h, half-life {half_life}h]: "
                    f"{decay_pct:.1f}% → size adj ×{adj:.3f}"
                )
            else:
                audit.append(
                    f"Signal fresh [{signal_grade}, {age_hours:.1f}h]: no decay adj"
                )
            return adj, decay_pct
        except Exception as exc:  # noqa: BLE001
            audit.append(f"Decay module unavailable ({exc}), no adj")
            return 1.0, 0.0

    def _heat_scale(self, audit: List[str]) -> float:
        """Return heat throttle scale factor [0–1]."""
        heat_remaining = max(0.0, self.max_portfolio_heat - self.current_heat_pct)
        if heat_remaining <= 0:
            audit.append("Portfolio heat FULL — size zeroed by heat gate")
            return 0.0
        scale = min(1.0, heat_remaining / max(self.max_risk_pct, 0.001))
        scale = min(scale, 1.0)
        if scale < 1.0:
            audit.append(
                f"Heat throttle: ×{scale:.3f} "
                f"(heat {self.current_heat_pct:.1%} / {self.max_portfolio_heat:.1%})"
            )
        return scale

    def _zero(
        self,
        ticker: str,
        entry_price: float,
        stop_price: float,
        signal_score: float,
        signal_grade: str,
        age_hours: float,
        strategy: str,
        regime: str,
        reason: str,
        audit: List[str],
    ) -> AdvisedSize:
        audit.append(f"ZERO: {reason}")
        return AdvisedSize(
            ticker=ticker,
            base_size_pct=0.0,
            thompson_mult=1.0,
            decay_adj=1.0,
            heat_scale=1.0,
            final_size_pct=0.0,
            dollar_amount=0.0,
            shares=0,
            entry_price=entry_price,
            stop_price=stop_price,
            risk_per_share=abs(entry_price - stop_price),
            total_risk_usd=0.0,
            risk_pct_of_equity=0.0,
            signal_score=signal_score,
            signal_grade=signal_grade,
            age_hours=age_hours,
            decay_pct=0.0,
            strategy=strategy,
            regime=regime,
            method="zero",
            size_ok=False,
            zero_reason=reason,
            audit_trail=audit,
        )
