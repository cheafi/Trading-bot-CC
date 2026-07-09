"""
Decision Journal — evidence-only event log for decision quality learning.

Journal events never authorize deploy. Every event records authority_state
and blocked_actions. Sizing/handoff fields only when authority chain permits.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

EVENT_TYPES: Set[str] = {
    "BOARD_BLOCKED",
    "NO_EDGE_TODAY",
    "WATCH_CANDIDATE",
    "NEAR_MISS",
    "DEPLOY_CANDIDATE",
    "DOSSIER_CONFIRM_ONLY",
    "MONITOR_RULE_CREATED",
    "PAPER_DRAFT_CREATED",
    "LIVE_HANDOFF_READY",
    "TRADE_EXECUTED",
    "TRADE_REJECTED",
    "STOP_BREACH",
    "TARGET_HIT",
    "RULE_TRIGGERED",
    "OPERATOR_OVERRIDE_ATTEMPT",
    "AUTHORITY_GUARDRAIL_BLOCKED",
}

_RESEARCH_SURFACES = frozenset({"dossier", "research", "strategy_lab", "backtest", "guide"})
_SIZING_FIELDS = frozenset({"position_shares", "position_dollar", "risk_pct", "size_multiplier"})


@dataclass
class DecisionEvent:
    """Canonical decision event — evidence only, never deploy authority."""

    event_id: str
    timestamp: str
    session_id: str = ""
    surface: str = "dashboard"
    ticker: str = ""
    event_type: str = "WATCH_CANDIDATE"
    authority_state: Dict[str, Any] = field(default_factory=dict)
    board_state: Dict[str, Any] = field(default_factory=dict)
    market_state: Dict[str, Any] = field(default_factory=dict)
    brief_state: Dict[str, Any] = field(default_factory=dict)
    broker_state: Dict[str, Any] = field(default_factory=dict)
    runtime_state: Dict[str, Any] = field(default_factory=dict)
    candidate_bucket: str = ""
    score: Optional[float] = None
    thesis_score: Optional[float] = None
    timing_score: Optional[float] = None
    exec_score: Optional[float] = None
    data_score: Optional[float] = None
    rr: Optional[float] = None
    entry_ref: Optional[float] = None
    stop_ref: Optional[float] = None
    target_ref: Optional[float] = None
    expected_r: Optional[float] = None
    allowed_actions: List[str] = field(default_factory=list)
    blocked_actions: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    signal_families: List[str] = field(default_factory=list)
    operator_action: str = ""
    authority_effect: str = "none"
    notes: str = ""
    position_shares: Optional[int] = None
    position_dollar: Optional[float] = None
    risk_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for k in ("score", "thesis_score", "timing_score", "exec_score", "data_score", "rr",
                  "entry_ref", "stop_ref", "target_ref", "expected_r", "position_dollar", "risk_pct"):
            if d.get(k) is not None:
                d[k] = round(float(d[k]), 2) if k != "position_shares" else d[k]
        d["evidence_only"] = True
        d["may_authorize_deploy"] = False
        return d


def _new_event_id() -> str:
    return f"DE-{uuid.uuid4().hex[:10].upper()}"


def _authority_snapshot(truth: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t = dict(truth or {})
    return {
        "deploy_authority": bool(t.get("deploy_authority")),
        "deploy_authority_tier": str(t.get("deploy_authority_tier") or "blocked"),
        "board_gate": str(t.get("board_gate") or ""),
        "regime_state": str(t.get("regime_state") or ""),
        "primary_blocker": str(t.get("primary_blocker") or ""),
        "reason_codes": list(t.get("reason_codes") or [])[:8],
    }


def _blocked_actions_for_truth(truth: Dict[str, Any], surface: str) -> List[str]:
    blocked: List[str] = []
    if not truth.get("deploy_authority"):
        blocked.extend(["deploy", "size", "live_handoff"])
    if surface in _RESEARCH_SURFACES:
        blocked.extend(["deploy", "size", "live_handoff", "paper_draft"])
    er = truth.get("execution_readiness") or {}
    if not er.get("broker_connected"):
        blocked.append("live_handoff")
    if not er.get("trade_handoff_ready"):
        blocked.append("live_handoff")
    return sorted(set(blocked))


def _allowed_actions_for_truth(truth: Dict[str, Any], surface: str) -> List[str]:
    allowed = ["monitor", "review_dossier", "create_alert"]
    if surface in ("dashboard", "playbook", "agent"):
        allowed.append("promote_to_playbook_review")
    if truth.get("deploy_authority") and surface in ("dashboard", "playbook"):
        er = truth.get("execution_readiness") or {}
        if er.get("broker_connected"):
            allowed.append("paper_draft")
        if er.get("trade_handoff_ready"):
            allowed.append("deploy_review")
    return sorted(set(allowed))


def _event_type_for_row(row: Dict[str, Any], bucket: str = "") -> str:
    action = str(row.get("action") or row.get("effective_action") or "WATCH").upper()
    bucket = str(bucket or row.get("candidate_bucket") or "").lower()
    if bucket == "near_miss" or row.get("near_miss"):
        return "NEAR_MISS"
    if action in ("TRADE", "DEPLOY", "STRONG_TRADE", "BUY", "BUY_ON_DIP"):
        return "DEPLOY_CANDIDATE"
    if action in ("AVOID", "NO_TRADE", "BLOCKED", "PASS"):
        return "BOARD_BLOCKED"
    if action == "PILOT":
        return "WATCH_CANDIDATE"
    return "WATCH_CANDIDATE"


def _strip_sizing_if_blocked(event: DecisionEvent) -> DecisionEvent:
    """Remove sizing fields when authority does not permit."""
    auth = event.authority_state or {}
    blocked = set(a.lower() for a in (event.blocked_actions or []))
    surface = str(event.surface or "").lower()
    may_size = (
        auth.get("deploy_authority")
        and "size" not in blocked
        and "deploy" not in blocked
        and surface not in _RESEARCH_SURFACES
        and (event.broker_state or {}).get("handoff_ready")
    )
    if not may_size:
        event.position_shares = None
        event.position_dollar = None
        event.risk_pct = None
    return event


def build_event_from_candidate(
    row: Dict[str, Any],
    *,
    truth: Optional[Dict[str, Any]] = None,
    surface: str = "playbook",
    session_id: str = "",
    bucket: str = "",
) -> DecisionEvent:
    """Build a DecisionEvent from a playbook/today row."""
    t = dict(truth or {})
    ticker = str(row.get("ticker") or "").upper().strip()
    blocked = _blocked_actions_for_truth(t, surface)
    allowed = _allowed_actions_for_truth(t, surface)
    er = t.get("execution_readiness") or {}
    evt = DecisionEvent(
        event_id=_new_event_id(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        surface=surface,
        ticker=ticker,
        event_type=_event_type_for_row(row, bucket),
        authority_state=_authority_snapshot(t),
        board_state={
            "tradeability": str(t.get("tradeability") or t.get("board_gate") or ""),
            "deploy_qualified": int(t.get("deploy_qualified_count") or 0),
            "watch_qualified": int(t.get("watch_qualified_count") or 0),
        },
        market_state={
            "regime": str(t.get("regime_state") or ""),
            "vix": t.get("vix"),
        },
        brief_state={
            "freshness": str(t.get("brief_freshness") or ""),
            "expired": bool(t.get("brief_expired")),
        },
        broker_state={
            "connected": bool(er.get("broker_connected")),
            "handoff_ready": bool(er.get("trade_handoff_ready")),
        },
        runtime_state={"state": str(t.get("runtime_state") or "")},
        candidate_bucket=bucket or str(row.get("bucket") or ""),
        score=float(row["score"]) if row.get("score") is not None else None,
        thesis_score=float(row["thesis_conf"]) if row.get("thesis_conf") is not None else None,
        timing_score=float(row["timing_conf"]) if row.get("timing_conf") is not None else None,
        exec_score=float(row.get("execution_conf") or row.get("exec_conf") or 0) or None,
        data_score=float(row["data_conf"]) if row.get("data_conf") is not None else None,
        rr=float(row.get("risk_reward") or row.get("rr_ratio") or row.get("rr") or 0) or None,
        entry_ref=float(row["entry_price"]) if row.get("entry_price") else None,
        stop_ref=float(row["stop_price"]) if row.get("stop_price") else None,
        target_ref=float(row["target_price"]) if row.get("target_price") else None,
        expected_r=float(row["expected_r"]) if row.get("expected_r") is not None else None,
        allowed_actions=allowed,
        blocked_actions=blocked,
        reason_codes=list(t.get("reason_codes") or [])[:6],
        signal_families=list(row.get("signal_families") or []),
        authority_effect="none",
        notes="evidence only — journal does not authorize deploy",
    )
    sizing = row.get("sizing") or {}
    if sizing and t.get("deploy_authority"):
        evt.position_shares = int(sizing.get("shares") or sizing.get("quantity") or 0) or None
        evt.position_dollar = float(sizing.get("dollar") or sizing.get("notional") or 0) or None
        evt.risk_pct = float(sizing.get("risk_pct") or 0) or None
    return _strip_sizing_if_blocked(evt)


def build_no_edge_event(
    *,
    truth: Optional[Dict[str, Any]] = None,
    surface: str = "dashboard",
    session_id: str = "",
) -> DecisionEvent:
    t = dict(truth or {})
    return _strip_sizing_if_blocked(
        DecisionEvent(
            event_id=_new_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            surface=surface,
            ticker="",
            event_type="NO_EDGE_TODAY",
            authority_state=_authority_snapshot(t),
            board_state={"deploy_qualified": int(t.get("deploy_qualified_count") or 0)},
            market_state={"regime": str(t.get("regime_state") or "")},
            brief_state={"freshness": str(t.get("brief_freshness") or "")},
            broker_state={
                "connected": bool((t.get("execution_readiness") or {}).get("broker_connected")),
            },
            allowed_actions=["monitor", "create_alert"],
            blocked_actions=_blocked_actions_for_truth(t, surface),
            reason_codes=list(t.get("reason_codes") or [])[:6],
            authority_effect="none",
            notes="no-edge day — cash protected; forward outcome study only",
        )
    )


class DecisionJournalService:
    """In-memory bounded journal — evidence only."""

    MAX_EVENTS = 500

    def __init__(self) -> None:
        self._events: deque[DecisionEvent] = deque(maxlen=self.MAX_EVENTS)

    def record(self, event: DecisionEvent) -> DecisionEvent:
        if event.event_type not in EVENT_TYPES:
            event.event_type = "WATCH_CANDIDATE"
        event = _strip_sizing_if_blocked(event)
        if str(event.surface or "").lower() in _RESEARCH_SURFACES:
            event.blocked_actions = sorted(
                set(event.blocked_actions or []) | {"deploy", "size", "live_handoff"}
            )
            event.authority_effect = "none"
        self._events.append(event)
        return event

    def recent(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in list(self._events)[-limit:]]

    def by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events if e.event_type == event_type]

    def summary(self) -> Dict[str, Any]:
        events = list(self._events)
        by_type: Dict[str, int] = {}
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        return {
            "total": len(events),
            "by_type": by_type,
            "evidence_only": True,
            "may_authorize_deploy": False,
        }


def build_journal_batch(
    *,
    truth: Optional[Dict[str, Any]] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    surface: str = "dashboard",
    session_id: str = "",
    limit: int = 20,
    persist: bool = False,
    store: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build journal events for today payload; optionally persist to store."""
    journal = DecisionJournalService()
    t = dict(truth or {})
    deploy_n = int(t.get("deploy_qualified_count") or 0)
    if deploy_n < 1 and int(t.get("watch_qualified_count") or 0) < 1:
        journal.record(build_no_edge_event(truth=t, surface=surface, session_id=session_id))

    for row in candidates or []:
        journal.record(
            build_event_from_candidate(row, truth=t, surface=surface, session_id=session_id)
        )
    for row in near_miss or []:
        journal.record(
            build_event_from_candidate(
                row, truth=t, surface=surface, session_id=session_id, bucket="near_miss"
            )
        )

    result = {
        "events": journal.recent(limit=limit),
        "summary": journal.summary(),
        "evidence_only": True,
        "authority_effect": "none",
    }
    if persist:
        from src.services.decision_journal_store import (
            get_decision_journal_store,
            persist_journal_batch,
        )

        st = store or get_decision_journal_store()
        persist_result = persist_journal_batch(result, session_id=session_id, store=st)
        result["persisted"] = persist_result
        result["store_summary"] = st.summary()
    return result
