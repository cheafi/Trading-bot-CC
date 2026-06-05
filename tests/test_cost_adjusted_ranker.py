"""Cost-adjusted ranker — WAIT cannot be overridden."""

from src.services.cost_adjusted_ranker import (
    LABEL_COST_TOO_HIGH,
    LABEL_MONITOR_ONLY,
    LABEL_NET_SURVIVES,
    enrich_opportunity_rows,
    rank_opportunity_rows,
    rank_single_row,
    resolve_cost_rank_label,
)
from src.services.index_regime import build_index_regime_summary


def test_wait_forces_monitor_only_label():
    assert (
        resolve_cost_rank_label(
            raw_score=9.0, net_score=8.0, tradeability="WAIT"
        )
        == LABEL_MONITOR_ONLY
    )


def test_net_survives_when_healthy():
    assert (
        resolve_cost_rank_label(
            raw_score=8.0, net_score=7.0, tradeability="SELECTIVE"
        )
        == LABEL_NET_SURVIVES
    )


def test_rank_row_never_overrides_wait():
    row = rank_single_row(
        {"ticker": "AAPL", "raw_score": 9.0, "action": "TRADE"},
        tradeability="WAIT",
    )
    assert row["may_override_wait"] is False
    assert row["cost_rank_blocked_on_wait"] is True
    assert row["cost_rank_label"] == LABEL_MONITOR_ONLY


def test_weak_net_cost_too_high():
    row = rank_single_row(
        {"ticker": "X", "raw_score": 6.0},
        tradeability="SELECTIVE",
    )
    assert row["cost_rank_label"] in (LABEL_COST_TOO_HIGH, LABEL_MONITOR_ONLY)


def test_sort_orders_net_survives_first():
    rows = rank_opportunity_rows(
        [
            {"ticker": "A", "raw_score": 5.0},
            {"ticker": "B", "raw_score": 8.5},
        ],
        tradeability="SELECTIVE",
    )
    assert rows[0]["ticker"] == "B"


def test_enrich_adds_regime_and_leadership_monitor_only():
    regime = build_index_regime_summary(tradeability="WAIT", should_trade=False)
    rows = enrich_opportunity_rows(
        [{"ticker": "NVDA", "raw_score": 8.0, "vol_ratio": 1.2}],
        index_regime=regime,
        tradeability="WAIT",
    )
    row = rows[0]
    assert row["regime_fit"] == "wait_filter"
    assert row["regime_intel_monitor_only"] is True
    assert row["may_authorize_deploy"] is False
    assert "index_leadership" in row
    assert row.get("net_edge_score") is not None
