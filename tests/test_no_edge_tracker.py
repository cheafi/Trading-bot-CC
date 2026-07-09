"""No-edge tracker — learning until threshold, avoided loss, missed opportunity."""

from __future__ import annotations

from src.services.no_edge_tracker import (
    NoEdgeTracker,
    build_no_edge_outcome_tracking,
    classify_blockers,
    evaluate_call_quality,
)


def test_learning_until_threshold():
    assert evaluate_call_quality(sample_size=1) == "learning"
    assert evaluate_call_quality(sample_size=5) == "insufficient_data"


def test_avoided_loss_good_avoidance():
    quality = evaluate_call_quality(
        market_forward_returns={1: -2.0, 3: -3.0, 5: -4.0},
        top_rejected_forward_r=-1.2,
        sample_size=10,
        blocker_class="quality",
    )
    assert quality == "good_avoidance"


def test_missed_opportunity_too_conservative():
    quality = evaluate_call_quality(
        market_forward_returns={1: 3.0, 3: 4.0, 5: 5.0},
        top_rejected_forward_r=2.0,
        missed_opportunity=0.8,
        sample_size=10,
        blocker_class="quality",
    )
    assert quality == "too_conservative"


def test_infrastructure_vs_quality_blockers():
    infra = classify_blockers(
        reason_codes=["BROKER_OFFLINE"],
        primary_blocker="broker offline",
    )
    assert infra["blocker_class"] == "infrastructure"
    quality = classify_blockers(
        reason_codes=["NO_EDGE_TODAY", "REGIME_WAIT"],
        primary_blocker="regime wait",
    )
    assert quality["blocker_class"] == "quality"
    assert "REGIME_WAIT" in quality["quality_blockers"]


def test_persist_and_summarize(tmp_path):
    tracker = NoEdgeTracker(path=str(tmp_path / "no_edge.jsonl"))
    tracker.record(
        session_id="20260709",
        truth={
            "reason_codes": ["NO_EDGE_TODAY"],
            "primary_blocker": "no setups",
            "deploy_qualified_count": 0,
        },
        market_forward={1: -1.5, 3: -2.0, 5: -2.5},
    )
    summary = tracker.summarize()
    assert summary["no_edge_samples"] == 1
    assert summary["learning_mode"] is True


def test_build_no_edge_outcome_tracking_with_store(tmp_path):
    tracker = NoEdgeTracker(path=str(tmp_path / "no_edge.jsonl"))
    result = build_no_edge_outcome_tracking(
        truth={"deploy_qualified_count": 0, "reason_codes": ["NO_EDGE_TODAY"]},
        market_forward={5: -1.0},
        tracker=tracker,
        session_id="20260709",
        persist=True,
    )
    assert result["no_edge_day"] is True
    assert result["may_authorize_deploy"] is False
    assert result["authority_effect"] == "none"
