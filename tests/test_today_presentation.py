"""Today regressions. Fixtures are SYNTHETIC, never market facts."""

import gzip
from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js
from src.services.ui_render_safety import assert_template_render_safe

ROOT = Path(__file__).resolve().parents[1]


def test_initial_loading_error_and_completed_empty_are_distinct():
    run_dashboard_js("""
        app.today7.tradeability = 'WAIT';
        assert.equal(app.dashboardEmptyState().kind, 'WARMING');
        assert.equal(app.surfaceEmptyState('today').kind, 'WARMING');
        app.todayFetch.loading = true;
        assert.equal(app.dashboardEmptyState().kind, 'WARMING');
        app.todayFetch.loading = false;
        app.todayFetch.error = 'SYNTHETIC HTTP 503';
        assert.equal(app.dashboardEmptyState().kind, 'FETCH_FAILED');
        assert.equal(app.missionControlLoading(), false);
        app.todayFetch.error = '';
        app.todayFetch.completed = true;
        app.today7.regime = {tradeability: 'WAIT'};
        assert.equal(app.dashboardEmptyState().kind, 'WAIT_DAY_OK');
        app.today7.trust = {stale: true, source: 'local-cache'};
        assert.equal(app.dashboardEmptyState().kind, 'UNAVAILABLE');
    """)


def test_populated_blocked_and_rejected_results_are_not_empty():
    run_dashboard_js("""
        app.todayFetch.completed = true;
        app.today7.regime = {tradeability: 'WAIT'};
        for (const field of ['top_ranked', 'near_miss', 'avoid_list']) {
            app.today7[field] = [{ticker: 'SYNTH', action: 'BLOCKED'}];
            assert.equal(app.dashboardHasNoBoardData(), false);
            assert.equal(app.dashboardEmptyState().kind, 'BOARD_PRESENT');
            app.today7[field] = [];
        }
        app.today7.dashboard_monitors = ['SYNTH'];
        assert.equal(app.dashboardHasNoBoardData(), false);
        assert.equal(app.todayResearchNames()[0], 'SYNTH');
        assert.match(app.todayPresentationQuestions().act,
            /No new deployment authority/);
    """)


def test_missing_trust_quality_and_confidence_are_not_reassuring_defaults():
    run_dashboard_js("""
        assert.equal(app.todayEvidenceModeLabel(), 'Mode unverified');
        assert.equal(app.todayEvidenceFreshnessLabel(), 'Freshness unknown');
        assert.match(app.todayEvidenceSourceLine(), /Source unavailable/);
        assert.match(app.todayPresentationQuestions().believe, /not assessed/);
        app.today7.regime = {};
        assert.equal(app.todayConfidencePct(), null);
        assert.equal(app.todayConfidenceLabel(), 'Confidence unavailable');
        for (const bad of [null, '', ' ', NaN, Infinity, false, {}, 2, -1]) {
            app.today7.regime.confidence = bad;
            assert.equal(app.todayConfidencePct(), null);
        }
        app.today7.regime.confidence = 0;
        assert.equal(app.todayConfidenceLabel(), '0%');
        app.today7.regime.confidence = 0.73;
        assert.equal(app.todayConfidenceLabel(), '73%');
        app.trust = {mode: 'LIVE', source: 'cc-header'};
        assert.equal(app.todayEvidenceModeLabel(), 'Mode unverified');
    """)


def test_market_evidence_and_provenance_survive_wait_without_authority():
    run_dashboard_js("""
        app.todayFetch.completed = true;
        app.today7.regime = {tradeability: 'WAIT', vix: 19, breadth: 0};
        app.today7.trust = {source: 'SYNTHETIC fixture',
            freshness: 'DELAYED', as_of: '2026-10-14T12:00:00Z'};
        app._marketStripFromLive({
            indices: [{symbol: 'SYNTH', price: 100, change_pct: 0}],
            sectors: [{symbol: 'SYNTHSEC', price: 100, change_pct: 1}],
            trust: app.today7.trust});
        const before = app.deployOpen();
        assert.match(app.todayMarketEvidenceLine(),
            /1 market rows · 1 sectors · SYNTH/);
        assert.match(app.todayMarketEvidenceLine(), /SYNTHETIC fixture/);
        assert.match(app.todayEvidenceSourceLine(), /2026-10-14T12:00:00Z/);
        assert.match(app.todayPresentationQuestions().know, /Breadth 0%/);
        assert.equal(app.deployOpen(), before);
        app.today7.trust.stale = true;
        assert.equal(app.todayEvidenceFreshnessLabel(),
            'STALE / reference only');
        app._marketStripFromLive({indices: [{symbol: 'MISSING'}]});
        assert.match(app.todayMarketEvidenceLine(),
            /Market evidence unavailable/);
    """)


