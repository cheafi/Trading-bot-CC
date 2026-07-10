"""
Threshold Governance Store — append-only proposals, decisions, live changes.

data/decision_journal/threshold_governance/
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
    os.path.dirname(__file__), "..", "..", "data", "decision_journal", "threshold_governance"
)
_PROPOSALS_PATH = os.environ.get("THRESHOLD_PROPOSALS_PATH") or os.path.join(
    _DATA_DIR, "proposals.jsonl"
)
_DECISIONS_PATH = os.environ.get("THRESHOLD_DECISIONS_PATH") or os.path.join(
    _DATA_DIR, "decisions.jsonl"
)
_LIVE_CHANGES_PATH = os.environ.get("THRESHOLD_LIVE_CHANGES_PATH") or os.path.join(
    _DATA_DIR, "live_changes.jsonl"
)
_INDEX_PATH = os.environ.get("THRESHOLD_GOVERNANCE_INDEX_PATH") or os.path.join(
    _DATA_DIR, "index.json"
)

PROPOSAL_STATUSES: tuple[str, ...] = (
    "open",
    "shadow",
    "approved_shadow",
    "rejected",
    "deferred",
    "more_samples",
    "promoted",
    "rolled_back",
)

PROPOSAL_TYPES: tuple[str, ...] = (
    "tighten",
    "loosen_review",
    "retire_threshold",
    "collect_more_samples",
    "no_change",
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "tgp") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


@dataclass
class ThresholdProposal:
    proposal_id: str
    threshold_key: str
    proposal_type: str = "no_change"
    status: str = "open"
    current_value: float = 0.0
    proposed_value: Optional[float] = None
    rationale: str = ""
    source: str = "alpha_review"
    source_report_id: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    rollback_value: Optional[float] = None
    reviewer: str = ""
    reviewer_rationale: str = ""
    shadow_run_id: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    may_authorize_deploy: bool = False
    authority_effect: str = "none"
    can_auto_loosen: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["can_auto_loosen"] = False
        if d["proposal_type"] == "loosen_review":
            d["status"] = d["status"] if d["status"] != "promoted" else "shadow"
        return d


@dataclass
class ThresholdDecision:
    decision_id: str
    proposal_id: str
    action: str
    reviewer: str
    rationale: str = ""
    prior_status: str = ""
    new_status: str = ""
    recorded_at: str = field(default_factory=_now_iso)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        return d


@dataclass
class ThresholdLiveChange:
    change_id: str
    proposal_id: str
    threshold_key: str
    prior_value: float
    new_value: float
    rollback_value: float
    action: str = "promote_to_live"
    reviewer: str = ""
    rationale: str = ""
    recorded_at: str = field(default_factory=_now_iso)
    rolled_back: bool = False
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        return d


class ThresholdGovernanceStore:
    """Append-only store for threshold governance audit trail."""

    def __init__(
        self,
        proposals_path: Optional[str] = None,
        decisions_path: Optional[str] = None,
        live_changes_path: Optional[str] = None,
        index_path: Optional[str] = None,
    ) -> None:
        self.proposals_path = proposals_path or _PROPOSALS_PATH
        self.decisions_path = decisions_path or _DECISIONS_PATH
        self.live_changes_path = live_changes_path or _LIVE_CHANGES_PATH
        self.index_path = index_path or _INDEX_PATH
        for p in (self.proposals_path, self.decisions_path, self.live_changes_path):
            _ensure_dir(p)
        _ensure_dir(self.index_path)

    def _append(self, path: str, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.isfile(path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _latest_by_id(self, path: str, id_field: str) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for row in self._load_jsonl(path):
            rid = str(row.get(id_field) or "")
            if rid:
                latest[rid] = row
        return latest

    def append_proposal(self, proposal: ThresholdProposal) -> str:
        payload = proposal.to_dict()
        self._append(self.proposals_path, payload)
        self._update_index()
        return proposal.proposal_id

    def update_proposal(self, proposal: ThresholdProposal) -> str:
        proposal.updated_at = _now_iso()
        return self.append_proposal(proposal)

    def append_decision(self, decision: ThresholdDecision) -> str:
        payload = decision.to_dict()
        self._append(self.decisions_path, payload)
        self._update_index()
        return decision.decision_id

    def append_live_change(self, change: ThresholdLiveChange) -> str:
        payload = change.to_dict()
        self._append(self.live_changes_path, payload)
        self._update_index()
        return change.change_id

    def _update_index(self) -> None:
        try:
            proposals = self._latest_by_id(self.proposals_path, "proposal_id")
            open_count = sum(
                1 for p in proposals.values() if p.get("status") in ("open", "deferred")
            )
            shadow_count = sum(
                1
                for p in proposals.values()
                if p.get("status") in ("shadow", "approved_shadow")
            )
            index = {
                "open_proposals": open_count,
                "shadow_proposals": shadow_count,
                "total_proposals": len(proposals),
                "updated_at": _now_iso(),
                "authority_effect": "none",
                "may_authorize_deploy": False,
                "can_auto_loosen": False,
            }
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
        except OSError as exc:
            logger.debug("Threshold governance index update skipped: %s", exc)

    def load_proposals(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        latest = self._latest_by_id(self.proposals_path, "proposal_id")
        rows = list(latest.values())
        rows.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        return rows[:limit]

    def open_proposals(self) -> List[Dict[str, Any]]:
        return [
            p
            for p in self.load_proposals()
            if p.get("status") in ("open", "deferred", "more_samples")
        ]

    def shadow_proposals(self) -> List[Dict[str, Any]]:
        return [
            p
            for p in self.load_proposals()
            if p.get("status") in ("shadow", "approved_shadow")
        ]

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self._latest_by_id(self.proposals_path, "proposal_id").get(proposal_id)

    def load_decisions(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        return self._load_jsonl(self.decisions_path)[-limit:]

    def load_live_changes(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        return self._load_jsonl(self.live_changes_path)[-limit:]

    def summary(self) -> Dict[str, Any]:
        open_p = self.open_proposals()
        shadow_p = self.shadow_proposals()
        live = self.load_live_changes(limit=10)
        recent_live = [c for c in live if not c.get("rolled_back")]
        return {
            "open_count": len(open_p),
            "shadow_count": len(shadow_p),
            "live_change_count": len(recent_live),
            "open_proposals": open_p[:10],
            "shadow_proposals": shadow_p[:10],
            "no_live_changes_from_analytics": True,
            "can_auto_loosen": False,
            "authority_effect": "none",
            "may_authorize_deploy": False,
            "collapsed": True,
        }


_store: Optional[ThresholdGovernanceStore] = None


def get_threshold_governance_store() -> ThresholdGovernanceStore:
    global _store
    if _store is None:
        _store = ThresholdGovernanceStore()
    return _store


def make_proposal_id() -> str:
    return _new_id("tprop")


def make_decision_id() -> str:
    return _new_id("tdec")


def make_change_id() -> str:
    return _new_id("tlch")
