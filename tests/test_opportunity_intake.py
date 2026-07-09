"""Opportunity intake — normalize, dedupe, stage caps."""

from __future__ import annotations

from src.services.opportunity_intake import (
    build_dedupe_key,
    intake_batch,
    infer_stage_from_row,
    normalize_intake_row,
    persist_intake_batch,
)
from src.services.opportunity_intelligence_store import OpportunityIntelligenceStore


def _truth():
    return {"deploy_authority": False, "regime_state": "WAIT", "brief_expired": False}


def test_dedupe_key_stable():
    k1 = build_dedupe_key(
        ticker="AAPL",
        setup_tags=["breakout"],
        regime="WAIT",
        source_family="scanner",
        date_bucket="2026-07-09",
    )
    k2 = build_dedupe_key(
        ticker="AAPL",
        setup_tags=["breakout"],
        regime="WAIT",
        source_family="scanner",
        date_bucket="2026-07-09",
    )
    assert k1 == k2


def test_discovery_capped_at_research_hit():
    row = {"ticker": "MSFT", "action": "TRADE", "score": 8.0}
    cand = normalize_intake_row(row, surface="discovery", truth=_truth())
    assert cand.stage == "research_hit"


def test_playbook_stage_inference():
    row = {"ticker": "NVDA", "action": "WATCH", "primary_bucket": "watch"}
    assert infer_stage_from_row(row, surface="playbook") == "watch_candidate"


def test_intake_batch_dedupes(tmp_path):
    rows = [
        {"ticker": "AAPL", "scanner": "breakout", "score": 7},
        {"ticker": "AAPL", "scanner": "breakout", "score": 7.1},
    ]
    cands = intake_batch(truth=_truth(), discovery_hits=rows, session_id="20260709")
    assert len(cands) == 1


def test_persist_intake_no_duplicate_candidates(tmp_path):
    store = OpportunityIntelligenceStore(
        candidates_path=str(tmp_path / "candidates.jsonl"),
        snapshots_path=str(tmp_path / "snapshots.jsonl"),
        transitions_path=str(tmp_path / "transitions.jsonl"),
        use_index=False,
    )
    rows = [{"ticker": "TSLA", "scanner": "momentum", "score": 6.5}]
    cands = intake_batch(truth=_truth(), playbook_rows=rows, session_id="20260709")
    r1 = persist_intake_batch(cands, store=store)
    r2 = persist_intake_batch(cands, store=store)
    assert r1["persisted"] == 1
    assert r2["persisted"] == 1
    assert store.count_by_stage().get("playbook_review", 0) >= 1
