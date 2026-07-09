"""
No-Edge Tracker — persistent tracking of no-edge day call quality.

Separates infrastructure blockers (broker, runtime) from quality blockers
(regime, setup scarcity). Labels: learning, good_avoidance, too_conservative,
noisy, insufficient_data.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.forward_outcome_tracker import STUDY_LABEL

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal"
)
_NO_EDGE_PATH = os.environ.get("NO_EDGE_TRACKER_PATH") or os.path.join(
    _DATA_DIR, "no_edge_days.jsonl"
)

INFRASTRUCTURE_BLOCKERS = frozenset(
    {
        "BROKER_OFFLINE",
        "RUNTIME_DEGRADED",
        "RUNTIME_CRITICAL",
        "MANUAL_DEMO_BOOK",
        "HANDOFF_NOT_READY",
        "DATA_STALE",
    }
)
QUALITY_BLOCKERS = frozenset(
    {
        "NO_EDGE_TODAY",
        "REGIME_WAIT",
        "BRIEF_EXPIRED",
        "LOW_SETUP_QUALITY",
        "CORRELATION_CLUSTER",
        "DRAWDOWN_BREACH",
    }
)

MIN_SAMPLES_FOR_LABEL = 8
MIN_SAMPLES_LEARNING = 3

QUALITY_LABELS = (
    "learning",
    "good_avoidance",
    "too_conservative",
    "noisy",
    "insufficient_data",
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def classify_blockers(
    reason_codes: Optional[List[str]] = None,
    primary_blocker: str = "",
) -> Dict[str, Any]:
    codes = [str(c).upper() for c in (reason_codes or [])]
    primary = str(primary_blocker or "").upper().replace(" ", "_")
    infra = [c for c in codes if c in INFRASTRUCTURE_BLOCKERS]
    quality = [c for c in codes if c in QUALITY_BLOCKERS]
    if primary:
        if primary in INFRASTRUCTURE_BLOCKERS and primary not in infra:
            infra.append(primary)
        elif primary in QUALITY_BLOCKERS and primary not in quality:
            quality.append(primary)
    return {
        "infrastructure_blockers": infra[:4],
        "quality_blockers": quality[:4],
        "primary_blocker": primary_blocker or (codes[0] if codes else ""),
        "blocker_class": (
            "infrastructure"
            if infra and not quality
            else "quality"
            if quality and not infra
            else "mixed"
            if infra and quality
            else "unknown"
        ),
    }


def evaluate_call_quality(
    *,
    market_forward_returns: Optional[Dict[int, float]] = None,
    top_rejected_forward_r: Optional[float] = None,
    avoided_drawdown: Optional[float] = None,
    missed_opportunity: Optional[float] = None,
    sample_size: int = 0,
    blocker_class: str = "unknown",
) -> str:
    """
    Classify no-edge call quality from forward market evidence.
    Never claims precision below MIN_SAMPLES_LEARNING.
    """
    if sample_size < MIN_SAMPLES_LEARNING:
        return "learning"
    if sample_size < MIN_SAMPLES_FOR_LABEL:
        return "insufficient_data"

    mkt = dict(market_forward_returns or {})
    avg_fwd = None
    vals = [v for v in mkt.values() if v is not None]
    if vals:
        avg_fwd = sum(vals) / len(vals)

    if top_rejected_forward_r is not None and top_rejected_forward_r > 1.5:
        return "too_conservative"
    if missed_opportunity is not None and missed_opportunity > 0.5:
        return "too_conservative"
    if avg_fwd is not None and avg_fwd > 2.0 and blocker_class == "quality":
        return "too_conservative"

    if avoided_drawdown is not None and avoided_drawdown > 0:
        return "good_avoidance"
    if top_rejected_forward_r is not None and top_rejected_forward_r < -0.5:
        return "good_avoidance"
    if avg_fwd is not None and avg_fwd < -1.0:
        return "good_avoidance"

    if blocker_class == "infrastructure":
        return "insufficient_data"

    return "noisy"


class NoEdgeTracker:
    """Append-only no-edge day records."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or _NO_EDGE_PATH
        _ensure_dir(self.path)

    def record(
        self,
        *,
        session_id: str,
        truth: Optional[Dict[str, Any]] = None,
        market_forward: Optional[Dict[int, float]] = None,
        top_rejected_forward_r: Optional[float] = None,
        avoided_drawdown: Optional[float] = None,
        missed_opportunity: Optional[float] = None,
    ) -> Dict[str, Any]:
        t = dict(truth or {})
        blockers = classify_blockers(
            reason_codes=list(t.get("reason_codes") or []),
            primary_blocker=str(t.get("primary_blocker") or ""),
        )
        mkt = dict(market_forward or {})
        outcomes = []
        for h in (1, 3, 5):
            px = mkt.get(h)
            outcomes.append(
                {
                    "horizon": h,
                    "market_forward_return_pct": round(px, 2) if px is not None else None,
                    "label": STUDY_LABEL,
                }
            )
        n = sum(1 for o in outcomes if o.get("market_forward_return_pct") is not None)
        quality = evaluate_call_quality(
            market_forward_returns=mkt,
            top_rejected_forward_r=top_rejected_forward_r,
            avoided_drawdown=avoided_drawdown,
            missed_opportunity=missed_opportunity,
            sample_size=n,
            blocker_class=blockers["blocker_class"],
        )
        record = {
            "record_type": "no_edge_day",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "no_edge_day": True,
            "market_outcomes": outcomes,
            "top_rejected_forward_r": top_rejected_forward_r,
            "avoided_drawdown": avoided_drawdown,
            "missed_opportunity": missed_opportunity,
            "quality_label": quality,
            "sample_size": n,
            "label": STUDY_LABEL,
            "primary_blocker": blockers["primary_blocker"],
            "infrastructure_blockers": blockers["infrastructure_blockers"],
            "quality_blockers": blockers["quality_blockers"],
            "blocker_class": blockers["blocker_class"],
            "authority_state": (t.get("deploy_authority_tier") or "blocked"),
            "authority_effect": "none",
            "learning_mode": n < MIN_SAMPLES_FOR_LABEL,
            "may_authorize_deploy": False,
            "evidence_only": True,
        }
        line = json.dumps(record, separators=(",", ":"), default=str) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
        return record

    def load_all(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows

    def count(self) -> int:
        return len(self.load_all())

    def summarize(self, *, window: int = 30) -> Dict[str, Any]:
        rows = self.load_all()[-window:]
        if not rows:
            return {
                "no_edge_samples": 0,
                "quality_label": "learning",
                "learning_mode": True,
                "good_avoidance_count": 0,
                "too_conservative_count": 0,
                "noisy_count": 0,
                "infrastructure_blocked_count": 0,
                "quality_blocked_count": 0,
                "sample_size": 0,
                "label": STUDY_LABEL,
                "may_authorize_deploy": False,
            }
        labels: Dict[str, int] = {}
        infra_n = 0
        quality_n = 0
        total_samples = 0
        for r in rows:
            lbl = str(r.get("quality_label") or "learning")
            labels[lbl] = labels.get(lbl, 0) + 1
            total_samples += int(r.get("sample_size") or 0)
            if r.get("blocker_class") == "infrastructure":
                infra_n += 1
            elif r.get("blocker_class") == "quality":
                quality_n += 1
        dominant = max(labels, key=labels.get) if labels else "learning"
        n_days = len(rows)
        return {
            "no_edge_samples": n_days,
            "quality_label": dominant if n_days >= MIN_SAMPLES_LEARNING else "learning",
            "learning_mode": n_days < MIN_SAMPLES_FOR_LABEL,
            "good_avoidance_count": labels.get("good_avoidance", 0),
            "too_conservative_count": labels.get("too_conservative", 0),
            "noisy_count": labels.get("noisy", 0),
            "insufficient_data_count": labels.get("insufficient_data", 0),
            "infrastructure_blocked_count": infra_n,
            "quality_blocked_count": quality_n,
            "sample_size": total_samples,
            "label": STUDY_LABEL,
            "may_authorize_deploy": False,
            "authority_effect": "none",
        }


def get_no_edge_tracker(path: Optional[str] = None) -> NoEdgeTracker:
    return NoEdgeTracker(path=path)


def build_no_edge_outcome_tracking(
    *,
    truth: Optional[Dict[str, Any]] = None,
    market_forward: Optional[Dict[int, float]] = None,
    tracker: Optional[NoEdgeTracker] = None,
    session_id: str = "",
    persist: bool = False,
) -> Dict[str, Any]:
    """Build no-edge tracking — optionally persist to store."""
    t = dict(truth or {})
    mkt = dict(market_forward or {})
    tr = NoEdgeTracker() if tracker is None else tracker
    summary = tr.summarize()
    if persist and session_id:
        record = tr.record(
            session_id=session_id,
            truth=t,
            market_forward=mkt,
        )
        summary = tr.summarize()
        summary["latest_record"] = record
    blockers = classify_blockers(
        reason_codes=list(t.get("reason_codes") or []),
        primary_blocker=str(t.get("primary_blocker") or ""),
    )
    n = sum(1 for h in (1, 3, 5) if mkt.get(h) is not None)
    quality = evaluate_call_quality(
        market_forward_returns=mkt,
        sample_size=max(n, summary.get("no_edge_samples", 0)),
        blocker_class=blockers["blocker_class"],
    )
    return {
        "no_edge_day": int(t.get("deploy_qualified_count") or 0) < 1,
        "market_outcomes": [
            {
                "horizon": h,
                "market_forward_return_pct": round(mkt[h], 2) if mkt.get(h) is not None else None,
                "label": STUDY_LABEL,
            }
            for h in (1, 3, 5)
        ],
        "top_rejected_forward_r": None,
        "avoided_drawdown": None,
        "missed_opportunity": None,
        "reason_accuracy": None,
        "quality_label": quality if n >= MIN_SAMPLES_LEARNING else summary.get("quality_label", "learning"),
        "sample_size": max(n, int(summary.get("sample_size") or 0)),
        "no_edge_samples": int(summary.get("no_edge_samples") or 0),
        "label": STUDY_LABEL,
        "primary_blocker": blockers["primary_blocker"],
        "infrastructure_blockers": blockers["infrastructure_blockers"],
        "quality_blockers": blockers["quality_blockers"],
        "blocker_class": blockers["blocker_class"],
        "learning_mode": summary.get("learning_mode", True),
        "may_authorize_deploy": False,
        "authority_effect": "none",
    }
