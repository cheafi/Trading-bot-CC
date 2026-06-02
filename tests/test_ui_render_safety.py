"""Ensure CC templates never leak raw JS fragments into visible HTML."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.ui_render_safety import (
    assert_template_render_safe,
    contains_js_leak_fragment,
    find_js_leaks_in_file,
    sanitize_visible_text,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_index_html_has_no_post_close_leak():
    hits = find_js_leaks_in_file(INDEX_HTML)
    assert hits == [], f"index.html render leaks: {hits}"


def test_index_html_passes_template_render_safe():
    assert_template_render_safe([INDEX_HTML])


def test_contains_js_leak_fragment_detects_known_tail():
    assert contains_js_leak_fragment("led',e);alert('Auto-schedule failed: '+e.message)}")
    assert not contains_js_leak_fragment("Guide mode — reference only")


def test_sanitize_visible_text_strips_handler_fragments():
    dirty = "led',e);alert('Auto-schedule failed: '+e.message)} }, }}"
    assert sanitize_visible_text(dirty) == ""
    assert sanitize_visible_text("Reference only · Decision surfaces suspended") == (
        "Reference only · Decision surfaces suspended"
    )


def test_index_html_has_no_autoschedule_leak_substrings():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "</html>oSchedule" not in raw
    close = raw.lower().rfind("</html>")
    tail = raw[close + len("</html>") :].strip()
    assert tail == "", f"post-</html> leak: {tail[:80]!r}"
    assert "await this.fetchABStatus();" not in tail
    # Handler tail must stay inside the main cc() script block, never after </html>
    script_end = raw.lower().rfind("</script>")
    html_end = raw.lower().rfind("</html>")
    pos = raw.find("async autoScheduleExperiments()")
    assert pos >= 0, "autoScheduleExperiments handler missing from template"
    assert pos < script_end, "autoSchedule handler leaked outside script block"
    assert script_end < html_end


def test_index_html_autoschedule_handler_not_visible_fragment():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    fragment = "_handleAutoScheduleError(e);} }, }}"
    assert fragment not in raw
    assert "}}, }}" not in raw


def test_index_html_fallback_confidence_single_binding():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "confidenceBannerLine(opp)" in raw
    assert "confidenceIsFallback(opp)" in raw
    assert raw.count("Fallback confidence — non-comparable") == 0
    assert "confidence_label||'Fallback confidence" not in raw


def test_index_html_fallback_sizing_gates():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "cardShowsExecutableSizing" in raw
    assert "cardSizingNote" in raw
    assert "Sizing suspended in fallback mode" in raw


def test_index_html_today_regime_uses_canonical_line():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    today_start = raw.find("x-show=\"tab==='today'\"")
    assert today_start > 0
    today_chunk = raw[today_start : today_start + 120000]
    assert today_chunk.count("canonicalRegimeLine()") >= 3
    assert "(today7.todays_decision.regime?.trend||'—')+' · '" not in today_chunk
    assert "(today7.regime.trend||'—')+' · '+(today7.tradeability" not in today_chunk


def test_index_html_error_log_unavailable_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "Error log fetch failed:" not in raw
    assert "Unable to confirm whether errors were logged this session" in raw
    assert "!errorLog.loading && !errorLog.entries.length && !errorLog.error" in raw


def test_index_html_ops_degraded_helpers_present():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "opsDegradedCopy(" in raw
    assert "opsDegradedLine(" in raw


def test_assert_template_render_safe_raises_on_leak(tmp_path: Path):
    bad = tmp_path / "bad.html"
    bad.write_text("<html></html>led',e);alert('fail')", encoding="utf-8")
    with pytest.raises(AssertionError, match="render safety"):
        assert_template_render_safe([bad])
