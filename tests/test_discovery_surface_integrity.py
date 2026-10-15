"""Discovery tab integrity — no JS leaks, fallback scores, research-only header."""

from __future__ import annotations

from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.engines.scanner_matrix import ScannerCategory, ScannerHit, ScannerMatrix
from src.services.surface_authority import AUTHORITY_RESEARCH, resolve_authority
from src.utils.ui_render_safety import (
    assert_template_render_safe,
    contains_js_leak_fragment,
    find_js_leaks_in_file,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
JS_LEAK_SUBSTRING = "led',e);alert('Auto-schedule failed: '+e.message)} }, }}"


def test_index_html_has_no_auto_schedule_js_leak_substring():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert JS_LEAK_SUBSTRING not in text
    assert "}}, }}" not in text
    close = text.lower().rfind("</html>")
    assert close >= 0
    assert not contains_js_leak_fragment(text[close + len("</html>") :])
    assert find_js_leaks_in_file(INDEX_HTML) == []


def test_index_html_passes_render_safe_guard():
    assert_template_render_safe([INDEX_HTML])


def test_fallback_score_and_research_bindings():
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index('data-cc="discovery-surface"')
    discovery = text[start : text.index("</main>", start)]
    for binding in (
        'x-text="scannerScoreLabel(h)"',
        'x-text="discoveryVerdictQualityLabel()"',
        "scannerDiscoveryHitsLabel()",
        'x-text="discoveryConfidenceLine(h)"',
        'x-text="discoveryPrimaryHeadline()"',
        'x-text="discoveryPrimaryBlockerLine()"',
        'x-text="discoveryPrimaryNextActionLine()"',
        'x-text="discoveryEmptyState().badge"',
        'x-text="scannerPageGateLabel()"',
    ):
        assert binding in discovery
    assert 'x-text="researchOnlyBannerLine()"' in text
    assert 'src="/static/cc-helpers.js"' in text
    run_dashboard_js("""
        app.tab = 'scanners';
        app.today7.tradeability = 'WAIT';
        assert.equal(app.discoveryHeaderMode(), true);
        for (const [score, tier] of [[7.5, 'high'], [7.49, 'medium'],
            [6, 'medium'], [5.99, 'low']]) {
            const row = {score, score_display_mode: 'fallback_rank'};
            assert.equal(app.formatFallbackScore(row),
                'Fallback rank · ' + tier);
            assert.equal(app.scannerScoreLabel(row),
                'Fallback rank · ' + tier);
            assert.equal(app.discoveryConfidenceLabel(row),
                'estimated confidence');
        }
        const missingScore = {score_display_mode: 'fallback_rank'};
        assert.equal(app.formatFallbackScore(missingScore),
            'Indicative rank (fallback)');
        assert.equal(app.scannerScoreLabel({score: 8}), 'Score 8');
        app.scannerHub.error = 'HTTP 503';
        app.scannerHub.data = {hits: [{ticker: 'QCOM'}]};
        assert.equal(app.scannerDiscoveryHasFallbackRows(), true);
        assert.equal(app.discoveryVerdictQualityLabel(),
            'FETCH FAILED · heuristic');
        assert.equal(app.scannerDiscoveryFetchHintLine(), '');
        assert.match(app.discoveryFallbackBannerLine(),
            /Research-only fallback/);
        app.scannerHub.data = null;
        assert.equal(app.surfaceEmptyState('scanners').kind, 'FETCH_FAILED');
    """)


def test_enrich_hit_fallback_rank_uses_tier_not_deploy_score():
    hit = ScannerHit(
        ticker="QCOM",
        scanner_name="leaders",
        category=ScannerCategory.PATTERN,
        score=9.0,
        headline="test",
    )
    payload = ScannerMatrix.enrich_hit_for_ui(hit, score_display_mode="fallback_rank")
    assert payload["score_display_mode"] == "fallback_rank"
    assert payload["priority_tier"] == "High"
    assert payload["score_display"] == "High"
    assert payload["score_display_label"] == "Fallback rank · high"
    assert payload["score_source"] == "brief-fallback"
    assert payload["strength"] == 9.0


def test_fallback_priority_tier_bands():
    assert ScannerMatrix.fallback_priority_tier(9.0) == "High"
    assert ScannerMatrix.fallback_priority_tier(6.5) == "Medium"
    assert ScannerMatrix.fallback_priority_tier(4.2) == "Low"


def test_discovery_surface_authority_wait_is_research_only():
    auth = resolve_authority(
        "discovery",
        tradeability="WAIT",
        deployable_count=0,
    )
    assert auth["authority"] == AUTHORITY_RESEARCH
    assert any("research-only" in r.lower() for r in auth["reasons"])
