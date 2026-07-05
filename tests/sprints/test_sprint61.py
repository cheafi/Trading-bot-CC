"""
Phase E tests — Validation: Pipeline backtester, confidence calibration, slippage model.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

# ─── E1: Confidence Calibration ─────────────────────────────────────


def test_calibration_well_calibrated():
    """Well-calibrated trades should have low Brier score."""
    from src.backtest.calibration import ConfidenceCalibrator

    # Simulate trades where confidence ≈ actual win rate
    trades = []
    rng = np.random.RandomState(42)
    for _ in range(200):
        conf = rng.uniform(0.3, 0.9)
        win = rng.random() < conf  # truly calibrated
        pnl = 0.03 if win else -0.02
        trades.append({"confidence": conf, "pnl_pct": pnl})

    cal = ConfidenceCalibrator(n_buckets=5)
    report = cal.calibrate(trades)

    assert report.total_trades == 200
    assert (
        report.brier_score < 0.30
    ), f"Brier too high for calibrated data: {report.brier_score}"
    assert len(report.buckets) == 5
    assert report.recommendation  # has a recommendation string


def test_calibration_overconfident():
    """System that always says 90% but only wins 40% → overconfident."""
    from src.backtest.calibration import ConfidenceCalibrator

    trades = []
    for i in range(100):
        trades.append(
            {
                "confidence": 0.9,
                "pnl_pct": 0.02 if i < 40 else -0.03,
            }
        )

    cal = ConfidenceCalibrator(n_buckets=5)
    report = cal.calibrate(trades)

    assert report.overconfident is True
    assert report.brier_score > 0.2, "Should have high Brier for overconfident"


def test_calibration_recalibrate():
    """recalibrate() returns a mapping of confidence ranges → actual win rates."""
    from src.backtest.calibration import ConfidenceCalibrator

    trades = [
        {"confidence": 0.8, "pnl_pct": 0.05},
        {"confidence": 0.8, "pnl_pct": -0.02},
        {"confidence": 0.8, "pnl_pct": 0.03},
    ]
    cal = ConfidenceCalibrator(n_buckets=5)
    mapping = cal.recalibrate(trades)

    assert isinstance(mapping, dict)
    # All 3 trades are in the 0.8 bucket → actual win rate = 2/3
    for key, val in mapping.items():
        if "0.8" in key:
            assert abs(val - 2 / 3) < 0.01


def test_calibration_empty():
    """Empty trades list should not crash."""
    from src.backtest.calibration import ConfidenceCalibrator

    cal = ConfidenceCalibrator()
    report = cal.calibrate([])
    assert report.total_trades == 0
    assert report.brier_score == 1.0


# ─── E2: Pipeline Backtester ────────────────────────────────────────


def test_pipeline_backtester_basic():
    """Pipeline backtester processes TRADE/WATCH/AVOID signals."""
    from src.backtest.pipeline_backtester import PipelineBacktester

    signals = [
        {
            "ticker": "AAPL",
            "action": "TRADE",
            "grade": "A",
            "sector": "Technology",
            "confidence": 0.75,
            "entry_price": 150.0,
            "stop_loss": 142.5,
            "take_profit": 165.0,
            "position_size_pct": 2.0,
            "date": "2025-01-10",
        },
        {
            "ticker": "MSFT",
            "action": "WATCH",
            "grade": "B",
            "sector": "Technology",
            "confidence": 0.55,
            "entry_price": 400.0,
            "stop_loss": 380.0,
            "take_profit": 440.0,
            "position_size_pct": 1.5,
            "date": "2025-01-10",
        },
        {
            "ticker": "XOM",
            "action": "AVOID",
            "grade": "D",
            "sector": "Energy",
            "confidence": 0.30,
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "position_size_pct": 0.5,
            "date": "2025-01-10",
        },
    ]

    bt = PipelineBacktester(forward_days=10)
    result = bt.run(signals)

    assert result.total_signals == 3
    assert result.trade_signals == 1
    assert result.watch_signals == 1
    assert result.avoid_signals == 1
    assert result.trades_taken == 1  # only TRADE actions


def test_pipeline_backtester_with_prices():
    """Pipeline backtester resolves outcomes from price data."""
    from src.backtest.pipeline_backtester import PipelineBacktester

    signals = [
        {
            "ticker": "AAPL",
            "action": "TRADE",
            "grade": "A",
            "sector": "Technology",
            "confidence": 0.80,
            "entry_price": 150.0,
            "stop_loss": 142.0,
            "take_profit": 165.0,
            "position_size_pct": 2.0,
            "date": "2025-01-10",
        },
    ]

    # Price data: hits target on day 5
    prices = {
        "AAPL": [
            {"date": "2025-01-10", "close": 150.0},
            {"date": "2025-01-11", "close": 152.0},
            {"date": "2025-01-12", "close": 155.0},
            {"date": "2025-01-13", "close": 160.0},
            {"date": "2025-01-14", "close": 163.0},
            {"date": "2025-01-15", "close": 166.0},  # above target
        ]
    }

    bt = PipelineBacktester(forward_days=10)
    result = bt.run(signals, price_lookup=prices)

    assert result.trades_taken == 1
    assert result.wins == 1
    assert result.win_rate == 1.0
    assert result.avg_pnl_pct > 0


def test_pipeline_backtester_stop_hit():
    """Pipeline backtester detects stop loss hit."""
    from src.backtest.pipeline_backtester import PipelineBacktester

    signals = [
        {
            "ticker": "TSLA",
            "action": "TRADE",
            "grade": "B",
            "sector": "Auto",
            "confidence": 0.60,
            "entry_price": 200.0,
            "stop_loss": 190.0,
            "take_profit": 220.0,
            "position_size_pct": 1.5,
            "date": "2025-01-10",
        },
    ]

    prices = {
        "TSLA": [
            {"date": "2025-01-10", "close": 200.0},
            {"date": "2025-01-11", "close": 195.0},
            {"date": "2025-01-12", "close": 188.0},  # below stop
        ]
    }

    bt = PipelineBacktester(forward_days=10)
    result = bt.run(signals, price_lookup=prices)

    assert result.losses == 1
    assert result.avg_pnl_pct < 0


def test_pipeline_backtester_by_grade():
    """Results break down by grade."""
    from src.backtest.pipeline_backtester import PipelineBacktester

    signals = [
        {
            "ticker": "A1",
            "action": "TRADE",
            "grade": "A",
            "sector": "Tech",
            "confidence": 0.85,
            "entry_price": 100,
            "stop_loss": 95,
            "take_profit": 110,
            "position_size_pct": 2,
            "date": "2025-01-10",
        },
        {
            "ticker": "B1",
            "action": "TRADE",
            "grade": "B",
            "sector": "Tech",
            "confidence": 0.65,
            "entry_price": 50,
            "stop_loss": 47,
            "take_profit": 55,
            "position_size_pct": 1,
            "date": "2025-01-10",
        },
    ]

    bt = PipelineBacktester()
    result = bt.run(signals)

    assert "A" in result.by_grade
    assert "B" in result.by_grade
    assert result.by_grade["A"]["count"] == 1
    assert result.by_grade["B"]["count"] == 1


def test_pipeline_backtester_summary():
    """Summary string renders without error."""
    from src.backtest.pipeline_backtester import PipelineBacktester

    signals = [
        {
            "ticker": "X",
            "action": "TRADE",
            "grade": "A",
            "sector": "Tech",
            "confidence": 0.7,
            "entry_price": 100,
            "stop_loss": 95,
            "take_profit": 110,
            "position_size_pct": 2,
            "date": "2025-01-10",
        },
    ]
    bt = PipelineBacktester()
    result = bt.run(signals)
    text = result.summary()
    assert "Pipeline Backtest" in text
    assert "Win rate" in text


# ─── E3: Dynamic Slippage Model (already in enhanced_backtester) ────


def test_dynamic_slippage_model():
    """Enhanced backtester's dynamic slippage increases with low volume."""
    import pandas as pd

    from src.backtest.enhanced_backtester import BacktestConfig, BacktestEngine

    config = BacktestConfig(use_dynamic_slippage=True)
    engine = BacktestEngine(config)

    # Build price data with today's volume much lower than average
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    volumes = [500000] * 29 + [50000]  # last day very low volume
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 102.0,
            "low": 98.0,
            "close": 100.0,
            "volume": volumes,
        },
        index=dates,
    )

    price_data = {"TEST": df}
    date = dates[29]  # last day with low volume

    slip = engine._calculate_slippage("TEST", 100.0, price_data, date)

    # Dynamic slippage should be > flat rate
    assert (
        slip > config.slippage_rate
    ), f"Dynamic slippage {slip} should exceed flat {config.slippage_rate}"


