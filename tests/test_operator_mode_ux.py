"""Operator Mode UX — Mission Brief, nav reorder, page gate strips."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"
CC_APP = ROOT / "src/api/static/cc-app.js"
DEPLOY_PARTIAL = ROOT / "src/api/templates/cc/partials/deploy_surfaces.html"
GUIDE_PARTIAL = ROOT / "src/api/templates/cc/partials/guide.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_today_is_default_tab():
    js = _read(CC_APP)
    assert 'return qs.get("tab") || "today"' in js
    assert 'ccNormalizeTab(t, "today")' in js
    tabs_block = js[js.index("tabs: [") : js.index("],", js.index("tabs: ["))]
    assert tabs_block.index('"today"') < tabs_block.index('"signals"')


def test_guide_demoted_from_primary_nav():
    js = _read(CC_APP)
    assert "guideTab:" in js
    assert '{ id: "guide"' not in js.split("tabs: [")[1].split("],")[0]
    html = _read(INDEX)
    assert "guideTab.icon" in html
    assert 'switchTab(guideTab.id)' in html


def test_mission_brief_card_in_deploy_partial():
    html = _read(DEPLOY_PARTIAL)
    assert 'data-cc="mission-brief-card"' in html
    assert "missionBriefCard().title" in html
    assert "Why not deploy?" in html
    assert "Next action" in html


def test_page_gate_and_research_banners():
    html = _read(INDEX)
    assert 'data-cc="page-gate-philosophy-strip"' in html
    assert "pageGatePhilosophyLine()" in html
    assert 'data-cc="research-only-banner"' in html
    assert "isResearchSurfaceTab()" in html


def test_now_blocker_next_compact_strip():
    html = _read(INDEX)
    assert 'data-cc="page-operator-compact"' in html
    assert "pageOperatorCompactVisible()" in html
    assert "pageOperatorSentence().now" in html
    assert "pageOperatorSentence().blocker" in html
    assert "pageOperatorSentence().next_action" in html


def test_guide_progressive_subnav():
    html = _read(GUIDE_PARTIAL)
    assert 'data-cc="guide-subnav"' in html
    assert "guideSections" in html
    assert 'guideSection===\'quickstart\'' in html
    assert 'guideSection===\'workflow\'' in html
    assert 'guideSection===\'glossary\'' in html


def test_cc_app_mission_brief_helpers():
    js = _read(CC_APP)
    assert "missionBriefCard()" in js
    assert "pageOperatorCompactVisible()" in js
    assert "isResearchSurfaceTab(tab)" in js
    assert "guideSection:" in js
