"""
Trade Gate Engine — Sprint 50
==============================
Pre-trade gating: evaluates whether *any* new trade should be taken
right now, independent of the specific signal quality.

This is the "should we even be trading?" check that runs BEFORE
signal-specific logic.

Hard gates (reject trade outright):
 • Max drawdown breached
 • Max open positions reached
 • Portfolio heat at maximum
 • Market-wide circuit breaker (extreme VIX, flash-crash detection)

Soft gates (warn but allow with reduced size):
 • Elevated VIX regime
 • Low liquidity hours
 • Earnings blackout for specific ticker
 • Regime uncertainty (conflicting signals)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.core.risk_limits import RISK
from datetime import datetime, timezone
from typing import Optional


@dataclass
class GateResult:
    """Result of the trade gate evaluation."""

    allowed: bool
    hard_blocks: list[str] = field(default_factory=list)
    soft_warnings: list[str] = field(default_factory=list)
    size_multiplier: float = 1.0  # 0.0–1.0, scale position size
    gate_timestamp: str = ""

    def __post_init__(self):
        if not self.gate_timestamp:
            self.gate_timestamp = datetime.now(timezone.utc).isoformat() + "Z"

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "hard_blocks": self.hard_blocks,
            "soft_warnings": self.soft_warnings,
            "size_multiplier": self.size_multiplier,
            "gate_timestamp": self.gate_timestamp,
        }


class TradeGate:
    """
    Pre-trade gating engine.

    Parameters
    ----------
    max_open_positions : int    Max concurrent open trades.
    max_drawdown_pct : float    If drawdown > this, hard block.
    max_portfolio_heat : float  Max portfolio heat %.
    vix_hard_block : float      VIX above this → hard block.
    vix_soft_warn : float       VIX above this → soft warning + size reduction.
    """

    def __init__(
        self,
        max_open_positions: int = RISK.max_positions,
        max_drawdown_pct: float = 0.15,
        max_portfolio_heat: float = 0.06,
        vix_hard_block: float = 45.0,
        vix_soft_warn: float = 25.0,
    ):
        self.max_open_positions = max_open_positions
        self.max_drawdown_pct = max_drawdown_pct
        self.max_portfolio_heat = max_portfolio_heat
        self.vix_hard_block = vix_hard_block
        self.vix_soft_warn = vix_soft_warn

    def evaluate(
        self,
        current_drawdown_pct: float = 0.0,
        open_positions: int = 0,
        portfolio_heat_pct: float = 0.0,
        vix: Optional[float] = None,
        regime: str = "UNKNOWN",
        ticker: Optional[str] = None,
        is_earnings_week: bool = False,
        current_hour_utc: Optional[int] = None,
    ) -> GateResult:
        """Evaluate all gates and return allow/block decision."""
        hard: list[str] = []
        soft: list[str] = []
        multiplier = 1.0

        # ── Hard gates ──────────────────────────────────────────────
        if current_drawdown_pct >= self.max_drawdown_pct:
            hard.append(
                f"Drawdown {current_drawdown_pct:.1%} exceeds "
                f"max {self.max_drawdown_pct:.1%} — "
                f"trading suspended"
            )

        if open_positions >= self.max_open_positions:
            hard.append(
                f"{open_positions} open positions = max "
                f"({self.max_open_positions}) — no new trades"
            )

        if portfolio_heat_pct >= self.max_portfolio_heat:
            hard.append(
                f"Portfolio heat {portfolio_heat_pct:.1%} at maximum "
                f"({self.max_portfolio_heat:.1%})"
            )

        if vix is not None and vix >= self.vix_hard_block:
            hard.append(
                f"VIX at {vix:.1f} — extreme fear, "
                f"hard block (threshold {self.vix_hard_block})"
            )

        # ── Soft gates ──────────────────────────────────────────────
        if vix is not None and vix >= self.vix_soft_warn:
            if vix < self.vix_hard_block:
                reduction = min(0.5, (vix - self.vix_soft_warn) / 40)
                multiplier *= 1.0 - reduction
                soft.append(
                    f"VIX at {vix:.1f} — elevated, " f"size reduced to {multiplier:.0%}"
                )

        if regime in ("UNKNOWN", "TRANSITIONAL", "CONFLICTED"):
            multiplier *= 0.5
            soft.append(f"Regime '{regime}' uncertain — " f"half size recommended")

        if is_earnings_week and ticker:
            multiplier *= 0.5
            soft.append(
                f"{ticker} in earnings week — " f"size halved due to event risk"
            )

        if current_hour_utc is not None:
            if current_hour_utc < 13 or current_hour_utc > 20:
                # Outside US market core hours (9:00–16:00 ET)
                soft.append("Outside core US market hours — " "wider spreads likely")
                multiplier *= 0.8

        # ── Final decision ──────────────────────────────────────────
        allowed = len(hard) == 0
        if not allowed:
            multiplier = 0.0

        return GateResult(
            allowed=allowed,
            hard_blocks=hard,
            soft_warnings=soft,
            size_multiplier=round(multiplier, 2),
        )

    def summary(self) -> dict:
        return {
            "max_open_positions": self.max_open_positions,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_portfolio_heat": self.max_portfolio_heat,
            "vix_hard_block": self.vix_hard_block,
            "vix_soft_warn": self.vix_soft_warn,
        }
