"""Guide tab consolidated briefing API and panel integrity."""

from __future__ import annotations

from pathlib import Path

from src.services.guide_briefing import load_guide_briefing

ROOT = Path(__file__).resolve().parents[1]
GUIDE_PARTIAL = ROOT / "src" / "api" / "templates" / "cc" / "partials" / "guide.html"
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_APP = ROOT / "src" / "api" / "static" / "cc-app.js"


def test_load_guide_briefing_returns_section_ten_prompts():
    data = load_guide_briefing()
    assert len(data["prompts"]) == 10
    assert data["missing"] is False
    assert data["full_markdown"]
    assert "CC / TradingAI Bot" in data["full_markdown"]
    assert data["doc_path"] == "docs/CC_CONSOLIDATED_BRIEFING.md"
    assert "deploy authority" in data["authority_note"].lower()


def test_guide_briefing_prompt_titles_bilingual():
    data = load_guide_briefing()
    titles = {p["title_en"] for p in data["prompts"]}
    assert "Authority audit" in titles
    assert "Research vs deploy boundary" in titles
    for p in data["prompts"]:
        assert " · " in p["title"]
        assert p["title_zh"]
        assert p["text"]


def test_guide_briefing_scrubs_obvious_secrets():
    data = load_guide_briefing()
    body = data["full_markdown"]
    assert "sk-" not in body.lower() or "[REDACTED]" in body


def test_guide_partial_project_briefing_panel():
    html = GUIDE_PARTIAL.read_text(encoding="utf-8")
    assert "cc-project-briefing-panel" in html
    assert "Project briefing (for ChatGPT)" in html
    assert "Suggested prompts" in html
    assert "does not grant deploy authority" in html
    assert "copyGuidePrompt" in html
    assert "copyGuideBriefingFull" in html


def test_cc_app_guide_briefing_helpers():
    js = CC_APP.read_text(encoding="utf-8")
    assert "fetchGuideBriefing()" in js
    assert "ccCopyText(text)" in js
    assert "guideBriefing:" in js
    assert "switchTab" in js
    assert "if(tSafe==='guide')" in js


def test_index_html_guide_briefing_panel_inlined():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "cc-project-briefing-panel" in raw
    assert "專案簡報 · Project briefing (for ChatGPT)" in raw
