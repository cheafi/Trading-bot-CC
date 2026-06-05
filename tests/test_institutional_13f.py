"""Institutional 13F unit tests."""

from src.services.institutional_13f import (
    CHANGE_ADDED,
    CHANGE_NEW_POSITION,
    build_institutional_context,
    classify_13f_change,
    crowdedness_hint,
)


def test_classify_new_position():
    assert classify_13f_change(shares_prev=0, shares_curr=1000, value_curr_usd=1e6) == (
        CHANGE_NEW_POSITION
    )


def test_classify_added():
    assert (
        classify_13f_change(shares_prev=100, shares_curr=120, value_curr_usd=1e6)
        == CHANGE_ADDED
    )


def test_crowdedness_high():
    assert crowdedness_hint(holder_count=20, top10_pct_float=0.3) == "high_crowded"


def test_build_institutional_mock():
    ctx = build_institutional_context("AAPL")
    assert ctx["ticker"] == "AAPL"
    assert ctx["monitor_trigger_type"] == "13f_sponsorship"
