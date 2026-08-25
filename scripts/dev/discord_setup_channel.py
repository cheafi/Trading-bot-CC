#!/usr/bin/env python3
"""Resolve Discord channel ID by name and optionally print webhook setup steps.

Usage:
  python scripts/dev/discord_setup_channel.py
  python scripts/dev/discord_setup_channel.py --name "Trading CC"

Reads DISCORD_BOT_TOKEN and DISCORD_CHANNEL_NAME from .env (or environment).
Does not print tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip().strip('"').strip("'")


def _api_get(path: str, token: str) -> object:
    req = urllib.request.Request(
        f"https://discord.com/api/v10{path}",
        headers={"Authorization": f"Bot {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve Discord channel ID for CC alerts")
    parser.add_argument("--name", default="", help="Channel name (default: DISCORD_CHANNEL_NAME)")
    args = parser.parse_args()
    _load_dotenv()

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not set in .env")
        return 1

    target = (args.name or os.getenv("DISCORD_CHANNEL_NAME", "Trading CC")).strip().lower()
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip() or os.getenv(
        "DISCORD_ALERT_WEBHOOK", ""
    ).strip()

    if webhook:
        print("OK: DISCORD_WEBHOOK_URL is already set — alerts use webhook mode.")
        return 0

    existing = os.getenv("DISCORD_CHANNEL_ID", "").strip()
    if existing:
        print(f"OK: DISCORD_CHANNEL_ID already set ({existing})")
        print("Restart API and use Ops → Test Discord ping")
        return 0

    try:
        guilds = _api_get("/users/@me/guilds", token)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: Discord API {exc.code} — check bot token and intents")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    if not isinstance(guilds, list):
        print("ERROR: unexpected guilds response")
        return 1

    matches: list[tuple[str, str, str]] = []
    for guild in guilds:
        gid = str(guild.get("id") or "")
        gname = str(guild.get("name") or "")
        if not gid:
            continue
        try:
            channels = _api_get(f"/guilds/{gid}/channels", token)
        except Exception:
            continue
        if not isinstance(channels, list):
            continue
        for ch in channels:
            if str(ch.get("type")) not in ("0", "5"):  # text / announcement
                continue
            cname = str(ch.get("name") or "")
            if cname.lower() == target or target in cname.lower():
                matches.append((gid, str(ch.get("id") or ""), f"{gname}/{cname}"))

    if not matches:
        print(f"No channel matching '{target}' found.")
        print("Invite the bot to your server, or pass --name 'your-channel'")
        return 1

    if len(matches) > 1:
        print("Multiple matches — pick one:")
        for i, (_, cid, label) in enumerate(matches, 1):
            print(f"  {i}. {label} → {cid}")
        print("\nAdd to .env:")
        print(f"DISCORD_CHANNEL_ID={matches[0][1]}")
        return 0

    _, channel_id, label = matches[0]
    print(f"Found channel: {label}")
    print("\nAdd this line to your .env:")
    print(f"DISCORD_CHANNEL_ID={channel_id}")
    print("\nThen restart the API and click Ops → Test Discord ping")
    print("\nAlternative: create a webhook in channel settings and set DISCORD_WEBHOOK_URL instead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
