"""
Forward Shadow Thresholds — parallel forward shadow tracking.

Analytics only; no live Playbook changes. Tracks shadow vs live pass rates.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from src.services.shadow_threshold_simulator import would_pass_threshold
from src.services.threshold_registry import get_threshold

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal", "threshold_governance"
)
_SHADOW_RUNS_PATH = os.environ.get("THRESHOLD_SHADOW_RUNS_PATH") or os.path.join(
    _DATA_DIR, "shadow_runs.jsonl"
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "tsr") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


@dataclass
class ShadowRunSnapshot:
    run_id: str
    proposal_id: str
    threshold_key: str
    live_value: float
    shadow_value: float
    live_pass_count: int = 0
    shadow_pass_count: int = 0
    live_reject_count: int = 0
    shadow_reject_count: int = 0
    divergence_count: int = 0
    window_rows: int = 0
    recorded_at: str = field(default_factory=_now_iso)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False
    no_live_changes: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["no_live_changes"] = True
        return d


class ForwardShadowTracker:
    """Append-only forward shadow run log."""

    def __init__(self, runs_path: Optional[str] = None) -> None:
        self.runs_path = runs_path or _SHADOW_RUNS_PATH
        _ensure_dir(self.runs_path)

    def _append(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(self.runs_path, "a", encoding="utf-8") as f:
            f.write(line)

    def _load_all(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.runs_path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.runs_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def record_run(self, snapshot: ShadowRunSnapshot) -> str:
        self._append(snapshot.to_dict())
        return snapshot.run_id

    def load_runs(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        return self._load_all()[-limit:]

    def latest_for_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        for row in reversed(self._load_all()):
            if row.get("proposal_id") == proposal_id:
                return row
        return None


_tracker: Optional[ForwardShadowTracker] = None


def get_forward_shadow_tracker() -> ForwardShadowTracker:
    global _tracker
    if _tracker is None:
        _tracker = ForwardShadowTracker()
    return _tracker


def run_forward_shadow(
    proposal: Dict[str, Any],
    *,
    forward_rows: Sequence[Dict[str, Any]],
    persist: bool = False,
    tracker: Optional[ForwardShadowTracker] = None,
) -> Dict[str, Any]:
    """
    Parallel forward shadow: compare live registry value vs proposed shadow value.
    Analytics only — does not mutate live thresholds.
    """
    key = str(proposal.get("threshold_key") or "")
    defn = get_threshold(key)
    live_value = float(defn.current_value) if defn else float(proposal.get("current_value") or 0)
    shadow_value = proposal.get("proposed_value")
    if shadow_value is None:
        return {
            "ok": False,
            "error": "no shadow value",
            "authority_effect": "none",
            "no_live_changes": True,
        }
    shadow_value = float(shadow_value)

    live_pass = shadow_pass = live_reject = shadow_reject = divergence = 0
    rows = list(forward_rows or [])

    for row in rows:
        lp = would_pass_threshold(row, key, live_value)
        sp = would_pass_threshold(row, key, shadow_value)
        if lp:
            live_pass += 1
        else:
            live_reject += 1
        if sp:
            shadow_pass += 1
        else:
            shadow_reject += 1
        if lp != sp:
            divergence += 1

    run_id = _new_id("fsh")
    snapshot = ShadowRunSnapshot(
        run_id=run_id,
        proposal_id=str(proposal.get("proposal_id") or ""),
        threshold_key=key,
        live_value=live_value,
        shadow_value=shadow_value,
        live_pass_count=live_pass,
        shadow_pass_count=shadow_pass,
        live_reject_count=live_reject,
        shadow_reject_count=shadow_reject,
        divergence_count=divergence,
        window_rows=len(rows),
    )

    tr = tracker or get_forward_shadow_tracker()
    if persist:
        tr.record_run(snapshot)

    return {
        "ok": True,
        "run_id": run_id,
        "snapshot": snapshot.to_dict(),
        "divergence_rate": round(divergence / len(rows), 4) if rows else 0.0,
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "no_live_changes": True,
    }


def batch_forward_shadow(
    proposals: Sequence[Dict[str, Any]],
    *,
    forward_rows: Sequence[Dict[str, Any]],
    persist: bool = False,
) -> Dict[str, Any]:
    """Run forward shadow for multiple proposals."""
    results = []
    for p in proposals:
        if p.get("status") in ("approved_shadow", "shadow", "open") and p.get("proposed_value"):
            results.append(
                run_forward_shadow(p, forward_rows=forward_rows, persist=persist)
            )
    return {
        "runs": results,
        "count": len(results),
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "no_live_changes": True,
    }


def forward_shadow_summary(
    *,
    tracker: Optional[ForwardShadowTracker] = None,
) -> Dict[str, Any]:
    tr = tracker or get_forward_shadow_tracker()
    runs = tr.load_runs(limit=20)
    active = [r for r in runs if r.get("divergence_count", 0) > 0]
    return {
        "total_runs": len(runs),
        "active_divergence_runs": len(active),
        "latest_runs": runs[-5:],
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "no_live_changes": True,
        "collapsed": True,
    }
