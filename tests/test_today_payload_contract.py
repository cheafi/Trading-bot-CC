"""Today / opportunities payload contracts — lock scope, authority wiring, CC OS."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION_SRC = (ROOT / "src/api/routers/decision.py").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "src/api/templates/index.html").read_text(encoding="utf-8")
CC_HELPERS = (ROOT / "src/api/static/cc-helpers.js").read_text(encoding="utf-8")
RANKED_PIPELINE = (ROOT / "src/services/ranked_board_pipeline.py").read_text(encoding="utf-8")
TODAY_BUILDER = (ROOT / "src/services/today_payload_builder.py").read_text(encoding="utf-8")


def test_today_build_runs_inside_lock():
    """Full today build must be serialized — not only cache re-check."""
    lock_idx = DECISION_SRC.find("async with _today_lock:")
    assert lock_idx >= 0
    delegate_idx = DECISION_SRC.find("build_today_payload", lock_idx)
    assert delegate_idx > lock_idx
    # Circuit breaker fix must use shared helper in builder, not bool(breaker)
    assert "circuit_breaker_tripped" in TODAY_BUILDER
    assert 'exec_blocked = bool(getattr(engine, "circuit_breaker"' not in TODAY_BUILDER


def test_opportunities_scanner_degraded_not_hardcoded_false():
    """Opportunities must propagate empty-scan degradation into authority."""
    opp_start = DECISION_SRC.find('@router.get("/api/v7/opportunities")')
    assert opp_start >= 0
    opp_block = DECISION_SRC[opp_start : opp_start + 6000]
    assert "scanner_degraded_from_scan" in opp_block
    assert "scanner_degraded=False" not in opp_block


def test_today_uses_ranked_board_pipeline_helpers():
    today_block = TODAY_BUILDER
    for needle in (
        "gather_today_side_context",
        "enrich_today_rows_post_regime",
        "apply_today_opportunity_quality",
    ):
        assert needle in today_block, f"missing {needle}"


def test_opportunities_uses_ranked_board_pipeline():
    opp_start = DECISION_SRC.find('@router.get("/api/v7/opportunities")')
    opp_block = DECISION_SRC[opp_start : opp_start + 8000]
    assert "enrich_ranked_board_rows" in opp_block
    assert "authority_first=False" in opp_block


def test_ranked_board_pipeline_module_exists():
    assert "def enrich_ranked_board_rows" in RANKED_PIPELINE
    assert "def tradeability_from_funnel" in RANKED_PIPELINE


def test_today_payload_builder_module_exists():
    assert "async def gather_today_side_context" in TODAY_BUILDER
    assert "def enrich_today_rows_post_regime" in TODAY_BUILDER
    assert "async def build_today_payload" in TODAY_BUILDER


def test_today_summary_delegates_to_builder():
    """today_summary handler stays thin — orchestration lives in builder."""
    today_start = DECISION_SRC.find("async def today_summary")
    today_end = DECISION_SRC.find('@router.get("/api/v7/opportunities")')
    today_block = DECISION_SRC[today_start:today_end]
    assert "build_today_payload" in today_block
    assert "await build_today_payload(request)" in today_block
    assert "build_cc_operating_system_context" not in today_block
    assert "build_tracker_wave_context" not in today_block
    lock_idx = today_block.find("async with _today_lock:")
    delegate_idx = today_block.find("build_today_payload")
    assert lock_idx >= 0 and delegate_idx > lock_idx


def test_cc_os_details_collapsed_on_wait():
    assert 'data-cc="tracker-wave-strip"' in INDEX_HTML
    assert ':open="!isWaitDay()"' in INDEX_HTML


def test_fetch_scanners_uses_cc_fetch_json():
    start = INDEX_HTML.find("async fetchScanners(cat)")
    end = INDEX_HTML.find("tabAuthorityAlias(t){")
    assert start >= 0 and end > start
    block = INDEX_HTML[start:end]
    assert "ccFetchJson" in block
    assert "await fetch(u)" not in block


def test_fetch_command_board_uses_cc_fetch_json():
    start = INDEX_HTML.find("async fetchCommandBoard")
    end = INDEX_HTML.find("async fetchDecision(ticker)")
    assert start >= 0 and end > start
    block = INDEX_HTML[start:end]
    assert "ccFetchJson" in block
    assert "await fetch(" not in block


def test_today_payload_includes_cc_os_and_authority_keys():
    for needle in (
        '"cc_os": cc_os',
        "build_cc_operating_system_context",
        "positions=pf_holdings",
        "build_decision_authority",
        '"decision_authority"',
        '"trust"',
    ):
        assert needle in TODAY_BUILDER, f"missing {needle}"


def test_fetch_ranked_uses_cc_fetch_json():
    assert "async fetchRanked" in INDEX_HTML
    ranked_block = INDEX_HTML[INDEX_HTML.find("async fetchRanked") : INDEX_HTML.find("applyRankedPayload")]
    assert "ccFetchJson" in ranked_block
    assert "fetch(u)" not in ranked_block


def test_operator_detail_sanitized():
    assert "sanitizeOperatorDetail" in CC_HELPERS
    assert "sanitizeOperatorDetail" in INDEX_HTML or "CCHelpers.sanitizeOperatorDetail" in INDEX_HTML


def test_fund_manager_research_only_badge():
    assert "RESEARCH ONLY" in INDEX_HTML
    assert "Fund research context" in INDEX_HTML
    assert "NOT DEPLOY AUTHORITY" in INDEX_HTML


def test_today_skips_inline_fund_lab_preload():
    """Today must not block on fund-lab build — lazy-load via Funds tab."""
    assert "_build_payload" not in TODAY_BUILDER