def test_slippage_cap():
    """Slippage is capped at slippage_cap_bps."""
    from src.backtest.enhanced_backtester import BacktestConfig, BacktestEngine

    config = BacktestConfig(
        use_dynamic_slippage=True,
        slippage_cap_bps=20.0,  # 20 bps cap
    )
    engine = BacktestEngine(config)

    # No price data → base bps only
    slip = engine._calculate_slippage("XYZ", 100.0, {}, None)

    assert slip <= 20.0 / 10000.0, f"Slippage {slip} exceeds cap"


# ─── E4: Calibration + Pipeline integration ────────────────────────


def test_calibration_from_pipeline_output():
    """ConfidenceCalibrator works on PipelineBacktester's calibration_trades."""
    from src.backtest.calibration import ConfidenceCalibrator
    from src.backtest.pipeline_backtester import PipelineBacktester

    signals = []
    for i in range(50):
        signals.append(
            {
                "ticker": f"T{i}",
                "action": "TRADE",
                "grade": "B",
                "sector": "Tech",
                "confidence": 0.5 + (i % 5) * 0.1,
                "entry_price": 100,
                "stop_loss": 95,
                "take_profit": 110,
                "position_size_pct": 1,
                "date": f"2025-01-{10 + i % 20:02d}",
            }
        )

    bt = PipelineBacktester()
    result = bt.run(signals)

    # Feed calibration data to calibrator
    cal = ConfidenceCalibrator(n_buckets=5)
    report = cal.calibrate(result.calibration_trades)

    assert report.total_trades == 50
    assert 0 <= report.brier_score <= 1.0
    text = report.summary()
    assert "Calibration" in text


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
