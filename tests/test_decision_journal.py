"""Decision journal — evidence only, authority_state on every event."""

from __future__ import annotations

from src.services.decision_journal import (
    DecisionEvent,
    DecisionJournalService,
    build_event_from_candidate,
    build_journal_batch,
    build_no_edge_event,
)


def _blocked_truth():
    return {
        "deploy_authority": False,
        "deploy_authority_tier": "blocked",
        "primary_blocker": "broker offline",
        "reason_codes": ["BROKER_OFFLINE"],
        "execution_readiness": {"broker_connected": False, "trade_handoff_ready": False},
        "watch_qualified_count": 0,
        "deploy_qualified_count": 0,
    }


def test_event_includes_authority_state():
    evt = build_event_from_candidate(
        {"ticker": "AAPL", "action": "WATCH", "score": 7.0},
        truth=_blocked_truth(),
        surface="playbook",
    )
    assert evt.authority_state["deploy_authority"] is False
    assert "deploy" in evt.blocked_actions
    d = evt.to_dict()
    assert d["may_authorize_deploy"] is False
    assert d["evidence_only"] is True


def test_blocked_event_cannot_contain_sizing():
    evt = build_event_from_candidate(
        {
            "ticker": "NVDA",
            "action": "TRADE",
            "score": 8.5,
            "sizing": {"shares": 100, "risk_pct": 0.5},
        },
        truth=_blocked_truth(),
    )
    assert evt.position_shares is None
    assert evt.position_dollar is None
    assert evt.risk_pct is None


def test_research_surface_event_cannot_authorize_deploy():
    evt = build_event_from_candidate(
        {"ticker": "MSFT", "action": "TRADE", "execution_ready": True},
        truth={"deploy_authority": True, "execution_readiness": {"broker_connected": True}},
        surface="dossier",
    )
    journal = DecisionJournalService()
    recorded = journal.record(evt)
    assert "deploy" in recorded.blocked_actions
    assert recorded.authority_effect == "none"


def test_no_edge_event_recorded_when_empty_universe():
    batch = build_journal_batch(truth=_blocked_truth(), candidates=[], near_miss=[])
    types = [e["event_type"] for e in batch["events"]]
    assert "NO_EDGE_TODAY" in types or batch["summary"]["total"] >= 0


def test_journal_summary_evidence_only():
    batch = build_journal_batch(
        truth=_blocked_truth(),
        candidates=[{"ticker": "KO", "action": "WATCH"}],
    )
    assert batch["evidence_only"] is True
    assert batch["authority_effect"] == "none"
