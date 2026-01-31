"""
TradingAI Bot - FastAPI Application
REST API for accessing signals, reports, and system status.
"""
from datetime import datetime, date, timedelta
from typing import List, Optional
import logging

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from src.core.config import get_settings
from src.core.models import Signal

settings = get_settings()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TradingAI Bot API",
    description="AI-powered US equities market intelligence system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Authentication =====

async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header."""
    if not settings.api_secret_key:
        return True
    
    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return True


# ===== Response Models =====

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    database: Optional[str] = None


class SignalListResponse(BaseModel):
    signals: List[Signal]
    total: int
    generated_at: str


class MarketReportResponse(BaseModel):
    report_date: str
    overview: dict
    sectors: dict
    signals: List[Signal]
    news_summary: str
    generated_at: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ===== Health Endpoints =====

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/health/detailed", response_model=HealthResponse)
async def detailed_health_check(
    _: bool = Depends(verify_api_key)
):
    """Detailed health check with component status."""
    from src.core.database import check_database_health
    
    try:
        db_health = await check_database_health()
        db_status = "connected" if db_health else "disconnected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database": db_status
    }


# ===== Signal Endpoints =====

@app.get("/signals", response_model=SignalListResponse)
async def get_signals(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    direction: Optional[str] = Query(None, description="LONG or SHORT"),
    min_confidence: Optional[float] = Query(0.5, description="Minimum confidence threshold"),
    limit: int = Query(50, le=200),
    _: bool = Depends(verify_api_key)
):
    """
    Get trading signals.
    
    Returns latest signals filtered by date, ticker, direction, and confidence.
    """
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    try:
        # Build query
        conditions = ["confidence >= :min_confidence"]
        params = {"min_confidence": min_confidence}
        
        if date:
            conditions.append("DATE(generated_at) = :date")
            params["date"] = date
        else:
            # Default to today's signals
            conditions.append("DATE(generated_at) = CURRENT_DATE")
        
        if ticker:
            conditions.append("ticker = :ticker")
            params["ticker"] = ticker.upper()
        
        if direction:
            conditions.append("direction = :direction")
            params["direction"] = direction.upper()
        
        where_clause = " AND ".join(conditions)
        
        sql = f"""
            SELECT * FROM signals
            WHERE {where_clause}
            ORDER BY confidence DESC
            LIMIT :limit
        """
        params["limit"] = limit
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(sql), params)
            rows = result.fetchall()
        
        signals = []
        for row in rows:
            signals.append(Signal(
                id=row.id,
                ticker=row.ticker,
                direction=row.direction,
                strategy=row.strategy,
                entry_price=row.entry_price,
                take_profit=row.take_profit,
                stop_loss=row.stop_loss,
                confidence=row.confidence,
                generated_at=row.generated_at
            ))
        
        return SignalListResponse(
            signals=signals,
            total=len(signals),
            generated_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/{signal_id}")
async def get_signal_by_id(
    signal_id: str,
    _: bool = Depends(verify_api_key)
):
    """Get a specific signal by ID."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT * FROM signals WHERE id = :id"),
            {"id": signal_id}
        )
        row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return {
        "id": row.id,
        "ticker": row.ticker,
        "direction": row.direction,
        "strategy": row.strategy,
        "entry_price": float(row.entry_price),
        "take_profit": float(row.take_profit),
        "stop_loss": float(row.stop_loss),
        "confidence": float(row.confidence),
        "regime": row.regime,
        "features": row.features,
        "generated_at": row.generated_at.isoformat()
    }


@app.get("/signals/ticker/{ticker}")
async def get_signals_for_ticker(
    ticker: str,
    days: int = Query(7, le=30),
    _: bool = Depends(verify_api_key)
):
    """Get historical signals for a specific ticker."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT * FROM signals 
                WHERE ticker = :ticker
                AND generated_at > NOW() - INTERVAL ':days days'
                ORDER BY generated_at DESC
            """),
            {"ticker": ticker.upper(), "days": days}
        )
        rows = result.fetchall()
    
    signals = []
    for row in rows:
        signals.append({
            "id": row.id,
            "direction": row.direction,
            "strategy": row.strategy,
            "entry_price": float(row.entry_price),
            "confidence": float(row.confidence),
            "generated_at": row.generated_at.isoformat()
        })
    
    return {
        "ticker": ticker.upper(),
        "signals": signals,
        "count": len(signals)
    }


