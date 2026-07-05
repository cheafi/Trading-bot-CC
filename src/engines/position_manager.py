"""
Position Management Engine — Sprint 65
========================================
Monitors open positions and generates HOLD/REDUCE/EXIT signals.

Missing from the pipeline: once a TRADE signal fires, nothing
monitors the position. This engine fills that gap.

Management rules:
  - Trailing stop: trail at 2x ATR below recent high
  - Partial profit: take 1/3 at 1R, 1/3 at 2R
  - RS deterioration: if RS drops below 50, flag REDUCE
  - Structure break: if trend_structure → downtrend, flag EXIT
  - Time stop: if no progress after 20 bars, flag REVIEW

Usage:
    manager = PositionManager()
    actions = manager.evaluate(open_positions, current_data)
    # actions = [PositionAction(ticker="NVDA", action="REDUCE", ...)]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PositionAction:
    """Action to take on an open position."""

    ticker: str = ""
    action: str = "HOLD"  # HOLD / REDUCE / EXIT / TRAIL_STOP
    reason: str = ""
    urgency: str = "LOW"  # LOW / MEDIUM / HIGH / URGENT
    # Sizing guidance
    reduce_pct: float = 0.0  # % of position to reduce
    new_stop: float = 0.0  # Updated stop price
    # Context
    current_pnl_pct: float = 0.0
    rs_rank: float = 0.0
    days_held: int = 0
    r_multiple: float = 0.0  # Current P&L in R multiples

    def to_dict(self) -> dict:
        d = {
            "ticker": self.ticker,
            "action": self.action,
            "reason": self.reason,
            "urgency": self.urgency,
        }
        if self.reduce_pct > 0:
            d["reduce_pct"] = round(self.reduce_pct, 1)
        if self.new_stop > 0:
            d["new_stop"] = round(self.new_stop, 2)
        d["current_pnl_pct"] = round(self.current_pnl_pct, 2)
        d["days_held"] = self.days_held
        if self.r_multiple != 0:
            d["r_multiple"] = round(self.r_multiple, 2)
        return d


@dataclass
class OpenPosition:
    """An open position to evaluate."""

    ticker: str
    entry_price: float
    current_price: float
    stop_price: float = 0.0
    target_price: float = 0.0
    shares: int = 0
    entry_date: str = ""
    days_held: int = 0
    highest_price: float = 0.0  # High water mark since entry
    atr_pct: float = 2.0  # Current ATR as % of price
    rs_rank: float = 50.0
    trend_structure: str = ""
    volume_confirms: bool = False


class PositionManager:
    """
    Evaluate open positions and generate management actions.
    """

    # Configuration
    TRAIL_ATR_MULTIPLE = 2.0  # Trail stop at 2x ATR
    PARTIAL_1R_PCT = 33.0  # Take 33% at 1R
    PARTIAL_2R_PCT = 33.0  # Take 33% at 2R
    RS_REDUCE_THRESHOLD = 40  # RS below 40 → reduce
    TIME_STOP_DAYS = 20  # No progress after 20 days → review
    STRUCTURE_EXIT_TRENDS = ("strong_downtrend", "downtrend")

    def evaluate(
        self,
        positions: List[OpenPosition],
        regime: Dict[str, Any] | None = None,
    ) -> List[PositionAction]:
        """
        Evaluate all open positions and return management actions.
        """
        regime = regime or {}
        actions = []
        for pos in positions:
            action = self._evaluate_single(pos, regime)
            actions.append(action)

        # Sort: EXIT first, then REDUCE, then TRAIL_STOP, then HOLD
        _ORDER = {"EXIT": 0, "REDUCE": 1, "TRAIL_STOP": 2, "HOLD": 3}
        actions.sort(key=lambda a: _ORDER.get(a.action, 9))
        return actions

    def _evaluate_single(self, pos: OpenPosition, regime: dict) -> PositionAction:
        """Evaluate a single position."""
        action = PositionAction(ticker=pos.ticker)
        action.days_held = pos.days_held
        action.rs_rank = pos.rs_rank

        # P&L
        if pos.entry_price > 0:
            action.current_pnl_pct = (
                (pos.current_price - pos.entry_price) / pos.entry_price * 100
            )

        # R-multiple (if stop is set)
        risk = pos.entry_price - pos.stop_price if pos.stop_price > 0 else 0
        if risk > 0:
            action.r_multiple = (pos.current_price - pos.entry_price) / risk

        reasons = []

        # ── Check 1: Hard stop hit ──
        if pos.stop_price > 0 and pos.current_price <= pos.stop_price:
            action.action = "EXIT"
            action.reason = (
                f"Stop hit at ${pos.stop_price:.2f} "
                f"(P&L: {action.current_pnl_pct:+.1f}%)"
            )
            action.urgency = "URGENT"
            return action

        # ── Check 2: Structure breakdown ──
        if pos.trend_structure in self.STRUCTURE_EXIT_TRENDS:
            action.action = "EXIT"
            action.reason = (
                f"Structure breakdown: {pos.trend_structure} "
                f"(P&L: {action.current_pnl_pct:+.1f}%)"
            )
            action.urgency = "HIGH"
            return action

        # ── Check 3: Regime crisis → exit if losing ──
        regime_trend = regime.get("trend", "")
        if regime_trend == "CRISIS" and action.current_pnl_pct < 0:
            action.action = "EXIT"
            action.reason = (
                f"CRISIS regime + underwater " f"({action.current_pnl_pct:+.1f}%)"
            )
            action.urgency = "HIGH"
            return action

        # ── Check 4: Partial profit at 1R ──
        if action.r_multiple >= 1.0 and action.r_multiple < 2.0:
            action.action = "REDUCE"
            action.reduce_pct = self.PARTIAL_1R_PCT
            reasons.append(
                f"1R reached ({action.r_multiple:.1f}R) — "
                f"take {self.PARTIAL_1R_PCT:.0f}%"
            )
            action.urgency = "MEDIUM"

        # ── Check 5: Partial profit at 2R ──
        if action.r_multiple >= 2.0:
            action.action = "REDUCE"
            action.reduce_pct = self.PARTIAL_2R_PCT
            reasons.append(
                f"2R reached ({action.r_multiple:.1f}R) — "
                f"take {self.PARTIAL_2R_PCT:.0f}%"
            )
            action.urgency = "MEDIUM"

        # ── Check 6: RS deterioration ──
        if pos.rs_rank < self.RS_REDUCE_THRESHOLD:
            if action.action != "REDUCE":
                action.action = "REDUCE"
                action.reduce_pct = 50.0
            reasons.append(
                f"RS rank {pos.rs_rank:.0f} below " f"{self.RS_REDUCE_THRESHOLD}"
            )
            action.urgency = "MEDIUM"

        # ── Check 7: Trailing stop update ──
        if pos.highest_price > 0 and pos.atr_pct > 0:
            trail_stop = pos.highest_price * (
                1 - self.TRAIL_ATR_MULTIPLE * pos.atr_pct / 100
            )
            if trail_stop > pos.stop_price:
                action.new_stop = trail_stop
                if action.action == "HOLD":
                    action.action = "TRAIL_STOP"
                reasons.append(
                    f"Trail stop → ${trail_stop:.2f} " f"(from ${pos.stop_price:.2f})"
                )

        # ── Check 8: Time stop ──
        if pos.days_held >= self.TIME_STOP_DAYS and action.current_pnl_pct < 2.0:
            if action.action == "HOLD":
                action.action = "REDUCE"
                action.reduce_pct = 50.0
            reasons.append(
                f"Time stop: {pos.days_held}d held, "
                f"only {action.current_pnl_pct:+.1f}%"
            )

        # ── Default: HOLD ──
        if not reasons:
            action.action = "HOLD"
            action.reason = "Position healthy"
        else:
            action.reason = "; ".join(reasons)

        return action

    def summary(self, actions: List[PositionAction]) -> dict:
        """Summarize position management actions."""
        return {
            "total": len(actions),
            "hold": sum(1 for a in actions if a.action == "HOLD"),
            "reduce": sum(1 for a in actions if a.action == "REDUCE"),
            "exit": sum(1 for a in actions if a.action == "EXIT"),
            "trail_stop": sum(1 for a in actions if a.action == "TRAIL_STOP"),
            "urgent": [a.to_dict() for a in actions if a.urgency in ("URGENT", "HIGH")],
        }
