"""
Guards against leaking raw JS/handler fragments into CC HTML output.

Used by export tests and server-side template validation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Pattern

# Patterns that indicate a truncated handler tail pasted into visible HTML.
_JS_LEAK_PATTERNS: List[Pattern[str]] = [
    re.compile(r"led',e\);alert\("),
    re.compile(r"</html>[^{]*catch\(e\)", re.IGNORECASE),
    re.compile(r"</html>[^<]+\}\s*,\s*\}\}", re.IGNORECASE),
    re.compile(r"</html>oSchedule=", re.IGNORECASE),
    re.compile(r"^\s*\}\s*,\s*\}\}\s*$"),
    re.compile(r"console\.warn\s*\(\s*'auto-schedule failed'"),
]

_OBJECT_OBJECT = re.compile(r"\[object Object\]", re.IGNORECASE)

_HANDLER_FRAGMENT = re.compile(
    r"(?:catch\s*\(\s*\w+\s*\)\s*\{|alert\s*\(|console\.warn\s*\()",
    re.IGNORECASE,
)


def contains_js_leak_fragment(text: str) -> bool:
    """Return True if text looks like leaked JS/handler markup."""
    if not text:
        return False
    return any(p.search(text) for p in _JS_LEAK_PATTERNS)


def contains_object_object_leak(text: str) -> bool:
    return bool(_OBJECT_OBJECT.search(text or ""))


def sanitize_visible_text(text: str) -> str:
    """Strip dynamic copy that resembles handler fragments before render."""
    if not text:
        return ""
    if contains_js_leak_fragment(text):
        return ""
    if contains_object_object_leak(text):
        return "Evidence unavailable"
    if _HANDLER_FRAGMENT.search(text) and ("});" in text or "}, }}" in text):
        return ""
    return text.strip()


def format_visible_value(value: object, default: str = "—") -> str:
    """Safe string for x-text / evidence fields — never [object Object]."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        s = value.strip()
        return sanitize_visible_text(s) or default
    if isinstance(value, dict):
        for key in ("label", "tier", "badge", "text", "summary"):
            if value.get(key) is not None:
                return format_visible_value(value[key], default)
        return default
    if isinstance(value, list):
        parts = [format_visible_value(v, "") for v in value]
        joined = " · ".join(p for p in parts if p and p != default)
        return joined or default
    return default


def find_js_leaks_in_file(path: Path) -> List[str]:
    """Scan a template file for known leak signatures (post-</html> tails, etc.)."""
    raw = path.read_text(encoding="utf-8")
    hits: List[str] = []
    close = raw.lower().rfind("</html>")
    if close >= 0:
        tail = raw[close + len("</html>") :].strip()
        if tail:
            hits.append(f"content_after_html_close:{tail[:80]!r}")
            if contains_js_leak_fragment(tail):
                hits.append("known_js_leak_pattern_in_tail")
    if contains_js_leak_fragment(raw) and "auto-schedule failed" in raw:
        # Only flag if leak pattern appears outside the main script block
        script_end = raw.lower().rfind("</script>")
        html_end = raw.lower().rfind("</html>")
        for pat in _JS_LEAK_PATTERNS:
            for m in pat.finditer(raw):
                pos = m.start()
                if script_end >= 0 and pos > script_end and pos < html_end:
                    hits.append(f"js_leak_outside_script:{m.group()[:40]!r}")
    return hits


def assert_template_render_safe(paths: Iterable[Path]) -> None:
    """Raise AssertionError if any template path contains render leaks."""
    problems: List[str] = []
    for path in paths:
        for hit in find_js_leaks_in_file(path):
            problems.append(f"{path}: {hit}")
    if problems:
        raise AssertionError("UI render safety violations:\n" + "\n".join(problems))
