"""Load CC consolidated project briefing for Guide tab ChatGPT advisory panel."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_BRIEFING_REL = Path("docs") / "CC_CONSOLIDATED_BRIEFING.md"
_DOC_PATH_LABEL = "docs/CC_CONSOLIDATED_BRIEFING.md"


def _briefing_path_candidates() -> List[Path]:
    """Resolve briefing markdown in Docker (/app) and local repo layouts."""
    here = Path(__file__).resolve()
    roots = (
        here.parents[2],  # repo root from src/services/
        Path("/app"),  # Docker WORKDIR
        Path.cwd(),
    )
    seen: set[str] = set()
    candidates: List[Path] = []
    for root in roots:
        path = (root / _BRIEFING_REL).resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def resolve_briefing_path() -> Optional[Path]:
    """Return the first existing CC consolidated briefing markdown path."""
    for path in _briefing_path_candidates():
        if path.is_file():
            return path
    return None


BRIEFING_PATH = resolve_briefing_path() or _briefing_path_candidates()[0]

_PROMPT_TITLES_ZH: Dict[str, str] = {
    "authority audit": "權限審計",
    "ops diagnostics": "維運診斷",
    "i18n strategy": "雙語策略",
    "discord setup": "Discord 設定",
    "research vs deploy boundary": "研究 vs 部署邊界",
    "architecture review": "架構審查",
    "ops honesty model": "維運誠實模型",
    "performance": "效能優化",
    "testing plan": "測試計劃",
    "ibkr monitor ladder": "IBKR 監控階梯",
}

_FALLBACK_PROMPTS: List[Dict[str, str]] = [
    {
        "id": "authority_audit",
        "title_zh": "權限審計",
        "title_en": "Authority audit",
        "title": "權限審計 · Authority audit",
        "text": (
            "Given the authority model in §2, review my planned feature [describe feature] "
            "and tell me which tab(s) it belongs on, what `PageCapability` flags it needs, "
            "and what gates must block it when tradeability is WAIT."
        ),
    },
    {
        "id": "ops_diagnostics",
        "title_zh": "維運診斷",
        "title_en": "Ops diagnostics",
        "title": "維運診斷 · Ops diagnostics",
        "text": (
            "My Ops tab shows engine off and insufficient sample on advanced diagnostics. "
            "Using §6–7, give me a step-by-step recovery checklist for Docker dev "
            "(`cc_api_dev`) including which env vars to verify and which `/health` / "
            "`/api/ops` endpoints to hit."
        ),
    },
    {
        "id": "i18n_strategy",
        "title_zh": "雙語策略",
        "title_en": "i18n strategy",
        "title": "雙語策略 · i18n strategy",
        "text": (
            "§9 says Chinese is incomplete. Propose a maintainable i18n plan for CC that "
            "doesn't break the 14k-line `index.html` tests — should we extend `cc-i18n.js`, "
            "move Ops strings server-side, or extract a locale JSON? Prioritize Ops "
            "probe/runtime and advanced diagnostics."
        ),
    },
    {
        "id": "discord_setup",
        "title_zh": "Discord 設定",
        "title_en": "Discord setup",
        "title": "Discord 設定 · Discord setup",
        "text": (
            "I want reliable operator alerts without bot permission issues. Based on §6 and "
            "the Discord dispatch architecture, recommend webhook vs bot mode and exact "
            "`.env` keys for my setup (macOS Docker dev)."
        ),
    },
    {
        "id": "research_vs_deploy_boundary",
        "title_zh": "研究 vs 部署邊界",
        "title_en": "Research vs deploy boundary",
        "title": "研究 vs 部署邊界 · Research vs deploy boundary",
        "text": (
            "I'm building [Vibe Agent rule / Strategy Lab draft / Shadow analysis]. Confirm "
            "it cannot grant deploy authority, list the API surfaces involved, and suggest "
            "UX copy that makes the research-only boundary obvious to a Chinese-speaking "
            "operator."
        ),
    },
]

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}"),
)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug or "prompt"


def _extract_summary(text: str) -> str:
    purpose_lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("> **Purpose"):
            purpose_lines.append(stripped.lstrip("> ").strip())
        elif stripped.startswith("> ") and purpose_lines:
            purpose_lines.append(stripped.lstrip("> ").strip())
        elif purpose_lines and not stripped.startswith(">"):
            break
    if purpose_lines:
        return " ".join(purpose_lines)
    return (
        "CC consolidated project briefing for external advisors. "
        "Copy to ChatGPT for architecture/ops guidance — research/monitor framing only."
    )


def _extract_version(text: str) -> str:
    match = re.search(r"\*\*Version:\*\*\s*([0-9.]+)", text)
    return match.group(1) if match else ""


def _extract_prompts(text: str) -> List[Dict[str, str]]:
    section_match = re.search(
        r"## 10\. Suggested Advisory Prompts[\s\S]*?(?=\n---|\n## |\Z)",
        text,
    )
    if not section_match:
        return list(_FALLBACK_PROMPTS)

    section = section_match.group(0)
    prompts: List[Dict[str, str]] = []
    pattern = re.compile(
        r"\d+\.\s+\*\*([^*]+):\*\*\s+\"([^\"]+)\"",
        re.MULTILINE,
    )
    for match in pattern.finditer(section):
        title_en = match.group(1).strip()
        prompt_text = match.group(2).strip()
        key = title_en.lower()
        title_zh = _PROMPT_TITLES_ZH.get(key, title_en)
        prompts.append(
            {
                "id": _slugify(title_en),
                "title_zh": title_zh,
                "title_en": title_en,
                "title": f"{title_zh} · {title_en}",
                "text": prompt_text,
            }
        )
    return prompts if prompts else list(_FALLBACK_PROMPTS)


def _scrub_secrets(text: str) -> str:
    scrubbed = text
    for pattern in _SECRET_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed


def load_guide_briefing() -> Dict[str, Any]:
    """Read fixed briefing markdown and return API-safe advisory payload."""
    briefing_path = resolve_briefing_path()
    if briefing_path is None:
        return {
            "summary": _extract_summary(""),
            "prompts": list(_FALLBACK_PROMPTS),
            "full_markdown": "",
            "doc_path": _DOC_PATH_LABEL,
            "version": "",
            "authority_note": (
                "Reference-only — this panel does not grant deploy authority. "
                "研究/監控參考 only."
            ),
            "missing": True,
        }

    raw = briefing_path.read_text(encoding="utf-8")
    safe = _scrub_secrets(raw)
    return {
        "summary": _extract_summary(safe),
        "prompts": _extract_prompts(safe),
        "full_markdown": safe,
        "doc_path": _DOC_PATH_LABEL,
        "version": _extract_version(safe),
        "authority_note": (
            "Reference-only — this panel does not grant deploy authority. "
            "研究/監控參考 only."
        ),
        "missing": False,
    }
