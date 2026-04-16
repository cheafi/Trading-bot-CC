"""
CC — Shadow-Mode Tracker

Records every recommendation in shadow mode, then compares
predicted vs realized outcomes after the horizon expires.

This is the core feedback loop: every signal gets tracked,
and calibration drift is detected automatically.

Usage:
    from src.engines.shadow_tracker import shadow_tracker
    shadow_tracker.record_prediction(ticker="AAPL", ...)
    # After horizon expires:
    shadow_tracker.record_outcome(prediction_id, realized_pnl_pct=0.03)
    # Dashboard:
    report = shadow_tracker.shadow_report()
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ShadowPrediction:
    """A tracked prediction awaiting outcome."""

    prediction_id: str = ""
    ticker: str = ""
    direction: str = "LONG"
    strategy: str = "unknown"
    regime: str = "unknown"
    horizon: str = "5D"

    # Predicted
    forecast_probability: float = 0.5
    action_state: str = "WATCH"
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    composite_score: float = 0.0

    # Timing
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Realized (filled after outcome)
    realized: bool = False
    realized_at: Optional[datetime] = None
    realized_pnl_pct: float = 0.0
    hit_target: bool = False
    hit_stop: bool = False
    exit_reason: str = ""

    @property
    def won(self) -> bool:
        return self.realized_pnl_pct > 0

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return _utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "ticker": self.ticker,
            "direction": self.direction,
            "strategy": self.strategy,
            "regime": self.regime,
            "horizon": self.horizon,
            "forecast_probability": round(self.forecast_probability, 3),
            "action_state": self.action_state,
            "entry_price": self.entry_price,
            "realized": self.realized,
            "realized_pnl_pct": round(self.realized_pnl_pct, 4),
            "won": self.won if self.realized else None,
            "exit_reason": self.exit_reason,
        }


class ShadowTracker:
    """
    Shadow-mode evaluation engine.

    Tracks all predictions, compares vs realized outcomes,
    and generates calibration drift alerts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._predictions: Dict[str, ShadowPrediction] = {}
        self._by_regime: Dict[str, List[str]] = defaultdict(list)
        self._by_strategy: Dict[str, List[str]] = defaultdict(list)
        self._by_sector: Dict[str, List[str]] = defaultdict(list)

    # ── Recording ─────────────────────────────────────────────

    def record_prediction(
        self,
        ticker: str,
        direction: str = "LONG",
        strategy: str = "unknown",
        regime: str = "unknown",
        horizon: str = "5D",
        forecast_probability: float = 0.5,
        action_state: str = "WATCH",
        entry_price: float = 0.0,
        target_price: float = 0.0,
        stop_price: float = 0.0,
        composite_score: float = 0.0,
        sector: str = "unknown",
    ) -> str:
        """Record a new shadow prediction. Returns prediction_id."""
        now = _utcnow()
        pid = hashlib.sha256(
            f"{ticker}:{now.isoformat()}:{strategy}".encode()
        ).hexdigest()[:12]

        pred = ShadowPrediction(
            prediction_id=pid,
            ticker=ticker,
            direction=direction,
            strategy=strategy,
            regime=regime,
            horizon=horizon,
            forecast_probability=forecast_probability,
            action_state=action_state,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            composite_score=composite_score,
            created_at=now,
        )

        with self._lock:
            self._predictions[pid] = pred
            self._by_regime[regime].append(pid)
            self._by_strategy[strategy].append(pid)
            self._by_sector[sector].append(pid)

        return pid

    def record_outcome(
        self,
        prediction_id: str,
        realized_pnl_pct: float = 0.0,
        hit_target: bool = False,
        hit_stop: bool = False,
        exit_reason: str = "",
    ) -> bool:
        """Record realized outcome for a shadow prediction."""
        with self._lock:
            pred = self._predictions.get(prediction_id)
            if pred is None:
                return False
            pred.realized = True
            pred.realized_at = _utcnow()
            pred.realized_pnl_pct = realized_pnl_pct
            pred.hit_target = hit_target
            pred.hit_stop = hit_stop
            pred.exit_reason = exit_reason
            return True

    # ── Reports ───────────────────────────────────────────────

    def shadow_report(self) -> Dict[str, Any]:
        """Full shadow-mode report."""
        with self._lock:
            all_preds = list(self._predictions.values())
            realized = [p for p in all_preds if p.realized]
            pending = [p for p in all_preds if not p.realized]

            if not realized:
                return {
                    "total_predictions": len(all_preds),
                    "realized": 0,
                    "pending": len(pending),
                    "hit_rate": None,
                    "avg_pnl_pct": None,
                    "by_regime": {},
                    "by_strategy": {},
                    "calibration_drift": [],
                }

            wins = sum(1 for p in realized if p.won)
            hit_rate = wins / len(realized)
            avg_pnl = sum(p.realized_pnl_pct for p in realized) / len(realized)

            return {
                "total_predictions": len(all_preds),
                "realized": len(realized),
                "pending": len(pending),
                "hit_rate": round(hit_rate, 3),
                "avg_pnl_pct": round(avg_pnl, 4),
                "by_regime": self._group_stats(realized, "regime"),
                "by_strategy": self._group_stats(realized, "strategy"),
                "calibration_drift": self._detect_drift(realized),
            }

    def confidence_vs_hitrate(self) -> List[Dict[str, Any]]:
        """
        Confidence vs hit-rate scatter data by regime/sector.
        For the calibration drift dashboard.
        """
        with self._lock:
            realized = [p for p in self._predictions.values() if p.realized]

        buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "wins": 0, "sum_forecast": 0.0}
        )
        for p in realized:
            # Bucket by decile
            decile = min(9, int(p.forecast_probability * 10))
            key = f"{decile * 10}-{(decile + 1) * 10}%"
            b = buckets[key]
            b["count"] += 1
            b["wins"] += int(p.won)
            b["sum_forecast"] += p.forecast_probability

        result = []
        for key, b in sorted(buckets.items()):
            if b["count"] > 0:
                result.append(
                    {
                        "bucket": key,
                        "sample_size": b["count"],
                        "avg_forecast": round(b["sum_forecast"] / b["count"], 3),
                        "realized_hit_rate": round(b["wins"] / b["count"], 3),
                        "calibration_error": round(
                            abs(
                                b["sum_forecast"] / b["count"] - b["wins"] / b["count"]
                            ),
                            3,
                        ),
                    }
                )
        return result

    # ── Drift detection ───────────────────────────────────────

    def _detect_drift(self, realized: List[ShadowPrediction]) -> List[Dict[str, Any]]:
        """Detect calibration drift — alerts when forecast ≠ realized."""
        alerts = []

        # Check per-regime drift
        regime_groups: Dict[str, List[ShadowPrediction]] = defaultdict(list)
        for p in realized:
            regime_groups[p.regime].append(p)

        for regime, preds in regime_groups.items():
            if len(preds) < 10:
                continue
            avg_forecast = sum(p.forecast_probability for p in preds) / len(preds)
            hit_rate = sum(1 for p in preds if p.won) / len(preds)
            drift = abs(avg_forecast - hit_rate)
            if drift > 0.15:
                alerts.append(
                    {
                        "type": "calibration_drift",
                        "scope": f"regime:{regime}",
                        "avg_forecast": round(avg_forecast, 3),
                        "realized_hit_rate": round(hit_rate, 3),
                        "drift": round(drift, 3),
                        "sample_size": len(preds),
                        "severity": ("high" if drift > 0.25 else "medium"),
                    }
                )

        return alerts

    @staticmethod
    def _group_stats(
        predictions: List[ShadowPrediction],
        group_by: str,
    ) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, List[ShadowPrediction]] = defaultdict(list)
        for p in predictions:
            key = getattr(p, group_by, "unknown")
            groups[key].append(p)

        result = {}
        for key, preds in groups.items():
            wins = sum(1 for p in preds if p.won)
            result[key] = {
                "count": len(preds),
                "wins": wins,
                "hit_rate": round(wins / len(preds), 3) if preds else 0,
                "avg_pnl_pct": (
                    round(
                        sum(p.realized_pnl_pct for p in preds) / len(preds),
                        4,
                    )
                    if preds
                    else 0
                ),
            }
        return result


# ── Module singleton ──────────────────────────────────────────
shadow_tracker = ShadowTracker()
