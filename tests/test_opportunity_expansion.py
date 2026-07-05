"""Opportunity expansion — options, grade calibration, universe caps, ranker."""

from __future__ import annotations

import os

from src.engines.scanner_matrix import (
    DISCOVERY_QUALIFIED_WATCH_CAP_EXPANDED,
    DISCOVERY_SHORTLIST_CAP_EXPANDED,
    ScannerMatrix,
    resolve_discovery_funnel_caps,
)
from src.services.opportunity_quality import (
    ai_opportunity_brief,
    build_grade_calibration,
    build_opportunity_status,
    rank_opportunities,
)
from src.services.options_availability import assess_options_availability, batch_options_availability
from src.services.system_truth import resolve_system_truth


def test_options_signal_research_only_when_deploy_blocked():
    sig = assess_options_availability(
        "AAPL",
        {"action": "WATCH", "options_meta": {"liquidity_score": 0.8, "iv_rank": 45}},
        deploy_blocked=True,
    )
    assert sig["options_liquid"] == "liquid"
    assert sig["research_only"] is True
    assert "research" in sig["display"].lower() or "僅研究" in sig["display_zh"]
    assert "buy" not in sig["display"].lower()


def test_options_batch_no_buy_now_copy():
    rows = batch_options_availability(
        [{"ticker": "MSFT", "options_meta": {"liquidity_score": 0.7, "iv_rank": 50}}],
        deploy_blocked=True,
    )
    assert len(rows) == 1
    assert "now" not in rows[0]["display"].lower()


def test_expanded_universe_only_when_env_and_fresh_board(monkeypatch):
    monkeypatch.setenv("CC_SCAN_UNIVERSE_MODE", "expanded")
    fresh = resolve_discovery_funnel_caps(ranked_board_fresh=True)
    stale = resolve_discovery_funnel_caps(ranked_board_fresh=False)
    assert fresh["shortlist"] == DISCOVERY_SHORTLIST_CAP_EXPANDED
    assert fresh["qualified_watch"] == DISCOVERY_QUALIFIED_WATCH_CAP_EXPANDED
    assert stale["shortlist"] == 30
    monkeypatch.delenv("CC_SCAN_UNIVERSE_MODE", raising=False)


def test_merged_discovery_uses_expanded_caps(monkeypatch):
    monkeypatch.setenv("CC_SCAN_UNIVERSE_MODE", "expanded")
    matrix = ScannerMatrix()
    grouped = {
        "PATTERN": {
            "vcp": {
                "count": 60,
                "top_hits": [
                    {
                        "ticker": f"N{i}",
                        "score": 8.0,
                        "strength": 8.0,
                        "scanner": "vcp",
                        "headline": "VCP",
                    }
                    for i in range(60)
                ],
            }
        }
    }
    out = matrix.build_merged_discovery_rank(
        grouped, {"PATTERN": {"count": 60}}, {"label": "UPTREND"}, universe_size=500
    )
    assert out["funnel_caps"]["shortlist"] == DISCOVERY_SHORTLIST_CAP_EXPANDED
    assert len(out["merged_top_names"]) <= DISCOVERY_SHORTLIST_CAP_EXPANDED
    monkeypatch.delenv("CC_SCAN_UNIVERSE_MODE", raising=False)


def test_grade_calibration_heuristic_when_uncalibrated():
    cal = build_grade_calibration(
        [{"ticker": "KO", "setup_evidence": {"sample_size": 0, "data_quality_pct": 42}}],
        {"regime_state": "WAIT"},
    )
    assert cal["heuristic_only"] is True
    assert "Heuristic" in cal["heuristic_banner"] or "啟發" in cal["heuristic_banner_zh"]


def test_rank_opportunities_returns_closest_near_miss():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"setup_qualified": 2},
            "top_5": [{"ticker": "KO", "action": "WATCH", "score": 7.2, "risk_reward": 2.1}],
        },
        cc_header={"data_tier": "FRESH"},
    )
    ranked = rank_opportunities(
        [
            {"ticker": "KO", "score": 7.2, "risk_reward": 2.1, "action": "WATCH"},
            {"ticker": "XLP", "score": 6.5, "risk_reward": 1.5, "action": "WATCH"},
        ],
        truth,
    )
    assert ranked[0]["ticker"] == "KO"
    assert ranked[0]["research_score"] > ranked[1]["research_score"]


def test_opportunity_status_includes_pilot_watch_and_diagnosis():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"setup_qualified": 1},
            "top_5": [{"ticker": "KO", "action": "WATCH", "grade": "B+", "score": 7.2}],
        },
        cc_header={"data_tier": "FRESH"},
    )
    status = build_opportunity_status(
        truth,
        candidates=[{"ticker": "KO", "grade": "B+", "score": 7.2, "risk_reward": 2.2, "action": "WATCH"}],
        near_miss=[
            {
                "ticker": "KO",
                "grade": "B+",
                "score": 7.2,
                "risk_reward": 2.2,
                "action": "WATCH",
                "gaps": ["execution"],
                "upgrade_trigger": "needs execution_ready",
            }
        ],
        sector_leaders=[{"sector": "XLP", "ticker": "KO", "label": "Staples lead"}],
    )
    assert status["deploy_blocker_diagnosis"]["category"] in ("infra", "mixed", "threshold_or_regime")
    assert status["grade_calibration"]["title_zh"] == "評分說明"
    assert "僅監察" in status["monitor_only_guide_zh"]
    assert len(status["ai_opportunity_brief"]) >= 1
    closest = status["closest_candidates"]
    assert closest and closest[0]["ticker"] == "KO"


def test_deploy_still_blocked_when_broker_offline():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 2},
            "execution_ready_count": 2,
            "top_5": [{"ticker": "NVDA", "action": "TRADE"}],
        },
        cc_header={"data_tier": "FRESH"},
    )
    assert truth["deploy_authority"] is False
    assert "BROKER_OFFLINE" in truth["reason_codes"]
