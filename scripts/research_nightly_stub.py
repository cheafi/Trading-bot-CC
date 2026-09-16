#!/usr/bin/env python3
"""Nightly research stub — walk-forward / DSR jobs (wire real pipeline on VPS)."""

from __future__ import annotations

import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.logging_config import setup_logging

logger = logging.getLogger("tradingai.research")


def main() -> None:
    setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"), log_format="auto")
    interval = int(os.environ.get("RESEARCH_INTERVAL_SECONDS", "86400"))
    logger.info(
        "Research container stub active — schedule nightly walk-forward/DSR here "
        "(interval=%ss)",
        interval,
    )
    while True:
        logger.info("Research tick — no jobs configured (stub)")
        time.sleep(interval)


if __name__ == "__main__":
    main()
