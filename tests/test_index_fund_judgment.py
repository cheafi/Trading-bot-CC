"""Tests for 《指数基金投资指南》index fund judgment module."""

from __future__ import annotations

from src.services.index_fund_judgment import (
    classify_index_fund,
    enrich_funds_console_index_layer,
    evaluate_allocation_decision,
    evaluate_investment_mode,
    evaluate_valuation_zone,
    index_fund_alignment_for_core_satellite,
    index_fund_posture_strip_for_today,
    is_index_etf_symbol,
    tags_for_playbook_row,
)


def test_broad_index_classification_spy():
    cls = classify_index_fund({"ticker": "SPY", "name": "S&P 500"})
    assert cls["classification"] == "broad"
    assert cls["is_index"] is True


def test_narrow_sector_classification():
    cls = classify_index_fund(
        {"ticker": "SOXX", "name": "Semiconductor sector ETF", "sector_tags": ["semiconductor"]}
    )
    assert cls["classification"] == "narrow"
    assert cls["scope"] == "narrow"


def test_not_index_stock():
    cls = classify_index_fund({"ticker": "AAPL", "name": "Apple Inc"})
    assert cls["is_index"] is False
    assert cls["classification"] == "not_index"


def test_valuation_cheap_zone():
    val = evaluate_valuation_zone({"ticker": "SPY", "pe_percentile": 22})
    assert val["valuation_zone"] == "cheap"
    assert val["proxy"] is True


def test_valuation_expensive_zone():
    val = evaluate_valuation_zone({"ticker": "SPY", "pe_percentile": 82})
    assert val["valuation_zone"] == "expensive"


def test_investment_mode_continue_dca_fair():
    mode = evaluate_investment_mode({"ticker": "VTI", "pe_percentile": 50})
    assert mode["action"] == "continue_dca"


def test_investment_mode_pause_expensive():
    mode = evaluate_investment_mode({"ticker": "SPY", "pe_percentile": 85})
    assert mode["action"] == "pause_dca"


def test_allocation_decision_bundle():
    j = evaluate_allocation_decision({"ticker": "VOO", "pe_percentile": 25})
    assert j["mode"] == "index_fund_guide"
    assert j["classification"]["is_index"] is True
    assert j["investment_mode"]["action"] in ("continue_dca", "hold_core")


def test_playbook_tags_only_for_index():
    assert tags_for_playbook_row({"ticker": "AAPL"}) == {}
    tags = tags_for_playbook_row({"ticker": "SPY", "pe_percentile": 40})
    assert tags["index_fund_scope"] == "broad"
    assert tags["index_fund_valuation_zone"] == "fair"
    assert "index_fund_action" in tags


def test_is_index_etf_symbol():
    assert is_index_etf_symbol("SPY") is True
    assert is_index_etf_symbol("MSFT") is False
    assert is_index_etf_symbol("XYZ", {"asset_class": "etf"}) is True


def test_posture_strip_no_urgency():
    strip = index_fund_posture_strip_for_today(
        {"tradeability": "WAIT"},
        {"honest_tradeability": "WAIT"},
        benchmark="SPY",
        market_pe_percentile=55,
    )
    assert strip["mode"] == "index_fund_guide"
    assert strip["urgent_action_required"] is False
    assert strip["core_priority"] is True
    assert "SPY" in strip["valuation_summary"]


def test_enrich_funds_console_index_layer():
    console = enrich_funds_console_index_layer(
        {"cards": [{"id": "X", "holdings": [{"ticker": "SPY"}]}], "tradeability": "WAIT"},
        benchmark="SPY",
        market_pe_percentile=60,
    )
    assert "index_fund_posture" in console
    assert console["cards"][0]["index_fund_layer"]["benchmark"] == "SPY"


def test_core_satellite_alignment():
    align = index_fund_alignment_for_core_satellite(
        [{"ticker": "SPY", "sleeve_role": "core_passive", "market_value": 10000}]
    )
    assert align["benchmark"] == "SPY"
    assert "SPY" in align["core_index_tickers"]
    assert align["proxy"] is True
