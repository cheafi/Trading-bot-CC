"""
TradingAI Bot — Ingestor Service Entry-Point

Runs the market-data, news, and social ingestors in an asyncio loop
with configurable intervals.  Designed to be launched by Docker:

    CMD ["python", "-m", "src.ingestors.main"]
"""
import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class IngestorService:
    """
    Orchestrates periodic data-ingestion tasks:
      • MarketDataIngestor  — OHLCV prices  (every 60 s)
      • NewsIngestor        — financial news (every 300 s)
      • SocialIngestor      — social feeds   (every 600 s)
    """

    DEFAULT_INTERVALS = {
        "market_data": 60,
        "news": 300,
        "social": 600,
    }

    def __init__(self, intervals: Optional[dict] = None):
        self.intervals = {**self.DEFAULT_INTERVALS, **(intervals or {})}
        self._running = False
        self._tasks: list = []
        self._market: Optional[object] = None
        self._news: Optional[object] = None
        self._social: Optional[object] = None

    # ── bootstrap ──────────────────────────────────────────────────
    def _init_ingestors(self):
        """Lazy-import and instantiate ingestors (keeps top-level lean)."""
        try:
            from src.ingestors.market_data import MarketDataIngestor
            self._market = MarketDataIngestor()
            logger.info("MarketDataIngestor ready")
        except Exception as exc:
            logger.warning("MarketDataIngestor unavailable: %s", exc)

        try:
            from src.ingestors.news import NewsIngestor
            self._news = NewsIngestor()
            logger.info("NewsIngestor ready")
        except Exception as exc:
            logger.warning("NewsIngestor unavailable: %s", exc)

        try:
            from src.ingestors.social import SocialIngestor
            self._social = SocialIngestor()
            logger.info("SocialIngestor ready")
        except Exception as exc:
            logger.warning("SocialIngestor unavailable: %s", exc)

    # ── periodic runners ───────────────────────────────────────────
    async def _run_loop(self, name: str, coro_factory, interval: int):
        """Generic run-sleep loop for an ingestor."""
        while self._running:
            try:
                logger.info("[%s] starting cycle", name)
                await coro_factory()
                logger.info("[%s] cycle complete", name)
            except Exception as exc:
                logger.error("[%s] cycle error: %s", name, exc)
            await asyncio.sleep(interval)

    async def _market_cycle(self):
        if self._market:
            await self._market.fetch()

    async def _news_cycle(self):
        if self._news:
            await self._news.fetch()

    async def _social_cycle(self):
        if self._social:
            await self._social.fetch()

    # ── lifecycle ──────────────────────────────────────────────────
    async def start(self):
        """Initialise ingestors and launch background loops."""
        logger.info("IngestorService starting …")
        self._init_ingestors()
        self._running = True

        loop_specs = [
            ("market_data", self._market_cycle, self.intervals["market_data"]),
            ("news", self._news_cycle, self.intervals["news"]),
            ("social", self._social_cycle, self.intervals["social"]),
        ]
        for name, factory, interval in loop_specs:
            task = asyncio.create_task(self._run_loop(name, factory, interval))
            self._tasks.append(task)

        logger.info(
            "IngestorService running — %d loops (intervals=%s)",
            len(self._tasks),
            self.intervals,
        )

    async def stop(self):
        """Graceful shutdown."""
        logger.info("IngestorService stopping …")
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("IngestorService stopped")

    def health(self) -> dict:
        return {
            "running": self._running,
            "loops": len(self._tasks),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── CLI entry-point ────────────────────────────────────────────────
async def main():
    service = IngestorService()
    loop = asyncio.get_event_loop()

    def _shutdown():
        logger.info("Shutdown signal received")
        asyncio.ensure_future(service.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows

    await service.start()

    # Keep alive until stopped
    try:
        while service._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
