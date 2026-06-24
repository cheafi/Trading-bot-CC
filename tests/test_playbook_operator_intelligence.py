"""Tests for Playbook operator intelligence enrichment."""

from __future__ import annotations

from src.services.playbook_operator_intelligence import (
    build_ai_vibe,
    build_auto_execution_stub,
    build_board_posture,
    build_monitor_auto_actions,
    build_operator_insight,
    build_paper_automation_stub,
    classify_monitor_state,
    enrich_playbook_payload,
)


def _sample_row(**overrides):
    base = {
        "ticker": "NVDA",
        "action": "WATCH",
        "score": 7.5,
        "thesis_conf": 0.7,
        "timing_conf": 0.45,
        "exec_conf": 0.2,
        "risk_reward": 2.8,
        "execution_ready": False,
        "leader": "LEADER",
        "rank_explain": ["Strong structure"],
    }
    base.update(overrides)
    return base


def test_operator_insight_strip_fields():
    row = _sample_row()
    from src.services.playbook_upgrade_ladder import enrich_row_ladder_fields

    row = enrich_row_ladder_fields(row)
    insight = build_operator_insight(row, board_wait=True)
    assert insight["now"]
    assert insight["blocker"]
    assert insight["upgrade"]
    assert insight["risk"]
    assert insight["next_check"]


def test_board_posture_selective_without_deploy():
    posture = build_board_posture(
        tradeability="SELECTIVE",
        deploy_count=0,
        pilot_count=2,
        board_wait=True,
    )
    assert posture["effective_posture"] == "SELECTIVE_MONITOR"
    assert "monitor only" in posture["copy_line"].lower()
    assert posture["deploy_open"] is False


def test_ai_vibe_never_grants_authority():
    vibe = build_ai_vibe(
        tradeability="WAIT",
        deploy_count=0,
        watch_count=5,
        opportunities=[_sample_row()],
    )
    assert vibe["monitor_only"] is True
    assert vibe["authority"] == "research_supporting"
    assert vibe["guidance"] == "wait"


def test_auto_execution_disabled_when_gates_closed():
    stub = build_auto_execution_stub(
        deploy_open=False,
        broker_ready=False,
        data_fresh=False,
        degraded=True,
    )
    assert stub["enabled"] is False
    assert stub["mode"] == "disabled"
    assert "kill_switch" in stub["modules"]


def test_paper_automation_is_paper_only():
    row = _sample_row()
    from src.services.playbook_upgrade_ladder import enrich_row_ladder_fields

    row = enrich_row_ladder_fields(row)
    paper = build_paper_automation_stub([row])
    assert paper["mode"] == "PAPER_ONLY"
    assert paper["live_disabled"] is True
    assert paper["queue"][0]["ticker"] == "NVDA"


def test_classify_monitor_state_avoid():
    assert classify_monitor_state({"action": "AVOID"}) == "avoid"


def test_monitor_auto_actions_paper_only():
    from src.services.playbook_upgrade_ladder import enrich_row_ladder_fields

    row = enrich_row_ladder_fields(_sample_row(timing_conf=0.72, thesis_conf=0.75))
    row["watch_intelligence"] = {
        "upgrade_probability": 0.7,
        "alert_worthy": True,
    }
    row["monitor_state"] = "watch"
    row["alert_trigger"] = "volume reclaim"
    actions = build_monitor_auto_actions([row])
    assert actions
    assert all(a["paper_only"] for a in actions)
    kinds = {a["action"] for a in actions}
    assert "auto_promote_watch" in kinds or "alert" in kinds


def test_enrich_playbook_payload_attaches_layers():
    payload = enrich_playbook_payload(
        {
            "opportunities": [_sample_row()],
            "near_miss": [],
            "best_action": {"tradeability": "WAIT", "pilot_count": 1},
            "filter_funnel": {"deploy_qualified_setups": 0, "watch_qualified_setups": 3},
        }
    )
    assert payload["operator_board"]
    assert payload["watch_queues"]
    assert payload["ai_vibe"]["monitor_only"] is True
    assert payload["board_posture"]["effective_posture"] == "WAIT"
    assert payload["opportunities"][0]["operator_insight"]
    assert payload["paper_automation"]["live_disabled"] is True
    assert payload["auto_execution"]["enabled"] is False
    assert "monitor_auto_actions" in payload