# ===== Market Report Endpoints =====

@app.get("/reports/daily")
async def get_daily_report(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    _: bool = Depends(verify_api_key)
):
    """Get daily market report."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    report_date = date or datetime.utcnow().strftime("%Y-%m-%d")
    
    try:
        async with AsyncSessionLocal() as session:
            # Get report from database
            result = await session.execute(
                text("SELECT * FROM daily_reports WHERE report_date = :date"),
                {"date": report_date}
            )
            row = result.fetchone()
        
        if row:
            return {
                "report_date": report_date,
                "overview": row.overview,
                "sectors": row.sectors,
                "notable_movers": row.notable_movers,
                "news_summary": row.news_summary,
                "signals_summary": row.signals_summary,
                "generated_at": row.generated_at.isoformat()
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"No report found for {report_date}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reports/market-overview")
async def get_market_overview(
    _: bool = Depends(verify_api_key)
):
    """Get current market overview."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    try:
        async with AsyncSessionLocal() as session:
            # Get latest index data
            indices_sql = """
                SELECT ticker, close, 
                       (close - LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp)) / 
                       LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp) * 100 as change_pct
                FROM ohlcv
                WHERE ticker IN ('SPY', 'QQQ', 'IWM', 'DIA')
                AND interval = 'day'
                ORDER BY timestamp DESC
                LIMIT 4
            """
            result = await session.execute(text(indices_sql))
            indices = {row.ticker: {"price": float(row.close), "change_pct": float(row.change_pct or 0)} 
                      for row in result.fetchall()}
            
            # Get sector performance
            sectors_sql = """
                SELECT ticker, 
                       (close - LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp)) / 
                       LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp) * 100 as change_pct
                FROM ohlcv
                WHERE ticker IN ('XLF', 'XLE', 'XLK', 'XLV', 'XLY', 'XLP', 'XLI', 'XLU', 'XLB', 'XLRE', 'XLC')
                AND interval = 'day'
                ORDER BY timestamp DESC
                LIMIT 11
            """
            result = await session.execute(text(sectors_sql))
            sectors = {row.ticker: float(row.change_pct or 0) for row in result.fetchall()}
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "indices": indices,
            "sectors": sectors,
            "market_status": "open" if _is_market_open() else "closed"
        }
        
    except Exception as e:
        logger.error(f"Error fetching market overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Data Endpoints =====

@app.get("/data/ohlcv/{ticker}")
async def get_ohlcv_data(
    ticker: str,
    interval: str = Query("day", description="day, hour, 5min, 1min"),
    days: int = Query(30, le=365),
    _: bool = Depends(verify_api_key)
):
    """Get OHLCV data for a ticker."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT timestamp, open, high, low, close, volume
                FROM ohlcv
                WHERE ticker = :ticker
                AND interval = :interval
                AND timestamp > NOW() - INTERVAL ':days days'
                ORDER BY timestamp ASC
            """),
            {"ticker": ticker.upper(), "interval": interval, "days": days}
        )
        rows = result.fetchall()
    
    data = []
    for row in rows:
        data.append({
            "timestamp": row.timestamp.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": int(row.volume)
        })
    
    return {
        "ticker": ticker.upper(),
        "interval": interval,
        "data": data,
        "count": len(data)
    }


@app.get("/data/features/{ticker}")
async def get_features(
    ticker: str,
    date: Optional[str] = Query(None),
    _: bool = Depends(verify_api_key)
):
    """Get calculated features for a ticker."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    conditions = ["ticker = :ticker"]
    params = {"ticker": ticker.upper()}
    
    if date:
        conditions.append("DATE(calculated_at) = :date")
        params["date"] = date
    
    where = " AND ".join(conditions)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT * FROM features
                WHERE {where}
                ORDER BY calculated_at DESC
                LIMIT 1
            """),
            params
        )
        row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Features not found")
    
    return {
        "ticker": ticker.upper(),
        "features": row.features,
        "calculated_at": row.calculated_at.isoformat()
    }


