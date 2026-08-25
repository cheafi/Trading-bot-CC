#!/usr/bin/env python3
"""Lightweight Telegram bot polling for /status and /test (no webhook infra).

Usage:
  export TELEGRAM_BOT_TOKEN=...
  export TELEGRAM_CHAT_ID=...   # optional — restricts replies to this chat
  python scripts/dev/telegram_bot_poll.py

Requires CC API at http://127.0.0.1:8000 (or API_BASE_URL).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_TELEGRAM_API = "https://api.telegram.org"
_POLL_INTERVAL_SEC = 2
_OFFSET_FILE = os.path.join("data", "artifacts", "telegram_poll_offset.json")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _api_base() -> str:
    return (
        _env("API_BASE_URL")
        or _env("CC_PUBLIC_BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _load_offset() -> int:
    try:
        if os.path.isfile(_OFFSET_FILE):
            data = json.loads(open(_OFFSET_FILE, encoding="utf-8").read())
            return int(data.get("offset") or 0)
    except Exception:
        pass
    return 0


def _save_offset(offset: int) -> None:
    try:
        os.makedirs(os.path.dirname(_OFFSET_FILE), exist_ok=True)
        with open(_OFFSET_FILE, "w", encoding="utf-8") as fh:
            json.dump({"offset": offset}, fh)
    except Exception:
        pass


def _tg_request(method: str, payload: dict) -> dict:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set")
    url = f"{_TELEGRAM_API}/bot{token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cc_get(path: str) -> dict:
    url = f"{_api_base()}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cc_post(path: str) -> dict:
    url = f"{_api_base()}{path}"
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _reply(chat_id: int, text: str) -> None:
    _tg_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def _handle_command(chat_id: int, command: str) -> None:
    allowed = _env("TELEGRAM_CHAT_ID")
    if allowed and str(chat_id) != allowed:
        _reply(chat_id, "Unauthorized chat · 未授權的聊天室")
        return

    if command == "/status":
        try:
            st = _cc_get("/api/v7/notify/status")
            tg = st.get("telegram") or {}
            lines = [
                "<b>CC Live Intelligence · Status</b>",
                f"Telegram configured: {tg.get('telegram_configured')}",
                f"Deploy alerts: {_env('TELEGRAM_NOTIFY_DEPLOY', 'true')}",
                f"Monitor alerts: {_env('TELEGRAM_NOTIFY_MONITOR', 'true')}",
                f"System alerts: {_env('TELEGRAM_NOTIFY_SYSTEM', 'true')}",
                f"CC base URL set: {tg.get('cc_base_url_set')}",
            ]
            if st.get("last_alert_ts"):
                lines.append(f"Last alert: {st.get('last_alert_type')} @ {st.get('last_alert_ts')}")
            _reply(chat_id, "\n".join(lines))
        except urllib.error.URLError as exc:
            _reply(chat_id, f"CC API unreachable: {exc.reason}")
        return

    if command == "/test":
        try:
            result = _cc_post("/api/v7/notify/telegram/test")
            if result.get("pushed_to_telegram"):
                _reply(chat_id, "Test alert dispatched · 測試推播已送出")
            else:
                _reply(chat_id, f"Test failed: {result.get('error', 'unknown')}")
        except urllib.error.URLError as exc:
            _reply(chat_id, f"CC API unreachable: {exc.reason}")
        return

    _reply(
        chat_id,
        "Commands: /status · /test\nAdvisory only · 僅供參考",
    )


def main() -> None:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN", file=sys.stderr)
        sys.exit(1)
    print(f"Polling Telegram bot — CC API {_api_base()}")
    offset = _load_offset()
    while True:
        try:
            data = _tg_request("getUpdates", {"offset": offset, "timeout": 30})
            for upd in data.get("result") or []:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                msg = upd.get("message") or {}
                text = str(msg.get("text") or "").strip()
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                if not chat_id or not text.startswith("/"):
                    continue
                cmd = text.split()[0].split("@")[0].lower()
                if cmd in ("/status", "/test", "/start", "/help"):
                    _handle_command(int(chat_id), "/test" if cmd == "/start" else cmd)
            _save_offset(offset)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print(f"poll error: {exc}", file=sys.stderr)
            time.sleep(_POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
