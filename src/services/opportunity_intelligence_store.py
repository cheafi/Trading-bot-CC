"""
Opportunity Intelligence Store — append-only candidates, score snapshots, stage transitions.

Persisted under data/decision_journal/opportunities/. Research surfaces always
authority_effect=none; no surface may authorize deploy from stored evidence alone.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FUNNEL_STAGES: Tuple[str, ...] = (
    "raw_universe",
    "research_hit",
    "evidence_candidate",
    "watch_candidate",
    "near_miss",
    "playbook_review",
    "deploy_review",
    "capital_candidate",
)

SURFACE_STAGE_CAPS: Dict[str, str] = {
    "discovery": "research_hit",
    "scanners": "research_hit",
    "rs": "evidence_candidate",
    "flow": "evidence_candidate",
    "playbook": "playbook_review",
    "signals": "playbook_review",
    "dossier": "evidence_candidate",
    "rejections": "near_miss",
    "watchlist": "watch_candidate",
    "funds": "capital_candidate",
    "agent": "evidence_candidate",
    "strategy": "evidence_candidate",
    "strategy_lab": "evidence_candidate",
    "portfolio": "watch_candidate",
    "dashboard": "playbook_review",
}

_RESEARCH_SURFACES = frozenset(
    {
        "discovery",
        "scanners",
        "dossier",
        "research",
        "strategy_lab",
        "backtest",
        "guide",
        "rs",
        "flow",
    }
)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal", "opportunities"
)
_CANDIDATES_PATH = os.environ.get("OPPORTUNITY_CANDIDATES_PATH") or os.path.join(
    _DATA_DIR, "candidates.jsonl"
)
_SNAPSHOTS_PATH = os.environ.get("OPPORTUNITY_SNAPSHOTS_PATH") or os.path.join(
    _DATA_DIR, "score_snapshots.jsonl"
)
_TRANSITIONS_PATH = os.environ.get("OPPORTUNITY_TRANSITIONS_PATH") or os.path.join(
    _DATA_DIR, "stage_transitions.jsonl"
)
_INDEX_PATH = os.environ.get("OPPORTUNITY_INDEX_PATH") or os.path.join(
    _DATA_DIR, "index.db"
)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "opp") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


def _stage_index(stage: str) -> int:
    try:
        return FUNNEL_STAGES.index(stage)
    except ValueError:
        return 0


@dataclass
class OpportunityCandidate:
    candidate_id: str
    ticker: str
    stage: str = "raw_universe"
    source_surface: str = "dashboard"
    source_family: str = ""
    setup_tags: List[str] = field(default_factory=list)
    regime: str = ""
    sector: str = ""
    theme: str = ""
    dedupe_key: str = ""
    session_id: str = ""
    recorded_at: str = field(default_factory=_now_iso)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False
    evidence_only: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        d["evidence_only"] = True
        return d


@dataclass
class OpportunityScoreSnapshot:
    snapshot_id: str
    candidate_id: str
    ticker: str
    stage: str
    evidence_grade: str = "ungraded"
    evidence_score: float = 0.0
    calibration_state: str = "learning"
    sample_size: int = 0
    hit_rate_range: Optional[Dict[str, Any]] = None
    expectancy_range: Optional[Dict[str, Any]] = None
    cost_drag_r: Optional[float] = None
    cost_adjusted_expected_r: Optional[Dict[str, Any]] = None
    pattern_status: str = "unvalidated"
    screen_labels: List[str] = field(default_factory=list)
    session_id: str = ""
    recorded_at: str = field(default_factory=_now_iso)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        return d


@dataclass
class OpportunityStageTransition:
    transition_id: str
    candidate_id: str
    ticker: str
    from_stage: str
    to_stage: str
    reason: str = ""
    source_surface: str = "dashboard"
    session_id: str = ""
    recorded_at: str = field(default_factory=_now_iso)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        return d


def apply_authority_effect_rules(
    *,
    surface: str,
    stage: str,
    deploy_authority: bool = False,
) -> Dict[str, Any]:
    """Research surfaces and pre-deploy_review stages never grant authority."""
    surf = str(surface or "").lower()
    st = str(stage or "raw_universe")
    effect = "none"
    if deploy_authority and st in ("deploy_review", "capital_candidate"):
        effect = "review_only"
    if surf in _RESEARCH_SURFACES:
        effect = "none"
    if st in ("raw_universe", "research_hit", "evidence_candidate", "watch_candidate", "near_miss"):
        effect = "none"
    return {
        "authority_effect": effect,
        "may_authorize_deploy": False,
        "evidence_only": True,
    }


def cap_stage_for_surface(stage: str, surface: str) -> str:
    """Clamp stage to per-surface ceiling."""
    cap = SURFACE_STAGE_CAPS.get(str(surface or "").lower(), "evidence_candidate")
    if _stage_index(stage) > _stage_index(cap):
        return cap
    return stage


def _get_index(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _INDEX_PATH
    _ensure_dir(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS opportunity_candidates (
            candidate_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            stage TEXT NOT NULL,
            dedupe_key TEXT,
            session_id TEXT,
            recorded_at TEXT NOT NULL,
            line_offset INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_oc_ticker ON opportunity_candidates(ticker);
        CREATE INDEX IF NOT EXISTS idx_oc_stage ON opportunity_candidates(stage);
        CREATE INDEX IF NOT EXISTS idx_oc_dedupe ON opportunity_candidates(dedupe_key);
        CREATE TABLE IF NOT EXISTS opportunity_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            candidate_id TEXT,
            ticker TEXT,
            stage TEXT,
            recorded_at TEXT NOT NULL,
            line_offset INTEGER
        );
        CREATE TABLE IF NOT EXISTS opportunity_transitions (
            transition_id TEXT PRIMARY KEY,
            candidate_id TEXT,
            from_stage TEXT,
            to_stage TEXT,
            recorded_at TEXT NOT NULL,
            line_offset INTEGER
        );
        """
    )
    return conn


