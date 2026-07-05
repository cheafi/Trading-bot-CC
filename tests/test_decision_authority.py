"""Decision authority gating — page gates vs card labels."""

from src.services.decision_truth_model import (
    apply_authority_to_row,
    assemble_confidence_breakdown,
    build_decision_authority,
    effective_card_action,
    resolve_active_data_source,
)


def test_confidence_null_when_all_components_zero():
    row = {"thesis_conf": 0, "timing_conf": 0, "exec_conf": 0, "data_conf": 0}
    conf = assemble_confidence_breakdown(row)
    assert conf["final"] is None
    assert conf["unavailable"] is True


def test_confidence_not_fake_sixty_on_fallback():
    row = {
        "thesis_conf": 0,
        "timing_conf": 0,
        "exec_conf": 0,
        "data_conf": 0,
        "confidence_fallback_only": True,
        "evidence_badge": "brief-fallback",
    }
    out = apply_authority_to_row(row, build_decision_authority(fallback_brief=True))
    assert out["final_conf"] is None
    assert out["confidence_fallback_only"] is True


def test_trade_downgraded_under_wait_gate():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=True,
        scanner_degraded=True,
    )
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "execution_ready": False,
            "risk_reward": 3.0,
            "thesis_conf": 0.8,
            "timing_conf": 0.7,
            "exec_conf": 0.6,
            "data_conf": 0.6,
        },
        authority,
    )
    assert row["action"] != "TRADE"
    assert row["action"] in ("WATCH ONLY", "RESEARCH ONLY", "NOT EXECUTION-GRADE")


def test_fallback_brief_label():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=False,
        fallback_brief=True,
    )
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "risk_reward": 2.8,
            "thesis_conf": 0.7,
            "timing_conf": 0.7,
            "exec_conf": 0.6,
            "data_conf": 0.6,
        },
        authority,
    )
    assert row["action"] == "FALLBACK WATCH"


def test_rr_missing_blocks_trade_label():
    authority = build_decision_authority(
        tradeability="TRADE",
        should_trade=True,
    )
    authority["allows_trade_labels"] = True
    authority["gates_active"] = False
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "execution_ready": True,
            "risk_reward": None,
            "thesis_conf": 0.8,
            "timing_conf": 0.7,
            "exec_conf": 0.6,
            "data_conf": 0.6,
        },
        authority,
    )
    assert effective_card_action(row, authority) == "INCOMPLETE"


def test_resolve_active_data_source_priority():
    assert (
        resolve_active_data_source(fallback_brief=True, trust_source="live")
        == "fallback_brief"
    )
    assert (
        resolve_active_data_source(stale=True, ranked_source="disk-snapshot")
        == "stale_cache"
    )
    assert resolve_active_data_source(trust_source="decision_engine") == "live"


def test_data_source_mismatch_flag():
    authority = build_decision_authority(
        council_count=5,
        live_council_count=12,
        deploy_ideas_count=0,
        live_deploy_count=2,
    )
    assert authority["data_source_mismatch"] is True
    assert "Council count" in authority["data_source_mismatch_detail"]
