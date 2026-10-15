"""Vibe-Trading workspace — teams, symbols, shadow audit export."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.services.composite_backtest import attach_run_card_to_draft
from src.services.cross_market_loader import resolve_symbols_from_prompt
from src.services.vibe_trading_teams import run_trading_teams
from src.services.vibe_trading_workspace import build_shadow_audit_export


def test_resolve_symbols_merges_crypto_and_defaults() -> None:
    syms = resolve_symbols_from_prompt("Watch BTC breakout and SPY")
    assert "BTC-USD" in syms or "BTC" in syms
    assert "SPY" in syms


def test_attach_run_card_to_draft() -> None:
    draft = {"universe": ["SPY"], "hypothesis": "test"}
    rc = {"aggregate_return_pct": 5.2, "ok_count": 2}
    out = attach_run_card_to_draft(draft, rc)
    assert out["lastRunCard"]["aggregate_return_pct"] == 5.2
    assert out["backtestSummary"]["composite_return_pct"] == 5.2


def test_shadow_audit_export_schema() -> None:
    payload = build_shadow_audit_export(
        {
            "id": "abc",
            "behaviorTags": ["early_exits"],
            "lessons": ["Hold to invalidation"],
            "pnlDifference": -120.0,
        }
    )
    assert payload["schema"] == "cc.shadow_audit.v1"
    assert payload["authority"] == "research_only"


@pytest.mark.asyncio
async def test_trading_teams_structure() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    draft = {
        "universe": ["SPY", "BTC-USD"],
        "hypothesis": "SMA cross",
        "entryRules": ["Fast MA cross slow"],
    }
    market = {"regions": {"US": [{"ok": True, "symbol": "SPY"}]}}
    composite = {
        "ok": True,
        "run_card": {"aggregate_return_pct": 3.0, "ok_count": 2, "leg_count": 2},
        "legs": [],
    }
    teams = await run_trading_teams(
        request,
        question="Test quant crypto risk",
        draft=draft,
        market_snapshots=market,
        system_state={"tradeability": "WAIT", "deploy_open": False},
        composite_backtest=composite,
    )
    ids = {t["id"] for t in teams["teams"]}
    assert ids == {"investment", "quant", "crypto", "macro", "risk"}
    assert teams["execution_permission"] is False
    assert len(teams["streaming_progress"]) == 5
