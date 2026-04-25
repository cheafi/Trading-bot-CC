"""
Post-Trade Learning Loop (Sprint 49)
======================================
Automated pipeline:
  closed trade → attribution → MetaEnsemble.record_outcome → retrain
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("CC_DATA_DIR", "data"))
_TRADES_FILE = _DATA_DIR / "closed_trades.jsonl"


@dataclass
class ClosedTrade:
    """Record of a completed trade for learning."""

    ticker: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    strategy_id: str
    pnl_pct: float
    r_multiple: float
    regime_at_entry: str = ""
    setup_grade: str = "C"
    hold_days: float = 0.0

    @property
    def won(self) -> bool:
        return self.pnl_pct > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_pct": round(self.pnl_pct, 2),
            "r_multiple": round(self.r_multiple, 2),
            "strategy_id": self.strategy_id,
            "regime": self.regime_at_entry,
            "setup_grade": self.setup_grade,
            "hold_days": round(self.hold_days, 1),
            "won": self.won,
        }


class LearningLoopPipeline:
    """Closes the loop: trade outcomes → weight adaptation."""

    def __init__(self) -> None:
        self._closed_trades: List[ClosedTrade] = []
        self._meta_ensemble = None
        self._attribution_log: List[Dict[str, Any]] = []
        self._load_persisted_trades()

    def _load_persisted_trades(self) -> None:
        """Load closed trades from JSONL file."""
        if not _TRADES_FILE.exists():
            return
        try:
            count = 0
            for line in _TRADES_FILE.read_text().strip().splitlines():
                d = json.loads(line)
                self._closed_trades.append(ClosedTrade(**d))
                count += 1
            if count:
                logger.info("Loaded %d persisted trades", count)
        except Exception as e:
            logger.warning("Failed to load trades: %s", e)

    def _persist_trade(self, trade: ClosedTrade) -> None:
        """Append trade to JSONL file."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(_TRADES_FILE, "a") as f:
                row = {
                    "ticker": trade.ticker,
                    "direction": trade.direction,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "entry_time": trade.entry_time,
                    "exit_time": trade.exit_time,
                    "strategy_id": trade.strategy_id,
                    "pnl_pct": trade.pnl_pct,
                    "r_multiple": trade.r_multiple,
                    "regime_at_entry": trade.regime_at_entry,
                    "setup_grade": trade.setup_grade,
                    "hold_days": trade.hold_days,
                }
                f.write(json.dumps(row) + "\n")
        except Exception as e:
            logger.warning("Failed to persist trade: %s", e)

    def _get_ensemble(self):
        if self._meta_ensemble is None:
            try:
                from src.engines.meta_ensemble import MetaEnsemble

                self._meta_ensemble = MetaEnsemble()
            except Exception as e:
                logger.warning("MetaEnsemble unavailable: %s", e)
        return self._meta_ensemble

    def record_closed_trade(
        self,
        ticker: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        entry_time: str,
        exit_time: str,
        strategy_id: str,
        regime_at_entry: str = "",
        setup_grade: str = "C",
        component_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Record a closed trade and feed to MetaEnsemble."""
        if entry_price > 0:
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl_pct = 0.0
        if direction == "SHORT":
            pnl_pct = -pnl_pct

        risk = abs(entry_price * 0.05)
        r_multiple = (exit_price - entry_price) / risk if risk > 0 else 0
        if direction == "SHORT":
            r_multiple = -r_multiple

        trade = ClosedTrade(
            ticker=ticker,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            strategy_id=strategy_id,
            pnl_pct=pnl_pct,
            r_multiple=r_multiple,
            regime_at_entry=regime_at_entry,
            setup_grade=setup_grade,
        )
        self._closed_trades.append(trade)
        self._persist_trade(trade)

        ensemble = self._get_ensemble()
        if ensemble and component_scores:
            try:
                ensemble.record_outcome(
                    component_scores=component_scores,
                    pnl_pct=pnl_pct,
                    r_multiple=r_multiple,
                    regime_label=regime_at_entry,
                    strategy_id=strategy_id,
                )
            except Exception as e:
                logger.warning("Ensemble record failed: %s", e)

        attribution = {
            "trade": trade.to_dict(),
            "component_scores": component_scores,
            "ensemble_trained": (ensemble.is_trained if ensemble else False),
            "ensemble_samples": (ensemble.sample_count if ensemble else 0),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._attribution_log.append(attribution)
        return attribution

    def get_trade_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._closed_trades[-limit:]]

    def get_attribution_log(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return self._attribution_log[-limit:]

    def win_rate_by_grade(self) -> Dict[str, Dict[str, Any]]:
        grades: Dict[str, List[bool]] = {}
        for t in self._closed_trades:
            g = t.setup_grade
            if g not in grades:
                grades[g] = []
            grades[g].append(t.won)
        return {
            g: {
                "count": len(v),
                "wins": sum(v),
                "win_rate": round(sum(v) / len(v), 2) if v else 0,
            }
            for g, v in sorted(grades.items())
        }

    def win_rate_by_regime(self) -> Dict[str, Dict[str, Any]]:
        regimes: Dict[str, List[bool]] = {}
        for t in self._closed_trades:
            r = t.regime_at_entry or "UNKNOWN"
            if r not in regimes:
                regimes[r] = []
            regimes[r].append(t.won)
        return {
            r: {
                "count": len(v),
                "wins": sum(v),
                "win_rate": round(sum(v) / len(v), 2) if v else 0,
            }
            for r, v in sorted(regimes.items())
        }

    def summary(self) -> Dict[str, Any]:
        total = len(self._closed_trades)
        wins = sum(1 for t in self._closed_trades if t.won)
        ens = self._get_ensemble()
        return {
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total, 2) if total > 0 else 0,
            "by_grade": self.win_rate_by_grade(),
            "by_regime": self.win_rate_by_regime(),
            "meta_ensemble_trained": (ens.is_trained if ens else False),
            "ensemble_samples": (ens.sample_count if ens else 0),
            "learned_weights": (
                ens.get_learned_weights() if ens and ens.is_trained else None
            ),
        }
