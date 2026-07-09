"""Alpha review items — blocked deploy/auto-loosen."""

from __future__ import annotations

from src.services.alpha_review_items import (
    BLOCKED_ACTIONS,
    make_review_item,
    review_items_summary,
    sort_review_items,
)


def test_blocked_deploy_action_sanitized():
    item = make_review_item(
        title="Test",
        recommended_action="deploy",
        allowed_action="auto_loosen",
    )
    d = item.to_dict()
    assert d["recommended_action"] == "human_review"
    assert d["allowed_action"] == "monitor"
    assert d["may_authorize_deploy"] is False
    assert d["authority_effect"] == "none"


def test_human_review_item_flagged():
    item = make_review_item(
        title="Governor QA",
        category="governor",
        recommended_action="human_review",
        requires_human_review=True,
    )
    summary = review_items_summary([item])
    assert summary["human_review_count"] == 1
    assert summary["authority_effect"] == "none"


def test_sort_critical_first():
    items = [
        make_review_item(title="info", severity="info"),
        make_review_item(title="critical", severity="critical"),
        make_review_item(title="warn", severity="warning"),
    ]
    ordered = sort_review_items(items)
    assert ordered[0].severity == "critical"
    assert "deploy" in BLOCKED_ACTIONS
    assert "auto_loosen" in BLOCKED_ACTIONS
