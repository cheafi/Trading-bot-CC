"""Shared opportunity pipeline — playbook + today parity."""

from __future__ import annotations

from pathlib import Path

from src.services.opportunity_pipeline import finalize_opportunity_pipeline

ROOT = Path(__file__).resolve().parents[1]


def _sample_row(ticker: str = "AAPL") -> dict:
    return {
        "ticker": ticker,
        "rank": 1,
        "score": 7.5,
        "action": "WATCH",
        "raw_action": "WATCH",
        "risk_reward": 2.4,
        "thesis_conf": 0.62,
        "timing_conf": 0.58,
        "exec_conf": 0.55,
        "data_conf": 0.72,
        "leader": "LEADER",
        "conflict_level": "LOW",
        "structure": {"is_extended": False, "trend": "uptrend"},
        "execution_ready": False,
    }


def test_playbook_pipeline_attaches_quality_and_io_fields():
    payload = finalize_opportunity_pipeline(
        {
            "opportunities": [_sample_row("NVDA"), _sample_row("MSFT")],
            "near_miss": [],
            "filter_funnel": {"watch_qualified_setups": 2},
            "best_action": {"tradeability": "SELECTIVE"},
        },
        source="playbook",
        tradeability="SELECTIVE",
    )
    rows = payload["opportunities"]
    assert rows[0].get("quality", {}).get("tier")
    assert rows[0].get("quality_tier") or rows[0]["quality"]["tier"]
    assert payload.get("opportunity_verdict")
    assert any(
        rows[0].get(k)
        for k in ("investment_object", "alpha_object", "artifact_id", "ev_score")
    )


def test_today_pipeline_preserves_verdict_and_research_authority():
    payload = finalize_opportunity_pipeline(
        {
            "top_ranked": [_sample_row()],
            "near_miss": [],
            "filter_funnel": {},
            "best_action": {"tradeability": "WAIT"},
        },
        source="today",
        tradeability="WAIT",
        index_regime={"label": "defensive", "posture": "WAIT"},
    )
    verdict = payload["opportunity_verdict"]
    assert verdict["authority_note"]
    assert "deploy" in verdict["authority_note"].lower()
    assert payload["top_ranked"][0]["quality"]["tier"] in (
        "STRONG",
        "PROMISING",
        "WEAK",
        "REJECT",
    )


def test_pipeline_attaches_decision_id_on_rows():
    payload = finalize_opportunity_pipeline(
        {"top_5": [_sample_row("AAPL")]},
        source="today",
        tradeability="WAIT",
    )
    row = payload["top_5"][0]
    assert row.get("decision_id")
    assert row.get("attribution_root_ref")


def test_cc_app_deploy_ssot_no_dual_can_deploy_sources():
    app_js = (ROOT / "src/api/static/cc-app.js").read_text(encoding="utf-8")
    assert "can_deploy_today" not in app_js
    assert "deploy_open ||" not in app_js
    assert "|| td.can_deploy" not in app_js
    assert "deployOpen()" in app_js
    assert "deployOpenFromSystemState" in (
        ROOT / "src/api/static/cc-helpers.js"
    ).read_text(encoding="utf-8")
