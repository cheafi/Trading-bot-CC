"""Research Console — PM-grade Strategy Lab UX contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"
CC_APP = ROOT / "src/api/static/cc-app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_research_console_surface_in_index():
    html = _read(INDEX)
    assert 'data-cc="research-console"' in html
    assert "Research Console" in html
    assert "researchIdosBlock()" in html
    assert "runResearchTaskQuick(" in html
    assert "loadShadowFromLocal()" in html
    assert "research-console-kpi" in html


def test_research_console_js_helpers():
    js = _read(CC_APP)
    assert "fetchResearchConsoleBootstrap" not in js  # merged into fetchStrategyLabShell
    assert "/api/v7/research/console/bootstrap" in js
    assert "researchIdosBlock()" in js
    assert "runResearchTaskQuick(" in js
    assert "exportResearchTdxMt5()" in js
    assert "strategyLabTeamsList()" in js
    assert "sendResearchToPlaybook()" in js
    assert "fetchPortfolioCorrelationSurface()" in js
    assert "researchWorkflowStepper()" in js


def test_portfolio_correlation_surface_in_index():
    html = _read(INDEX)
    assert 'data-cc="portfolio-correlation-surface"' in html
    assert "fetchPortfolioCorrelationSurface()" in html


def test_playbook_research_handoff_banner():
    html = _read(INDEX)
    assert 'data-cc="research-playbook-handoff"' in html


def test_bootstrap_route_registered():
    router = _read(ROOT / "src/api/routers/research_integrations.py")
    assert "/console/bootstrap" in router
