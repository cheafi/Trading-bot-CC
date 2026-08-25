"""Buy signal summary — clarity labels without deploy authority."""

from __future__ import annotations

from src.services.buy_signal_summary import (
    attach_buy_signal_summary,
    build_buy_signal_summary,
    classify_signal_type,
)
from src.services.decision_truth_model import is_execution_ready


def test_classify_breakout_signal():
    row = {"strategy": "breakout", "near_52w_high": True, "vol_ratio": 1.5}
    assert classify_signal_type(row) == "BREAKOUT"


def test_classify_etf_theme():
    row = {"asset_class": "etf", "ticker": "XLK", "theme": "Technology"}
    assert classify_signal_type(row) == "ETF_THEME"


def test_buy_signal_summary_watch_row():
    row = {
        "ticker": "NVDA",
        "action": "WATCH",
        "score": 7.2,
        "thesis_conf": 0.58,
        "timing_conf": 0.52,
        "vol_ratio": 1.3,
        "rs_rank": 82,
        "leader": "LEADER",
        "execution_ready": False,
        "whats_missing": "timing not fully confirmed",
    }
    out = build_buy_signal_summary(row)
    assert out["signal_type"] in ("RS_LEADER", "BREAKOUT", "TREND")
    assert out["authority_label"] == "WATCH"
    assert out["confidence_tier"] in ("HIGH", "MEDIUM", "LOW")
    assert "NVDA" in out["buy_signal_summary"]
    assert out["primary_blocker"]
    assert out["why_now"]
    assert "deploy" not in out["upgrade_path"].lower() or "未" in out["upgrade_path"]


def test_buy_signal_does_not_grant_deploy_on_watch():
    row = {
        "ticker": "AMD",
        "action": "WATCH",
        "score": 8.5,
        "execution_ready": False,
    }
    enriched = attach_buy_signal_summary(row)
    assert enriched["authority_label"] != "DEPLOY"
    assert enriched.get("surface_authority") == "monitor_only"


def test_deploy_row_labeled_deploy():
    row = {
        "ticker": "MSFT",
        "action": "TRADE",
        "score": 8.8,
        "execution_ready": True,
        "trade_bar": {"passes_trade_bar": True},
    }
    out = build_buy_signal_summary(row)
    assert out["authority_label"] == "DEPLOY"
    assert out["confidence_tier"] == "DEPLOY"


def test_execution_ready_gate_unchanged():
    """Sanity — decision_truth deploy gate not weakened by buy_signal module."""
    from types import SimpleNamespace

    cr = SimpleNamespace(
        pipeline=SimpleNamespace(
            decision=SimpleNamespace(action="TRADE"),
            fit=SimpleNamespace(final_score=8.0),
            confidence=SimpleNamespace(final=0.55),
            signal={
                "entry_price": 100,
                "stop_price": 95,
                "target_price": 110,
                "risk_reward": 2.0,
            },
        )
    )
    assert is_execution_ready(cr) is False
