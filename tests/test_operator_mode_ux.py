"""Operator Mode UX — Mission Control, nav reorder, page gate strips."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"
CC_APP = ROOT / "src/api/static/cc-app.js"
CC_HELPERS = ROOT / "src/api/static/cc-helpers.js"
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


def test_guide_not_first_in_nav_order():
    js = _read(CC_APP)
    assert "guideTab:" in js
    assert '{ id: "guide"' not in js.split("tabs: [")[1].split("],")[0]
    html = _read(INDEX)
    assert "guideTab.icon" in html
    assert "settingsTab.icon" in html
    nav_pos = html.index('data-cc-nav="today"')
    guide_pos = html.index('data-cc-nav="guide"')
    assert nav_pos < guide_pos


def test_primary_nav_order_portfolio_before_workspace():
    js = _read(CC_APP)
    tabs_block = js[js.index("tabs: [") : js.index("],", js.index("tabs: ["))]
    assert tabs_block.index('"portfolio"') < tabs_block.index('"dossier"')


def test_mission_control_fields_in_deploy_partial():
    html = _read(DEPLOY_PARTIAL)
    assert 'data-cc="mission-control-card"' in html
    assert "missionControl().market_state" in html
    assert "missionControl().deploy" in html
    assert "missionControl().good_opportunity" in html
    assert "missionControl().what_to_do" in html
    assert "missionControl().why" in html
    assert "missionControl().next_review" in html


def test_opportunity_verdict_block_on_today_first_screen():
    html = _read(DEPLOY_PARTIAL)
    assert 'data-cc="opportunity-verdict-block"' in html
    mc = html.index("mission-control-card")
    ov = html.index("opportunity-verdict-block")
    assert mc < ov


def test_page_gate_and_research_banners():
    html = _read(INDEX)
    assert 'data-cc="page-gate-philosophy-strip"' in html
    assert "pageGatePhilosophyLine()" in html
    assert "Page Gate > Card Rank" in _read(CC_HELPERS)
    assert 'data-cc="research-only-banner"' in html
    assert "isResearchSurfaceTab()" in html
    assert "Cannot authorize deployment" in _read(CC_HELPERS)


def test_guide_progressive_subnav_quick_advanced_reference():
    html = _read(GUIDE_PARTIAL)
    assert 'data-cc="guide-subnav"' in html
    assert "guideSections" in html
    assert 'guideSection===\'quickstart\'' in html
    assert 'guideSection===\'advanced\'' in html
    assert 'guideSection===\'reference\'' in html


def test_cc_app_mission_control_helpers():
    js = _read(CC_APP)
    assert "missionControl()" in js
    assert "missionBriefCard()" in js
    assert "settingsTab:" in js
    assert "guideSection:" in js
    assert '"advanced"' in js
