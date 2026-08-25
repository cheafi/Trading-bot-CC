"""Tests for research-quality classification (rank ≠ quality ≠ authority)."""

from __future__ import annotations

from src.services.opportunity_quality import (
    attach_quality_to_row,
    build_opportunity_verdict,
    classify_opportunity_quality,
)


def _mstr_like_row() -> dict:
    return {
        "ticker": "MSTR",
        "rank": 1,
        "score": 6.4,
        "action": "WATCH",
        "raw_action": "WATCH",
        "risk_reward": 1.8,
        "thesis_conf": 0.45,
        "timing_conf": 0.55,
        "exec_conf": 0.58,
        "data_conf": 0.62,
        "leader": "NEUTRAL",
        "conflict_level": "LOW",
        "structure": {"is_extended": False, "trend": "uptrend"},
        "execution_ready": False,
    }


def _v_like_row(*, laggard: bool = True) -> dict:
    return {
        "ticker": "V",
        "rank": 2,
        "score": 7.1,
        "action": "WATCH",
        "raw_action": "WATCH",
        "risk_reward": 2.3,
        "thesis_conf": 0.58,
        "timing_conf": 0.62,
        "exec_conf": 0.61,
        "data_conf": 0.72,
        "leader": "LAGGARD" if laggard else "LEADER",
        "why_not": "laggard position in sector" if laggard else "",
        "conflict_level": "LOW",
        "structure": {"is_extended": False, "trend": "uptrend"},
        "execution_ready": False,
    }


def test_mstr_like_row_is_weak():
    q = classify_opportunity_quality(_mstr_like_row())
    assert q["tier"] == "WEAK"
    assert q["score"] < 70
    assert any("R:R" in r or "Thesis" in r for r in q["reasons"])


def test_v_like_laggard_is_promising_not_strong():
    q = classify_opportunity_quality(_v_like_row(laggard=True))
    assert q["tier"] == "PROMISING"
    assert q["tier"] != "STRONG"
    assert any("laggard" in r.lower() for r in q["reasons"])


def test_stale_data_cannot_be_strong():
    row = {
        "ticker": "AAPL",
        "score": 8.5,
        "action": "WATCH",
        "risk_reward": 3.0,
        "thesis_conf": 0.72,
        "timing_conf": 0.68,
        "exec_conf": 0.65,
        "data_conf": 0.75,
        "leader": "LEADER",
        "conflict_level": "LOW",
        "structure": {"is_extended": False},
        "execution_ready": False,
    }
    q = classify_opportunity_quality(row, data_stale=True)
    assert q["tier"] != "STRONG"


def test_board_verdict_zero_quality_when_all_weak():
    rows = [attach_quality_to_row(_mstr_like_row()), attach_quality_to_row(_v_like_row())]
    verdict = build_opportunity_verdict({"top_ranked": rows, "near_miss": [], "filter_funnel": {}})
    assert verdict["quality_qualified_count"] == 0
    assert verdict["state"] in ("NO_HIGH_QUALITY_SETUP", "PROMISING_ONLY")
    assert verdict["monitor_qualified_count"] >= 1


def test_strong_does_not_set_deploy_eligible():
    row = {
        "ticker": "NVDA",
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
        "deploy_eligible": False,
    }
    out = attach_quality_to_row(row)
    assert out["quality"]["tier"] == "STRONG"
    assert out.get("deploy_eligible") is not True
    assert out.get("execution_ready") is False


def test_brief_stale_marks_research_context():
    row = _mstr_like_row()
    q = classify_opportunity_quality(row, brief_stale=True)
    assert q["research_context_only"] is True
    assert q["tier"] in ("REJECT", "WEAK", "PROMISING")


def test_reject_extended_row():
    row = _mstr_like_row()
    row["structure"] = {"is_extended": True, "extension_pct": 0.18}
    row["data_conf"] = 0.30
    q = classify_opportunity_quality(row)
    assert q["tier"] == "REJECT"


def test_attach_opportunity_verdict_enriches_rows():
    from src.services.opportunity_quality import attach_opportunity_verdict_to_payload

    rows = [attach_quality_to_row(_mstr_like_row()), attach_quality_to_row(_v_like_row())]
    payload = attach_opportunity_verdict_to_payload({"top_ranked": rows, "near_miss": []})
    assert payload["opportunity_verdict"]["tier_counts"]["WEAK"] >= 1
    assert payload["top_ranked"][0]["quality_tier"] == "WEAK"
    assert payload["top_ranked"][0]["authority_label"]
