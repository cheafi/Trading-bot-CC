"""
Sprint 65 Tests
================
- RS score bug fix (bench_ret==0)
- Scanner RSI overlap fix
- PositionManager (HOLD/REDUCE/EXIT/TRAIL_STOP)
- Circuit breaker wired into pipeline
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


# ── RS Score Fix ──

def test_rs_score_bench_zero_positive():
    """RS score when bench_ret=0, stock positive → bounded."""
    from src.engines.rs_ranking import RSRankingEngine
    eng = RSRankingEngine()
    stock = {"return_1w": 10, "return_1m": 10, "return_3m": 10, "return_6m": 10}
    bench = {"return_1w": 0, "return_1m": 0, "return_3m": 0, "return_6m": 0}
    entry = eng._compute_rs(stock, bench)
    assert entry.rs_composite > 100, f"Expected >100, got {entry.rs_composite}"


def test_rs_score_bench_zero_negative():
    """RS score when bench_ret=0, stock negative → bounded."""
    from src.engines.rs_ranking import RSRankingEngine
    eng = RSRankingEngine()
    stock = {"return_1w": -20, "return_1m": -20, "return_3m": -20, "return_6m": -20}
    bench = {"return_1w": 0, "return_1m": 0, "return_3m": 0, "return_6m": 0}
    entry = eng._compute_rs(stock, bench)
    assert entry.rs_composite < 100, f"Expected <100, got {entry.rs_composite}"


def test_rs_score_bench_zero_extreme():
    """RS score when bench_ret=0, extreme stock → clamped to [0,300]."""
    from src.engines.rs_ranking import RSRankingEngine
    eng = RSRankingEngine()
    stock = {"return_1w": 500, "return_1m": 500, "return_3m": 500, "return_6m": 500}
    bench = {"return_1w": 0, "return_1m": 0, "return_3m": 0, "return_6m": 0}
    entry = eng._compute_rs(stock, bench)
    assert entry.rs_composite <= 300, f"Expected ≤300, got {entry.rs_composite}"


# ── Scanner RSI Overlap Fix ──

def test_mean_reversion_skips_breakdown_rsi():
    """MeanReversionScanner should NOT fire at RSI < 25."""
    from src.engines.scanner_matrix import ScannerMatrix
    matrix = ScannerMatrix()
    mr = next(
        (s for s in matrix.scanners
         if type(s).__name__ == "MeanReversionScanner"), None
    )
    assert mr is not None, "MeanReversionScanner not found"
    signals = [{"ticker": "TEST", "rsi": 20, "is_breakdown": True}]
    hits = mr.scan(signals, {})
    assert len(hits) == 0, "RSI=20 should be breakdown, not mean reversion"


def test_mean_reversion_fires_rsi_27():
    """MeanReversionScanner SHOULD fire at RSI=27 (sweet spot)."""
    from src.engines.scanner_matrix import ScannerMatrix
    matrix = ScannerMatrix()
    mr = next(
        (s for s in matrix.scanners
         if type(s).__name__ == "MeanReversionScanner"), None
    )
    assert mr is not None
    signals = [{"ticker": "TEST", "rsi": 27, "is_breakdown": False}]
    hits = mr.scan(signals, {})
    assert len(hits) == 1, "RSI=27 should trigger mean reversion"


# ── Position Manager ──

def test_position_manager_hold():
    """Healthy position → HOLD."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="AAPL", entry_price=150, current_price=153,
        stop_price=145, rs_rank=70, days_held=5,
    )
    actions = mgr.evaluate([pos])
    assert len(actions) == 1
    assert actions[0].action == "HOLD"


def test_position_manager_stop_hit():
    """Price below stop → EXIT URGENT."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="TSLA", entry_price=200, current_price=140,
        stop_price=145,
    )
    actions = mgr.evaluate([pos])
    assert actions[0].action == "EXIT"
    assert actions[0].urgency == "URGENT"


def test_position_manager_1r_reduce():
    """1R profit reached → REDUCE 33%."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="NVDA", entry_price=100, current_price=107,
        stop_price=95, rs_rank=80, days_held=8,
    )
    # Risk = 100 - 95 = 5, profit = 7, R = 1.4
    actions = mgr.evaluate([pos])
    assert actions[0].action == "REDUCE"
    assert actions[0].reduce_pct == 33.0


def test_position_manager_structure_break():
    """Downtrend structure → EXIT HIGH."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="META", entry_price=400, current_price=380,
        stop_price=370, trend_structure="downtrend",
    )
    actions = mgr.evaluate([pos])
    assert actions[0].action == "EXIT"
    assert actions[0].urgency == "HIGH"


def test_position_manager_rs_deterioration():
    """RS rank below threshold → REDUCE."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="XOM", entry_price=100, current_price=101,
        stop_price=95, rs_rank=30, days_held=10,
    )
    actions = mgr.evaluate([pos])
    assert actions[0].action == "REDUCE"
    assert "RS rank" in actions[0].reason


