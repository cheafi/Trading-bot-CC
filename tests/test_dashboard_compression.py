"""Dashboard compression — single default operator blocker summary."""

from __future__ import annotations

from pathlib import Path

from src.services.today_insights import build_evidence_conflict

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src" / "api" / "templates" / "index.html"


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


def test_dashboard_has_single_operator_block_summary():
    raw = INDEX.read_text(encoding="utf-8", errors="replace")
    assert raw.count('data-cc="operator-block-dashboard"') == 1
    assert "VALID CANDIDATES" in raw
    assert raw.count("Why not deploy?") >= 1
    assert 'x-show="today7.ai_narrative||today7.ai_loading"' not in raw

