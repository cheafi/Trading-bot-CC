"""Alpha review service — synthesize QA into advisory report."""

from __future__ import annotations

from src.services.alpha_review_service import (
    alpha_review_summary_for_dashboard,
    build_alpha_review,
)
from src.services.alpha_review_store import AlphaReviewStore
from src.services.human_review_queue import HumanReviewQueue


def _snap(status: str = "learning", n: int = 3, **extra):
    return {
        "snapshot_id": "s1",
        "status": status,
        "sample_size": n,
        "oi_lift_display": "learning",
        "cost_adj_expectancy_display": "learning",
        "overfit_risk": "high",
        "governor_qa": {"can_loosen_automatically": False, "authority_effect": "none"},
        **extra,
    }


def test_learning_mode_low_n():
    report = build_alpha_review(
        alpha_snapshots=[_snap(n=3)],
        alpha_quality_report=_snap(n=3),
        overfit={"overfit_risk": "high", "reason_codes": ["LOW_N"]},
        persist=False,
    )
    assert report["status"] == "learning"
    assert report["evidence_level"] == "learning"
    assert report["may_authorize_deploy"] is False
    assert report["authority_effect"] == "none"
    assert any("collect" in a.lower() for a in report["next_actions"])


def test_needs_human_review_when_flagged():
    report = build_alpha_review(
        alpha_snapshots=[_snap(n=15, status="deteriorating")],
        alpha_quality_report=_snap(
            n=15,
            status="deteriorating",
            cost_adj_expectancy_display="net +0.10R",
        ),
        overfit={"overfit_risk": "low", "allow_green_ui": True, "allow_validated_label": True},
        missed_opportunity={"human_review_suggested": True, "too_conservative_count": 4},
        governor_qa={"human_review_suggested": True, "qa_adjustment": "tighten_only"},
        persist=False,
    )
    assert report["status"] == "needs_human_review"
    assert report["human_review_count"] >= 1
    assert report["governor_review"]["can_loosen_automatically"] is False


def test_no_deploy_in_review_items():
    report = build_alpha_review(
        alpha_quality_report=_snap(n=20, cost_adj_expectancy_display="net +0.30R"),
        overfit={"overfit_risk": "low", "allow_green_ui": True, "allow_validated_label": True},
        persist=False,
    )
    for item in report["review_items"]:
        assert item.get("recommended_action") not in ("deploy", "auto_loosen")
        assert item.get("may_authorize_deploy") is False


def test_persist_and_dashboard_summary(tmp_path):
    store = AlphaReviewStore(
        reports_path=str(tmp_path / "reports.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    queue = HumanReviewQueue(tasks_path=str(tmp_path / "tasks.jsonl"))
    report = build_alpha_review(
        alpha_quality_report=_snap(n=6),
        missed_opportunity={"human_review_suggested": True},
        persist=True,
        store=store,
        human_queue=queue,
    )
    assert store.load_reports()
    summary = alpha_review_summary_for_dashboard(report)
    assert summary["collapsed"] is True
    assert summary["authority_effect"] == "none"
    assert "status" in summary
