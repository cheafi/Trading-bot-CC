"""
Alpha Quality Store — append-only snapshots for OI quality control tower.

Persisted under data/decision_journal/alpha_quality/. Learning mode when low n;
never authorizes deploy; authority_effect=none.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MIN_SAMPLES_LEARNING = 5
MIN_SAMPLES_LIFT = 12

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal", "alpha_quality"
)
_SNAPSHOTS_PATH = os.environ.get("ALPHA_QUALITY_SNAPSHOTS_PATH") or os.path.join(
    _DATA_DIR, "snapshots.jsonl"
)
_BY_STAGE_PATH = os.environ.get("ALPHA_QUALITY_BY_STAGE_PATH") or os.path.join(
    _DATA_DIR, "by_stage.jsonl"
)
_BY_FAMILY_PATH = os.environ.get("ALPHA_QUALITY_BY_FAMILY_PATH") or os.path.join(
    _DATA_DIR, "by_signal_family.jsonl"
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "aq") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


@dataclass
class AlphaQualityByStage:
    stage: str
    sample_size: int = 0
    hit_rate_display: str = "learning"
    expectancy_display: str = "learning"
    cost_adj_expectancy_display: str = "learning"
    conversion_rate_display: Optional[str] = None
    lift_vs_baseline: Optional[str] = None
    learning_mode: bool = True
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["learning_mode"] = self.sample_size < MIN_SAMPLES_LEARNING
        return d


@dataclass
class AlphaQualityBySignalFamily:
    family: str
    sample_size: int = 0
    hit_rate_display: str = "learning"
    expectancy_display: str = "learning"
    cost_adj_expectancy_display: str = "learning"
    status: str = "learning"
    overfit_capped: bool = False
    learning_mode: bool = True
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["learning_mode"] = self.sample_size < MIN_SAMPLES_LEARNING
        return d


@dataclass
class AlphaQualitySnapshot:
    snapshot_id: str
    session_id: str = ""
    window_days: int = 20
    sample_size: int = 0
    status: str = "learning"
    oi_lift_display: str = "learning"
    cost_adj_expectancy_display: str = "learning"
    conversion_quality: str = "learning"
    overfit_risk: str = "medium"
    hit_rate_trap: bool = False
    payoff_degradation: bool = False
    by_stage: List[Dict[str, Any]] = field(default_factory=list)
    by_signal_family: List[Dict[str, Any]] = field(default_factory=list)
    baseline_comparison: Dict[str, Any] = field(default_factory=dict)
    missed_opportunity_summary: Dict[str, Any] = field(default_factory=dict)
    governor_qa: Dict[str, Any] = field(default_factory=dict)
    learning_mode: bool = True
    recorded_at: str = field(default_factory=_now_iso)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False
    evidence_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["evidence_only"] = True
        d["learning_mode"] = self.sample_size < MIN_SAMPLES_LEARNING
        return d


class AlphaQualityStore:
    """Append-only JSONL store for alpha quality snapshots."""

    def __init__(
        self,
        snapshots_path: Optional[str] = None,
        by_stage_path: Optional[str] = None,
        by_family_path: Optional[str] = None,
    ) -> None:
        self.snapshots_path = snapshots_path or _SNAPSHOTS_PATH
        self.by_stage_path = by_stage_path or _BY_STAGE_PATH
        self.by_family_path = by_family_path or _BY_FAMILY_PATH
        for p in (self.snapshots_path, self.by_stage_path, self.by_family_path):
            _ensure_dir(p)

    def _append(self, path: str, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def append_snapshot(self, snapshot: AlphaQualitySnapshot) -> str:
        payload = snapshot.to_dict()
        self._append(self.snapshots_path, payload)
        for stage_row in snapshot.by_stage:
            self._append(
                self.by_stage_path,
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "session_id": snapshot.session_id,
                    "recorded_at": snapshot.recorded_at,
                    **stage_row,
                },
            )
        for fam_row in snapshot.by_signal_family:
            self._append(
                self.by_family_path,
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "session_id": snapshot.session_id,
                    "recorded_at": snapshot.recorded_at,
                    **fam_row,
                },
            )
        return snapshot.snapshot_id

    def load_snapshots(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.snapshots_path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.snapshots_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        rows = self.load_snapshots(limit=1)
        return rows[-1] if rows else None

    def summary(self) -> Dict[str, Any]:
        rows = self.load_snapshots(limit=50)
        latest = rows[-1] if rows else {}
        return {
            "total_snapshots": len(rows),
            "latest_status": latest.get("status", "learning"),
            "latest_sample_size": latest.get("sample_size", 0),
            "learning_mode": bool(latest.get("learning_mode", True)),
            "authority_effect": "none",
            "may_authorize_deploy": False,
        }


_store: Optional[AlphaQualityStore] = None


def get_alpha_quality_store() -> AlphaQualityStore:
    global _store
    if _store is None:
        _store = AlphaQualityStore()
    return _store


def make_snapshot_id() -> str:
    return _new_id("aqsnap")
