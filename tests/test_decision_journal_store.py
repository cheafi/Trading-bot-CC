"""Decision journal store — persist, reload, append-only, blocked rejects sizing."""

from __future__ import annotations

import json

from src.services.decision_journal import (
    DecisionEvent,
    build_event_from_candidate,
    build_no_edge_event,
)
from src.services.decision_journal_store import DecisionJournalStore


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


def test_persist_and_reload(tmp_path):
    store = DecisionJournalStore(
        events_path=str(tmp_path / "events.jsonl"),
        index_path=str(tmp_path / "index.db"),
    )
    evt = build_event_from_candidate(
        {"ticker": "AAPL", "action": "WATCH", "score": 7.0},
        truth=_blocked_truth(),
    )
    store.persist(evt)
    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0]["ticker"] == "AAPL"
    assert loaded[0]["may_authorize_deploy"] is False


def test_append_only_correction_is_new_event(tmp_path):
    store = DecisionJournalStore(
        events_path=str(tmp_path / "events.jsonl"),
        index_path=str(tmp_path / "index.db"),
    )
    evt = build_no_edge_event(truth=_blocked_truth(), session_id="20260709")
    original_id = evt.event_id
    store.persist(evt)
    corrected = store.append_correction(original_id, {"notes": "regime clarified"})
    assert corrected is not None
    assert corrected["event_id"] != original_id
    assert corrected.get("correction_of") == original_id
    all_rows = store.load_all()
    assert len(all_rows) == 2
    with open(store.events_path) as f:
        lines = [ln for ln in f if ln.strip()]
    assert len(lines) == 2


def test_blocked_rejects_sizing_on_persist(tmp_path):
    store = DecisionJournalStore(
        events_path=str(tmp_path / "events.jsonl"),
        index_path=str(tmp_path / "index.db"),
        use_index=False,
    )
    evt = build_event_from_candidate(
        {
            "ticker": "NVDA",
            "action": "TRADE",
            "sizing": {"shares": 50, "risk_pct": 0.5},
        },
        truth=_blocked_truth(),
    )
    stored = store.persist(evt)
    assert stored["position_shares"] is None
    assert stored["risk_pct"] is None


def test_research_surface_authority_effect_none(tmp_path):
    store = DecisionJournalStore(
        events_path=str(tmp_path / "events.jsonl"),
        use_index=False,
    )
    evt = build_event_from_candidate(
        {"ticker": "MSFT", "action": "TRADE"},
        truth={"deploy_authority": True, "execution_readiness": {"broker_connected": True}},
        surface="dossier",
    )
    stored = store.persist(evt)
    assert stored["authority_effect"] == "none"
    assert "deploy" in stored["blocked_actions"]


def test_load_by_event_id(tmp_path):
    store = DecisionJournalStore(
        events_path=str(tmp_path / "events.jsonl"),
        index_path=str(tmp_path / "index.db"),
    )
    evt = DecisionEvent(
        event_id="DE-TEST001",
        timestamp="2026-07-09T00:00:00Z",
        ticker="KO",
        event_type="WATCH_CANDIDATE",
    )
    store.persist(evt)
    found = store.load_by_event_id("DE-TEST001")
    assert found is not None
    assert found["ticker"] == "KO"
