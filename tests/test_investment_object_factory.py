"""Tests for InvestmentObject factory (CC X Sprint 118+)."""

from __future__ import annotations

from src.services.investment_object_factory import (
    attach_investment_objects,
    investment_object_from_row,
    make_attribution_root_ref,
    make_decision_id,
)


def test_investment_object_from_row_research_only():
    row = {
        "ticker": "AAPL",
        "score": 7.2,
        "why_now": "Breakout above 50 SMA",
        "source": "scanner",
        "as_of": "2026-08-25T08:00:00Z",
        "mode": "LIVE",
    }
    io = investment_object_from_row(row, tradeability="WAIT")
    assert io.ticker == "AAPL"
    assert io.authority == "research_only"
    assert io.may_authorize_deploy is False
    assert io.provenance.source == "scanner"
    assert io.provenance.mode == "LIVE"


def test_attach_investment_objects_adds_attribution_refs():
    rows = [{"ticker": "MSFT", "rank": 1, "score": 6.8}]
    out = attach_investment_objects(rows, tradeability="SELECTIVE")
    assert out[0]["decision_id"].startswith("dec-MSFT-")
    assert out[0]["attribution_root_ref"].startswith("attr-root-dec-MSFT-")
    assert out[0]["investment_object"]["ticker"] == "MSFT"


def test_decision_id_stable_for_same_inputs():
    row = {"ticker": "NVDA", "rank": 2, "as_of": "2026-08-25T08:00:00Z"}
    d1 = make_decision_id("NVDA", row=row)
    d2 = make_decision_id("NVDA", row=row)
    assert d1 == d2
    assert make_attribution_root_ref(d1) == f"attr-root-{d1}"
