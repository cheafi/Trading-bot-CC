"""Tests for the per-order execution TCA ledger (ops_probe / research-only)."""

from __future__ import annotations

from src.services.execution_tca import (
    TIME_BUCKET_CLOSE,
    TIME_BUCKET_MIDDAY,
    TIME_BUCKET_OPEN,
    TIME_BUCKET_UNKNOWN,
    ExecutionTcaLedger,
    aggregate_tca,
    build_execution_tca_context,
    compute_order_tca,
    execution_drag_overlay,
    execution_quality_trend,
    time_bucket,
)

_BUY = {
    "ticker": "aapl", "side": "BUY", "algo": "vwap", "venue": "IBKR", "order_type": "LMT",
    "session_minute": 10, "order_qty": 1000, "filled_qty": 1000,
    "arrival_price": 100.0, "avg_fill_price": 100.10, "interval_vwap": 100.05,
    "midpoint_price": 100.0, "ref_end_price": 101.0,
    "ts_signal": 0, "ts_send": 100, "ts_first_fill": 300, "ts_final_fill": 800,
}


def test_time_bucket():
    assert time_bucket(5) == TIME_BUCKET_OPEN
    assert time_bucket(120) == TIME_BUCKET_MIDDAY
    assert time_bucket(400) == TIME_BUCKET_CLOSE
    assert time_bucket(None) == TIME_BUCKET_UNKNOWN


def test_buy_arrival_slippage_positive_is_adverse():
    t = compute_order_tca(_BUY)
    # paid 100.10 vs arrival 100.00 -> +10 bps adverse
    assert t["slippage_vs_arrival_bps"] == 10.0
    assert t["slippage_vs_vwap_bps"] == 5.0
    assert t["fill_ratio"] == 1.0
    assert t["partial_fill"] is False
    assert t["degraded"] is False


def test_sell_slippage_sign_convention():
    sell = {**_BUY, "side": "SELL", "avg_fill_price": 99.90}
    t = compute_order_tca(sell)
    # sold at 99.90 vs arrival 100.00 -> adverse (received less) -> positive bps
    assert t["slippage_vs_arrival_bps"] == 10.0


def test_implementation_shortfall_filled_and_complete():
    t = compute_order_tca(_BUY)
    # fully filled buy: IS ~= exec cost (10 bps); opp cost weight 0
    assert t["implementation_shortfall_bps"] == 10.0
    assert t["is_complete"] is True


def test_partial_fill_blends_opportunity_cost():
    partial = {**_BUY, "filled_qty": 500, "ref_end_price": 102.0}
    t = compute_order_tca(partial)
    assert t["partial_fill"] is True
    assert t["fill_ratio"] == 0.5
    # exec cost 10bps*0.5 + opp cost 200bps*0.5 = 105 bps
    assert t["implementation_shortfall_bps"] == 105.0


def test_effective_spread_proxy():
    t = compute_order_tca(_BUY)
    # 2*|100.10-100.00|/100 = 20 bps
    assert t["effective_spread_bps"] == 20.0


def test_latency_chain():
    t = compute_order_tca(_BUY)
    assert t["latency"]["time_to_send_ms"] == 100
    assert t["latency"]["time_to_first_fill_ms"] == 200
    assert t["latency"]["time_to_complete_ms"] == 700


def test_degraded_when_no_fill_price():
    t = compute_order_tca({"ticker": "X", "side": "BUY", "order_qty": 100, "filled_qty": 0,
                           "arrival_price": 50.0, "avg_fill_price": None})
    assert t["degraded"] is True
    assert t["slippage_vs_arrival_bps"] is None
    assert t["implementation_shortfall_bps"] is None
    assert t["handoff_ok"] is False  # no fill -> handoff failed by default


def test_aggregate_by_algo_and_handoff_rate():
    rows = [compute_order_tca(_BUY),
            compute_order_tca({**_BUY, "algo": "twap", "handoff_ok": False, "filled_qty": 0,
                               "avg_fill_price": None})]
    agg = aggregate_tca(rows, by="algo")
    by = {g["algo"]: g for g in agg["groups"]}
    assert by["vwap"]["handoff_success_rate"] == 1.0
    assert by["twap"]["handoff_success_rate"] == 0.0


def test_quality_trend_detects_deterioration():
    early = [{**_BUY} for _ in range(2)]
    late = [{**_BUY, "avg_fill_price": 100.5} for _ in range(2)]  # 50 bps adverse
    rows = [compute_order_tca(o) for o in early + late]
    trend = execution_quality_trend(rows)
    assert trend["trend"] == "deteriorating"


def test_execution_drag_overlay_labels():
    rows = [compute_order_tca({**_BUY, "avg_fill_price": 100.30}) for _ in range(3)]  # 30bps
    overlay = execution_drag_overlay(rows)
    assert overlay["drag_bps"] == 30.0
    assert "heavy" in overlay["label"]
    assert overlay["downgrade_only"] is True


def test_ledger_persists(tmp_path):
    led = ExecutionTcaLedger(path=str(tmp_path / "tca.jsonl"))
    led.record_order(_BUY)
    led2 = ExecutionTcaLedger(path=str(tmp_path / "tca.jsonl"))
    assert len(led2.orders()) == 1


# -- authority --------------------------------------------------------------
def test_context_does_not_authorize_execution():
    from src.services.signal_provenance import assert_no_deploy_from_signals

    ctx = build_execution_tca_context([_BUY], ibkr_connected=False)
    assert ctx["data_mode"] == "research_only"  # not connected -> research only
    assert ctx["degraded"] is True
    assert ctx["authorizes_execution"] is False
    assert ctx["provenance"]["deploy_from_signal_alone"] is False
    assert_no_deploy_from_signals([ctx])


def test_context_ops_probe_when_connected():
    ctx = build_execution_tca_context([_BUY], ibkr_connected=True)
    assert ctx["data_mode"] == "ops_probe"
    assert ctx["authorizes_execution"] is False
