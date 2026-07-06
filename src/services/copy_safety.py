"""
Global copy sanitizer — single module for operator-facing strings.

Wire through explainer, best_action, today_payload_builder, and card reasons.
Blocked / expired-brief paths must never leak pilot, half-size, or deploy language.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from src.services.fetch_surface_state import (
    remove_sizing_language_when_blocked,
    remove_trade_language_when_blocked,
    sanitize_blocked_candidate_copy,
)

Context = Optional[Dict[str, Any]]

_BRIEF_FALLBACK_RE = re.compile(r"brief[\s-]?fallback", re.IGNORECASE)
_BRIEF_FALLBACK_ZH_RE = re.compile(r"簡報備援|brief\s*fallback", re.IGNORECASE)


def _ctx(context: Context) -> Dict[str, Any]:
    return dict(context or {})


def brief_expired(context: Context) -> bool:
    c = _ctx(context)
    if c.get("brief_expired") is True:
        return True
    if str(c.get("brief_freshness") or "").lower() == "expired":
        return True
    age = c.get("brief_age_days")
    if age is not None and int(age) > 2:
        return True
    return False


def deploy_blocked(context: Context) -> bool:
    c = _ctx(context)
    if c.get("blocked") is True or c.get("deploy_blocked") is True:
        return True
    if c.get("deploy_authority") is False:
        return True
    tier = str(c.get("deploy_authority_tier") or c.get("deployAuthority") or "").lower()
    if tier in ("blocked", "paper_only"):
        return True
    if c.get("gates_active") is True:
        return True
    return False


def _strip_brief_fallback_language(text: str) -> str:
    out = str(text or "")
    if not out:
        return out
    out = _BRIEF_FALLBACK_RE.sub("brief expired — excluded from ranking", out)
    out = _BRIEF_FALLBACK_ZH_RE.sub("簡報已過期 — 不納入排名", out)
    out = out.replace("brief-fallback", "brief expired")
    out = out.replace("fallback brief", "brief expired")
    return out


def sanitize_for_render(text: Union[str, List[str], None], context: Context = None) -> str:
    """Sanitize operator copy for render — respects blocked + brief-expired context."""
    if text is None:
        return ""
    if isinstance(text, list):
        parts = [sanitize_for_render(part, context) for part in text if part]
        return " · ".join(p for p in parts if p)
    out = str(text).strip()
    if not out:
        return out

    c = _ctx(context)
    if brief_expired(c) or brief_expired(c.get("system_truth")):
        out = _strip_brief_fallback_language(out)

    truth = c.get("system_truth")
    blocked = deploy_blocked(c) or (isinstance(truth, dict) and deploy_blocked(truth))
    if blocked:
        out = remove_trade_language_when_blocked(out, blocked=True)
        out = remove_sizing_language_when_blocked(out, blocked=True)

    surface = str(c.get("surface") or "").lower()
    if surface in ("discovery", "funds", "flow", "shadow", "strategy"):
        if "actionable" in out.lower() and blocked:
            out = out.replace("actionable", "research context")
            out = out.replace("ACTIONABLE", "research context")

    return out


def sanitize_card_row(row: Optional[Dict[str, Any]], *, context: Context = None) -> Dict[str, Any]:
    """Sanitize action_reason / why_now on a candidate row in-place copy."""
    r = dict(row or {})
    c = _ctx(context)
    blocked = deploy_blocked(c) or deploy_blocked(c.get("system_truth"))
    if blocked:
        line = sanitize_blocked_candidate_copy(
            r,
            blocked=True,
            blocker=str(
                c.get("blocker")
                or (c.get("system_truth") or {}).get("primary_blocker")
                or "no pilot entry — deploy authority blocked"
            ),
        )
        r["action_reason"] = line
        r["display_copy"] = line
        if r.get("why_now"):
            wn = r["why_now"]
            if isinstance(wn, list):
                r["why_now"] = [sanitize_for_render(x, context) for x in wn]
            else:
                r["why_now"] = [sanitize_for_render(wn, context)]
    else:
        for key in ("action_reason", "action_rationale", "why_now", "display_copy", "summary"):
            if key not in r or r[key] in (None, "", []):
                continue
            val = r[key]
            if isinstance(val, list):
                r[key] = [sanitize_for_render(x, context) for x in val]
            else:
                r[key] = sanitize_for_render(val, context)
    return r


def sanitize_rows(
    rows: Optional[List[Dict[str, Any]]],
    *,
    context: Context = None,
) -> List[Dict[str, Any]]:
    return [sanitize_card_row(row, context=context) for row in list(rows or [])]
