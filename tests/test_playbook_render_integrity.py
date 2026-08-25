"""Playbook UI string integrity — no visible $1/$2 replace placeholders."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def _playbook_unlock_detail_block() -> str:
    raw = INDEX_HTML.read_text(encoding="utf-8")
    idx = raw.index("playbookUnlockConditionDetail(c){")
    return raw[idx : idx + 1400]


def test_playbook_unlock_detail_uses_capture_not_dollar_one():
    """Board detail uses funnel authority; fallback replace uses capture group n."""
    body = _playbook_unlock_detail_block()
    assert "(m,n)=>'$1 scan-ranked" not in body
    assert "funnel watch-qualified" in body
    assert "scan-ranked (not watch-qualified)" in body
    assert "n+' scan-ranked (not watch-qualified)'" in body


def test_playbook_unlock_detail_replace_produces_numeric_count():
    """Mirror JS replace logic — count must appear, not $1."""
    sample = "50 validated · data STALE"
    out = re.sub(
        r"\b(\d+)\s+validated\b",
        lambda m: f"{m.group(1)} scan-ranked (not watch-qualified)",
        sample,
        flags=re.IGNORECASE,
    )
    assert out == "50 scan-ranked (not watch-qualified) · data STALE"
    assert "$1" not in out


def test_index_html_no_callback_replace_dollar_placeholders():
    """Audit: no (m,n)=>'$N' patterns in template JS."""
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert not re.search(r"\([^)]*\)\s*=>\s*['\"]\$\d", raw)
