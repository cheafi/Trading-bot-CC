"""Dossier confirm-only degraded polish — JS/Python copy parity."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    DOSSIER_CONFIRM_ONLY_SIZING,
    dossier_change_pct_display,
    dossier_price_display,
    dossier_quote_available,
    dossier_sizing_display,
    dossier_sizing_explanation,
    dossier_trade_plan_note,
    insider_context_label,
    institutional_sponsorship_label,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"


def test_dossier_quote_unavailable_not_zero_dollar():
    assert dossier_quote_available({"price": 0}) is False
    assert dossier_quote_available({"price": None, "quote_pending": True}) is False
    assert dossier_price_display({"price": 0}) == "Quote unavailable"
    assert dossier_change_pct_display({"price": 0}) == "—"
    assert dossier_price_display({"price": 187.42}) == "$187.42"
    assert dossier_change_pct_display({"price": 10, "change_pct": 1.25}) == "+1.25%"


def test_dossier_confirm_only_sizing_copy_not_duplicated_in_cell():
    assert dossier_sizing_display(blocked=True, reason="confirm_only") == "—"
    assert DOSSIER_CONFIRM_ONLY_SIZING in dossier_sizing_explanation(
        blocked=True, reason="confirm_only"
    )
    assert dossier_sizing_display(blocked=True, reason="confirm_only") != (
        dossier_sizing_explanation(blocked=True, reason="confirm_only")
    )


def test_dossier_trade_plan_note_when_levels_blank():
    assert (
        dossier_trade_plan_note(research_only=True, levels_blank=True)
        == "Live structure unavailable — confirm-only dossier"
    )
    assert dossier_trade_plan_note(levels_blank=True) == "Live structure unavailable"
    assert dossier_trade_plan_note(setup_type="Pullback") == "Pullback"


def test_opportunity_intel_degraded_labels_softer():
    mock = {"degraded": True, "data_tier": "mock"}
    assert "mock" in insider_context_label("notable_accumulation", mock).lower()
    assert "Illustrative" in institutional_sponsorship_label(
        "Added sponsorship (lagged)", mock
    )


def test_index_html_dossier_polish_wired():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "dosPriceDisplay()" in text
    assert "dosChangePctDisplay()" in text
    assert "dosSizeExplanationVisible()" in text
    assert "dosTradePlanNoteValue()" in text
    assert "institutionalSponsorshipLabel" in text


def test_cc_helpers_exports_dossier_polish():
    js = CC_HELPERS.read_text(encoding="utf-8")
    for fn in (
        "dossierPriceDisplay",
        "dossierSizingExplanation",
        "dossierTradePlanNote",
        "institutionalSponsorshipLabel",
    ):
        assert fn in js
