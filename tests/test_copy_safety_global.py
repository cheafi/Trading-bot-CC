"""Global copy_safety module — sanitize_for_render contract."""

from __future__ import annotations

from src.services.copy_safety import (
    brief_expired,
    deploy_blocked,
    sanitize_card_row,
    sanitize_for_render,
    sanitize_rows,
)


def test_sanitize_for_render_blocked_strips_pilot_language():
    out = sanitize_for_render(
        "KO decent setup — taking a Pilot entry · Deploy gate open · half size max",
        {"blocked": True, "deploy_blocked": True},
    )
    assert "taking a Pilot" not in out
    assert "Deploy gate open" not in out
    assert "half size" not in out
    assert "monitor only" in out.lower()


def test_sanitize_for_render_brief_expired_never_fallback():
    out = sanitize_for_render(
        "Board uses brief fallback sample for monitor queue",
        {"brief_expired": True, "brief_age_days": 21},
    )
    assert "brief fallback" not in out.lower()
    assert "expired" in out.lower()


def test_sanitize_card_row_blocked_monitor_only():
    row = sanitize_card_row(
        {"ticker": "XLP", "primary_bucket": "Watch", "action_reason": "taking a Pilot entry"},
        context={"deploy_blocked": True},
    )
    assert "monitor only" in row["action_reason"].lower()
    assert "taking a Pilot" not in row["action_reason"]


def test_sanitize_rows_batch():
    rows = sanitize_rows(
        [{"ticker": "KO", "action_reason": "half size pilot"}],
        context={"blocked": True},
    )
    assert rows[0]["action_reason"]
    assert "half size" not in rows[0]["action_reason"]


def test_deploy_blocked_from_tier():
    assert deploy_blocked({"deploy_authority_tier": "blocked"})
    assert deploy_blocked({"deploy_authority": False})
    assert not deploy_blocked({"deploy_authority": True, "deploy_authority_tier": "allowed"})


def test_brief_expired_helper():
    assert brief_expired({"brief_age_days": 21})
    assert brief_expired({"brief_freshness": "expired"})
    assert not brief_expired({"brief_age_days": 1})
