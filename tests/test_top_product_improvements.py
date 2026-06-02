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
    assert "cc_operator_checklist_seen" in raw
    assert "operatorChecklistVisible()" in raw
    assert "Page gate beats card rank" in raw
    assert "Research ≠ permission" in raw
    assert "Dashboard first" in raw
    assert "Most common mistakes" in raw
    assert "When capital is allowed / blocked" in raw


def test_tab_ia_demotions():
    raw = _html()
    assert "RS·research" in raw
    assert "Command · advanced" in raw
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
