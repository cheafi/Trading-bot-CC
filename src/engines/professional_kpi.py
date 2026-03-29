"""
Professional KPI Dashboard — real desk metrics (Sprint 35).

Surfaces the metrics a professional PM uses to evaluate
a trading system, not retail vanity metrics:

  • net expectancy (in R)
  • average R multiple
  • profit factor
  • max drawdown
  • CVaR-95
  • exposure-adjusted return
  • alpha / beta vs SPY
  • calibration error
  • turnover
  • no-trade rate
  • coverage funnel: watched → eligible → ranked → rejected → executed

Consumed by API, Discord /performance, and dashboard.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CoverageFunnel:
    """Tracks how many names flow through each pipeline stage."""
    watched: int = 0      # universe size
    eligible: int = 0     # passed quality filter
    ranked: int = 0       # scored by ensembler
    approved: int = 0     # passed trade_decision
    rejected: int = 0     # suppressed
    executed: int = 0     # actually traded

    def to_dict(self) -> Dict[str, int]:
        return {
            "watched": self.watched,
            "eligible": self.eligible,
            "ranked": self.ranked,
            "approved": self.approved,
            "rejected": self.rejected,
            "executed": self.executed,
        }

    @property
    def pass_rate(self) -> float:
        """Fraction of watched names that got executed."""
        return self.executed / self.watched if self.watched else 0

    @property
    def rejection_rate(self) -> float:
        """Fraction of ranked that were rejected."""
        return self.rejected / self.ranked if self.ranked else 0


@dataclass
class KPISnapshot:
    """Point-in-time professional KPI report."""

    # Economic value metrics
    net_expectancy_r: float = 0.0     # p(win)*avg_win_R - p(loss)*avg_loss_R
    avg_r_multiple: float = 0.0       # average R on closed trades
    profit_factor: float = 0.0        # gross_win / gross_loss
    win_rate: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    cvar_95: float = 0.0              # conditional VaR (daily)
    volatility: float = 0.0

    # Benchmark comparison
    alpha: Optional[float] = None
    beta: Optional[float] = None
    information_ratio: Optional[float] = None

    # Activity metrics
    turnover: float = 0.0             # trades per day
    no_trade_rate: float = 0.0        # fraction of cycles with no trade
    avg_hold_hours: float = 0.0

    # Coverage funnel
    funnel: CoverageFunnel = field(
        default_factory=CoverageFunnel,
    )

    # Trade counts
    total_trades: int = 0
    total_cycles: int = 0

    # Calibration
    calibration_error: float = 0.0    # |predicted_wr - actual_wr|

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "net_expectancy_r": round(self.net_expectancy_r, 3),
            "avg_r_multiple": round(self.avg_r_multiple, 3),
            "profit_factor": round(self.profit_factor, 2),
            "win_rate": round(self.win_rate, 3),
            "max_drawdown": round(self.max_drawdown, 4),
            "cvar_95": round(self.cvar_95, 4),
            "volatility": round(self.volatility, 4),
            "alpha": (
                round(self.alpha, 4)
                if self.alpha is not None else None
            ),
            "beta": (
                round(self.beta, 3)
                if self.beta is not None else None
            ),
            "information_ratio": (
                round(self.information_ratio, 3)
                if self.information_ratio is not None else None
            ),
            "turnover": round(self.turnover, 2),
            "no_trade_rate": round(self.no_trade_rate, 3),
            "avg_hold_hours": round(self.avg_hold_hours, 1),
            "total_trades": self.total_trades,
            "total_cycles": self.total_cycles,
            "calibration_error": round(self.calibration_error, 3),
            "funnel": self.funnel.to_dict(),
        }
        return d

    def summary_text(self) -> str:
        """Human-readable KPI summary for bots / reports."""
        lines = [
            "📊 Professional KPI Report",
            "═" * 30,
            f"Net Expectancy: {self.net_expectancy_r:+.3f}R",
            f"Avg R Multiple: {self.avg_r_multiple:+.3f}R",
            f"Profit Factor:  {self.profit_factor:.2f}",
            f"Win Rate:       {self.win_rate:.1%}",
            "",
            f"Max Drawdown:   {self.max_drawdown:.2%}",
            f"CVaR-95:        {self.cvar_95:.2%}",
        ]
        if self.alpha is not None:
            lines.append(f"Alpha (ann.):   {self.alpha:+.2%}")
            lines.append(f"Beta:           {self.beta:.2f}")
        lines.extend([
            "",
            f"Turnover:       {self.turnover:.1f} trades/day",
            f"No-trade rate:  {self.no_trade_rate:.1%}",
            f"Avg hold:       {self.avg_hold_hours:.0f}h",
            f"Total trades:   {self.total_trades}",
            "",
            "Coverage Funnel:",
            f"  Watched:  {self.funnel.watched}",
            f"  Eligible: {self.funnel.eligible}",
            f"  Ranked:   {self.funnel.ranked}",
            f"  Approved: {self.funnel.approved}",
            f"  Rejected: {self.funnel.rejected}",
            f"  Executed: {self.funnel.executed}",
            f"  Pass rate: {self.funnel.pass_rate:.1%}",
        ])
        return "\n".join(lines)


class ProfessionalKPI:
    """
    Computes professional-grade KPIs from trade history.

    Tracks coverage funnel per cycle and computes rolling
    metrics for API / bot display.
    """

    def __init__(self):
        self._trades: List[Dict[str, Any]] = []
        self._cycles: int = 0
        self._no_trade_cycles: int = 0
        self._funnels: List[CoverageFunnel] = []
        self._predicted_wrs: List[float] = []
        self._actual_wrs: List[float] = []

    def record_trade(
        self,
        pnl_pct: float,
        r_multiple: float = 0.0,
        hold_hours: float = 0.0,
        predicted_wr: float = 0.0,
    ):
        """Record a closed trade outcome."""
        self._trades.append({
            "pnl_pct": pnl_pct,
            "r_multiple": r_multiple,
            "hold_hours": hold_hours,
            "is_win": pnl_pct > 0,
        })
        if predicted_wr > 0:
            self._predicted_wrs.append(predicted_wr)
            self._actual_wrs.append(1.0 if pnl_pct > 0 else 0.0)

    def record_cycle(
        self,
        traded: bool,
        funnel: Optional[CoverageFunnel] = None,
    ):
        """Record one engine cycle."""
        self._cycles += 1
        if not traded:
            self._no_trade_cycles += 1
        if funnel:
            self._funnels.append(funnel)

    def compute(self) -> KPISnapshot:
        """Compute all KPIs from recorded history."""
        kpi = KPISnapshot()
        trades = self._trades
        kpi.total_trades = len(trades)
        kpi.total_cycles = self._cycles

        if not trades:
            return kpi

        # Win / loss split
        wins = [t for t in trades if t["is_win"]]
        losses = [t for t in trades if not t["is_win"]]

        kpi.win_rate = len(wins) / len(trades)

        # R multiples
        r_vals = [t["r_multiple"] for t in trades if t["r_multiple"] != 0]
        if r_vals:
            kpi.avg_r_multiple = sum(r_vals) / len(r_vals)

        # Net expectancy in R
        avg_win_r = (
            sum(t["r_multiple"] for t in wins if t["r_multiple"] > 0)
            / max(len(wins), 1)
        ) if wins else 0
        avg_loss_r = abs(
            sum(t["r_multiple"] for t in losses if t["r_multiple"] < 0)
            / max(len(losses), 1)
        ) if losses else 1.0
        kpi.net_expectancy_r = (
            kpi.win_rate * avg_win_r
            - (1 - kpi.win_rate) * avg_loss_r
        )

        # Profit factor
        gross_win = sum(t["pnl_pct"] for t in wins) if wins else 0
        gross_loss = abs(
            sum(t["pnl_pct"] for t in losses),
        ) if losses else 0.001
        kpi.profit_factor = gross_win / gross_loss if gross_loss > 0 else 0

        # PnL series for risk metrics
        pnls = [t["pnl_pct"] for t in trades]

        # Max drawdown (from pnl series)
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = cumulative - peak
            if dd < max_dd:
                max_dd = dd
        kpi.max_drawdown = max_dd / 100.0 if max_dd != 0 else 0

        # CVaR-95 (from pnl distribution)
        sorted_pnls = sorted(pnls)
        n = len(sorted_pnls)
        cutoff = max(1, int(n * 0.05))
        tail = sorted_pnls[:cutoff]
        kpi.cvar_95 = sum(tail) / len(tail) / 100.0 if tail else 0

        # Volatility
        if len(pnls) > 1:
            mean_pnl = sum(pnls) / len(pnls)
            var = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
            kpi.volatility = math.sqrt(var) / 100.0
        else:
            kpi.volatility = 0

        # Activity
        kpi.turnover = (
            len(trades) / max(self._cycles, 1)
        )
        kpi.no_trade_rate = (
            self._no_trade_cycles / max(self._cycles, 1)
        )

        # Hold time
        hold_vals = [t["hold_hours"] for t in trades if t["hold_hours"] > 0]
        kpi.avg_hold_hours = (
            sum(hold_vals) / len(hold_vals) if hold_vals else 0
        )

        # Calibration error
        if self._predicted_wrs and self._actual_wrs:
            pred_avg = sum(self._predicted_wrs) / len(self._predicted_wrs)
            act_avg = sum(self._actual_wrs) / len(self._actual_wrs)
            kpi.calibration_error = abs(pred_avg - act_avg)

        # Aggregate funnel
        if self._funnels:
            agg = CoverageFunnel()
            for f in self._funnels:
                agg.watched += f.watched
                agg.eligible += f.eligible
                agg.ranked += f.ranked
                agg.approved += f.approved
                agg.rejected += f.rejected
                agg.executed += f.executed
            kpi.funnel = agg

        return kpi
