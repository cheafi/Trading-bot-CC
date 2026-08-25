"""Tests for Nison candlestick context engine."""

from src.services.candlestick_context import (
    NISON_LABELS,
    build_candlestick_analysis,
    demote_scanner_hit_metadata,
    score_pattern_context,
    score_risk_geometry,
    tags_for_playbook_row,
)
from src.services.macro_trend import assess_macro_trend, assess_market_macro


def _bullish_dossier():
    return {
        "price": 100.0,
        "technicals": {
            "rsi": 58,
            "macd_signal": "BULLISH",
            "volume_ratio": 1.6,
            "above_sma20": True,
            "above_sma50": True,
            "above_sma200": True,
            "support": 97.0,
            "support_dist_pct": 3.0,
            "resistance": 108.0,
            "resistance_dist_pct": 8.0,
        },
        "trade_plan": {
            "stop": 95.0,
            "invalidation": "Close below $97.00",
            "rr_ratio": 2.5,
        },
        "regime": {"label": "Risk-on", "should_trade": True},
    }


def test_strong_context_actionable_when_geometry_ok():
    analysis = build_candlestick_analysis(_bullish_dossier(), unified={"stop": 95.0, "rr_ratio": 2.5})
    assert analysis["scores"]["pattern_context"] >= 55
    assert analysis["risk_reward"]["meets_trade_gate"] is True
    assert analysis["stop_invalidation"]["no_stop_no_trade"] is False
    assert analysis["execution_status"] in ("ACTIONABLE", "WATCH_FOR_TRIGGER")


def test_no_stop_demotes_execution():
    dossier = _bullish_dossier()
    dossier["trade_plan"] = {"rr_ratio": 2.5}
    analysis = build_candlestick_analysis(dossier)
    assert analysis["stop_invalidation"]["no_stop_no_trade"] is True
    assert analysis["execution_status"] != "ACTIONABLE"
    assert NISON_LABELS["no_stop_no_trade"] in analysis["humility_labels"]


def test_bullish_pattern_bearish_backdrop_label():
    dossier = _bullish_dossier()
    dossier["technicals"]["above_sma50"] = False
    dossier["technicals"]["above_sma200"] = False
    dossier["regime"] = {"label": "Hostile", "should_trade": False}
    analysis = build_candlestick_analysis(dossier)
    assert NISON_LABELS["bullish_pattern_bearish_backdrop"] in analysis["humility_labels"]


def test_pattern_context_penalizes_bear_macro_for_bull_pattern():
    tech = {
        "rsi": 55,
        "support_dist_pct": 2.0,
        "resistance_dist_pct": 10.0,
    }
    macro_bull = assess_macro_trend(
        {**tech, "above_sma20": True, "above_sma50": True, "above_sma200": True},
        {"should_trade": True},
    )
    macro_bear = assess_macro_trend(
        {**tech, "above_sma20": False, "above_sma50": False},
        {"label": "Hostile", "should_trade": False},
    )
    pattern = {"direction": "bullish"}
    bull_ctx = score_pattern_context(tech, macro_bull, pattern)
    bear_ctx = score_pattern_context(tech, macro_bear, pattern)
    assert bull_ctx > bear_ctx


def test_risk_geometry_requires_stop():
    tech = {"support_dist_pct": 2.0}
    with_stop = score_risk_geometry({"stop": 90.0, "rr_ratio": 2.5}, {}, tech)
    without_stop = score_risk_geometry({}, {}, tech)
    assert with_stop > without_stop


def test_playbook_tags_from_signal():
    tags = tags_for_playbook_row(
        signal={
            "rsi": 30,
            "entry_price": 50,
            "stop_price": 48,
            "risk_reward": 2.2,
            "invalidation": "Close below $48",
        }
    )
    assert tags["context_checked"] is True
    assert "pattern_tag" in tags
    assert tags["rr_tag"] in ("rr_ok", "rr_weak")


def test_scanner_hit_demoted_without_actionable_context():
    meta = demote_scanner_hit_metadata(
        {"ticker": "TEST", "score": 8.0},
        signal={"rsi": 80, "entry_price": 100, "stop_price": 0, "risk_reward": 1.2},
    )
    assert meta.get("nison_demoted") is True
    assert meta.get("nison_context_label")


def test_market_macro_strip():
    strip = assess_market_macro({"label": "Caution", "should_trade": False, "tradeability": "WAIT"})
    assert strip["trend_bias"] in ("bearish", "neutral")
    assert "summary" in strip
