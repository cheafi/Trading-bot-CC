"""Dossier confirm-only structure review — no trade-plan authority leakage."""

from __future__ import annotations

from pathlib import Path

from src.services.dossier_mode import (
    DOSSIER_CONFIRM_ONLY_STRIP,
    PAPER_DRAFT_DISABLED_COPY,
    STRUCTURE_SNAPSHOT_TITLE,
    build_dossier_operator_block,
    build_structure_snapshot_rows,
    resolve_dossier_mode,
    structure_level_label,
)
from src.services.fetch_surface_state import (
    dossier_confirm_only_strip,
    dossier_structure_level_label,
    dossier_structure_snapshot_title,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def test_confirm_only_maps_to_structure_review_only():
    assert (
        resolve_dossier_mode(
            unified_label="CONFIRM ONLY",
            instant_degraded=True,
            brief_backed=True,
            has_quote=True,
        )
        == "structure_review_only"
    )


def test_unavailable_when_no_quote_and_degraded():
    assert (
        resolve_dossier_mode(
            unified_label="CONFIRM ONLY",
            instant_degraded=True,
            brief_backed=False,
            has_quote=False,
            partial=True,
        )
        == "unavailable"
    )


def test_loading_when_core_phase():
    assert resolve_dossier_mode(load_phase="core", has_quote=True) == "loading"


def test_usable_mode_when_live_and_trade_label():
    assert (
        resolve_dossier_mode(
            unified_label="TRADE",
            has_quote=True,
            partial=False,
            rr_unavailable=False,
        )
        == "usable"
    )


def test_structure_snapshot_labels_bilingual():
    assert "參考價位" in structure_level_label("entry", mode="structure_review_only")
    assert structure_level_label("entry", mode="usable") == "Entry zone"
    assert "風險參考" in structure_level_label("stop", mode="structure_review_only")
    assert "上行參考" in structure_level_label("target", mode="structure_review_only")


def test_structure_snapshot_hides_rr_unless_live_validated():
    rows = build_structure_snapshot_rows(
        mode="structure_review_only",
        entry_zone=[100, 102],
        stop=95,
        target_1r=110,
        target_2r=120,
        rr_display="2.5",
        live_validated=False,
    )
    labels = [r["label"] for r in rows]
    assert "R:R" not in labels
    assert any("Use: structure review only" in r["value"] for r in rows)


def test_structure_snapshot_shows_rr_when_usable():
    rows = build_structure_snapshot_rows(
        mode="usable",
        entry_zone=[100, 102],
        stop=95,
        target_1r=110,
        target_2r=120,
        rr_display="2.5",
        live_validated=True,
    )
    assert any(r["label"] == "R:R" for r in rows)


def test_operator_block_xlp_degraded_shape():
    block = build_dossier_operator_block(
        mode="unavailable",
        ticker="XLP",
        has_quote=False,
        brief_backed=False,
        instant_degraded=True,
        missing_data=["quote", "technicals", "peers", "options", "catalysts", "risk"],
    )
    assert block["now"] == "XLP · Structure unavailable"
    assert "live quote unavailable" in block["why"]
    assert "no brief row" in block["why"]
    assert "retry" in block["allowed"][0]
    assert "no trade plan" in block["blocked"]
    assert "quote" in block["missing_data"]


def test_index_html_no_trade_plan_in_structure_review_only():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierRecoveryMode()" in text
    assert "dossierTradePlanVisible()" in text
    assert "dossierUsable()" in text
    assert "dossierPaperDraftVisible()" in text
    assert "dossierPaperDraftDisabledCopy()" in text
    assert "dossierMonitorRuleLabel()" in text
    assert DOSSIER_CONFIRM_ONLY_STRIP.split("·")[0].strip() in text
    assert STRUCTURE_SNAPSHOT_TITLE in text
    assert PAPER_DRAFT_DISABLED_COPY in text
    assert "x-show=\"dossierTradePlanVisible()\"" in text


def test_index_html_no_duplicate_confirm_only_sizing_strip():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert text.count(DOSSIER_CONFIRM_ONLY_STRIP) >= 1
    assert 'x-show="dosDashboardReminderLine()"' not in text
    assert "Confirm-only — no IBKR handoff or sizing" not in text


def test_index_html_mock_context_collapsed():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-cc="dossier-opp-intel"' in text
    assert ':open="dossierUsable()"' in text
    assert "dossierLaggedContextNote()" in text
    assert "Lagged / illustrative context" in text


def test_index_html_confirm_only_blocks_present():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-cc="dossier-confirm-only-blocks"' in text
    for label in (
        "現在 · Now",
        "缺少內容 · Missing",
        "禁止 · Blocked",
        "允許 · Allowed",
    ):
        assert label in text


def test_cc_helpers_dossier_mode_exports():
    js = CC_HELPERS.read_text(encoding="utf-8")
    for fn in (
        "resolveDossierMode",
        "dossierRecoveryMode",
        "dossierUsableMode",
        "dossierOperatorBlock",
        "dossierTradePlanVisible",
        "dossierEvidenceStatus",
        "dossierStructureReviewOnly",
        "dossierConfirmOnlyStrip",
        "dossierStructureSnapshotTitle",
        "dossierPaperDraftVisible",
        "dossierStructureSnapshotRows",
    ):
        assert fn in js


def test_fetch_surface_state_parity():
    assert dossier_confirm_only_strip() == DOSSIER_CONFIRM_ONLY_STRIP
    assert dossier_structure_snapshot_title() == STRUCTURE_SNAPSHOT_TITLE
    assert "參考價位" in dossier_structure_level_label("entry", mode="structure_review_only")
