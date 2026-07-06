"""Guide tab suspends decision-language surface authority."""

from __future__ import annotations

import re
from pathlib import Path

from src.services.surface_authority import (
    AUTHORITY_SUSPENDED,
    GUIDE_AUTHORITY_STRIP,
    GUIDE_STATUS_NOTE,
    guide_mode_strip,
    is_decision_surface_suspended,
    resolve_authority,
    resolve_authority_for_ui_tab,
)

_INDEX_HTML = Path(__file__).resolve().parents[1] / "src" / "api" / "templates" / "index.html"
_GUIDE_HTML = Path(__file__).resolve().parents[1] / "src" / "api" / "templates" / "cc" / "partials" / "guide.html"


def test_guide_tab_resolves_suspended_authority():
    auth = resolve_authority("guide", tradeability="TRADE", deployable_count=5)
    assert auth["authority"] == AUTHORITY_SUSPENDED
    assert auth["badge"] == "GUIDE MODE"
    assert "Reference only" in auth["short"]
    assert "suspended" in auth["authority_label"].lower()


def test_resolve_authority_for_ui_tab_guide():
    auth = resolve_authority_for_ui_tab(
        "guide",
        tradeability="STRONG_TRADE",
        deployable_count=10,
        ibkr_connected=True,
    )
    assert auth["tab"] == "guide"
    assert auth["badge"] == "GUIDE MODE"
    assert auth["authority"] == AUTHORITY_SUSPENDED


def test_is_decision_surface_suspended_only_for_guide():
    assert is_decision_surface_suspended("guide") is True
    assert is_decision_surface_suspended("today") is False
    assert is_decision_surface_suspended("signals") is False


def test_guide_mode_strip_passive_status_only():
    strip = guide_mode_strip(engine_running=True, display_mode="PAPER")
    assert strip["guide_mode"] is True
    assert strip["badge"] == "GUIDE MODE"
    assert strip["strip"] == GUIDE_AUTHORITY_STRIP
    assert strip["engine_on"] is True
    assert strip["display_mode"] == "PAPER"
    assert strip["mode_label"] == "Mode · PAPER"
    assert strip["status_note"] == GUIDE_STATUS_NOTE
    assert strip["principle"] == "Fresh output beats pretty output"
    assert "Decision surfaces suspended in Guide" not in strip["principle"]


def test_guide_authority_strip_constant_is_canonical():
    assert GUIDE_AUTHORITY_STRIP == "GUIDE MODE · Reference only · Decision surfaces suspended"
    assert "Decision surfaces suspended" in GUIDE_AUTHORITY_STRIP


def test_guide_header_bindings_no_duplicate_authority_strip():
    """Guide tab must expose one authority strip — no second Authority bar."""
    html = _INDEX_HTML.read_text(encoding="utf-8")
    guide_trust = re.search(
        r'<div class="trust-strip" x-show="tab===\'guide\'".*?</div>',
        html,
        re.DOTALL,
    )
    assert guide_trust is not None
    trust_block = guide_trust.group(0)
    assert trust_block.count("Decision surfaces suspended") == 1
    assert "Engine ·" not in trust_block
    assert "guideStatusNote()" in trust_block
    # Removed duplicate Guide-only Authority bar (GUIDE MODE pill + suspended copy)
    assert 'tab===\'guide\'" style="background:var(--s0)' not in html
    assert html.count("Decision surfaces suspended in Guide") == 0


def test_guide_layer1_usability_polish():
    """Layer 1: capital checklist label, mistakes block, compressed checklist."""
    html = _INDEX_HTML.read_text(encoding="utf-8")
    assert "Layer 1 — Quick Start" in html
    assert "When capital is allowed / blocked" in html
    assert "Capital allowed when" in html
    assert "Capital blocked when" in html
    assert "When you can / cannot act" not in html
    assert "Most common mistakes" in html
    assert "Don't size from fallback cards" in html
    assert "Don't treat IBKR LOGIN as execution-ready" in html
    assert "Don't treat Discovery / Flow / RS as deploy permission" in html
    assert "Don't treat Backtest Lab as live evidence" in html
    assert "4 rules that prevent most mistakes" not in html
    # Compressed checklist — three essentials only
    checklist = re.search(
        r'id="cc-operator-checklist"[\s\S]{0,1200}',
        html,
    )
    assert checklist is not None
    block = checklist.group(0)
    assert "Page gate beats card rank" in block
    assert "Research ≠ permission" in block
    assert "Dashboard first" in block


def test_guide_signal_card_degraded_examples():
    """Layer 2 signal card section shows ideal + degraded illustrative examples."""
    html = _GUIDE_HTML.read_text(encoding="utf-8")
    assert "Reading a signal card" in html
    assert "Illustrative examples only" in html
    assert "Ideal — deploy-grade" in html
    assert "Degraded — fallback watch" in html
    assert "FALLBACK WATCH" in html
    assert "Degraded — confirm-only dossier" in html
    assert "Confirm-only · 僅結構確認" in html
    assert "No sizing guidance in confirm-only mode" in html


def test_guide_copy_aligned_with_product_wording():
    """Guide copy matches live Command, Dossier, IBKR, Backtest Lab surfaces."""
    html = _GUIDE_HTML.read_text(encoding="utf-8")
    assert "advanced aggregate — not deploy gate" in html.lower()
    assert "GATEWAY UP · LOGIN REQUIRED" in html
    assert "backtest research only; not deployment authority" in html.lower()
    assert "Confirm-only · 僅結構確認" in html
    assert "TRADE LIST" not in html
    assert "decision card" not in html.lower()
    assert "structure review surface" in html.lower()
