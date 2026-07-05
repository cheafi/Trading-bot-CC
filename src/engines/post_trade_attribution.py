"""
CC — Post-Trade Attribution Engine
====================================
Compares stated reasons to realized outcomes.
Tracks by-regime, by-strategy, and by-bucket accuracy.
Enables learning: which reasons/regimes/strategies actually work?

Key questions answered:
  - Did the stated bull case play out?
  - Which strategies perform in which regimes?
  - Are our confidence buckets well-calibrated?
  - What is the accuracy of each expert council member?
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Trade Record ─────────────────────────────────────────────────


@dataclass
class TradeRecord:
    """A completed trade with stated reasons and realized outcome."""

    trade_id: str = ""
    ticker: str = ""
    direction: str = "LONG"
    strategy: str = ""
    regime: str = "unknown"
    # Stated at entry
    entry_date: str = ""
    entry_price: float = 0.0
    stated_bull_case: str = ""
    stated_bear_case: str = ""
    stated_invalidation: List[str] = field(default_factory=list)
    stated_confidence: float = 0.5
    confidence_bucket: str = "uncalibrated"
    meta_decision: str = "WATCH"
    size_multiplier: float = 1.0
    # Realized at exit
    exit_date: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""  # take_profit / stop_loss / time / manual
    realized_pnl_pct: float = 0.0
    max_favorable_excursion_pct: float = 0.0  # MFE
    max_adverse_excursion_pct: float = 0.0  # MAE
    holding_days: int = 0
    # Post-analysis
    bull_case_played_out: Optional[bool] = None
    invalidation_triggered: Optional[bool] = None
    notes: str = ""


# ─── Attribution Engine ──────────────────────────────────────────


class PostTradeAttribution:
    """
    Records completed trades and produces attribution reports:
    - By regime
    - By strategy
    - By confidence bucket
    - By exit reason
    - Stated vs realized comparison
    """

    def __init__(self):
        self._trades: List[TradeRecord] = []
        self._by_regime: Dict[str, List[int]] = defaultdict(list)
        self._by_strategy: Dict[str, List[int]] = defaultdict(list)
        self._by_bucket: Dict[str, List[int]] = defaultdict(list)

    def record_trade(self, trade: TradeRecord) -> int:
        """Record a completed trade. Returns index."""
        idx = len(self._trades)
        self._trades.append(trade)
        self._by_regime[trade.regime].append(idx)
        self._by_strategy[trade.strategy].append(idx)
        self._by_bucket[trade.confidence_bucket].append(idx)
        return idx

    # ── Reports ───────────────────────────────────────────────

    def full_report(self) -> Dict[str, Any]:
        """Comprehensive attribution report."""
        if not self._trades:
            return {
                "total_trades": 0,
                "by_regime": {},
                "by_strategy": {},
                "by_bucket": {},
                "by_exit_reason": {},
                "mfe_mae_summary": {},
                "bull_case_accuracy": None,
                "generated_at": _utcnow(),
            }

        return {
            "total_trades": len(self._trades),
            "overall": self._group_stats(self._trades),
            "by_regime": {
                r: self._group_stats([self._trades[i] for i in idxs])
                for r, idxs in self._by_regime.items()
            },
            "by_strategy": {
                s: self._group_stats([self._trades[i] for i in idxs])
                for s, idxs in self._by_strategy.items()
            },
            "by_bucket": {
                b: self._group_stats([self._trades[i] for i in idxs])
                for b, idxs in self._by_bucket.items()
            },
            "by_exit_reason": self._by_exit_reason(),
            "mfe_mae_summary": self._mfe_mae_summary(),
            "bull_case_accuracy": self._bull_case_accuracy(),
            "calibration_check": self._calibration_check(),
            "generated_at": _utcnow(),
        }

    def regime_heatmap(self) -> Dict[str, Dict[str, float]]:
        """
        PnL heatmap by regime × strategy.
        Returns {regime: {strategy: avg_pnl_pct}}.
        """
        heatmap: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for t in self._trades:
            heatmap[t.regime][t.strategy].append(t.realized_pnl_pct)

        return {
            regime: {
                strat: round(sum(pnls) / len(pnls), 4) if pnls else 0.0
                for strat, pnls in strategies.items()
            }
            for regime, strategies in heatmap.items()
        }

    # ── Internals ─────────────────────────────────────────────

    def _group_stats(self, trades: List[TradeRecord]) -> Dict[str, Any]:
        if not trades:
            return {}
        wins = [t for t in trades if t.realized_pnl_pct > 0]
        losses = [t for t in trades if t.realized_pnl_pct <= 0]
        pnls = [t.realized_pnl_pct for t in trades]
        avg_pnl = sum(pnls) / len(pnls)
        return {
            "count": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(trades), 3),
            "avg_pnl_pct": round(avg_pnl, 4),
            "best_pnl_pct": round(max(pnls), 4),
            "worst_pnl_pct": round(min(pnls), 4),
            "avg_holding_days": round(
                sum(t.holding_days for t in trades) / len(trades),
                1,
            ),
        }

    def _by_exit_reason(self) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, List[TradeRecord]] = defaultdict(list)
        for t in self._trades:
            groups[t.exit_reason or "unknown"].append(t)
        return {reason: self._group_stats(trades) for reason, trades in groups.items()}

    def _mfe_mae_summary(self) -> Dict[str, float]:
        if not self._trades:
            return {}
        mfes = [t.max_favorable_excursion_pct for t in self._trades]
        maes = [t.max_adverse_excursion_pct for t in self._trades]
        return {
            "avg_mfe_pct": round(sum(mfes) / len(mfes), 4),
            "avg_mae_pct": round(sum(maes) / len(maes), 4),
            "capture_ratio": round(
                (sum(mfes) / len(mfes)) / max(0.001, sum(maes) / len(maes)),
                2,
            ),
        }

    def _bull_case_accuracy(self) -> Optional[Dict[str, Any]]:
        assessed = [t for t in self._trades if t.bull_case_played_out is not None]
        if not assessed:
            return None
        correct = sum(1 for t in assessed if t.bull_case_played_out)
        return {
            "assessed": len(assessed),
            "bull_case_correct": correct,
            "accuracy": round(correct / len(assessed), 3),
        }

    def _calibration_check(self) -> Dict[str, Any]:
        """Compare stated confidence vs realized win rate by bucket."""
        result = {}
        for bucket, idxs in self._by_bucket.items():
            trades = [self._trades[i] for i in idxs]
            if not trades:
                continue
            avg_conf = sum(t.stated_confidence for t in trades) / len(trades)
            win_rate = sum(1 for t in trades if t.realized_pnl_pct > 0) / len(trades)
            result[bucket] = {
                "sample_size": len(trades),
                "avg_stated_confidence": round(avg_conf, 3),
                "realized_win_rate": round(win_rate, 3),
                "calibration_error": round(abs(avg_conf - win_rate), 3),
            }
        return result


# Module singleton
post_trade_attribution = PostTradeAttribution()
