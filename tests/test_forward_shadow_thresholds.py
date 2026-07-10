"""Forward shadow thresholds — parallel analytics tracking."""

from __future__ import annotations

from src.services.forward_shadow_thresholds import (
    ForwardShadowTracker,
    batch_forward_shadow,
    forward_shadow_summary,
    run_forward_shadow,
)


def _rows():
    return [
        {"composite_score": 80, "risk_reward": 3.0},
        {"composite_score": 70, "risk_reward": 2.0},
        {"composite_score": 74, "risk_reward": 2.6},
    ]


def test_run_forward_shadow_no_live_change(tmp_path):
    tracker = ForwardShadowTracker(runs_path=str(tmp_path / "shadow_runs.jsonl"))
    proposal = {
        "proposal_id": "tprop_fsh",
        "threshold_key": "playbook.deploy_score_min",
        "proposal_type": "tighten",
        "current_value": 72.0,
        "proposed_value": 76.0,
        "status": "approved_shadow",
    }
    result = run_forward_shadow(
        proposal,
        forward_rows=_rows(),
        persist=True,
        tracker=tracker,
    )
    assert result["ok"] is True
    assert result["no_live_changes"] is True
    assert result["may_authorize_deploy"] is False
    snap = result["snapshot"]
    assert snap["divergence_count"] >= 0
    assert tracker.latest_for_proposal("tprop_fsh") is not None


def test_batch_forward_shadow(tmp_path):
    tracker = ForwardShadowTracker(runs_path=str(tmp_path / "shadow_runs.jsonl"))
    proposals = [
        {
            "proposal_id": "p1",
            "threshold_key": "playbook.deploy_score_min",
            "proposed_value": 76.0,
            "status": "open",
        }
    ]
    batch = batch_forward_shadow(proposals, forward_rows=_rows(), persist=False)
    assert batch["count"] == 1
    assert batch["no_live_changes"] is True


def test_forward_shadow_summary(tmp_path):
    tracker = ForwardShadowTracker(runs_path=str(tmp_path / "shadow_runs.jsonl"))
    run_forward_shadow(
        {
            "proposal_id": "p_sum",
            "threshold_key": "playbook.deploy_score_min",
            "proposed_value": 76.0,
            "status": "open",
        },
        forward_rows=_rows(),
        persist=True,
        tracker=tracker,
    )
    summary = forward_shadow_summary(tracker=tracker)
    assert summary["total_runs"] == 1
    assert summary["collapsed"] is True
    assert summary["may_authorize_deploy"] is False
