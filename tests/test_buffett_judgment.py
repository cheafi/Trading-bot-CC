"""Tests for 《巴菲特传》Buffett biography judgment module."""

from __future__ import annotations

from src.services.buffett_judgment import (
    buffett_clarity_strip_for_today,
    build_buffett_owner_view,
    evaluate_allocation,
    evaluate_buffett_competence,
    evaluate_business,
    evaluate_hold_sell,
    evaluate_temperament,
    tags_for_playbook_row,
)


def test_business_quality_high_on_thesis():
    biz = evaluate_business(
        {
            "ticker": "KO",
            "sector": "Consumer Staples",
            "thesis_conf": 0.72,
            "structure": {"is_extended": False},
            "fundamentals_block": {"flags": [], "story_broken": False},
        }
    )
    assert biz["business_quality"] == "high"
    assert biz["moat"] == "likely"


def test_competence_outside_low_thesis():
    comp = evaluate_buffett_competence(
        {"sector": "exotic widgets", "thesis_conf": 0.35, "calibration_n": 0}
    )
    assert comp["competence_fit"] == "outside"


def test_allocation_inferior_on_broken_story():
    alloc = evaluate_allocation(
        {
            "thesis_conf": 0.7,
            "score": 8,
            "fundamentals_block": {"flags": ["story_broken_risk"], "story_broken": True},
        },
        tradeability="TRADE",
    )
    assert alloc["allocation_action"] == "inferior"


def test_allocation_ownable_when_aligned():
    alloc = evaluate_allocation(
        {
            "ticker": "BRK",
            "sector": "Financials",
            "thesis_conf": 0.7,
            "score": 7.5,
            "structure": {"is_extended": False},
        },
        tradeability="TRADE",
    )
    assert alloc["allocation_action"] in ("ownable", "study")


def test_patience_downgrades_ownable_on_wait():
    alloc = evaluate_allocation(
        {
            "sector": "Technology",
            "thesis_conf": 0.72,
            "score": 8,
            "structure": {},
        },
        tradeability="WAIT",
    )
    assert alloc["allocation_action"] in ("study", "watch")


def test_temperament_noise_on_wait_with_scores():
    temp = evaluate_temperament(
        tradeability="WAIT",
        deployable_count=0,
        opportunities=[{"score": 8}, {"score": 8.2}],
    )
    assert temp["noise_high"] is True
    assert temp["action_necessary"] is False


def test_hold_exit_on_broken_story():
    hold = evaluate_hold_sell(
        {"thesis_conf": 0.3, "fundamentals_block": {"story_broken": True}}
    )
    assert hold["hold_stance"] == "exit_watch"


def test_playbook_tags_shape():
    tags = tags_for_playbook_row(
        {"sector": "Technology", "thesis_conf": 0.6, "score": 7},
        tradeability="WAIT",
    )
    assert "business_quality" in tags
    assert "portfolio_worthiness" in tags
    assert "buffett_competence_fit" in tags


def test_owner_view_dossier_block():
    view = build_buffett_owner_view(
        ticker="AAPL",
        dossier={"sector": "Technology", "structure": {}},
        unified={"score": 7.2, "confidence": {"thesis": 0.68}},
        fundamentals_block={"flags": []},
        regime={"tradeability": "WAIT"},
    )
    assert view["mode"] == "buffett_biography"
    assert view["business_summary"]
    assert view["allocation_action"] in ("ownable", "study", "watch", "inferior")


def test_clarity_strip_for_today():
    strip = buffett_clarity_strip_for_today(
        {"tradeability": "WAIT"},
        {"honest_tradeability": "WAIT"},
        opportunities=[{"ticker": "X", "score": 8, "thesis_conf": 0.7, "sector": "Technology"}],
        deployable_count=0,
    )
    assert strip["mode"] == "buffett_biography"
    assert strip["patience"] is True
    assert "headline" in strip
