"""Guide operator manual and advisory briefing API integrity."""

from __future__ import annotations

from pathlib import Path

from _dashboard_html_contract import bindings
from _dashboard_js_runtime import run_dashboard_js

from src.services.guide_briefing import load_guide_briefing

ROOT = Path(__file__).resolve().parents[1]
GUIDE_PARTIAL = ROOT / "src/api/templates/cc/partials/guide.html"
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_load_guide_briefing_returns_current_five_advisory_prompts():
    data = load_guide_briefing()
    assert {p["id"] for p in data["prompts"]} == {
        "authority_audit",
        "ops_diagnostics",
        "i18n_strategy",
        "discord_setup",
        "research_vs_deploy_boundary",
    }
    assert len(data["prompts"]) == 5
    assert data["missing"] is False
    assert data["full_markdown"]
    assert data["full_markdown"].startswith("# CC X")
    assert "TradingAI_Bot" in data["full_markdown"]
    assert data["doc_path"] == "docs/CC_X_ARCHITECTURE.md"
    assert "deploy authority" in data["authority_note"].lower()


def test_guide_briefing_prompt_titles_bilingual():
    data = load_guide_briefing()
    titles = {p["title_en"] for p in data["prompts"]}
    assert "Authority audit" in titles
    assert "Research vs deploy boundary" in titles
    for p in data["prompts"]:
        assert " · " in p["title"]
        assert p["title_zh"]
        assert p["text"]


def test_guide_briefing_scrubs_obvious_secrets():
    data = load_guide_briefing()
    body = data["full_markdown"]
    assert "sk-" not in body.lower() or "[REDACTED]" in body


def test_guide_partial_project_briefing_panel():
    """Guide is the committed operator manual, not the removed advisory panel."""
    html = GUIDE_PARTIAL.read_text(encoding="utf-8")
    assert "Operator Manual" in html
    assert "Reference-only" in html
    assert "cc-project-briefing-panel" not in html
    assert "sec in guideSections" in bindings(GUIDE_PARTIAL, "x-for")
    assert "guideSection=sec.id" in bindings(GUIDE_PARTIAL, "@click")
    assert "sec.label" in bindings(GUIDE_PARTIAL, "x-text")
    assert {
        "guideSection==='quickstart'",
        "guideSection==='advanced'",
        "guideSection==='reference'",
    } <= set(bindings(GUIDE_PARTIAL, "x-show"))


def test_cc_app_guide_briefing_helpers():
    run_dashboard_js("""
        assert.equal(app.guideSection, 'quickstart');
        assert.equal(app.guideTab.id, 'guide');
        assert.deepEqual(Array.from(app.guideSections, s => s.id),
            ['quickstart', 'advanced', 'reference']);
        for (const section of app.guideSections) {
            assert.ok(section.label);
            app.guideSection = section.id;
            assert.equal(app.guideSectionLabel(), section.label);
            for (const other of app.guideSections)
                assert.equal(app.guideLayerVisible(other.id),
                    other.id === section.id);
        }
        // Guide navigation refreshes the header, not advisory briefing.
        app.onAttentionBudgetTabChange = () => {};
        app.logSurfaceUsage = () => {};
        let refreshes = 0;
        app.fetchCcStatus = () => { refreshes++; };
        app.switchTab('guide');
        assert.equal(app.tab, 'guide');
        assert.equal(refreshes, 1);
        assert.equal(app.tabAuthorityChip().authority, 'suspended');
        assert.equal(app.contextDecisionBar(), null);
    """)


def test_index_html_guide_briefing_panel_inlined():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "cc-project-briefing-panel" not in raw
    assert GUIDE_PARTIAL.read_text(encoding="utf-8").strip() in raw
    assert "switchTab('today')" in bindings(GUIDE_PARTIAL, "@click")
    assert "switchTab('signals');fetchRanked()" in bindings(GUIDE_PARTIAL, "@click")
