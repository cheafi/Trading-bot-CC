"""Backtest lab → curve health bridge."""

from src.services.backtest_curve_bridge import curve_metrics_from_lab


def test_curve_metrics_from_walk_forward():
    wf = {
        "windows": [
            {
                "window": "recent",
                "sharpe": 1.1,
                "max_dd": 12.5,
                "win_rate": 52,
                "trades": 30,
                "return_pct": 8.0,
            },
            {
                "window": "1y",
                "sharpe": 0.9,
                "max_dd": 15.0,
                "win_rate": 48,
                "trades": 55,
                "return_pct": 5.0,
            },
        ]
    }
    review = {"trade_count": 30, "win_rate": 52.0}
    metrics = curve_metrics_from_lab(wf, review, ticker="SPY")
    assert metrics is not None
    assert metrics["deploy_from_curve_alone"] is False
    assert metrics["backtest_not_live_edge"] is True
    assert metrics["metrics"]["n_trades"] == 30