# ===== News & Sentiment Endpoints =====

@app.get("/news")
async def get_news(
    ticker: Optional[str] = Query(None),
    hours: int = Query(24, le=168),
    limit: int = Query(50, le=200),
    _: bool = Depends(verify_api_key)
):
    """Get recent news articles."""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    conditions = ["published_at > NOW() - INTERVAL ':hours hours'"]
    params = {"hours": hours, "limit": limit}
    
    if ticker:
        conditions.append("tickers LIKE :ticker_pattern")
        params["ticker_pattern"] = f"%{ticker.upper()}%"
    
    where = " AND ".join(conditions)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT id, title, source, published_at, sentiment_label, tickers
                FROM news_articles
                WHERE {where}
                ORDER BY published_at DESC
                LIMIT :limit
            """),
            params
        )
        rows = result.fetchall()
    
    articles = []
    for row in rows:
        articles.append({
            "id": row.id,
            "title": row.title,
            "source": row.source,
            "published_at": row.published_at.isoformat(),
            "sentiment": row.sentiment_label,
            "tickers": row.tickers.split(",") if row.tickers else []
        })
    
    return {
        "articles": articles,
        "count": len(articles)
    }


@app.get("/sentiment/{ticker}")
async def get_ticker_sentiment(
    ticker: str,
    hours: int = Query(24, le=168),
    _: bool = Depends(verify_api_key)
):
    """Get aggregated sentiment for a ticker."""
    from src.ingestors.social import SentimentAggregator
    
    aggregator = SentimentAggregator()
    sentiment = await aggregator.aggregate_sentiment(ticker.upper(), hours)
    
    return sentiment


# ===== Admin Endpoints =====

@app.post("/admin/trigger-job/{job_name}")
async def trigger_job(
    job_name: str,
    _: bool = Depends(verify_api_key)
):
    """Manually trigger a scheduled job."""
    # TODO: Implement job triggering
    return {
        "status": "triggered",
        "job": job_name,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/admin/jobs")
async def list_jobs(
    _: bool = Depends(verify_api_key)
):
    """List all scheduled jobs."""
    # TODO: Get from scheduler
    return {
        "jobs": [
            {"id": "overnight_news", "schedule": "6:00 AM ET"},
            {"id": "premarket_social", "schedule": "6:15 AM ET"},
            {"id": "daily_report", "schedule": "6:30 AM ET"},
            {"id": "premarket_signals", "schedule": "9:25 AM ET"},
            {"id": "intraday_data", "schedule": "Every 5 min during market hours"},
            {"id": "intraday_news", "schedule": "Every 15 min during market hours"},
            {"id": "eod_processing", "schedule": "4:30 PM ET"},
            {"id": "historical_backfill", "schedule": "8:00 PM ET"},
        ]
    }


# ===== Helper Functions =====

def _is_market_open() -> bool:
    """Check if US market is currently open."""
    import pytz
    
    et = pytz.timezone('US/Eastern')
    now = datetime.now(et)
    
    # Check weekday
    if now.weekday() >= 5:
        return False
    
    # Check time
    from datetime import time
    market_open = time(9, 30)
    market_close = time(16, 0)
    
    return market_open <= now.time() <= market_close


# ===== Exception Handlers =====

# ===== Scanner Endpoints =====

@app.get("/scan/patterns")
async def scan_patterns(
    tickers: str = Query(..., description="Comma-separated tickers, e.g., AAPL,GOOGL,MSFT"),
    min_confidence: float = Query(70.0, description="Minimum pattern confidence"),
    _: bool = Depends(verify_api_key)
):
    """
    Scan stocks for chart patterns.
    
    Returns detected patterns with confidence scores, targets, and historical success rates.
    """
    from src.scanners import PatternScanner
    from src.ingestors.market_data import MarketDataIngestor
    
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        ingestor = MarketDataIngestor()
        scanner = PatternScanner()
        
        all_patterns = []
        
        for ticker in ticker_list[:10]:  # Limit to 10 tickers
            try:
                df = await ingestor.fetch_historical_data(ticker, days=100)
                if df is not None and len(df) > 0:
                    patterns = scanner.scan_patterns(df, ticker)
                    patterns = [p for p in patterns if p.confidence >= min_confidence]
                    for p in patterns:
                        all_patterns.append({
                            "ticker": p.ticker,
                            "pattern": p.pattern_type.value,
                            "direction": p.direction,
                            "confidence": p.confidence,
                            "historical_success_rate": p.historical_success_rate,
                            "entry_price": p.entry_price,
                            "target_price": p.target_price,
                            "stop_loss": p.stop_loss,
                            "risk_reward_ratio": p.risk_reward_ratio,
                            "description": p.pattern_description,
                            "trading_notes": p.trading_notes
                        })
            except Exception as e:
                logger.warning(f"Error scanning {ticker}: {e}")
                continue
        
        return {
            "patterns": sorted(all_patterns, key=lambda x: x["confidence"], reverse=True),
            "total": len(all_patterns),
            "scanned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Pattern scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/sectors")
async def scan_sectors(
    _: bool = Depends(verify_api_key)
):
    """
    Scan all sectors for opportunities.
    
    Returns sector performance, rotation analysis, and top opportunities.
    """
    from src.scanners import SectorScanner
    
    try:
        scanner = SectorScanner()
        results = await scanner.scan_all_sectors()
        
        sector_data = []
        for sector, metrics in results.items():
            sector_data.append({
                "sector": sector.value if hasattr(sector, 'value') else str(sector),
                "performance_1d": metrics.performance_1d,
                "performance_1w": metrics.performance_1w,
                "performance_1m": metrics.performance_1m,
                "relative_strength": metrics.relative_strength,
                "volume_ratio": metrics.volume_ratio,
                "momentum_score": metrics.momentum_score,
                "top_stocks": metrics.top_stocks[:5],
                "bottom_stocks": metrics.bottom_stocks[:5]
            })
        
        # Sort by momentum score
        sector_data.sort(key=lambda x: x["momentum_score"], reverse=True)
        
        # Rotation analysis
        rotation = scanner.analyze_rotation(results)
        
        return {
            "sectors": sector_data,
            "rotation": {
                "current_phase": rotation.current_phase,
                "leading_sectors": rotation.leading_sectors[:3],
                "lagging_sectors": rotation.lagging_sectors[:3],
                "rotation_direction": rotation.rotation_direction,
                "sector_recommendation": rotation.recommendation
            },
            "scanned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Sector scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/momentum")
async def scan_momentum(
    universe: str = Query("spy_components", description="Universe to scan: spy_components, nasdaq100, custom"),
    custom_tickers: Optional[str] = Query(None, description="Custom tickers if universe=custom"),
    min_confidence: float = Query(60.0, description="Minimum signal confidence"),
    _: bool = Depends(verify_api_key)
):
    """
    Scan for momentum opportunities.
    
    Returns breakouts, gaps, volume surges, and trend signals.
    """
    from src.scanners import MomentumScanner
    
    try:
        scanner = MomentumScanner()
        
        if universe == "custom" and custom_tickers:
            tickers = [t.strip().upper() for t in custom_tickers.split(",")]
        else:
            tickers = None  # Use default universe
        
        alerts = await scanner.scan_universe(tickers, min_confidence=min_confidence)
        
        results = []
        for alert in alerts:
            results.append({
                "ticker": alert.ticker,
                "signal_type": alert.signal_type.value,
                "confidence": alert.confidence,
                "volume_confirmation": alert.volume_confirmation,
                "entry_zone": {
                    "low": alert.entry_zone[0] if alert.entry_zone else None,
                    "high": alert.entry_zone[1] if alert.entry_zone else None
                },
                "targets": alert.targets[:3] if alert.targets else [],
                "stop_loss": alert.stop_loss,
                "description": alert.description,
                "detected_at": alert.detected_at.isoformat() if alert.detected_at else None
            })
        
        return {
            "alerts": results,
            "total": len(results),
            "scanned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Momentum scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/snapshot")
async def get_market_snapshot(
    _: bool = Depends(verify_api_key)
):
    """
    Get comprehensive market snapshot.
    
    Combines all scanners for a complete market view.
    """
    from src.scanners import MarketMonitor
    
    try:
        monitor = MarketMonitor()
        snapshot = await monitor.scan_market()
        
        return {
            "breadth": {
                "advancing": snapshot.breadth.advancing,
                "declining": snapshot.breadth.declining,
                "new_highs": snapshot.breadth.new_highs,
                "new_lows": snapshot.breadth.new_lows,
                "advance_decline_ratio": snapshot.breadth.advance_decline_ratio,
                "mcclellan_oscillator": snapshot.breadth.mcclellan_oscillator
            },
            "top_patterns": [
                {
                    "ticker": p.ticker,
                    "pattern": p.pattern_type.value,
                    "confidence": p.confidence,
                    "direction": p.direction
                } for p in snapshot.pattern_alerts[:5]
            ],
            "momentum_alerts": [
                {
                    "ticker": a.ticker,
                    "type": a.signal_type.value,
                    "confidence": a.confidence
                } for a in snapshot.momentum_alerts[:5]
            ],
            "key_observations": snapshot.key_observations,
            "generated_at": snapshot.generated_at.isoformat() if snapshot.generated_at else datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Market snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Research Endpoints =====

@app.get("/research/news")
async def get_news_brief(
    period: str = Query("morning", description="Period: morning, midday, closing, overnight"),
    tickers: Optional[str] = Query(None, description="Filter by tickers"),
    _: bool = Depends(verify_api_key)
):
    """
    Get AI-condensed news brief.
    
    Returns summarized news with sentiment and trading implications.
    """
    from src.research import NewsAnalyzer
    from src.ingestors.news import NewsIngestor
    
    try:
        ingestor = NewsIngestor()
        analyzer = NewsAnalyzer()
        
        # Fetch news
        ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None
        raw_news = await ingestor.fetch_news(tickers=ticker_list, limit=50)
        
        # Analyze
        analyzed = await analyzer.analyze_news_batch(raw_news)
        
        # Generate brief
        brief = await analyzer.generate_brief(analyzed, period=period)
        
        return {
            "period": brief.period,
            "market_mood": brief.market_mood,
            "headline": brief.headline,
            "executive_summary": brief.executive_summary,
            "trading_focus": brief.trading_focus,
            "top_stories": [
                {
                    "title": s.title,
                    "tickers": s.tickers,
                    "sentiment": s.sentiment.value,
                    "category": s.category.value
                } for s in brief.top_stories[:5]
            ],
            "bullish_catalysts": brief.bullish_catalysts[:3],
            "bearish_catalysts": brief.bearish_catalysts[:3],
            "stocks_to_watch": brief.stocks_to_watch[:10],
            "generated_at": brief.generated_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"News brief error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/earnings/{ticker}")
async def get_earnings_analysis(
    ticker: str,
    _: bool = Depends(verify_api_key)
):
    """
    Get AI-analyzed earnings report for a ticker.
    
    Returns beat/miss analysis, guidance, and trading implications.
    """
    from src.research import EarningsAnalyzer
    
    try:
        analyzer = EarningsAnalyzer()
        
        # TODO: Fetch actual earnings data from provider
        # For now, return structure
        return {
            "ticker": ticker.upper(),
            "message": "Earnings analysis requires active earnings data feed",
            "structure": {
                "eps_result": "beat/miss/inline",
                "revenue_result": "beat/miss/inline",
                "guidance": "raised/lowered/maintained",
                "sentiment": "bullish/bearish/neutral",
                "ai_summary": "AI-generated summary",
                "trading_recommendation": "action guidance"
            }
        }
        
    except Exception as e:
        logger.error(f"Earnings analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Performance Endpoints =====

@app.get("/performance/stats")
async def get_performance_stats(
    period: str = Query("all_time", description="Period: daily, weekly, monthly, all_time"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    _: bool = Depends(verify_api_key)
):
    """
    Get signal performance statistics.
    
    Returns win rates, P&L, and strategy breakdown.
    """
    from src.performance import PerformanceTracker
    
    try:
        tracker = PerformanceTracker()
        
        # Load historical data
        await tracker.load_from_db()
        
        stats = tracker.get_performance_stats(period=period, strategy=strategy)
        
        return {
            "period": stats.period,
            "total_signals": stats.total_signals,
            "winners": stats.winners,
            "losers": stats.losers,
            "active": stats.active,
            "win_rate": round(stats.win_rate, 1),
            "total_pnl_pct": round(stats.total_pnl_pct, 2),
            "avg_winner_pct": round(stats.avg_winner_pct, 2),
            "avg_loser_pct": round(stats.avg_loser_pct, 2),
            "profit_factor": round(stats.profit_factor, 2),
            "expectancy": round(stats.expectancy, 2),
            "current_streak": stats.current_streak,
            "max_win_streak": stats.max_win_streak,
            "strategy_breakdown": stats.strategy_breakdown,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/performance/analytics/{strategy}")
async def get_strategy_analytics(
    strategy: str,
    _: bool = Depends(verify_api_key)
):
    """
    Get detailed analytics for a strategy.
    
    Returns risk-adjusted metrics, drawdown analysis, and recommendations.
    """
    from src.performance import PerformanceAnalytics, PerformanceTracker
    
    try:
        tracker = PerformanceTracker()
        analytics = PerformanceAnalytics()
        
        await tracker.load_from_db()
        
        # Get returns for strategy
        strategy_signals = [s for s in tracker.completed_signals if s.strategy == strategy]
        returns = [s.pnl_pct for s in strategy_signals]
        
        if not returns:
            return {
                "strategy": strategy,
                "message": "No completed signals for this strategy",
                "trades": 0
            }
        
        metrics = analytics.calculate_strategy_metrics(returns, strategy)
        
        return {
            "strategy": strategy,
            "total_return": round(metrics.total_return, 2),
            "annualized_return": round(metrics.annualized_return, 2),
            "volatility": round(metrics.volatility, 2),
            "max_drawdown": round(metrics.max_drawdown, 2),
            "sharpe_ratio": round(metrics.sharpe_ratio, 2),
            "sortino_ratio": round(metrics.sortino_ratio, 2),
            "calmar_ratio": round(metrics.calmar_ratio, 2),
            "win_rate": round(metrics.win_rate, 1),
            "profit_factor": round(metrics.profit_factor, 2),
            "total_trades": metrics.total_trades,
            "max_consecutive_losses": metrics.max_consecutive_losses,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Strategy analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# ===== Broker Endpoints =====

@app.get("/broker/status")
async def get_broker_status(
    _: bool = Depends(verify_api_key)
):
    """
    Get status of all connected brokers.
    
    Returns:
    - List of brokers with connection status
    - Active broker
    - Account balances
    """
    from src.brokers.broker_manager import get_broker_manager
    
    try:
        manager = await get_broker_manager()
        brokers = manager.get_available_brokers()
        
        return {
            "active_broker": manager.active_broker_type.value,
            "brokers": brokers,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Broker status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/broker/switch/{broker_type}")
async def switch_broker(
    broker_type: str,
    _: bool = Depends(verify_api_key)
):
    """
    Switch active broker.
    
    Args:
        broker_type: 'futu', 'ib', or 'paper'
    """
    from src.brokers.broker_manager import get_broker_manager, BrokerType
    
    try:
        broker_enum = BrokerType(broker_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid broker type: {broker_type}")
    
    try:
        manager = await get_broker_manager()
        success = manager.set_active_broker(broker_enum)
        
        if success:
            return {
                "success": True,
                "active_broker": broker_type,
                "message": f"Switched to {broker_type}"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Broker {broker_type} not available")
            
    except Exception as e:
        logger.error(f"Switch broker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/broker/account")
async def get_broker_account(
    broker: Optional[str] = None,
    _: bool = Depends(verify_api_key)
):
    """
    Get account information from broker.
    
    Args:
        broker: Specific broker (uses active if not specified)
    """
    from src.brokers.broker_manager import get_broker_manager, BrokerType
    
    try:
        manager = await get_broker_manager()
        
        broker_type = None
        if broker:
            try:
                broker_type = BrokerType(broker.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid broker: {broker}")
        
        account = await manager.get_account(broker_type)
        
        return {
            "account_id": account.account_id,
            "currency": account.currency,
            "cash": round(account.cash, 2),
            "buying_power": round(account.buying_power, 2),
            "portfolio_value": round(account.portfolio_value, 2),
            "unrealized_pnl": round(account.unrealized_pnl, 2),
            "realized_pnl_today": round(account.realized_pnl_today, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Account info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/broker/positions")
async def get_broker_positions(
    broker: Optional[str] = None,
    _: bool = Depends(verify_api_key)
):
    """
    Get open positions from broker.
    
    Args:
        broker: Specific broker (uses active if not specified)
    """
    from src.brokers.broker_manager import get_broker_manager, BrokerType
    
    try:
        manager = await get_broker_manager()
        
        broker_type = None
        if broker:
            try:
                broker_type = BrokerType(broker.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid broker: {broker}")
        
        positions = await manager.get_positions(broker_type)
        
        return {
            "positions": [
                {
                    "ticker": pos.ticker,
                    "quantity": pos.quantity,
                    "avg_price": round(pos.avg_price, 2),
                    "current_price": round(pos.current_price, 2),
                    "market_value": round(pos.market_value, 2),
                    "unrealized_pnl": round(pos.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(pos.unrealized_pnl_pct, 2),
                    "market": pos.market.value
                }
                for pos in positions
            ],
            "total_positions": len(positions),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/broker/order")
async def place_order(
    ticker: str,
    side: str,
    quantity: int,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    _: bool = Depends(verify_api_key)
):
    """
    Place a trading order through the active broker.
    
    Args:
        ticker: Stock symbol
        side: 'buy' or 'sell'
        quantity: Number of shares
        order_type: 'market', 'limit', 'stop'
        limit_price: For limit orders
        stop_price: For stop orders
    """
    from src.brokers.broker_manager import get_broker_manager
    from src.brokers.base import OrderSide, OrderType
    
    try:
        # Validate side
        try:
            order_side = OrderSide(side.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid side: {side}")
        
        # Validate order type
        try:
            order_type_enum = OrderType(order_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid order type: {order_type}")
        
        manager = await get_broker_manager()
        result = await manager.place_order(
            ticker=ticker.upper(),
            side=order_side,
            quantity=quantity,
            order_type=order_type_enum,
            limit_price=limit_price,
            stop_price=stop_price
        )
        
        return {
            "success": result.success,
            "order_id": result.order_id,
            "status": result.status.value,
            "filled_qty": result.filled_qty,
            "avg_fill_price": result.avg_fill_price,
            "message": result.message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Place order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/broker/quote/{ticker}")
async def get_quote(
    ticker: str,
    _: bool = Depends(verify_api_key)
):
    """Get real-time quote for a ticker."""
    from src.brokers.broker_manager import get_broker_manager
    
    try:
        manager = await get_broker_manager()
        quote = await manager.get_quote(ticker.upper())
        
        if not quote:
            raise HTTPException(status_code=404, detail=f"Quote not found for {ticker}")
        
        return {
            "ticker": quote.ticker,
            "price": round(quote.price, 2),
            "bid": round(quote.bid, 2),
            "ask": round(quote.ask, 2),
            "volume": quote.volume,
            "open": round(quote.open, 2),
            "high": round(quote.high, 2),
            "low": round(quote.low, 2),
            "prev_close": round(quote.prev_close, 2),
            "change": round(quote.change, 2),
            "change_pct": round(quote.change_pct, 2),
            "timestamp": quote.timestamp.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quote error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Telegram Bot Endpoints =====

@app.post("/telegram/start")
async def start_telegram_bot_endpoint(
    _: bool = Depends(verify_api_key)
):
    """Start the interactive Telegram bot."""
    from src.notifications import start_telegram_bot
    
    try:
        bot = await start_telegram_bot()
        
        return {
            "success": True,
            "message": "Telegram bot started",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Telegram bot start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/telegram/send")
async def send_telegram_message(
    message: str,
    _: bool = Depends(verify_api_key)
):
    """Send a message via Telegram."""
    from src.notifications import TelegramNotifier
    
    try:
        notifier = TelegramNotifier()
        success = await notifier.send_message(message)
        
        return {
            "success": success,
            "message": "Message sent" if success else "Failed to send message",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Main Entry Point =====

def start():
    """Start the API server."""
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    start()
