"""Discovery research funnel — label sanitation, caps, and authority contract."""

from __future__ import annotations

from src.services.authority_engine import primary_operator_state
from src.services.discovery_funnel import (
    build_discovery_funnel,
    build_discovery_verdict,
    build_research_shortlist,
    calibrate_discovery_score,
    collapse_broad_clusters,
    hide_uncalibrated_confidence,
    resolve_discovery_mode,
    sanitize_discovery_action_labels,
)
from src.services.operator_surface import build_operator_block
from src.services.system_truth import resolve_system_truth


def _research_truth() -> dict:
    return {
        "deploy_authority": False,
        "allows_trade_labels": False,
        "regime_state": "WAIT",
        "authority_level": "research",
    }


def test_research_only_no_actionable():
    out = sanitize_discovery_action_labels("actionable — open dossier", "research_only")
    assert "actionable" not in out.lower()


def test_negative_score_not_rendered_raw():
    cal = calibrate_discovery_score(-491.5)
    assert cal["raw_hidden"] is True
    assert "-491" not in str(cal["display"])
    assert "Excluded" in cal["display"]


def test_uncalibrated_no_percent_confidence():
    line = hide_uncalibrated_confidence(0.95, None)
    assert "%" not in line
    assert "heuristic" in line.lower()


def test_similar_pattern_over_100_collapsed_excluded():
    hits = [
        {"scanner": "similar_pattern", "ticker": f"T{i}", "score": 7.0}
        for i in range(150)
    ]
    collapsed = collapse_broad_clusters(hits, threshold=100)
    assert collapsed
    assert all(h.get("broad_cluster") for h in collapsed)
    assert all(h.get("excluded") for h in collapsed)


def test_strict_passed_zero_hides_raw_rows():
    hits = [
        {
            "scanner": "similar_pattern",
            "ticker": "X",
            "score": -491.5,
            "metadata": {"cluster_size": 3000},
        }
    ]
    funnel = build_discovery_funnel(hits, _research_truth())
    assert funnel["strict_passed_count"] == 0
    assert funnel["hide_raw_hits"] is True
    verdict = funnel["verdict"]
    assert verdict["hide_raw_hits"] is True


def test_raw_hit_cannot_create_monitor_rule():
    hits = [
        {"scanner": "vcp", "ticker": "BAD", "score": -491.5},
        {
            "scanner": "similar_pattern",
            "ticker": "CLU",
            "score": 7.0,
            "metadata": {"cluster_size": 500},
        },
    ]
    funnel = build_discovery_funnel(hits, _research_truth())
    for h in funnel["raw_hits"]:
        assert not h.get("monitor_rule_enabled")


def test_shortlist_max_10():
    hits = [
        {"scanner": "vcp", "ticker": f"N{i}", "score": 8.0 - i * 0.01}
        for i in range(25)
    ]
    collapsed = collapse_broad_clusters(hits)
    shortlist = build_research_shortlist(collapsed, max_items=10)
    assert len(shortlist) <= 10
    funnel = build_discovery_funnel(hits, _research_truth())
    assert len(funnel["review_shortlist"]) <= 10


def test_resolve_discovery_mode_research_only_when_blocked():
    assert resolve_discovery_mode(_research_truth()) == "research_only"
    assert (
        resolve_discovery_mode({"deploy_authority": True, "regime_state": "ACTIVE"})
        == "usable"
    )


def test_authority_tests_still_pass():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "SELECTIVE", "should_trade": True},
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 2, "setup_qualified": 3},
            "top_5": [{"ticker": "XLP", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": True},
    )
    posture = primary_operator_state(truth)
    assert posture["primary"] == "MONITOR ONLY"
    block = build_operator_block(truth, "dashboard")
    assert block["now"] == "MONITOR ONLY · Deploy blocked"
    assert block["blocked"] == "no sizing, no handoff, no pilot entry"


def test_verdict_default_sentence_when_zero_strict_passed():
    funnel = build_discovery_funnel([], _research_truth())
    verdict = build_discovery_verdict(funnel, _research_truth())
    assert "No validated research candidates" in verdict["default_sentence"]
