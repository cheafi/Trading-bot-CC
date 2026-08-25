#!/usr/bin/env python3
"""Long-polling Telegram bot runner for CC Live Intelligence inbound commands.

Usage (from repo root, with .env present):
  python scripts/run_telegram_bot.py

Requires CC API at http://127.0.0.1:8000 (or API_BASE_URL / CC_PUBLIC_BASE_URL).
See docs/TELEGRAM_SETUP.md for full setup.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.notifications.telegram_bot_handlers import (  # noqa: E402
    KNOWN_COMMANDS,
    format_api_error,
    handle_telegram_command,
    normalize_command,
)

_TELEGRAM_API = "https://api.telegram.org"
_POLL_INTERVAL_SEC = 2
_OFFSET_FILE = ROOT / "data" / "artifacts" / "telegram_poll_offset.json"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _api_base() -> str:
    return (
        _env("API_BASE_URL") or _env("CC_PUBLIC_BASE_URL") or "http://127.0.0.1:8000"
    ).rstrip("/")


def _load_offset() -> int:
    try:
        if _OFFSET_FILE.is_file():
            data = json.loads(_OFFSET_FILE.read_text(encoding="utf-8"))
            return int(data.get("offset") or 0)
    except Exception:
        pass
    return 0


def _save_offset(offset: int) -> None:
    try:
        _OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _OFFSET_FILE.write_text(json.dumps({"offset": offset}), encoding="utf-8")
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
    with urllib.request.urlopen(req, timeout=35) as resp:
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


def _process_update(upd: dict) -> None:
    msg = upd.get("message") or {}
    text = str(msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id or not text.startswith("/"):
        return
    cmd = normalize_command(text)
    if cmd not in KNOWN_COMMANDS:
        return
    try:
        reply = handle_telegram_command(
            cmd,
            int(chat_id),
            cc_get=_cc_get,
            cc_post=_cc_post,
        )
    except urllib.error.URLError as exc:
        reply = format_api_error(exc.reason)
    _reply(int(chat_id), reply)


def main() -> None:
    _load_dotenv()
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in .env or environment", file=sys.stderr)
        sys.exit(1)
    print(f"Polling Telegram bot — CC API {_api_base()}")
    offset = _load_offset()
    while True:
        try:
            data = _tg_request("getUpdates", {"offset": offset, "timeout": 30})
            for upd in data.get("result") or []:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                _process_update(upd)
            _save_offset(offset)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print(f"poll error: {exc}", file=sys.stderr)
            time.sleep(_POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
