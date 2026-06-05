"""Template + formatter integrity — no JS leaks, no [object Object]."""

from __future__ import annotations

from pathlib import Path

from src.services.ui_render_safety import (
    assert_template_render_safe,
    contains_js_leak_fragment,
    find_alpine_html_break_leaks,
    format_visible_value,
    sanitize_visible_text,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
DEPLOY_PARTIAL = (
    ROOT / "src" / "api" / "templates" / "cc" / "partials" / "deploy_surfaces.html"
)


def test_index_html_passes_render_safe():
    assert_template_render_safe([INDEX_HTML])


def test_no_js_leak_fragment_in_sanitize():
    dirty = "led',e);alert('Auto-schedule failed: '+e.message)} }, }}"
    assert sanitize_visible_text(dirty) == ""


def test_format_visible_value_never_object_object():
    assert format_visible_value({"foo": "bar"}) == "—"
    assert format_visible_value({"label": "Tier A"}) == "Tier A"
    assert format_visible_value("[object Object]") == "Evidence unavailable"


def test_contains_js_leak_detects_auto_schedule_tail():
    assert contains_js_leak_fragment("led',e);alert('Auto-schedule failed: '+e.message)}")


def test_index_html_has_playbook_funnel_helpers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookFunnelLabel" in raw
    assert "playbookLayerDefinitions" in raw
    assert "playbookLayerDefinitionsNote" in raw
    assert "playbookUnlockConditionDetail" in raw
    assert "canonicalRegimeLine" in raw
    assert "playbookEvidenceLine" in raw
    assert "watch-qualified" in raw
    assert "playbookCardPrimaryBlocker" in raw
    assert "upgrade layer" in raw
    assert "Full live board" not in raw
    assert "playbookUseCompactCards(r)" in raw
    assert 'x-show="!playbookUseCompactCards(r)"' in raw


def test_index_html_kpi_pipeline_labels_not_deploy_ideas_static():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "kpiDeployQualifiedLabel" in raw
    assert "kpiWatchQualifiedLabel" in raw
    assert "kpiWatchQualifiedHint" in raw
    assert "kpiScannedLabel" in raw
    assert "kpi-lbl-pipeline" in raw
    assert "'deploy-qualified'" in raw
    assert "'watch-qualified'" in raw
    assert "'scanned'" in raw
    assert "Watch candidates" not in raw
    assert "kpiPipelineFilteredLabel" not in raw
    assert '<div class="kpi-lbl">Deploy ideas</div>' not in raw


def test_index_html_stale_market_data_downgrade_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "marketStripStaleDowngrade" in raw
    assert "marketStripSnapshotLine" in raw
    assert "marketStripRenderLine" in raw
    assert "Snapshot as of" in raw
    assert "Historical snapshot only" in raw
    assert "Not suitable for execution decisions" in raw
    assert "Refresh required for decision use" in raw


def test_index_html_flow_summary_degraded_helpers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "flowOverlayDegraded" in raw
    assert "flowOverlayDegradedShort" in raw
    assert "Flow overlay unavailable" in raw
    assert "No live flow overlay" in raw
    assert "Fallback only" in raw


def test_index_html_has_no_inline_js_leak_substring():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "led',e);alert(" not in raw
    assert "scheduleAuto" not in raw
    # Inline catch+alert on one line was the leak vector — must use handler method
    assert "_handleAutoScheduleError" in raw


def test_index_html_pm_strip_no_literal_trade_prefix_on_wait():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "pmDecisionTickerLine()" in raw
    assert "'TRADE '+(today7.todays_decision.best_trade" not in raw


def test_index_html_playbook_ibkr_handoff_gated_by_effective_grade():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookCanSendToIbkr(r)" in raw
    assert "(r.action==='TRADE'||r.action==='BUY')&&r.execution_ready" not in raw


def test_index_html_ibkr_trust_strip_distinguishes_gateway_login():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "ibkrTrustStripLabel" in raw
    idx = raw.index("ibkrTrustStripLabel(){")
    body = raw[idx : idx + 900]
    assert "st.gw&&!st.connected" in body
    assert "GATEWAY UP" in body or "st.label" in body


def test_index_html_legacy_opps_use_effective_card_action():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    idx = raw.index("Fallback to legacy opps")
    block = raw[idx : idx + 1200]
    assert "effectiveCardAction(r)" in block
    assert "playbookOppsFallbackVisible()" in block


def test_index_html_dashboard_actionable_uses_effective_grade():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dashboardActionablePicks()" in raw
    assert "o.action==='BUY'||o.action==='TRADE'" not in raw
    assert "effectiveCardAction(pick)" in raw


def test_index_html_dashboard_best_trade_label_respects_deploy_gate():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dashboardBestActionLabel('trade')" in raw
    assert '<div style="color:var(--t3)">Best TRADE</div>' not in raw


def test_index_html_instant_degraded_banner_helpers():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "instantDegradedBannerVisible()" in raw
    assert "instantDegradedBannerLine()" in raw
    assert "fetchHealth()" in raw
    assert "INSTANT DEGRADED" in raw


def test_index_html_ai_commentary_warmup_errors():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "fetchAINarrative()" in raw
    assert "/api/v7/today/ai-narrative" in raw
    block = raw[raw.find("async fetchAINarrative(") : raw.find("async fetchRanked(")]
    assert "surfaceWarmupLoadingLine('dashboard')" in block
    assert "normalizeFetchError" in block
    assert "aiCommentaryCtaLabel()" in raw
    assert "today7.ai_provider='loading'" in block
    assert "ai_provider==='loading'" in raw


def test_index_html_ibkr_recovery_hint_state_driven():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    idx = raw.index("ibkrLoginToReadyHint(){")
    body = raw[idx : idx + 700]
    assert "ibkrStateFrom(this.today7.execution_readiness" in body
    assert "IBKR OFFLINE" in body
    assert "IBKR LOGIN" in body


def test_index_html_flow_kpi_pipeline_structure():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "flowKpiLabel()" in raw
    assert "flowKpiSubLabel()" in raw
    idx = raw.index("flowKpiLabel(){")
    assert "return 'flow'" in raw[idx : idx + 80]


def test_index_html_mission_monitors_fallback_label():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "Fallback monitors" in raw
    idx = raw.index("todayMissionMonitorsColumnHint(){")
    body = raw[idx : idx + 600]
    assert "watchQualified" in body
    assert "filter_funnel" in body


def test_cc_instant_degraded_banner_contract():
    source = (ROOT / "_cc_instant.py").read_text(encoding="utf-8")
    assert "DEGRADED_BANNER" in source
    assert "_stamp_instant_degraded" in source
    assert "_encode_degraded" in source
    assert "degraded_banner" in source


def test_index_html_playbook_empty_state_kinds():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "kind:'FETCH_FAILED'" in raw
    assert "kind:'WAIT_DAY_OK'" in raw
    assert "kind:'WARMING'" in raw


def test_index_html_no_portfolio_strip_js_leaks():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "+pf.summary.total_value.toLocaleString()" not in raw
    assert "portfolioSummaryPositionsLabel()+' · $'+pf" not in raw
    assert 'total_positions>0"' not in raw
    assert "portfolioSummaryStripLine()" in raw
    assert "portfolioSummaryStripVisible()" in raw
    assert "riskAlertsStripVisible()" in raw


def test_deploy_surfaces_partial_no_alpine_html_breaks():
    hits = find_alpine_html_break_leaks(DEPLOY_PARTIAL)
    assert hits == [], f"deploy_surfaces.html leaks: {hits}"
    raw = DEPLOY_PARTIAL.read_text(encoding="utf-8")
    assert "portfolioSummaryStripLine()" in raw
    assert "riskAlertsStripLine()" in raw


def test_index_html_single_cc_app_no_duplicate_blocks():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert raw.count("function cc(){return{") == 1
    assert raw.count('<!-- @cc-partial deploy_surfaces -->') == 1
    assert raw.count('data-cc="playbook-surface"') == 1
    assert raw.count("<!-- ══════ ALPINE JS ══════ -->") == 1
    html_only = raw[raw.index("<body") : raw.index("<!-- ══════ ALPINE JS ══════ -->")]
    assert "+pf.summary.total_value.toLocaleString()" not in html_only
    assert "portfolioSummaryPositionsLabel()+' · $'+pf" not in html_only
    assert html_only.count("Near-miss · upgrade layer") == 1
    assert html_only.count('class="fade" data-cc="playbook-surface"') == 1


def test_index_html_playbook_unlock_detail_uses_filter_funnel_when_watch_positive():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    idx = raw.index("playbookUnlockConditionDetail(c){")
    body = raw[idx : idx + 1200]
    assert "filter_funnel" in body
    assert "playbookFunnelCounts" in body
    assert "scan-ranked (not watch-qualified)" in body
    assert "wq>0" in body or "Number(wq)>0" in body or "if(wq>0)" in body


def test_build_cc_template_check_passes():
    import subprocess

    root = INDEX_HTML.resolve().parents[3]
    proc = subprocess.run(
        ["node", "scripts/build-cc-template.mjs", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
