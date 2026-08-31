"""Attention Budget — category time limits (research_only, display only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

DEFAULT_BUDGETS: Dict[str, int] = {
    "research": 60,
    "portfolio": 30,
    "market": 15,
}

_CATEGORY_LABELS: Dict[str, str] = {
    "research": "Research · 研究",
    "portfolio": "Portfolio · 持倉",
    "market": "Market · 市場",
}

_ENOUGH_MESSAGE = "Enough — come back tomorrow · 夠了 — 明天再來"
_ENOUGH_MESSAGE_BILINGUAL = (
    "Enough — come back tomorrow · 夠了 — 明天再來"
)


def budget_schema() -> Dict[str, Any]:
    """Default category budgets for client-side session tracking."""
    categories: List[Dict[str, Any]] = []
    for cat_id, minutes in DEFAULT_BUDGETS.items():
        categories.append(
            {
                "id": cat_id,
                "label": _CATEGORY_LABELS.get(cat_id, cat_id),
                "budget_minutes": minutes,
            }
        )
    return {
        "authority": "research_only",
        "categories": categories,
        "default_budgets": dict(DEFAULT_BUDGETS),
        "tracking": "client_localStorage",
        "enough_message": _ENOUGH_MESSAGE,
        "enough_message_bilingual": _ENOUGH_MESSAGE_BILINGUAL,
        "headline": "Attention Budget · 專注預算 — CIIO says Enough when expired",
    }


def build_attention_budget_summary(
    *,
    usage: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Summarize attention budget — optional client-reported usage from query/body.

    Server stores defaults only; session minutes tracked in browser localStorage.
    """
    schema = budget_schema()
    reported = usage or {}
    categories_out: List[Dict[str, Any]] = []
    any_exceeded = False
    for cat in schema["categories"]:
        cat_id = cat["id"]
        budget = int(cat["budget_minutes"])
        used = int(reported.get(cat_id) or 0)
        remaining = max(0, budget - used)
        exceeded = used >= budget
        if exceeded:
            any_exceeded = True
        categories_out.append(
            {
                **cat,
                "used_minutes": used,
                "remaining_minutes": remaining,
                "exceeded": exceeded,
            }
        )
    total_budget = sum(c["budget_minutes"] for c in schema["categories"])
    total_used = sum(c["used_minutes"] for c in categories_out)
    return {
        **schema,
        "status": "exceeded" if any_exceeded else "ok",
        "categories_live": categories_out,
        "total_budget_minutes": total_budget,
        "total_used_minutes": total_used,
        "total_remaining_minutes": max(0, total_budget - total_used),
        "any_exceeded": any_exceeded,
        "ciio_message": _ENOUGH_MESSAGE if any_exceeded else "",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
