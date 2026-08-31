"""Operator Mode UX — Mission Control, nav reorder, page gate strips."""

from __future__ import annotations

import asyncio
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


def test_primary_nav_professional_labels():
    js = _read(CC_APP)
    assert "TODAY · 今日" in js
    assert "PLAYBOOK · 策略簿" in js
    assert "PORTFOLIO · 持倉" in js
    assert "WORKSPACE · 工作區" in js


def test_workflow_stage_hint_in_index():
    html = _read(INDEX)
    assert 'data-cc="workflow-stage-hint"' in html
    assert "workflowStageHint()" in html


def test_page_gate_strip_css_class():
    html = _read(INDEX)
    assert "page-gate-strip" in html
    assert 'data-cc="page-gate-philosophy-strip"' in html


def test_mission_control_fields_in_deploy_partial():
    html = _read(DEPLOY_PARTIAL)
    assert 'data-cc="mission-control-card"' in html
    assert 'data-cc="four-questions-block"' in html
    assert "fourQuestionsBlock().know" in html
    assert "fourQuestionsBlock().believe" in html
    assert "fourQuestionsBlock().doubt" in html
    assert "fourQuestionsBlock().therefore" in html
    assert "workflowStage().label" in html
    assert "missionControl().quality_headline" in html
    assert "missionControl().best_trade" in html
    assert "missionControl().near_miss_top" in html
    assert "missionControl().sleeve_gate_status" in html
    assert 'data-cc="pm-board-ssot-strip"' in html


def test_four_questions_helpers_in_cc_helpers():
    helpers = _read(CC_HELPERS)
    assert "buildFourQuestionsBlock" in helpers
    assert "WE KNOW" in helpers
    assert "THEREFORE" in helpers
    assert "resolveWorkflowStage" in helpers


def test_workflow_stage_helpers_in_cc_app():
    js = _read(CC_APP)
    assert "workflowStage()" in js
    assert "workflowStageHint()" in js
    assert "fourQuestionsBlock()" in js
    assert "missionControlLoading()" in js


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


def test_deploy_ssot_no_can_deploy_today_in_cc_app():
    js = _read(CC_APP)
    assert "can_deploy_today" not in js
    assert "deployOpen()" in js
    assert "deployOpenFromSystemState" in js or "CCHelpers.deployOpenFromSystemState" in js


def test_portfolio_ssot_no_localstorage_merge_on_read():
    """Server holdings are SSOT — localStorage must not merge into fetchPortfolio read path."""
    js = _read(CC_HELPERS)
    assert "mergeLocalPortfolioHoldings(d.positions" not in js
    assert "this.pf.positions = d.positions || []" in js
    merge_block = js[js.index("mergeLocalPortfolioHoldings(holdings)") : js.index("buildLocalPosition(body)")]
    assert "hydratePortfolioFromLocal()" not in merge_block


def test_portfolio_ssot_v7_endpoint_and_fallback_banner():
    js = _read(CC_APP)
    html = _read(INDEX)
    assert "/api/v7/portfolio" in js
    assert "ssotFallback" in js
    assert "portfolioSsotFallbackActive()" in js
    assert 'data-cc="portfolio-ssot-fallback-banner"' in html


def test_score_families_strip_on_today():
    html = _read(INDEX)
    js = _read(CC_APP)
    assert 'data-cc="score-families-strip"' in html
    assert "dashboardScoreReconciliationActive()" in js
    assert "dashboardScoreReconciliationMessage()" in js


def test_wait_day_secondary_context_collapse():
    html = _read(INDEX)
    partial = _read(DEPLOY_PARTIAL)
    assert "todaySecondaryContextVisible()" in html
    assert "toggleTodayContextExpanded()" in html
    assert "todaySecondaryContextVisible()" in partial
    assert "mission-control-card" in partial


def test_belief_review_ops_panel():
    html = _read(INDEX)
    assert 'data-cc="belief-review-panel"' in html
    assert "fetchBeliefReview()" in _read(CC_APP)


def test_decision_journal_ops_panel():
    html = _read(INDEX)
    js = _read(CC_APP)
    assert 'data-cc="decision-journal-panel"' in html
    assert "fetchDecisionJournal()" in js
    assert "decisionJournal" in js
    assert "RESEARCH ONLY" in html


def test_decision_journal_api_contract_direct():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.decision_journal_recent(limit=5))
    assert payload["authority"] == "research_only"


def test_firm_cadence_ops_panel():
    html = _read(INDEX)
    js = _read(CC_APP)
    assert 'data-cc="firm-cadence-panel"' in html
    assert 'data-cc="firm-cadence-strip"' in html
    assert "fetchFirmCadence()" in js
    assert "firmCadence" in js
    assert "RESEARCH ONLY" in html


def test_firm_cadence_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.firm_cadence_summary())
    assert payload["authority"] == "research_only"
    assert payload["status"] == "stub"
    assert "rituals" in payload
    assert len(payload["rituals"]) >= 5
    assert payload["next_ritual"]["id"]


def test_belief_review_phase2_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.belief_review_summary())
    assert payload["authority"] == "research_only"
    assert "items" in payload
    assert "editable_fields" in payload
    assert "thesis" in payload["editable_fields"]
    assert "kill_condition" in payload["editable_fields"]


def test_marginal_roc_api_contract():
    from src.api.routers import decision as decision_router

    payload = asyncio.run(decision_router.marginal_roc_summary())
    assert payload["authority"] == "research_only"
    assert payload["status"] in {"stub", "live", "empty"}
    assert "cash_hurdle_bps" in payload
    assert "ladder" in payload
    assert "holdings_count" in payload


def test_wait_day_hides_top_ranked_hero():
    html = _read(INDEX)
    js = _read(CC_APP)
    assert "topRankedHeroVisible()" in js
    assert "topRankedHeroVisible()" in html
    assert "!isWaitDay()" not in html.split("TOP-1 hero")[1].split("template")[0] or "topRankedHeroVisible()" in html


def test_marginal_roc_mission_control_strip():
    partial = _read(DEPLOY_PARTIAL)
    js = _read(CC_APP)
    assert 'data-cc="marginal-roc-strip"' in partial
    assert "fetchMarginalRoc()" in js
    assert "marginalRocLadderLine()" in js


def test_belief_review_thesis_kill_ui():
    html = _read(INDEX)
    js = _read(CC_APP)
    assert "saveBeliefItem(" in js
    assert "kill_condition" in html
    assert "Thesis · 論點" in html


def test_pre_decision_gate_and_belief_deploy_in_cc_app():
    js = _read(CC_APP)
    assert "preDecisionGateVisible()" in js
    assert "topDeployCandidate()" in js
    assert "beliefDeployStripLine()" in js


def test_marginal_roc_live_wire_fields():
    from src.services.marginal_roc import build_marginal_roc_ladder

    payload = build_marginal_roc_ladder(deploy_open=True)
    assert payload["authority"] == "research_only"
    assert "holdings_count" in payload
    assert "playbook_rows" in payload
    assert payload["status"] in {"live", "empty"}


def test_export_review_pack_settings_button():
    html = _read(INDEX)
    js = _read(CC_APP)
    helpers = _read(CC_HELPERS)
    assert 'data-cc="export-review-pack"' in html
    assert "Export review pack · 匯出審查包" in html
    assert "exportReviewPack()" in html
    assert "async exportReviewPack()" in js
    assert "reviewPackLoading" in js
    assert "buildReviewPackDocument" in helpers
    assert "stripReviewPackSecrets" in helpers
    assert "@media print" in html
