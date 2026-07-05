"""Tests for decision honesty helpers (runner-up, day state, rank explain)."""

from src.services.decision_truth_model import (
    build_runner_up_comparison,
    build_trade_bar_status,
    row_passes_trade_bar,
)
from src.services.today_insights import _derive_day_state, build_no_setup_diagnosis, build_todays_decision, build_unlock_deploy


def test_runner_up_uses_fit_score_not_inverted():
    cur = {"ticker": "AAA", "score": 7.2, "thesis_conf": 0.7, "timing_conf": 0.5}
    nxt = {"ticker": "BBB", "score": 6.1, "thesis_conf": 0.6, "timing_conf": 0.55}
    cmp_row = build_runner_up_comparison(cur, nxt)
    assert cmp_row is not None
    assert "7.2" in cmp_row["reason"]
    assert "6.1" in cmp_row["reason"]
    assert cmp_row["fit_score"] == 6.1


def test_runner_up_skips_ties():
    cur = {"ticker": "AAA", "score": 6.5}
    nxt = {"ticker": "BBB", "score": 6.48}
    assert build_runner_up_comparison(cur, nxt) is None


def test_trade_bar_requires_execution_ready():
    row = {
        "score": 8.2,
        "thesis_conf": 0.7,
        "timing_conf": 0.7,
        "risk_reward": 3.0,
        "action": "TRADE",
        "execution_ready": False,
    }
    assert build_trade_bar_status(row)["passes_trade_bar"] is False
    row["execution_ready"] = True
    assert row_passes_trade_bar(row) is True


def test_day_state_pilot_watch_when_no_execution_ready():
    assert (
        _derive_day_state(
            tradeability="SELECTIVE",
            should_trade=True,
            execution_ready_count=0,
            has_pilot=True,
            has_watch=True,
        )
        == "PILOT_WATCH_DAY"
    )


def test_todays_decision_no_full_deploy_on_pilot_day():
    td = build_todays_decision(
        tradeability="SELECTIVE",
        should_trade=True,
        trend_label="UPTREND",
        decision_model={},
        best_action={},
        opportunities=[
            {
                "ticker": "X",
                "action": "PILOT",
                "score": 6.8,
                "execution_ready": False,
            }
        ],
        near_miss=[],
        no_setup_diagnosis=None,
        regime_wait_explanation=[],
        execution_readiness={},
        event_risks=[],
        execution_ready_count=0,
    )
    assert td["day_state"] == "PILOT_WATCH_DAY"
    assert td["can_deploy_today"] is False
    assert "WATCH/PILOT" in td["hero_label"]


def test_no_setup_diagnosis_blocker_tree_wait_day():
    diag = build_no_setup_diagnosis(
        [],
        scanner_degraded=False,
        tradeability="WAIT",
        should_trade=True,
        validated_count=0,
        deployable_count=0,
        execution_readiness={"broker_connected": False, "trade_handoff_ready": False},
    )
    assert diag["blocker_tree"]["regime"]["blocked"] is False
    assert diag["deployable_count"] == 0
    assert diag["primary_blocker"]


def test_effective_grade_matches_effective_action_on_wait():
    from src.services.decision_truth_model import apply_authority_to_row, build_decision_authority

    authority = build_decision_authority(tradeability="WAIT", should_trade=False)
    row = apply_authority_to_row(
        {"action": "TRADE", "raw_action": "TRADE", "risk_reward": 3.0},
        authority,
    )
    assert row["effective_grade"] == row["effective_action"]


def test_unlock_deploy_locked_on_wait():
    unlock = build_unlock_deploy(
        tradeability="WAIT",
        should_trade=True,
        watch_qualified_count=0,
        deployable_count=0,
        scanner_degraded=False,
        execution_readiness={"trade_handoff_ready": False, "unified_label": "BROKER OFFLINE"},
    )
    assert unlock["unlocked"] is False
    assert any(c["key"] == "regime" and not c["met"] for c in unlock["conditions"])
    board = next(c for c in unlock["conditions"] if c["key"] == "board")
    assert board["detail"] == "0 watch-qualified"
    assert "validated" not in board["detail"]
