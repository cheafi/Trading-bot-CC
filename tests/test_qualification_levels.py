"""Qualification levels — setup / trade / execution / deploy counts."""

from __future__ import annotations

from src.services.qualification_levels import (
    compute_qualification_levels,
    qualification_count_line,
)


def _row(ticker: str, action: str, score: float = 8.0, execution_ready: bool = False):
    return {
        "ticker": ticker,
        "action": action,
        "score": score,
        "execution_ready": execution_ready,
        "thesis_conf": 0.7,
        "timing_conf": 0.6,
    }


def test_deploy_qualified_zero_without_authority():
    levels = compute_qualification_levels(
        [_row("AAPL", "TRADE", execution_ready=True)],
        deploy_authority=False,
    )
    assert levels["execution_qualified"] == 1
    assert levels["deploy_qualified"] == 0
    assert "0 deploy-qualified" in levels["count_line"]


def test_deploy_qualified_requires_authority_and_execution():
    levels = compute_qualification_levels(
        [_row("AAPL", "TRADE", execution_ready=True)],
        deploy_authority=True,
    )
    assert levels["deploy_qualified"] == 1
    assert "1 deploy-qualified" in levels["count_line"]


def test_avoid_not_setup_qualified():
    levels = compute_qualification_levels(
        [_row("BAD", "AVOID", score=9.0)],
        deploy_authority=True,
    )
    assert levels["setup_qualified"] == 0


def test_invalid_score_not_setup_qualified():
    levels = compute_qualification_levels(
        [{"ticker": "X", "action": "WATCH", "score": -491.5}],
        deploy_authority=False,
    )
    assert levels["setup_qualified"] == 0
    row = levels["rows_sanitized"][0]
    assert row.get("calibration_state") == "invalid"


def test_qualification_count_line_helper():
    assert (
        qualification_count_line({"count_line": "2 setup-qualified · 0 deploy-qualified"})
        == "2 setup-qualified · 0 deploy-qualified"
    )
