"""Dispatch research session summaries to IM channels."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


def format_research_summary(result: Dict[str, Any], *, task: str) -> str:
    lines = [f"CC Research · {task}", f"Authority: research_only"]
    if result.get("consensus"):
        lines.append(f"Consensus: {result.get('consensus')}")
    if result.get("teams") and isinstance(result["teams"], dict):
        lines.append(f"Teams: {result['teams'].get('consensus')}")
    rc = (result.get("composite_backtest") or {}).get("run_card") or result.get(
        "run_card"
    )
    if isinstance(rc, dict) and rc.get("aggregate_return_pct") is not None:
        lines.append(f"Composite return: {rc.get('aggregate_return_pct')}%")
    shadow = result.get("shadow")
    if isinstance(shadow, dict) and shadow.get("lessons"):
        lines.append("Shadow: " + "; ".join(shadow.get("lessons")[:2]))
    return "\n".join(lines)[:1800]


async def dispatch_research_to_im(
    result: Dict[str, Any],
    *,
    task: str,
    channel: str = "discord",
    severity: str = "info",
) -> Dict[str, Any]:
    ch = str(channel or "discord").lower()
    message = format_research_summary(result, task=task)
    if ch == "discord":
        try:
            from src.notifications.discord_dispatch import push_notice

            push_notice(
                title=f"Research · {task}",
                message=message,
                severity=severity,
                event_type="research_session",
            )
            return {"ok": True, "channel": "discord", "delivered": True}
        except Exception as exc:
            return {"ok": False, "channel": "discord", "error": type(exc).__name__}
    if ch == "slack":
        url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
        if not url.startswith("https://"):
            return {"ok": False, "channel": "slack", "error": "SLACK_WEBHOOK_URL missing"}
        body = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = 200 <= resp.status < 300
            return {"ok": ok, "channel": "slack", "delivered": ok}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "channel": "slack", "error": f"http_{exc.code}"}
    if ch == "webhook":
        url = os.getenv("RESEARCH_WEBHOOK_URL", "").strip()
        if not url.startswith("https://"):
            return {"ok": False, "channel": "webhook", "error": "RESEARCH_WEBHOOK_URL missing"}
        body = json.dumps({"text": message, "task": task, "authority": "research_only"}).encode(
            "utf-8"
        )
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = 200 <= resp.status < 300
            return {"ok": ok, "channel": "webhook", "delivered": ok}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "channel": "webhook", "error": f"http_{exc.code}"}
    if ch in ("matrix", "teams"):
        url = os.getenv("MATRIX_WEBHOOK_URL", "").strip() or os.getenv(
            "TEAMS_WEBHOOK_URL", ""
        ).strip()
        if not url.startswith("https://"):
            return {
                "ok": False,
                "channel": ch,
                "error": "MATRIX_WEBHOOK_URL or TEAMS_WEBHOOK_URL missing",
            }
        body = json.dumps(
            {
                "text": message,
                "task": task,
                "authority": "research_only",
                "source": "cc_research",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = 200 <= resp.status < 300
            return {"ok": ok, "channel": ch, "delivered": ok}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "channel": ch, "error": f"http_{exc.code}"}
    if ch == "ntfy":
        topic = os.getenv("NTFY_TOPIC", "").strip()
        base = os.getenv("NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/")
        if not topic:
            return {"ok": False, "channel": "ntfy", "error": "NTFY_TOPIC missing"}
        url = f"{base}/{urllib.parse.quote(topic, safe='')}"
        req = urllib.request.Request(
            url,
            data=message[:4000].encode("utf-8"),
            headers={"Title": f"CC Research · {task}"[:64], "Priority": "3"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = 200 <= resp.status < 300
            return {"ok": ok, "channel": "ntfy", "delivered": ok}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "channel": "ntfy", "error": f"http_{exc.code}"}
    if ch == "whatsapp":
        wa_url = os.getenv("WHATSAPP_WEBHOOK_URL", "").strip()
        if wa_url.startswith("https://"):
            body = json.dumps(
                {"text": message[:4000], "task": task, "authority": "research_only"}
            ).encode("utf-8")
            req = urllib.request.Request(
                wa_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    ok = 200 <= resp.status < 300
                return {"ok": ok, "channel": "whatsapp", "delivered": ok}
            except urllib.error.HTTPError as exc:
                return {"ok": False, "channel": "whatsapp", "error": f"http_{exc.code}"}
        token = os.getenv("WHATSAPP_CLOUD_TOKEN", "").strip()
        phone_id = os.getenv("WHATSAPP_PHONE_ID", "").strip()
        to = os.getenv("WHATSAPP_TO", "").strip()
        if token and phone_id and to:
            api = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": message[:4000]},
            }
            req = urllib.request.Request(
                api,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    ok = 200 <= resp.status < 300
                return {"ok": ok, "channel": "whatsapp", "delivered": ok}
            except urllib.error.HTTPError as exc:
                return {"ok": False, "channel": "whatsapp", "error": f"http_{exc.code}"}
        return {
            "ok": False,
            "channel": "whatsapp",
            "error": "WHATSAPP_WEBHOOK_URL or WHATSAPP_CLOUD_TOKEN+PHONE_ID+TO missing",
        }
    if ch == "telegram":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            return {
                "ok": False,
                "channel": "telegram",
                "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing",
            }
        api = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": message[:4000]}
        ).encode("utf-8")
        req = urllib.request.Request(api, data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = 200 <= resp.status < 300
            return {"ok": ok, "channel": "telegram", "delivered": ok}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "channel": "telegram", "error": f"http_{exc.code}"}
    return {
        "ok": False,
        "channel": ch,
        "delivered": False,
        "note": (
            "Supported: discord, slack, telegram, whatsapp, webhook, ntfy, matrix, teams."
        ),
    }
