"""Instant-server core dossier fallback for stock-intel (Load core only path)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC_INSTANT = ROOT / "_cc_instant.py"


def _load_cc_helpers():
    import os

    os.chdir(ROOT)
    source = CC_INSTANT.read_text(encoding="utf-8")
    ns: dict = {"__file__": str(CC_INSTANT)}
    exec(  # noqa: S102
        source.split("class Handler")[0],
        ns,
    )
    return ns


def test_cc_instant_degraded_response_routes_stock_intel():
    raw = CC_INSTANT.read_text(encoding="utf-8")
    assert 'path_only.startswith("/api/v7/stock-intel/")' in raw
    assert "_stale_stock_intel_bytes" in raw


def test_stale_stock_intel_core_aapl_from_brief():
    ns = _load_cc_helpers()
    body = ns["_stale_stock_intel_bytes"](
        "/api/v7/stock-intel/AAPL?lite=true",
        "backend importing — full API still loading",
    )
    assert body is not None
    payload = json.loads(body.decode())
    assert payload["ticker"] == "AAPL"
    assert payload["load_phase"] == "core"
    assert payload["partial"] is True
    assert payload["research_only"] is True
    assert payload.get("degraded") is True
    dossier = payload["dossier"]
    assert dossier["symbol"] == "AAPL"
    assert dossier.get("price") or dossier.get("symbol") == "AAPL"
    assert dossier["technicals"]["atr"] >= 0
    assert payload["unified_decision"]["label"] == "CONFIRM ONLY"
    assert payload.get("partial_notice")
    mod = payload.get("module_errors") or {}
    if mod.get("dossier"):
        assert "not in latest brief cache" in mod["dossier"]
    else:
        assert "fetch failed" not in str(payload.get("partial_notice", "")).lower()


def test_stale_stock_intel_core_missing_brief_row_sets_module_error():
    ns = _load_cc_helpers()
    body = ns["_stale_stock_intel_bytes"](
        "/api/v7/stock-intel/ZZZZ?lite=true",
        "backend importing",
    )
    assert body is not None
    payload = json.loads(body.decode())
    assert "dossier" in (payload.get("module_errors") or {})


def test_stale_stock_intel_enrichments_phase():
    ns = _load_cc_helpers()
    body = ns["_stale_stock_intel_bytes"](
        "/api/v7/stock-intel/MSFT?enrichments=true",
        "backend proxy failed",
    )
    payload = json.loads(body.decode())
    assert payload["load_phase"] == "enrichments"
    assert payload["module_errors"]["enrichments"]
    assert payload.get("sizing_blocked") is True
    assert payload.get("size_info", {}).get("shares") == 0
    assert payload["size_info"].get("sizing_blocked") is True


def test_stale_stock_intel_core_blocks_actionable_sizing():
    ns = _load_cc_helpers()
    body = ns["_stale_stock_intel_bytes"](
        "/api/v7/stock-intel/AAPL?lite=true",
        "backend importing — full API still loading",
    )
    payload = json.loads(body.decode())
    assert payload.get("sizing_blocked") is True
    size_info = payload.get("size_info") or {}
    assert size_info.get("shares") == 0
    assert size_info.get("sizing_blocked") is True
    assert "confirm-only" in size_info.get("size_explanation", "").lower()
    assert payload["unified_decision"]["label"] == "CONFIRM ONLY"