class OpportunityIntelligenceStore:
    """Append-only JSONL store for candidates, snapshots, and transitions."""

    def __init__(
        self,
        candidates_path: Optional[str] = None,
        snapshots_path: Optional[str] = None,
        transitions_path: Optional[str] = None,
        index_path: Optional[str] = None,
        *,
        use_index: bool = True,
    ) -> None:
        self.candidates_path = candidates_path or _CANDIDATES_PATH
        self.snapshots_path = snapshots_path or _SNAPSHOTS_PATH
        self.transitions_path = transitions_path or _TRANSITIONS_PATH
        self.index_path = index_path or _INDEX_PATH
        self.use_index = use_index
        for p in (self.candidates_path, self.snapshots_path, self.transitions_path):
            _ensure_dir(p)

    def _append(self, path: str, payload: Dict[str, Any]) -> int:
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            offset = f.tell() - len(line.encode("utf-8"))
        return max(0, offset)

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.isfile(path):
            return []
        out: List[Dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping corrupt opportunity line in %s", path)
        return out

    def persist_candidate(
        self,
        candidate: OpportunityCandidate,
        *,
        deploy_authority: bool = False,
    ) -> Dict[str, Any]:
        auth = apply_authority_effect_rules(
            surface=candidate.source_surface,
            stage=candidate.stage,
            deploy_authority=deploy_authority,
        )
        candidate.stage = cap_stage_for_surface(candidate.stage, candidate.source_surface)
        candidate.authority_effect = auth["authority_effect"]
        candidate.may_authorize_deploy = False
        payload = candidate.to_dict()
        offset = self._append(self.candidates_path, payload)
        if self.use_index:
            conn = _get_index(self.index_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO opportunity_candidates
                (candidate_id, ticker, stage, dedupe_key, session_id, recorded_at, line_offset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.ticker,
                    candidate.stage,
                    candidate.dedupe_key,
                    candidate.session_id,
                    candidate.recorded_at,
                    offset,
                ),
            )
            conn.commit()
            conn.close()
        return payload

    def persist_snapshot(self, snapshot: OpportunityScoreSnapshot) -> Dict[str, Any]:
        snapshot.authority_effect = "none"
        snapshot.may_authorize_deploy = False
        payload = snapshot.to_dict()
        offset = self._append(self.snapshots_path, payload)
        if self.use_index:
            conn = _get_index(self.index_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO opportunity_snapshots
                (snapshot_id, candidate_id, ticker, stage, recorded_at, line_offset)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.candidate_id,
                    snapshot.ticker,
                    snapshot.stage,
                    snapshot.recorded_at,
                    offset,
                ),
            )
            conn.commit()
            conn.close()
        return payload

    def persist_transition(
        self,
        transition: OpportunityStageTransition,
        *,
        deploy_authority: bool = False,
    ) -> Dict[str, Any]:
        auth = apply_authority_effect_rules(
            surface=transition.source_surface,
            stage=transition.to_stage,
            deploy_authority=deploy_authority,
        )
        transition.authority_effect = auth["authority_effect"]
        transition.may_authorize_deploy = False
        payload = transition.to_dict()
        offset = self._append(self.transitions_path, payload)
        if self.use_index:
            conn = _get_index(self.index_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO opportunity_transitions
                (transition_id, candidate_id, from_stage, to_stage, recorded_at, line_offset)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transition.transition_id,
                    transition.candidate_id,
                    transition.from_stage,
                    transition.to_stage,
                    transition.recorded_at,
                    offset,
                ),
            )
            conn.commit()
            conn.close()
        return payload

    def load_candidates(self, *, limit: int = 500) -> List[Dict[str, Any]]:
        rows = self._load_jsonl(self.candidates_path)
        return rows[-limit:]

    def load_snapshots(self, *, limit: int = 500) -> List[Dict[str, Any]]:
        rows = self._load_jsonl(self.snapshots_path)
        return rows[-limit:]

    def load_transitions(self, *, limit: int = 500) -> List[Dict[str, Any]]:
        rows = self._load_jsonl(self.transitions_path)
        return rows[-limit:]

    def find_by_dedupe_key(self, dedupe_key: str) -> Optional[Dict[str, Any]]:
        for row in reversed(self.load_candidates(limit=2000)):
            if str(row.get("dedupe_key") or "") == dedupe_key:
                return row
        return None

    def count_by_stage(self) -> Dict[str, int]:
        counts: Dict[str, int] = {s: 0 for s in FUNNEL_STAGES}
        for row in self.load_candidates():
            st = str(row.get("stage") or "raw_universe")
            counts[st] = counts.get(st, 0) + 1
        return counts

    def summary(self) -> Dict[str, Any]:
        candidates = self.load_candidates()
        snapshots = self.load_snapshots(limit=100)
        transitions = self.load_transitions(limit=100)
        return {
            "candidates_total": len(candidates),
            "snapshots_total": len(self._load_jsonl(self.snapshots_path)),
            "transitions_total": len(self._load_jsonl(self.transitions_path)),
            "by_stage": self.count_by_stage(),
            "recent_snapshots": len(snapshots),
            "recent_transitions": len(transitions),
            "store_path": self.candidates_path,
            "evidence_only": True,
            "may_authorize_deploy": False,
            "authority_effect": "none",
        }


def get_opportunity_intelligence_store(
    candidates_path: Optional[str] = None,
    index_path: Optional[str] = None,
) -> OpportunityIntelligenceStore:
    return OpportunityIntelligenceStore(
        candidates_path=candidates_path,
        index_path=index_path,
    )
