"""Cross-surface DOM ownership — deploy chrome stays on today/signals only."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
DEPLOY_PARTIAL = (
    ROOT / "src" / "api" / "templates" / "cc" / "partials" / "deploy_surfaces.html"
)

TODAY_MAIN_OPEN = '<main x-show="tab===\'today\'"'
PLAYBOOK_MAIN_OPEN = '<main x-show="tab===\'signals\'"'
DISCOVERY_MARKER = 'data-cc="discovery-surface"'

TODAY_ONLY_MARKERS = (
    "deploy-status-strip",
    "today-deploy-chrome",
    "today-mission-panel",
    "today-dashboard-body",
    "FALLBACK / BRIEF ONLY",
    "honestFunnelLabel(today7.filter_funnel",
)

RESEARCH_SURFACES: list[tuple[str, str]] = [
    ("rs", 'data-cc="rs-surface"'),
    ("scanners", DISCOVERY_MARKER),
    ("dossier", 'data-cc="dossier-surface"'),
    ("guide", 'data-cc="guide-surface"'),
    ("ops", 'data-cc="ops-surface"'),
    ("notrade", 'data-cc="rejections-surface"'),
    ("btlab", 'data-cc="btlab-surface"'),
]


def _read_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _surface_block(raw: str, open_marker: str) -> str:
    start = raw.index(open_marker)
    end = raw.index("</main>", start) + len("</main>")
    return raw[start:end]


class _MainStackParser(HTMLParser):
    """Track whether deploy-status-strip opens while today main is on stack."""

    def __init__(self, body_html: str) -> None:
        super().__init__()
        self._body = body_html
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.today_main_depth: int | None = None
        self.deploy_strip_under_today = False
        self.today_main_orphan_close = False
        self.stray_div_after_today_open = False
        self._today_open_line: int | None = None

    def _file_line(self) -> int:
        return self.getpos()[0]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrd = {k: (v or "") for k, v in attrs}
        self.stack.append((tag, attrd))
        if tag == "main" and attrd.get("x-show") == "tab==='today'":
            self.today_main_depth = len(self.stack)
            self._today_open_line = self._file_line()
        if (
            tag == "div"
            and attrd.get("data-cc") == "deploy-status-strip"
            and self.today_main_depth is not None
            and len(self.stack) >= self.today_main_depth
        ):
            self.deploy_strip_under_today = True

    def handle_endtag(self, tag: str) -> None:
        if (
            tag == "div"
            and self._today_open_line is not None
            and self._file_line() == self._today_open_line + 1
            and self.stack
            and self.stack[-1][0] == "main"
            and self.stack[-1][1].get("x-show") == "tab==='today'"
        ):
            self.stray_div_after_today_open = True
        if tag == "main" and (not self.stack or self.stack[-1][0] != "main"):
            if self.today_main_depth is not None:
                self.today_main_orphan_close = True
            return
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()


def _body_html(raw: str) -> str:
    body_start = raw.index("<body")
    script_marker = raw.index("<!-- ══════ ALPINE JS ══════ -->")
    return raw[body_start:script_marker]


def test_today_main_opens_without_stray_div_close():
    raw = _read_index()
    idx = raw.index(TODAY_MAIN_OPEN)
    after = raw[idx + len(TODAY_MAIN_OPEN) : idx + len(TODAY_MAIN_OPEN) + 120]
    assert not after.lstrip().startswith("</div>"), (
        "stray </div> after today <main> breaks tab guard (HTML5 auto-closes main)"
    )


def test_deploy_status_strip_inside_today_main_block():
    raw = _read_index()
    today = _surface_block(raw, TODAY_MAIN_OPEN)
    assert 'data-cc="deploy-status-strip"' in today
    assert 'data-cc="today-deploy-chrome"' in today
    assert 'data-cc="today-dashboard-body"' in today


def test_discovery_surface_excludes_deploy_strip():
    raw = _read_index()
    discovery = _surface_block(raw, DISCOVERY_MARKER)
    assert "deploy-status-strip" not in discovery
    assert "today-deploy-chrome" not in discovery
    assert "FALLBACK / BRIEF ONLY" not in discovery


def test_playbook_surface_excludes_today_deploy_strip():
    raw = _read_index()
    playbook = _surface_block(raw, PLAYBOOK_MAIN_OPEN)
    assert "deploy-status-strip" not in playbook
    assert "today-deploy-chrome" not in playbook


@pytest.mark.parametrize("tab_name,open_marker", RESEARCH_SURFACES)
def test_research_surface_excludes_today_deploy_chrome(tab_name: str, open_marker: str):
    raw = _read_index()
    block = _surface_block(raw, open_marker)
    for needle in TODAY_ONLY_MARKERS:
        assert needle not in block, f"{tab_name} surface must not contain {needle!r}"


def test_deploy_partial_wrapped_with_today_tab_guard():
    partial = DEPLOY_PARTIAL.read_text(encoding="utf-8")
    assert 'x-show="tab===\'today\'"' in partial
    assert 'data-cc="today-deploy-chrome"' in partial
    assert 'data-cc="deploy-status-strip"' in partial
    assert 'x-show="tab===\'today\'" data-cc="deploy-status-strip"' in partial


def test_deploy_partial_markers_only_in_today_section():
    raw = _read_index()
    deploy_start = raw.index("<!-- @cc-partial deploy_surfaces -->")
    today_start = raw.index(TODAY_MAIN_OPEN)
    today_end = raw.index("</main>", today_start)
    assert today_start < deploy_start < today_end


def test_no_pf_summary_alpine_leak_patterns():
    raw = _read_index()
    html_only = raw[raw.index("<body") : raw.index("<!-- ══════ ALPINE JS ══════ -->")]
    assert "+pf.summary.total_value.toLocaleString()" not in html_only
    assert "portfolioSummaryPositionsLabel()+' · $'+pf" not in html_only
    assert not re.search(r'x-(?:show|if)="[^"]*total_positions>0', html_only)


def test_today_main_dom_stack_owns_deploy_strip():
    raw = _read_index()
    parser = _MainStackParser(_body_html(raw))
    parser.feed(_body_html(raw))
    assert parser.deploy_strip_under_today, "deploy-status-strip must nest under today main"
    assert not parser.stray_div_after_today_open


def test_playwright_surface_hooks_present():
    raw = _read_index()
    assert 'data-cc="today-surface"' in raw
    assert 'data-cc="playbook-surface"' in raw
    assert 'data-cc="discovery-surface"' in raw
    assert 'data-cc="rs-surface"' in raw
    assert 'data-cc="deploy-status-strip"' in raw


def test_header_context_scopes_board_fallback_to_dashboard_playbook():
    raw = _read_index()
    idx = raw.index("headerContext(){")
    body = raw[idx : idx + 900]
    assert "mode==='dashboard_core'&&this.todayUsesBriefFallback()" in body
    assert "mode==='playbook_core'&&this.playbookUsesBriefFallback()" in body
    assert "this.todayUsesBriefFallback()||this.playbookUsesBriefFallback()" not in body


def test_build_cc_template_check_passes():
    import subprocess

    root = INDEX_HTML.resolve().parents[3]
    proc = subprocess.run(
        ["node", "scripts/build-cc-template.mjs", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
