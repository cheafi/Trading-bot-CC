"""Soak / staging verification — selector anchors, recovery copy parity, runbook wiring."""

from __future__ import annotations

import re
from pathlib import Path

from src.services.fetch_surface_state import (
    engine_off_recovery_line,
    ibkr_login_to_ready_hint,
    loading_session_recovery_line,
    operator_loading_safe_line,
    ops_recovery_guide,
    route_abort_recovery_hint,
    soak_confirmation_signals,
    stale_refresh_recovery_line,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
DEPLOY_PARTIAL = ROOT / "src" / "api" / "templates" / "cc" / "partials" / "deploy_surfaces.html"
RUNBOOK = ROOT / "docs" / "CC_SOAK_STAGING_RUNBOOK.md"


def _extract_js_object(fn_name: str, js: str) -> dict[str, str]:
    """Parse simple string-key object from soakConfirmationSelectors()."""
    m = re.search(
        rf"function {re.escape(fn_name)}\(\)\s*\{{\s*return\s*\{{([\s\S]*?)\}}\s*\}}",
        js,
    )
    assert m, f"{fn_name} not found in cc-helpers.js"
    body = m.group(1)
    out: dict[str, str] = {}
    for km in re.finditer(r"(\w+)\s*:\s*'(\[[^\]]+\]|[^']*)'", body):
        out[km.group(1)] = km.group(2)
    return out


def test_soak_confirmation_signals_selectors_in_index():
    signals = soak_confirmation_signals()
    raw = INDEX_HTML.read_text(encoding="utf-8")
    for key, selector in signals.items():
        if not str(selector).startswith('data-cc="'):
            continue
        assert selector in raw, f"missing soak anchor {key}: {selector}"


def test_soak_recovery_copy_parity():
    assert "8001" in loading_session_recovery_line(health_mode="loading")
    assert "Safe now" in operator_loading_safe_line(health_mode="loading")
    assert "Engine OFF" in engine_off_recovery_line()
    assert "stale" in stale_refresh_recovery_line().lower()
    assert "READY" in ibkr_login_to_ready_hint()
    assert "CONFIRM ONLY" in route_abort_recovery_hint("dossier")
    assert "Run Scanners" in route_abort_recovery_hint("discovery")


def test_ops_recovery_guide_matches_runbook_sections():
    g = ops_recovery_guide(health_mode="loading", engine_running=False, breaker=True)
    assert g["retry"] and g["blocks_capital"] and g["safe_degraded"]
    assert any("port 8000" in r.lower() for r in g["retry"])
    assert any("Safe now" in s or "monitor" in s.lower() for s in g["safe_degraded"])


def _selector_attr(selector: str) -> str:
    s = str(selector or "").strip()
    if s.startswith("[") and s.endswith("]"):
        return s[1:-1]
    return s


def test_cc_helpers_soak_selectors_match_python():
    js = CC_HELPERS.read_text(encoding="utf-8")
    py = soak_confirmation_signals()
    js_sel = _extract_js_object("soakConfirmationSelectors", js)
    mapping = {
        "instantDegraded": "instant_degraded",
        "warmupStrip": "warmup_strip",
        "dataContractStrip": "data_contract_strip",
        "deployStrip": "deploy_strip",
        "missionPanel": "mission_panel",
        "playbookSurface": "playbook_surface",
        "marketStale": "market_stale",
        "opsRunbook": "ops_runbook",
    }
    for js_key, py_key in mapping.items():
        assert _selector_attr(js_sel[js_key]) == _selector_attr(py[py_key])


def test_deploy_surfaces_recovery_checkpoints():
    partial = DEPLOY_PARTIAL.read_text(encoding="utf-8")
    assert 'data-cc="deploy-status-strip"' in partial
    assert "engineOffRecoveryLine()" in partial
    assert "ibkrLoginToReadyHint()" in partial
    assert 'data-cc="today-mission-panel"' in partial


def test_index_recovery_helpers_wired():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    for fn in (
        "staleRefreshRecoveryLine()",
        "engineOffRecoveryLine()",
        "ibkrLoginToReadyHint()",
        "routeAbortRecoveryHint(",
        "operatorLoadingSafeLine()",
    ):
        assert fn in raw


def test_runbook_documents_soak_anchors():
    body = RUNBOOK.read_text(encoding="utf-8")
    for anchor in (
        "instant-degraded-banner",
        "warmup-context-strip",
        "deploy-status-strip",
        "today-mission-panel",
        "playbook-surface",
        "market-strip-stale",
        "ops-recovery-runbook",
    ):
        assert anchor in body


def test_build_script_replacement_handles_dollar_signs():
    script = (ROOT / "scripts" / "build-cc-template.mjs").read_text(encoding="utf-8")
    assert "replace(re, () => block)" in script
