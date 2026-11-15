"""Walk-forward evidence engine: fills, costs, look-ahead, purging, grading."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import walk_forward as wf
from src.engines.walk_forward import (
    CostModel,
    Rule,
    simulate_trades,
    walk_forward_report,
)

P = {"stop_atr": 1.0, "target_r": 2.0, "max_hold": 5}


def _flat(n=40, px=100.0, rng=1.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": px,
            "High": px + rng / 2,
            "Low": px - rng / 2,
            "Close": px,
            "Volume": 1e6,
        },
        index=idx,
    )


def _signal_at(df, i):
    s = pd.Series(False, index=df.index)
    s.iloc[i] = True
    return s


def test_entry_is_next_open_and_target_hit():
    df = _flat()  # ATR14 = 1.0 → stop 99, target 102
    df.iloc[21, df.columns.get_loc("Open")] = 100.0
    df.iloc[22, df.columns.get_loc("High")] = 102.5
    trades = simulate_trades(df, _signal_at(df, 20), P)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_date == df.index[21] and t.entry_raw == 100.0
    assert t.exit_reason == "target" and t.exit_raw == pytest.approx(102.0)
    assert t.r_multiple(0.0) == pytest.approx(2.0)


def test_same_bar_stop_and_target_scores_stop():
    df = _flat()
    df.iloc[22, df.columns.get_loc("High")] = 103.0
    df.iloc[22, df.columns.get_loc("Low")] = 98.0
    t = simulate_trades(df, _signal_at(df, 20), P)[0]
    assert t.exit_reason == "stop" and t.r_multiple(0.0) == pytest.approx(-1.0)


def test_gap_through_stop_fills_at_open():
    df = _flat()
    for col, v in (("Open", 97.0), ("High", 97.5), ("Low", 96.5), ("Close", 97.0)):
        df.iloc[23, df.columns.get_loc(col)] = v
    t = simulate_trades(df, _signal_at(df, 20), P)[0]
    assert t.exit_reason == "stop_gap" and t.exit_raw == 97.0
    assert t.r_multiple(0.0) == pytest.approx(-3.0)


def test_time_stop_and_open_trade_at_end_excluded():
    df = _flat()
    t = simulate_trades(df, _signal_at(df, 20), P)[0]
    assert t.exit_reason == "time" and t.exit_date == df.index[25]
    assert simulate_trades(df, _signal_at(df, len(df) - 3), P) == []


def test_costs_charged_on_both_sides():
    df = _flat()
    df.iloc[22, df.columns.get_loc("High")] = 102.5
    t = simulate_trades(df, _signal_at(df, 20), P)[0]
    c = CostModel(commission_bps=1, slippage_bps=5, spread_bps=4).per_side
    expected = (102.0 * (1 - c) - 100.0 * (1 + c)) / 1.0
    assert t.r_multiple(c) == pytest.approx(expected)
    assert t.r_multiple(c) < t.r_multiple(0.0)


def _random_walk(n=900, seed=0, drift=0.0005):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n)))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol = rng.integers(5e5, 3e6, n).astype(float)
    idx = pd.date_range("2021-01-04", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_rule_signal_is_causal():
    df = _random_walk()
    spy = _random_walk(seed=9)["Close"]
    rule = wf.RULES["brief_rs_leader_v1"]
    p = rule.param_grid[0]
    full = rule.signal(df, spy, p)
    k = 600
    mutated = df.copy()
    mutated.iloc[k:] *= 3.0
    assert full.iloc[:k].equals(rule.signal(mutated, spy, p).iloc[:k])


def test_closed_trades_unchanged_by_future_bars():
    df = _random_walk()
    sig = pd.Series(np.arange(len(df)) % 7 == 0, index=df.index)
    p = {"stop_atr": 1.0, "target_r": 2.0, "max_hold": 20}
    k = 600
    before = [t for t in simulate_trades(df, sig, p) if t.exit_date < df.index[k]]
    mutated = df.copy()
    mutated.iloc[k:] *= 0.5
    after = [t for t in simulate_trades(mutated, sig, p) if t.exit_date < df.index[k]]
    assert before == after and len(before) > 10


def _every_n_rule(n_bars: int, grid=None) -> Rule:
    def sig(df, bench, p):
        return pd.Series(np.arange(len(df)) % n_bars == 0, index=df.index)

    return Rule(
        strategy_id="test_rule",
        description="test",
        signal=sig,
        param_grid=grid or ({"stop_atr": 1.0, "target_r": 2.0, "max_hold": 10},),
    )


def test_only_test_window_trades_are_graded():
    data = {"AAA": _random_walk(seed=1)}
    rep = walk_forward_report(data, _every_n_rule(5))
    first_test = pd.Timestamp(rep["folds"][0]["test_start"])
    assert rep["trades"] == sum(f["oos"]["trades"] for f in rep["folds"])
    assert rep["evidence"]["sample_size"] == rep["trades"]
    assert rep["evidence"]["out_of_sample_count"] == rep["trades"]
    # Nothing entered during the first train year is counted.
    total_all = len(
        simulate_trades(
            data["AAA"],
            _every_n_rule(5).signal(data["AAA"], None, {}),
            {"stop_atr": 1.0, "target_r": 2.0, "max_hold": 10},
        )
    )
    assert rep["trades"] < total_all
    assert first_test >= data["AAA"].index[0] + pd.Timedelta(days=wf.TRAIN_DAYS)


def test_purge_excludes_train_trades_that_exit_in_test():
    ts = pd.Timestamp
    fold = wf._Fold(
        train_start=ts("2024-01-01"),
        test_start=ts("2025-01-01"),
        test_end=ts("2025-04-01"),
    )

    def tr(entry, exit_):
        return wf.SimTrade("A", ts(entry), ts(exit_), 100.0, 101.0, 1.0, "time", "k")

    kept = tr("2024-06-03", "2024-06-20")
    straddles = tr("2024-12-20", "2025-01-08")
    in_test = tr("2025-01-10", "2025-01-20")
    before_train = tr("2023-12-01", "2023-12-10")
    assert wf.in_sample_trades([kept, straddles, in_test, before_train], fold) == [kept]


def test_parameter_selection_runs_per_fold():
    rule = _every_n_rule(
        3,
        grid=(
            {"stop_atr": 1.0, "target_r": 2.0, "max_hold": 10},
            {"stop_atr": 2.0, "target_r": 1.0, "max_hold": 10},
        ),
    )
    data = {"AAA": _random_walk(seed=2)}
    rep = walk_forward_report(data, rule)
    assert rep["folds"] and all(f["params"] for f in rep["folds"])
    for f in rep["folds"]:
        assert f["selection"] in (
            "in_sample_expectancy",
            "default_params_insufficient_in_sample",
        )


def test_thirty_oos_trades_is_not_validated():
    data = {"AAA": _random_walk(n=700, seed=3, drift=0.003)}
    rep = walk_forward_report(data, _every_n_rule(9), point_in_time_universe=True)
    assert rep["evidence"]["grade"] != "VALIDATED"
    assert rep["trades"] < 100


def test_survivorship_caps_validated(monkeypatch):
    from src.engines.strategy_evidence import EvidenceGrade, EvidenceReport

    def fake_grade(trades, **kw):
        list(trades)
        return EvidenceReport(grade=EvidenceGrade.VALIDATED, sample_size=150)

    monkeypatch.setattr(wf, "grade_strategy_evidence", fake_grade)
    data = {"AAA": _random_walk(seed=4)}
    capped = walk_forward_report(data, _every_n_rule(5))
    assert capped["evidence"]["grade"] == "PRELIMINARY"
    assert capped["evidence"]["reason_codes"] == ["UNIVERSE_NOT_POINT_IN_TIME"]
    pit = walk_forward_report(data, _every_n_rule(5), point_in_time_universe=True)
    assert pit["evidence"]["grade"] == "VALIDATED"


def test_windows_costs_and_missing_data():
    data = {"AAA": _random_walk(seed=6), "BBB": _random_walk(seed=7)}
    rep = walk_forward_report(data, _every_n_rule(4))
    assert set(rep["windows"]) == {"90d", "6m", "1y", "2y"}
    assert (
        rep["windows"]["90d"]["trades"]
        <= rep["windows"]["2y"]["trades"]
        <= rep["trades"]
    )
    cs = rep["cost_sensitivity"]
    assert cs["0x"] > cs["1x"] > cs["2x"]

    assert (
        walk_forward_report({}, _every_n_rule(4))["evidence"]["grade"] == "NO_BACKTEST"
    )
    no_bench = walk_forward_report(data, wf.RULES["brief_rs_leader_v1"])
    assert no_bench["evidence"]["reason_codes"] == ["NO_BENCHMARK_DATA"]
    short = walk_forward_report({"AAA": _random_walk(n=100)}, _every_n_rule(4))
    assert short["evidence"]["reason_codes"] == ["HISTORY_SHORTER_THAN_TRAIN_WINDOW"]
