"""Opportunity status panel — operator clarity when deploy/watch blocked."""

from __future__ import annotations

from src.services.opportunity_quality import build_opportunity_status
from src.services.system_truth import resolve_system_truth


def _blocked_truth(**extra):
    base = {
        "market_regime": {"tradeability": "WAIT", "should_trade": True},
        "trust": {"stale": True, "source": "decision_engine_degraded"},
        "decision_authority": {
            "authority_level": "research",
            "gates_active": True,
            "allows_trade_labels": False,
        },
        "execution_readiness": {"broker_connected": False},
        "qualification_levels": {"setup_qualified": 0, "deploy_qualified": 0},
        "top_5": [],
    }
    base.update(extra)
    return resolve_system_truth(base, cc_header={"data_tier": "STALE"}, ops_console={})


def test_opportunity_status_when_deploy_blocked_watch_zero_has_upgrade_triggers():
    truth = _blocked_truth()
    status = build_opportunity_status(truth, candidates=[], near_miss=[])
    assert status["edge_today"] == "None"
    assert len(status["upgrade_triggers"]) >= 1
    assert any("broker" in t.lower() or "board" in t.lower() for t in status["upgrade_triggers"])


def test_closest_candidates_surfaced_when_near_miss_exist():
    truth = _blocked_truth(
        qualification_levels={"setup_qualified": 2, "deploy_qualified": 0},
    )
    near_miss = [
        {
            "ticker": "KO",
            "action": "WATCH",
            "grade": "B+",
            "score": 7.2,
            "gaps": ["R:R"],
            "upgrade_trigger": "needs fresh board + R:R confirm",
            "whats_missing": "R:R",
        },
        {
            "ticker": "XLP",
            "action": "WATCH",
            "grade": "B",
            "score": 6.8,
            "gaps": ["timing", "R:R"],
            "upgrade_trigger": "Fix timing — reclaim entry on volume",
        },
    ]
    status = build_opportunity_status(truth, candidates=[], near_miss=near_miss)
    closest = status["closest_candidates"]
    assert len(closest) >= 1
    assert closest[0]["ticker"] == "KO"
    assert "upgrade_trigger" in closest[0]
    assert closest[0]["structure"]


def test_opportunity_status_watch_only_edge():
    truth = _blocked_truth(
        qualification_levels={"setup_qualified": 3, "deploy_qualified": 0},
        top_5=[{"ticker": "AAPL", "action": "WATCH", "grade": "B+", "score": 7.5}],
    )
    status = build_opportunity_status(
        truth,
        candidates=[{"ticker": "AAPL", "action": "WATCH", "grade": "B+", "score": 7.5}],
        near_miss=[],
    )
    assert status["edge_today"] == "Watch only"
    assert status["collapsed"] is False


def test_opportunity_status_collapsed_when_healthy():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "TRADE", "should_trade": True},
            "decision_authority": {
                "authority_level": "deploy",
                "gates_active": False,
                "allows_trade_labels": True,
            },
            "execution_readiness": {"broker_connected": True, "trade_handoff_ready": True},
            "qualification_levels": {"setup_qualified": 10, "deploy_qualified": 2},
            "execution_ready_count": 2,
            "top_5": [{"ticker": "NVDA", "action": "TRADE"}],
        },
        cc_header={"data_tier": "FRESH", "ibkr_ready": True},
        ops_console={"engine_running": True},
    )
    status = build_opportunity_status(
        truth,
        candidates=[{"ticker": "NVDA", "action": "TRADE"}],
    )
    assert status["edge_today"] == "Deploy ready"
    assert status["collapsed"] is True
