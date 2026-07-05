"""Confidence-based position sizing — authority tiers and confidence bands."""

from __future__ import annotations

import os

from src.services.cc_daily_trading import build_actionable_today
from src.services.position_sizing import (
    ACTION_HALF,
    ACTION_MONITOR,
    ACTION_QUARTER,
    ACTION_WAIT,
    sanitize_sizing_for_authority,
    suggest_position_size,
)


def _high_candidate(**overrides):
    base = {
        "ticker": "KO",
        "action": "TRADE",
        "score": 8.0,
        "grade": "A",
        "final_conf": 0.72,
        "risk_reward": 2.4,
        "execution_ready": True,
        "setup_evidence": {"sample_size": 30, "data_quality_pct": 75},
    }
    base.update(overrides)
    return base


def _low_candidate(**overrides):
    base = {
        "ticker": "X",
        "action": "PILOT",
        "score": 7.1,
        "grade": "B+",
        "final_conf": 0.48,
        "risk_reward": 1.5,
        "execution_ready": False,
        "setup_evidence": {"sample_size": 5, "data_quality_pct": 50},
    }
    base.update(overrides)
    return base


def test_high_confidence_allowed_execution_ready_full_size():
    truth = {"deploy_authority": True, "deploy_authority_tier": "allowed"}
    out = suggest_position_size(_high_candidate(), truth)
    assert out["action"] == "full"
    assert out["size_pct"] == 0.01
    assert out["confidence_band"] == "high"
    assert "Full pilot" in out["size_label"]


def test_high_confidence_respects_cc_max_position_pct(monkeypatch):
    monkeypatch.setenv("CC_MAX_POSITION_PCT", "0.015")
    truth = {"deploy_authority": True, "deploy_authority_tier": "allowed"}
    out = suggest_position_size(_high_candidate(), truth)
    assert out["size_pct"] == 0.015
    monkeypatch.delenv("CC_MAX_POSITION_PCT", raising=False)


def test_low_confidence_quarter_or_wait():
    truth = {"deploy_authority": True, "deploy_authority_tier": "allowed"}
    out = suggest_position_size(_low_candidate(), truth)
    assert out["action"] in (ACTION_QUARTER, ACTION_WAIT)
    if out["action"] == ACTION_QUARTER:
        assert out["size_pct"] == 0.0025


def test_blocked_authority_monitor_only_zero_size():
    truth = {"deploy_authority": False, "deploy_authority_tier": "blocked"}
    out = suggest_position_size(_high_candidate(), truth)
    assert out["action"] == ACTION_MONITOR
    assert out["size_pct"] == 0.0
    assert "僅監察" in out["size_label"]


def test_paper_only_half_max():
    truth = {"deploy_authority": False, "deploy_authority_tier": "paper_only"}
    out = suggest_position_size(_high_candidate(), truth)
    assert out["action"] == ACTION_HALF
    assert out["size_pct"] <= 0.005


def test_paper_only_low_conf_quarter():
    truth = {"deploy_authority": False, "deploy_authority_tier": "paper_only"}
    out = suggest_position_size(
        _low_candidate(score=7.05, risk_reward=1.6, final_conf=0.48),
        truth,
    )
    assert out["action"] in (ACTION_QUARTER, ACTION_WAIT)
    if out["action"] == ACTION_QUARTER:
        assert out["size_pct"] <= 0.0025


def test_uncalibrated_heuristic_caps_at_half():
    truth = {"deploy_authority": True, "deploy_authority_tier": "allowed"}
    cand = _high_candidate(setup_evidence={"sample_size": 8, "data_quality_pct": 72})
    out = suggest_position_size(cand, truth)
    assert out["size_pct"] <= 0.005
    assert out.get("heuristic_cap") is True


def test_avoid_action_wait():
    truth = {"deploy_authority": True, "deploy_authority_tier": "allowed"}
    out = suggest_position_size(_high_candidate(action="AVOID"), truth)
    assert out["action"] == ACTION_WAIT
    assert out["size_pct"] == 0.0


def test_sanitize_blocked_strips_positive_sizing():
    truth = {"deploy_authority": False, "deploy_authority_tier": "blocked"}
    raw = {"action": "full", "size_pct": 0.01, "size_label": "1.0% · Full"}
    out = sanitize_sizing_for_authority(raw, truth, _high_candidate())
    assert out["size_pct"] == 0.0
    assert out["action"] == ACTION_MONITOR


def test_build_actionable_today_includes_sizing():
    truth = {
        "deploy_authority": True,
        "deploy_authority_tier": "allowed",
        "regime_state": "TRADE",
    }
    out = build_actionable_today([_high_candidate()], system_truth=truth, limit=3)
    assert out["cards"]
    assert out["cards"][0]["ticker"] == "KO"
    assert "sizing" in out["cards"][0]
    assert out["cards"][0]["sizing"]["size_pct"] > 0
