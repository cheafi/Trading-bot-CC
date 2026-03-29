"""
Monthly Scorecard Builder (Sprint 38).

Aggregates trade outcomes, KPIs, and coverage data into
a monthly performance report card.

Consumed by:
  - Discord ``/scorecard`` command
  - API ``/api/v1/scorecard``
  - Telegram monthly notification
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MonthlyScorecard:
    """One month's aggregated performance."""

    # Period
    month: str = ""          # "2026-03"
    start_date: str = ""
    end_date: str = ""

    # Returns
    total_return_pct: float = 0.0
    gross_return_pct: float = 0.0
    fees_pct: float = 0.0
    best_day_pct: float = 0.0
    worst_day_pct: float = 0.0

    # Activity
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_hold_hours: float = 0.0

    # Risk
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_r_multiple: float = 0.0

    # Coverage
    total_cycles: int = 0
    no_trade_cycles: int = 0
    no_trade_rate: float = 0.0

    # Strategy breakdown
    strategy_breakdown: Dict[str, Dict[str, Any]] = field(
        default_factory=dict,
    )

    # Top winners / losers
    top_winners: List[Dict[str, Any]] = field(
        default_factory=list,
    )
    top_losers: List[Dict[str, Any]] = field(
        default_factory=list,
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "month": self.month,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_return_pct": round(
                self.total_return_pct, 2,
            ),
            "gross_return_pct": round(
                self.gross_return_pct, 2,
            ),
            "fees_pct": round(self.fees_pct, 3),
            "best_day_pct": round(self.best_day_pct, 2),
            "worst_day_pct": round(self.worst_day_pct, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 3),
            "avg_hold_hours": round(self.avg_hold_hours, 1),
            "max_drawdown_pct": round(
                self.max_drawdown_pct, 2,
            ),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_r_multiple": round(self.avg_r_multiple, 3),
            "total_cycles": self.total_cycles,
            "no_trade_cycles": self.no_trade_cycles,
            "no_trade_rate": round(self.no_trade_rate, 3),
            "strategy_breakdown": self.strategy_breakdown,
            "top_winners": self.top_winners[:5],
            "top_losers": self.top_losers[:5],
        }

    def format_text(self) -> str:
        """Render as plain text for Discord / Telegram."""
        lines = [
            f"\U0001f4c5 Monthly Scorecard \u2014 {self.month}",
            "\u2550" * 34,
            "",
            "\U0001f4b0 Returns",
            f"  Total: {self.total_return_pct:+.2f}%",
            f"  Gross: {self.gross_return_pct:+.2f}% "
            f"(fees: {self.fees_pct:.3f}%)",
            f"  Best day: {self.best_day_pct:+.2f}% "
            f"| Worst: {self.worst_day_pct:+.2f}%",
            "",
            "\u2694\ufe0f Activity",
            f"  Trades: {self.total_trades} "
            f"(W: {self.winning_trades} / "
            f"L: {self.losing_trades})",
            f"  Win rate: {self.win_rate:.1%}",
            f"  Avg hold: {self.avg_hold_hours:.0f}h",
            "",
            "\U0001f6e1\ufe0f Risk",
            f"  Max DD: {self.max_drawdown_pct:.2f}%",
            f"  Sharpe: {self.sharpe_ratio:.2f}",
            f"  Profit factor: {self.profit_factor:.2f}",
            f"  Avg R: {self.avg_r_multiple:+.3f}R",
        ]

        if self.strategy_breakdown:
            lines.extend(["", "\U0001f3c6 Strategy Breakdown"])
            for name, stats in sorted(
                self.strategy_breakdown.items(),
                key=lambda x: -x[1].get("pnl", 0),
            )[:5]:
                pnl = stats.get("pnl", 0)
                trades = stats.get("trades", 0)
                wr = stats.get("win_rate", 0)
                emoji = "\U0001f7e2" if pnl > 0 else "\U0001f534"
                lines.append(
                    f"  {emoji} {name}: "
                    f"{pnl:+.2f}% ({trades}T, "
                    f"{wr:.0%} WR)"
                )

        if self.top_winners:
            lines.extend(["", "\u2b50 Top Winners"])
            for w in self.top_winners[:3]:
                lines.append(
                    f"  {w['ticker']}: "
                    f"{w['pnl_pct']:+.2f}%"
                )

        if self.top_losers:
            lines.extend(["", "\U0001f4a5 Top Losers"])
            for lo in self.top_losers[:3]:
                lines.append(
                    f"  {lo['ticker']}: "
                    f"{lo['pnl_pct']:+.2f}%"
                )

        return "\n".join(lines)


