"""Intelligence panels — learning empty states must never render blank."""

from __future__ import annotations

from pathlib import Path

from src.services.cc_live_policy import (
    INTELLIGENCE_EMPTY_LEARNING,
    INTELLIGENCE_EMPTY_NO_RESEARCH,
    INTELLIGENCE_EMPTY_NO_REVIEW,
    INTELLIGENCE_EMPTY_NO_THRESHOLD,
    ensure_intelligence_payload_blocks,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "src/api/templates/index.html").read_text(encoding="utf-8")
CC_HELPERS = (ROOT / "src/api/static/cc-helpers.js").read_text(encoding="utf-8")
TODAY_BUILDER = (ROOT / "src/services/today_payload_builder.py").read_text(encoding="utf-8")


def test_ensure_intelligence_blocks_merges_missing_payload():
    payload = ensure_intelligence_payload_blocks({"market_regime": {"label": "NEUTRAL"}})
    dq = payload["decision_quality"]
    oi = payload["opportunity_intelligence"]
    assert dq["banner"] == INTELLIGENCE_EMPTY_LEARNING
    assert dq["alpha_quality"]["empty_message"] == INTELLIGENCE_EMPTY_LEARNING
    assert dq["alpha_review"]["empty_message"] == INTELLIGENCE_EMPTY_NO_REVIEW
    assert dq["threshold_governance"]["empty_message"] == INTELLIGENCE_EMPTY_NO_THRESHOLD
    assert oi["empty_message"] == INTELLIGENCE_EMPTY_NO_RESEARCH


def test_ensure_intelligence_blocks_preserves_existing_counts():
    payload = ensure_intelligence_payload_blocks(
        {
            "decision_quality": {
                "banner": "Forward outcome study active",
                "metrics": {"learning_mode": False, "sample_size": 12},
                "alpha_quality": {"sample_size": 8, "status_label": "promising"},
                "alpha_review": {"next_actions": ["Run backfill"]},
                "threshold_governance": {"open_count": 2},
            },
            "opportunity_intelligence": {
                "counts": {"total": 3},
                "best_action": "review_dossier",
            },
        }
    )
    assert payload["decision_quality"]["banner"] == "Forward outcome study active"
    assert "empty_message" not in (payload["decision_quality"]["alpha_quality"] or {})
    assert payload["opportunity_intelligence"]["best_action"] == "review_dossier"


def test_today_builder_calls_ensure_intelligence():
    assert "ensure_intelligence_payload_blocks" in TODAY_BUILDER


def test_frontend_intelligence_fallback_wiring():
    for needle in (
        "ensureIntelligenceBlocks",
        "intelligenceEmptyMessage",
        "decision-quality-panel-fallback",
        INTELLIGENCE_EMPTY_LEARNING,
        INTELLIGENCE_EMPTY_NO_RESEARCH,
        INTELLIGENCE_EMPTY_NO_REVIEW,
        INTELLIGENCE_EMPTY_NO_THRESHOLD,
    ):
        assert needle in INDEX_HTML or needle in CC_HELPERS


def test_deploy_surfaces_engine_off_recovery_checkpoint():
    partial = (ROOT / "src/api/templates/cc/partials/deploy_surfaces.html").read_text(
        encoding="utf-8"
    )
    assert "engineOffRecoveryLine()" in partial
