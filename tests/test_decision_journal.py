"""Tests for IDOS Decision Journal (Phase 1) and challenge engine stubs."""

from __future__ import annotations

import asyncio
import json

import pytest

from src.services.decision_journal import (
    append_entry,
    load_recent,
    maybe_stub_from_decision_id,
    record_deploy_intent_stub,
    summary,
)


@pytest.fixture
def journal_path(tmp_path, monkeypatch):
    path = tmp_path / "decision_journal.jsonl"
    monkeypatch.setattr("src.services.decision_journal._DATA_PATH", path)
    return path


def _full_payload(**overrides):
    base = {
        "decision": "WAIT",
        "ticker": "AAPL",
        "decision_id": "dec-AAPL-test",
        "thesis": "Cash is winning; no marginal deploy beats hurdle.",
        "alternatives_considered": ["deploy AAPL", "cash", "trim MSFT"],
        "rejected_alternative": "deploy AAPL — below marginal ROC hurdle",
        "expected_probability": 0.42,
        "expected_downside": "-8% to stop",
        "expected_upside": "+18% to target",
        "why_now": "Explicit wait day — document discipline.",
        "what_changes_mind": "Deploy_open + beat cash hurdle on fresh data.",
    }
    base.update(overrides)
    return base


def test_append_entry_writes_jsonl(journal_path):
    entry = append_entry(_full_payload())
    assert journal_path.is_file()
    row = json.loads(journal_path.read_text(encoding="utf-8").strip())
    assert row["entry_id"] == entry["entry_id"]
    assert row["decision"] == "WAIT"
    assert row["authority"] == "research_only"
    assert row["may_authorize_deploy"] is False
    assert "30d" in row["review_dates"]
    assert row["four_questions"]["act"] == "WAIT"
    assert row["outcome"] is None


def test_append_entry_requires_fields(journal_path):
    with pytest.raises(ValueError, match="missing required fields"):
        append_entry({"decision": "DEPLOY"})


def test_load_recent_returns_newest_first(journal_path):
    append_entry(_full_payload(decision="WAIT", thesis="first"))
    append_entry(_full_payload(decision="DEPLOY", thesis="second"))
    recent = load_recent(limit=2)
    assert len(recent) == 2
    assert recent[0]["thesis"] == "second"
    assert recent[1]["thesis"] == "first"


def test_maybe_stub_from_decision_id_idempotent(journal_path):
    first = maybe_stub_from_decision_id(decision_id="dec-001", ticker="NVDA")
    second = maybe_stub_from_decision_id(decision_id="dec-001", ticker="NVDA")
    assert first is not None
    assert first["stub"] is True
    assert second is None
    assert len(journal_path.read_text(encoding="utf-8").splitlines()) == 1


def test_record_deploy_intent_stub(journal_path):
    row = record_deploy_intent_stub(ticker="MSFT", decision_id="dec-msft-1")
    assert row is not None
    assert row["decision"] == "DEPLOY_INTENT"
    assert row["source"] == "deploy_intent_hook"


def test_summary_payload(journal_path):
    append_entry(_full_payload())
    payload = summary(limit=5)
    assert payload["authority"] == "research_only"
    assert payload["recent_count"] == 1
    assert payload["entries"][0]["ticker"] == "AAPL"


def test_decision_journal_api_contract(journal_path):
    from src.api.routers import decision as decision_router

    created = asyncio.run(
        decision_router.decision_journal_create_entry(_full_payload(decision="NO_ACTION"))
    )
    assert created["ok"] is True
    assert created["authority"] == "research_only"
    assert created["entry"]["decision"] == "NO_ACTION"

    recent = asyncio.run(decision_router.decision_journal_recent(limit=10))
    assert recent["authority"] == "research_only"
    assert len(recent["entries"]) >= 1


def test_belief_review_hook_creates_stub(journal_path, monkeypatch):
    from src.api.routers import decision as decision_router

    monkeypatch.setattr(
        "src.services.forward_outcomes.load_forward_outcomes",
        lambda limit=50: [
            {
                "ticker": "AAPL",
                "decision_id": "dec-hook-001",
                "horizon": "T+0",
                "authority": "research_only",
            }
        ],
    )
    monkeypatch.setattr(
        "src.services.belief_review._load_store",
        lambda: {"items": {}},
    )
    asyncio.run(decision_router.belief_review_summary())
    rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["decision_id"] == "dec-hook-001"
    assert rows[0]["stub"] is True


def test_red_team_api_stub():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.red_team_challenge(ticker="AAPL"))
    assert payload["authority"] == "research_only"
    assert payload["status"] == "stub"
    assert "four_questions" in payload
    assert "challenges" in payload


def test_outside_view_api_stub():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.outside_view_base_rate(setup_type="breakout"))
    assert payload["authority"] == "research_only"
    assert payload["base_rate"]["class"] == "breakout"


def test_decision_committee_api_stub():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.decision_committee_review(ticker="MSFT"))
    assert payload["authority"] == "research_only"
    assert len(payload["members"]) == 7


def test_decision_health_api_stub():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.decision_health_summary())
    assert payload["authority"] == "research_only"
    assert payload["status"] == "stub"
    assert "inputs" in payload


def test_deploy_intent_journal_checklist_missing(journal_path):
    from src.services.decision_journal import deploy_intent_journal_status

    payload = deploy_intent_journal_status(decision_id="dec-missing", ticker="AAPL")
    assert payload["authority"] == "research_only"
    assert payload["complete"] is False
    assert payload["status"] == "missing"
    assert "thesis" in payload["missing_fields"]


def test_deploy_intent_journal_checklist_complete(journal_path):
    from src.api.routers import decision as decision_router
    from src.services.decision_journal import deploy_intent_journal_status

    asyncio.run(
        decision_router.decision_journal_create_entry(_full_payload(decision="DEPLOY"))
    )
    payload = deploy_intent_journal_status(
        decision_id="dec-AAPL-test", ticker="AAPL"
    )
    assert payload["complete"] is True
    assert payload["status"] == "complete"
    assert payload["may_authorize_deploy"] is False


def test_deploy_intent_journal_api_contract(journal_path):
    from src.api.routers import decision as decision_router

    payload = asyncio.run(
        decision_router.decision_journal_deploy_intent_checklist(
            ticker="NVDA", decision_id=""
        )
    )
    assert payload["authority"] == "research_only"
    assert payload["ticker"] == "NVDA"
    assert payload["complete"] is False
