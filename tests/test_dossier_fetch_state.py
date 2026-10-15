"""Dossier fetch-failed UX — research-specific copy and template wiring."""

from __future__ import annotations

from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.services.fetch_surface_state import (
    DOSSIER_SERVICE_DEFAULT,
    STATE_FAILED_FETCH,
    STATE_LOADING,
    STATE_PARTIAL,
    STATE_STALE,
    describe_dossier_fetch_state,
)
from src.services.surface_authority import build_header_summary

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_describe_dossier_fetch_failed_copy():
    copy = describe_dossier_fetch_state(STATE_FAILED_FETCH)
    assert copy["title"] == "Research unavailable"
    assert DOSSIER_SERVICE_DEFAULT in copy["explanation"]
    assert "Live dossier fetch failed" in copy["explanation"]
    assert copy["next_action"] == "This page is not decision-grade until research loads"
    assert copy["badge"] == "RESEARCH UNAVAILABLE"


def test_describe_dossier_fetch_failed_includes_service_and_detail():
    copy = describe_dossier_fetch_state(
        STATE_FAILED_FETCH,
        detail="HTTP 503",
        service="market_data_service",
    )
    assert "market_data_service" in copy["explanation"]
    assert "HTTP 503" in copy["explanation"]


def test_describe_dossier_loading_and_stale_copy():
    loading = describe_dossier_fetch_state(STATE_LOADING)
    assert loading["badge"] == "LOADING"
    assert "market_data_service" in loading["explanation"]

    stale = describe_dossier_fetch_state(STATE_STALE, service="cached_intel")
    assert stale["badge"] == "STALE"
    assert "cached_intel" in stale["explanation"]


def test_build_header_summary_dossier_failed_fetch():
    summary = build_header_summary(
        "dossier_research",
        {
            "error": "upstream timeout",
            "fetch_detail": "HTTP 503",
            "ticker": "JPM",
        },
    )
    assert summary["fetch_state"] == STATE_FAILED_FETCH
    assert summary["badge"] == "RESEARCH UNAVAILABLE"
    assert "Live dossier fetch failed" in summary["explanation"]
    assert (
        summary["next_action"] == "This page is not decision-grade until research loads"
    )
    assert any(chip["label"] == "JPM" for chip in summary["chips"])


def test_index_html_dossier_fetch_helpers_and_copy():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'x-show="dosShowsFetchBanner()"' in text
    assert '@click="fetchDossier({coreOnly:true})"' in text
    assert '@click="fetchDossierEnrichments()"' in text
    assert '@click="fetchDossier({useCached:true})"' in text
    run_dashboard_js("""
        for (const state of ['failed_fetch', 'partial', 'stale']) {
            const copy = app.dossierFetchStateCopy(
                state, 'brief-backed core', 'instant-degraded');
            assert.equal(copy.state, state);
            assert.equal(copy.badge, 'CONFIRM ONLY');
            assert.match(copy.next_action, /Retry|enrichments/);
        }
        const loading = app.dossierFetchStateCopy(
            'loading', '', 'market_data_service');
        assert.equal(loading.badge, 'LOADING');
        assert.match(loading.explanation, /market_data_service/);
        app.dos.ticker = 'JPM';
        app.dos.status = 'failed';
        app.dos.error = 'HTTP 503';
        app._syncDossierFetchHints();
        assert.equal(app.surfaceFetchHints.dossier.failed_fetch, true);
        assert.equal(app.dosShowsFetchBanner(), true);
        assert.equal(app.dosFetchBannerKind(), 'error');
        assert.equal(app.dosFetchBannerBadge(), 'CONFIRM ONLY');
    """)


def test_index_html_error_banner_does_not_repeat_ticker():
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index('x-show="dosShowsFetchBanner()"')
    end = text.index("</main>", start)
    banner = text[start:end]
    assert banner.count("x-text=\"dos.ticker||'Dossier'\"") == 1
    for field in ("now", "blocker", "next_action"):
        assert f'x-text="dossierPageOperatorCompact().{field}"' in banner
    assert banner.count("CONFIRM ONLY") == 1
    assert "No sizing · no handoff" in banner
    run_dashboard_js("""
        app.tab = 'dossier';
        app.dos.ticker = 'JPM';
        app.dos.status = 'failed';
        app.dos.error = 'HTTP 503';
        app.dos.missing_modules = ['quote', 'structure'];
        const compact = app.dossierPageOperatorCompact();
        assert.equal((compact.now.match(/JPM/g) || []).length, 1);
        assert.match(compact.blocker, /quote · structure/);
        assert.ok(compact.next_action.includes('no sizing/handoff'));
    """)


