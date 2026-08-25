"""Section 7 top product improvements — CC Clarity Console template contracts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_data_contract_strip_helpers_and_markup():
    raw = _html()
    assert "dataContractStrip()" in raw
    assert "dataContractStrip().fetch" in raw
    assert "dataContractStrip().board" in raw
    assert "dataContractStrip().broker" in raw
    assert "dataContractFetchBadge" in raw
    assert "dataContractBrokerShort" in raw
    assert "dismissDataContract" in raw
    assert 'x-show="tab!==\'guide\'"&&!dataContractDismissed' not in raw
    assert "dataContractStripVisible()" in raw
    assert 'class="data-contract-strip"' in raw


def test_surface_empty_state_kinds():
    raw = _html()
    assert "surfaceEmptyState(tab,ctx)" in raw
    for kind in ("NO_DATA", "FETCH_FAILED", "WAIT_DAY_OK", "WARMING"):
        assert f"kind:'{kind}'" in raw
    assert "discoveryEmptyState()" in raw
    assert "dashboardEmptyState()" in raw
    assert "rejectionsEmptyState()" in raw


def test_boot_guards_survive_bad_persisted_state():
    raw = _html()
    assert "function ccStoredObject(key)" in raw
    assert "function ccNormalizeTab(tab, fallback)" in raw
    assert "ccStarred:ccStoredObject('ccStarred')" in raw
    assert "ccLoved:ccStoredObject('ccLoved')" in raw
    assert "ccWatchlist:ccStoredObject('ccWatchlist')" in raw
    assert "this.tab=ccNormalizeTab(this.tab,'today');" in raw
    assert "const tSafe=this.tab;" in raw


def test_cc_state_unified_truth_hooks():
    raw = _html()
    assert "ccState()" in raw
    assert "currentSurfaceCcState()" in raw
    assert "currentSurfaceAuthorityStrip()" in raw
    assert "authorityChipPillClass(chip)" in raw
    assert "normalizedAuthorityChipForTab(t, rawEntry)" in raw
    assert "dashboardOperatorNowLine()" in raw
    assert "playbookOperatorNowLine()" in raw
    assert "cs.board_decision_state" in raw
    assert "cs.tradeability_state" in raw
    assert "executionState()" in raw
    assert "primaryBlockerLine()" in raw
    assert "primaryBlockerChip()" in raw
    assert "ccFreshnessState()" in raw
    assert "cardActionDisplay(opp)" in raw
    assert "cardActionDisplayClass(opp)" in raw
    assert "this.canonicalTradeability()" in raw
    assert "discoveryPromotionPack(h)" in raw
    assert "dossierGateSnapshotLine()" in raw
    assert "dosOpenContextLine()" in raw
    assert "playbookCardBlockers(r)" in raw
    assert "playbookCompactEvidenceLine(r)" in raw
    assert "pfPrioritySummary()" in raw
    assert "fundPrimarySummary()" in raw
    assert "rejectionsClusterCards()" in raw


def test_p2_copy_cleanup_stays_chinese_primary():
    raw = _html()
    assert "核心暫不可用 · confirm-only" in raw
    assert "Discovery 屬 research-only；就算分數高，仍要經 Playbook 驗證 board 同 execution gates。" in raw
    assert "WAIT · 今日不可 Deploy。" in raw
    assert "排名只代表關注優先次序，唔代表 Deploy 權限。" in raw
    assert "目前只可 Monitor · " in raw
    assert "暫未形成 deploy-grade board · 只可 Monitor。" in raw
    assert "Research-only 結論 · sizing 或 IBKR handoff 前，先去 Dashboard 確認 board gate。" in raw
    assert "Sizing unavailable" in raw
    assert "IBKR repair checklist" in raw
    assert "下一步 · " in raw
    assert "Funds first screen" in raw
    assert "Blocker clusters" in raw
    assert "Book truth" in raw
    assert "Sync state" in raw
    assert "Top flow research candidates" in raw
    assert "Top RS research candidates" in raw
    assert "MONITOR CANDIDATE" in raw
    assert "不可執行 · blocked here" in raw


def test_dossier_fallback_uses_intentional_operator_lines():
    raw = _html()
    assert "dosFetchBannerNowLine()" in raw
    assert "dosFetchBannerBlockerLine()" in raw
    assert "dosFetchBannerRestoreLine()" in raw
    assert "現有資料" in raw
    assert "缺少 · " in raw


def test_template_balance_around_discovery_tail():
    raw = _html()
    assert raw.count("<template") == raw.count("</template>")
    assert "emptybox-'+catName" not in raw


def test_dossier_autocomplete_selection_triggers_fetch():
    raw = _html()
    assert "if(t==='dos'&&this.dos.ticker)this.fetchDossier();" in raw
    assert "@mousedown.prevent=\"acSelect(item)\"" in raw


def test_legacy_opps_graded_not_raw_action():
    raw = _html()
    assert "playbookOppsFallbackRows()" in raw
    assert "cardExecutionGrade(r)" in raw
    assert "effectiveCardAction(r)" in raw
    # Legacy path must not paint raw BUY/TRADE from r.action alone
    assert re.search(
        r"playbookOppsFallbackRows[\s\S]{0,800}r\.action==='BUY'",
        raw,
    ) is None


def test_guide_operator_checklist_copy():
    raw = _html()
    assert "cc_operator_checklist_seen" not in raw
    assert "operatorChecklistVisible()" not in raw
    assert "使用手冊 · Operator Manual" in raw
    assert "Page gate beats card rank" in raw
    assert "Research ≠ permission" in raw
    assert "Dashboard first" in raw
    assert "Most common mistakes" in raw
    assert "When capital is allowed / blocked" in raw


def test_tab_ia_demotions():
    raw = _html()
    assert "RS 相對強度 · research" in raw
    assert "Command 指揮台 · advanced" in raw
    assert 'switchTab(\'command\')' not in re.search(
        r"BOTTOM NAV[\s\S]{0,1200}",
        raw,
    ).group(0)
    assert "Open RS research layer" in raw
    assert "pmStripUseChipMenu()" in raw
    assert "Status ▾" in raw
    assert "pmStripChipMenuToggle()" in raw
    assert 'id="pm-strip"' in raw
    assert "overflow:visible" in raw.split('id="pm-strip"')[1].split(">")[0]
    assert "ibkrApplyStatusFetchFailure" in raw
    assert 'id="ibkr-session-state"' in raw
