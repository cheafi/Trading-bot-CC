"""Rendered CC contract — banned operator copy must not appear in live template paths."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src" / "api" / "templates" / "index.html"
HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"

BANNED_IN_RUNTIME = [
    r"x-text=\"today7\.tradeability",
    r"x-text=\"canonicalTradeability\(\)\"",
    r"taking a Pilot entry",
    r"Deploy gate open",
    r"brief fallback",
    r"BOARD POSTURE TRADE",
    r"Current: TRADE",
]

RUNTIME_REQUIRED = [
    "runtimePrimaryStateLine()",
    "runtimeSecondaryRegimeLine()",
    "data-role=\"secondary-regime\"",
    "safeRenderText(",
    "cardShowsStructureReference(",
    "Structure reference only",
    "CCHelpers.safeRenderText",
    "runtimePrimaryStateLine",
    "resolveEngineState",
    "Runtime: Conflict",
]


def _blocked_truth_fixture() -> dict:
    return {
        "regime_state": "SELECTIVE",
        "deploy_authority": False,
        "deploy_authority_tier": "blocked",
        "broker_freshness": "offline",
        "brief_freshness": "expired",
        "brief_age_days": 26,
        "brief_expired": True,
        "board_gate": "wait",
        "market_data_freshness": "stale",
        "ranked_board_freshness": "stale",
        "reason_codes": ["ENGINE_OFF", "IBKR_OFFLINE", "BRIEF_EXPIRED"],
        "execution_readiness": {"engine_running": False, "sub_status": {"engine": "off"}},
    }


def test_index_primary_uses_runtime_state_line_not_raw_tradeability():
    html = INDEX.read_text(encoding="utf-8")
    assert "trust-strip-tier-primary" in html
    primary = html.split("trust-strip-tier-primary", 1)[1].split("</div>", 1)[0]
    assert "runtimePrimaryStateLine()" in primary
    assert 'x-text="today7.tradeability' not in primary
    assert "data-role=\"secondary-regime\"" in primary


def test_index_banned_phrases_absent_from_runtime_bindings():
    html = INDEX.read_text(encoding="utf-8")
    trust = html.split("trust-strip-tier-primary", 1)[1].split("<!--", 1)[0]
    playbook = html.split('data-cc="playbook-surface"', 1)[1].split("<!-- SURFACE:", 1)[0]
    runtime_chunk = trust + playbook
    for pattern in BANNED_IN_RUNTIME:
        assert re.search(pattern, runtime_chunk, re.I) is None, f"banned in runtime: {pattern}"


def test_index_runtime_helpers_wired():
    html = INDEX.read_text(encoding="utf-8")
    for needle in RUNTIME_REQUIRED:
        assert needle in html, f"missing runtime wiring: {needle}"


def test_cc_helpers_blocked_primary_not_selective():
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "function runtimePrimaryStateLine" in helpers
    assert "function deployAuthorityTier" in helpers
    assert "function safeRenderText" in helpers
    assert 'return "conflict"' in helpers
    assert "Runtime: Conflict" in helpers


def test_safe_render_sanitizes_blocked_card_copy():
    helpers = HELPERS.read_text(encoding="utf-8")
    assert "taking a Pilot entry" in helpers
    assert "Deploy gate open" in helpers
    assert "removeTradeLanguageWhenBlocked" in helpers


def test_playbook_qualification_zero_deploy_when_blocked():
    from src.services.playbook_truth import format_playbook_qualification_line

    line = format_playbook_qualification_line(
        setup_qualified=3,
        trade_qualified=2,
        execution_qualified=2,
        deploy_qualified=2,
        deploy_authority=False,
        regime_state="SELECTIVE",
        board_gate="wait",
    )
    assert "2 deploy-qualified" not in line
    assert "0 deploy-qualified" in line
    assert "deploy gate open" not in line.lower()


def test_blocked_fixture_primary_monitor_only_not_selective():
    from src.services.authority_engine import primary_operator_state

    posture = primary_operator_state(_blocked_truth_fixture())
    assert posture["primary"] == "MONITOR ONLY"
    assert posture["secondary"] == "SELECTIVE"


def test_guide_operator_quick_read_uses_monitor_model():
    html = INDEX.read_text(encoding="utf-8")
    guide = html.split("<!-- @cc-partial guide", 1)[1].split("<!-- @cc-partial-end guide", 1)[0]
    assert "MONITOR ONLY" in guide and "Deploy blocked" in guide
    assert "TRADE LIST" not in guide
    assert "pilot half-size" not in guide.lower()
