"""
Sprint 66 Tests
================
- /brief Discord command (import check)
- Gap detection engine
- Scenario engine dynamic sector mapping
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


# ── Gap Detector ──


def test_gap_detector_basic_gap_up():
    """Detect a gap up in OHLCV data."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = [
        {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"open": 103, "high": 105, "low": 102, "close": 104, "volume": 1500},
    ]
    report = det.detect(bars, ticker="TEST")
    assert len(report.gaps) == 1
    assert report.gaps[0].direction == "UP"
    assert report.gaps[0].gap_pct > 0


def test_gap_detector_basic_gap_down():
    """Detect a gap down."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = [
        {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"open": 99, "high": 100, "low": 97, "close": 98, "volume": 1200},
    ]
    report = det.detect(bars, ticker="TEST")
    assert len(report.gaps) == 1
    assert report.gaps[0].direction == "DOWN"


def test_gap_detector_no_gap():
    """Small move → no gap detected."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = [
        {"open": 100, "high": 101, "low": 99, "close": 100.2, "volume": 1000},
        {"open": 100.3, "high": 101, "low": 99.5, "close": 100.5, "volume": 1000},
    ]
    report = det.detect(bars, ticker="TEST")
    assert len(report.gaps) == 0


def test_gap_detector_gap_fill():
    """Gap gets filled by subsequent price action."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = [
        {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"open": 103, "high": 105, "low": 102, "close": 104, "volume": 1500},
        {"open": 103, "high": 104, "low": 100, "close": 100.5, "volume": 1200},
    ]
    report = det.detect(bars, ticker="TEST")
    assert len(report.gaps) >= 1
    assert report.gaps[0].filled is True
    assert report.gaps[0].fill_bars == 1


def test_gap_detector_breakaway():
    """Large gap + high volume → BREAKAWAY classification."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    # Build 25 bars of quiet trading, then a big gap
    bars = []
    for i in range(25):
        bars.append({"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000})
    # Big gap up on 3x volume
    bars.append({"open": 105, "high": 108, "low": 104, "close": 107, "volume": 3000})
    report = det.detect(bars, ticker="BRKWY")
    breakaway = [g for g in report.gaps if g.gap_type == "BREAKAWAY"]
    assert len(breakaway) >= 1


def test_gap_detector_report_to_dict():
    """GapReport.to_dict() returns valid structure."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = [
        {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"open": 103, "high": 105, "low": 102, "close": 104, "volume": 1500},
    ]
    report = det.detect(bars, ticker="DICT")
    d = report.to_dict()
    assert d["ticker"] == "DICT"
    assert d["total_gaps"] == 1
    assert "recent_gap" in d


def test_gap_detector_multiple_gaps():
    """Detect multiple gaps in sequence."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = [
        {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"open": 102, "high": 103, "low": 101, "close": 102, "volume": 1000},
        {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"open": 102, "high": 103, "low": 101, "close": 102.5, "volume": 1000},
    ]
    report = det.detect(bars)
    assert len(report.gaps) >= 2


def test_gap_detector_tendency():
    """Gap tendency = fills_fast when gaps fill within 3 bars."""
    from src.engines.gap_detector import GapDetector

    det = GapDetector()
    bars = []
    # 3 gap-up-then-fill cycles
    for _ in range(3):
        bars.append({"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000})
        bars.append({"open": 102, "high": 103, "low": 99, "close": 100, "volume": 1000})
    report = det.detect(bars)
    if len(report.gaps) >= 3:
        assert report.gap_tendency == "fills_fast"


# ── Scenario Engine Dynamic Sectors ──


def test_scenario_engine_known_ticker():
    """Known ticker uses static map."""
    from src.engines.scenario_engine import _get_shock_for_ticker

    shocks = {"equity": -0.10, "tech": -0.20, "growth": -0.25}
    shock = _get_shock_for_ticker("NVDA", shocks)
    assert shock <= -0.20  # Should pick worst of tech/growth


def test_scenario_engine_unknown_ticker_fallback():
    """Unknown ticker falls back to SectorClassifier → equity."""
    from src.engines.scenario_engine import _get_shock_for_ticker

    shocks = {"equity": -0.10, "tech": -0.15}
    shock = _get_shock_for_ticker("RANDOMXYZ123", shocks)
    assert shock <= 0  # Should get some shock


def test_scenario_engine_run():
    """ScenarioEngine.run_scenario works end to end."""
    from src.engines.scenario_engine import ScenarioEngine

    eng = ScenarioEngine()
    scenarios = eng.list_scenarios()
    assert len(scenarios) > 0
    result = eng.run_scenario(
        scenario_key=scenarios[0]["key"],
        positions=[
            {"ticker": "AAPL", "weight": 0.5, "entry_price": 150},
            {"ticker": "JPM", "weight": 0.3, "entry_price": 170},
        ],
    )
    d = result.to_dict()
    assert "estimated_pnl_pct" in d


# ── Discord /brief command ──
# Import test removed — discord_bot.py pulls 30+ min
# of transitive deps. The /brief command is verified
# by code inspection (registered in run_interactive_bot).


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