def test_portfolio_missing_partial_zero_stale_and_risk_first():
    run_dashboard_js("""
        let p = app.todayPortfolioPresentation();
        for (const key of ['positions', 'value', 'pnl', 'heat'])
            assert.equal(p[key], 'Unavailable');
        assert.equal(app.portfolioSummaryPositionsLabel(),
            'Positions unavailable');
        app.pf.summary = {total_positions: 0, total_value: 0, total_pnl: 0};
        p = app.todayPortfolioPresentation();
        assert.equal(p.positions, '0');
        assert.equal(p.value, '$0');
        assert.equal(p.pnl, '$0');
        assert.equal(p.status, 'Confirmed empty book');
        app.pf.summary.total_value = null;
        assert.equal(app.todayPortfolioPresentation().value, 'Unavailable');
        assert.equal(app.portfolioSummaryMoneyLine('total_value'), '—');
        assert.equal(app.portfolioSummaryValueShortLine(),
            'Value unavailable');
        app.pf.summary.total_pnl = null;
        assert.equal(app.portfolioSummaryPnlLine(), '—');
        assert.equal(app.portfolioSummaryPnlIsPositive(), false);
        app.pf.positions = [{ticker: 'SYNTH', shares: 2,
            market_value: 200, stop_defined: false}];
        app.pf.summary.total_positions = 1;
        app.pf.alerts = [{message: 'SYNTHETIC stop warning'}];
        app.pfDecision = {portfolio_heat: {heat_available: true, heat_r: 0}};
        p = app.todayPortfolioPresentation();
        assert.equal(p.heat, 'Unavailable');
        assert.ok(p.warnings.some(w => /stop/i.test(w)));
        assert.match(p.next, /existing-book warnings before new allocation/);
        app.pf.ssotFallback = true;
        assert.match(app.todayPortfolioPresentation().source, /Browser cache/);
        app.pf.error = 'SYNTHETIC unavailable';
        assert.equal(app.todayPortfolioPresentation().status,
            'Book refresh failed');
        app.pf.positions = [];
        app.pf.error = '';
        app.pf.ssotFallback = false;
        assert.equal(app.todayPortfolioPresentation().heat, '0R');
    """)


def test_fetch_lifecycle_validates_same_hash_and_keeps_error_on_fallback():
    run_dashboard_js("""
        (async () => {
            app.hydrateToday7FromCache = () => {};
            app.playbookBridgeFromCaches = () => [];
            app.fetchWarmupBriefBoard = () => {};
            app.rebuildIdentifiedErrors = () => {};
            app.today7.regime = {tradeability: 'WAIT'};
            app.today7.top_ranked = [{ticker: 'SYNTH'}];
            app.today7.decision_board_hash = 'same';
            let response = {decision_board_hash: 'same',
                error: 'SYNTHETIC invalid'};
            app.ccFetch = async () => ({ok: true, json: async () => response});
            const pending = app.fetchToday7();
            assert.equal(app.todayFetch.loading, true);
            await pending;
            assert.equal(app.todayFetch.loading, false);
            assert.equal(app.todayFetch.completed, false);
            assert.equal(app.todayPresentationState(), 'error');
            response = {decision_board_hash: 'same',
                market_regime: {tradeability: 'WAIT'}, trust: {stale: false}};
            await app.fetchToday7();
            assert.equal(app.todayFetch.completed, true);
            assert.equal(app.todayFetch.error, '');
            assert.equal(app.todayFetch.loading, false);
            assert.equal(app.todayPresentationState(), 'ready');
        })()
    """)


