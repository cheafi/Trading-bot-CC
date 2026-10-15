"""Research task catalog, journal parser, correlation timeline, alpha bench."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.services.alpha_zoo_bench import bench_alphas_on_history
from src.services.broker_journal_parser import parse_broker_journal
from src.services.correlation_regime_timeline import (
    align_histories_local_date,
    edge_density_from_panel,
    hysteresis_timeline,
)
from src.services.research_document_reader import read_document
from src.services.research_task_catalog import catalog_payload
from src.services.research_skills import list_skills, upsert_skill
import base64


def test_task_catalog_has_core_tasks() -> None:
    cat = catalog_payload()
    ids = {t["task"] for t in cat["tasks"]}
    assert "ask_question" in ids
    assert "correlation_regime" in ids


def test_journal_csv_parse() -> None:
    csv_text = "ticker,pnl,exit_reason\nAAPL,100,stop\nMSFT,-50,chase\n"
    out = parse_broker_journal(text=csv_text, fmt="csv")
    assert out["trade_count"] == 2
    assert out["extracted_rules"]


def test_read_document_txt() -> None:
    b64 = base64.b64encode(b"hello research").decode()
    doc = read_document(filename="note.txt", content_b64=b64)
    assert doc["ok"] is True
    assert "hello" in doc["excerpt"]


def test_edge_density_undefined_pairs() -> None:
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    a = pd.Series(np.linspace(100, 110, 30), index=idx)
    b = pd.Series(np.full(30, 50.0), index=idx)
    panel = pd.DataFrame({"A": a, "B": b})
    ed = edge_density_from_panel(panel)
    assert ed["pairs_measured"] == 0
    assert ed["edge_density"] is None


def test_hysteresis_timeline() -> None:
    regs = hysteresis_timeline([0.3, 0.8, 0.75, 0.4, 0.5])
    assert regs[1] == "fused_bloc"
    assert regs[-1] in ("normal", "fused_bloc")


def test_align_mixed_tz_naive() -> None:
    idx_naive = pd.date_range("2024-01-01", periods=10, freq="D")
    idx_tz = pd.date_range("2024-01-01", periods=10, freq="D", tz="America/New_York")
    df1 = pd.DataFrame({"Close": range(10)}, index=idx_naive)
    df2 = pd.DataFrame({"Close": range(10, 20)}, index=idx_tz)
    panel, _ = align_histories_local_date({"SPY": df1, "QQQ": df2})
    assert len(panel) == 10


def test_alpha_bench_synthetic() -> None:
    n = 200
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = np.cumsum(np.random.randn(n)) + 100
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": np.full(n, 1e6),
        },
        index=idx,
    )
    out = bench_alphas_on_history(df)
    assert out["ok"] is True
    assert len(out["results"]) >= 5


def test_mcp_tool_catalog() -> None:
    from src.services.research_mcp_tools import mcp_tool_catalog

    cat = mcp_tool_catalog()
    names = {t["name"] for t in cat["tools"]}
    assert "research_task" in names
    assert "read_document" in names


def test_strategy_export_tdx_mt5() -> None:
    from src.services.strategy_export import export_mt5_mql5_stub, export_tdx_formula

    draft = {"hypothesis": "test", "entryRules": ["MA cross"]}
    assert "MA5" in export_tdx_formula(draft)
    assert "OnTick" in export_mt5_mql5_stub(draft)


def test_13f_qoq_diff() -> None:
    from src.services.filing_13f_qoq import qoq_sponsor_diffs

    rows = [
        {"cik": "1", "name": "A", "filing_date": "2024-02-15"},
        {"cik": "2", "name": "B", "filing_date": "2024-02-20"},
        {"cik": "1", "name": "A", "filing_date": "2024-08-10"},
        {"cik": "3", "name": "C", "filing_date": "2024-08-12"},
    ]
    out = qoq_sponsor_diffs(rows)
    assert out["ok"] is True
    assert out["counts"]["added"] >= 1


def test_session_recall() -> None:
    from src.services.research_memory_recall import recall_similar_sessions

    # No crash when store empty or sparse
    assert isinstance(recall_similar_sessions("SPY momentum VIX"), list)


def test_etf_constituents() -> None:
    from src.services.institutional_intel import etf_constituents_across_markets

    out = etf_constituents_across_markets("XLK")
    assert out["ok"] is True
    assert len(out["constituents"]) >= 3


def test_skills_upsert_roundtrip(tmp_path, monkeypatch) -> None:
    from src.services import research_skills as rs

    monkeypatch.setattr(rs, "_STORE", tmp_path / "skills.json")
    upsert_skill(
        skill_id=None,
        name="My routine",
        task="ask_question",
        steps=["teams"],
        prompt_template="Analyze {{ticker}}",
    )
    assert any(s["name"] == "My routine" for s in list_skills())
