"""Opportunity intelligence — authority boundaries and provenance."""

from __future__ import annotations

from src.services.decision_truth_model import (
    apply_authority_to_row,
    build_decision_authority,
)
from src.services.event_noise_filter import build_event_risk_context
from src.services.insider_tracker import build_insider_context
from src.services.institutional_13f import build_institutional_context
from src.services.signal_provenance import (
    SIGNAL_EVENT_NARRATIVE,
    SIGNAL_INSIDER_FORM4,
    SIGNAL_INSTITUTIONAL_13F,
    SIGNAL_STRATEGY_CURVE,
    assert_no_deploy_from_signals,
    may_authorize_deploy,
)
from src.services.strategy_curve_health import build_strategy_curve_context
from src.services.surface_authority import AUTHORITY_DEPLOY, AUTHORITY_RESEARCH


def test_no_signal_type_may_authorize_deploy():
    for st in (
        SIGNAL_INSIDER_FORM4,
        SIGNAL_INSTITUTIONAL_13F,
        SIGNAL_EVENT_NARRATIVE,
        SIGNAL_STRATEGY_CURVE,
    ):
        assert may_authorize_deploy(st) is False


def test_insider_payload_research_only():
    payload = build_insider_context("AAPL")
    assert payload["data_mode"] == "research_only"
    assert payload["provenance"]["deploy_from_signal_alone"] is False
    assert payload["authority_ceiling"] == AUTHORITY_RESEARCH


def test_institutional_payload_not_deploy():
    payload = build_institutional_context("MSFT")
    assert payload["provenance"]["may_authorize_deploy"] is False
    assert "lag" in payload["lag_copy"].lower()


def test_events_downgrade_only_flag():
    payload = build_event_risk_context("NVDA")
    assert payload["downgrade_only"] is True
    assert all(not e.get("may_upgrade_trade") for e in payload["events"])


def test_strategy_curve_no_deploy_alone():
    payload = build_strategy_curve_context("QQQ")
    curve = payload["strategies"][0]
    assert curve["deploy_from_curve_alone"] is False


def test_trade_not_upgraded_from_insider_alone():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=False,
        fallback_brief=False,
    )
    row = apply_authority_to_row(
        {"action": "TRADE", "raw_action": "TRADE", "thesis_conf": 0.9},
        authority,
    )
    assert row["action"] != "TRADE"
    insider = build_insider_context("AAPL")
    assert insider["authority_ceiling"] != AUTHORITY_DEPLOY
    assert_no_deploy_from_signals(
        [
            {"signal_type": insider["signal_type"]},
            {"signal_type": build_institutional_context("AAPL")["signal_type"]},
        ]
    )
