"""Today quant_cluster_hints wiring — contract, WAIT fixture, monitor copy."""

from __future__ import annotations

from pathlib import Path

from src.services.today_insights import (
    _dd_pct_from_underwater_curve,
    build_monitor_triggers,
    build_opportunity_recheck_heuristic,
    build_quant_cluster_hints,
    detect_monitor_upgrade_gap_alerts,
    format_monitor_upgrade_gap_alert,
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
    assert "load_equity_dd_pct_for_hints" in src
    assert "equity_dd_pct=equity_dd_pct" in src


def test_wait_fixture_quant_cluster_hints_types():
    hints = build_quant_cluster_hints(tradeability="WAIT", best_net_score=5.0)
    types = {h.get("type") for h in hints}
    assert "cluster_watch" in types
    assert "cluster_near_miss" in types
    assert "cluster_blocked_cost" in types


def test_dd_utilization_omitted_when_fallback_stale():
    assert resolve_book_dd_utilization_for_hints(fallback_or_stale=True) is None
    assert (
        resolve_book_dd_utilization_for_hints(
            fallback_or_stale=True,
            equity_dd_pct=12.0,
        )
        is None
    )


def test_dd_pct_from_underwater_curve_omits_at_peak():
    assert _dd_pct_from_underwater_curve([-4.0, -3.2, -2.1]) == 2.1
    assert _dd_pct_from_underwater_curve([0.0, 0.5]) is None
    assert _dd_pct_from_underwater_curve([]) is None


def test_dd_utilization_equity_fallback_when_heat_empty(monkeypatch):
    class _Snap:
        max_drawdown_pct = 0

    class _Engine:
        def snapshot(self):
            return _Snap()

    monkeypatch.setattr(
        "src.engines.portfolio_heat.get_portfolio_heat_engine",
        lambda: _Engine(),
    )
    util = resolve_book_dd_utilization_for_hints(equity_dd_pct=7.5)
    assert util is not None
    assert util > 0


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
    assert 'data-cc="regime-stack-strip"' in html
    assert 'data-cc="ai-reason-codes"' in html
    assert 'data-cc="exec-analytics-sample"' in html
    assert "playbookCostRankPill" in js
    assert "playbookStrategyDecayLine" in js
    assert "regimeStackStrip" in js
    assert "aiReasonCodes" in js
    assert "execAnalyticsSample" in js


def test_opportunities_router_enrich_parity():
    """Ranked /api/v7/opportunities uses same enrich stack as Today/Playbook."""
    src = DECISION_SRC.read_text(encoding="utf-8")
    start = src.index("async def ranked_opportunities(")
    assert start > 0
    end = src.index("\n\n# ═", start)
    block = src[start:end]
    assert "enrich_opportunity_row" in block
    assert "enrich_opportunity_rows" in block
    assert "attach_row_ai_hints" in block
    assert "may_authorize_deploy" in block
    assert block.index("may_authorize_deploy") > block.index("attach_row_ai_hints")


def test_monitor_upgrade_alert_gap_drop():
    prior = [{"ticker": "AMD", "gaps": ["timing", "thesis"]}]
    current = [{"ticker": "AMD", "gaps": ["timing"], "upgrade_trigger": "Reclaim"}]
    alerts = detect_monitor_upgrade_gap_alerts(current, prior_near_miss=prior)
    assert alerts
    assert alerts[0]["type"] == "monitor_upgrade_alert"
    assert "dropped" in alerts[0]["detail"]
    assert alerts[0].get("monitoring_only") is True


def test_monitor_upgrade_alert_single_gap_trigger():
    triggers = build_monitor_triggers(
        market_pulse={},
        near_miss=[{"ticker": "NVDA", "gaps": ["timing"], "upgrade_trigger": "Vol"}],
        vix=18,
        breadth=55,
        tradeability="WAIT",
    )
    upgrade = [t for t in triggers if t["type"] == "monitor_upgrade_alert"]
    assert upgrade
    assert "single gate gap" in upgrade[0]["detail"]


def test_opportunity_recheck_heuristic_monitor_only():
    hints = build_opportunity_recheck_heuristic(
        near_miss=[{"ticker": "AAPL", "gaps": ["timing", "R:R"]}],
        prior_near_miss=[{"ticker": "AAPL", "gaps": ["timing", "R:R"]}],
    )
    assert hints
    assert hints[0]["may_authorize_deploy"] is False
    assert "recycle" in hints[0]["hint"].lower()


def test_today_router_execution_analytics_wired():
    src = DECISION_SRC.read_text(encoding="utf-8")
    assert '"execution_analytics": execution_analytics' in src
    assert "build_empty_execution_analytics_state" in src
