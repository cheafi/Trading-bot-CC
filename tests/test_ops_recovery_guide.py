"""Ops recovery runbook — shared copy with ops_degraded vocabulary."""

from __future__ import annotations

from pathlib import Path

from _dashboard_html_contract import bindings
from _dashboard_js_runtime import run_dashboard_js

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
    partial = ROOT / "src/api/templates/cc/partials/ops_recovery_runbook.html"
    assert partial.read_text(encoding="utf-8").strip() in raw
    for path in (INDEX_HTML, partial):
        assert "opsRecoveryRunbookTitle()" in bindings(path, "x-text")
        for section in ("retry", "blocks_capital", "safe_degraded"):
            assert f"ln in opsRecoveryGuide().{section}" in bindings(path, "x-for")
    run_dashboard_js("""
        app.tab = 'ops';
        app.healthMode = 'loading';
        app.ops.running = false;
        app.cc_status.breaker = true;
        const guide = app.opsRecoveryGuide();
        assert.ok(guide.retry.some(s => s.includes('/health')));
        assert.ok(guide.retry.some(s => /mode=full/.test(s)));
        assert.ok(guide.retry.some(s => /重啟|restart/i.test(s)));
        assert.ok(guide.blocks_capital.some(s => /breaker/i.test(s)));
        assert.ok(guide.blocks_capital.some(s => /IBKR|handoff/.test(s)));
        assert.ok(guide.safe_degraded.some(s => /monitor|監察|監控/i.test(s)));
        assert.ok(guide.safe_degraded.some(s => /sizing|倉位/.test(s)));
        assert.equal(app.deployOpen(), false);
        assert.ok(app.opsRecoveryRunbookTitle());
    """)
