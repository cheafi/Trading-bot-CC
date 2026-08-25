"""Telegram Bot API dispatch for immediate operator alerts."""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger("telegram_dispatch")

_TELEGRAM_API = "https://api.telegram.org"

# Institutional branding — bilingual header/footer for all operator-facing messages
BRAND_HEADER = "CC Live Intelligence · 即時情報"
BRAND_FOOTER = (
    "Advisory only · 僅供參考 · Human approval required · CC Operator Decision OS"
)
BRAND_SHORT_DESCRIPTION = (
    "Live AI intelligence & deploy signals for CC Operator Decision OS"
)
BRAND_LONG_DESCRIPTION = (
    "CC Live Intelligence delivers real-time playbook alerts for the CC Operator "
    "Decision OS.\n\n"
    "• DEPLOY — execution-ready setups that pass the full TRADE bar (human approval "
    "still required before orders)\n"
    "• WATCH / MONITOR — high-tier research signals; rank ≠ deploy permission\n\n"
    "Advisory only · 僅供參考 · Not financial advice."
)
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


def format_cc_dashboard_link(path: str = "") -> str:
    """CC dashboard deep link (optionally with path suffix)."""
    base = _cc_base_url()
    if not base:
        return ""
    suffix = str(path or "").strip()
    if suffix and not suffix.startswith("/"):
        suffix = f"/{suffix}"
    return f"{base}{suffix}" if suffix else base


def format_cc_link(ticker: str) -> str:
    """Optional CC deep link when a public base URL is configured."""
    sym = validate_ticker(ticker)
    if not sym:
        return ""
    base = format_cc_dashboard_link()
    if not base:
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


def format_brand_header() -> str:
    """Top strip for all CC Telegram alerts."""
    return f"<b>{escape_html(BRAND_HEADER)}</b>"


def format_brand_footer(*, extra: str = "") -> str:
    """Standard disclaimer footer; optional extra line (kind-specific guidance)."""
    lines = [escape_html(BRAND_FOOTER)]
    if extra:
        lines.append(escape_html(extra))
    return "\n".join(lines)


def format_alert_timestamp(when: Optional[datetime] = None) -> str:
    """UTC timestamp line for alert audit trail."""
    ts = when or datetime.now(timezone.utc)
    label = ts.strftime("%Y-%m-%d %H:%M UTC")
    return f"🕐 {escape_html(label)}"


def format_test_welcome_message(*, custom_note: str = "") -> str:
    """Professional intro sent from /telegram/test or first-time verification."""
    lines = [
        format_brand_header(),
        "",
        "<b>Connection verified · 連線成功</b>",
        "",
        "You will receive live alerts when the playbook scan detects:",
        "",
        "🟢 <b>DEPLOY</b> — TRADE-bar qualified, execution-ready setups",
        "   (human approval required before any order · 下單前需人工確認)",
        "",
        "👀 <b>WATCH / MONITOR</b> — high-tier research signals",
        "   (monitor only — not deploy permission · 僅監控，非部署許可)",
        "",
        "Alerts include score, tier, R:R, blockers, and a CC deep link when configured.",
    ]
    if custom_note:
        lines.extend(["", f"Note: {escape_html(custom_note)}"])
    lines.extend(["", format_brand_footer()])
    return "\n".join(lines)


async def _bot_api_post(method: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Call Telegram Bot API method (HTTPS). Never logs token."""
    token = _bot_token()
    if not token:
        return False, "bot token not set"
    url = f"{_TELEGRAM_API}/bot{token}/{method}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                body = await resp.text()
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        return True, ""
                    return False, str(data.get("description", body))[:200]
                return False, body[:200]
    except Exception as exc:
        logger.warning("Telegram %s error: %s", method, exc)
        return False, str(exc)


async def set_bot_description_async(
    description: str = BRAND_LONG_DESCRIPTION,
    *,
    language_code: str = "",
) -> bool:
    """Set bot long description (BotFather equivalent: /setdescription)."""
    payload: Dict[str, Any] = {"description": str(description)[:512]}
    if language_code:
        payload["language_code"] = language_code
    ok, err = await _bot_api_post("setMyDescription", payload)
    if not ok:
        logger.warning("Telegram setMyDescription failed: %s", err)
    return ok


async def set_bot_short_description_async(
    short_description: str = BRAND_SHORT_DESCRIPTION,
    *,
    language_code: str = "",
) -> bool:
    """Set bot short description shown in chat list."""
    payload: Dict[str, Any] = {"short_description": str(short_description)[:120]}
    if language_code:
        payload["language_code"] = language_code
    ok, err = await _bot_api_post("setMyShortDescription", payload)
    if not ok:
        logger.warning("Telegram setMyShortDescription failed: %s", err)
    return ok


async def set_bot_commands_async(
    commands: Optional[List[Dict[str, str]]] = None,
) -> bool:
    """Register slash commands for operator discovery."""
    cmds = commands or [
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
    ok, err = await _bot_api_post("setMyCommands", {"commands": cmds})
    if not ok:
        logger.warning("Telegram setMyCommands failed: %s", err)
    return ok


async def configure_bot_profile_async() -> Dict[str, Any]:
    """Apply institutional bot profile (description + commands) when token is set."""
    if not _bot_token():
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not set"}
    desc = await set_bot_description_async()
    short = await set_bot_short_description_async()
    cmds = await set_bot_commands_async()
    return {
        "ok": desc and short and cmds,
        "description_set": desc,
        "short_description_set": short,
        "commands_set": cmds,
    }


def configure_bot_profile() -> Dict[str, Any]:
    """Sync wrapper for configure_bot_profile_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("use configure_bot_profile_async in async context")
        return loop.run_until_complete(configure_bot_profile_async())
    except RuntimeError:
        return asyncio.run(configure_bot_profile_async())
