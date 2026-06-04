"""Today quant_cluster_hints wiring — contract, WAIT fixture, monitor copy."""

from __future__ import annotations

from pathlib import Path

from src.services.today_insights import (
    build_monitor_triggers,
    build_quant_cluster_hints,
    resolve_book_dd_utilization_for_hints,
)

ROOT = Path(__file__).resolve().parents[1]
DECISION_SRC = ROOT / "src/api/routers/decision.py"
INDEX_HTML = ROOT / "src/api/templates/index.html"
CC_HELPERS = ROOT / "src/api/static/cc-helpers.js"


def test_today_router_contract_quant_cluster_hints():
    """/api/v7/today payload must include wired quant_cluster_hints (no full-app hang)."""
    src = DECISION_SRC.read_text(encoding="utf-8")
    assert '"quant_cluster_hints": quant_cluster_hints' in src
    assert "resolve_book_dd_utilization_for_hints" in src
    assert "dd_utilization_pct=resolve_book_dd_utilization_for_hints" in src


def test_wait_fixture_quant_cluster_hints_types():
    hints = build_quant_cluster_hints(tradeability="WAIT", best_net_score=5.0)
    types = {h.get("type") for h in hints}
    assert "cluster_watch" in types
    assert "cluster_near_miss" in types
    assert "cluster_blocked_cost" in types


def test_dd_utilization_omitted_when_fallback_stale():
    assert resolve_book_dd_utilization_for_hints(fallback_or_stale=True) is None


def test_quant_hints_blocked_dd_when_util_high():
    hints = build_quant_cluster_hints(
        tradeability="WAIT",
        best_net_score=5.0,
        dd_utilization_pct=90.0,
    )
    assert any(h.get("type") == "cluster_blocked_dd" for h in hints)


def test_monitor_near_miss_single_gap_copy():
    triggers = build_monitor_triggers(
        market_pulse={},
        near_miss=[
            {
                "ticker": "AMD",
                "upgrade_trigger": "Reclaim entry",
                "distance_to_pass": "timing +5pts",
                "gaps": ["timing"],
            }
        ],
        vix=18,
        breadth=55,
        tradeability="WAIT",
    )
    nm = [t for t in triggers if t["type"] == "near_miss"][0]
    assert "1 gate gap" in nm["detail"]
    assert "timing" in nm["detail"]
    assert nm.get("monitoring_only") is True


def test_playbook_e2e_selectors_present():
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert 'data-cc="playbook-cost-rank-pill"' in html
    assert 'data-cc="playbook-strategy-decay-line"' in html
    assert "playbookCostRankPill" in js
    assert "playbookStrategyDecayLine" in js
