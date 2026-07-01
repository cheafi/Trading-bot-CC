"""Dashboard compression — evidence conflict collapsed without valid candidate."""

from __future__ import annotations

from src.services.today_insights import build_evidence_conflict


def test_evidence_conflict_collapsed_without_candidate():
    panel = build_evidence_conflict(top5=[], near_miss=[], todays_decision={"deploy_label": "Wait"})
    assert panel["collapsed"] is True
    assert "No valid" in panel["headline"]


def test_evidence_conflict_open_with_candidate():
    panel = build_evidence_conflict(
        top5=[{"ticker": "SPY", "action": "WATCH", "why_now": ["Trend intact"]}],
        near_miss=[],
        todays_decision={"deploy_label": "Watch only"},
    )
    assert panel["collapsed"] is False
    assert panel["for"]
