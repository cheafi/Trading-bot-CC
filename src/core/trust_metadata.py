"""
Trust Metadata — professional trust signals for every card (Sprint 36).

Every output surface (Discord, Telegram, API, dashboard) should carry
clear trust indicators so users never mistake paper for live, stale
for fresh, or cherry-picked for systematic.

Trust dimensions:
  • Badge:      LIVE | PAPER | BACKTEST | RESEARCH
  • Freshness:  FRESH | AGING | STALE  (based on data age)
  • Source:     source_count, contradiction_level
  • PnL:       gross / net / fees / slippage decomposition
  • Attribution: what_worked / what_failed on every close
  • Model:      version tag + regime at decision time

Usage::

    from src.core.trust_metadata import (
        TrustBadge, FreshnessLevel, TrustMetadata,
        PnLBreakdown, TradeAttribution,
    )

    meta = TrustMetadata(
        badge=TrustBadge.PAPER,
        freshness=FreshnessLevel.FRESH,
        source_count=3,
    )
    card["trust"] = meta.to_dict()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────

MODEL_VERSION = "v6.38"  # bump each sprint


class TrustBadge(Enum):
    """Execution-mode badge for every card."""
    LIVE = "LIVE"
    PAPER = "PAPER"
    BACKTEST = "BACKTEST"
    RESEARCH = "RESEARCH"


class FreshnessLevel(Enum):
    """Data freshness classification."""
    FRESH = "FRESH"          # < 15 min
    AGING = "AGING"          # 15 min – 2 h
    STALE = "STALE"          # > 2 h


class ContradictionLevel(Enum):
    """Source agreement classification."""
    LOW = "LOW"              # sources agree
    MEDIUM = "MEDIUM"        # partial disagreement
    HIGH = "HIGH"            # sources conflict


class ConfidenceTier(Enum):
    """Signal confidence tier for display."""
    HIGH = "HIGH"            # ≥ 75
    MEDIUM = "MEDIUM"        # 50–74
    LOW = "LOW"              # < 50


# ─────────────────────────────────────────────────────────────────────
# PnL Breakdown
# ─────────────────────────────────────────────────────────────────────

@dataclass
class PnLBreakdown:
    """Gross/net P&L decomposition for professional result cards.

    All values in percent of entry capital.
    """
    gross_pnl_pct: float = 0.0
    fees_pct: float = 0.0
    slippage_pct: float = 0.0
    net_pnl_pct: float = 0.0

    # Context
    hold_hours: float = 0.0
    exit_reason: str = ""
    is_win: bool = False

    def __post_init__(self):
        if self.net_pnl_pct == 0.0 and self.gross_pnl_pct != 0.0:
            self.net_pnl_pct = (
                self.gross_pnl_pct - self.fees_pct - self.slippage_pct
            )
        self.is_win = self.net_pnl_pct > 0

    @classmethod
    def from_trade(
        cls,
        gross_pnl_pct: float,
        fees_pct: float = 0.0,
        slippage_pct: float = 0.0,
        hold_hours: float = 0.0,
        exit_reason: str = "",
    ) -> "PnLBreakdown":
        net = gross_pnl_pct - fees_pct - slippage_pct
        return cls(
            gross_pnl_pct=gross_pnl_pct,
            fees_pct=fees_pct,
            slippage_pct=slippage_pct,
            net_pnl_pct=net,
            hold_hours=hold_hours,
            exit_reason=exit_reason,
            is_win=net > 0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_pnl_pct": round(self.gross_pnl_pct, 3),
            "fees_pct": round(self.fees_pct, 3),
            "slippage_pct": round(self.slippage_pct, 3),
            "net_pnl_pct": round(self.net_pnl_pct, 3),
            "hold_hours": round(self.hold_hours, 1),
            "exit_reason": self.exit_reason,
            "is_win": self.is_win,
        }

    def summary_line(self) -> str:
        """One-liner for cards: Gross +2.50% → Net +2.35% (fees 0.10%, slip 0.05%)"""
        return (
            f"Gross {self.gross_pnl_pct:+.2f}% → "
            f"Net {self.net_pnl_pct:+.2f}% "
            f"(fees {self.fees_pct:.2f}%, slip {self.slippage_pct:.2f}%)"
        )


# ─────────────────────────────────────────────────────────────────────
# Trade Attribution
# ─────────────────────────────────────────────────────────────────────

@dataclass
class TradeAttribution:
    """Post-trade attribution: what worked / what failed.

    Populated when a position closes, surfaced on result cards.
    """
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    regime_correct: bool = False
    timing_correct: bool = False
    signal_correct: bool = False
    exit_optimal: bool = False

    @classmethod
    def from_closed_trade(
        cls,
        pnl_pct: float,
        exit_reason: str,
        regime_at_entry: str = "",
        regime_at_exit: str = "",
        hold_hours: float = 0.0,
        max_hold_hours: float = 120.0,
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        stop_price: float = 0.0,
        target_price: float = 0.0,
        direction: str = "LONG",
    ) -> "TradeAttribution":
        """Auto-generate attribution from trade data."""
        attr = cls()
        is_win = pnl_pct > 0

        # Regime assessment
        same_regime = (
            regime_at_entry == regime_at_exit
            or not regime_at_exit
        )
        attr.regime_correct = same_regime and is_win
        if attr.regime_correct:
            attr.what_worked.append("Regime stable throughout hold")
        elif not same_regime:
            attr.what_failed.append(
                f"Regime shifted: {regime_at_entry} → {regime_at_exit}"
            )

        # Signal assessment
        attr.signal_correct = is_win
        if is_win:
            attr.what_worked.append(
                f"Signal direction correct ({direction})"
            )
        else:
            attr.what_failed.append(
                f"Signal direction wrong ({direction})"
            )

        # Timing assessment
        attr.timing_correct = (
            is_win and hold_hours < max_hold_hours
        )
        if exit_reason == "time_stop":
            attr.what_failed.append("Timed out before target")
        elif exit_reason == "stop_loss":
            attr.what_failed.append("Hit stop loss")
        elif exit_reason in ("target_hit", "tp1", "tp2"):
            attr.what_worked.append("Reached price target")

        # Exit quality
        if target_price > 0 and entry_price > 0:
            if direction == "LONG":
                max_possible = (
                    (target_price - entry_price) / entry_price * 100
                )
                capture_pct = (
                    pnl_pct / max_possible * 100
                    if max_possible > 0 else 0
                )
            else:
                max_possible = (
                    (entry_price - target_price) / entry_price * 100
                )
                capture_pct = (
                    pnl_pct / max_possible * 100
                    if max_possible > 0 else 0
                )
            attr.exit_optimal = capture_pct >= 60
            if attr.exit_optimal:
                attr.what_worked.append(
                    f"Captured {capture_pct:.0f}% of target move"
                )
            elif is_win and capture_pct < 40:
                attr.what_failed.append(
                    f"Only captured {capture_pct:.0f}% — "
                    "exited too early"
                )

        return attr

    def to_dict(self) -> Dict[str, Any]:
        return {
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "regime_correct": self.regime_correct,
            "timing_correct": self.timing_correct,
            "signal_correct": self.signal_correct,
            "exit_optimal": self.exit_optimal,
        }

    def summary_lines(self) -> str:
        """Multi-line summary for cards."""
        lines = []
        if self.what_worked:
            lines.append("✅ " + " | ".join(self.what_worked[:3]))
        if self.what_failed:
            lines.append("❌ " + " | ".join(self.what_failed[:3]))
        return "\n".join(lines) if lines else "—"


# ─────────────────────────────────────────────────────────────────────
# No-Trade Reason
# ─────────────────────────────────────────────────────────────────────

@dataclass
class NoTradeCard:
    """Structured no-trade card for when the system decides NOT to trade.

    Professional systems show their discipline by explaining
    why they passed, not just when they traded.
    """
    reason: str = ""
    tickers_considered: List[str] = field(default_factory=list)
    regime_label: str = ""
    resume_conditions: List[str] = field(default_factory=list)
    confidence_tier: str = "LOW"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(
                timezone.utc,
            ).strftime("%Y-%m-%d %H:%M UTC")

    @classmethod
    def from_regime(
        cls,
        regime_state: Dict[str, Any],
        tickers: Optional[List[str]] = None,
    ) -> "NoTradeCard":
        """Build no-trade card from regime state."""
        reason = regime_state.get("no_trade_reason", "")
        if not reason:
            if not regime_state.get("should_trade", True):
                reason = "Regime unfavourable"
            else:
                reason = "No qualifying setups"

        resume = []
        risk = regime_state.get("risk_regime", "")
        if risk == "risk_off":
            resume.append("VIX drops below 25")
            resume.append("Breadth recovers above 40%")
        elif risk == "neutral":
            resume.append("Clear trend signal emerges")
        resume.append("Second source confirms catalyst")

        return cls(
            reason=reason,
            tickers_considered=tickers or [],
            regime_label=regime_state.get("regime", "unknown"),
            resume_conditions=resume,
            confidence_tier="LOW",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "tickers_considered": self.tickers_considered,
            "regime_label": self.regime_label,
            "resume_conditions": self.resume_conditions,
            "confidence_tier": self.confidence_tier,
            "timestamp": self.timestamp,
        }

    def format_card(self) -> str:
        """Text-format for Telegram / Discord."""
        lines = [
            "🚫 No Trade",
            f"Regime: {self.regime_label}",
            f"Reason: {self.reason}",
        ]
        if self.tickers_considered:
            lines.append(
                f"Considered: {', '.join(self.tickers_considered[:5])}"
            )
        if self.resume_conditions:
            lines.append("Resume when:")
            for c in self.resume_conditions[:3]:
                lines.append(f"  • {c}")
        lines.append(f"Updated: {self.timestamp}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Main TrustMetadata container
# ─────────────────────────────────────────────────────────────────────

@dataclass
class TrustMetadata:
    """Unified trust metadata attached to every output card.

    Ensures every card clearly shows:
      - Is this live, paper, or backtest?
      - How fresh is the data?
      - How many sources confirmed?
      - What are the gross/net numbers?
      - What model version produced this?
    """
    # Badge
    badge: TrustBadge = TrustBadge.PAPER
    model_version: str = MODEL_VERSION

    # Freshness
    freshness: FreshnessLevel = FreshnessLevel.FRESH
    data_age_minutes: float = 0.0
    source_count: int = 1
    contradiction: ContradictionLevel = ContradictionLevel.LOW

    # Confidence
    confidence_tier: ConfidenceTier = ConfidenceTier.MEDIUM

    # P&L (populated on result cards)
    pnl: Optional[PnLBreakdown] = None

    # Attribution (populated on close cards)
    attribution: Optional[TradeAttribution] = None

    # Regime at decision time
    regime_label: str = ""
    risk_regime: str = ""

    @classmethod
    def classify_freshness(
        cls, age_minutes: float,
    ) -> FreshnessLevel:
        """Classify data age into freshness level."""
        if age_minutes < 15:
            return FreshnessLevel.FRESH
        elif age_minutes < 120:
            return FreshnessLevel.AGING
        else:
            return FreshnessLevel.STALE

    @classmethod
    def classify_confidence(
        cls, confidence: float,
    ) -> ConfidenceTier:
        """Classify signal confidence into tier."""
        if confidence >= 75:
            return ConfidenceTier.HIGH
        elif confidence >= 50:
            return ConfidenceTier.MEDIUM
        else:
            return ConfidenceTier.LOW

    @classmethod
    def for_entry(
        cls,
        badge: TrustBadge = TrustBadge.PAPER,
        confidence: float = 50,
        source_count: int = 1,
        data_age_minutes: float = 0.0,
        regime_label: str = "",
        risk_regime: str = "",
    ) -> "TrustMetadata":
        """Build trust metadata for a trade entry card."""
        return cls(
            badge=badge,
            freshness=cls.classify_freshness(data_age_minutes),
            data_age_minutes=data_age_minutes,
            source_count=source_count,
            confidence_tier=cls.classify_confidence(confidence),
            regime_label=regime_label,
            risk_regime=risk_regime,
        )

    @classmethod
    def for_exit(
        cls,
        badge: TrustBadge = TrustBadge.PAPER,
        pnl: Optional[PnLBreakdown] = None,
        attribution: Optional[TradeAttribution] = None,
        regime_label: str = "",
    ) -> "TrustMetadata":
        """Build trust metadata for a position-close card."""
        return cls(
            badge=badge,
            pnl=pnl,
            attribution=attribution,
            regime_label=regime_label,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "badge": self.badge.value,
            "model_version": self.model_version,
            "freshness": self.freshness.value,
            "data_age_minutes": round(self.data_age_minutes, 1),
            "source_count": self.source_count,
            "contradiction": self.contradiction.value,
            "confidence_tier": self.confidence_tier.value,
            "regime_label": self.regime_label,
            "risk_regime": self.risk_regime,
        }
        if self.pnl:
            d["pnl"] = self.pnl.to_dict()
        if self.attribution:
            d["attribution"] = self.attribution.to_dict()
        return d

    # ── Card rendering helpers ────────────────────────────────────

    def badge_emoji(self) -> str:
        """Emoji + text badge for cards."""
        return {
            TrustBadge.LIVE: "🟢 LIVE",
            TrustBadge.PAPER: "📋 PAPER",
            TrustBadge.BACKTEST: "🔬 BACKTEST",
            TrustBadge.RESEARCH: "🔍 RESEARCH",
        }.get(self.badge, "❓ UNKNOWN")

    def freshness_emoji(self) -> str:
        """Freshness indicator."""
        return {
            FreshnessLevel.FRESH: "🟢 Fresh",
            FreshnessLevel.AGING: "🟡 Aging",
            FreshnessLevel.STALE: "🔴 Stale",
        }.get(self.freshness, "❓")

    def header_line(self) -> str:
        """One-liner for card header/footer."""
        parts = [
            self.badge_emoji(),
            self.freshness_emoji(),
            f"Sources: {self.source_count}",
        ]
        if self.regime_label:
            parts.append(f"Regime: {self.regime_label}")
        parts.append(self.model_version)
        return " │ ".join(parts)

    def footer_line(self) -> str:
        """Compact footer for embeds."""
        age_str = (
            f"{self.data_age_minutes:.0f}m ago"
            if self.data_age_minutes > 0
            else "just now"
        )
        return (
            f"{self.badge_emoji()} │ "
            f"Updated: {age_str} │ "
            f"{self.model_version}"
        )
