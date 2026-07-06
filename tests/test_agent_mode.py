"""Agent page — monitoring copilot, not deploy mirror."""

from __future__ import annotations

from pathlib import Path

from src.services.agent_mode import (
    agent_brief_label,
    agent_max_one_blocker_line,
    build_agent_audit_journal_on_load,
    build_agent_page_state,
    build_degraded_agent_status,
    enforce_agent_authority_guardrail,
    exclude_expired_brief_from_agent,
    resolve_agent_mode,
    suggest_safe_watch_rules,
)
from src.services.authority_engine import primary_operator_state
from src.services.system_truth import mission_blockers_from_truth, resolve_system_truth

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def _degraded_truth(*, brief_age_days: int = 1) -> dict:
    return resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 2, "setup_qualified": 3},
            "top_5": [{"ticker": "XLP", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
        brief_age_days=brief_age_days,
    )


def test_no_brief_fallback_when_brief_expired_26d():
    truth = _degraded_truth(brief_age_days=26)
    assert exclude_expired_brief_from_agent(truth) is True
    label = agent_brief_label(truth)
    assert "Expired 26d" in label
    assert "fallback" not in label.lower()
    assert suggest_safe_watch_rules([{"ticker": "KO", "action": "WATCH"}], truth) == []


def test_degraded_primary_is_monitor_only_not_selective():
    truth = _degraded_truth()
    state = build_agent_page_state(truth, [{"ticker": "XLP", "action": "WATCH"}], [])
    assert state["now"] == "MONITOR ONLY · Agent degraded"
    assert "SELECTIVE" not in state["now"]
    posture = primary_operator_state(truth)
    assert posture["primary"] == "MONITOR ONLY"
    assert posture["secondary"] == "SELECTIVE"


def test_max_one_blocker_line_default():
    truth = _degraded_truth()
    truth["agent_blocker_compact"] = True
    blockers = mission_blockers_from_truth(truth)
    assert len(blockers) == 1
    line = agent_max_one_blocker_line(truth)
    assert line == blockers[0]


def test_no_overnight_brief_when_degraded():
    truth = _degraded_truth(brief_age_days=26)
    note = build_degraded_agent_status(truth)
    assert note.startswith("Degraded Status Note:")
    assert "Overnight Brief" not in note
    assert "overnight brief" not in note.lower()


def test_no_brief_derived_rules_when_expired():
    truth = _degraded_truth(brief_age_days=26)
    rules = suggest_safe_watch_rules(
        [{"ticker": "KO", "action": "WATCH"}, {"ticker": "XLP", "action": "WATCH"}],
        truth,
    )
    assert rules == []
    state = build_agent_page_state(
        truth,
        [{"ticker": "KO", "action": "WATCH"}],
        [{"ticker": "XLP", "action": "WATCH"}],
    )
    assert state["suggested_rules"] == []
    assert "excluded" in state["suggested_rules_reason"].lower()


def test_suggested_rules_authority_effect_none():
    truth = _degraded_truth(brief_age_days=1)
    rules = suggest_safe_watch_rules(
        [{"ticker": "KO", "action": "WATCH"}, {"ticker": "XLP", "action": "WATCH"}],
        truth,
        max_rules=3,
    )
    assert rules
    assert all(r["authority_effect"] == "none" for r in rules)
    assert len(rules) <= 3


def test_no_deploy_size_handoff_actions():
    truth = _degraded_truth()
    state = build_agent_page_state(truth, [], [])
    assert state["agent_can_deploy"] is False
    assert state["agent_can_size"] is False
    assert state["agent_can_handoff"] is False
    assert "no sizing" in state["blocked"]
    assert "handoff" in state["blocked"]


def test_no_test_deploy_override_text_in_ui():
    html = INDEX_HTML.read_text(encoding="utf-8")
    helpers = CC_HELPERS.read_text(encoding="utf-8")
    assert "Test deploy override" not in html
    assert "Test deploy override" not in helpers
    assert "Test authority guardrail" in html
    assert "agentPageState" in helpers


def test_journal_logs_degraded():
    truth = _degraded_truth(brief_age_days=26)
    state = build_agent_page_state(truth, [], [])
    journal = build_agent_audit_journal_on_load(truth, state, rules_count=0)
    categories = {e["category"] for e in journal}
    assert "degraded" in categories
    assert "brief_expiry" in categories
    assert "no_rules" in categories
    assert "guardrail_test" in categories
    assert all(e["authority_effect"] == "none" for e in journal)


def test_authority_guardrail_passes():
    guardrail = enforce_agent_authority_guardrail()
    assert guardrail["pass"] is True
    assert guardrail["label"] == "Test authority guardrail"
    assert "deploy" in guardrail["message"].lower()


def test_resolve_agent_mode_degraded_when_deploy_blocked():
    truth = _degraded_truth()
    assert resolve_agent_mode(truth) == "degraded_monitor"


def test_no_safe_rules_reason_when_empty_candidates():
    truth = _degraded_truth(brief_age_days=1)
    state = build_agent_page_state(truth, [], [])
    assert state["suggested_rules"] == []
    assert "no safe rule candidates" in state["suggested_rules_reason"].lower()
