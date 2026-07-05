"""Ops recovery runbook — shared copy with ops_degraded vocabulary."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import ops_recovery_guide

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_ops_recovery_guide_sections():
    g = ops_recovery_guide(health_mode="loading", engine_running=False, breaker=True)
    assert g["retry"]
    assert any("health" in r.lower() for r in g["retry"])
    assert any("port 8000" in r.lower() for r in g["retry"])
    assert g["blocks_capital"]
    assert any("breaker" in b.lower() for b in g["blocks_capital"])
    assert g["safe_degraded"]
    assert any("monitor" in s.lower() for s in g["safe_degraded"])


def test_index_html_ops_recovery_guide_panel():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "opsRecoveryGuide()" in raw
    start = raw.find("<!-- SURFACE 7: OPERATOR CONSOLE")
    assert start >= 0
    assert "Recovery runbook" in raw[start : start + 12000]
    assert "blocks_capital" in raw
    assert "safe_degraded" in raw
