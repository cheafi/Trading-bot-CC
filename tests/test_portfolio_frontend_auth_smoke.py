"""Smoke checks: dashboard JS uses server-injected key, not hardcoded secrets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_index_injects_api_key_from_template_not_static_secret() -> None:
    html = (ROOT / "src/api/templates/index.html").read_text(encoding="utf-8")
    assert "cc-api-key" in html
    assert "{{ api_key" in html
    assert "API_SECRET_KEY" not in html


def test_cc_app_portfolio_decision_uses_cc_fetch_with_api_key_header() -> None:
    js = (ROOT / "src/api/static/cc-app.js").read_text(encoding="utf-8")
    assert 'ccFetch("/api/v7/portfolio-decision"' in js
    assert '"X-API-Key": window._apiKey' in js


def test_cc_app_alerts_history_sends_api_key_header() -> None:
    js = (ROOT / "src/api/static/cc-app.js").read_text(encoding="utf-8")
    assert "/api/portfolio/alerts-history" in js
    idx = js.index("/api/portfolio/alerts-history")
    snippet = js[max(0, idx - 200) : idx + 200]
    assert "window._apiKey" in snippet
