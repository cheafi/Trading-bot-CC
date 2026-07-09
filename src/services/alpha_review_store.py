"""
Alpha Review Store — append-only reports under decision_journal/alpha_reviews/.

Supersede creates a new report; prior rows remain for audit.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal", "alpha_reviews"
)
_REPORTS_PATH = os.environ.get("ALPHA_REVIEW_REPORTS_PATH") or os.path.join(
    _DATA_DIR, "reports.jsonl"
)
_INDEX_PATH = os.environ.get("ALPHA_REVIEW_INDEX_PATH") or os.path.join(
    _DATA_DIR, "index.json"
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "ar") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


@dataclass
class AlphaReviewReport:
    report_id: str
    window_days: int = 20
    status: str = "learning"
    evidence_level: str = "learning"
    sample_size: int = 0
    what_improved: List[str] = field(default_factory=list)
    what_deteriorated: List[str] = field(default_factory=list)
    signal_families: List[Dict[str, Any]] = field(default_factory=list)
    stage_conversion: Dict[str, Any] = field(default_factory=dict)
    rule_actions: List[Dict[str, Any]] = field(default_factory=list)
    human_review_items: List[Dict[str, Any]] = field(default_factory=list)
    review_items: List[Dict[str, Any]] = field(default_factory=list)
    governor_review: Dict[str, Any] = field(default_factory=dict)
    next_actions: List[str] = field(default_factory=list)
    alpha_snapshot_id: str = ""
    supersedes_id: str = ""
    recorded_at: str = field(default_factory=_now_iso)
    collapsed: bool = True
    evidence_only: bool = True
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["evidence_only"] = True
        d["collapsed"] = True
        return d


class AlphaReviewStore:
    """Append-only JSONL store for alpha review reports."""

    def __init__(
        self,
        reports_path: Optional[str] = None,
        index_path: Optional[str] = None,
    ) -> None:
        self.reports_path = reports_path or _REPORTS_PATH
        self.index_path = index_path or _INDEX_PATH
        _ensure_dir(self.reports_path)
        _ensure_dir(self.index_path)

    def _append(self, path: str, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def append_report(self, report: AlphaReviewReport) -> str:
        payload = report.to_dict()
        self._append(self.reports_path, payload)
        self._update_index(payload)
        return report.report_id

    def supersede_report(
        self,
        report: AlphaReviewReport,
        *,
        prior_report_id: str,
    ) -> str:
        report.supersedes_id = prior_report_id
        return self.append_report(report)

    def _update_index(self, payload: Dict[str, Any]) -> None:
        try:
            index: Dict[str, Any] = {}
            if os.path.isfile(self.index_path):
                with open(self.index_path, encoding="utf-8") as f:
                    index = json.load(f)
            index["latest_report_id"] = payload.get("report_id")
            index["latest_status"] = payload.get("status")
            index["latest_evidence_level"] = payload.get("evidence_level")
            index["latest_sample_size"] = payload.get("sample_size")
            index["updated_at"] = _now_iso()
            index["authority_effect"] = "none"
            index["may_authorize_deploy"] = False
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
        except OSError as exc:
            logger.debug("Alpha review index update skipped: %s", exc)

    def load_reports(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.reports_path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.reports_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    def latest_report(self) -> Optional[Dict[str, Any]]:
        rows = self.load_reports(limit=1)
        return rows[-1] if rows else None

    def summary(self) -> Dict[str, Any]:
        latest = self.latest_report() or {}
        rows = self.load_reports(limit=100)
        return {
            "total_reports": len(rows),
            "latest_report_id": latest.get("report_id"),
            "latest_status": latest.get("status", "learning"),
            "latest_evidence_level": latest.get("evidence_level", "learning"),
            "latest_sample_size": latest.get("sample_size", 0),
            "human_review_count": len(latest.get("human_review_items") or []),
            "authority_effect": "none",
            "may_authorize_deploy": False,
            "collapsed": True,
        }


_store: Optional[AlphaReviewStore] = None


def get_alpha_review_store() -> AlphaReviewStore:
    global _store
    if _store is None:
        _store = AlphaReviewStore()
    return _store


def make_report_id() -> str:
    return _new_id("arpt")
