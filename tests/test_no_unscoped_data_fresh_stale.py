"""No unscoped DATA FRESH / DATA STALE in header truth strip."""

from __future__ import annotations

from pathlib import Path

from src.services.system_truth import build_unified_truth_strip, resolve_system_truth, system_truth_line

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


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
    assert strip == (
        "Market: Fresh · Board: Stale · Brief: Expired 21d · Broker: Offline · "
        "Runtime: Unknown · Authority: Blocked"
    )


def test_index_header_uses_scoped_strip_not_data_fresh_pill():
    raw = INDEX.read_text(encoding="utf-8", errors="replace")
    header = raw.split("</header>", 1)[0]
    assert "DATA FRESH" not in header
    assert "DATA STALE" not in header
    assert "scopedFreshnessStrip" in raw or "unifiedTruthStripLine" in raw


def test_cc_helpers_strip_avoids_unscoped_data_labels():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "DATA FRESH" not in js
    assert "DATA STALE" not in js
    assert "function scopedFreshnessStrip" in js
    assert "function shellTruthViewModel" in js
    assert "ENGINE ON" not in js


def test_shell_truth_vm_no_data_fresh_stale_contradiction():
    truth = resolve_system_truth(
        {
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {"authority_level": "research", "gates_active": True},
            "execution_readiness": {"engine_running": True},
            "qualification_levels": {"setup_qualified": 2, "deploy_qualified": 0},
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    strip = truth["typed_freshness_display"]
    assert "DATA STALE" not in strip
    assert "DATA FRESH" not in strip
    assert "Market:" in strip
    assert "Board:" in strip

