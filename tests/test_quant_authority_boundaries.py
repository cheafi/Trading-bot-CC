"""Quant / algo authority — no deploy from curve, cost, allocator, validity."""

from __future__ import annotations

from src.services.cost_adjusted_ranker import build_cost_rank_context, rank_single_row
from src.services.signal_provenance import (
    SIGNAL_COST_RANK,
    SIGNAL_INDEX_REGIME,
    SIGNAL_STRATEGY_ALLOCATION,
    SIGNAL_STRATEGY_CURVE,
    SIGNAL_STRATEGY_VALIDITY,
    assert_no_deploy_from_signals,
    may_authorize_deploy,
    quant_authority_can,
    quant_authority_cannot,
)
from src.services.index_regime import build_index_regime_summary
from src.services.strategy_allocator import build_allocator_context
from src.services.strategy_curve_health import build_strategy_curve_context
from src.services.strategy_validity import build_strategy_validity_context
from src.services.surface_authority import AUTHORITY_DEPLOY


def test_quant_signal_types_never_may_deploy():
    for st in (
        SIGNAL_STRATEGY_CURVE,
        SIGNAL_COST_RANK,
        SIGNAL_STRATEGY_ALLOCATION,
        SIGNAL_STRATEGY_VALIDITY,
        SIGNAL_INDEX_REGIME,
    ):
        assert may_authorize_deploy(st) is False
        assert quant_authority_can(st, "TRADE") is False
        assert "authorize_deploy" in quant_authority_cannot(st)


def test_curve_no_deploy_alone():
    payload = build_strategy_curve_context("SPY")
    assert payload["strategies"][0]["deploy_from_curve_alone"] is False
    assert payload["authority_ceiling"] != AUTHORITY_DEPLOY


def test_cost_rank_wait_blocked():
    payload = build_cost_rank_context("AAPL", tradeability="WAIT")
    assert payload["may_override_wait"] is False
    row = rank_single_row({"action": "TRADE", "raw_score": 9}, tradeability="WAIT")
    assert row["action"] != "TRADE"


def test_index_regime_outputs_never_set_deploy_true():
    summary = build_index_regime_summary(tradeability="TRADE", should_trade=True)
    assert summary.get("may_authorize_deploy") is False
    assert summary.get("may_override_wait") is False
    for block_key in ("vol_regime", "breadth_regime", "factor_regime"):
        block = summary.get(block_key) or {}
        assert block.get("monitor_only") is True


def test_allocator_and_validity_envelopes():
    alloc = build_allocator_context()
    valid = build_strategy_validity_context()
    assert alloc["deploy_from_allocator_alone"] is False
    assert valid["validity"]["deploy_from_validity_alone"] is False
    assert_no_deploy_from_signals(
        [
            {"signal_type": alloc["signal_type"]},
            {"signal_type": valid["signal_type"]},
            {"signal_type": build_cost_rank_context("X")["signal_type"]},
        ]
    )
