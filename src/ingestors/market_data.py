"""
TradingAI Bot - Market Data Ingestor
Fetches OHLCV price data from market data providers.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import aiohttp

from src.core.config import get_settings
from src.core.database import get_session
from src.ingestors.base import BaseIngestor

settings = get_settings()


class MarketDataIngestor(BaseIngestor):
    """
    Ingests OHLCV market data from Polygon.io and/or Alpaca.
    
    Supports:
    - Daily OHLCV for US equities
    - Intraday data (1min, 5min, 15min, 1H)
    - Historical backfill
    """
    
    # Polygon.io base URL
    POLYGON_BASE_URL = "https://api.polygon.io"
    
    # Alpaca Markets base URL
    ALPACA_BASE_URL = "https://data.alpaca.markets"
    
    def __init__(self):
        super().__init__("market_data")
        self.polygon_api_key = settings.polygon_api_key
        self.alpaca_api_key = settings.alpaca_api_key
        self.alpaca_api_secret = settings.alpaca_secret_key
        self._rate_limit_delay = 0.15  # Polygon free tier: 5 calls/min
    
    async def fetch(
        self, 
        tickers: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interval: str = "day"
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV data for specified tickers.
        
        Args:
            tickers: List of ticker symbols (default: SP500 constituents)
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Data interval (day, hour, minute)
        
        Returns:
            List of OHLCV records
        """
        if not tickers:
            tickers = await self._get_universe()
        
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        all_data = []
        
        async with aiohttp.ClientSession() as session:
            for ticker in tickers:
                await self._respect_rate_limit()
                
                try:
                    data = await self._fetch_polygon(
                        session, ticker, start_date, end_date, interval
                    )
                    all_data.extend(data)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch {ticker}: {e}")
                    continue
        
        return all_data
    
    async def _fetch_polygon(
        self,
        session: aiohttp.ClientSession,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """Fetch data from Polygon.io."""
        # Map interval to Polygon format
        interval_map = {
            "minute": ("minute", 1),
            "5min": ("minute", 5),
            "15min": ("minute", 15),
            "hour": ("hour", 1),
            "day": ("day", 1)
        }
        
        timespan, multiplier = interval_map.get(interval, ("day", 1))
        
        url = (
            f"{self.POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/"
            f"{multiplier}/{timespan}/"
            f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        )
        
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.polygon_api_key
        }
        
        async with session.get(url, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Polygon API error: {response.status} - {text}")
            
            data = await response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                return []
            
            # Transform to standard format
            records = []
            for bar in data["results"]:
                records.append({
                    "ticker": ticker,
                    "timestamp": datetime.fromtimestamp(bar["t"] / 1000),
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"],
                    "volume": bar["v"],
                    "vwap": bar.get("vw"),
                    "trade_count": bar.get("n"),
                    "interval": interval,
                    "source": "polygon"
                })
            
            return records
    
    async def _fetch_alpaca(
        self,
        session: aiohttp.ClientSession,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """Fetch data from Alpaca Markets."""
        # Map interval to Alpaca format
        timeframe_map = {
            "minute": "1Min",
            "5min": "5Min",
            "15min": "15Min",
            "hour": "1Hour",
            "day": "1Day"
        }
        
        timeframe = timeframe_map.get(interval, "1Day")
        
        url = f"{self.ALPACA_BASE_URL}/v2/stocks/bars"
        
        headers = {
            "APCA-API-KEY-ID": self.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.alpaca_api_secret
        }
        
        params = {
            "symbols": ",".join(tickers[:100]),  # Alpaca limit
            "timeframe": timeframe,
            "start": start_date.isoformat() + "Z",
            "end": end_date.isoformat() + "Z",
            "limit": 10000,
            "adjustment": "all"
        }
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"Alpaca API error: {response.status} - {text}")
            
            data = await response.json()
            
            records = []
            for ticker, bars in data.get("bars", {}).items():
                for bar in bars:
                    records.append({
                        "ticker": ticker,
                        "timestamp": datetime.fromisoformat(bar["t"].replace("Z", "")),
                        "open": bar["o"],
                        "high": bar["h"],
                        "low": bar["l"],
                        "close": bar["c"],
                        "volume": bar["v"],
                        "vwap": bar.get("vw"),
                        "trade_count": bar.get("n"),
                        "interval": interval,
                        "source": "alpaca"
                    })
            
            return records
    
    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform and validate OHLCV data."""
        transformed = []
        
        for record in raw_data:
            # Basic validation
            if not all([
                record.get("ticker"),
                record.get("timestamp"),
                record.get("close") is not None,
                record.get("volume") is not None
            ]):
                continue
            
            # Ensure proper types
            transformed.append({
                "ticker": record["ticker"].upper(),
                "timestamp": record["timestamp"],
                "open": float(record.get("open", record["close"])),
                "high": float(record.get("high", record["close"])),
                "low": float(record.get("low", record["close"])),
                "close": float(record["close"]),
                "volume": int(record["volume"]),
                "vwap": float(record["vwap"]) if record.get("vwap") else None,
                "trade_count": int(record["trade_count"]) if record.get("trade_count") else None,
                "interval": record.get("interval", "day"),
                "source": record.get("source", "unknown")
            })
        
        return transformed
    
    async def store(self, records: List[Dict[str, Any]]) -> int:
        """Store OHLCV records in database."""
        if not records:
            return 0
        
        stored_count = 0
        
        async with get_session() as session:
            try:
                # Use raw SQL for bulk upsert (more efficient)
                from sqlalchemy import text
                
                # Batch insert with ON CONFLICT — parameterized to prevent SQL injection
                batch_size = 500
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]

                    for r in batch:
                        sql = text("""
                            INSERT INTO ohlcv (
                                ticker, timestamp, open, high, low, close,
                                volume, vwap, trade_count, interval, source
                            )
                            VALUES (
                                :ticker, :timestamp, :open, :high, :low, :close,
                                :volume, :vwap, :trade_count, :interval, :source
                            )
                            ON CONFLICT (ticker, timestamp, interval)
                            DO UPDATE SET
                                open = EXCLUDED.open,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                close = EXCLUDED.close,
                                volume = EXCLUDED.volume,
                                vwap = EXCLUDED.vwap,
                                trade_count = EXCLUDED.trade_count,
                                source = EXCLUDED.source,
                                updated_at = NOW()
                        """)
                        await session.execute(sql, {
                            "ticker": r["ticker"],
                            "timestamp": r["timestamp"],
                            "open": r["open"],
                            "high": r["high"],
                            "low": r["low"],
                            "close": r["close"],
                            "volume": r["volume"],
                            "vwap": r.get("vwap"),
                            "trade_count": r.get("trade_count"),
                            "interval": r["interval"],
                            "source": r["source"],
                        })
                    stored_count += len(batch)
                
                await session.commit()
                
            except Exception as e:
                self.logger.error(f"Failed to store OHLCV data: {e}")
                await session.rollback()
                raise
        
        return stored_count
    
    async def _get_universe(self) -> List[str]:
        """Get default trading universe (SP500 + some popular ETFs)."""
        # Major ETFs
        etfs = ["SPY", "QQQ", "IWM", "DIA", "VTI", "XLF", "XLE", "XLK", "XLV", "XLY"]
        
        # Top SP500 by market cap (sample)
        top_stocks = [
            "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "TSLA",
            "BRK.B", "UNH", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK",
            "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD", "TMO",
            "ACN", "CSCO", "ABT", "DHR", "NEE", "VZ", "ADBE", "TXN", "PM",
            "CMCSA", "NKE", "CRM", "AMD", "INTC", "QCOM", "BA", "CAT", "DE"
        ]
        
        return etfs + top_stocks
    
    async def fetch_realtime_quote(
        self,
        ticker: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch real-time quote for a single ticker."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.POLYGON_BASE_URL}/v2/last/trade/{ticker}"
            params = {"apiKey": self.polygon_api_key}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                if data.get("status") != "success":
                    return None
                
                result = data.get("results", {})
                return {
                    "ticker": ticker,
                    "price": result.get("p"),
                    "size": result.get("s"),
                    "timestamp": datetime.fromtimestamp(result.get("t", 0) / 1e9),
                    "exchange": result.get("x")
                }
