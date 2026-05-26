"""
Drawdown Circuit Breaker — Sprint 64
======================================
Monitors portfolio drawdown and reduces position sizes
when the portfolio is losing money.

Rules:
  - Down 3% this week  → reduce new position sizes by 30%
  - Down 5% this week  → reduce by 50%
  - Down 8% this week  → reduce by 75%
  - Down 10%+ this week → HALT new entries entirely

Usage:
    breaker = DrawdownCircuitBreaker()
    multiplier = breaker.get_size_multiplier(
        current_value=95000, peak_value=100000, period_start_value=98000
    )
    # multiplier = 0.7 (30% reduction)
    adjusted_size = original_size * multiplier
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CircuitBreakerResult:
    """Output of circuit breaker check."""
    size_multiplier: float = 1.0   # 0.0 = halt, 1.0 = normal
    drawdown_pct: float = 0.0     # Current drawdown from peak
    weekly_pnl_pct: float = 0.0   # This week's P&L
    level: str = "NORMAL"         # NORMAL / CAUTION / REDUCED / HALT
    reason: str = ""
    new_entries_allowed: bool = True

    def to_dict(self) -> dict:
        return {
            "size_multiplier": round(self.size_multiplier, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "weekly_pnl_pct": round(self.weekly_pnl_pct, 2),
            "level": self.level,
            "reason": self.reason,
            "new_entries_allowed": self.new_entries_allowed,
        }


class DrawdownCircuitBreaker:
    """
    Portfolio-level circuit breaker that throttles position
    sizing during drawdowns.
    """

    # Weekly drawdown thresholds → size multipliers
    THRESHOLDS = [
        (-3.0, 0.70, "CAUTION"),   # -3% → 30% reduction
        (-5.0, 0.50, "REDUCED"),   # -5% → 50% reduction
        (-8.0, 0.25, "REDUCED"),   # -8% → 75% reduction
        (-10.0, 0.0, "HALT"),      # -10% → no new entries
    ]

    def check(
        self,
        current_value: float,
        peak_value: float = 0.0,
        period_start_value: float = 0.0,
    ) -> CircuitBreakerResult:
        """
        Check circuit breaker status.

        Args:
            current_value: Current portfolio value
            peak_value: All-time high portfolio value
            period_start_value: Portfolio value at start of week
        """
        result = CircuitBreakerResult()

        # Drawdown from peak
        if peak_value > 0:
            result.drawdown_pct = (
                (current_value - peak_value) / peak_value * 100
            )

        # Weekly P&L
        if period_start_value > 0:
            result.weekly_pnl_pct = (
                (current_value - period_start_value)
                / period_start_value * 100
            )
        else:
            # Use drawdown if no weekly start
            result.weekly_pnl_pct = result.drawdown_pct

        # Apply thresholds (check from most severe to least)
        weekly = result.weekly_pnl_pct
        for threshold, multiplier, level in reversed(self.THRESHOLDS):
            if weekly <= threshold:
                result.size_multiplier = multiplier
                result.level = level
                result.new_entries_allowed = multiplier > 0
                result.reason = (
                    f"Portfolio down {abs(weekly):.1f}% this week "
                    f"(threshold {abs(threshold):.0f}%)"
                )
                break

        if not result.reason:
            result.level = "NORMAL"
            result.reason = "Within normal parameters"

        return result

    def adjust_size(
        self,
        base_size_pct: float,
        current_value: float,
        peak_value: float = 0.0,
        period_start_value: float = 0.0,
    ) -> tuple[float, CircuitBreakerResult]:
        """
        Adjust a position size through the circuit breaker.
        Returns (adjusted_size_pct, result).
        """
        result = self.check(current_value, peak_value, period_start_value)
        adjusted = round(base_size_pct * result.size_multiplier, 2)
        return adjusted, result