class MonthlyScorecardBuilder:
    """Builds monthly scorecard from trade history."""

    def build(
        self,
        trades: List[Dict[str, Any]],
        cycles: int = 0,
        no_trade_cycles: int = 0,
        month: Optional[str] = None,
    ) -> MonthlyScorecard:
        """Build scorecard from closed trades.

        Args:
            trades: list of dicts with pnl_pct, r_multiple,
                    ticker, strategy_id, hold_hours, fees_pct
            cycles: total engine cycles this month
            no_trade_cycles: cycles with no trade
            month: "YYYY-MM" string, defaults to current
        """
        now = datetime.now(timezone.utc)
        card = MonthlyScorecard(
            month=month or now.strftime("%Y-%m"),
            total_cycles=cycles,
            no_trade_cycles=no_trade_cycles,
        )

        if not trades:
            return card

        pnls = [t.get("pnl_pct", 0) for t in trades]
        card.total_trades = len(trades)
        card.total_return_pct = sum(pnls)
        card.gross_return_pct = sum(
            t.get("gross_pnl_pct", t.get("pnl_pct", 0))
            for t in trades
        )
        card.fees_pct = sum(
            t.get("fees_pct", 0) for t in trades
        )
        card.best_day_pct = max(pnls) if pnls else 0
        card.worst_day_pct = min(pnls) if pnls else 0

        wins = [t for t in trades if t.get("pnl_pct", 0) > 0]
        losses = [
            t for t in trades if t.get("pnl_pct", 0) <= 0
        ]
        card.winning_trades = len(wins)
        card.losing_trades = len(losses)
        card.win_rate = (
            len(wins) / len(trades) if trades else 0
        )

        holds = [
            t.get("hold_hours", 0) for t in trades
            if t.get("hold_hours", 0) > 0
        ]
        card.avg_hold_hours = (
            sum(holds) / len(holds) if holds else 0
        )

        # R multiples
        r_vals = [
            t.get("r_multiple", 0) for t in trades
            if t.get("r_multiple", 0) != 0
        ]
        card.avg_r_multiple = (
            sum(r_vals) / len(r_vals) if r_vals else 0
        )

        # Profit factor
        gross_win = sum(
            t["pnl_pct"] for t in wins
        ) if wins else 0
        gross_loss = abs(sum(
            t["pnl_pct"] for t in losses
        )) if losses else 0.001
        card.profit_factor = (
            gross_win / gross_loss if gross_loss > 0 else 0
        )

        # Max drawdown
        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cum += p
            if cum > peak:
                peak = cum
            dd = cum - peak
            if dd < max_dd:
                max_dd = dd
        card.max_drawdown_pct = max_dd

        # Sharpe (simplified)
        import math
        mean_pnl = sum(pnls) / len(pnls)
        if len(pnls) > 1:
            var = sum(
                (p - mean_pnl) ** 2 for p in pnls
            ) / (len(pnls) - 1)
            std = math.sqrt(var) if var > 0 else 0.001
            card.sharpe_ratio = mean_pnl / std
        else:
            card.sharpe_ratio = 0

        # No-trade rate
        card.no_trade_rate = (
            no_trade_cycles / max(cycles, 1)
        )

        # Strategy breakdown
        strat_map: Dict[str, List[float]] = {}
        for t in trades:
            sid = t.get("strategy_id", "unknown")
            strat_map.setdefault(sid, []).append(
                t.get("pnl_pct", 0)
            )
        for sid, pnl_list in strat_map.items():
            w = sum(1 for p in pnl_list if p > 0)
            card.strategy_breakdown[sid] = {
                "trades": len(pnl_list),
                "pnl": round(sum(pnl_list), 2),
                "win_rate": w / len(pnl_list),
            }

        # Top winners / losers
        sorted_trades = sorted(
            trades, key=lambda t: t.get("pnl_pct", 0),
            reverse=True,
        )
        card.top_winners = [
            {
                "ticker": t.get("ticker", "?"),
                "pnl_pct": t.get("pnl_pct", 0),
            }
            for t in sorted_trades[:5]
            if t.get("pnl_pct", 0) > 0
        ]
        card.top_losers = [
            {
                "ticker": t.get("ticker", "?"),
                "pnl_pct": t.get("pnl_pct", 0),
            }
            for t in reversed(sorted_trades)
            if t.get("pnl_pct", 0) < 0
        ][:5]

        return card