def test_describe_dossier_partial_instant_degraded_copy():
    copy = describe_dossier_fetch_state(
        STATE_PARTIAL,
        detail="brief-backed core",
        service="instant-degraded",
    )
    assert copy["badge"] == "RESEARCH ONLY"
    assert "instant-degraded" in copy["explanation"]
    assert "fetch failed" not in copy["explanation"].lower()
    assert "IBKR" in copy["next_action"]


def test_index_html_dossier_partial_banner_helpers():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'x-show="dosShowsFetchBanner()"' in text
    assert "dossierPageOperatorCompact().blocker" in text
    assert "dos.status==='partial_loaded'" in text
    run_dashboard_js("""
        app.dos.ticker = 'JPM';
        app.dos.data = {symbol: 'JPM', price: 100};
        app.dos.intel = {partial: true, load_phase: 'core'};
        app.dos.status = 'partial_loaded';
        app.dos.partialNotice = 'Missing research modules';
        app.dos.missing_modules = ['options', 'peers'];
        app._syncDossierFetchHints();
        assert.equal(app.surfaceFetchHints.dossier.partial, true);
        assert.equal(app.surfaceFetchHints.dossier.failed_fetch, false);
        assert.equal(app.dosShowsFetchBanner(), true);
        assert.equal(app.dosFetchBannerKind(), 'partial');
        assert.match(app.dosFetchBannerMissingLine(), /options · peers/);
        assert.equal(app.dossierActionsBlocked(), true);
        assert.equal(app.dossierExecutionHidden(), true);
        app.dos.status = 'stale_fallback';
        app.dos.error = 'Live fetch unavailable';
        app._syncDossierFetchHints();
        assert.equal(app.surfaceFetchHints.dossier.stale, true);
        assert.equal(app.surfaceFetchHints.dossier.failed_fetch, false);
        assert.equal(app.dosFetchBannerKind(), 'stale');
        assert.equal(app.dossierResearchOnly(), true);
        app.dos.status = 'idle_no_query';
        assert.equal(app.dosShowsFetchBanner(), false);
    """)


def test_index_html_surface_fetch_error_line_handles_dossier():
    run_dashboard_js("""
        app.dos.data = {trust: {source: 'test_provider'}};
        const errors = [
            'Failed to fetch', 'NetworkError', 'HTTP 0', 'HTTP 503'];
        for (const error of errors) {
            assert.match(app.surfaceFetchErrorLine(error, 'dossier'),
                /Live dossier fetch failed from test_provider/);
        }
        assert.doesNotMatch(
            app.surfaceFetchErrorLine('Failed to fetch', 'signals'),
            /Live dossier fetch failed/);
        assert.equal(app.surfaceFetchErrorLine('HTTP 403', 'dossier'),
            'HTTP 403');
    """)


def test_index_html_dossier_sizing_gated_when_research_only():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierSizingBlocked()" in text
    assert "dosSizeDisplay()" in text
    assert "dosSizeExplanationVisible()" in text
    assert "dosPriceDisplay()" in text
    assert ':disabled="dossierActionsBlocked()"' in text
    # Trade plan table must not render raw share counts unconditionally
    trade_plan = text[text.find("Trade plan") : text.find("Trade plan") + 2500]
    assert "dosSizeDisplay()" in trade_plan
    assert "dosSizeShares()+' sh'" not in trade_plan
    run_dashboard_js("""
        app.dos.ticker = 'JPM';
        app.dos.status = 'loaded';
        app.dos.data = {symbol: 'JPM', price: 100};
        app.dos.intel = {unified_decision: {
            label: 'CONFIRM ONLY', rr_ratio: 3},
            size_info: {shares: 500}};
        const before = JSON.stringify(app.ibkr.orderForm);
        assert.equal(app.dossierSizingBlocked(), true);
        assert.equal(app.dossierActionsBlocked(), true);
        assert.equal(app.dosSizeShares(), 0);
        assert.equal(app.dosSizeDisplay(), '—');
        app.dosIbkrPaperDraft();
        app.dosIbkrSetAlert();
        assert.equal(JSON.stringify(app.ibkr.orderForm), before);
        assert.equal(alerts.length, 2);
        assert.deepEqual(app.dossierConfirmOnlyScreen().blocked,
            ['Trade plan', 'Sizing', 'Paper order', 'IBKR handoff']);
        app.dos.intel = {unified_decision: {label: 'TRADE', rr_ratio: 3,
            confidence_pct: 75, confidence: 0.75}, size_info: {shares: 25}};
        assert.equal(app.dossierSizingBlocked(), false);
        assert.equal(app.dosSizeShares(), 25);
        app.dos.intel.unified_decision.rr_ratio = null;
        assert.equal(app.dossierSizingBlockedReason(), 'rr_unavailable');
        assert.equal(app.dosSizeShares(), 0);
    """)
