"""Getting-started guides for Agent, Strategy Lab, and Shadow research surfaces."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_HELPERS = ROOT / "src" / "api" / "static" / "cc-helpers.js"
GUIDE_HTML = ROOT / "src" / "api" / "templates" / "cc" / "partials" / "guide.html"


def test_cc_helpers_research_getting_started_exported():
    js = CC_HELPERS.read_text(encoding="utf-8")
    assert "function researchGettingStarted" in js
    assert "researchGettingStarted: researchGettingStarted" in js
    assert "當 KO 跌破 20 日線時提醒我" in js
    assert "defensive_pullback" in js
    assert "影子帳戶" in js


def test_agent_getting_started_in_command_tab():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    cmd = raw.split("x-show=\"tab==='command'\"")[1].split("x-show=\"tab==='today'\"")[0]
    assert 'data-cc="agent-getting-started"' in cmd
    assert "researchGettingStarted('agent')" in cmd
    assert "submitAgentMonitorPrompt" in cmd
    assert "agentCreateRulesFromPlaybook" in cmd
    assert "agentMonitorFillExample" in cmd


def test_stratlab_getting_started_empty_state():
    stratlab = INDEX_HTML.read_text(encoding="utf-8").split('data-cc="stratlab-surface"')[1].split(
        'data-cc="btlab-surface"'
    )[0]
    assert 'data-cc="stratlab-getting-started"' in stratlab
    assert "researchGettingStarted('strategy')" in stratlab
    assert "generateStratLabDraft" in stratlab
    assert "stratLabGettingStartedVisible" in INDEX_HTML.read_text(encoding="utf-8")


def test_shadow_getting_started_empty_state():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    shadow = raw.split('data-cc="shadow-surface"')[1].split("Experiment History")[0]
    assert 'data-cc="shadow-getting-started"' in shadow
    assert "researchGettingStarted('shadow')" in shadow
    assert "importShadowTradesCsv" in raw
    assert "shadowGettingStartedVisible" in raw


def test_guide_partial_research_surfaces_section():
    guide = GUIDE_HTML.read_text(encoding="utf-8")
    assert "研究介面快速上手" in guide
    assert "Agent 盯盤" in guide
    assert "策略實驗室" in guide
    assert "影子帳戶" in guide
