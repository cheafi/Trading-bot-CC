"""
Pipeline Backtester (Phase E)

Runs SectorPipeline.process() on historical enriched signals,
tracks outcomes by action/grade/sector, and produces a
CalibrationReport + attribution breakdown.

This is the "end-to-end truth test": feed real OHLCV data through
SignalEnricher → SectorPipeline → Decision → track P&L.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PipelineTrade:
    """A trade produced by running the full pipeline on historical data."""

    ticker: str
    action: str  # TRADE / WATCH / AVOID
    grade: str  # A / B / C / D
    sector: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_pct: float
    entry_date: str
    # Outcome (filled after forward walk)
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    pnl_pct: float = 0.0
    hit_target: bool = False
    hit_stop: bool = False
    outcome: str = "pending"  # "win", "loss", "scratch", "pending"


@dataclass
class PipelineBacktestResult:
    """Results from pipeline backtester."""

    total_signals: int
    trade_signals: int  # action == TRADE
    watch_signals: int
    avoid_signals: int

    # Outcome tracking (only TRADE signals)
    trades_taken: int
    wins: int
    losses: int
    scratches: int  # |pnl| < 0.5%
    win_rate: float
    avg_pnl_pct: float
    total_pnl_pct: float

    # By grade
    by_grade: Dict[str, Dict[str, Any]]
    # By sector
    by_sector: Dict[str, Dict[str, Any]]

    # Confidence calibration data
    calibration_trades: List[Dict[str, Any]]

    def summary(self) -> str:
        lines = [
            "Pipeline Backtest Results",
            "=" * 40,
            f"Total signals processed: {self.total_signals}",
            f"  TRADE: {self.trade_signals}  WATCH: {self.watch_signals}  AVOID: {self.avoid_signals}",
            "",
            f"Trades taken: {self.trades_taken}",
            f"  Wins: {self.wins}  Losses: {self.losses}  Scratches: {self.scratches}",
            f"  Win rate: {self.win_rate:.1%}",
            f"  Avg P&L: {self.avg_pnl_pct:.2%}",
            f"  Total P&L: {self.total_pnl_pct:.2%}",
            "",
            "By Grade:",
        ]
        for grade in sorted(self.by_grade.keys()):
            g = self.by_grade[grade]
            lines.append(
                f"  {grade}: {g['count']} trades, "
                f"WR={g['win_rate']:.0%}, "
                f"avg={g['avg_pnl']:.2%}"
            )
        lines.append("")
        lines.append("By Sector:")
        for sector in sorted(self.by_sector.keys()):
            s = self.by_sector[sector]
            lines.append(
                f"  {sector}: {s['count']} trades, "
                f"WR={s['win_rate']:.0%}, "
                f"avg={s['avg_pnl']:.2%}"
            )
        return "\n".join(lines)


class PipelineBacktester:
    """
    End-to-end pipeline backtester.

    Instead of using raw signal DataFrames, this runs the actual
    SectorPipeline.process() and tracks whether TRADE decisions
    actually make money.

    Usage:
        bt = PipelineBacktester(forward_days=10)
        result = bt.run(enriched_signals, price_lookup)
        print(result.summary())
    """

    def __init__(
        self,
        forward_days: int = 10,
        scratch_threshold: float = 0.005,
    ):
        """
        Args:
            forward_days: How many days forward to measure outcome
            scratch_threshold: P&L below this is a "scratch" (neither win nor loss)
        """
        self.forward_days = forward_days
        self.scratch_threshold = scratch_threshold

    def run(
        self,
        pipeline_outputs: List[Dict[str, Any]],
        price_lookup: Optional[Dict[str, List[Dict]]] = None,
    ) -> PipelineBacktestResult:
        """
        Run pipeline backtest on a list of pipeline outputs.

        Args:
            pipeline_outputs: List of dicts from SectorPipeline.process(),
                each must have: ticker, action, grade, sector, confidence,
                entry_price, stop_loss, take_profit, position_size_pct, date
            price_lookup: Dict[ticker] → list of {date, close} sorted by date.
                Used to simulate forward price movement.
                If None, uses take_profit/stop_loss to simulate random outcomes.

        Returns:
            PipelineBacktestResult
        """
        trades: List[PipelineTrade] = []
        trade_count = 0
        watch_count = 0
        avoid_count = 0

        for output in pipeline_outputs:
            action = output.get("action", "WATCH")
            if action == "TRADE":
                trade_count += 1
            elif action == "WATCH":
                watch_count += 1
            else:
                avoid_count += 1
                continue

            if action != "TRADE":
                continue

            t = PipelineTrade(
                ticker=output.get("ticker", "???"),
                action=action,
                grade=output.get("grade", "?"),
                sector=output.get("sector", "Unknown"),
                confidence=output.get("confidence", 0.5),
                entry_price=output.get("entry_price", 0),
                stop_loss=output.get("stop_loss", 0),
                take_profit=output.get("take_profit", 0),
                position_size_pct=output.get("position_size_pct", 1.0),
                entry_date=output.get("date", ""),
            )

            # Resolve outcome
            self._resolve_outcome(t, price_lookup)
            trades.append(t)

        # Compute stats
        wins = [t for t in trades if t.outcome == "win"]
        losses = [t for t in trades if t.outcome == "loss"]
        scratches = [t for t in trades if t.outcome == "scratch"]

        win_rate = len(wins) / len(trades) if trades else 0
        pnls = [t.pnl_pct for t in trades]
        avg_pnl = float(np.mean(pnls)) if pnls else 0
        total_pnl = float(np.sum(pnls)) if pnls else 0

        # By grade
        by_grade = self._bucket_by(trades, "grade")
        by_sector = self._bucket_by(trades, "sector")

        # Calibration data
        cal_trades = [
            {"confidence": t.confidence, "pnl_pct": t.pnl_pct} for t in trades
        ]

        return PipelineBacktestResult(
            total_signals=len(pipeline_outputs),
            trade_signals=trade_count,
            watch_signals=watch_count,
            avoid_signals=avoid_count,
            trades_taken=len(trades),
            wins=len(wins),
            losses=len(losses),
            scratches=len(scratches),
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl,
            total_pnl_pct=total_pnl,
            by_grade=by_grade,
            by_sector=by_sector,
            calibration_trades=cal_trades,
        )

    def _resolve_outcome(
        self,
        trade: PipelineTrade,
        price_lookup: Optional[Dict[str, List[Dict]]],
    ):
        """Resolve trade outcome using forward prices or R:R simulation."""
        if price_lookup and trade.ticker in price_lookup:
            self._resolve_from_prices(trade, price_lookup[trade.ticker])
        else:
            self._resolve_from_rr(trade)

    def _resolve_from_prices(self, trade: PipelineTrade, prices: List[Dict]):
        """Walk forward through actual prices to determine outcome."""
        entry = trade.entry_price
        if entry <= 0:
            trade.outcome = "scratch"
            return

        # Find entry date index
        entry_idx = None
        for i, p in enumerate(prices):
            if str(p.get("date", "")) >= trade.entry_date:
                entry_idx = i
                break

        if entry_idx is None:
            trade.outcome = "scratch"
            return

        # Walk forward
        end_idx = min(entry_idx + self.forward_days, len(prices))
        for i in range(entry_idx + 1, end_idx):
            price = prices[i].get("close", entry)

            # Check stop
            if trade.stop_loss > 0 and price <= trade.stop_loss:
                trade.exit_price = trade.stop_loss
                trade.exit_date = str(prices[i].get("date", ""))
                trade.pnl_pct = (trade.stop_loss - entry) / entry
                trade.hit_stop = True
                trade.outcome = "loss"
                return

            # Check target
            if trade.take_profit > 0 and price >= trade.take_profit:
                trade.exit_price = trade.take_profit
                trade.exit_date = str(prices[i].get("date", ""))
                trade.pnl_pct = (trade.take_profit - entry) / entry
                trade.hit_target = True
                trade.outcome = "win"
                return

        # Time exit at last price
        last_price = prices[min(end_idx - 1, len(prices) - 1)].get("close", entry)
        trade.exit_price = last_price
        trade.pnl_pct = (last_price - entry) / entry
        if abs(trade.pnl_pct) < self.scratch_threshold:
            trade.outcome = "scratch"
        elif trade.pnl_pct > 0:
            trade.outcome = "win"
        else:
            trade.outcome = "loss"

    def _resolve_from_rr(self, trade: PipelineTrade):
        """
        When no price data available, estimate outcome from R:R ratio
        and confidence. This is a probabilistic simulation.
        """
        entry = trade.entry_price
        if entry <= 0:
            trade.outcome = "scratch"
            return

        # R:R ratio
        risk = abs(entry - trade.stop_loss) if trade.stop_loss > 0 else entry * 0.05
        reward = (
            abs(trade.take_profit - entry) if trade.take_profit > 0 else entry * 0.10
        )

        rr = reward / risk if risk > 0 else 1.0

        # Win probability based on confidence and R:R
        # Higher R:R = lower probability of hitting target
        # But higher confidence should increase probability
        base_prob = min(0.5, 1.0 / (1.0 + rr))  # base from R:R
        adj_prob = base_prob + (trade.confidence - 0.5) * 0.3  # confidence adjustment
        win_prob = max(0.1, min(0.9, adj_prob))

        # Deterministic for reproducibility: use hash
        seed = hash(f"{trade.ticker}:{trade.entry_date}:{trade.confidence}")
        rng = np.random.RandomState(abs(seed) % (2**31))

        if rng.random() < win_prob:
            trade.pnl_pct = reward / entry
            trade.outcome = "win"
            trade.hit_target = True
        else:
            trade.pnl_pct = -risk / entry
            trade.outcome = "loss"
            trade.hit_stop = True

    def _bucket_by(
        self, trades: List[PipelineTrade], field: str
    ) -> Dict[str, Dict[str, Any]]:
        """Bucket trades by a field and compute stats."""
        buckets: Dict[str, List[PipelineTrade]] = {}
        for t in trades:
            key = getattr(t, field, "Unknown")
            buckets.setdefault(key, []).append(t)

        result = {}
        for key, group in buckets.items():
            wins = [t for t in group if t.outcome == "win"]
            pnls = [t.pnl_pct for t in group]
            result[key] = {
                "count": len(group),
                "win_rate": len(wins) / len(group) if group else 0,
                "avg_pnl": float(np.mean(pnls)) if pnls else 0,
                "total_pnl": float(np.sum(pnls)) if pnls else 0,
            }
        return result
