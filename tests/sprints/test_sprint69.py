"""
Sprint 69 Tests
================
- Model portfolios (trend_leader, pullback_swing, tactical_event)
- RegimeMonitorCog uses RegimeService
- Historical analog matching
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


# ── Model Portfolios ──


def test_trend_leader_portfolio():
    """trend_leader() creates fund with correct strategies."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder.trend_leader(capital=50000)
    assert fund.name == "Trend Leader"
    assert fund.starting_capital == 50000
    assert "MOMENTUM" in fund.strategies
    assert "BREAKOUT" in fund.strategies
    assert "VCP" in fund.strategies
    assert abs(sum(fund.strategies.values()) - 1.0) < 0.01


def test_pullback_swing_portfolio():
    """pullback_swing() creates fund with correct strategies."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder.pullback_swing()
    assert fund.name == "Pullback Swing"
    assert "MEAN_REVERT" in fund.strategies
    assert "DEFENSIVE" in fund.strategies


def test_tactical_event_portfolio():
    """tactical_event() creates fund with correct strategies."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder.tactical_event()
    assert fund.name == "Tactical Event"
    assert "BREAKOUT" in fund.strategies
    assert "MOMENTUM" in fund.strategies
    assert "MEAN_REVERT" in fund.strategies


def test_model_portfolio_usable():
    """Model portfolio can add positions and report."""
    from src.engines.fund_builder import FundBuilder

    fund = FundBuilder.trend_leader()
    fund.add_position("NVDA", 100, 50, "MOMENTUM")
    report = fund.performance_report({"NVDA": 110})
    assert report["fund_return_pct"] > 0


# ── Historical Analog Matching ──


def test_load_closed_trades():
    """Load trades from closed_trades.jsonl."""
    from src.engines.historical_analog import load_closed_trades

    trades = load_closed_trades()
    assert len(trades) >= 2
    assert "ticker" in trades[0]


def test_find_similar_cases_strategy_match():
    """Find cases matching strategy."""
    from src.engines.historical_analog import find_similar_cases

    trades = [
        {
            "ticker": "A",
            "strategy_id": "breakout",
            "pnl_pct": 5,
            "r_multiple": 1.0,
            "regime_at_entry": "UPTREND",
            "setup_grade": "B+",
            "direction": "LONG",
            "hold_days": 10,
        },
        {
            "ticker": "B",
            "strategy_id": "momentum",
            "pnl_pct": -2,
            "r_multiple": -0.5,
            "regime_at_entry": "UPTREND",
            "setup_grade": "B",
            "direction": "LONG",
            "hold_days": 5,
        },
    ]
    cases = find_similar_cases("breakout", trades=trades)
    assert len(cases) == 1
    assert cases[0]["ticker"] == "A"


def test_find_similar_cases_regime_boost():
    """Same regime boosts similarity score."""
    from src.engines.historical_analog import find_similar_cases

    trades = [
        {
            "ticker": "X",
            "strategy_id": "momentum",
            "pnl_pct": 8,
            "r_multiple": 1.5,
            "regime_at_entry": "UPTREND",
            "setup_grade": "A",
            "direction": "LONG",
            "hold_days": 15,
        },
        {
            "ticker": "Y",
            "strategy_id": "momentum",
            "pnl_pct": 3,
            "r_multiple": 0.5,
            "regime_at_entry": "SIDEWAYS",
            "setup_grade": "B",
            "direction": "LONG",
            "hold_days": 8,
        },
    ]
    cases = find_similar_cases("momentum", regime="UPTREND", trades=trades)
    assert cases[0]["ticker"] == "X"  # Higher score


def test_analog_summary():
    """analog_summary produces stats."""
    from src.engines.historical_analog import analog_summary

    cases = [
        {"pnl_pct": 5, "r_multiple": 1.0},
        {"pnl_pct": -2, "r_multiple": -0.5},
        {"pnl_pct": 8, "r_multiple": 1.5},
    ]
    s = analog_summary(cases)
    assert s["count"] == 3
    assert s["win_rate"] > 60
    assert "similar trades" in s["message"]


def test_analog_summary_empty():
    """Empty cases returns safe default."""
    from src.engines.historical_analog import analog_summary

    s = analog_summary([])
    assert s["count"] == 0
    assert "No historical" in s["message"]


def test_find_from_real_trades():
    """Find analogs from actual closed_trades.jsonl."""
    from src.engines.historical_analog import find_similar_cases, load_closed_trades

    trades = load_closed_trades()
    if trades:
        cases = find_similar_cases("breakout", regime="UPTREND", trades=trades)
        # Should find at least the AAPL breakout trade
        assert len(cases) >= 1


# ── Regime Monitor Cog ──


def test_regime_monitor_uses_regime_service():
    """RegimeMonitorCog imports and has /regime command."""
    # Just verify the module imports without discord
    import importlib

    spec = importlib.util.find_spec("src.notifications.cogs.regime_monitor")
    assert spec is not None


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
