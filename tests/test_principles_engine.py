"""Tests for 《原则系列》Principles series modules."""

from __future__ import annotations

from src.services.decision_machines import (
    MACHINE_CATALOG,
    build_machines_health_panel,
    evaluate_machine_health,
)
from src.services.platform_error_log import clear_error_log_for_tests, get_error_log
from src.services.principles_engine import (
    build_principles_memo,
    classify_root_cause,
    classify_truth_integrity,
    evaluate_decision_posture,
    evaluate_decision_quality_principles,
    log_principles_lesson,
    principles_posture_for_today,
    score_evidence_weight,
    tags_for_playbook_row,
)


def test_truth_integrity_unknown_on_weak_data():
    t = classify_truth_integrity({"data_conf": 0.2})
    assert t["integrity"] == "unknown"
    assert t["unknowns"]


def test_evidence_weight_high_when_calibrated():
    e = score_evidence_weight(
        {
            "thesis_conf": 0.72,
            "timing_conf": 0.65,
            "data_conf": 0.7,
            "calibration_n": 40,
            "execution_ready": True,
        }
    )
    assert e["tier"] == "high"
    assert e["calibration_available"] is True


def test_decision_quality_grade_a_with_objections():
    q = evaluate_decision_quality_principles(
        {
            "thesis_conf": 0.68,
            "timing_conf": 0.55,
            "data_conf": 0.62,
            "invalidation": "Close below 200dma",
            "why_not": "Extended",
            "data_freshness": "fresh",
        }
    )
    assert q["grade"] in ("A", "B")
    assert q["outcome_independent"] is True


def test_posture_blocked_on_wait():
    p = evaluate_decision_posture(
        {"action": "TRADE", "thesis_conf": 0.7, "data_conf": 0.6},
        tradeability="WAIT",
    )
    assert p["posture"] == "blocked"
    assert p["principle_support"] == "weak"
    assert any("board gate" in r for r in p["blocked_reasons"])


def test_posture_allowed_when_gate_and_process_align():
    p = evaluate_decision_posture(
        {
            "action": "TRADE",
            "thesis_conf": 0.72,
            "timing_conf": 0.66,
            "data_conf": 0.68,
            "invalidation": "Stop below support",
            "data_freshness": "fresh",
            "calibration_n": 35,
            "execution_ready": True,
        },
        tradeability="TRADE",
    )
    assert p["posture"] == "allowed"
    assert p["decision_grade"] in ("A", "B")


def test_playbook_tags_surface_fields():
    tags = tags_for_playbook_row(
        {"thesis_conf": 0.5, "data_conf": 0.4, "action": "WATCH"},
        tradeability="WAIT",
    )
    assert "principle_support" in tags
    assert "evidence_quality" in tags
    assert "decision_grade" in tags
    assert tags["principles_posture"] == "blocked"


def test_principles_strip_blocks_on_wait():
    strip = principles_posture_for_today(
        {"tradeability": "WAIT"},
        {"honest_tradeability": "WAIT"},
        opportunities=[{"score": 8, "action": "WATCH", "thesis_conf": 0.6}],
        deployable_count=0,
    )
    assert strip["action_blocked_by_principle"] is True
    assert strip["governing_principle"] == "process_over_outcome"


def test_principles_memo_includes_unknowns():
    memo = build_principles_memo(
        ticker="AAPL",
        dossier={"thesis_conf": 0.55, "signal": {"data_freshness": "stale"}},
        unified={"action": "WATCH", "confidence": {"thesis": 0.55, "data": 0.3}},
        regime={"tradeability": "WAIT"},
    )
    assert memo["mode"] == "principles_series"
    assert memo["principle_decision"] in ("blocked", "deferred")
    assert memo["unknowns"] or memo["truth_integrity"] != "fact"


def test_root_cause_data_failure():
    rc = classify_root_cause(component="api", message="503 timeout", detail="provider stale")
    assert rc["root_cause"] == "data_failure"
    assert rc["lesson"]


def test_log_principles_lesson_persists_fields():
    clear_error_log_for_tests()
    entry = log_principles_lesson(
        severity="warning",
        component="engine",
        message="Engine stopped",
        detail="No cycles",
    )
    assert entry is not None
    assert entry.get("root_cause")
    assert entry.get("lesson")
    rows = get_error_log(limit=5)["entries"]
    assert rows[0].get("root_cause") == entry["root_cause"]


def test_machines_catalog_has_eight():
    assert len(MACHINE_CATALOG) == 8


def test_machines_health_panel_structure():
    panel = build_machines_health_panel(
        ops_status={"engine": {"running": False, "cycle_count": 0, "cached_recommendations": 0}},
        today={"decision_model": {"honest_tradeability": "WAIT"}},
    )
    assert panel["machine_count"] == 8
    assert len(panel["machines"]) == 8
    assert panel["overall"] in ("healthy", "degraded", "blocked")


def test_regime_machine_blocked_on_wait():
    m = evaluate_machine_health(
        "regime",
        today={"decision_model": {"honest_tradeability": "WAIT"}},
    )
    assert m["health"] == "blocked"
