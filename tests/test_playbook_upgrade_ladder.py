"""Tests for Playbook upgrade ladder enrichment."""

from __future__ import annotations

from src.services.playbook_upgrade_ladder import (
    classify_ladder_bucket,
    compute_upgrade_gaps,
    enrich_row_ladder_fields,
    operator_action_line,
    upgrade_proximity_score,
)


def test_classify_deploy_ready_row():
    row = {
        "action": "TRADE",
        "execution_ready": True,
        "thesis_conf": 0.7,
        "timing_conf": 0.7,
        "risk_reward": 3.0,
        "score": 8.5,
        "trade_bar": {
            "passes_trade_bar": True,
            "score_ok": True,
            "thesis_ok": True,
            "timing_ok": True,
            "rr_ok": True,
            "execution_ready": True,
        },
    }
    assert classify_ladder_bucket(row) == "deploy_ready"


def test_classify_hard_reject():
    row = {"action": "AVOID", "thesis_conf": 0.3}
    assert classify_ladder_bucket(row) == "hard_reject"


def test_upgrade_gaps_show_distance():
    row = {
        "thesis_conf": 0.55,
        "timing_conf": 0.45,
        "exec_conf": 0.2,
        "data_conf": 0.25,
        "risk_reward": 2.0,
        "execution_ready": False,
    }
    gaps = compute_upgrade_gaps(row)
    assert gaps["thesis"].startswith("+")
    assert gaps["timing"].startswith("+")
    assert gaps["exec"] == "blocked"
    assert gaps["rr"].startswith("+")


def test_proximity_lower_when_closer_to_gate():
    near = {"thesis_conf": 0.64, "timing_conf": 0.64, "exec_conf": 0.5, "risk_reward": 2.4, "execution_ready": True}
    far = {"thesis_conf": 0.4, "timing_conf": 0.3, "exec_conf": 0.1, "risk_reward": 1.5, "execution_ready": False}
    assert upgrade_proximity_score(near) < upgrade_proximity_score(far)


def test_enrich_row_adds_operator_fields():
    row = enrich_row_ladder_fields(
        {
            "ticker": "TEST",
            "action": "WATCH",
            "thesis_conf": 0.7,
            "timing_conf": 0.4,
            "exec_conf": 0.2,
            "stop_price": 95.0,
            "rank_explain": ["Strong thesis (70%)"],
        }
    )
    assert row["ladder_bucket"] == "watch_upgrade"
    assert row["operator_action"]
    assert row["holder_guidance"]
    assert row["alert_trigger"]
    assert row["why_here"] == "Strong thesis (70%)"


def test_operator_action_exec_blocked():
    row = enrich_row_ladder_fields(
        {"action": "WATCH", "exec_conf": 0.1, "execution_ready": False, "thesis_conf": 0.7, "timing_conf": 0.7}
    )
    assert "reclaim" in operator_action_line(row).lower() or "breakout" in operator_action_line(row).lower()
