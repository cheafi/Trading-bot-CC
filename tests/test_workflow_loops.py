"""Workflow loops Phase 1 — pre-decision checklist, research queue, decision cooling."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PARTIAL = ROOT / "src/api/templates/cc/partials/deploy_surfaces.html"
INDEX = ROOT / "src/api/templates/index.html"
CC_APP = ROOT / "src/api/static/cc-app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolated_workflow_stores(tmp_path, monkeypatch):
    """Point workflow JSON stores and cooling sessions at temp paths."""
    monkeypatch.setenv("DECISION_COOLING_SECONDS", "1")
    from src.services import decision_cooling, decision_readiness, research_queue

    dr_path = tmp_path / "decision_readiness.json"
    rq_path = tmp_path / "research_queue.json"
    monkeypatch.setattr(decision_readiness, "_DATA_PATH", dr_path)
    monkeypatch.setattr(research_queue, "_DATA_PATH", rq_path)
    decision_cooling.reset_sessions()
    yield
    decision_cooling.reset_sessions()


def test_decision_readiness_checklist_roundtrip():
    from src.api.routers import decision as decision_router
    from src.services.decision_readiness import checklist_complete, load_checklist

    empty = asyncio.run(decision_router.decision_readiness_get(ticker="AAPL"))
    assert empty["authority"] == "research_only"
    assert empty["ticker"] == "AAPL"
    assert empty["complete"] is False
    assert len(empty["fields"]) == 7

    saved = asyncio.run(
        decision_router.decision_readiness_save(
            {
                "ticker": "AAPL",
                "answers": {
                    "why_now": "Regime open",
                    "why_not_later": "Setup decaying",
                    "why_not_cash": "Marginal ROC beats cash",
                    "why_not_another_stock": "Best monitor qualified",
                    "what_changes_mind": "Kill condition hit",
                    "what_would_invalidate": "Thesis break",
                    "opportunity_cost": "Next best is cash",
                },
            }
        )
    )
    assert saved["ok"] is True
    assert saved["complete"] is True
    assert checklist_complete(load_checklist("AAPL")["answers"])


def test_decision_readiness_ui_strip():
    partial = _read(DEPLOY_PARTIAL)
    assert 'data-cc="decision-readiness-strip"' in partial
    js = _read(CC_APP)
    assert "fetchDecisionReadiness" in js
    assert "decisionReadinessLine" in js


def test_research_queue_add_remove_validated():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.research_queue_list())
    assert payload["authority"] == "research_only"
    assert "category_budgets" in payload

    added = asyncio.run(
        decision_router.research_queue_add(
            {"ticker": "MSFT", "budget_minutes": 45, "category": "Research"}
        )
    )
    assert added["ok"] is True
    tickers = [it["ticker"] for it in added["items"]]
    assert "MSFT" in tickers

    with pytest.raises(Exception):
        asyncio.run(
            decision_router.research_queue_add(
                {"ticker": "BAD!!", "budget_minutes": 30}
            )
        )

    removed = asyncio.run(
        decision_router.research_queue_remove({"ticker": "MSFT"})
    )
    assert removed["ok"] is True
    assert all(it["ticker"] != "MSFT" for it in removed["items"])


def test_research_queue_ops_panel():
    html = _read(INDEX)
    assert 'data-cc="research-queue-panel"' in html
    js = _read(CC_APP)
    assert "fetchResearchQueue" in js


def test_decision_cooling_state_machine():
    from src.api.routers import decision as decision_router
    from src.services.decision_cooling import STATE_CANCELLED, STATE_READY_TO_CONFIRM

    started = asyncio.run(
        decision_router.decision_cooling_start(
            {"ticker": "NVDA", "counterargument": "Crowded trade"}
        )
    )
    assert started["authority"] == "research_only"
    sid = started["session_id"]
    assert started["state"] == "COOLING"

    import time

    time.sleep(1.1)
    ready = asyncio.run(decision_router.decision_cooling_status(session_id=sid))
    assert ready["state"] == STATE_READY_TO_CONFIRM
    assert ready["ready_to_confirm"] is True

    started2 = asyncio.run(decision_router.decision_cooling_start({"ticker": "TSLA"}))
    cancelled = asyncio.run(
        decision_router.decision_cooling_cancel(
            {"session_id": started2["session_id"], "reason": "WAIT"}
        )
    )
    assert cancelled["state"] == STATE_CANCELLED
    assert cancelled["cancel_reason"] == "WAIT"


def test_decision_cooling_configurable_window(monkeypatch):
    monkeypatch.setenv("DECISION_COOLING_SECONDS", "2")
    from src.services.decision_cooling import cooling_seconds, reset_sessions, start_cooling

    reset_sessions()
    assert cooling_seconds() == 2
    session = start_cooling("AAPL")
    assert session["cooling_seconds"] == 2


def test_workflow_journal_hook_on_checklist_save(monkeypatch):
    captured: list = []
    from src.engines.decision_journal import DecisionJournal
    from src.services.decision_readiness import save_checklist

    original_record = DecisionJournal.record

    def capture_record(self, **kwargs):
        captured.append(kwargs)
        return original_record(self, **kwargs)

    monkeypatch.setattr(DecisionJournal, "record", capture_record)
    save_checklist(
        "GOOG",
        {
            "why_now": "x",
            "why_not_later": "x",
            "why_not_cash": "x",
            "why_not_another_stock": "x",
            "what_changes_mind": "x",
            "what_would_invalidate": "x",
            "opportunity_cost": "x",
        },
    )
    assert captured
    assert captured[0]["ticker"] == "GOOG"
    assert captured[0]["decision"] == "WORKFLOW"


def test_daily_ic_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.daily_ic_summary())
    assert payload["authority"] == "research_only"
    assert payload["may_authorize_deploy"] is False
    assert "mission" in payload
    assert "market" in payload
    assert "portfolio" in payload
    assert "capital" in payload
    assert "one_belief" in payload


def test_daily_ic_mission_control_strip():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="daily-ic-strip"' in partial
    assert 'data-cc="daily-ic-one-pager"' in partial
    assert "fetchDailyIc()" in js
    assert "dailyIcLine()" in js
    assert "dailyIcOnePagerLines()" in js
    assert "toggleDailyIcExpanded()" in js


def test_deploy_intent_journal_when_deploy_open():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="deploy-intent-journal-strip"' in partial
    assert "deployIntentJournalVisible()" in js
    assert "fetchDeployIntentJournal()" in js
    assert 'x-show="deployIntentJournalVisible()"' in partial


def test_workflow_stage_hint_playbook_portfolio():
    html = _read(INDEX)
    assert 'data-cc="workflow-stage-hint-playbook"' in html
    assert 'data-cc="workflow-stage-hint-portfolio"' in html
    helpers = _read(ROOT / "src/api/static/cc-helpers.js")
    assert '"signals" || tab === "playbook"' in helpers or "signals\" || tab === \"playbook\"" in helpers


def test_deploy_intent_checklist_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(
        decision_router.decision_journal_deploy_intent_checklist(
            ticker="AAPL", decision_id=""
        )
    )
    assert payload["authority"] == "research_only"
    assert payload["may_authorize_deploy"] is False
    assert "missing_fields" in payload
    assert "readiness_path" in payload


def test_pm_board_ssot_strip():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="pm-board-ssot-strip"' in partial
    assert "pmDecisionTickerLine()" in js
    assert "buildPmStripBoardLine" in _read(ROOT / "src/api/static/cc-helpers.js")


def test_workflow_stage_pill():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert "workflowStage().label" in partial
    assert "workflowStage()" in js


def test_pre_decision_gate_panel():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="pre-decision-gate-panel"' in partial
    assert "preDecisionGateVisible()" in js
    assert "fetchPreDecisionGate()" in js
    assert "togglePreDecisionAck()" in js
    assert "postJournalStubIfNeeded()" in js


def test_attention_budget_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.attention_budget_summary())
    assert payload["authority"] == "research_only"
    assert payload["default_budgets"]["research"] == 60
    assert payload["default_budgets"]["portfolio"] == 30
    assert payload["default_budgets"]["market"] == 15


def test_attention_budget_ui_strip():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    html = _read(INDEX)
    assert 'data-cc="attention-budget-strip"' in partial
    assert 'data-cc="attention-budget-panel"' in html
    assert "fetchAttentionBudget()" in js
    assert "attentionBudgetLine()" in js


def test_knowledge_lessons_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.knowledge_lessons(ticker="AAPL"))
    assert payload["authority"] == "research_only"
    assert payload["ticker"] == "AAPL"
    assert "lessons" in payload


def test_pre_decision_gate_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.pre_decision_gate(ticker="NVDA"))
    assert payload["authority"] == "research_only"
    assert payload["may_authorize_deploy"] is False
    assert "checklist" in payload
    assert "red_team" in payload
    assert "outside_view" in payload
    assert "journal" in payload


def test_prior_lessons_strip():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="prior-lessons-strip"' in partial
    assert "fetchPriorLessons" in js
    assert "priorLessonsLine()" in js


def test_belief_deploy_strip():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="belief-deploy-strip"' in partial
    assert "beliefDeployStripVisible()" in js
    assert "fetchBeliefDeployFlags()" in js