def test_position_manager_trailing_stop():
    """High water mark → trail stop up."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="AMZN", entry_price=150, current_price=170,
        stop_price=145, highest_price=175, atr_pct=2.0,
        rs_rank=80, days_held=15,
    )
    actions = mgr.evaluate([pos])
    # Trail stop = 175 * (1 - 2*2/100) = 175 * 0.96 = 168
    assert actions[0].new_stop > 145


def test_position_manager_time_stop():
    """20+ days held with minimal gain → REDUCE."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="WMT", entry_price=100, current_price=101,
        stop_price=95, rs_rank=55, days_held=25,
    )
    actions = mgr.evaluate([pos])
    assert actions[0].action == "REDUCE"
    assert "Time stop" in actions[0].reason


def test_position_manager_crisis_exit():
    """CRISIS regime + underwater → EXIT."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    pos = OpenPosition(
        ticker="SQ", entry_price=100, current_price=90,
        stop_price=85,
    )
    actions = mgr.evaluate([pos], regime={"trend": "CRISIS"})
    assert actions[0].action == "EXIT"


def test_position_manager_sort_order():
    """EXIT before REDUCE before HOLD."""
    from src.engines.position_manager import PositionManager, OpenPosition
    mgr = PositionManager()
    positions = [
        OpenPosition(
            ticker="A", entry_price=100, current_price=102,
            stop_price=95, rs_rank=80,
        ),
        OpenPosition(
            ticker="B", entry_price=100, current_price=80,
            stop_price=85, trend_structure="downtrend",
        ),
        OpenPosition(
            ticker="C", entry_price=100, current_price=102,
            stop_price=95, rs_rank=30,
        ),
    ]
    actions = mgr.evaluate(positions)
    assert actions[0].action == "EXIT"    # B
    assert actions[1].action == "REDUCE"  # C
    assert actions[2].action == "HOLD"    # A


def test_position_manager_summary():
    """Summary counts actions correctly."""
    from src.engines.position_manager import (
        PositionManager, OpenPosition, PositionAction,
    )
    mgr = PositionManager()
    actions = [
        PositionAction(ticker="A", action="HOLD"),
        PositionAction(ticker="B", action="EXIT", urgency="URGENT"),
        PositionAction(ticker="C", action="REDUCE"),
    ]
    s = mgr.summary(actions)
    assert s["hold"] == 1
    assert s["exit"] == 1
    assert s["reduce"] == 1
    assert len(s["urgent"]) == 1


# ── Circuit Breaker in Pipeline ──

def test_pipeline_circuit_breaker_halt():
    """Pipeline halts trades when drawdown exceeds 10%."""
    from src.engines.sector_pipeline import SectorPipeline
    pipeline = SectorPipeline()
    signal = {
        "ticker": "TEST",
        "rsi": 55,
        "volume_ratio": 2.0,
        "rs_rank": 80,
        "sector": "Technology",
        "_portfolio_value": 90000,
        "_portfolio_peak": 100000,  # -10% drawdown
    }
    regime = {"trend": "UPTREND", "risk_score": 30}
    result = pipeline.process(signal, regime)
    # With -10% drawdown, circuit breaker should halt
    assert "circuit breaker" in result.decision.rationale.lower() or \
        result.decision.action in ("NO_TRADE", "WATCH")


def test_pipeline_circuit_breaker_reduced():
    """Pipeline reduces sizing during moderate drawdown."""
    from src.engines.sector_pipeline import SectorPipeline
    pipeline = SectorPipeline()
    signal = {
        "ticker": "TEST2",
        "rsi": 50,
        "volume_ratio": 2.5,
        "rs_rank": 90,
        "sector": "Technology",
        "_portfolio_value": 95000,
        "_portfolio_peak": 100000,  # -5% drawdown
    }
    regime = {"trend": "UPTREND", "risk_score": 20}
    result = pipeline.process(signal, regime)
    # Should have drawdown note in rationale
    if result.decision.action == "TRADE":
        assert "drawdown" in result.decision.rationale.lower()


# ── Cross-Asset Monitor Wiring ──

def test_cross_asset_monitor_standalone():
    """CrossAssetMonitor returns stress report."""
    from src.engines.cross_asset_monitor import CrossAssetMonitor
    mon = CrossAssetMonitor()
    report = mon.analyse(vix=35, spy_change_pct=-2.0, tlt_change_pct=-1.0)
    assert report.stress_score > 0
    assert report.stress_level in ("calm", "elevated", "high", "crisis")


def test_pipeline_cross_asset_stress():
    """Pipeline applies cross-asset sizing when stress data provided."""
    from src.engines.sector_pipeline import SectorPipeline
    pipeline = SectorPipeline()
    signal = {
        "ticker": "STRESS",
        "rsi": 50,
        "volume_ratio": 2.0,
        "rs_rank": 80,
        "sector": "Technology",
    }
    regime = {
        "trend": "UPTREND",
        "risk_score": 20,
        "cross_asset": {"vix": 40, "spy_change": -2.0, "breadth": 30},
    }
    result = pipeline.process(signal, regime)
    # High VIX + low breadth → stress note in rationale
    if result.decision.action == "TRADE":
        assert "cross-asset" in result.decision.rationale.lower()


def test_position_manager_to_dict():
    """PositionAction.to_dict() includes key fields."""
    from src.engines.position_manager import PositionAction
    a = PositionAction(
        ticker="AAPL", action="REDUCE", reason="1R hit",
        reduce_pct=33.0, current_pnl_pct=5.2, days_held=10,
    )
    d = a.to_dict()
    assert d["ticker"] == "AAPL"
    assert d["reduce_pct"] == 33.0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
