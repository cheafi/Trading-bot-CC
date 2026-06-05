"""Insider tracker unit tests."""

from src.services.insider_tracker import (
    QUALITY_NOTABLE_ACCUMULATION,
    QUALITY_NOTABLE_DISTRIBUTION,
    QUALITY_NOISE,
    build_insider_context,
    score_form4_significance,
)


def test_large_purchase_notable_accumulation():
    sig = score_form4_significance(
        transaction_type="P",
        shares=50000,
        value_usd=2_000_000,
        role="ceo",
        filing_count_90d=4,
    )
    assert sig["quality_label"] == QUALITY_NOTABLE_ACCUMULATION


def test_small_sale_low_significance():
    sig = score_form4_significance(
        transaction_type="S",
        shares=100,
        value_usd=5000,
        role="director",
        filing_count_90d=0,
    )
    assert sig["quality_label"] in (
        QUALITY_NOISE,
        QUALITY_NOTABLE_DISTRIBUTION,
        "supportive_only",
    )


def test_build_insider_mock_honest():
    ctx = build_insider_context("TEST")
    assert ctx["data_tier"] == "mock"
    assert ctx["ticker"] == "TEST"
    assert len(ctx["filings"]) >= 1
