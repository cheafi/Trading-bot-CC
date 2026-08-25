from src.services.random_walk_guardrails import build_random_walk_guardrails


def test_random_walk_guardrails_returns_ui_shape():
    out = build_random_walk_guardrails(
        ticker="AAPL",
        dossier={"_partial": False},
        unified={"net_deploy_score": 5.1},
        timing={"extended": False, "timing_weak": False},
        confluence={"score": 42},
        portfolio_fit={"score": 61},
        options_block={"has_data": False},
        smart_money={"insider": "neutral"},
        confidence_metrics={"thesis_quality": 58, "timing_quality": 51, "rr_quality": 55},
        conf_display={"predictive_confidence": 52},
        layers={"identity": True, "fundamentals": True, "technicals": True, "options": False},
        module_errors={},
        narrative={"bull_case": ["x"]},
        peers_block={"rows": []},
        regime_ok=True,
    )

    assert isinstance(out["guardrail_labels"], list)
    assert out["evidence_strength"] in {"low", "medium", "high"}
    assert out["data_completeness"] in {"low", "medium", "high"}
    assert out["cost_adjusted_expected_edge"] == 5.1
    assert "summary" in out["market_efficiency_warning"]
    assert "summary" in out["bubble_crowding_risk"]
    assert "summary" in out["cost_realism"]
    assert "summary" in out["portfolio_necessity"]
    assert "summary" in out["operator_verdict"]
