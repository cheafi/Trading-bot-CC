"""Score families disagreement — rank ≠ quality ≠ authority ≠ EV."""

from __future__ import annotations

from src.services.opportunity_quality import attach_quality_to_row
from src.services.score_families import (
    DISAGREEMENT_MESSAGE,
    attach_score_families_disagreement_to_row,
    build_score_families_summary,
    build_score_reconciliation,
    detect_score_family_disagreement,
    row_has_council_scanner_divergence,
)


def _rank1_weak_row() -> dict:
    return attach_quality_to_row(
        {
            "ticker": "MSTR",
            "rank": 1,
            "score": 6.4,
            "action": "WATCH",
            "risk_reward": 1.8,
            "thesis_conf": 0.45,
            "timing_conf": 0.55,
            "exec_conf": 0.58,
            "data_conf": 0.62,
            "leader": "NEUTRAL",
            "conflict_level": "LOW",
            "structure": {"is_extended": False, "trend": "uptrend"},
            "execution_ready": False,
            "ev_score": 0.42,
        }
    )


def _rank2_strong_wait_row() -> dict:
    return attach_quality_to_row(
        {
            "ticker": "NVDA",
            "rank": 2,
            "score": 9.0,
            "action": "WATCH",
            "risk_reward": 3.2,
            "thesis_conf": 0.75,
            "timing_conf": 0.70,
            "exec_conf": 0.65,
            "data_conf": 0.80,
            "leader": "LEADER",
            "conflict_level": "LOW",
            "structure": {"is_extended": False, "trend": "uptrend"},
            "execution_ready": False,
            "ev_score": 0.88,
        }
    )


def test_rank1_weak_quality_disagrees():
    row = _rank1_weak_row()
    sf = detect_score_family_disagreement(
        row, rank_total=5, peers=[row], deploy_open=False, tradeability="WAIT"
    )
    assert sf["disagree"] is True
    assert sf["message"] == DISAGREEMENT_MESSAGE
    assert any("quality WEAK" in r for r in sf["reasons"])


def test_top3_wait_not_strong_disagrees():
    row = _rank1_weak_row()
    sf = detect_score_family_disagreement(
        row, rank_total=5, peers=[row], deploy_open=False, tradeability="WAIT"
    )
    assert any("gate WAIT" in r for r in sf["reasons"])


def test_low_ev_vs_peers_disagrees():
    peers = [
        _rank1_weak_row(),
        attach_quality_to_row(
            {
                **(_rank1_weak_row()),
                "ticker": "AAPL",
                "rank": 2,
                "ev_score": 0.95,
            }
        ),
    ]
    sf = detect_score_family_disagreement(
        peers[0], rank_total=2, peers=peers, deploy_open=False, tradeability="WAIT"
    )
    assert any("EV" in r for r in sf["reasons"])


def test_strong_quality_wait_gate_disagrees():
    row = _rank2_strong_wait_row()
    assert row["quality"]["tier"] == "STRONG"
    sf = detect_score_family_disagreement(
        row, rank_total=5, peers=[row], deploy_open=False, tradeability="WAIT"
    )
    assert sf["disagree"] is True
    assert any("quality STRONG" in r and "gate WAIT" in r for r in sf["reasons"])


def test_council_scanner_divergence():
    row = {
        "ticker": "AAPL",
        "score": 8.0,
        "evidence_quality": {"raw_score": 5.0},
    }
    assert row_has_council_scanner_divergence(row) is True


def test_aligned_strong_deploy_no_disagree():
    row = attach_quality_to_row(
        {
            "ticker": "MSFT",
            "rank": 1,
            "score": 8.8,
            "action": "TRADE",
            "risk_reward": 3.0,
            "thesis_conf": 0.72,
            "timing_conf": 0.68,
            "exec_conf": 0.66,
            "data_conf": 0.78,
            "leader": "LEADER",
            "conflict_level": "LOW",
            "structure": {"is_extended": False},
            "execution_ready": True,
            "ev_score": 0.82,
            "evidence_quality": {"raw_score": 8.6, "validated_score": 8.8},
        }
    )
    sf = detect_score_family_disagreement(
        row,
        rank_total=3,
        peers=[row],
        deploy_open=True,
        tradeability="TRADE",
    )
    assert sf["disagree"] is False


def test_attach_row_includes_score_families():
    out = attach_score_families_disagreement_to_row(
        _rank1_weak_row(),
        rank_total=5,
        peers=[_rank1_weak_row()],
        deploy_open=False,
        tradeability="WAIT",
    )
    assert out["score_families"]["disagree"] is True
    assert "score_card" in out


def test_payload_summary_and_reconciliation():
    rows = [_rank1_weak_row(), _rank2_strong_wait_row()]
    summary = build_score_families_summary(
        rows, deploy_open=False, tradeability="WAIT"
    )
    assert summary["active"] is True
    assert summary["disagree_count"] >= 1
    recon = build_score_reconciliation(
        rows, deploy_open=False, tradeability="WAIT"
    )
    assert recon["active"] is True
    assert recon["score_families_summary"]["disagree_count"] >= 1
    assert DISAGREEMENT_MESSAGE in recon["message"]
    assert "MSTR" in recon["divergent_tickers"]


def test_disagreement_never_sets_execution_ready():
    out = attach_score_families_disagreement_to_row(
        _rank1_weak_row(),
        rank_total=1,
        peers=[_rank1_weak_row()],
        deploy_open=False,
        tradeability="WAIT",
    )
    assert out.get("execution_ready") is not True
    assert out["score_families"]["families"]["authority"] == "MONITOR"


def test_attention_budget_service_defaults():
    from src.services.attention_budget import DEFAULT_BUDGETS, build_attention_budget_summary

    summary = build_attention_budget_summary(usage={"research": 61, "portfolio": 0, "market": 0})
    assert summary["any_exceeded"] is True
    assert "Enough" in summary["ciio_message"]
    assert DEFAULT_BUDGETS["research"] == 60


def test_knowledge_retrieval_empty_ticker_lessons():
    from src.services.knowledge_retrieval import build_ticker_lessons

    payload = build_ticker_lessons("ZZZZ")
    assert payload["ticker"] == "ZZZZ"
    assert payload["status"] == "empty"
    assert payload["lesson_count"] == 0
