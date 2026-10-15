"""Research integrations — signal sync, paper copy, backtrader bridge."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.research.backtrader_bridge import run_sma_cross_backtest
from src.services.copy_trading_paper import paper_copy_leaders
from src.services.signal_sync import SCHEMA_VERSION, build_sync_export, import_sync_payload


def test_signal_sync_export_schema() -> None:
    board = {
        "regime": {"label": "RISK_ON"},
        "generated_at": "2026-01-01T00:00:00Z",
        "buckets": {
            "strong_buy": [
                {
                    "ticker": "BTC-USD",
                    "side": "BUY",
                    "entry": 100,
                    "stop": 90,
                    "target1": 120,
                    "score": 90,
                    "setup": "Breakout",
                    "authority": "Paper signal",
                }
            ],
        },
    }
    payload = build_sync_export(board=board)
    assert payload["schema"] == SCHEMA_VERSION
    assert payload["execution_permission"] is False
    assert payload["signals"][0]["asset_class"] == "crypto"


def test_signal_sync_import_rejects_execution() -> None:
    with pytest.raises(ValueError):
        import_sync_payload(
            {"schema": SCHEMA_VERSION, "execution_permission": True, "signals": []}
        )


def test_paper_copy_leaders() -> None:
    board = {
        "generated_at": "x",
        "regime": {"label": "RISK_ON"},
        "buckets": {
            "strong_buy": [{"ticker": "AAPL", "entry": 100, "stop": 95, "score": 88}],
        },
    }
    out = paper_copy_leaders(board, limit=3)
    assert out["execution_permission"] is False
    assert len(out["positions"]) == 1


def test_backtrader_bridge_synthetic_or_skip() -> None:
    n = 120
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.linspace(100, 130, n) + np.sin(np.arange(n)) * 2
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
        },
        index=idx,
    )
    result = run_sma_cross_backtest(df, fast=5, slow=20)
    if not result.get("available", True):
        pytest.skip("backtrader not installed")
    assert result["ok"] is True
    assert result["engine"] == "backtrader"
