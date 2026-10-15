"""Guide tab suspends decision-language surface authority."""

from __future__ import annotations

import re
from pathlib import Path

from _dashboard_js_runtime import run_dashboard_js

from src.services.surface_authority import (
    AUTHORITY_SUSPENDED,
    GUIDE_AUTHORITY_STRIP,
    GUIDE_STATUS_NOTE,
    guide_mode_strip,
    is_decision_surface_suspended,
    resolve_authority,
    resolve_authority_for_ui_tab,
)

_ROOT = Path(__file__).resolve().parents[1]
_INDEX_HTML = _ROOT / "src" / "api" / "templates" / "index.html"
_GUIDE_PARTIAL = _ROOT / "src" / "api" / "templates" / "cc" / "partials" / "guide.html"


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
    assert (
        GUIDE_AUTHORITY_STRIP
        == "GUIDE MODE · Reference only · Decision surfaces suspended"
    )
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
    assert trust_block.lower().count("decision surfaces suspended") == 1
    assert "Engine ·" not in trust_block
    assert "guideStatusNote()" in trust_block
    # No duplicate Guide-only Authority bar.
    assert "tab==='guide'\" style=\"background:var(--s0)" not in html
    assert html.count("Decision surfaces suspended in Guide") == 0
    run_dashboard_js("""
        app.tab = 'guide';
        app.today7.tradeability = 'STRONG_TRADE';
        app.today7.system_state = {
            deploy_open: true, global_strip_active: true};
        app.decisionHub = {decision_bar: {verdict: 'DEPLOY'}};
        assert.equal(app.tabAuthorityChip().authority, 'suspended');
        assert.equal(app.contextDecisionBar(), null);
        assert.equal(app.normalizedContextDecisionBar(), null);
        assert.equal(app.globalSystemStripVisible(), false);
        assert.equal(app.dataContractStripVisible(), false);
        assert.equal(app.pageOperatorCompactVisible(), false);
        assert.equal(app.headerSummary().show_decision_chips, false);
        assert.equal(app.headerSummary().show_regime_strip, false);
        assert.match(app.guideStatusNote(), /Runtime|執行時|運行|評估/);
    """)


def test_guide_layer1_usability_polish():
    """Quickstart: three plain-language rules + capital when/blocked summary."""
    html = _INDEX_HTML.read_text(encoding="utf-8")
    assert "三條鐵律" in html
    assert "幾時可以動錢" in html
    assert "Random Walk — Global Principles" not in html
    checklist = re.search(
        r'id="cc-operator-checklist"[\s\S]{0,1200}',
        html,
    )
    assert checklist is not None
    block = checklist.group(0)
    assert "今日大環境" in block
    assert "研究頁" in block
    assert "止蝕" in block


def test_guide_signal_card_degraded_examples():
    """Advanced section: one illustrative card + short legend (no degraded clutter)."""
    guide = _GUIDE_PARTIAL.read_text(encoding="utf-8")
    assert "Reading a signal card" in guide
    assert "完整卡" in guide
    assert "Degraded — fallback watch" not in guide
    assert "FALLBACK WATCH" not in guide


def test_guide_copy_aligned_with_product_wording():
    """Guide glossary still aligns with IBKR LOGIN vs READY and research-only tabs."""
    html = _INDEX_HTML.read_text(encoding="utf-8")
    assert "advanced aggregate — not deploy gate" in html.lower()
    assert "GATEWAY UP · LOGIN REQUIRED" in html
    assert "回測" in html or "backtest" in html.lower()
    assert "LOGIN ≠ READY" in html or "淨係 LOGIN" in html
