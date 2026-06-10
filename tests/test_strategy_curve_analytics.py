"""Tests for time-series strategy curve analytics (research-only)."""

from __future__ import annotations

from src.services.strategy_curve_analytics import (
    CALIB_AGING,
    CALIB_FRESH,
    CALIB_STALE,
    CURVE_PAUSED,
    CURVE_PILOT_ONLY,
    SAMPLE_ROBUST,
    SAMPLE_THIN,
    build_strategy_curve_analytics,
    calibration_status,
    drawdown_profile,
    expectancy_trend,
    hit_rate_trend,
    live_vs_backtest_divergence,
    resolve_curve_state,
    returns_from_equity,
    rolling_sharpe,
    sample_depth_badge,
    sharpe,
    strategy_decay_score,
)


def test_returns_and_sharpe():
    eq = [100, 101, 102, 101, 103]
    rets = returns_from_equity(eq)
    assert len(rets) == 4
    s = sharpe(rets)
    assert s is not None


def test_sharpe_undefined_on_flat():
    assert sharpe([0.0, 0.0, 0.0]) is None  # zero stdev
    assert sharpe([0.01]) is None  # too short


def test_rolling_sharpe_trend_labels():
    # steadily worsening returns -> deteriorating
    rets = [0.02] * 20 + [-0.02] * 20
    roll = rolling_sharpe(rets, window=10)
    assert roll["latest"] is not None
    assert roll["trend"] in {"deteriorating", "stable", "improving"}


def test_rolling_sharpe_insufficient():
    assert rolling_sharpe([0.01, 0.02], window=20)["trend"] == "insufficient_sample"


def test_drawdown_profile_known_curve():
    eq = [100, 110, 99, 90, 95, 120]  # peak 110 -> trough 90 = -18.18%
    dd = drawdown_profile(eq)
    assert dd["max_dd_pct"] == 18.18
    assert dd["current_dd_pct"] == 0.0  # recovered to new high
    assert dd["max_underwater_len"] >= 1


def test_drawdown_acceleration_flag():
    eq = [100, 100, 100, 99, 97, 92, 85]  # accelerating losses at the end
    dd = drawdown_profile(eq)
    assert dd["dd_accelerating"] is True


def test_expectancy_and_hit_rate_trend():
    decaying = [2.0, 1.8, 1.5, 0.2, -0.5, -1.0]
    assert expectancy_trend(decaying)["trend"] == "decaying"
    improving_hits = [False, False, True, True, True, True]
    assert hit_rate_trend(improving_hits)["trend"] == "improving"


def test_live_vs_backtest_divergence():
    assert live_vs_backtest_divergence(0.1, 0.4)["ratio"] == 0.25
    assert "decay" in live_vs_backtest_divergence(0.1, 0.4)["label"].lower()
    assert live_vs_backtest_divergence(0.35, 0.35)["ratio"] == 1.0
    assert live_vs_backtest_divergence(None, 0.4)["degraded"] is True


def test_calibration_status_badges():
    assert calibration_status(10)["badge"] == CALIB_FRESH
    assert calibration_status(60)["badge"] == CALIB_AGING
    assert calibration_status(200)["badge"] == CALIB_STALE
    assert calibration_status(None)["badge"] == CALIB_STALE


def test_sample_depth_badge():
    assert sample_depth_badge(5) == SAMPLE_THIN
    assert sample_depth_badge(100) == SAMPLE_ROBUST


def test_decay_score_monotonic_and_componentized():
    low = strategy_decay_score(
        rolling_sharpe_trend="improving", dd_accelerating=False,
        expectancy_trend_label="improving", divergence_ratio=1.0,
        calibration_badge=CALIB_FRESH, execution_drag_bps=2.0,
    )
    high = strategy_decay_score(
        rolling_sharpe_trend="deteriorating", dd_accelerating=True,
        expectancy_trend_label="decaying", divergence_ratio=0.2,
        calibration_badge=CALIB_STALE, execution_drag_bps=40.0,
    )
    assert high["score"] > low["score"]
    assert high["band"] == "high_decay"
    assert "rolling_sharpe" in high["components"]


def test_decay_downgrades_curve_state_only():
    # Healthy scalars but high decay -> downgraded, never upgraded.
    state = resolve_curve_state(
        sharpe_wf=1.5, max_dd_pct=8, win_rate=0.5, n_trades=80, decay_band="high_decay"
    )
    assert state == CURVE_PILOT_ONLY


def test_paused_state_on_broken_curve():
    state = resolve_curve_state(
        sharpe_wf=-0.5, max_dd_pct=30, win_rate=0.3, n_trades=40, decay_band="moderate_decay"
    )
    assert state == CURVE_PAUSED


def test_context_is_research_only():
    from src.services.signal_provenance import assert_no_deploy_from_signals
    from src.services.surface_authority import AUTHORITY_RESEARCH

    eq = [100 * (1.01 ** i) for i in range(40)]
    ctx = build_strategy_curve_analytics(
        equity_curve=eq, r_multiples=[0.5, -0.3] * 20, win_flags=[True, False] * 20,
        live_expectancy_r=0.3, backtest_expectancy_r=0.35, days_since_calibration=20,
    )
    assert ctx["authority_ceiling"] == AUTHORITY_RESEARCH
    assert ctx["deploy_from_curve_alone"] is False
    assert ctx["provenance"]["deploy_from_signal_alone"] is False
    assert_no_deploy_from_signals([ctx])
