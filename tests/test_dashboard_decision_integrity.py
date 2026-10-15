"""Dashboard decision integrity — card grades vs page authority gates."""

from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.services.decision_truth_model import (
    DASHBOARD_KPI_PIPELINE_LABELS,
    FLOW_OVERLAY_DEGRADED_HEADLINES,
    FLOW_OVERLAY_DEGRADED_SHORT,
    PLAYBOOK_FUNNEL_LAYER_DEFINITIONS,
    apply_authority_to_row,
    assemble_confidence_breakdown,
    build_decision_authority,
    effective_card_grade,
    playbook_funnel_layer_note,
)


def test_wait_trade_card_downgraded():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=True,
        scanner_degraded=True,
    )
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "execution_ready": True,
            "risk_reward": 3.0,
            "thesis_conf": 0.8,
            "timing_conf": 0.7,
            "exec_conf": 0.6,
            "data_conf": 0.6,
        },
        authority,
    )
    assert row["action"] != "TRADE"
    assert row["action"] in ("WATCH ONLY", "RESEARCH ONLY", "NOT EXECUTION-GRADE")


def test_fallback_row_not_trade():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=False,
        fallback_brief=True,
    )
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "risk_reward": 2.8,
            "card_display_mode": "reference_only",
            "thesis_conf": 0.7,
            "timing_conf": 0.7,
            "exec_conf": 0.6,
            "data_conf": 0.6,
        },
        authority,
    )
    assert row["action"] == "FALLBACK WATCH"
    assert (
        row.get("confidence_fallback_only")
        or row.get("card_display_mode") == "reference_only"
    )


def test_confidence_all_zero_unavailable():
    row = {
        "thesis_conf": 0,
        "timing_conf": 0,
        "exec_conf": 0,
        "data_conf": 0,
        "confidence": 0.6,
    }
    conf = assemble_confidence_breakdown(row)
    out = apply_authority_to_row(row, build_decision_authority(fallback_brief=True))
    assert conf["final"] is None
    assert conf["unavailable"] is True
    assert out["final_conf"] is None
    assert out["confidence_unavailable"] is True


def test_rr_null_not_trade():
    authority = build_decision_authority(
        tradeability="TRADE",
        should_trade=True,
    )
    authority["allows_trade_labels"] = True
    authority["gates_active"] = False
    row = {
        "action": "TRADE",
        "raw_action": "TRADE",
        "execution_ready": True,
        "risk_reward": None,
        "thesis_conf": 0.8,
        "timing_conf": 0.7,
        "exec_conf": 0.6,
        "data_conf": 0.6,
    }
    assert effective_card_grade(row, authority) == "INCOMPLETE"
    out = apply_authority_to_row(row, authority)
    assert out["action"] == "INCOMPLETE"


def test_stale_snapshot_degraded_labels():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=True,
        data_stale=True,
        ranked_source="disk-snapshot",
        ranked_stale=True,
    )
    dc = authority.get("degraded_copy") or {}
    lines = dc.get("stale_snapshot_lines") or []
    assert authority["source"] == "stale_cache"
    assert "Historical snapshot only" in lines
    assert "Not suitable for execution decisions" in lines
    assert "Refresh required for decision use" in lines
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "execution_ready": True,
            "risk_reward": 3.0,
        },
        authority,
    )
    assert row["action"] == "REFERENCE ONLY"


def test_dashboard_kpi_pipeline_labels_aligned():
    assert DASHBOARD_KPI_PIPELINE_LABELS == (
        "scanned",
        "watch-qualified",
        "deploy-qualified",
    )
    assert "scanned" in PLAYBOOK_FUNNEL_LAYER_DEFINITIONS
    assert "watch_qualified" in PLAYBOOK_FUNNEL_LAYER_DEFINITIONS
    assert "deploy_qualified" in PLAYBOOK_FUNNEL_LAYER_DEFINITIONS
    note = playbook_funnel_layer_note()
    assert "Scanned = universe evaluated" in note
    assert "Watch-qualified" in note
    assert "Deploy-qualified" in note


def test_dashboard_kpi_watch_qualified_uses_funnel_only():
    """Dashboard KPI counts must not inflate from ranked or near-miss rows."""
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert 'x-text="kpiWatchQualifiedCount()"' in raw
    assert 'x-text="kpiDeployQualifiedCount()"' in raw
    run_dashboard_js("""
        app.today7.top_ranked = [
            {action: 'WATCH'}, {action: 'TRADE', execution_ready: true}];
        app.today7.near_miss = [{ticker: 'A'}, {ticker: 'B'}];
        app.rankedOpps.rows = app.today7.top_ranked;
        app.rankedOpps.filter_funnel = {
            watch_qualified_setups: 99, deploy_qualified_setups: 88};
        for (const [watch, deploy] of [[0, 0], [2, 1]]) {
            app.today7.filter_funnel = {
                watch_qualified_setups: watch,
                deploy_qualified_setups: deploy};
            assert.equal(app.kpiWatchQualifiedCount(), watch);
            assert.equal(app.kpiDeployQualifiedCount(), deploy);
        }
        app.today7.filter_funnel = null;
        assert.equal(app.kpiWatchQualifiedCount(), 0);
        assert.equal(app.kpiDeployQualifiedCount(), 0);
    """)


