"""Strategy curve health unit tests."""

from src.services.strategy_curve_health import (
    HEALTH_FULL_SIZE,
    HEALTH_MONITOR,
    HEALTH_PAUSED,
    SAMPLE_LOW,
    build_strategy_curve_context,
    evaluate_regime_filter,
    resolve_health_state,
)


def test_paused_on_bad_dd():
    assert (
        resolve_health_state(sharpe_wf=1.5, max_dd_pct=30, win_rate=0.5, n_trades=50)
        == HEALTH_PAUSED
    )


def test_monitor_low_sample():
    assert (
        resolve_health_state(sharpe_wf=2.0, max_dd_pct=5, win_rate=0.6, n_trades=5)
        == HEALTH_MONITOR
    )


def test_full_size_healthy():
    assert (
        resolve_health_state(sharpe_wf=1.3, max_dd_pct=10, win_rate=0.5, n_trades=40)
        == HEALTH_FULL_SIZE
    )


def test_build_curve_context():
    ctx = build_strategy_curve_context("SPY")
    curve = ctx["strategies"][0]
    assert curve["deploy_from_curve_alone"] is False
    assert curve.get("regime_filter")
    assert curve["backtest_not_live_edge"] is True


def test_regime_filter_low_sample():
    reg = evaluate_regime_filter(n_trades=5)
    assert reg["sample"] == SAMPLE_LOW
