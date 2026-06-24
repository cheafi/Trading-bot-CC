"""Playbook signal universe — brief normalization fixes empty monitor pool."""

from __future__ import annotations

from src.engines.sector_pipeline import SectorPipeline
from src.services.decision_truth_model import (
    _PipelineWrap,
    build_honest_funnel,
    refine_action,
)
from src.services.playbook_signal_universe import (
    load_brief_pipeline_signals,
    normalize_brief_row,
)


def _sample_brief_row() -> dict:
    return {
        "ticker": "AMD",
        "price": 408.46,
        "rs_score": 89.74,
        "atr_pct": 6.02,
        "vol_ratio": 1.0,
        "near_52w_high": True,
        "conviction": "LEADER",
        "entry": 408.46,
        "stop": 383.88,
        "target_2r": 457.62,
    }


def test_normalize_brief_row_maps_score_and_levels():
    sig = normalize_brief_row(_sample_brief_row())
    assert sig["ticker"] == "AMD"
    assert sig["score"] >= 8.0
    assert sig["entry_price"] == 408.46
    assert sig["stop_price"] == 383.88
    assert sig["target_price"] == 457.62
    assert float(sig["risk_reward"]) == 2.0


def test_raw_brief_without_normalize_scores_avoid():
    """Regression: raw brief rows must not enter pipeline unscored."""
    regime = {"should_trade": True, "trend": "SIDEWAYS", "vix": 18}
    raw = [_sample_brief_row()]
    results = SectorPipeline().process_batch(raw, regime)
    acts = {refine_action(_PipelineWrap(r)) for r in results}
    assert acts == {"AVOID"}


def test_normalized_brief_produces_watch_pool():
    regime = {"should_trade": True, "trend": "SIDEWAYS", "vix": 18}
    signals = load_brief_pipeline_signals(
        {
            "actionable": [_sample_brief_row()],
            "watch": [],
            "review": [],
        }
    )
    results = SectorPipeline().process_batch(signals, regime)
    funnel = build_honest_funnel(
        universe=len(signals),
        scanned=[{"score": r.fit.final_score} for r in results],
        council_results=[_PipelineWrap(r) for r in results],
    )
    assert funnel["watch_qualified_setups"] >= 1
    assert refine_action(_PipelineWrap(results[0])) == "WATCH"


def test_load_brief_pipeline_signals_dedupes_sections():
    row = _sample_brief_row()
    brief = {
        "actionable": [row],
        "watch": [{**row, "conviction": "WATCH"}],
        "review": [],
    }
    signals = load_brief_pipeline_signals(brief)
    assert len(signals) == 1
    assert signals[0]["brief_section"] == "actionable"
