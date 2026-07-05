"""Operator surface blocks — dashboard NOW/WHY/ALLOWED/BLOCKED/NEXT."""

from __future__ import annotations

from src.services.operator_surface import build_operator_block
from src.services.system_truth import resolve_system_truth


def test_research_surface_block_fields():
    from src.services.operator_surface import build_research_surface_block

    block = build_research_surface_block(
        {"deploy_authority": False, "primary_blocker": "Board WAIT"},
        surface="discovery",
    )
    for key in ("now", "blocker", "next", "research_only"):
        assert key in block
    assert block["research_only"] is True
    assert "Playbook" in block["next"]


def test_research_surface_shadow_surface():
    from src.services.operator_surface import build_research_surface_block

    block = build_research_surface_block(
        {"deploy_authority": False, "primary_blocker": "Board WAIT"},
        surface="shadow",
    )
    assert block["surface"] == "shadow"
    assert "capital" in block["next"].lower() or "promoted" in block["next"].lower()
    assert block["research_only"] is True


def test_research_surface_strategy_details_collapsed_flag():
    from src.services.operator_surface import build_research_surface_block

    block = build_research_surface_block(surface="strategy")
    assert block.get("details_collapsed") is True


def test_dashboard_operator_block_fields():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "trust": {"stale": True, "source": "decision_engine_degraded"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"setup_qualified": 2, "deploy_qualified": 0},
            "top_5": [{"ticker": "XLP", "action": "WATCH"}],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={},
        brief_age_days=23,
    )
    block = build_operator_block(truth, "dashboard")
    for key in ("now", "why", "allowed", "blocked", "valid_candidates", "next"):
        assert key in block
    assert block["now"] == "MONITOR ONLY · Deploy blocked"
    assert "monitor candidates" in block["allowed"]
    assert "no pilot entry" in block["blocked"]
    assert "Deploy-qualified: 0" in block["valid_candidates"] or "Deploy 0" in block["valid_candidates"]
