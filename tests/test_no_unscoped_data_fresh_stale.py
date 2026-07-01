"""No unscoped DATA FRESH / DATA STALE in header truth strip."""

from __future__ import annotations

from src.services.system_truth import build_unified_truth_strip, resolve_system_truth, system_truth_line


def test_truth_strip_uses_scoped_labels_not_data_stale():
    truth = resolve_system_truth(
        {
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {},
            "qualification_levels": {"setup_qualified": 2, "deploy_qualified": 0},
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    strip = truth["truth_strip"]
    line = system_truth_line(truth)
    assert "DATA STALE" not in strip
    assert "DATA FRESH" not in strip
    assert "DATA STALE" not in line
    assert "DATA FRESH" not in line
    assert "Market:" in strip
    assert "Board:" in strip
    assert "Authority:" in strip


def test_build_unified_truth_strip_format():
    strip = build_unified_truth_strip(
        {
            "market_data_freshness": "fresh",
            "ranked_board_freshness": "stale",
            "brief_freshness": "expired",
            "broker_freshness": "offline",
            "brief_age_days": 21,
            "deploy_authority": False,
        }
    )
    assert strip == "Market: Fresh · Board: Stale · Brief: Expired 21d · Broker: Offline · Authority: Blocked"
