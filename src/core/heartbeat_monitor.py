"""External dead-man's switch via healthchecks.io (HEARTBEAT_URL)."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def ping_heartbeat_url() -> bool:
    """Ping HEARTBEAT_URL if configured. Returns True on success or when unset."""
    url = os.environ.get("HEARTBEAT_URL", "").strip()
    if not url:
        return True
    if not url.startswith("https://"):
        logger.warning("HEARTBEAT_URL must use HTTPS — skipping ping")
        return False
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Heartbeat ping failed: %s", exc)
        return False
