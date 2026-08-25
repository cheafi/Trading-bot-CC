"""Notify Router — alert log, Discord test, unified status."""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Query

from src.api.deps import sanitize_for_json

router = APIRouter(prefix="/api/v7/notify", tags=["notify"])


@router.get("/log")
async def alert_log(limit: int = Query(default=20, ge=1, le=50)) -> Dict[str, Any]:
    """Return the last *limit* alert events persisted by AlertService."""
    try:
        from src.services.alert_service import get_alert_log

        events = get_alert_log(limit=limit)
        return sanitize_for_json({"count": len(events), "events": events})
    except Exception as exc:
        return {"count": 0, "events": [], "error": str(exc)}


@router.post("/test")
async def send_test_alert(
    message: str = Query(default="AlertService test ping from TradingAI Bot"),
    severity: str = Query(default="info"),
) -> Dict[str, Any]:
    """Fire a test Discord alert and log it."""
    valid_severities = {"info", "warning", "critical", "ok"}
    if severity not in valid_severities:
        severity = "info"
    try:
        from src.notifications.discord_dispatch import (
            discord_config_status,
            push_notice,
        )

        pushed = push_notice(
            title="🧪 Test Alert · CC",
            message=message,
            severity=severity,
            event_type="test",
            log=True,
        )
        return {
            "ok": True,
            "pushed_to_discord": pushed,
            "severity": severity,
            "message": message,
            "config": discord_config_status(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/setup")
async def notify_setup() -> Dict[str, Any]:
    """Human-readable Discord setup checklist."""
    from src.notifications.discord_dispatch import discord_config_status

    st = discord_config_status()
    steps = [
        "1. Discord channel → Integrations → Webhooks → New Webhook → copy URL",
        "2. Add DISCORD_WEBHOOK_URL=<url> to .env (recommended — no bot permissions needed)",
        "OR: DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID (right-click channel → Copy ID)",
        "OR: DISCORD_BOT_TOKEN + DISCORD_CHANNEL_NAME=Trading CC (auto-resolve on first ping)",
        "3. Restart API process",
        "4. Ops tab → Test Discord ping (or GET /api/v7/notify/resolve-channel)",
    ]
    return {**st, "steps": steps}


@router.get("/resolve-channel")
async def resolve_discord_channel() -> Dict[str, Any]:
    """Try to resolve DISCORD_CHANNEL_NAME → channel ID (bot token required)."""
    from src.notifications.discord_dispatch import (
        discord_config_status,
        resolve_channel_id_async,
    )

    cid = await resolve_channel_id_async()
    st = discord_config_status()
    return {
        "ok": bool(cid),
        "channel_id": cid or None,
        "config": st,
        "hint": (
            "Channel resolved — test ping should work"
            if cid
            else "Check bot token, server invite, and channel name"
        ),
    }


@router.get("/status")
async def notify_status() -> Dict[str, Any]:
    """Discord + Telegram configuration and last alert timestamp."""
    try:
        from src.notifications.discord_dispatch import discord_config_status
        from src.notifications.telegram import telegram_config_status
        from src.services.alert_service import get_alert_log

        status = {
            **discord_config_status(),
            "telegram": telegram_config_status(),
        }
        log = get_alert_log(limit=1)
        status["last_alert_ts"] = log[-1]["ts"] if log else None
        status["last_alert_type"] = log[-1]["event_type"] if log else None
        if not status.get("discord_configured"):
            status["setup_hint"] = (
                "Set DISCORD_WEBHOOK_URL (recommended), or "
                "DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID, or "
                "DISCORD_BOT_TOKEN + DISCORD_CHANNEL_NAME"
            )
        if not status.get("telegram", {}).get("telegram_configured"):
            status["telegram_setup_hint"] = (
                "Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — see docs/TELEGRAM_SETUP.md"
            )
        return status
    except Exception as exc:
        webhook = os.getenv("DISCORD_WEBHOOK_URL", "") or os.getenv(
            "DISCORD_ALERT_WEBHOOK", ""
        )
        return {
            "discord_configured": bool(webhook),
            "error": str(exc),
        }


@router.post("/telegram/test")
async def send_telegram_test(
    message: str = Query(default=""),
) -> Dict[str, Any]:
    """Fire a professional Telegram welcome/test message (HTML)."""
    try:
        from src.notifications.telegram import (
            format_test_welcome_message,
            send_message,
            telegram_config_status,
        )

        note = message.strip() if message else ""
        text = format_test_welcome_message(custom_note=note)
        pushed = send_message(text)
        return {
            "ok": True,
            "pushed_to_telegram": pushed,
            "message": note or "welcome intro",
            "config": telegram_config_status(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/telegram/configure-profile")
async def configure_telegram_profile() -> Dict[str, Any]:
    """Set bot description, short description, and commands via Bot API."""
    try:
        from src.notifications.telegram import (
            configure_bot_profile_async,
            telegram_config_status,
        )

        st = telegram_config_status()
        if not st.get("bot_token_set"):
            return {
                "ok": False,
                "error": "TELEGRAM_BOT_TOKEN not set",
                "config": st,
            }
        result = await configure_bot_profile_async()
        return {"ok": result.get("ok"), **result, "config": st}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/telegram/opportunities-now")
async def telegram_opportunities_now(
    force: bool = Query(
        True,
        description="Push alerts for all current deploy/monitor rows (test mode)",
    ),
) -> Dict[str, Any]:
    """Force opportunity Telegram alerts from latest playbook ranked snapshot."""
    try:
        from src.services.opportunity_telegram_alerts import notify_live_playbook_scan
        from src.services.playbook_board_fallback import load_playbook_snapshot
        from src.notifications.telegram import telegram_config_status

        st = telegram_config_status()
        if not st.get("telegram_configured"):
            return {
                "ok": False,
                "error": "Telegram not configured",
                "config": st,
            }
        payload = load_playbook_snapshot("30::") or {}
        if not payload.get("opportunities"):
            return {
                "ok": False,
                "error": "No playbook ranked snapshot — run GET /api/v7/playbook/ranked?refresh=true first",
                "config": st,
            }
        result = notify_live_playbook_scan(
            payload, source="manual_opportunities_now", force=force
        )
        return {"ok": True, **result, "config": st}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/telegram/setup")
async def telegram_setup() -> Dict[str, Any]:
    """Human-readable Telegram setup checklist for CC Live Intelligence."""
    from src.notifications.telegram import (
        BRAND_LONG_DESCRIPTION,
        BRAND_SHORT_DESCRIPTION,
        telegram_config_status,
    )

    st = telegram_config_status()
    steps = [
        "1. @BotFather → /newbot → name: TradingAI Alerts CC → username: TradingAI_AlertsCC_bot",
        "2. /setdescription — paste long description from botfather_description below",
        "3. /setabouttext — paste short description from botfather_short_description",
        "4. Send /start to your bot → getUpdates → copy chat.id → TELEGRAM_CHAT_ID",
        "5. Add TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to .env (see config/telegram.env.example)",
        "6. Optional: CC_PUBLIC_BASE_URL for deep links in live alerts",
        "7. Restart API → run bot poller: python scripts/run_telegram_bot.py",
        "8. Send /start in Telegram — bot should reply with welcome",
        "9. POST /api/v7/notify/telegram/test or send /test in Telegram",
        "10. Optional: POST /api/v7/notify/telegram/configure-profile to set via API",
    ]
    botfather_commands = [
        {
            "command": "start",
            "description": "Welcome & setup · 歡迎與設定",
        },
        {
            "command": "status",
            "description": "CC deploy gate & channel status · 部署閘門與頻道狀態",
        },
        {
            "command": "test",
            "description": "Send test alert · 測試推播",
        },
        {
            "command": "help",
            "description": "Command list · 指令說明",
        },
    ]
    return {
        **st,
        "steps": steps,
        "bot_username": "@TradingAI_AlertsCC_bot",
        "botfather_short_description": BRAND_SHORT_DESCRIPTION,
        "botfather_description": BRAND_LONG_DESCRIPTION,
        "botfather_commands": botfather_commands,
    }