def test_core_today_completion_does_not_wait_for_quant_enrichment():
    run_dashboard_js("""
        (async () => {
            app.buildDecisionHubFromToday = () => {};
            app.rebuildIdentifiedErrors = () => {};
            app.pmStrip.funds = [{}];
            let release;
            app.ccFetchJson = () => new Promise(resolve => {
                release = resolve;
            });
            app.ccFetch = async () => ({ok: true,
                json: async () => ({market_regime: {tradeability: 'WAIT'}})});
            const pending = app.fetchToday7();
            await Promise.resolve(); await Promise.resolve();
            assert.equal(app.todayFetch.completed, true);
            assert.equal(app.todayFetch.loading, false);
            assert.equal(app.dashboardEmptyState().kind, 'WAIT_DAY_OK');
            release({ok: false});
            await pending;
        })()
    """)


def test_replay_never_claims_live_evidence():
    run_dashboard_js("""
        app.replay.active = true;
        app.replay.loading = true;
        assert.equal(app.dashboardEmptyState().kind, 'WARMING');
        assert.match(app.todayEvidenceModeLabel(), /no live authority/);
        assert.equal(app.todayEvidenceFreshnessLabel(), 'Historical replay');
        app.replay.loading = false;
        app.replay.error = 'SYNTHETIC replay failure';
        assert.equal(app.dashboardEmptyState().kind, 'FETCH_FAILED');
        assert.match(app.todayPresentationQuestions().act,
            /no live authority/);
    """)


def test_single_mission_markup_preserves_warnings_and_demotes_duplicate_hero():
    html = (ROOT / "src/api/templates/index.html").read_text()
    path = ROOT / "src/api/templates/partials/today_mission_control.html"
    partial = path.read_text()
    assert_template_render_safe([path])
    assert html.count('data-cc="mission-control-card"') == 1
    assert partial.strip() in html
    for marker in ("today-portfolio-risk", "today-mission-blockers"):
        assert f'data-cc="{marker}"' in partial
    assert "Research monitors · no deploy authority" in partial
    assert '<details data-cc="today-decision-detail"' in html
    assert ">Today Focus<" not in html
    assert "today7.todays_decision.risk_blockers" in html
    assert "today7.todays_decision.why_not_aggressive" in html
    assert "today7.todays_decision.narrative_snippet" in html
    for fabricated in (
        "trust.mode||'LIVE'", "trust.source||'engine'",
        "trust.freshness||'REAL_TIME'", "confidence*100||50", "confidence||.5",
    ):
        assert fabricated not in html


def test_served_source_cache_and_both_gzip_assets_match():
    source = (ROOT / "src/api/static/cc-app.js").read_text()
    helpers = (ROOT / "src/api/static/cc-helpers.js").read_text()
    assert helpers.endswith(source)
    cache = ROOT / "data/cache/cc-helpers.bundle.js"
    # The isolated container deliberately mounts no writable host cache.
    if cache.exists():
        assert cache.read_text() == helpers
    html = (ROOT / "src/api/templates/index.html").read_bytes()
    for asset in (
        ROOT / ".dashboard.html.gz",
        ROOT / "src/api/static/cc-dashboard.html.gz",
    ):
        assert gzip.decompress(asset.read_bytes()) == html


def test_presentation_does_not_mutate_trade_gates_or_card_grade():
    run_dashboard_js("""
        app.today7.regime = {tradeability: 'WAIT'};
        app.today7.tradeability = 'WAIT';
        app.today7.decision_authority = {gates_active: true,
            allows_trade_labels: false, effective_action_max: 'WATCH'};
        const row = {ticker: 'SYNTH', action: 'TRADE',
            execution_ready: true, risk_reward: 3, conviction_tier: 'TRADE'};
        app.today7.top_ranked = [row];
        const before = [app.deployOpen(), app.effectiveCardAction(row),
            app.playbookCanSendToIbkr(row)];
        const authority = JSON.stringify(app.today7.decision_authority);
        for (const loading of [true, false]) {
            app.todayFetch.loading = loading;
            app.todayFetch.completed = !loading;
            app.todayPresentationQuestions();
            app.todayPortfolioPresentation();
            app.dashboardEmptyState();
        }
        const after = [app.deployOpen(), app.effectiveCardAction(row),
            app.playbookCanSendToIbkr(row)];
        assert.deepEqual(after, before);
        assert.equal(after[0], false);
        assert.equal(after[2], false);
        assert.equal(JSON.stringify(app.today7.decision_authority), authority);
        assert.equal(row.action, 'TRADE');
    """)
