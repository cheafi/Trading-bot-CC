"""
Alpha Review Items — structured review findings without deploy authority.

No deploy recommendations, no auto-loosen. authority_effect=none.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

REVIEW_SEVERITIES: Tuple[str, ...] = ("info", "warning", "critical")
REVIEW_CATEGORIES: Tuple[str, ...] = (
    "sample",
    "baseline",
    "overfit",
    "conversion",
    "attribution",
    "missed_opportunity",
    "governor",
    "rule",
    "no_edge",
    "stage",
)

ALLOWED_ACTIONS: Tuple[str, ...] = (
    "monitor",
    "collect_more_samples",
    "tighten",
    "mute",
    "retire",
    "keep",
    "human_review",
    "convert_to_playbook_review",
)

BLOCKED_ACTIONS: Tuple[str, ...] = (
    "deploy",
    "auto_loosen",
    "loosen_threshold",
    "open_deploy_authority",
    "size_position",
    "handoff_trade",
)


@dataclass
class ReviewItem:
    item_id: str
    title: str
    severity: str = "info"
    category: str = "sample"
    summary: str = ""
    recommended_action: str = "monitor"
    allowed_action: str = "monitor"
    blocked_action: str = "deploy"
    requires_human_review: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)
    authority_effect: str = "none"
    may_authorize_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["may_authorize_deploy"] = False
        d["authority_effect"] = "none"
        if d["recommended_action"] in BLOCKED_ACTIONS:
            d["recommended_action"] = "human_review"
        if d["allowed_action"] in BLOCKED_ACTIONS:
            d["allowed_action"] = "monitor"
        return d


def _new_item_id(prefix: str = "ari") -> str:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


def make_review_item(
    *,
    title: str,
    category: str = "sample",
    severity: str = "info",
    summary: str = "",
    recommended_action: str = "monitor",
    allowed_action: Optional[str] = None,
    blocked_action: str = "deploy",
    requires_human_review: bool = False,
    evidence: Optional[Dict[str, Any]] = None,
) -> ReviewItem:
    """Factory — sanitizes blocked deploy/loosen actions."""
    rec = recommended_action if recommended_action not in BLOCKED_ACTIONS else "human_review"
    allowed = allowed_action or rec
    if allowed in BLOCKED_ACTIONS:
        allowed = "monitor"
    return ReviewItem(
        item_id=_new_item_id(),
        title=title,
        severity=severity if severity in REVIEW_SEVERITIES else "info",
        category=category if category in REVIEW_CATEGORIES else "sample",
        summary=summary,
        recommended_action=rec,
        allowed_action=allowed,
        blocked_action=blocked_action,
        requires_human_review=requires_human_review,
        evidence=dict(evidence or {}),
    )


def sort_review_items(items: List[ReviewItem]) -> List[ReviewItem]:
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(items, key=lambda i: (order.get(i.severity, 3), i.category, i.title))


def review_items_summary(items: List[ReviewItem]) -> Dict[str, Any]:
    rows = [i.to_dict() for i in sort_review_items(items)]
    human = [r for r in rows if r.get("requires_human_review")]
    return {
        "total": len(rows),
        "critical": sum(1 for r in rows if r.get("severity") == "critical"),
        "warning": sum(1 for r in rows if r.get("severity") == "warning"),
        "human_review_count": len(human),
        "items": rows[:12],
        "human_review_items": human[:6],
        "may_authorize_deploy": False,
        "authority_effect": "none",
    }
