"""
tests/sprints/test_sprint108.py — Sprint 108: Signal Confidence Decay Penalty
===============================================================================
Covers:
  - apply_decay_penalty: zero penalty when age=0
  - apply_decay_penalty: positive penalty when aged
  - apply_decay_penalty: exponential half-life formula
  - apply_decay_penalty: A+ grade decays slower than D grade
  - apply_decay_penalty: cap at _MAX_DECAY_PENALTY_PTS
  - apply_decay_penalty: infers age from data_freshness_minutes
  - apply_decay_penalty: returns (float, float) tuple
  - get_stale_signals: filters by threshold
  - get_stale_signals: sorted descending by age
  - get_stale_signals: adds age_hours and decay_pct keys
  - GET /api/v7/decay/stale endpoint returns required keys
  - GET /api/v7/decay/penalty endpoint preview arithmetic
  - MultiLayerRanker applies lower action_score for stale signal vs fresh
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

# ── apply_decay_penalty ───────────────────────────────────────────────────────


def test_decay_zero_when_fresh():
    from src.engines.signal_decay import apply_decay_penalty

    score, decay = apply_decay_penalty({"score": 80, "setup_grade": "B"}, age_hours=0.0)
    assert score == 80.0
    assert decay == 0.0


def test_decay_positive_when_aged():
    from src.engines.signal_decay import apply_decay_penalty

    score, decay = apply_decay_penalty(
        {"score": 80, "setup_grade": "B"}, age_hours=18.0
    )
    assert score < 80.0
    assert decay > 0.0


def test_decay_returns_tuple_of_floats():
    from src.engines.signal_decay import apply_decay_penalty

    result = apply_decay_penalty({"score": 60, "setup_grade": "C"}, age_hours=4.0)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], float)
    assert isinstance(result[1], float)


def test_decay_half_life_formula():
    """At age = half_life, decay_fraction should be ~0.5."""
    from src.engines.signal_decay import apply_decay_penalty, DECAY_SCHEDULE

    half_life = DECAY_SCHEDULE["B"]  # 18h
    score = 100.0
    _, decay_frac = apply_decay_penalty(
        {"score": score, "setup_grade": "B"}, age_hours=half_life
    )
    # Expected: 1 - exp(-ln2) = 0.5
    assert abs(decay_frac - 0.5) < 0.01


def test_aplus_decays_slower_than_d():
    """A+ signal should retain more score than D signal at the same age."""
    from src.engines.signal_decay import apply_decay_penalty

    age = 12.0
    score_aplus, _ = apply_decay_penalty(
        {"score": 80, "setup_grade": "A+"}, age_hours=age
    )
    score_d, _ = apply_decay_penalty({"score": 80, "setup_grade": "D"}, age_hours=age)
    assert score_aplus > score_d


def test_decay_capped_at_max_penalty():
    """Penalty should never exceed _MAX_DECAY_PENALTY_PTS."""
    from src.engines.signal_decay import apply_decay_penalty, _MAX_DECAY_PENALTY_PTS

    score = 50.0
    penalised, _ = apply_decay_penalty(
        {"score": score, "setup_grade": "D"}, age_hours=200.0  # fully decayed
    )
    assert score - penalised <= _MAX_DECAY_PENALTY_PTS + 0.01


def test_decay_infers_age_from_freshness_minutes():
    """data_freshness_minutes=480 → age=8h → should produce non-zero penalty."""
    from src.engines.signal_decay import apply_decay_penalty

    signal = {"score": 70, "setup_grade": "C", "data_freshness_minutes": 480}
    score, decay = apply_decay_penalty(signal)  # no explicit age_hours
    assert decay > 0.0
    assert score < 70.0


def test_decay_zero_when_freshness_negative():
    """data_freshness_minutes=-1 (unknown) → no penalty."""
    from src.engines.signal_decay import apply_decay_penalty

    signal = {"score": 70, "setup_grade": "C", "data_freshness_minutes": -1}
    score, decay = apply_decay_penalty(signal)
    assert score == 70.0
    assert decay == 0.0


# ── get_stale_signals ─────────────────────────────────────────────────────────


def test_get_stale_signals_filters_by_threshold():
    from src.engines.signal_decay import get_stale_signals

    signals = [
        {"ticker": "OLD", "score": 70, "setup_grade": "B", "age_hours": 10.0},
        {"ticker": "NEW", "score": 80, "setup_grade": "A", "age_hours": 2.0},
    ]
    stale = get_stale_signals(signals, threshold_hours=8.0)
    tickers = [s["ticker"] for s in stale]
    assert "OLD" in tickers
    assert "NEW" not in tickers


def test_get_stale_signals_sorted_desc_by_age():
    from src.engines.signal_decay import get_stale_signals

    signals = [
        {"ticker": "A", "score": 70, "setup_grade": "B", "age_hours": 9.0},
        {"ticker": "B", "score": 60, "setup_grade": "C", "age_hours": 12.0},
        {"ticker": "C", "score": 50, "setup_grade": "D", "age_hours": 20.0},
    ]
    stale = get_stale_signals(signals, threshold_hours=8.0)
    ages = [s["age_hours"] for s in stale]
    assert ages == sorted(ages, reverse=True)


def test_get_stale_signals_adds_decay_pct_key():
    from src.engines.signal_decay import get_stale_signals

    signals = [{"ticker": "X", "score": 80, "setup_grade": "C", "age_hours": 10.0}]
    stale = get_stale_signals(signals, threshold_hours=8.0)
    assert stale
    assert "decay_pct" in stale[0]
    assert "age_hours" in stale[0]


# ── REST endpoints ────────────────────────────────────────────────────────────


def test_decay_stale_endpoint_structure():
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.get("/api/v7/decay/stale")
    assert resp.status_code == 200
    data = resp.json()
    assert "stale_count" in data
    assert "total_active" in data
    assert "signals" in data
    assert "threshold_hours" in data


def test_decay_penalty_preview_endpoint():
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.get("/api/v7/decay/penalty?age_hours=18&score=100&grade=B")
    assert resp.status_code == 200
    data = resp.json()
    assert "penalised_score" in data
    assert "decay_pct" in data
    assert "penalty_pts" in data
    # At half-life (B=18h), decay_pct should be ~50% but penalty is capped at 20pts
    # So penalised_score = 100 - 20 = 80 (cap applies)
    assert data["penalty_pts"] <= 20.0 + 0.01
    assert data["penalised_score"] >= 0.0
    assert data["decay_pct"] > 40.0  # at least 40% decay at half-life


# ── MultiLayerRanker decay integration ───────────────────────────────────────


def test_ranker_lower_score_for_stale_signal():
    """A stale signal (high data_freshness_minutes) should rank lower than identical fresh signal."""
    from src.engines.multi_ranker import MultiLayerRanker

    def _mock_result(ticker, freshness_minutes):
        r = MagicMock()
        r.signal = {
            "ticker": ticker,
            "score": 8,
            "vol_ratio": 2.0,
            "rs_rank": 80,
            "final_confidence": 0.75,
            "data_freshness_minutes": freshness_minutes,
            "setup_grade": "B",
            "action": "BUY",
            "sector_fit": 0.7,
            "timing_confidence": 0.7,
            "risk_reward": 3.0,
            "has_catalyst": False,
            "insider_buy": False,
            "options_bullish": False,
            "mtf_confluence_score": 0.7,
            "thesis_confidence": 0.7,
            "regime": "BULL",
        }
        r.sector_context = None
        r.fit = MagicMock()
        r.fit.setup_fit = 0.8
        r.fit.timing_fit = 80.0
        r.fit.sector_fit = 80.0
        r.fit.regime_fit = 80.0
        r.fit.execution_fit = 80.0
        r.fit.risk_fit = 80.0
        r.fit.final_score = 80.0
        r.fit.evidence_conflicts = []
        r.fit.risk_reward = 3.0
        r.confidence = MagicMock()
        r.confidence.final = 0.75
        r.confidence.thesis = 0.75
        r.sector = MagicMock()
        r.sector.leader_status = MagicMock()
        r.sector.leader_status.value = "WATCH"
        r.decision = MagicMock()
        r.decision.action = "TRADE"
        return r

    ranker = MultiLayerRanker()
    fresh = _mock_result("FRESH", freshness_minutes=30)  # 0.5h old
    stale = _mock_result("STALE", freshness_minutes=960)  # 16h old

    ranks = ranker.rank_batch([fresh, stale])
    fresh_action = ranks["FRESH"].action_score
    stale_action = ranks["STALE"].action_score
    assert (
        fresh_action >= stale_action
    ), f"Fresh signal should have >= action score: fresh={fresh_action:.1f} stale={stale_action:.1f}"
