"""Tests for CC X sprint modules — EV, Alpha Factory, Attribution, Intelligence."""

from __future__ import annotations

from src.services.alpha_factory import spawn_alpha_object_from_row
from src.services.attribution_tree import resolve_attribution_chain
from src.services.ev_ranking import compute_ev_score, enrich_rows_with_ev
from src.services.intelligence_engine import build_intelligence_daily_report
from src.services.knowledge_graph import neighbors_for, theme_cluster_id_for


def test_ev_score_research_only():
    row = {"ticker": "AAPL", "score": 7.5, "thesis_conf": 0.6, "execution_ready": False}
    ev = compute_ev_score(row, tradeability="WAIT")
    assert "ev_score" in ev
    assert ev["authority"] == "research_only"
    assert ev["may_authorize_deploy"] is False


def test_enrich_rows_with_ev_sorts_descending():
    rows = [
        {"ticker": "A", "score": 5.0, "thesis_conf": 0.4},
        {"ticker": "B", "score": 8.0, "thesis_conf": 0.7},
    ]
    out = enrich_rows_with_ev(rows, tradeability="SELECTIVE")
    assert out[0]["ticker"] == "B"


def test_alpha_factory_spawns_research_only():
    row = {
        "ticker": "TSLA",
        "why_now": "Momentum continuation",
        "source": "scanner",
        "as_of": "2026-08-25T08:00:00Z",
        "mode": "LIVE",
    }
    alpha = spawn_alpha_object_from_row(row)
    assert alpha.ticker == "TSLA"
    assert alpha.authority == "research_only"
    assert alpha.may_authorize_deploy is False
    assert len(alpha.evidence) >= 1
    assert row.get("artifact_id")


def test_attribution_chain_seven_levels():
    chain = resolve_attribution_chain(
        position_id="pos-1",
        ticker="AAPL",
        decision_id="dec-AAPL-abc",
        alpha_id="alpha-1",
    )
    assert chain["chain_depth"] == 7
    assert chain["complete"] is True
    assert chain["authority"] == "research_only"


def test_knowledge_graph_neighbors_research_only():
    n = neighbors_for("AAPL")
    assert n["authority"] == "research_only"
    assert n["theme_cluster_id"].startswith("theme-")


def test_intelligence_daily_report_research_only():
    report = build_intelligence_daily_report(today_payload={"top_5": [{"ticker": "AAPL"}]})
    assert report["authority"] == "research_only"
    assert "platform_smarter_today" in report
    assert len(report["scores"]) == 7
