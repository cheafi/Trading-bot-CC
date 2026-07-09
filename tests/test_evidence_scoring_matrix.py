"""Evidence scoring matrix — 19 families, brief expired, AI cap."""

from __future__ import annotations

from src.services.evidence_scoring_matrix import (
    EVIDENCE_FAMILIES,
    score_evidence_matrix,
)


def test_nineteen_evidence_families():
    assert len(EVIDENCE_FAMILIES) == 19


def test_brief_expired_excludes_brief_families():
    row = {"ticker": "AAPL", "score": 8.0, "timing_conf": 0.8}
    truth = {"brief_expired": True, "brief_freshness": "expired"}
    result = score_evidence_matrix(row, truth=truth)
    assert "setup_quality" in result["excluded_families"]
    assert result["may_authorize_deploy"] is False


def test_ai_narrative_capped():
    row = {"ticker": "NVDA", "ai_hint": "strong narrative", "score": 7.0}
    result = score_evidence_matrix(row, truth={})
    ai = next(f for f in result["families"] if f["family"] == "ai_narrative")
    assert ai["score"] <= 0.15


def test_deploy_review_requires_freshness():
    row = {"ticker": "MSFT", "score": 7.5, "data_freshness_minutes": 600, "execution_ready": True}
    truth = {"brief_expired": True}
    result = score_evidence_matrix(row, truth=truth, stage="deploy_review")
    assert result["deploy_review_evidence_ready"] is False