def test_dashboard_and_playbook_funnel_share_filter_funnel_field():
    """Both surfaces read watch_qualified_setups from filter_funnel (today vs ranked)."""
    from src.services.decision_truth_model import normalize_playbook_funnel

    funnel = normalize_playbook_funnel(
        {
            "universe_scanned": 50,
            "watch_qualified_setups": 0,
            "deploy_qualified_setups": 0,
            "high_score_setups": 12,
        },
        near_miss=[{"ticker": "A"}, {"ticker": "B"}, {"ticker": "C"}],
    )
    assert funnel["watch_qualified_setups"] == 0
    assert funnel["universe_scanned"] == 50


def test_flow_overlay_degraded_copy_contract():
    assert FLOW_OVERLAY_DEGRADED_HEADLINES["synthetic"] == "No live flow overlay"
    assert FLOW_OVERLAY_DEGRADED_HEADLINES["offline"] == "Flow overlay unavailable"
    assert FLOW_OVERLAY_DEGRADED_SHORT["synthetic"] == "Fallback only"
    assert FLOW_OVERLAY_DEGRADED_SHORT["offline"] == "No live overlay"
    assert FLOW_OVERLAY_DEGRADED_SHORT["uncalibrated"] == "Unavailable"


def test_fallback_confidence_label_non_comparable():
    authority = build_decision_authority(
        tradeability="WAIT",
        should_trade=False,
        fallback_brief=True,
    )
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "thesis_conf": 0,
            "timing_conf": 0,
            "exec_conf": 0,
            "data_conf": 0,
            "confidence": 0.6,
            "evidence_badge": "fallback-brief",
        },
        authority,
    )
    conf = assemble_confidence_breakdown(row)
    assert conf["label"] == "Fallback estimate — non-comparable"
    assert row.get("confidence_label") == "Fallback estimate — non-comparable"


def test_dashboard_actionable_filter_excludes_raw_trade_on_wait():
    """Deploy picks must respect authority — WAIT day downgrades TRADE rows."""
    authority = build_decision_authority(tradeability="WAIT", should_trade=True)
    row = apply_authority_to_row(
        {
            "action": "TRADE",
            "raw_action": "TRADE",
            "execution_ready": True,
            "risk_reward": 3.0,
        },
        authority,
    )
    assert row["action"] != "TRADE"
    assert row["action"] in (
        "WATCH ONLY",
        "RESEARCH ONLY",
        "REFERENCE ONLY",
        "NOT EXECUTION-GRADE",
    )


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_index_html_unified_empty_state_and_card_score_helpers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert 'x-text="playbookEmptyState().title"' in raw
    assert 'x-text="playbookEmptyState().detail"' in raw
    assert 'x-text="playbookEmptyState().badge"' in raw
    assert 'x-text="cardScoreLabel(opp)"' in raw
    assert ':class="cardScorePillClass(r)"' in raw
    run_dashboard_js("""
        app.today7.tradeability = 'WAIT';
        app.rankedOpps.loading = true;
        app.rankedOpps.fetch_failed = true;
        assert.equal(app.surfaceEmptyState('signals').kind, 'WARMING');
        app.rankedOpps.loading = false;
        assert.equal(app.playbookFetchFailed(), true);
        assert.equal(app.surfaceEmptyState('signals').kind, 'FETCH_FAILED');
        assert.equal(app.playbookEmptyState().badge, 'FETCH FAILED');
        app.rankedOpps.fetch_failed = false;
        assert.equal(app.surfaceEmptyState('signals').kind, 'WAIT_DAY_OK');
        assert.equal(app.playbookEmptyState().badge, 'WAIT DAY OK');
        assert.equal(app.surfaceEmptyState('other').kind, 'NO_DATA');
        assert.equal(app.cardScoreLabel({score: 8.25}), '8.3');
        assert.equal(app.cardScorePillClass({score: 8.25}), 'pg');
        assert.equal(app.cardScoreLabel({}), '—');
        const fallback = {score: 9, score_display_mode: 'fallback_rank'};
        assert.equal(app.cardScoreLabel(fallback), 'Fallback rank · high');
        assert.equal(app.cardScorePillClass(fallback), 'pa');
    """)


def test_index_html_confidence_component_pct_not_zero_literal():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "confidenceComponentPct(val)" in raw
    assert "confidenceBannerLine(opp)" in raw
    assert "confidenceFinal(opp)" in raw


def test_index_html_market_strip_refresh_when_stale():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "Refresh market data" in raw
    assert "marketStripStaleDowngradeLines()" in raw
