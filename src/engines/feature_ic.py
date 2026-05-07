"""
Feature Importance IC Decay Detector — Sprint 103
===================================================
Track the rolling Information Coefficient (IC) of each feature used in
trade decisions. IC = correlation between feature value and binary outcome.

For each feature we maintain:
  • A rolling window of (feature_value, outcome) pairs
  • Rolling IC (Pearson correlation × sign adjustment)
  • Decay alert when IC drops below threshold from its rolling peak

Persistence: models/feature_ic.json
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_IC_FILE = Path("models/feature_ic.json")
_IC_WINDOW = 50  # rolling window per feature
_IC_DECAY_THRESHOLD = 0.10  # alert if IC drops >0.10 from peak
_IC_MIN_SAMPLES = 10  # minimum samples before computing IC

# Features tracked: any numeric signal value that can be paired with outcome
TRACKED_FEATURES = [
    "final_confidence",
    "rs_composite",
    "mtf_confluence_score",
    "thesis_confidence",
    "timing_confidence",
    "vix",
]


@dataclass
class FeatureICState:
    """Rolling IC state for one feature."""

    name: str
    history: list = field(default_factory=list)  # [{val, win}, ...]
    latest_ic: Optional[float] = None
    peak_ic: Optional[float] = None
    n: int = 0

    @property
    def decay(self) -> float:
        if self.latest_ic is None or self.peak_ic is None:
            return 0.0
        return round(self.peak_ic - self.latest_ic, 4)

    @property
    def alert(self) -> bool:
        return self.decay > _IC_DECAY_THRESHOLD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.name,
            "latest_ic": self.latest_ic,
            "peak_ic": self.peak_ic,
            "decay": self.decay,
            "alert": self.alert,
            "n": self.n,
        }


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    """Compute Pearson correlation between xs and ys."""
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-9 or dy < 1e-9:
        return None
    return round(num / (dx * dy), 4)


def record_feature_outcomes(
    features: Dict[str, float],
    actual_win: bool,
) -> Dict[str, Any]:
    """
    Record a (feature_value, outcome) pair for each feature in ``features``.
    Returns the current IC state for all tracked features.
    """
    data = _load_ic_data()
    outcome = 1 if actual_win else 0

    for feat_name, val in features.items():
        if val is None:
            continue
        feat_key = feat_name.lower().strip()
        bucket = data["features"].setdefault(
            feat_key, {"history": [], "peak_ic": None, "latest_ic": None}
        )
        bucket["history"].append({"val": float(val), "win": outcome})
        bucket["history"] = bucket["history"][-_IC_WINDOW:]

    _save_ic_data(data)
    return _compute_ic_summary(data)


def get_feature_ic_status() -> Dict[str, Any]:
    """Return current IC scores, peaks, decay and alerts for all features."""
    data = _load_ic_data()
    return _compute_ic_summary(data)


def _compute_ic_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    features_out: Dict[str, Any] = {}
    alerts = []

    for feat_key, bucket in data.get("features", {}).items():
        hist = bucket.get("history", [])
        n = len(hist)
        if n < _IC_MIN_SAMPLES:
            features_out[feat_key] = {
                "feature": feat_key,
                "latest_ic": None,
                "peak_ic": None,
                "decay": 0.0,
                "alert": False,
                "n": n,
            }
            continue

        xs = [e["val"] for e in hist]
        ys = [float(e["win"]) for e in hist]
        ic = _pearson(xs, ys)

        peak = bucket.get("peak_ic")
        if ic is not None:
            if peak is None or abs(ic) > abs(peak):
                bucket["peak_ic"] = ic
                peak = ic
        decay = (
            round((abs(peak) - abs(ic)), 4)
            if (ic is not None and peak is not None)
            else 0.0
        )
        alert = decay > _IC_DECAY_THRESHOLD

        features_out[feat_key] = {
            "feature": feat_key,
            "latest_ic": ic,
            "peak_ic": peak,
            "decay": decay,
            "alert": alert,
            "n": n,
        }
        if alert:
            alerts.append(feat_key)

    # Persist updated peaks
    _save_ic_data(data)

    if alerts:
        logger.warning("[FeatureIC] Decay alert for features: %s", alerts)

    return {
        "features": features_out,
        "alerts": alerts,
        "total_features": len(features_out),
        "status": "decay_detected" if alerts else "ok",
    }


def _load_ic_data() -> Dict[str, Any]:
    if not _IC_FILE.exists():
        return {"features": {}}
    try:
        with open(_IC_FILE) as f:
            return json.load(f)
    except Exception:
        return {"features": {}}


def _save_ic_data(data: Dict[str, Any]) -> None:
    try:
        _IC_FILE.parent.mkdir(exist_ok=True)
        with open(_IC_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.debug("[FeatureIC] save error: %s", e)
