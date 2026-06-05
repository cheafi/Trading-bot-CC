"""AI intelligence — deterministic explainer authority boundaries."""

from __future__ import annotations

from src.services.ai_intelligence import (
    REASON_DEPLOY_BLOCKED,
    REASON_MONITOR_UPGRADE_BLOCKED,
    attach_row_ai_hints,
    build_ai_intelligence_for_today,
    build_regime_stack_summary,
    collect_ai_reason_codes,
    detect_contradictions,
    detect_watchlist_recurrence,
    explain_reason_code,
    triage_catalyst,
)
from src.services.decision_truth_model import build_decision_authority
from src.services.index_regime import build_index_regime_summary
from src.services.signal_provenance import (
    SIGNAL_AI_INTELLIGENCE,
    may_authorize_deploy,
)


def test_ai_signal_never_authorizes_deploy():
    payload = build_ai_intelligence_for_today(scanner_degraded=True, degraded=True)
    assert payload["ai_explanatory_only"] is True
    assert payload["deploy_from_ai_alone"] is False
    assert payload["may_authorize_deploy"] is False
    assert may_authorize_deploy(SIGNAL_AI_INTELLIGENCE) is False


def test_reason_code_explainer_monitor_only():
    rc = explain_reason_code(REASON_MONITOR_UPGRADE_BLOCKED, context={"detail": "WAIT"})
    assert rc["deploy_from_ai_alone"] is False
    assert "WAIT" in rc["message"]


def test_contradiction_breadth_vs_index():
    hints = detect_contradictions(
        market_regime={"trend": "UPTREND", "breadth": 38},
        index_regime=build_index_regime_summary(
            vix=17, breadth=38, should_trade=True, tradeability="SELECTIVE"
        ),
    )
    assert hints
    assert hints[0]["deploy_from_ai_alone"] is False


def test_catalyst_triage_downgrade():
    tier = triage_catalyst({"impact": "risk_downgrade", "headline": "Guidance cut"})
    assert tier["tier"] == "downgrade"
    assert tier["downgrade_only"] is True


def test_watchlist_recurrence_near_miss():
    recurring = detect_watchlist_recurrence(
        near_miss=[{"ticker": "AAPL"}, {"ticker": "AAPL"}],
        monitor_triggers=[{"type": "near_miss", "label": "AAPL upgrade"}],
    )
    assert any(r["ticker"] == "AAPL" for r in recurring)


def test_regime_stack_summary_monitor_only():
    idx = build_index_regime_summary(vix=18, breadth=55, cross_asset={"alignment": "mixed"})
    stack = build_regime_stack_summary(idx)
    assert stack["monitor_only"] is True
    assert stack["may_authorize_deploy"] is False
    assert len(stack["blocks"]) >= 2


def test_ai_reason_codes_on_wait():
    auth = build_decision_authority(tradeability="WAIT", should_trade=False)
    codes = collect_ai_reason_codes(
        tradeability="WAIT",
        decision_authority=auth,
        scanner_degraded=False,
    )
    code_ids = {c["code"] for c in codes}
    assert REASON_MONITOR_UPGRADE_BLOCKED in code_ids
    assert REASON_DEPLOY_BLOCKED in code_ids


def test_row_hints_never_grant_deploy():
    rows = attach_row_ai_hints(
        [{"ticker": "NVDA", "raw_score": 8.0, "net_edge_score": 7.2, "action": "TRADE"}],
        market_regime={"trend": "UPTREND", "breadth": 35},
        event_risks=["VIX elevated"],
    )
    assert rows[0]["deploy_from_ai_alone"] is False
    assert rows[0].get("net_edge_display")
