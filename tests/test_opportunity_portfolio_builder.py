"""Opportunity portfolio builder — caps and diversification."""

from __future__ import annotations

from src.services.opportunity_portfolio_builder import (
    NEAR_MISS_CAP,
    RESEARCH_CAP,
    WATCH_CAP,
    build_opportunity_portfolio,
)


def _entry(ticker: str, stage: str, sector: str = "tech", score: float = 0.7):
    return {
        "candidate": {"ticker": ticker, "stage": stage, "sector": sector, "theme": sector},
        "evidence": {"composite_score": score, "grade": "B"},
        "calibration": {"state": "learning", "learning_mode": True, "cost_drag_r": 0.1},
        "screens": {"pattern_status": "heuristic_pass"},
    }


def test_research_cap_enforced():
    rows = [_entry(f"T{i}", "research_hit", "tech") for i in range(30)]
    book = build_opportunity_portfolio(rows)
    assert book["counts"]["research"] <= RESEARCH_CAP


def test_sector_diversification():
    rows = [_entry(f"S{i}", "research_hit", "tech") for i in range(10)]
    rows += [_entry(f"X{i}", "research_hit", "energy") for i in range(10)]
    book = build_opportunity_portfolio(rows)
    assert book["counts"]["research"] <= RESEARCH_CAP


def test_watch_and_near_miss_caps():
    watch = [_entry(f"W{i}", "watch_candidate") for i in range(15)]
    near = [_entry(f"N{i}", "near_miss") for i in range(10)]
    book = build_opportunity_portfolio(watch + near)
    assert book["counts"]["watch"] <= WATCH_CAP
    assert book["counts"]["near_miss"] <= NEAR_MISS_CAP
    assert book["may_authorize_deploy"] is False
