"""
CC — Portfolio Heat Engine

Tracks portfolio-level exposure, concentration, and risk state.
Promotes portfolio intelligence from metadata to primary decision surface.

Key concepts:
- Portfolio Heat: total risk budget consumed (0-100%)
- Exposure Map: sector, beta, theme, correlation, event proximity
- Throttle State: normal / half_size / starter_only / no_new_longs / reduce_gross
- Correlated Cluster Cap: max names from same correlation bucket
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# ═══════════════════════════════════════════════════════════════════
# THROTTLE STATES — dynamic risk throttles
# ═══════════════════════════════════════════════════════════════════


class ThrottleState:
    """Portfolio-level throttle (Section 8 of review)."""

    NORMAL = "normal"
    HALF_SIZE = "half_size"
    STARTER_ONLY = "starter_only"
    NO_NEW_LONGS = "no_new_longs"
    REDUCE_GROSS = "reduce_gross"
    HEDGE_ONLY = "hedge_only"
    NO_TRADE = "no_trade"

    ALL = (
        NORMAL,
        HALF_SIZE,
        STARTER_ONLY,
        NO_NEW_LONGS,
        REDUCE_GROSS,
        HEDGE_ONLY,
        NO_TRADE,
    )


# ═══════════════════════════════════════════════════════════════════
# EXPOSURE SNAPSHOT
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ExposureSnapshot:
    """Point-in-time portfolio exposure state."""

    timestamp: str = ""

    # Gross / net
    gross_exposure_pct: float = 0.0
    net_exposure_pct: float = 0.0
    long_exposure_pct: float = 0.0
    short_exposure_pct: float = 0.0
    cash_pct: float = 100.0

    # Concentration
    sector_weights: Dict[str, float] = field(default_factory=dict)
    top_5_weight_pct: float = 0.0
    max_single_name_pct: float = 0.0
    hhi_concentration: float = 0.0  # Herfindahl-Hirschman

    # Factor exposure
    portfolio_beta: float = 1.0
    avg_correlation: float = 0.0
    max_cluster_correlation: float = 0.0
    correlated_cluster_count: int = 0

    # Event exposure
    positions_near_earnings: int = 0
    positions_near_events: int = 0

    # Risk budget consumed
    heat_pct: float = 0.0  # 0-100
    daily_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    consecutive_losses: int = 0

    # Throttle
    throttle_state: str = ThrottleState.NORMAL
    throttle_reasons: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_exposure_pct": round(self.gross_exposure_pct, 2),
            "net_exposure_pct": round(self.net_exposure_pct, 2),
            "long_exposure_pct": round(self.long_exposure_pct, 2),
            "short_exposure_pct": round(self.short_exposure_pct, 2),
            "cash_pct": round(self.cash_pct, 2),
            "concentration": {
                "sector_weights": {
                    k: round(v, 3) for k, v in self.sector_weights.items()
                },
                "top_5_weight_pct": round(self.top_5_weight_pct, 2),
                "max_single_name_pct": round(self.max_single_name_pct, 2),
                "hhi": round(self.hhi_concentration, 4),
            },
            "factor_exposure": {
                "portfolio_beta": round(self.portfolio_beta, 3),
                "avg_correlation": round(self.avg_correlation, 3),
                "correlated_clusters": self.correlated_cluster_count,
            },
            "event_exposure": {
                "near_earnings": self.positions_near_earnings,
                "near_events": self.positions_near_events,
            },
            "risk_budget": {
                "heat_pct": round(self.heat_pct, 1),
                "daily_pnl_pct": round(self.daily_pnl_pct, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "consecutive_losses": self.consecutive_losses,
            },
            "throttle": {
                "state": self.throttle_state,
                "reasons": self.throttle_reasons,
            },
        }


# ═══════════════════════════════════════════════════════════════════
# PORTFOLIO HEAT ENGINE
# ═══════════════════════════════════════════════════════════════════


@dataclass
class Position:
    """Tracked position for heat calculation."""

    ticker: str
    direction: str = "LONG"
    weight_pct: float = 0.0
    sector: str = "unknown"
    beta: float = 1.0
    entry_date: str = ""
    pnl_pct: float = 0.0
    days_to_earnings: int = 999
    stop_distance_pct: float = 0.02


class PortfolioHeatEngine:
    """
    Calculates portfolio heat, exposure, and throttle state.

    Heat = sum of position risk (weight × stop distance).
    Throttle = dynamic sizing multiplier based on heat + market conditions.
    """

    def __init__(
        self,
        max_heat_pct: float = 15.0,
        max_single_name_pct: float = 5.0,
        max_sector_pct: float = 25.0,
        max_correlated_cluster: int = 3,
        max_positions: int = 15,
        max_beta: float = 1.5,
        daily_loss_limit_pct: float = 3.0,
        max_drawdown_pct: float = 15.0,
        spread_kill_switch_bps: float = 100.0,
        slippage_ceiling_bps: float = 50.0,
    ):
        self.max_heat_pct = max_heat_pct
        self.max_single_name_pct = max_single_name_pct
        self.max_sector_pct = max_sector_pct
        self.max_correlated_cluster = max_correlated_cluster
        self.max_positions = max_positions
        self.max_beta = max_beta
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.spread_kill_switch_bps = spread_kill_switch_bps
        self.slippage_ceiling_bps = slippage_ceiling_bps

        self._positions: Dict[str, Position] = {}
        self._daily_pnl_pct: float = 0.0
        self._peak_equity: float = 100.0
        self._current_equity: float = 100.0
        self._consecutive_losses: int = 0

    # ── Position management ───────────────────────────────────

    def add_position(self, pos: Position) -> None:
        self._positions[pos.ticker] = pos

    def remove_position(self, ticker: str) -> None:
        self._positions.pop(ticker, None)

    def update_pnl(self, daily_pnl_pct: float) -> None:
        self._daily_pnl_pct = daily_pnl_pct
        self._current_equity *= 1 + daily_pnl_pct / 100
        self._peak_equity = max(self._peak_equity, self._current_equity)
        if daily_pnl_pct < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    # ── Snapshot builder ──────────────────────────────────────

    def snapshot(self) -> ExposureSnapshot:
        """Build current exposure snapshot."""
        positions = list(self._positions.values())

        if not positions:
            return ExposureSnapshot(
                cash_pct=100.0,
                throttle_state=ThrottleState.NORMAL,
            )

        # Weights
        long_w = sum(p.weight_pct for p in positions if p.direction == "LONG")
        short_w = sum(p.weight_pct for p in positions if p.direction == "SHORT")
        gross = long_w + short_w
        net = long_w - short_w
        cash = max(0.0, 100.0 - gross)

        # Sector weights
        sector_w: Dict[str, float] = {}
        for p in positions:
            sector_w[p.sector] = sector_w.get(p.sector, 0) + p.weight_pct

        # Concentration
        sorted_weights = sorted([p.weight_pct for p in positions], reverse=True)
        top5 = sum(sorted_weights[:5])
        max_name = sorted_weights[0] if sorted_weights else 0
        hhi = sum(w**2 for w in sorted_weights) / (gross**2) if gross > 0 else 0

        # Beta
        weighted_beta = (
            sum(p.weight_pct * p.beta for p in positions) / gross if gross > 0 else 1.0
        )

        # Heat = sum of risk at stop
        heat = sum(p.weight_pct * p.stop_distance_pct for p in positions)
        heat_pct = heat * 100  # convert to percentage points

        # Events
        near_earnings = sum(1 for p in positions if p.days_to_earnings <= 2)

        # Drawdown
        dd = (
            (self._peak_equity - self._current_equity) / self._peak_equity * 100
            if self._peak_equity > 0
            else 0
        )

        # Throttle
        throttle, reasons = self._compute_throttle(
            heat_pct,
            gross,
            weighted_beta,
            dd,
            self._daily_pnl_pct,
            self._consecutive_losses,
            near_earnings,
            len(positions),
        )

        return ExposureSnapshot(
            gross_exposure_pct=gross,
            net_exposure_pct=net,
            long_exposure_pct=long_w,
            short_exposure_pct=short_w,
            cash_pct=cash,
            sector_weights=sector_w,
            top_5_weight_pct=top5,
            max_single_name_pct=max_name,
            hhi_concentration=hhi,
            portfolio_beta=weighted_beta,
            positions_near_earnings=near_earnings,
            heat_pct=heat_pct,
            daily_pnl_pct=self._daily_pnl_pct,
            max_drawdown_pct=dd,
            consecutive_losses=self._consecutive_losses,
            throttle_state=throttle,
            throttle_reasons=reasons,
        )

    # ── Marginal risk check ───────────────────────────────────

    def check_new_position(
        self,
        ticker: str,
        sector: str,
        weight_pct: float,
        beta: float,
        spread_bps: float = 0.0,
        avg_slippage_bps: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Check if a new position would breach any limits.
        Includes spread/liquidity kill switch and slippage ceiling.
        Returns approval status + reasons.
        """
        snap = self.snapshot()
        issues: list = []

        # Spread / liquidity kill switch
        if spread_bps > self.spread_kill_switch_bps:
            issues.append(
                f"Spread {spread_bps:.0f}bps > kill switch "
                f"{self.spread_kill_switch_bps:.0f}bps"
            )

        # Execution slippage ceiling
        if avg_slippage_bps > self.slippage_ceiling_bps:
            issues.append(
                f"Avg slippage {avg_slippage_bps:.0f}bps > "
                f"ceiling {self.slippage_ceiling_bps:.0f}bps"
            )

        # Single name
        if weight_pct > self.max_single_name_pct:
            issues.append(f"Weight {weight_pct:.1f}% > max {self.max_single_name_pct}%")

        # Sector
        current_sector = snap.sector_weights.get(sector, 0)
        if current_sector + weight_pct > self.max_sector_pct:
            issues.append(
                f"Sector {sector} would be "
                f"{current_sector + weight_pct:.1f}% > max {self.max_sector_pct}%"
            )

        # Position count
        if len(self._positions) >= self.max_positions:
            issues.append(
                f"Already {len(self._positions)} positions (max {self.max_positions})"
            )

        # Gross
        if snap.gross_exposure_pct + weight_pct > 100.0:
            issues.append("Would exceed 100% gross exposure")

        # Throttle gate
        if snap.throttle_state == ThrottleState.NO_TRADE:
            issues.append("Portfolio in NO_TRADE throttle state")
        elif snap.throttle_state == ThrottleState.NO_NEW_LONGS:
            issues.append("Portfolio in NO_NEW_LONGS throttle state")
        elif snap.throttle_state == ThrottleState.HEDGE_ONLY:
            issues.append("Portfolio in HEDGE_ONLY throttle state")

        return {
            "approved": len(issues) == 0,
            "issues": issues,
            "current_heat_pct": round(snap.heat_pct, 1),
            "throttle_state": snap.throttle_state,
        }

    # ── Internal ──────────────────────────────────────────────

    def _compute_throttle(
        self,
        heat_pct: float,
        gross: float,
        beta: float,
        drawdown: float,
        daily_pnl: float,
        consec_losses: int,
        near_earnings: int,
        position_count: int,
    ) -> tuple:
        reasons = []

        # Kill switches
        if daily_pnl < -self.daily_loss_limit_pct:
            reasons.append(
                f"Daily loss {daily_pnl:.1f}% > limit {self.daily_loss_limit_pct}%"
            )
            return ThrottleState.NO_TRADE, reasons

        if drawdown > self.max_drawdown_pct:
            reasons.append(f"Drawdown {drawdown:.1f}% > max {self.max_drawdown_pct}%")
            return ThrottleState.REDUCE_GROSS, reasons

        if consec_losses >= 5:
            reasons.append(f"{consec_losses} consecutive losses")
            return ThrottleState.STARTER_ONLY, reasons

        # Graduated throttle
        if heat_pct > self.max_heat_pct * 0.9:
            reasons.append(f"Heat {heat_pct:.1f}% near max")
            return ThrottleState.HALF_SIZE, reasons

        if beta > self.max_beta:
            reasons.append(f"Portfolio beta {beta:.2f} > max {self.max_beta}")
            return ThrottleState.HALF_SIZE, reasons

        if gross > 80:
            reasons.append(f"Gross exposure {gross:.0f}% high")
            return ThrottleState.HALF_SIZE, reasons

        return ThrottleState.NORMAL, reasons


# ── Module singleton ──────────────────────────────────────────
_heat_engine: Optional[PortfolioHeatEngine] = None


def get_portfolio_heat_engine() -> PortfolioHeatEngine:
    global _heat_engine
    if _heat_engine is None:
        from src.core.risk_limits import RISK

        _heat_engine = PortfolioHeatEngine(
            max_heat_pct=RISK.max_drawdown_pct,
            max_single_name_pct=RISK.max_position_pct,
            max_sector_pct=RISK.max_sector_pct,
            max_positions=RISK.max_positions,
            daily_loss_limit_pct=RISK.daily_loss_limit_pct,
            max_drawdown_pct=RISK.max_drawdown_pct,
        )
    return _heat_engine
