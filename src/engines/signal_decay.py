"""
Signal Decay Tracker (Sprint 49) + Confidence Penalty (Sprint 108)
===================================================================
Tracks signal age and auto-expires signals past their time_stop_days.
Tracks performance-by-age to learn optimal holding periods.

Sprint 108 adds:
  - DECAY_SCHEDULE: half-life constants by signal grade
  - apply_decay_penalty(signal_dict, age_hours) → (penalised_score, decay_pct)
  - get_stale_signals(signals, threshold_hours) helper for REST layer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrackedSignal:
    """A signal being tracked for decay."""

    ticker: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    score: float
    setup_grade: str
    created_at: datetime
    time_stop_days: int = 5
    strategy_id: str = ""
    expired: bool = False
    outcome: Optional[str] = None

    @property
    def age_hours(self) -> float:
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() / 3600

    @property
    def age_days(self) -> float:
        return self.age_hours / 24

    @property
    def is_expired(self) -> bool:
        return self.age_days > self.time_stop_days

    def to_dict(self) -> Dict[str, Any]:
        outcome = self.outcome
        if not outcome:
            outcome = "expired" if self.is_expired else "active"
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "score": self.score,
            "setup_grade": self.setup_grade,
            "age_hours": round(self.age_hours, 1),
            "age_days": round(self.age_days, 1),
            "time_stop_days": self.time_stop_days,
            "expired": self.is_expired,
            "outcome": outcome,
            "strategy_id": self.strategy_id,
        }


class SignalDecayTracker:
    """Tracks signal freshness and enforces time-stop expiration."""

    MAX_TRACKED = 500

    def __init__(self) -> None:
        self._signals: Dict[str, TrackedSignal] = {}
        self._age_perf: List[Dict[str, Any]] = []

    def track(
        self,
        ticker: str,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        score: float,
        grade: str = "C",
        time_stop_days: int = 5,
        strategy_id: str = "",
    ) -> TrackedSignal:
        key = f"{ticker}_{direction}"
        sig = TrackedSignal(
            ticker=ticker,
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            score=score,
            setup_grade=grade,
            created_at=datetime.now(timezone.utc),
            time_stop_days=time_stop_days,
            strategy_id=strategy_id,
        )
        self._signals[key] = sig
        if len(self._signals) > self.MAX_TRACKED:
            oldest = min(
                self._signals,
                key=lambda k: self._signals[k].created_at,
            )
            del self._signals[oldest]
        return sig

    def check_expiry(self) -> List[TrackedSignal]:
        expired = []
        for sig in self._signals.values():
            if sig.is_expired and not sig.expired:
                sig.expired = True
                sig.outcome = "expired"
                expired.append(sig)
                self._age_perf.append(
                    {
                        "ticker": sig.ticker,
                        "age_days": round(sig.age_days, 1),
                        "outcome": "expired",
                        "grade": sig.setup_grade,
                    }
                )
        return expired

    def record_outcome(
        self,
        ticker: str,
        direction: str,
        outcome: str,
        pnl_pct: float = 0.0,
    ) -> None:
        key = f"{ticker}_{direction}"
        sig = self._signals.get(key)
        if sig:
            sig.outcome = outcome
            self._age_perf.append(
                {
                    "ticker": ticker,
                    "age_days": round(sig.age_days, 1),
                    "outcome": outcome,
                    "pnl_pct": round(pnl_pct, 2),
                    "grade": sig.setup_grade,
                }
            )

    def active_signals(self) -> List[Dict[str, Any]]:
        self.check_expiry()
        return [s.to_dict() for s in self._signals.values() if not s.expired]

    def expired_signals(self) -> List[Dict[str, Any]]:
        self.check_expiry()
        return [s.to_dict() for s in self._signals.values() if s.expired]

    def performance_by_age(self) -> Dict[str, Any]:
        buckets: Dict[str, list] = {
            "0-1d": [],
            "1-3d": [],
            "3-5d": [],
            "5d+": [],
        }
        for rec in self._age_perf:
            age = rec.get("age_days", 0)
            if age <= 1:
                buckets["0-1d"].append(rec)
            elif age <= 3:
                buckets["1-3d"].append(rec)
            elif age <= 5:
                buckets["3-5d"].append(rec)
            else:
                buckets["5d+"].append(rec)

        result = {}
        for bucket, records in buckets.items():
            hits = [r for r in records if r.get("outcome") == "hit_target"]
            total = len(records)
            result[bucket] = {
                "count": total,
                "wins": len(hits),
                "win_rate": (round(len(hits) / total, 2) if total > 0 else 0),
            }
        return result

    def summary(self) -> Dict[str, Any]:
        self.check_expiry()
        active = [s for s in self._signals.values() if not s.expired]
        expired = [s for s in self._signals.values() if s.expired]
        return {
            "active_count": len(active),
            "expired_count": len(expired),
            "total_tracked": len(self._signals),
            "performance_by_age": self.performance_by_age(),
            "active": [s.to_dict() for s in active[:20]],
        }


# ── Sprint 108: Confidence Decay Penalty ─────────────────────────────────────

import math  # noqa: E402  (placed here to avoid top-level ordering change)

# Half-life in hours by signal grade.
# A+ signals lose confidence slower than C grades.
DECAY_SCHEDULE: Dict[str, float] = {
    "A+": 48.0,
    "A": 36.0,
    "B+": 24.0,
    "B": 18.0,
    "C+": 12.0,
    "C": 8.0,
    "D": 4.0,
}
_DEFAULT_HALF_LIFE_HOURS = 16.0  # used when grade unknown

# Maximum absolute penalty subtracted from ranker score (keeps score bounded)
_MAX_DECAY_PENALTY_PTS = 20.0
# Scores this old are considered fully stale regardless of grade
STALE_THRESHOLD_HOURS = 8.0


def apply_decay_penalty(
    signal: Dict[str, Any],
    age_hours: Optional[float] = None,
) -> tuple[float, float]:
    """Apply an exponential confidence decay to a signal score.

    Uses the half-life formula:
        decay_fraction = 1 − exp(−λ × age)   where λ = ln(2) / half_life

    Parameters
    ----------
    signal : signal dict — must have ``score`` (0–100). Optionally ``setup_grade``
             and ``data_freshness_minutes`` (used to infer age_hours if not given).
    age_hours : override age. If None, inferred from ``data_freshness_minutes``.

    Returns
    -------
    (penalised_score, decay_pct)
        penalised_score : original score minus penalty (floored at 0)
        decay_pct       : percentage of score removed [0–1]
    """
    original_score = float(signal.get("score", 50))
    if original_score <= 0:
        return 0.0, 0.0

    # Determine age
    if age_hours is None:
        freshness_min = signal.get("data_freshness_minutes", -1) or -1
        age_hours = freshness_min / 60.0 if freshness_min > 0 else 0.0

    if age_hours <= 0:
        return original_score, 0.0

    grade = str(signal.get("setup_grade", signal.get("grade", "C")))
    half_life = DECAY_SCHEDULE.get(grade, _DEFAULT_HALF_LIFE_HOURS)

    lam = math.log(2) / half_life
    decay_fraction = 1.0 - math.exp(-lam * age_hours)
    penalty = min(_MAX_DECAY_PENALTY_PTS, original_score * decay_fraction)

    penalised = round(max(0.0, original_score - penalty), 2)
    return penalised, round(decay_fraction, 4)


def get_stale_signals(
    signals: List[Dict[str, Any]],
    threshold_hours: float = STALE_THRESHOLD_HOURS,
) -> List[Dict[str, Any]]:
    """Filter a list of signal dicts to those older than *threshold_hours*.

    Adds ``age_hours`` and ``decay_pct`` keys to each returned item.
    Age is inferred from ``data_freshness_minutes`` if present, else ``age_hours``
    field directly.
    """
    stale = []
    for sig in signals:
        age = sig.get("age_hours")
        if age is None:
            fm = sig.get("data_freshness_minutes", -1) or -1
            age = fm / 60.0 if fm > 0 else 0.0
        if age >= threshold_hours:
            _, decay_pct = apply_decay_penalty(sig, age_hours=float(age))
            item = dict(sig)
            item["age_hours"] = round(float(age), 1)
            item["decay_pct"] = round(decay_pct * 100, 1)
            stale.append(item)
    return sorted(stale, key=lambda x: x["age_hours"], reverse=True)
