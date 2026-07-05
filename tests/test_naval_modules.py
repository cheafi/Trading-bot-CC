"""Tests for 《纳瓦尔宝典》Naval Almanac modules."""

from __future__ import annotations

from src.services.calm_reactive_mode import evaluate_calm_reactive
from src.services.compounding_priority import evaluate_compounding_priority
from src.services.decision_quality_naval import (
    build_naval_thinking,
    evaluate_decision_quality,
    naval_clarity_strip_for_today,
)
from src.services.leverage_engine import label_leverage
from src.services.opportunity_quality_naval import evaluate_opportunity_quality
from src.services.signal_to_noise import classify_signal_to_noise
from src.services.specific_knowledge import evaluate_competence_fit


def test_signal_noise_ignore_on_wait():
    sn = classify_signal_to_noise(
        {"score": 8.2, "thesis_conf": 0.7, "action": "WATCH"},
        tradeability="WAIT",
        deployable_count=0,
    )
    assert sn["level"] in ("ignore", "monitor_lightly")
    assert sn["preserve_focus"] is True


def test_signal_act_now_when_deploy_ready():
    sn = classify_signal_to_noise(
        {
            "score": 8.5,
            "thesis_conf": 0.72,
            "action": "TRADE",
            "execution_ready": True,
        },
        tradeability="TRADE",
        deployable_count=2,
    )
    assert sn["level"] == "act_now"
    assert sn["action_necessity"] == "required"


def test_competence_borrowed_on_narrative():
    c = evaluate_competence_fit(
        {
            "thesis_conf": 0.52,
            "data_conf": 0.4,
            "why_now": "x" * 150,
        }
    )
    assert c["borrowed_conviction_risk"] in ("high", "medium")
    assert c["competence_fit"] in ("borrowed", "outside", "partial_fit")


def test_opportunity_bandwidth_worthy():
    q = evaluate_opportunity_quality(
        {"thesis_conf": 0.62, "timing_conf": 0.58, "risk_reward": 2.6}
    )
    assert q["mental_bandwidth_worthy"] is True
    assert q["asymmetry"] == "asymmetric"


def test_decision_quality_known_unknowns():
    dq = evaluate_decision_quality(
        {"thesis_conf": 0.7, "timing_conf": 0.35, "data_conf": 0.6, "why_not": "extended"}
    )
    assert dq["clarity"] in ("medium", "low")
    assert any("timing" in u for u in dq["known_unknowns"])


def test_leverage_process_on_wait():
    lev = label_leverage({"action": "WAIT"}, surface="today")
    assert lev["primary"] == "process"


def test_calm_false_urgency_on_wait_with_scores():
    calm = evaluate_calm_reactive(
        tradeability="WAIT",
        deployable_count=0,
        opportunities=[{"score": 8}, {"score": 8.1}, {"score": 7.9}],
    )
    assert calm["false_urgency"] is True
    assert calm["preserve_focus"] is True


def test_compounding_patience_on_wait():
    cp = evaluate_compounding_priority({}, context={"tradeability": "WAIT", "deployable_count": 0})
    assert cp["verdict"] == "compound"
    assert "patience" in cp["headline"].lower() or "compound" in cp["headline"].lower()


def test_naval_strip_aligns_with_no_deploy():
    strip = naval_clarity_strip_for_today(
        {"tradeability": "WAIT", "vix": 18},
        {"honest_tradeability": "WAIT"},
        opportunities=[
            {"ticker": "AAPL", "score": 8, "action": "WATCH", "thesis_conf": 0.5},
            {"ticker": "MSFT", "score": 8.1, "action": "WATCH", "thesis_conf": 0.55},
        ],
        deployable_count=0,
    )
    assert strip["mode"] == "naval_almanac"
    assert strip["preserve_focus"] is True
    assert strip["action_necessity"] == "none" or strip["false_urgency"]


def test_build_naval_thinking_dossier_block():
    block = build_naval_thinking(
        ticker="MSFT",
        dossier={"thesis_conf": 0.6, "risk_reward": 2.2, "structure": {}},
        unified={"action": "WATCH", "confidence": {"thesis": 0.6, "timing": 0.5, "data": 0.55}},
        regime={"tradeability": "WAIT"},
    )
    assert block["mode"] == "naval_almanac"
    assert "summary_30s" in block
    assert block["signal_to_noise"] in ("ignore", "monitor_lightly", "think_deeply", "noise")
