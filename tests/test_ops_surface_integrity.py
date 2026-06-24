"""Ops tab degraded copy, error-log UX, and render safety."""

from __future__ import annotations

from pathlib import Path

from src.services.ops_operator_console import build_degraded_ops_operator_console

from src.services.fetch_surface_state import (
    OPS_STATE_FALLBACK,
    OPS_STATE_LOADING,
    OPS_STATE_RETRY_RECOMMENDED,
    OPS_STATE_RUNTIME_UNKNOWN,
    OPS_STATE_UNAVAILABLE,
    normalize_ops_panel_state,
    ops_degraded_copy,
    ops_degraded_line,
    ops_updates_panel_title,
)
from src.services.ui_render_safety import find_js_leaks_in_file

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_ops_degraded_vocabulary_table():
    loading = ops_degraded_copy(OPS_STATE_LOADING)
    fallback = ops_degraded_copy(OPS_STATE_FALLBACK)
    unavailable = ops_degraded_copy(OPS_STATE_UNAVAILABLE)
    runtime_unknown = ops_degraded_copy(OPS_STATE_RUNTIME_UNKNOWN)
    retry = ops_degraded_copy(OPS_STATE_RETRY_RECOMMENDED)

    assert loading["title"] == "Loading"
    assert fallback["title"] == "Fallback"
    assert unavailable["title"] == "Unavailable"
    assert runtime_unknown["title"] == "Runtime unknown"
    assert retry["title"] == "Retry recommended"

    assert "LOADING" in ops_degraded_line(OPS_STATE_LOADING)
    assert "FALLBACK" in ops_degraded_line(OPS_STATE_FALLBACK)
    assert "UNAVAILABLE" in ops_degraded_line(OPS_STATE_UNAVAILABLE)
    assert "RUNTIME UNKNOWN" in ops_degraded_line(OPS_STATE_RUNTIME_UNKNOWN)
    assert "RETRY" in ops_degraded_line(OPS_STATE_RETRY_RECOMMENDED)


def test_normalize_ops_panel_state_maps_fetch_failures():
    assert normalize_ops_panel_state(loading=True) == OPS_STATE_LOADING
    assert (
        normalize_ops_panel_state(error="Failed to fetch")
        == OPS_STATE_RETRY_RECOMMENDED
    )
    assert (
        normalize_ops_panel_state(error="HTTP 500", fallback=True)
        == OPS_STATE_FALLBACK
    )
    assert (
        normalize_ops_panel_state(runtime_unknown=True)
        == OPS_STATE_RUNTIME_UNKNOWN
    )


def test_index_html_error_log_does_not_show_empty_when_fetch_failed():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "Error log fetch failed:" not in raw
    assert "Unable to confirm whether errors were logged this session" in raw
    assert "!errorLog.loading && !errorLog.entries.length && !errorLog.error" in raw


def test_ops_updates_panel_title_vocabulary():
    assert ops_updates_panel_title(OPS_STATE_UNAVAILABLE) == "Panel unavailable"
    assert ops_updates_panel_title(OPS_STATE_FALLBACK, timed_out=True) == "No fallback available"
    assert ops_updates_panel_title(OPS_STATE_FALLBACK, timed_out=False) == "Fallback unavailable"
    assert ops_updates_panel_title(OPS_STATE_RETRY_RECOMMENDED) == "Retry recommended"


def _ops_surface_html(raw: str) -> str:
    start = raw.find("<!-- SURFACE 7: OPERATOR CONSOLE")
    if start < 0:
        return ""
    end = raw.find("</main>", start)
    return raw[start : end + len("</main>")] if end >= 0 else raw[start:]


def test_degraded_ops_console_includes_component_evidence():
    out = build_degraded_ops_operator_console(reason="backend importing", brief_ok=False)
    assert len(out["component_evidence"]) >= 3
    assert out["providers_honest"]["regime_router"]["probe"] == "Warming"
    assert "probe_table_note" in out["diagnostics"]
    assert "Recovery runbook" in out["diagnostics"]["page_intro"]


def test_degraded_ops_console_surfaces_backend_fatal_hint():
    hint = "No module named 'uvicorn' — pip install uvicorn"
    out = build_degraded_ops_operator_console(
        reason="backend importing",
        brief_ok=True,
        backend_fatal_hint=hint,
    )
    assert any("Backend crash" in b for b in out["blockers"])
    assert "uvicorn" in out["diagnostics"]["page_intro"]
    assert "Backend crash detected" in out["diagnostics"]["probe_table_note"]


def test_index_html_ops_uses_shared_degraded_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    ops = _ops_surface_html(raw)
    assert "opsDegradedCopy(" in ops
    assert "opsDegradedLine(" in ops
    assert "opsInferDegradedState(" in raw
    assert "opsGlobalLoadingLine(" in raw
    assert "opsUpdatesPanelTitle(" in ops
    assert "opsPanelLoadingShort(" in ops
    assert "opsProviderRuntimeFallbackLabel(" in ops
    assert "surfaceFetchHints.ops_error_log" in raw
    assert "Changelog timed out — showing fallback." not in ops
    assert "Probe only — refresh ops console" not in ops
    assert "opsProviderRuntimeFallbackLabel(" in ops
    assert "Probe available · runtime unknown" in raw
    assert "Probe only — runtime unconfirmed" in raw
    assert "opsProbeRuntimeFallbackRows()" in raw
    assert "opsFormatEvidence(" in ops
    assert "opsComponentLabel(" in ops
    assert "opsProbeLabel(" in ops
    assert "Probe vs runtime evidence" in ops
    assert "探測 vs 執行時證據" in ops
    assert "probe_table_note" in raw
    assert "opsDegradedLine('loading')" not in ops
    assert 'x-text="opsGlobalLoadingLine()"' in ops
    assert "API still loading — retry in a few seconds." not in ops


def test_index_html_ops_advanced_diagnostics_bilingual_wiring():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    ops = _ops_surface_html(raw)
    assert "opsAdvancedDiagnosticsTitle()" in ops
    assert "opsAdvancedDiagnosticsCollapsedTitle()" in ops
    assert "opsAdvancedCollapsedCopy()" in ops
    assert "opsAdvancedSectionKey(" in ops
    assert "opsAdvancedSectionStatus(" in ops


def test_index_html_autoschedule_button_is_clean():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert '@click="autoScheduleExperiments()"' in raw
    assert "total_proposed||0)+' experiment(s) proposed.'" in raw
    script_end = raw.lower().rfind("</script>")
    leak_idx = raw.find("total_proposed||0)+' experiment(s) proposed.'")
    assert leak_idx < script_end
    assert find_js_leaks_in_file(INDEX_HTML) == []
