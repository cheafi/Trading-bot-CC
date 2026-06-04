"""Cross-surface DOM ownership — deploy chrome stays on today/signals only."""

from __future__ import annotations

import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
DEPLOY_PARTIAL = (
    ROOT / "src" / "api" / "templates" / "cc" / "partials" / "deploy_surfaces.html"
)
BUILD_SCRIPT = ROOT / "scripts" / "build-cc-template.mjs"

TODAY_MAIN_OPEN = '<main x-show="tab===\'today\'"'
PLAYBOOK_MAIN_OPEN = '<main x-show="tab===\'signals\'"'
DISCOVERY_MARKER = 'data-cc="discovery-surface"'

DEPLOY_FORBIDDEN = (
    "deploy-status-strip",
    "today-deploy-chrome",
    "today-mission-panel",
    "today-dashboard-body",
    "FALLBACK / BRIEF ONLY",
    "Fallback board:",
)

RESEARCH_TABS = (
    ("ops", '<main x-show="tab===\'ops\'"'),
    ("rs", '<main x-show="tab===\'rs\'"'),
    ("scanners", DISCOVERY_MARKER),
    ("dossier", 'data-cc="dossier-surface"'),
    ("notrade", '<main x-show="tab===\'notrade\'"'),
    ("btlab", '<main x-show="tab===\'btlab\'"'),
    ("guide", 'data-cc="guide-surface"'),
)


def _read_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _html_only(raw: str) -> str:
    return raw[raw.index("<body") : raw.index("<!-- ══════ ALPINE JS ══════ -->")]


def _main_open_index(raw: str, open_marker: str) -> int:
    if open_marker.startswith("<main"):
        return raw.index(open_marker)
    match = re.search(
        rf"<main\b[^>]*{re.escape(open_marker)}[^>]*>",
        raw,
        re.I,
    )
    if not match:
        raise AssertionError(f"No <main> with marker {open_marker!r}")
    return match.start()


def _extract_main_block(raw: str, open_marker: str) -> str:
    """Return HTML for one <main> using tag-depth (not first </main>)."""
    start = _main_open_index(raw, open_marker)
    pos = start
    depth = 0
    while pos < len(raw):
        open_m = re.search(r"<main\b", raw[pos:], re.I)
        close_m = re.search(r"</main>", raw[pos:], re.I)
        if close_m is None:
            raise AssertionError(f"No closing </main> after {open_marker!r}")
        if open_m and open_m.start() < close_m.start():
            depth += 1
            pos += open_m.end()
            continue
        depth -= 1
        pos += close_m.end()
        if depth == 0:
            return raw[start:pos]
    raise AssertionError(f"Unbalanced <main> for {open_marker!r}")


def _surface_block(raw: str, open_marker: str) -> str:
    return _extract_main_block(raw, open_marker)


class _MainStackParser(HTMLParser):
    """Track whether deploy-status-strip opens while today main is on stack."""

    def __init__(self, body_html: str) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.today_main_depth: int | None = None
        self.deploy_strip_under_today = False
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
            return
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()


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


@pytest.mark.parametrize("tab,open_marker", RESEARCH_TABS)
def test_research_surface_excludes_deploy_chrome(tab: str, open_marker: str):
    raw = _read_index()
    block = _surface_block(raw, open_marker)
    leaked = [pat for pat in DEPLOY_FORBIDDEN if pat in block]
    assert not leaked, f"{tab} surface leaked deploy chrome: {leaked}"


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
    assert "today-mission-panel" not in playbook


def test_global_trust_strip_today_only():
    raw = _read_index()
    html = _html_only(raw)
    m = re.search(
        r'<div class="trust-strip" x-show="([^"]+)"[^>]*>\s*\n\s*<div class="flex items-center gap-2 flex-wrap trust-strip-tier-primary"',
        html,
    )
    assert m, "global trust-strip tier-primary block missing"
    assert m.group(1) == "live && tab==='today'", (
        "global trust strip must not render dashboard regime on research tabs"
    )


def test_deploy_partial_wrapped_with_today_tab_guard():
    partial = DEPLOY_PARTIAL.read_text(encoding="utf-8")
    assert 'x-show="tab===\'today\'"' in partial
    assert 'data-cc="today-deploy-chrome"' in partial
    assert 'data-cc="deploy-status-strip"' in partial
    assert partial.count("tab==='today'") >= 4


def test_deploy_partial_markers_only_in_today_section():
    raw = _read_index()
    deploy_start = raw.index("<!-- @cc-partial deploy_surfaces -->")
    today_start = raw.index(TODAY_MAIN_OPEN)
    today_block = _surface_block(raw, TODAY_MAIN_OPEN)
    assert raw.index(today_block) == today_start
    assert deploy_start < today_start + len(today_block)


def test_no_pf_summary_alpine_leak_patterns():
    raw = _read_index()
    html_only = _html_only(raw)
    assert "+pf.summary.total_value.toLocaleString()" not in html_only
    assert "portfolioSummaryPositionsLabel()+' · $'+pf" not in html_only
    assert "pf.summary.total_pnl>=" not in html_only
    assert not re.search(r'x-(?:show|if)="[^"]*total_positions>0', html_only)


def test_today_main_dom_stack_owns_deploy_strip():
    raw = _read_index()
    parser = _MainStackParser(_html_only(raw))
    parser.feed(_html_only(raw))
    assert parser.deploy_strip_under_today, "deploy-status-strip must nest under today main"
    assert not parser.stray_div_after_today_open


def test_playwright_surface_hooks_present():
    raw = _read_index()
    assert 'data-cc="today-surface"' in raw
    assert 'data-cc="playbook-surface"' in raw
    assert 'data-cc="discovery-surface"' in raw
    assert 'data-cc="deploy-status-strip"' in raw


def test_single_cc_app_and_surface_markers():
    raw = _read_index()
    assert raw.count("function cc(){return{") == 1
    assert raw.count('<!-- @cc-partial deploy_surfaces -->') == 1
    assert raw.count('data-cc="today-surface"') == 1
    assert raw.count('data-cc="playbook-surface"') == 1


def test_build_cc_template_check_passes():
    proc = subprocess.run(
        ["node", str(BUILD_SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
