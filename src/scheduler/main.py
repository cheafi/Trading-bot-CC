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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('US/Eastern'))
        
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
            id='overnight_news',
            name='Overnight News Ingestion',
            replace_existing=True
        )
        
        # 6:15 AM - Social sentiment check
        self.scheduler.add_job(
            self._job_social_sentiment,
            CronTrigger(hour=6, minute=15),
            id='premarket_social',
            name='Pre-market Social Sentiment',
            replace_existing=True
        )
        
        # 6:30 AM - Generate daily report
        self.scheduler.add_job(
            self._job_daily_report,
            CronTrigger(hour=6, minute=30),
            id='daily_report',
            name='Daily Market Report',
            replace_existing=True
        )
        
        # 9:25 AM - Pre-market signal generation
        self.scheduler.add_job(
            self._job_premarket_signals,
            CronTrigger(hour=9, minute=25),
            id='premarket_signals',
            name='Pre-market Signal Generation',
            replace_existing=True
        )
        
        # ===== Market Hours Jobs (9:30 AM - 4:00 PM ET) =====
        
        # Every 5 minutes during market hours - Price data ingestion
        self.scheduler.add_job(
            self._job_market_data,
            CronTrigger(
                hour='9-15', minute='*/5',
                day_of_week='mon-fri'
            ),
            id='intraday_data',
            name='Intraday Price Data',
            replace_existing=True
        )
        
        # Every 15 minutes - News update
        self.scheduler.add_job(
            self._job_news_update,
            CronTrigger(
                hour='9-16', minute='*/15',
                day_of_week='mon-fri'
            ),
            id='intraday_news',
            name='Intraday News Update',
            replace_existing=True
        )
        
        # Every 30 minutes - Signal refresh
        self.scheduler.add_job(
            self._job_signal_refresh,
            CronTrigger(
                hour='10-15', minute='0,30',
                day_of_week='mon-fri'
            ),
            id='intraday_signals',
            name='Intraday Signal Refresh',
            replace_existing=True
        )
        
        # ===== After Hours Jobs =====
        
        # 4:30 PM - EOD processing
        self.scheduler.add_job(
            self._job_eod_processing,
            CronTrigger(hour=16, minute=30),
            id='eod_processing',
            name='End of Day Processing',
            replace_existing=True
        )
        
        # 8:00 PM - Historical data backfill
        self.scheduler.add_job(
            self._job_historical_backfill,
            CronTrigger(hour=20, minute=0),
            id='historical_backfill',
            name='Historical Data Backfill',
            replace_existing=True
        )
        
        # ===== Maintenance Jobs =====
        
        # Every hour - Health check
        self.scheduler.add_job(
            self._job_health_check,
            IntervalTrigger(hours=1),
            id='health_check',
            name='System Health Check',
            replace_existing=True
        )
        
        # Every Sunday 2 AM - Database maintenance
        self.scheduler.add_job(
            self._job_db_maintenance,
            CronTrigger(day_of_week='sun', hour=2),
            id='db_maintenance',
            name='Database Maintenance',
            replace_existing=True
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
            self._log_job_result('overnight_news', result)
        except Exception as e:
            logger.error(f"Overnight news job failed: {e}")
    
    async def _job_social_sentiment(self):
        """Fetch and analyze social media sentiment."""
        logger.info("Starting social sentiment analysis")
        try:
            # Get trending tickers from recent data
            result = await self.social_ingestor.run(hours_back=24)
            self._log_job_result('social_sentiment', result)
        except Exception as e:
            logger.error(f"Social sentiment job failed: {e}")
    
    async def _job_daily_report(self):
        """Generate daily market report."""
        logger.info("Generating daily market report")
        try:
            # Gather market data and news
            # TODO: Implement full report generation with actual data
            
            report = {
                'overview': {
                    'spy_change': '+0.5%',
                    'qqq_change': '+0.8%',
                    'iwm_change': '-0.2%',
                    'vix': 18.5,
                    'regime': 'Normal Volatility'
                },
                'signals': [],
                'news_summary': 'Market overview pending implementation'
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
                    level="ERROR"
                )
    
    async def _job_premarket_signals(self):
        """Generate pre-market trading signals."""
        logger.info("Generating pre-market signals")
        try:
            # Run signal generation
            # TODO: Implement with actual data pipeline
            signals = []
            
            # Send signals if any
            if signals and self.notifier.is_configured:
                await self.notifier.send_signals_batch(signals)
                logger.info(f"Sent {len(signals)} signals via notification channels")
            
        except Exception as e:
            logger.error(f"Pre-market signals job failed: {e}")
            if self.notifier.is_configured:
                await self.notifier.send_alert(
                    "Signal Generation Failed",
                    f"Error generating pre-market signals: {str(e)}",
                    level="ERROR"
                )
    
    async def _job_market_data(self):
        """Fetch intraday market data."""
        logger.info("Fetching intraday market data")
        try:
            # Only run on weekdays during market hours
            if not self._is_market_hours():
                return
            
            result = await self.market_ingestor.run(interval='5min')
            self._log_job_result('market_data', result)
        except Exception as e:
            logger.error(f"Market data job failed: {e}")
    
    async def _job_news_update(self):
        """Fetch news updates during market hours."""
        logger.info("Fetching news updates")
        try:
            result = await self.news_ingestor.run(hours_back=1)
            self._log_job_result('news_update', result)
        except Exception as e:
            logger.error(f"News update job failed: {e}")
    
    async def _job_signal_refresh(self):
        """Refresh trading signals during market hours."""
        logger.info("Refreshing trading signals")
        try:
            # TODO: Implement signal refresh
            pass
        except Exception as e:
            logger.error(f"Signal refresh job failed: {e}")
    
    async def _job_eod_processing(self):
        """End of day processing."""
        logger.info("Starting EOD processing")
        try:
            # Fetch daily EOD data
            result = await self.market_ingestor.run(interval='day')
            self._log_job_result('eod_data', result)
            
            # Calculate EOD features
            # TODO: Implement feature calculation
            
        except Exception as e:
            logger.error(f"EOD processing failed: {e}")
    
    async def _job_historical_backfill(self):
        """Backfill any missing historical data."""
        logger.info("Starting historical backfill")
        try:
            # TODO: Check for gaps and backfill
            pass
        except Exception as e:
            logger.error(f"Historical backfill failed: {e}")
    
    async def _job_health_check(self):
        """Run system health check."""
        logger.info("Running health check")
        try:
            health = {
                'timestamp': datetime.utcnow().isoformat(),
                'scheduler_running': self.scheduler.running,
                'jobs_count': len(self.scheduler.get_jobs()),
                'status': 'healthy'
            }
            
            # Check database connection
            from src.core.database import check_database_health
            try:
                db_health = await check_database_health()
                health['database'] = db_health
            except Exception as e:
                health['database'] = {'status': 'error', 'error': str(e)}
                health['status'] = 'degraded'
            
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
                await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_returns"))
                
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
        et = pytz.timezone('US/Eastern')
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
        self._job_history.append({
            'job': job_name,
            'timestamp': datetime.utcnow().isoformat(),
            'result': result
        })
        
        # Keep only last 1000 results
        if len(self._job_history) > 1000:
            self._job_history = self._job_history[-1000:]
        
        status = result.get('status', 'unknown')
        records = result.get('records_stored', 0)
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
