"""
tests/sprints/test_sprint107.py — Sprint 107: Fund Attribution Engine
======================================================================
Covers:
  - _attribution() contribution arithmetic (w × (r_pick - r_bm))
  - Sum of contributions ≈ excess return
  - Cash drag formula
  - Sector grouping for known and ETF tickers
  - Drawdown source = pick with worst max drawdown
  - Contributors sorted descending, detractors ascending
  - empty-picks guard returns attribution_available=False
  - _portfolio_returns() returns (series, dict) tuple
  - per_pick dict keyed by ticker
  - recent_wins / recent_losses split
  - all_contributions list length == number of picks
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _mk_ret_series(vals: List[float]) -> pd.Series:
    return pd.Series(vals, dtype=float)


def _call_attribution(
    picks: List[Dict[str, Any]],
    per_pick_rets: Dict[str, pd.Series],
    bm_rets: pd.Series,
) -> Dict[str, Any]:
    from src.services.fund_lab_service import FundLabService

    return FundLabService._attribution(picks, per_pick_rets, bm_rets)


# ── empty-picks guard ─────────────────────────────────────────────────────────


def test_attribution_empty_picks_returns_unavailable():
    result = _call_attribution([], {}, _mk_ret_series([0.01] * 10))
    assert result["attribution_available"] is False


def test_attribution_empty_per_pick_rets_returns_unavailable():
    picks = [{"ticker": "NVDA", "weight": 0.5}]
    result = _call_attribution(picks, {}, _mk_ret_series([0.01] * 10))
    assert result["attribution_available"] is False


# ── contribution arithmetic ───────────────────────────────────────────────────


def test_attribution_contribution_arithmetic():
    """contribution = weight × (pick_return - bm_return)"""
    # Single pick, known values
    bm_rets = _mk_ret_series([0.01, 0.01, 0.01])  # ~3.03% total
    pick_rets = _mk_ret_series([0.02, 0.02, 0.02])  # ~6.12% total
    picks = [{"ticker": "NVDA", "weight": 0.5, "score": 1.0, "momentum_12_1": 10.0}]
    per_pick = {"NVDA": pick_rets}
    result = _call_attribution(picks, per_pick, bm_rets)
    assert result["attribution_available"] is True
    contrib = result["all_contributions"][0]["contribution_pct"]
    bm_total = (1.01**3 - 1) * 100
    pick_total = (1.02**3 - 1) * 100
    expected = 0.5 * (pick_total - bm_total)
    assert abs(contrib - round(expected, 2)) < 0.05


def test_attribution_sum_of_contributions_approx_excess():
    """Sum of all contribution_pct ≈ portfolio excess return over benchmark."""
    bm_rets = _mk_ret_series([0.005] * 50)
    pick_a = _mk_ret_series([0.010] * 50)  # positive alpha
    pick_b = _mk_ret_series([0.003] * 50)  # negative alpha
    picks = [
        {"ticker": "A", "weight": 0.5, "score": 1.0, "momentum_12_1": 5.0},
        {"ticker": "B", "weight": 0.5, "score": 0.5, "momentum_12_1": 1.0},
    ]
    per_pick = {"A": pick_a, "B": pick_b}
    result = _call_attribution(picks, per_pick, bm_rets)
    total_contrib = sum(c["contribution_pct"] for c in result["all_contributions"])
    # Also compute directly
    bm_total = (1 + bm_rets).prod() - 1
    pick_a_total = (1 + pick_a).prod() - 1
    pick_b_total = (1 + pick_b).prod() - 1
    expected_excess = 0.5 * (pick_a_total - bm_total) + 0.5 * (pick_b_total - bm_total)
    assert abs(total_contrib - expected_excess * 100) < 0.1


# ── cash drag ─────────────────────────────────────────────────────────────────


def test_attribution_cash_drag_negative_when_bm_positive():
    """If benchmark positive and sum(weights)<1, cash drag should be ≤ 0."""
    bm_rets = _mk_ret_series([0.01] * 20)  # positive bm
    pick_rets = _mk_ret_series([0.01] * 20)
    picks = [
        {"ticker": "X", "weight": 0.7, "score": 1.0, "momentum_12_1": 5.0}
    ]  # 30% cash
    per_pick = {"X": pick_rets}
    result = _call_attribution(picks, per_pick, bm_rets)
    assert result["cash_drag_pct"] <= 0.0


def test_attribution_cash_weight_correct():
    bm_rets = _mk_ret_series([0.01] * 10)
    picks = [{"ticker": "X", "weight": 0.6, "score": 1.0, "momentum_12_1": 5.0}]
    per_pick = {"X": _mk_ret_series([0.01] * 10)}
    result = _call_attribution(picks, per_pick, bm_rets)
    assert abs(result["cash_weight_pct"] - 40.0) < 0.01


# ── contributor / detractor ordering ─────────────────────────────────────────


def test_contributors_sorted_descending():
    bm_rets = _mk_ret_series([0.0] * 20)
    picks = [
        {"ticker": "A", "weight": 0.33, "score": 1.0, "momentum_12_1": 5.0},
        {"ticker": "B", "weight": 0.33, "score": 0.9, "momentum_12_1": 3.0},
        {"ticker": "C", "weight": 0.34, "score": 0.8, "momentum_12_1": 1.0},
    ]
    per_pick = {
        "A": _mk_ret_series([0.03] * 20),
        "B": _mk_ret_series([0.02] * 20),
        "C": _mk_ret_series([0.01] * 20),
    }
    result = _call_attribution(picks, per_pick, bm_rets)
    contribs = result["contributors"]
    for i in range(len(contribs) - 1):
        assert contribs[i]["contribution_pct"] >= contribs[i + 1]["contribution_pct"]


def test_detractors_sorted_ascending():
    bm_rets = _mk_ret_series([0.02] * 20)  # high bm → picks underperform
    picks = [
        {"ticker": "X", "weight": 0.33, "score": 0.5, "momentum_12_1": -5.0},
        {"ticker": "Y", "weight": 0.33, "score": 0.4, "momentum_12_1": -3.0},
        {"ticker": "Z", "weight": 0.34, "score": 0.3, "momentum_12_1": -1.0},
    ]
    per_pick = {
        "X": _mk_ret_series([-0.01] * 20),
        "Y": _mk_ret_series([-0.005] * 20),
        "Z": _mk_ret_series([-0.002] * 20),
    }
    result = _call_attribution(picks, per_pick, bm_rets)
    detractors = result["detractors"]
    for i in range(len(detractors) - 1):
        assert (
            detractors[i]["contribution_pct"] <= detractors[i + 1]["contribution_pct"]
        )


# ── drawdown source ───────────────────────────────────────────────────────────


def test_drawdown_source_is_worst_pick():
    bm_rets = _mk_ret_series([0.005] * 30)
    picks = [
        {"ticker": "SAFE", "weight": 0.5, "score": 1.0, "momentum_12_1": 2.0},
        {"ticker": "RISKY", "weight": 0.5, "score": 0.5, "momentum_12_1": -5.0},
    ]
    per_pick = {
        "SAFE": _mk_ret_series([0.01] * 30),
        "RISKY": _mk_ret_series([0.05] * 5 + [-0.08] * 25),  # big drop
    }
    result = _call_attribution(picks, per_pick, bm_rets)
    assert result["drawdown_source"] == "RISKY"


# ── sector grouping ───────────────────────────────────────────────────────────


def test_sector_grouping_known_etfs():
    """ETF tickers like TLT and GLD should map to known sectors."""
    bm_rets = _mk_ret_series([0.005] * 20)
    picks = [
        {"ticker": "TLT", "weight": 0.5, "score": 1.0, "momentum_12_1": 2.0},
        {"ticker": "GLD", "weight": 0.5, "score": 0.9, "momentum_12_1": 1.0},
    ]
    per_pick = {
        "TLT": _mk_ret_series([0.01] * 20),
        "GLD": _mk_ret_series([0.008] * 20),
    }
    result = _call_attribution(picks, per_pick, bm_rets)
    sectors = result["sector_contribution"]
    assert len(sectors) >= 1
    # TLT should be in Bonds/Long sector
    assert "Bonds/Long" in sectors


def test_sector_contribution_values_sum_approx_total_contrib():
    bm_rets = _mk_ret_series([0.0] * 10)
    picks = [
        {"ticker": "TLT", "weight": 0.6, "score": 1.0, "momentum_12_1": 3.0},
        {"ticker": "BIL", "weight": 0.4, "score": 0.8, "momentum_12_1": 1.0},
    ]
    per_pick = {
        "TLT": _mk_ret_series([0.02] * 10),
        "BIL": _mk_ret_series([0.01] * 10),
    }
    result = _call_attribution(picks, per_pick, bm_rets)
    sector_sum = sum(result["sector_contribution"].values())
    total_contrib = sum(c["contribution_pct"] for c in result["all_contributions"])
    assert abs(sector_sum - total_contrib) < 0.01


# ── all_contributions length ──────────────────────────────────────────────────


def test_all_contributions_length_equals_picks():
    bm_rets = _mk_ret_series([0.005] * 15)
    picks = [
        {"ticker": "A", "weight": 0.25, "score": 1.0, "momentum_12_1": 5.0},
        {"ticker": "B", "weight": 0.25, "score": 0.9, "momentum_12_1": 3.0},
        {"ticker": "C", "weight": 0.25, "score": 0.8, "momentum_12_1": 1.0},
        {"ticker": "D", "weight": 0.25, "score": 0.7, "momentum_12_1": -1.0},
    ]
    per_pick = {t["ticker"]: _mk_ret_series([0.01] * 15) for t in picks}
    result = _call_attribution(picks, per_pick, bm_rets)
    assert len(result["all_contributions"]) == 4


# ── recent_wins / recent_losses split ────────────────────────────────────────


def test_recent_wins_losses_split():
    bm_rets = _mk_ret_series([0.005] * 30)
    picks = [
        {"ticker": "UP", "weight": 0.5, "score": 1.0, "momentum_12_1": 10.0},
        {"ticker": "DN", "weight": 0.5, "score": 0.5, "momentum_12_1": -5.0},
    ]
    per_pick = {
        "UP": _mk_ret_series([0.02] * 30),
        "DN": _mk_ret_series([-0.01] * 30),
    }
    result = _call_attribution(picks, per_pick, bm_rets)
    assert "UP" in result["recent_wins"]
    assert "DN" in result["recent_losses"]


# ── _portfolio_returns returns tuple ─────────────────────────────────────────


def test_portfolio_returns_returns_tuple():
    """_portfolio_returns() must return (pd.Series, dict) — Sprint 107 contract."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.services.fund_lab_service import FundLabService

    svc = FundLabService()
    picks = [{"ticker": "SPY", "weight": 1.0}]

    # Mock _history to return a simple series
    prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
    with patch.object(svc, "_history", return_value=prices):
        result = asyncio.get_event_loop().run_until_complete(
            svc._portfolio_returns(None, picks, "1y")
        )
    assert isinstance(result, tuple)
    assert len(result) == 2
    agg, per_pick = result
    assert isinstance(agg, pd.Series)
    assert isinstance(per_pick, dict)


def test_portfolio_returns_per_pick_keyed_by_ticker():
    import asyncio
    from unittest.mock import patch
    from src.services.fund_lab_service import FundLabService

    svc = FundLabService()
    picks = [
        {"ticker": "AAPL", "weight": 0.5},
        {"ticker": "MSFT", "weight": 0.5},
    ]
    prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
    with patch.object(svc, "_history", return_value=prices):
        agg, per_pick = asyncio.get_event_loop().run_until_complete(
            svc._portfolio_returns(None, picks, "1y")
        )
    assert "AAPL" in per_pick
    assert "MSFT" in per_pick
