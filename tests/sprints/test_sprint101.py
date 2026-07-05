"""
Sprint 101 — Canonical Decision Object Schema
===============================================
Tests:
  1. DecisionObject has all 7 new fields with correct defaults
  2. from_pipeline_result() produces a populated DecisionObject
  3. to_dict() includes all new fields
  4. trust_level stamped correctly for synthetic vs live
  5. JournalEntry.from_decision_object() factory creates valid entry
  6. JournalEntry factors dict contains enrichment fields
  7. gate_allowed reflects portfolio_fit
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_mock_result(ticker: str = "NVDA", synthetic: bool = False) -> MagicMock:
    """Build a minimal mock PipelineResult."""
    r = MagicMock()
    r.signal = {
        "ticker": ticker,
        "strategy": "PULLBACK_TREND",
        "entry": 850.0,
        "stop": 820.0,
        "target": 920.0,
        "risk_reward": 2.3,
        "synthetic": synthetic,
        "mtf_confluence_score": 0.82,
        "execution_cost_bps": 4.5,
    }
    r.confidence.thesis = 0.78
    r.confidence.timing = 0.65
    r.confidence.execution = 0.70
    r.confidence.data = 0.85
    r.confidence.final = 0.74
    r.decision.action = "TRADE"
    r.fit.final_score = 8.5
    r.fit.grade = "A"
    r.sector.sector_bucket.value = "HIGH_GROWTH"
    r.sector.sector_stage.value = "EARLY_LEADER"
    r.sector.leader_status.value = "LEADER"
    r.explanation.why_now = "RS turning positive"
    r.explanation.why_not_stronger = "Macro uncertain"
    r.ranking = None
    return r


def _make_regime(synthetic: bool = False) -> dict:
    return {
        "trend": "BULL",
        "vix": 16.0,
        "should_trade": True,
        "synthetic": synthetic,
    }


# ── 1. New fields exist on DecisionObject ────────────────────────────────────


def test_decision_object_new_fields_defaults():
    from src.engines.decision_object import DecisionObject

    obj = DecisionObject(ticker="TEST")
    assert obj.signal_source == "brief"
    assert obj.trust_level == "UNVERIFIED"
    assert obj.data_freshness_minutes == -1
    assert obj.benchmark_compare == "—"
    assert obj.mtf_confluence_score is None
    assert obj.execution_cost_bps is None
    assert obj.calibrated_confidence is None


# ── 2. from_pipeline_result() produces populated object ──────────────────────


def test_from_pipeline_result_basic():
    from src.engines.decision_object import DecisionObject

    r = _make_mock_result("NVDA")
    regime = _make_regime()
    obj = DecisionObject.from_pipeline_result(r, regime)

    assert obj.ticker == "NVDA"
    assert obj.action == "TRADE"
    assert obj.strategy_style == "PULLBACK_TREND"
    assert obj.stop == 820.0
    assert obj.target == 920.0
    assert obj.rr_ratio == 2.3


# ── 3. to_dict() includes all new keys ───────────────────────────────────────


def test_to_dict_includes_new_fields():
    from src.engines.decision_object import DecisionObject

    r = _make_mock_result("NVDA")
    obj = DecisionObject.from_pipeline_result(r, _make_regime())
    d = obj.to_dict()

    for key in (
        "signal_source",
        "trust_level",
        "data_freshness_minutes",
        "benchmark_compare",
        "mtf_confluence_score",
        "execution_cost_bps",
        "calibrated_confidence",
    ):
        assert key in d, f"Missing key: {key}"


# ── 4. trust_level stamped correctly ─────────────────────────────────────────


def test_trust_level_live():
    from src.engines.decision_object import DecisionObject

    obj = DecisionObject.from_pipeline_result(
        _make_mock_result(synthetic=False), _make_regime(False)
    )
    assert obj.trust_level == "LIVE"


def test_trust_level_synthetic():
    from src.engines.decision_object import DecisionObject

    obj = DecisionObject.from_pipeline_result(
        _make_mock_result(synthetic=True), _make_regime(True)
    )
    assert obj.trust_level == "SYNTHETIC"


# ── 5. mtf_confluence_score propagated ───────────────────────────────────────


def test_mtf_confluence_propagated():
    from src.engines.decision_object import DecisionObject

    r = _make_mock_result()
    obj = DecisionObject.from_pipeline_result(r, _make_regime())
    assert obj.mtf_confluence_score == pytest.approx(0.82)


# ── 6. JournalEntry.from_decision_object() factory ───────────────────────────


def test_journal_from_decision_object_basic():
    from src.engines.decision_object import DecisionObject
    from src.engines.decision_journal import JournalEntry

    r = _make_mock_result("NVDA")
    obj = DecisionObject.from_pipeline_result(r, _make_regime())
    obj.portfolio_fit = "ALLOWED"

    entry = JournalEntry.from_decision_object(obj, price=855.0)
    assert entry.ticker == "NVDA"
    assert entry.decision == "TRADE"
    assert entry.price == 855.0
    assert entry.gate_allowed is True
    assert entry.entry_id.startswith("DJ-")


# ── 7. JournalEntry factors contains enrichment ──────────────────────────────


def test_journal_factors_enrichment():
    from src.engines.decision_object import DecisionObject
    from src.engines.decision_journal import JournalEntry

    r = _make_mock_result("NVDA")
    obj = DecisionObject.from_pipeline_result(r, _make_regime())
    obj.execution_cost_bps = 4.5
    obj.mtf_confluence_score = 0.82

    entry = JournalEntry.from_decision_object(obj, price=855.0)
    assert entry.factors["mtf_confluence_score"] == pytest.approx(0.82)
    assert entry.factors["execution_cost_bps"] == pytest.approx(4.5)
    assert entry.factors["trust_level"] == "LIVE"
    assert entry.factors["signal_source"] == "brief"


# ── 8. gate_allowed blocked on BLOCKED portfolio fit ─────────────────────────


def test_journal_gate_blocked():
    from src.engines.decision_object import DecisionObject
    from src.engines.decision_journal import JournalEntry

    obj = DecisionObject(
        ticker="BADTICK",
        portfolio_fit="BLOCKED",
        portfolio_gate_reason="Macro risk-off",
    )
    entry = JournalEntry.from_decision_object(obj, price=0.0)
    assert entry.gate_allowed is False
    assert "Macro risk-off" in entry.gate_blocks


# ── 9. from_dict round-trip preserves new fields ─────────────────────────────


def test_from_dict_round_trip():
    from src.engines.decision_object import DecisionObject

    obj = DecisionObject(
        ticker="TEST",
        signal_source="scanner",
        trust_level="CACHED",
        mtf_confluence_score=0.75,
        calibrated_confidence=0.68,
    )
    d = obj.to_dict()
    obj2 = DecisionObject.from_dict(d)
    assert obj2.signal_source == "scanner"
    assert obj2.trust_level == "CACHED"
    assert obj2.mtf_confluence_score == pytest.approx(0.75)
    assert obj2.calibrated_confidence == pytest.approx(0.68)
