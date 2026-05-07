"""
TradingAI Bot - Scheduler Service
Manages scheduled jobs for data ingestion, signal generation, and reporting.
"""

import asyncio
from datetime import datetime, time
from typing import Any, Dict, Optional
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from src.core.config import get_settings
from src.ingestors import MarketDataIngestor, NewsIngestor, SocialIngestor
from src.engines import FeatureEngine, SignalEngine
from src.engines.gpt_validator import GPTSignalValidator, GPTSummarizer
from src.notifications.multi_channel import MultiChannelNotifier

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TradingScheduler:
    """
    Scheduler for all trading bot jobs.

    Schedule:
    - Pre-market (6:30 AM ET): Generate daily report, check news
    - Market open (9:30 AM ET): Start signal generation
    - During market (9:30 AM - 4:00 PM ET): Continuous data ingestion
    - After hours (4:30 PM ET): EOD processing
    - Overnight: Historical data backfill
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone("US/Eastern"))

        # Initialize components
        self.market_ingestor = MarketDataIngestor()
        self.news_ingestor = NewsIngestor()
        self.social_ingestor = SocialIngestor()
        self.feature_engine = FeatureEngine()
        self.signal_engine = SignalEngine()
        self.gpt_validator = GPTSignalValidator()
        self.gpt_summarizer = GPTSummarizer()
        self.notifier = MultiChannelNotifier()

        # Job tracking
        self._job_history: list = []

    def setup_jobs(self):
        """Configure all scheduled jobs."""

        # ===== Pre-Market Jobs (6:00 AM - 9:30 AM ET) =====

        # 6:00 AM - Overnight news ingestion
        self.scheduler.add_job(
            self._job_overnight_news,
            CronTrigger(hour=6, minute=0),
            id="overnight_news",
            name="Overnight News Ingestion",
            replace_existing=True,
        )

        # 6:15 AM - Social sentiment check
        self.scheduler.add_job(
            self._job_social_sentiment,
            CronTrigger(hour=6, minute=15),
            id="premarket_social",
            name="Pre-market Social Sentiment",
            replace_existing=True,
        )

        # 6:30 AM - Generate daily report
        self.scheduler.add_job(
            self._job_daily_report,
            CronTrigger(hour=6, minute=30),
            id="daily_report",
            name="Daily Market Report",
            replace_existing=True,
        )

        # 9:25 AM - Pre-market signal generation
        self.scheduler.add_job(
            self._job_premarket_signals,
            CronTrigger(hour=9, minute=25),
            id="premarket_signals",
            name="Pre-market Signal Generation",
            replace_existing=True,
        )

        # ===== Market Hours Jobs (9:30 AM - 4:00 PM ET) =====

        # Every 5 minutes during market hours - Price data ingestion
        self.scheduler.add_job(
            self._job_market_data,
            CronTrigger(hour="9-15", minute="*/5", day_of_week="mon-fri"),
            id="intraday_data",
            name="Intraday Price Data",
            replace_existing=True,
        )

        # Every 15 minutes - News update
        self.scheduler.add_job(
            self._job_news_update,
            CronTrigger(hour="9-16", minute="*/15", day_of_week="mon-fri"),
            id="intraday_news",
            name="Intraday News Update",
            replace_existing=True,
        )

        # Every 30 minutes - Signal refresh
        self.scheduler.add_job(
            self._job_signal_refresh,
            CronTrigger(hour="10-15", minute="0,30", day_of_week="mon-fri"),
            id="intraday_signals",
            name="Intraday Signal Refresh",
            replace_existing=True,
        )

        # ===== After Hours Jobs =====

        # 4:30 PM - EOD processing
        self.scheduler.add_job(
            self._job_eod_processing,
            CronTrigger(hour=16, minute=30),
            id="eod_processing",
            name="End of Day Processing",
            replace_existing=True,
        )

        # 8:00 PM - Historical data backfill
        self.scheduler.add_job(
            self._job_historical_backfill,
            CronTrigger(hour=20, minute=0),
            id="historical_backfill",
            name="Historical Data Backfill",
            replace_existing=True,
        )

        # ===== Maintenance Jobs =====

        # Every hour - Health check
        self.scheduler.add_job(
            self._job_health_check,
            IntervalTrigger(hours=1),
            id="health_check",
            name="System Health Check",
            replace_existing=True,
        )

        # Every Sunday 2 AM - Database maintenance
        self.scheduler.add_job(
            self._job_db_maintenance,
            CronTrigger(day_of_week="sun", hour=2),
            id="db_maintenance",
            name="Database Maintenance",
            replace_existing=True,
        )

        logger.info("All jobs scheduled successfully")

    def start(self):
        """Start the scheduler."""
        self.setup_jobs()
        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler gracefully."""
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    # ===== Job Implementations =====

    async def _job_overnight_news(self):
        """Fetch overnight news articles."""
        logger.info("Starting overnight news ingestion")
        try:
            result = await self.news_ingestor.run(hours_back=12)
            self._log_job_result("overnight_news", result)
        except Exception as e:
            logger.error(f"Overnight news job failed: {e}")

    async def _job_social_sentiment(self):
        """Fetch and analyze social media sentiment."""
        logger.info("Starting social sentiment analysis")
        try:
            # Get trending tickers from recent data
            result = await self.social_ingestor.run(hours_back=24)
            self._log_job_result("social_sentiment", result)
        except Exception as e:
            logger.error(f"Social sentiment job failed: {e}")

    async def _job_daily_report(self):
        """Generate daily market report."""
        logger.info("Generating daily market report")
        try:
            # ── Generate brief JSON (data/brief-YYYY-MM-DD.json) ────────────
            try:
                import asyncio
                from data.generate_brief import build_brief, save_brief  # noqa: PLC0415

                brief = await asyncio.to_thread(build_brief)
                if brief:
                    save_brief(brief)
                    logger.info("Brief JSON written for %s", brief.get("date"))
                    from src.services.brief_data_service import (
                        BriefDataService,
                    )  # noqa: PLC0415

                    BriefDataService.invalidate_cache()
            except Exception as exc:
                logger.warning("Brief generation failed (non-fatal): %s", exc)
            # ── Build summary report ─────────────────────────────────────────

            report = {
                "overview": {
                    "spy_change": "+0.5%",
                    "qqq_change": "+0.8%",
                    "iwm_change": "-0.2%",
                    "vix": 18.5,
                    "regime": "Normal Volatility",
                },
                "signals": [],
                "news_summary": "Market overview pending implementation",
            }

            # Send report via notification channels
            if self.notifier.is_configured:
                await self.notifier.send_daily_report(report)
                logger.info("Daily report sent via notification channels")

        except Exception as e:
            logger.error(f"Daily report job failed: {e}")
            # Alert on critical failures
            if self.notifier.is_configured:
                await self.notifier.send_alert(
                    "Daily Report Failed",
                    f"Error generating daily report: {str(e)}",
                    level="ERROR",
                )

    async def _job_premarket_signals(self):
        """Generate pre-market trading signals via BriefDataService pipeline."""
        logger.info("Generating pre-market signals")
        try:
            from src.services.brief_data_service import (
                BriefDataService,
                all_brief_tickers,
            )  # noqa: PLC0415
            from src.services.regime_service import RegimeService  # noqa: PLC0415

            # 1. Warm regime cache
            regime = await asyncio.to_thread(RegimeService.get)
            if not regime.get("should_trade", True):
                logger.warning(
                    "Regime blocks trading (should_trade=False) — skipping signal generation. "
                    "regime=%s",
                    regime.get("trend", "unknown"),
                )
                return

            # 2. Load today's brief signals
            brief = BriefDataService.load()
            if not brief:
                logger.warning(
                    "No brief data available — cannot generate pre-market signals"
                )
                return

            tickers = all_brief_tickers()[:30]  # cap at 30 for pre-market run
            signals = []
            for ticker in tickers:
                from src.services.brief_data_service import find_signal  # noqa: PLC0415

                sig = find_signal(ticker)
                if sig:
                    signals.append(sig)

            logger.info(
                "Pre-market signals: %d found from %d tickers",
                len(signals),
                len(tickers),
            )

            # 3. Send via notification channels
            if signals and self.notifier.is_configured:
                await self.notifier.send_signals_batch(signals)
                logger.info("Sent %d signals via notification channels", len(signals))

        except Exception as e:
            logger.error("Pre-market signals job failed: %s", e)
            if self.notifier.is_configured:
                await self.notifier.send_alert(
                    "Signal Generation Failed",
                    f"Error generating pre-market signals: {e}",
                    level="ERROR",
                )

    async def _job_market_data(self):
        """Fetch intraday market data."""
        logger.info("Fetching intraday market data")
        try:
            # Only run on weekdays during market hours
            if not self._is_market_hours():
                return

            result = await self.market_ingestor.run(interval="5min")
            self._log_job_result("market_data", result)
        except Exception as e:
            logger.error(f"Market data job failed: {e}")

    async def _job_news_update(self):
        """Fetch news updates during market hours."""
        logger.info("Fetching news updates")
        try:
            result = await self.news_ingestor.run(hours_back=1)
            self._log_job_result("news_update", result)
        except Exception as e:
            logger.error(f"News update job failed: {e}")

    async def _job_signal_refresh(self):
        """Refresh trading signals and regime cache during market hours."""
        logger.info("Refreshing trading signals")
        try:
            if not self._is_market_hours():
                return

            # Re-warm regime cache (RegimeService.get() is idempotent; cache TTL = 4h)
            from src.services.regime_service import RegimeService  # noqa: PLC0415

            regime = await asyncio.to_thread(RegimeService.get)
            logger.info(
                "Signal refresh — regime: %s should_trade=%s vix=%.1f",
                regime.get("trend", "?"),
                regime.get("should_trade"),
                regime.get("vix", 0.0),
            )

            # Invalidate brief data cache so next request picks up latest file
            from src.services.brief_data_service import (
                BriefDataService,
            )  # noqa: PLC0415

            BriefDataService.invalidate_cache()

        except Exception as e:
            logger.error("Signal refresh job failed: %s", e)

    async def _job_eod_processing(self):
        """End of day processing: build brief, review portfolio, send Discord summary."""
        logger.info("Starting EOD processing")
        try:
            # 1. Build and save today's brief JSON
            try:
                from data.generate_brief import build_brief, save_brief  # noqa: PLC0415

                brief = await asyncio.to_thread(build_brief)
                if brief:
                    save_brief(brief)
                    from src.services.brief_data_service import (
                        BriefDataService,
                    )  # noqa: PLC0415

                    BriefDataService.invalidate_cache()
                    logger.info("EOD brief saved: %s", brief.get("date"))
            except Exception as exc:
                logger.warning("EOD brief generation failed (non-fatal): %s", exc)

            # 2. Ingest EOD market data
            result = await self.market_ingestor.run(interval="day")
            self._log_job_result("eod_data", result)

            # 3. Portfolio review
            try:
                from src.algo.portfolio_brain import PortfolioBrain  # noqa: PLC0415

                brain = PortfolioBrain()
                review = await asyncio.to_thread(brain.review_all)
                logger.info(
                    "EOD portfolio review: %s positions reviewed", len(review or [])
                )
            except Exception as exc:
                logger.warning("EOD portfolio review failed (non-fatal): %s", exc)

            # 4. Send EOD summary notification
            if self.notifier.is_configured:
                from src.services.regime_service import RegimeService  # noqa: PLC0415

                regime = await asyncio.to_thread(RegimeService.get)
                summary = {
                    "type": "eod_summary",
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "regime": regime.get("trend", "unknown"),
                    "should_trade": regime.get("should_trade", True),
                    "vix": regime.get("vix", 0.0),
                }
                await self.notifier.send_daily_report(summary)

            # 5. Self-learning cycle — reset, analyse, apply, tune fund weights
            try:
                from src.engines.self_learning import (  # noqa: PLC0415
                    SelfLearningEngine,
                    pull_closed_trades_from_learning_loop,
                    tune_fund_weights,
                )
                from src.core.config import get_trading_config  # noqa: PLC0415

                engine = SelfLearningEngine()
                engine.reset_cycle()
                trades = pull_closed_trades_from_learning_loop()
                if trades:
                    cfg = get_trading_config()
                    current_rules = {
                        "stop_loss_pct": getattr(cfg, "stop_loss_pct", 0.03),
                        "ensemble_min_score": getattr(cfg, "ensemble_min_score", 0.35),
                        "signal_cooldown_hours": float(
                            getattr(cfg, "signal_cooldown_hours", 4)
                        ),
                        "max_position_pct": getattr(cfg, "max_position_pct", 0.05),
                        "trailing_stop_pct": getattr(cfg, "trailing_stop_pct", 0.02),
                    }
                    recs = engine.analyze_and_recommend(trades, current_rules)
                    applied = engine.apply_adjustments(recs)
                    logger.info(
                        "EOD self-learning: %d trades analysed, %d adjustments applied",
                        len(trades),
                        len(applied),
                    )
                else:
                    logger.info("EOD self-learning: no closed trades yet — skipped")
            except Exception as _sle:
                logger.warning("EOD self-learning cycle failed (non-fatal): %s", _sle)

            # 6. Per-regime parameter auto-tune (Sprint 98)
            try:
                from src.engines.self_learning import (  # noqa: PLC0415
                    pull_closed_trades_from_learning_loop as _pull,
                    tune_regime_params,
                )

                _trades = _pull()
                if _trades:
                    regime_changes = tune_regime_params(_trades)
                    if regime_changes:
                        logger.info(
                            "EOD regime-tune: params updated for %s",
                            list(regime_changes.keys()),
                        )
                    else:
                        logger.info(
                            "EOD regime-tune: no changes needed (insufficient data or win-rates in range)"
                        )
            except Exception as _rte:
                logger.warning("EOD regime-tune failed (non-fatal): %s", _rte)

            # 6b. Auto-Experiment Scheduler (Sprint 112) — propose A/B challengers
            # for any regime whose win-rate is outside [0.45, 0.60]
            try:
                from src.engines.self_learning import (  # noqa: PLC0415
                    auto_schedule_experiments,
                    pull_closed_trades_from_learning_loop as _pull_auto,
                )

                _auto_trades = _pull_auto()
                if _auto_trades:
                    _sched_result = auto_schedule_experiments(_auto_trades)
                    logger.info(
                        "EOD auto-schedule: proposed=%d skipped=%d",
                        _sched_result.get("total_proposed", 0),
                        len(_sched_result.get("skipped", [])),
                    )
            except Exception as _ase:
                logger.warning("EOD auto-schedule failed (non-fatal): %s", _ase)

            # 7. Closed-Trade Auto-Feedback Pipeline (Sprint 113) — unified 4-channel
            # feedback: Brier + A/B shadow + Thompson RL + Feature IC per trade.
            # Replaces the fragmented per-channel loop from Sprint 103.
            try:
                from src.engines.self_learning import (  # noqa: PLC0415
                    process_closed_trades_batch,
                    pull_closed_trades_from_learning_loop as _pull2,
                )

                _eod_trades = _pull2()
                if _eod_trades:
                    _fb_result = process_closed_trades_batch(_eod_trades)
                    logger.info(
                        "EOD feedback pipeline: %d trades processed — "
                        "brier=%d thompson=%d ic=%d ab_updates=%d",
                        _fb_result["total"],
                        _fb_result["channels"]["brier"],
                        _fb_result["channels"]["thompson"],
                        _fb_result["channels"]["feature_ic"],
                        _fb_result["channels"]["ab"],
                    )
                else:
                    logger.info("EOD feedback pipeline: no closed trades — skipped")
            except Exception as _fb:
                logger.warning("EOD feedback pipeline failed (non-fatal): %s", _fb)

            # 8. AlertService: check IC decay + Thompson arm degrade, push Discord (Sprint 106)
            try:
                from src.services.alert_service import (  # noqa: PLC0415
                    check_and_push_ic_decay,
                    check_and_push_thompson_degrade,
                )

                check_and_push_ic_decay()
                check_and_push_thompson_degrade()
                logger.info("EOD AlertService: decay/degrade checks complete")
            except Exception as _ale:
                logger.warning("EOD AlertService check failed (non-fatal): %s", _ale)

        except Exception as e:
            logger.error("EOD processing failed: %s", e)

    async def _job_historical_backfill(self):
        """Backfill any missing historical data."""
        logger.info("Starting historical backfill")
        try:
            import asyncio
            from datetime import datetime, timedelta
            import yfinance as yf

            # Universe: top 50 liquid symbols the engine tracks
            try:
                from src.scanners.us_universe import US_UNIVERSE

                symbols = list(US_UNIVERSE)[:50]
            except Exception:
                symbols = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=7)  # check last 7 calendar days

            gaps_found = 0
            for sym in symbols:
                try:
                    df = await asyncio.to_thread(
                        yf.download,
                        sym,
                        start=start_date.isoformat(),
                        end=end_date.isoformat(),
                        progress=False,
                        auto_adjust=True,
                    )
                    if df is None or df.empty:
                        logger.warning("[Backfill] No data for %s — possible gap", sym)
                        gaps_found += 1
                except Exception as e:
                    logger.warning("[Backfill] Fetch error for %s: %s", sym, e)

            logger.info(
                "[Backfill] Complete — checked %d symbols, %d potential gaps detected",
                len(symbols),
                gaps_found,
            )
        except Exception as e:
            logger.error("Historical backfill failed: %s", e)

    async def _job_health_check(self):
        """Run system health check."""
        logger.info("Running health check")
        try:
            health = {
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler_running": self.scheduler.running,
                "jobs_count": len(self.scheduler.get_jobs()),
                "status": "healthy",
            }

            # Check database connection
            from src.core.database import check_database_health

            try:
                db_health = await check_database_health()
                health["database"] = db_health
            except Exception as e:
                health["database"] = {"status": "error", "error": str(e)}
                health["status"] = "degraded"

            logger.info(f"Health check: {health}")

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    async def _job_db_maintenance(self):
        """Database maintenance tasks."""
        logger.info("Starting database maintenance")
        try:
            from src.core.database import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as session:
                # Refresh materialized views
                await session.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_returns")
                )

                # Clean up old data (keep 2 years)
                await session.execute(text("""
                    DELETE FROM ohlcv 
                    WHERE timestamp < NOW() - INTERVAL '2 years'
                    AND interval = '1min'
                """))

                # Vacuum analyze
                await session.execute(text("VACUUM ANALYZE"))

                await session.commit()

            logger.info("Database maintenance completed")

        except Exception as e:
            logger.error(f"Database maintenance failed: {e}")

    # ===== Helper Methods =====

    def _is_market_hours(self) -> bool:
        """Check if currently within US market hours."""
        et = pytz.timezone("US/Eastern")
        now = datetime.now(et)

        # Check weekday
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check time (9:30 AM - 4:00 PM ET)
        market_open = time(9, 30)
        market_close = time(16, 0)

        current_time = now.time()
        return market_open <= current_time <= market_close

    def _log_job_result(self, job_name: str, result: Dict[str, Any]):
        """Log job result and maintain history."""
        self._job_history.append(
            {
                "job": job_name,
                "timestamp": datetime.utcnow().isoformat(),
                "result": result,
            }
        )

        # Keep only last 1000 results
        if len(self._job_history) > 1000:
            self._job_history = self._job_history[-1000:]

        status = result.get("status", "unknown")
        records = result.get("records_stored", 0)
        logger.info(f"Job {job_name} completed: status={status}, records={records}")


async def main():
    """Main entry point for scheduler service."""
    scheduler = TradingScheduler()

    try:
        scheduler.start()

        # Keep running
        while True:
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())
