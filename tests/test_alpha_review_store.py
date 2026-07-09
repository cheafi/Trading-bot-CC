"""Alpha review store — append-only reports."""

from __future__ import annotations

from src.services.alpha_review_store import (
    AlphaReviewReport,
    AlphaReviewStore,
    make_report_id,
)


def test_append_report(tmp_path):
    store = AlphaReviewStore(
        reports_path=str(tmp_path / "reports.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    report = AlphaReviewReport(
        report_id=make_report_id(),
        status="learning",
        evidence_level="learning",
        sample_size=4,
    )
    rid = store.append_report(report)
    assert rid == report.report_id
    rows = store.load_reports()
    assert len(rows) == 1
    assert rows[0]["may_authorize_deploy"] is False
    assert rows[0]["authority_effect"] == "none"
    assert rows[0]["collapsed"] is True


def test_supersede_creates_new_report(tmp_path):
    store = AlphaReviewStore(
        reports_path=str(tmp_path / "reports.jsonl"),
        index_path=str(tmp_path / "index.json"),
    )
    first = AlphaReviewReport(report_id=make_report_id(), status="learning")
    second = AlphaReviewReport(report_id=make_report_id(), status="improving")
    store.append_report(first)
    store.supersede_report(second, prior_report_id=first.report_id)
    rows = store.load_reports()
    assert len(rows) == 2
    assert rows[-1]["supersedes_id"] == first.report_id
    summary = store.summary()
    assert summary["latest_status"] == "improving"
    assert summary["may_authorize_deploy"] is False
