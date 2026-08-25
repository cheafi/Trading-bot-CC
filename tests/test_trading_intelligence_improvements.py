"""Section 8 trading-intelligence improvements — authority, near-miss, track record."""

from src.services.decision_truth_model import (
    apply_authority_to_row,
    build_decision_authority,
    finalize_ranked_payload_authority,
)
from src.services.runtime_truth import engine_runtime_snapshot, merge_execution_runtime_truth
from src.services.score_families import build_score_reconciliation, row_has_council_scanner_divergence


def test_apply_authority_sets_effective_action_and_grade():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=False,
        fallback_brief=False,
    )
    row = apply_authority_to_row(
        {"ticker": "NVDA", "action": "TRADE", "raw_action": "TRADE", "risk_reward": 2.5},
        authority,
    )
    assert row["effective_action"] == "WATCH ONLY"
    assert row["effective_grade"] == row["effective_action"]


def test_finalize_ranked_payload_authority_on_all_row_keys():
    payload = {
        "source": "ranked_pipeline",
        "best_action": {"tradeability": "WAIT"},
        "opportunities": [
            {"ticker": "A", "action": "TRADE", "score": 7.0, "risk_reward": 2.0},
        ],
        "near_miss": [{"ticker": "B", "action": "WATCH", "score": 6.2}],
    }
    out = finalize_ranked_payload_authority(payload)
    assert out["opportunities"][0].get("effective_action")
    assert out["near_miss"][0].get("effective_action")


def test_build_decision_authority_keeps_canonical_deploy_ceiling():
    authority = build_decision_authority(
        tradeability="SELECTIVE",
        should_trade=True,
        fallback_brief=False,
        broker_offline=False,
        engine_off=False,
        exec_blocked=False,
        data_stale=False,
    )
    assert authority["authority_level"] == "deploy"
    assert authority["effective_action_max"] == "DEPLOY"
    assert authority["display_action_max"] == "WATCH"


def test_finalize_ranked_payload_authority_respects_engine_off_from_execution_readiness():
    payload = {
        "source": "ranked_pipeline",
        "best_action": {
            "tradeability": "SELECTIVE",
            "execution_readiness": {"engine_running": False, "circuit_breaker": False},
        },
        "opportunities": [
            {"ticker": "A", "action": "TRADE", "score": 7.0, "risk_reward": 2.0},
        ],
    }
    out = finalize_ranked_payload_authority(payload)
    assert out["decision_authority"]["gates"]["engine_off"] is True


def test_runtime_truth_uses_breaker_trigger_not_object_truthiness():
    class _Breaker:
        triggered = False
        trigger_reason = ""

    class _Engine:
        _running = True
        dry_run = True
        _cycle_count = 3
        _cached_recommendations = []
        _signals_today = []
        _trades_today = []
        circuit_breaker = _Breaker()

    snap = engine_runtime_snapshot(_Engine())
    merged = merge_execution_runtime_truth({}, engine=_Engine())
    assert snap["circuit_breaker"] is False
    assert merged["circuit_breaker"] is False
    assert merged["engine_running"] is True


def test_score_reconciliation_flags_divergence():
    rows = [
        {
            "ticker": "X",
            "score": 8.0,
            "evidence_quality": {"validated_score": 8.0, "raw_score": 5.0},
        }
    ]
    assert row_has_council_scanner_divergence(rows[0])
    rec = build_score_reconciliation(rows)
    assert rec["active"] is True
    assert "do not size on rank alone" in rec["message"].lower()
    assert "X" in rec["divergent_tickers"]


def test_index_html_playbook_near_miss_upgrade_helper():
    html = open("src/api/templates/index.html", encoding="utf-8").read()
    assert "playbookNearMissUpgradeLine()" in html
    assert "playbookNearMissUpgradeLine(){" in html.replace(" ", "")


def test_index_html_track_record_gate_helper():
    html = open("src/api/templates/index.html", encoding="utf-8").read()
    assert "trackRecordGateLine()" in html
    assert "NO TRACK RECORD" in html
