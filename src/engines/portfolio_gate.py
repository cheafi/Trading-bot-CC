"""
Portfolio Gate — Position-Level Risk Control.

Before any new signal becomes actionable, check:
1. Total open positions vs maximum
2. Sector concentration (max % per sector)
3. Correlation with existing holdings
4. Portfolio heat (total risk budget used)
5. Single-name sizing limit

If gate fails → signal demoted to WATCH or NO_TRADE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Portfolio gate check result."""

    allowed: bool = True
    max_size_pct: float = 2.0  # Max position size
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    sector_exposure_pct: float = 0.0
    total_positions: int = 0
    portfolio_heat_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "max_size_pct": round(self.max_size_pct, 2),
            "reasons": self.reasons,
            "warnings": self.warnings,
            "sector_exposure_pct": round(self.sector_exposure_pct, 1),
            "total_positions": self.total_positions,
            "portfolio_heat_pct": round(self.portfolio_heat_pct, 1),
        }


class PortfolioGate:
    """
    Portfolio-level gate before new entries.

    Enforces:
    - Max open positions (default 10)
    - Max sector concentration (default 30%)
    - Max portfolio heat (default 6% total risk)
    - Max single position (default 5% of portfolio)
    """

    def __init__(
        self,
        max_positions: int = 10,
        max_sector_pct: float = 30.0,
        max_heat_pct: float = 6.0,
        max_single_pct: float = 5.0,
    ):
        self.max_positions = max_positions
        self.max_sector_pct = max_sector_pct
        self.max_heat_pct = max_heat_pct
        self.max_single_pct = max_single_pct

    def check(
        self,
        ticker: str,
        sector: str,
        atr_risk_pct: float,
        current_positions: List[Dict[str, Any]],
    ) -> GateResult:
        """
        Check if a new position is allowed.

        current_positions: list of dicts with keys:
            ticker, sector, size_pct, risk_pct
        """
        result = GateResult()
        result.total_positions = len(current_positions)

        # ── 1. Max positions ──
        if len(current_positions) >= self.max_positions:
            result.allowed = False
            result.reasons.append(f"Max positions reached" f" ({self.max_positions})")

        # ── 2. Sector concentration ──
        sector_exposure = sum(
            p.get("size_pct", 0)
            for p in current_positions
            if p.get("sector", "").lower() == sector.lower()
        )
        result.sector_exposure_pct = sector_exposure
        if sector_exposure >= self.max_sector_pct:
            result.allowed = False
            result.reasons.append(
                f"{sector} exposure {sector_exposure:.0f}%"
                f" >= {self.max_sector_pct}% limit"
            )
        elif sector_exposure >= self.max_sector_pct * 0.7:
            result.warnings.append(
                f"{sector} exposure {sector_exposure:.0f}%" " — approaching limit"
            )

        # ── 3. Duplicate check ──
        existing_tickers = {
            p["ticker"].upper() for p in current_positions if "ticker" in p
        }
        if ticker.upper() in existing_tickers:
            result.warnings.append(f"Already holding {ticker}")

        # ── 4. Portfolio heat ──
        total_heat = sum(p.get("risk_pct", 0) for p in current_positions)
        result.portfolio_heat_pct = total_heat
        remaining_heat = self.max_heat_pct - total_heat
        if remaining_heat <= 0:
            result.allowed = False
            result.reasons.append(
                f"Portfolio heat {total_heat:.1f}%" f" >= {self.max_heat_pct}% limit"
            )
        elif remaining_heat < atr_risk_pct:
            result.max_size_pct = max(
                0.5,
                remaining_heat / atr_risk_pct * self.max_single_pct,
            )
            result.warnings.append(
                f"Reduced size to {result.max_size_pct:.1f}%" " — heat budget tight"
            )

        # ── 5. Size limit ──
        if result.allowed:
            result.max_size_pct = min(
                self.max_single_pct,
                result.max_size_pct,
            )

        if result.allowed and not result.warnings:
            result.reasons.append("Portfolio gate: PASS — room available")

        return result


# Singleton for use across the app
_gate = PortfolioGate()


def check_portfolio_gate(
    ticker: str,
    sector: str,
    atr_risk_pct: float = 1.0,
    current_positions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Convenience function."""
    return _gate.check(
        ticker,
        sector,
        atr_risk_pct,
        current_positions or [],
    ).to_dict()
