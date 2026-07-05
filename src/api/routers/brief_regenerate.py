"""
Brief Regenerator
==================
On-demand morning brief regeneration via subprocess to data/generate_brief.py.

POST /api/brief/regenerate     run generator, returns path + age
GET  /api/brief/status         report latest brief file + age in days
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request

from src.api.deps import optional_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

BRIEF_DIR = "data"
BRIEF_GLOB = os.path.join(BRIEF_DIR, "brief-*.json")
GENERATOR = os.path.join(BRIEF_DIR, "generate_brief.py")
DATE_RX = re.compile(r"brief-(\d{4}-\d{2}-\d{2})\.json$")


def _latest_brief() -> Optional[Dict[str, Any]]:
    """Find newest brief file by date in filename."""
    files = glob.glob(BRIEF_GLOB)
    parsed = []
    for f in files:
        m = DATE_RX.search(f)
        if m:
            try:
                parsed.append((date.fromisoformat(m.group(1)), f))
            except Exception:
                continue
    if not parsed:
        return None
    parsed.sort(reverse=True)
    latest_date, latest_path = parsed[0]
    today = date.today()
    age_days = (today - latest_date).days
    # Weekend grace: if today is Sat/Sun, a Friday brief counts as 0 (FRESH).
    # weekday(): Mon=0 ... Sun=6
    weekday = today.weekday()
    if weekday == 5 and latest_date == today.replace(day=today.day):
        # Saturday — pass through; handled by general case below
        pass
    if weekday == 5 and age_days == 1:
        effective_age = 0  # Sat with Friday brief
    elif weekday == 6 and age_days <= 2:
        effective_age = 0  # Sun with Fri/Sat brief
    elif weekday == 0 and age_days <= 3:
        effective_age = 0  # Mon with Fri brief still fresh until 06:00 ET regen
    else:
        effective_age = age_days
    try:
        size = os.path.getsize(latest_path)
        mtime = os.path.getmtime(latest_path)
    except Exception:
        size = 0
        mtime = 0
    # Generator health probes
    health_issues: list = []
    MIN_SIZE = 1024  # <1KB = likely failed/empty
    if size < MIN_SIZE:
        health_issues.append(f"file size {size}B < {MIN_SIZE}B (likely incomplete)")
    if mtime:
        file_mod_date = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
        # If file was modified more than 1 day BEFORE the date in its name,
        # the generator likely wrote to wrong filename or never ran fresh.
        gap_days = (latest_date - file_mod_date).days
        if gap_days > 1:
            health_issues.append(
                f"mtime ({file_mod_date}) precedes filename date "
                f"({latest_date}) by {gap_days}d"
            )
    return {
        "path": latest_path,
        "date": latest_date.isoformat(),
        "age_days": age_days,
        "effective_age_days": effective_age,
        "weekend_grace_applied": effective_age != age_days,
        "size_bytes": size,
        "mtime_iso": (
            datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            if mtime
            else None
        ),
        "health_issues": health_issues,
        "healthy": len(health_issues) == 0,
        "tier": (
            "FRESH"
            if effective_age == 0
            else "STALE" if effective_age <= 3 else "CRITICAL"
        ),
    }


@router.get("/api/brief/status", tags=["brief"])
async def brief_status(_=optional_api_key):
    """Report latest brief file + age."""
    info = _latest_brief()
    return {
        "ok": True,
        "latest": info,
        "generator_exists": os.path.exists(GENERATOR),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def _roll_forward_brief(source_path: str, source_date: str) -> Dict[str, Any]:
    """Stamp today's brief from the latest file when live fetch is unavailable."""
    today = date.today().isoformat()
    dest = os.path.join(BRIEF_DIR, f"brief-{today}.json")
    with open(source_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["date"] = today
    payload["generated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    meta = payload.setdefault("metadata", {})
    meta["rolled_forward_from"] = source_date
    meta["roll_forward_at"] = payload["generated_at"]
    meta["trust"] = "ROLLED_FORWARD"
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return {"path": dest, "date": today, "size_bytes": os.path.getsize(dest)}


@router.post("/api/brief/regenerate", tags=["brief"])
async def brief_regenerate(
    request: Request, dry_run: bool = False, _=optional_api_key
):
    """Run data/generate_brief.py in a subprocess. Returns generated path + age."""
    if not os.path.exists(GENERATOR):
        return {
            "ok": False,
            "error": f"Generator not found: {GENERATOR}",
        }
    before = _latest_brief()
    cmd = [sys.executable, GENERATOR]
    if dry_run:
        cmd.append("--dry-run")
    logger.info("brief.regenerate: running %s", " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("YFINANCE_CACHE_DIR", "/tmp/yfinance-cache")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
            env=env,
        )
        # 5 min ceiling — should finish in <60s
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=300)
        rc = proc.returncode
    except asyncio.TimeoutError:
        return {"ok": False, "error": "generator timed out (>5min)"}
    except Exception as exc:
        logger.exception("brief.regenerate failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    stdout = stdout_b.decode("utf-8", errors="replace")[-2000:]
    stderr = stderr_b.decode("utf-8", errors="replace")[-2000:]

    after = _latest_brief()
    rolled_forward = False
    if rc != 0 and before and before.get("path"):
        try:
            rolled = _roll_forward_brief(before["path"], before.get("date", ""))
            rolled_forward = True
            after = _latest_brief()
            logger.warning(
                "brief.regenerate: subprocess failed (rc=%s); rolled forward to %s",
                rc,
                rolled.get("path"),
            )
        except Exception as exc:
            logger.exception("brief roll-forward failed: %s", exc)

    # Invalidate cached brief so next read picks up new file
    try:
        from src.services.brief_data_service import BriefDataService

        BriefDataService.invalidate_cache()
    except Exception as exc:
        logger.debug("brief cache invalidate failed: %s", exc)

    ok = rc == 0 or rolled_forward
    return {
        "ok": ok,
        "return_code": rc,
        "dry_run": dry_run,
        "rolled_forward": rolled_forward,
        "before": before,
        "after": after,
        "changed": (before or {}).get("path") != (after or {}).get("path"),
        "stdout_tail": stdout,
        "stderr_tail": stderr if rc != 0 else stderr[-500:],
    }
