"""Provenance CI contract tests (Sprint 116)."""

from __future__ import annotations

import pytest

from src.services.provenance_contract import (
    assert_rows_have_provenance,
    enrich_row_provenance,
    validate_row_provenance,
)


def test_validate_row_provenance_ok():
    ok, missing = validate_row_provenance(
        {"ticker": "AAPL", "source": "yfinance", "as_of": "2026-08-25T08:00:00Z", "mode": "LIVE"}
    )
    assert ok is True
    assert missing == []


def test_validate_row_provenance_missing():
    ok, missing = validate_row_provenance({"ticker": "AAPL"})
    assert ok is False
    assert "source" in missing
    assert "as_of" in missing


def test_assert_rows_have_provenance_passes():
    rows = [
        enrich_row_provenance(
            {"ticker": "AAPL", "score": 7.0},
            source="scanner",
            as_of="2026-08-25T08:00:00Z",
            mode="LIVE",
        )
    ]
    assert_rows_have_provenance(rows)


def test_assert_rows_have_provenance_fails_ci():
    with pytest.raises(AssertionError, match="Provenance contract violation"):
        assert_rows_have_provenance([{"ticker": "AAPL", "score": 7.0}])
