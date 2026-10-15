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


async def _run_alpha_zoo_job() -> None:
    from src.services.alpha_zoo_cache import refresh_alpha_zoo_cache
    from src.services.market_data import MarketDataService

    mds = MarketDataService()
    ticker = os.environ.get("ALPHA_ZOO_TICKER", "SPY")
    limit = int(os.environ.get("ALPHA_ZOO_COMPUTE_LIMIT", "478"))
    logger.info("Alpha zoo refresh starting ticker=%s limit=%s", ticker, limit)
    result = await refresh_alpha_zoo_cache(mds, ticker=ticker, compute_limit=limit)
    logger.info(
        "Alpha zoo refresh done ok=%s computed=%s",
        result.get("ok"),
        result.get("computed_count"),
    )


def main() -> None:
    setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"), log_format="auto")
    interval = int(os.environ.get("RESEARCH_INTERVAL_SECONDS", "86400"))
    logger.info(
        "Research nightly loop — alpha zoo cache + walk-forward hooks (interval=%ss)",
        interval,
    )
    import asyncio

    while True:
        try:
            asyncio.run(_run_alpha_zoo_job())
        except Exception as exc:
            logger.warning("Research tick failed: %s", exc)
        time.sleep(interval)


if __name__ == "__main__":
    main()
