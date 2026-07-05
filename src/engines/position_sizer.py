"""
Position Sizing Engine — Sprint 50
===================================
Kelly-criterion & ATR-based position sizing with hard portfolio limits.
Determines *how much* to allocate per trade, not *whether* to trade.

Key principles (from institutional risk management):
 • Never risk more than a fixed % of equity on a single trade
 • Size inversely to volatility (ATR-based)
 • Apply Kelly fraction (half-Kelly for safety)
 • Respect max-position and max-sector concentration limits
 • Scale down when portfolio heat is elevated
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SizingResult:
    """Output of the position sizer."""

    ticker: str
    shares: int
    dollar_amount: float
    position_pct: float  # % of equity
    risk_per_share: float  # price − stop
    total_risk: float  # risk_per_share × shares
    risk_pct_of_equity: float  # total_risk / equity
    method: str  # "kelly" | "atr_fixed_risk" | "equal_weight"
    notes: list[str] = field(default_factory=list)


class PositionSizer:
    """
    Multi-method position sizer with hard limits.

    Parameters
    ----------
    equity : float          Total account equity.
    max_risk_pct : float    Max % of equity risked per trade (default 1 %).
    max_position_pct : float  Max single-position weight (default 10 %).
    max_portfolio_heat : float  When total open risk > this, scale down new
                                positions (default 6 %).
    current_heat_pct : float  Current portfolio heat as % of equity.
    """

    def __init__(
        self,
        equity: float = 100_000.0,
        max_risk_pct: float = 0.01,
        max_position_pct: float = 0.10,
        max_portfolio_heat: float = 0.06,
        current_heat_pct: float = 0.0,
    ):
        self.equity = max(equity, 1.0)
        self.max_risk_pct = max_risk_pct
        self.max_position_pct = max_position_pct
        self.max_portfolio_heat = max_portfolio_heat
        self.current_heat_pct = current_heat_pct

    # ── Public API ──────────────────────────────────────────────────

    def size_position(
        self,
        ticker: str,
        price: float,
        stop_price: float,
        win_rate: Optional[float] = None,
        avg_win_loss_ratio: Optional[float] = None,
        method: str = "atr_fixed_risk",
    ) -> SizingResult:
        """Compute position size for a single trade."""
        if price <= 0 or stop_price <= 0:
            return self._zero(ticker, "Invalid price or stop")

        risk_per_share = abs(price - stop_price)
        if risk_per_share < 0.01:
            return self._zero(ticker, "Risk per share ≈ 0")

        notes: list[str] = []

        # ── Heat throttle ───────────────────────────────────────────
        heat_remaining = max(0.0, self.max_portfolio_heat - self.current_heat_pct)
        if heat_remaining <= 0:
            return self._zero(ticker, "Portfolio heat at maximum — no new risk")

        heat_scale = min(1.0, heat_remaining / self.max_risk_pct)
        if heat_scale < 1.0:
            notes.append(f"Heat-throttled to {heat_scale:.0%} of normal size")

        # ── Method dispatch ─────────────────────────────────────────
        if (
            method == "kelly"
            and win_rate is not None
            and avg_win_loss_ratio is not None
        ):
            raw_pct = self._kelly(win_rate, avg_win_loss_ratio)
            notes.append(f"Half-Kelly fraction: {raw_pct:.2%}")
        elif method == "equal_weight":
            raw_pct = self.max_position_pct
        else:
            # Fixed-risk: risk max_risk_pct of equity
            raw_pct = (
                (self.max_risk_pct * self.equity)
                / (risk_per_share * (self.equity / price))
                if price > 0
                else 0
            )
            raw_pct = min(raw_pct, self.max_position_pct)
            method = "atr_fixed_risk"

        # Apply limits
        position_pct = min(raw_pct, self.max_position_pct) * heat_scale
        dollar_amount = self.equity * position_pct
        shares = int(dollar_amount / price) if price > 0 else 0

        if shares <= 0:
            return self._zero(ticker, "Computed 0 shares after limits")

        total_risk = risk_per_share * shares
        risk_pct = total_risk / self.equity if self.equity > 0 else 0

        # Hard risk cap
        if risk_pct > self.max_risk_pct:
            shares = int((self.max_risk_pct * self.equity) / risk_per_share)
            total_risk = risk_per_share * shares
            risk_pct = total_risk / self.equity
            notes.append("Shares capped by max-risk-per-trade limit")

        dollar_amount = shares * price
        position_pct = dollar_amount / self.equity

        return SizingResult(
            ticker=ticker,
            shares=shares,
            dollar_amount=round(dollar_amount, 2),
            position_pct=round(position_pct, 4),
            risk_per_share=round(risk_per_share, 2),
            total_risk=round(total_risk, 2),
            risk_pct_of_equity=round(risk_pct, 4),
            method=method,
            notes=notes,
        )

    # ── Kelly criterion ─────────────────────────────────────────────

    @staticmethod
    def _kelly(win_rate: float, avg_win_loss_ratio: float) -> float:
        """Half-Kelly fraction: f* = (p × b − q) / b / 2."""
        p = max(0.0, min(1.0, win_rate))
        b = max(0.01, avg_win_loss_ratio)
        q = 1 - p
        full_kelly = (p * b - q) / b
        if full_kelly <= 0:
            return 0.0
        return full_kelly / 2  # half-Kelly for safety

    # ── Helpers ─────────────────────────────────────────────────────

    def _zero(self, ticker: str, reason: str) -> SizingResult:
        return SizingResult(
            ticker=ticker,
            shares=0,
            dollar_amount=0.0,
            position_pct=0.0,
            risk_per_share=0.0,
            total_risk=0.0,
            risk_pct_of_equity=0.0,
            method="none",
            notes=[reason],
        )

    def summary(self) -> dict:
        return {
            "equity": self.equity,
            "max_risk_pct": self.max_risk_pct,
            "max_position_pct": self.max_position_pct,
            "max_portfolio_heat": self.max_portfolio_heat,
            "current_heat_pct": self.current_heat_pct,
        }
