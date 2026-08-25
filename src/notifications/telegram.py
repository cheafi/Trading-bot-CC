"""Telegram Bot API dispatch for immediate operator alerts."""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger("telegram_dispatch")

_TELEGRAM_API = "https://api.telegram.org"
_DEDUPE: Dict[str, float] = {}
_DEDUPE_COOLDOWN_SEC = int(os.getenv("TELEGRAM_ALERT_COOLDOWN_SEC", "300"))
_CHAT_ID_RE = re.compile(r"^-?\d+$|^@[\w\d_]{5,32}$")
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")


def _bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _notify_enabled() -> bool:
    return os.getenv("TELEGRAM_NOTIFY_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def telegram_is_configured() -> bool:
    """True when bot token and chat id are set and notifications are enabled."""
    if not _notify_enabled():
        return False
    token = _bot_token()
    chat = _chat_id()
    if not token or not chat:
        return False
    return bool(_CHAT_ID_RE.match(chat))


def telegram_config_status() -> Dict[str, Any]:
    token = bool(_bot_token())
    chat = bool(_chat_id())
    chat_valid = bool(_chat_id()) and bool(_CHAT_ID_RE.match(_chat_id()))
    return {
        "telegram_configured": telegram_is_configured(),
        "bot_token_set": token,
        "chat_id_set": chat,
        "chat_id_valid": chat_valid,
        "notify_enabled": _notify_enabled(),
        "dedupe_cooldown_sec": _DEDUPE_COOLDOWN_SEC,
        "cc_base_url_set": bool(_cc_base_url()),
    }


def _cc_base_url() -> str:
    for key in ("CC_PUBLIC_BASE_URL", "CC_BASE_URL", "API_BASE_URL"):
        val = os.getenv(key, "").strip().rstrip("/")
        if val:
            return val
    return ""


def validate_ticker(ticker: str) -> Optional[str]:
    """Sanitize ticker symbol for alert payloads."""
    sym = str(ticker or "").strip().upper()
    if not sym or not _TICKER_RE.match(sym):
        return None
    return sym


def _dedupe_key(kind: str, ticker: str, tier: str) -> str:
    raw = f"{kind}|{ticker}|{tier}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def dedupe_blocked_for_alert(kind: str, ticker: str, tier: str) -> bool:
    """Return True when an identical alert was sent inside the cooldown window."""
    key = _dedupe_key(kind, ticker, tier)
    if os.getenv("TELEGRAM_ALERT_DEDUPE", "true").lower() in ("0", "false", "no"):
        return False
    last = _DEDUPE.get(key)
    if last and (time.time() - last) < _DEDUPE_COOLDOWN_SEC:
        return True
    _DEDUPE[key] = time.time()
    return False


def format_cc_link(ticker: str) -> str:
    """Optional CC deep link when a public base URL is configured."""
    base = _cc_base_url()
    sym = validate_ticker(ticker)
    if not base or not sym:
        return ""
    return f"{base}/?ticker={sym}"


async def send_message_async(
    text: str,
    *,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
) -> bool:
    """Send a plain-text/HTML message via Telegram Bot API (HTTPS only)."""
    if not telegram_is_configured():
        return False
    token = _bot_token()
    chat_id = _chat_id()
    url = f"{_TELEGRAM_API}/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": str(text or "")[:4096],
        "disable_web_page_preview": disable_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return bool(data.get("ok"))
                body = await resp.text()
                logger.warning("Telegram sendMessage %s: %s", resp.status, body[:200])
    except Exception as exc:
        logger.warning("Telegram send error: %s", exc)
    return False


def send_message(text: str, *, parse_mode: str = "HTML") -> bool:
    """Sync entry — schedules async send when loop is running."""

    async def _run() -> bool:
        return await send_message_async(text, parse_mode=parse_mode)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_run())
            return True
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())
    except Exception as exc:
        logger.warning("telegram send_message failed: %s", exc)
        return False


def escape_html(text: Any) -> str:
    return html.escape(str(text or ""), quote=False)
