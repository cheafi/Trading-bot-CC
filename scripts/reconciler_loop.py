#!/usr/bin/env python3
"""Reconciler service — compare broker positions vs DB every 5 minutes.

Halts further reconciliation cycles on mismatch (operator must intervene).
Stub: uses in-process BrokerReconciliationEngine until broker adapters are wired.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.logging_config import setup_logging
from src.engines.broker_reconciliation import (
    BrokerReconciliationEngine,
    ReconciliationStatus,
)

logger = logging.getLogger("tradingai.reconciler")

INTERVAL_SECONDS = int(os.environ.get("RECONCILE_INTERVAL_SECONDS", "300"))


async def run_loop() -> None:
    engine = BrokerReconciliationEngine()
    halted = False

    while True:
        if halted:
            logger.error("Reconciler halted on mismatch — awaiting operator reset")
            await asyncio.sleep(INTERVAL_SECONDS)
            continue

        status = engine.reconcile(broker_positions={})
        logger.info("Reconciliation status: %s", status.value)

        if status == ReconciliationStatus.MISMATCH:
            halted = True
            logger.critical(
                "Broker vs DB mismatch — trading should halt until reconciled"
            )

        await asyncio.sleep(INTERVAL_SECONDS)


def main() -> None:
    setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"), log_format="auto")
    logger.info("Reconciler starting (interval=%ss)", INTERVAL_SECONDS)
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        logger.info("Reconciler stopped")


if __name__ == "__main__":
    main()
