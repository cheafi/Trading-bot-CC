"""Unit tests for strategy fitness matrix + DSR."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.engines.strategy_fitness import (
    build_fitness_matrix,
    compute_deflated_sharpe,
    dsr_passed,
    effective_profit_factor,
    evaluate_eligibility,
    load_fitness_matrix,
    persist_fitness_matrix,
)


def test_dsr_increases_with_better_sharpe():
    # Moderate Sharpe avoids CDF saturation at 1.0 for both arms.
    low = compute_deflated_sharpe(0.1, num_trials=10, num_observations=80)
    high = compute_deflated_sharpe(0.2, num_trials=10, num_observations=80)
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0
    assert high > low


def test_dsr_penalizes_many_trials():
    """More trials → higher selection-bias bar → lower DSR for same Sharpe."""
    few = compute_deflated_sharpe(0.15, num_trials=2, num_observations=100)
    many = compute_deflated_sharpe(0.15, num_trials=50, num_observations=100)
    assert few >= many
    assert many < few


def test_dsr_zero_on_insufficient_observations():
    assert compute_deflated_sharpe(2.0, num_trials=5, num_observations=1) == 0.0


def test_eligibility_all_gates_pass():
    ok, reasons = evaluate_eligibility(
        oos_sharpe=1.1,
        profit_factor=1.5,
        trade_count=80,
        oos_is_ratio=0.75,
        after_slippage=False,
        dsr_score=0.99,
    )
    assert ok is True
    assert reasons == []


def test_eligibility_fails_low_dsr():
    ok, reasons = evaluate_eligibility(
        oos_sharpe=1.1,
        profit_factor=1.5,
        trade_count=80,
        oos_is_ratio=0.75,
        dsr_score=0.5,
    )
    assert ok is False
    assert any("dsr<" in r for r in reasons)


@pytest.mark.parametrize(
    ("dsr", "expected"),
    [
        (0.94, False),
        (0.95, True),
        (0.99, True),
    ],
)
def test_dsr_passed_boundary(dsr: float, expected: bool):
    assert dsr_passed(dsr) is expected


def test_effective_profit_factor_zero_gross_loss():
    assert effective_profit_factor(1.2, gross_loss=0.0) == float("inf")


def test_zero_is_sharpe_oos_is_ratio():
    wf = {
        "ticker": "NVDA",
        "walk_forward": {
            "SWING": {
                "avg_oos_sharpe": 1.0,
                "profit_factor": 1.5,
                "max_dd": 0.1,
                "oos_trades": 80,
            },
        },
        "strategy_results": {"SWING": {"sharpe": 0.0}},
    }
    records = build_fitness_matrix(wf, num_trials=2)
    assert records[0].oos_is_ratio == 1.0


def test_eligibility_fails_low_trades():
    ok, reasons = evaluate_eligibility(
        oos_sharpe=1.1,
        profit_factor=1.5,
        trade_count=40,
        oos_is_ratio=0.75,
    )
    assert ok is False
    assert any("oos_trades" in r for r in reasons)


def test_eligibility_fails_low_sharpe():
    ok, reasons = evaluate_eligibility(
        oos_sharpe=0.5,
        profit_factor=1.5,
        trade_count=80,
        oos_is_ratio=0.75,
    )
    assert ok is False
    assert any("oos_sharpe" in r for r in reasons)


def test_eligibility_fails_oos_is_ratio():
    ok, reasons = evaluate_eligibility(
        oos_sharpe=1.1,
        profit_factor=1.5,
        trade_count=80,
        oos_is_ratio=0.4,
    )
    assert ok is False
    assert any("oos_is_ratio" in r for r in reasons)


def test_eligibility_slippage_discount_on_pf():
    ok, reasons = evaluate_eligibility(
        oos_sharpe=1.1,
        profit_factor=1.35,
        trade_count=80,
        oos_is_ratio=0.75,
        after_slippage=True,
    )
    assert ok is False
    assert any("profit_factor" in r for r in reasons)


def test_build_fitness_matrix_from_walk_forward_dict():
    wf = {
        "ticker": "AAPL",
        "walk_forward": {
            "SWING": {
                "avg_oos_sharpe": 1.2,
                "profit_factor": 1.6,
                "max_dd": 0.12,
                "oos_trades": 72,
            },
        },
        "strategy_results": {
            "SWING": {"sharpe": 1.5, "pf": 1.8},
        },
    }
    records = build_fitness_matrix(wf, num_trials=5)
    assert len(records) == 1
    rec = records[0]
    assert rec.ticker == "AAPL"
    assert rec.strategy == "SWING"
    assert rec.dsr_passed is True
    assert rec.eligible is True
    assert rec.authority == "research_only"
    assert rec.may_authorize_deploy is False
    assert rec.oos_is_ratio == pytest.approx(0.8, rel=1e-3)
    assert 0.0 < rec.dsr_score <= 1.0


def test_persist_and_load_matrix(tmp_path: Path):
    wf = {
        "ticker": "MSFT",
        "walk_forward": {
            "BREAKOUT": {
                "avg_oos_sharpe": 0.9,
                "profit_factor": 1.4,
                "max_dd": 0.15,
                "oos_trades": 65,
            },
        },
        "strategy_results": {"BREAKOUT": {"sharpe": 1.2}},
    }
    records = build_fitness_matrix(wf)
    path = tmp_path / "strategy_fitness_matrix.json"
    persist_fitness_matrix(records, path=path)
    assert path.is_file()

    loaded = load_fitness_matrix(path=path)
    assert loaded["authority"] == "research_only"
    assert loaded["may_authorize_deploy"] is False
    assert loaded["record_count"] == 1
    assert loaded["records"][0]["ticker"] == "MSFT"
