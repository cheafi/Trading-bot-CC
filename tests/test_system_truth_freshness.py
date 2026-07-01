"""Typed freshness — no unscoped DATA FRESH + DATA STALE together."""

from __future__ import annotations

from src.services.system_truth import (
    resolve_system_truth,
    system_truth_line,
    typed_freshness_display,
)


def test_typed_freshness_scoped_lines_not_mixed_generic():
    truth = resolve_system_truth(
        {
            "trust": {"stale": True, "freshness": "STALE", "source": "decision_engine"},
            "market_regime": {"tradeability": "WAIT", "should_trade": True, "vix": 16},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 0},
            "filter_funnel": {},
            "scanner_degraded": True,
            "top_5": [],
        },
        cc_header={"data_tier": "STALE"},
        ops={"engine_running": True},
        brief_age_days=1,
    )
    line = typed_freshness_display(truth)
    assert "Market:" in line
    assert "Board:" in line
    assert "Brief:" in line
    assert "Broker:" in line
    assert "Authority:" in line
    assert "DATA FRESH" not in line.upper() or "DATA STALE" not in line.upper() or line.upper().count("DATA") == 0
    assert "DATA FRESH" not in line
    assert "DATA STALE" not in line
    strip = system_truth_line(truth)
    assert strip == line
    assert "Fresh" in strip or "Stale" in strip or "Unavailable" in strip


def test_fresh_market_stale_board_distinct_labels():
    truth = resolve_system_truth(
        {
            "trust": {"stale": False, "source": "decision_engine", "freshness": "REAL_TIME"},
            "used_brief_fallback": True,
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {},
            "qualification_levels": {},
            "filter_funnel": {},
            "top_5": [{"ticker": "X", "action": "WATCH"}],
            "scanner_degraded": False,
        },
        cc_header={"data_tier": "FRESH"},
        ops={},
        brief_age_days=0,
    )
    line = typed_freshness_display(truth)
    assert "Market: Fresh" in line
    assert "Board: Fallback" in line
