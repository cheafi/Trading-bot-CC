"""Unified Discord dispatch for all real-life operator notices."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("discord_dispatch")

_CHANNEL_CACHE_PATH = Path("data") / "artifacts" / "discord_channel_id.json"

_SEVERITY_COLOR = {
    "critical": 0xFF4444,
    "warning": 0xFF8C00,
    "info": 0x5865F2,
    "ok": 0x00FF88,
}

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
    "ok": "🟢",
}

# event_type -> default severity floor for Discord (research can be muted)
_RESEARCH_EVENT_TYPES = frozenset(
    {
        "validation",
        "strategy_draft",
        "committee",
        "shadow_analysis",
        "research_pipeline",
    }
)

_DEDUPE: Dict[str, float] = {}
_DEDUPE_COOLDOWN_SEC = int(os.getenv("DISCORD_ALERT_COOLDOWN_SEC", "300"))


def _webhook_url() -> str:
    return (
        os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        or os.getenv("DISCORD_ALERT_WEBHOOK", "").strip()
    )


def _bot_token() -> str:
    return os.getenv("DISCORD_BOT_TOKEN", "").strip()


def _channel_id() -> str:
    return os.getenv("DISCORD_CHANNEL_ID", "").strip() or os.getenv(
        "DISCORD_ALERT_CHANNEL_ID", ""
    ).strip()


def _cached_channel_id() -> str:
    if not _CHANNEL_CACHE_PATH.exists():
        return ""
    try:
        data = json.loads(_CHANNEL_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return str(data.get("channel_id") or "").strip()
    except Exception:
        pass
    return ""


def _save_channel_cache(channel_id: str, *, label: str = "") -> None:
    _CHANNEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CHANNEL_CACHE_PATH.write_text(
        json.dumps(
            {
                "channel_id": channel_id,
                "label": label,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


async def resolve_channel_id_async() -> str:
    """Resolve channel ID from env, cache, or Discord API (bot token + channel name)."""
    cid = _channel_id() or _cached_channel_id()
    if cid:
        return cid
    token = _bot_token()
    if not token:
        return ""
    target = os.getenv("DISCORD_CHANNEL_NAME", "Trading CC").strip().lower()
    headers = {"Authorization": f"Bot {token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://discord.com/api/v10/users/@me/guilds", headers=headers
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Discord guilds %s: %s", resp.status, body[:120])
                    return ""
                guilds = await resp.json()
            for guild in guilds if isinstance(guilds, list) else []:
                gid = str(guild.get("id") or "")
                gname = str(guild.get("name") or "")
                if not gid:
                    continue
                async with session.get(
                    f"https://discord.com/api/v10/guilds/{gid}/channels",
                    headers=headers,
                ) as resp:
                    if resp.status != 200:
                        continue
                    channels = await resp.json()
                if not isinstance(channels, list):
                    continue
                for ch in channels:
                    if str(ch.get("type")) not in ("0", "5"):
                        continue
                    cname = str(ch.get("name") or "")
                    if cname.lower() == target or target in cname.lower():
                        cid = str(ch.get("id") or "")
                        if cid:
                            _save_channel_cache(cid, label=f"{gname}/{cname}")
                            logger.info("Discord channel resolved: %s/%s → %s", gname, cname, cid)
                            return cid
    except Exception as exc:
        logger.warning("Discord channel resolve failed: %s", exc)
    return ""


def discord_is_configured() -> bool:
    """True when webhook or bot token (+ channel id or resolvable channel name)."""
    if os.getenv("DISCORD_NOTIFY_ENABLED", "true").lower() in ("0", "false", "no"):
        return False
    if _webhook_url():
        return True
    if not _bot_token():
        return False
    return bool(_channel_id() or _cached_channel_id() or os.getenv("DISCORD_CHANNEL_NAME", "").strip())


def discord_config_status() -> Dict[str, Any]:
    webhook = bool(_webhook_url())
    token = bool(_bot_token())
    channel = bool(_channel_id() or _cached_channel_id())
    channel_name = os.getenv("DISCORD_CHANNEL_NAME", "").strip()
    return {
        "discord_configured": discord_is_configured(),
        "webhook_set": webhook,
        "bot_token_set": token,
        "channel_id_set": channel,
        "channel_name": channel_name,
        "channel_cached": bool(_cached_channel_id()),
        "mode": (
            "webhook"
            if webhook
            else "bot_channel"
            if token and (channel or channel_name)
            else "unconfigured"
        ),
        "notify_enabled": os.getenv("DISCORD_NOTIFY_ENABLED", "true").lower()
        not in ("0", "false", "no"),
        "notify_research": os.getenv("DISCORD_NOTIFY_RESEARCH", "false").lower()
        in ("1", "true", "yes"),
    }


def _normalize_severity(severity: str) -> str:
    s = str(severity or "info").lower()
    if s in ("critical", "crit", "high"):
        return "critical"
    if s in ("warning", "warn", "medium"):
        return "warning"
    if s in ("ok", "success"):
        return "ok"
    return "info"


def _should_send(event_type: str, severity: str) -> bool:
    if not discord_is_configured():
        return False
    if event_type in _RESEARCH_EVENT_TYPES:
        if os.getenv("DISCORD_NOTIFY_RESEARCH", "false").lower() not in (
            "1",
            "true",
            "yes",
        ):
            return severity in ("critical", "warning")
    return True


def _dedupe_key(event_type: str, title: str) -> str:
    raw = f"{event_type}|{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _dedupe_blocked(key: str) -> bool:
    if os.getenv("DISCORD_ALERT_DEDUPE", "true").lower() in ("0", "false", "no"):
        return False
    last = _DEDUPE.get(key)
    if last and (time.time() - last) < _DEDUPE_COOLDOWN_SEC:
        return True
    _DEDUPE[key] = time.time()
    return False


def _build_embed(
    *,
    title: str,
    message: str,
    severity: str,
    event_type: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sev = _normalize_severity(severity)
    emoji = _SEVERITY_EMOJI.get(sev, "ℹ️")
    embed: Dict[str, Any] = {
        "title": f"{emoji} {title}"[:256],
        "description": str(message or "")[:4096],
        "color": _SEVERITY_COLOR.get(sev, 0x5865F2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"CC · {event_type} · monitor only — confirm in Playbook"},
    }
    if meta:
        fields: List[Dict[str, Any]] = []
        for k, v in list(meta.items())[:6]:
            fields.append(
                {
                    "name": str(k)[:256],
                    "value": str(v)[:1024],
                    "inline": True,
                }
            )
        if fields:
            embed["fields"] = fields
    return embed


async def push_notice_async(
    *,
    title: str,
    message: str,
    severity: str = "info",
    event_type: str = "operator",
    meta: Optional[Dict[str, Any]] = None,
) -> bool:
    """Send embed to Discord via webhook or bot REST API."""
    if not _should_send(event_type, _normalize_severity(severity)):
        return False
    key = _dedupe_key(event_type, title)
    if _dedupe_blocked(key):
        logger.debug("discord dedupe skip: %s", title)
        return False

    embed = _build_embed(
        title=title, message=message, severity=severity, event_type=event_type, meta=meta
    )
    payload = {"embeds": [embed]}

    webhook = _webhook_url()
    if webhook:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook, json=payload) as resp:
                    if resp.status in (200, 204):
                        return True
                    body = await resp.text()
                    logger.warning("Discord webhook %s: %s", resp.status, body[:200])
        except Exception as exc:
            logger.warning("Discord webhook error: %s", exc)
        return False

    token = _bot_token()
    channel = _channel_id() or _cached_channel_id()
    if token and not channel:
        channel = await resolve_channel_id_async()
    if token and channel:
        url = f"https://discord.com/api/v10/channels/{channel}/messages"
        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in (200, 201):
                        return True
                    body = await resp.text()
                    logger.warning("Discord bot channel %s: %s", resp.status, body[:200])
        except Exception as exc:
            logger.warning("Discord bot channel error: %s", exc)
    return False


def push_notice(
    *,
    title: str,
    message: str,
    severity: str = "info",
    event_type: str = "operator",
    meta: Optional[Dict[str, Any]] = None,
    log: bool = True,
) -> bool:
    """Sync entry — logs to alert_log then pushes to Discord."""
    if log:
        try:
            from src.services.alert_service import _append_log, _make_event

            _append_log(
                _make_event(
                    event_type=event_type,
                    title=title,
                    message=message,
                    severity=_normalize_severity(severity),
                    meta=meta,
                )
            )
        except Exception as exc:
            logger.debug("alert log append failed: %s", exc)

    if not discord_is_configured():
        return False

    async def _run():
        return await push_notice_async(
            title=title,
            message=message,
            severity=severity,
            event_type=event_type,
            meta=meta,
        )

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_run())
            return True
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())
    except Exception as exc:
        logger.warning("push_notice failed: %s", exc)
        return False
