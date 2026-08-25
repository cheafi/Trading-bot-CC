"""Opportunity coverage — ETFs, indices, monitor pool expansion."""

from __future__ import annotations

import pytest

from src.core.stock_universe import (
    ALL_ETFS,
    INDEX_ETFS,
    OPPORTUNITY_COVERAGE_UNIVERSE,
    SECTOR_ETFS,
    asset_class_for,
    is_index_or_etf,
)
from src.engines.scanner_matrix import IndexETFTrendScanner
from src.engines.sector_classifier import SectorClassifier
from src.services.decision_truth_model import (
    _PipelineWrap,
    _brief_monitor_cap,
    refine_action,
)
from src.services.playbook_near_miss import (
    DISCOVERY_NEAR_MISS_STRIP_LIMIT,
    PLAYBOOK_NEAR_MISS_LIMIT,
    build_playbook_near_miss_rows,
)
from src.services.playbook_signal_universe import (
    PLAYBOOK_SIGNAL_TARGET,
    build_coverage_pad_signal,
    load_playbook_signals,
    pad_signals_with_coverage,
    resolve_rs_rank,
)


def test_coverage_universe_includes_indices_and_sectors():
    assert "SPY" in OPPORTUNITY_COVERAGE_UNIVERSE
    assert "QQQ" in OPPORTUNITY_COVERAGE_UNIVERSE
    assert "XLK" in OPPORTUNITY_COVERAGE_UNIVERSE
    assert "SOXX" in OPPORTUNITY_COVERAGE_UNIVERSE
    assert len(ALL_ETFS) >= len(INDEX_ETFS) + len(SECTOR_ETFS) // 2
    assert len(OPPORTUNITY_COVERAGE_UNIVERSE) >= 120


def test_asset_class_helpers():
    assert asset_class_for("SPY") == "index"
    assert asset_class_for("XLK") == "etf"
    assert asset_class_for("NVDA") == "equity"
    assert is_index_or_etf("QQQ") is True
    assert is_index_or_etf("AMD") is False


def test_resolve_rs_rank_from_composite():
    assert resolve_rs_rank({"rs_score": 89.7}) >= 85
    assert resolve_rs_rank({"rs_score": 7.2}) == 72


def test_coverage_pad_signal_is_monitor_only():
    sig = build_coverage_pad_signal("XLK")
    assert sig["ticker"] == "XLK"
    assert sig["source"] == "coverage_pad"
    assert sig["surface_authority"] == "monitor_only"
    assert sig["asset_class"] == "etf"


def test_pad_signals_with_coverage_fills_to_target():
    base = [build_coverage_pad_signal("SPY")]
    padded, count = pad_signals_with_coverage(base, target=5)
    assert len(padded) == 5
    assert count == 4
    assert len({s["ticker"] for s in padded}) == 5


def test_load_playbook_signals_applies_coverage_pad(monkeypatch):
    monkeypatch.setattr(
        "src.services.playbook_signal_universe.load_brief_pipeline_signals",
        lambda brief=None: [],
    )

    import asyncio

    signals, meta = asyncio.run(
        load_playbook_signals(scan_fn=None, target=10)
    )
    assert meta["coverage_pad_count"] >= 9
    assert len(signals) == 10
    assert all(s.get("source") == "coverage_pad" for s in signals)


def test_coverage_pad_capped_at_watch_like_brief():
    from types import SimpleNamespace

    wrap = SimpleNamespace(
        pipeline=SimpleNamespace(
            signal={"source": "coverage_pad"},
            fit=SimpleNamespace(final_score=8.5),
        )
    )
    assert _brief_monitor_cap(wrap, "TRADE") == "WATCH"
    assert _brief_monitor_cap(wrap, "PILOT") == "WATCH"


def test_sector_classifier_maps_sector_etf():
    ctx = SectorClassifier().classify("XLK", {"rs_rank": 72})
    assert ctx.benchmark_etf == "XLK"
    assert ctx.liquidity_quality == "deep"
    assert ctx.theme == "Sector/Tech"


def test_index_etf_trend_scanner_fires_for_sector_etf():
    scanner = IndexETFTrendScanner()
    hits = scanner.scan(
        [
            {
                "ticker": "SOXX",
                "rs_rank": 78,
                "vol_ratio": 1.3,
                "trend_structure": "uptrend",
            }
        ],
        {},
    )
    assert len(hits) == 1
    assert hits[0].metadata.get("rs_rank") == 78
    assert hits[0].metadata.get("research_only") is True


def test_near_miss_limit_expanded():
    assert PLAYBOOK_NEAR_MISS_LIMIT == 24
    assert DISCOVERY_NEAR_MISS_STRIP_LIMIT == 16


def test_near_miss_includes_etf_watch_at_lower_threshold():
    opps = [
        {
            "ticker": "XLK",
            "action": "WATCH",
            "score": 5.25,
            "asset_class": "etf",
            "execution_ready": False,
        },
        {
            "ticker": "LOW",
            "action": "WATCH",
            "score": 5.05,
            "execution_ready": False,
        },
    ]
    near = build_playbook_near_miss_rows(opps, limit=PLAYBOOK_NEAR_MISS_LIMIT)
    tickers = {r["ticker"] for r in near}
    assert "XLK" in tickers
    assert "LOW" not in tickers


def test_playbook_signal_target_increased():
    assert PLAYBOOK_SIGNAL_TARGET == 150
