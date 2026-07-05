"""Funds research-only semantics — no allocation language leakage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_INSTANT = ROOT / "_cc_instant.py"


def _sample_card(*, gate_status: str = "REDUCED", live_trades: int = 0) -> dict:
    return {
        "id": "TACTICAL_DEF",
        "display_name": "Tactical Defensive",
        "gate_status": gate_status,
        "regime_fit": 62,
        "fund_return_pct": 12.0,
        "excess_return_pct": 2.27,
        "max_drawdown_pct": -8.0,
        "sharpe": 2.72,
        "holdings": [{"ticker": "XLP", "weight": 1.0}],
        "evidence_quality": {"live_trades_count": live_trades, "trust_tier": "research_only"},
    }


def test_resolve_funds_mode_broker_offline_zero_eligible():
    from src.services.fund_manager_console import resolve_funds_mode

    mode = resolve_funds_mode(
        execution_readiness={"broker_connected": False, "portfolio_synced": False, "portfolio_source": "manual"},
        tradeability="NO_TRADE",
        cards=[_sample_card()],
        system_truth={"regime_state": "NO_TRADE", "deploy_authority": False},
        allocation={"deployable_capital_pct": 60, "deployable_capital_range": "55-65%"},
    )
    assert mode["live_allocation_eligible"] == 0
    assert mode["allocation_authority"] == "none"
    assert mode["research_only_mode"] is True
    assert "broker offline" in mode["blockers"]


def test_research_only_console_hides_allocatable_language():
    from src.services.fund_manager_console import build_fund_console_payload

    console = build_fund_console_payload(
        cards=[_sample_card()],
        regime="SIDEWAYS · WAIT",
        benchmark="SPY",
        execution_readiness={
            "broker_connected": False,
            "portfolio_synced": False,
            "portfolio_source": "manual",
            "trade_handoff_ready": False,
        },
        tradeability="NO_TRADE",
        system_truth={"regime_state": "NO_TRADE", "deploy_authority": False, "board_gate": "closed"},
    )
    blob = json.dumps(console)
    assert "Allocatable" not in blob
    assert console["live_allocation_eligible"] == 0
    assert console["allocation_authority"] == "none"
    assert console["allocator_truth_strip"]["live_eligible_capital_pct"] == 0
    assert console["research_only_mode"] is True


def test_live_trades_zero_hides_conviction_medium():
    from src.services.fund_manager_console import enrich_fund_card

    card = enrich_fund_card(_sample_card(live_trades=0), "SIDEWAYS", research_only_mode=True)
    conf = card.get("validation_confidence")
    assert conf is None or str(conf).upper() not in ("MEDIUM", "HIGH")
    assert card["model_stance_label"] == "Model stance: Reduced"
    assert card["backtest_quarantine"]["show_alpha_sharpe"] is False
    assert card["card_zones"]["current_book"]["hidden_default"] is True


def test_first_screen_core_before_sleeve_research_in_template():
    text = INDEX_HTML.read_text(encoding="utf-8")
    funds = text.split("x-show=\"tab==='funds'\"")[1].split("x-show=\"tab==='flow'\"")[0]
    assert "A · Core index posture" in funds
    assert "B · Sleeve research" in funds
    assert funds.index("A · Core index posture") < funds.index("B · Sleeve research")
    assert "Fund Research Lab" in funds
    assert "Active Fund Manager" not in funds


def test_index_no_allocatable_or_deploy_in_research_only_ui():
    text = INDEX_HTML.read_text(encoding="utf-8")
    funds = text.split("x-show=\"tab==='funds'\"")[1].split("x-show=\"tab==='flow'\"")[0]
    assert "fundResearchOnlyMode()" in funds
    assert ">Allocatable<" not in funds
    assert "'Deploy? '" not in funds
    assert "Highest research fit" in funds
    assert "Model holdings (hypothetical)" in funds
    assert "Validation confidence" in funds
    assert "Backtest quarantine" in funds
    assert "fundMonitor.console.guardrail" in funds or "funds_first_screen.guardrail" in funds


def test_backtest_alpha_sharpe_hidden_by_default():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "fundShowBacktestDetails(card)" in text
    assert "fundToggleBacktestDetails" in text
    block = text.split("Backtest quarantine")[1].split("Model holdings (hypothetical)")[0]
    assert "x-show=\"fundShowBacktestDetails(card)\"" in block
    assert "Sharpe" in block


def test_stale_fund_lab_research_only_fields():
    stub = """
import json
from datetime import datetime, timezone

def _load_latest_brief():
    return None

def _encode_degraded(payload, *, reason=None):
    return json.dumps(payload).encode()

"""
    fn_block = (
        CC_INSTANT.read_text(encoding="utf-8")
        .split("def _stale_fund_lab_bytes(reason: str) -> bytes:")[1]
        .split("\ndef _stale_no_trade_bytes(reason: str) -> bytes:")[0]
    )
    ns: dict = {}
    exec(stub + "def _stale_fund_lab_bytes(reason: str) -> bytes:" + fn_block, ns)  # noqa: S102
    payload = json.loads(ns["_stale_fund_lab_bytes"]("backend importing"))
    assert payload["console"]["live_allocation_eligible"] == 0
    assert payload["console"]["allocation_authority"] == "none"
    assert payload["console"]["research_lab_title"] == "Fund Research Lab"
