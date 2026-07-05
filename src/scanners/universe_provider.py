"""
TradingAI Bot - Universe Provider

Provides stock universe filtering and selection inspired by:
- FinanceDatabase: Comprehensive equity database with sector/industry filtering
- freqtrade: Dynamic pairlist management
- quantopian: Pipeline for universe selection

Features:
- Multiple index universes (S&P 500, Russell 2000, NASDAQ 100, etc.)
- Dynamic filtering by sector, industry, market cap
- Liquidity filtering (volume, spread)
- Custom screener integration
- Scheduled universe updates
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


class IndexUniverse(str, Enum):
    """Pre-defined stock universes."""
    SP500 = "sp500"                    # S&P 500 (large cap)
    SP400 = "sp400"                    # S&P 400 (mid cap)
    SP600 = "sp600"                    # S&P 600 (small cap)
    SP1500 = "sp1500"                  # S&P 1500 (combined)
    NASDAQ100 = "nasdaq100"            # NASDAQ 100
    NASDAQ = "nasdaq"                  # Full NASDAQ
    NYSE = "nyse"                      # Full NYSE
    RUSSELL1000 = "russell1000"        # Russell 1000
    RUSSELL2000 = "russell2000"        # Russell 2000 (small cap)
    RUSSELL3000 = "russell3000"        # Russell 3000
    DOW30 = "dow30"                    # Dow Jones 30
    ALL_US = "all_us"                  # All US stocks
    CUSTOM = "custom"                  # Custom list


class MarketCap(str, Enum):
    """Market capitalization categories."""
    MEGA = "mega"          # > $200B
    LARGE = "large"        # $10B - $200B
    MID = "mid"            # $2B - $10B
    SMALL = "small"        # $300M - $2B
    MICRO = "micro"        # $50M - $300M
    NANO = "nano"          # < $50M


class Sector(str, Enum):
    """GICS Sectors."""
    ENERGY = "Energy"
    MATERIALS = "Materials"
    INDUSTRIALS = "Industrials"
    CONSUMER_DISCRETIONARY = "Consumer Discretionary"
    CONSUMER_STAPLES = "Consumer Staples"
    HEALTH_CARE = "Health Care"
    FINANCIALS = "Financials"
    INFORMATION_TECHNOLOGY = "Information Technology"
    COMMUNICATION_SERVICES = "Communication Services"
    UTILITIES = "Utilities"
    REAL_ESTATE = "Real Estate"


@dataclass
class UniverseFilter:
    """Configuration for universe filtering."""
    
    # Base universe
    base_universe: IndexUniverse = IndexUniverse.SP500
    
    # Sector/Industry filtering
    include_sectors: List[str] = field(default_factory=list)
    exclude_sectors: List[str] = field(default_factory=list)
    include_industries: List[str] = field(default_factory=list)
    exclude_industries: List[str] = field(default_factory=list)
    
    # Market cap filtering
    market_caps: List[MarketCap] = field(default_factory=list)
    min_market_cap: float = 0           # In millions
    max_market_cap: float = float('inf')
    
    # Price filtering
    min_price: float = 5.0
    max_price: float = 10000.0
    
    # Liquidity filtering
    min_avg_volume: int = 100000        # Minimum 100K daily volume
    min_avg_dollar_volume: float = 1000000  # Minimum $1M daily dollar volume
    
    # Technical filters
    min_days_traded: int = 252          # At least 1 year of data
    exclude_otc: bool = True            # Exclude OTC/Pink sheets
    exclude_adr: bool = False           # Exclude ADRs
    exclude_etf: bool = True            # Exclude ETFs
    
    # Custom filters
    custom_tickers: List[str] = field(default_factory=list)
    exclude_tickers: List[str] = field(default_factory=list)


class UniverseProvider:
    """
    Provides filtered stock universes for screening and trading.
    
    Supports:
    - Pre-defined indices (S&P 500, NASDAQ, etc.)
    - Dynamic filtering by fundamentals
    - Technical filter integration
    - Scheduled refresh
    """
    
    # Popular index components (sample - in production, fetch from data provider)
    # These would be updated periodically
    SAMPLE_INDEX_COMPONENTS = {
        IndexUniverse.DOW30: [
            'AAPL', 'AMGN', 'AXP', 'BA', 'CAT', 'CRM', 'CSCO', 'CVX', 'DIS', 'DOW',
            'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM', 'KO', 'MCD', 'MMM',
            'MRK', 'MSFT', 'NKE', 'PG', 'TRV', 'UNH', 'V', 'VZ', 'WBA', 'WMT'
        ],
        IndexUniverse.NASDAQ100: [
            'AAPL', 'ABNB', 'ADBE', 'ADI', 'ADP', 'ADSK', 'AEP', 'AMAT', 'AMD', 'AMGN',
            'AMZN', 'ANSS', 'ASML', 'AVGO', 'AZN', 'BIIB', 'BKNG', 'BKR', 'CDNS', 'CEG',
            'CHTR', 'CMCSA', 'COST', 'CPRT', 'CRWD', 'CSCO', 'CSGP', 'CSX', 'CTAS', 'CTSH',
            'DDOG', 'DLTR', 'DXCM', 'EA', 'EBAY', 'ENPH', 'EXC', 'FANG', 'FAST', 'FTNT',
            'GFS', 'GILD', 'GOOG', 'GOOGL', 'HON', 'IDXX', 'ILMN', 'INTC', 'INTU', 'ISRG',
            'JD', 'KDP', 'KHC', 'KLAC', 'LRCX', 'LULU', 'MAR', 'MCHP', 'MDLZ', 'MELI',
            'META', 'MNST', 'MRNA', 'MRVL', 'MSFT', 'MU', 'NFLX', 'NVDA', 'NXPI', 'ODFL',
            'ON', 'ORLY', 'PANW', 'PAYX', 'PCAR', 'PDD', 'PEP', 'PYPL', 'QCOM', 'REGN',
            'RIVN', 'ROST', 'SBUX', 'SIRI', 'SNPS', 'SPLK', 'TEAM', 'TMUS', 'TSLA', 'TXN',
            'VRSK', 'VRTX', 'WBA', 'WBD', 'WDAY', 'XEL', 'ZM', 'ZS'
        ],
    }
    
    # Sector mapping for common stocks (sample)
    SECTOR_MAPPING = {
        'AAPL': Sector.INFORMATION_TECHNOLOGY,
        'MSFT': Sector.INFORMATION_TECHNOLOGY,
        'GOOGL': Sector.COMMUNICATION_SERVICES,
        'AMZN': Sector.CONSUMER_DISCRETIONARY,
        'NVDA': Sector.INFORMATION_TECHNOLOGY,
        'META': Sector.COMMUNICATION_SERVICES,
        'TSLA': Sector.CONSUMER_DISCRETIONARY,
        'JPM': Sector.FINANCIALS,
        'JNJ': Sector.HEALTH_CARE,
        'V': Sector.FINANCIALS,
        'UNH': Sector.HEALTH_CARE,
        'HD': Sector.CONSUMER_DISCRETIONARY,
        'PG': Sector.CONSUMER_STAPLES,
        'XOM': Sector.ENERGY,
        'CVX': Sector.ENERGY,
    }
    
    def __init__(self, data_provider=None):
        """
        Initialize universe provider.
        
        Args:
            data_provider: Optional market data provider for quotes/fundamentals
        """
        self.data_provider = data_provider
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_duration = timedelta(hours=1)
        self.logger = logging.getLogger(__name__)
    
    def get_universe(
        self, 
        filter_config: Optional[UniverseFilter] = None
    ) -> List[str]:
        """
        Get filtered stock universe.
        
        Args:
            filter_config: Universe filter configuration
        
        Returns:
            List of ticker symbols
        """
        if filter_config is None:
            filter_config = UniverseFilter()
        
        # Start with base universe
        tickers = self._get_base_universe(filter_config.base_universe)
        
        # Add custom tickers
        if filter_config.custom_tickers:
            tickers = list(set(tickers) | set(filter_config.custom_tickers))
        
        # Apply filters
        tickers = self._apply_filters(tickers, filter_config)
        
        # Remove excluded tickers
        if filter_config.exclude_tickers:
            tickers = [t for t in tickers if t not in filter_config.exclude_tickers]
        
        return sorted(tickers)
    
    def _get_base_universe(self, universe: IndexUniverse) -> List[str]:
        """Get base universe tickers."""
        
        # Check cache
        cache_key = f"universe_{universe.value}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        if universe in self.SAMPLE_INDEX_COMPONENTS:
            tickers = self.SAMPLE_INDEX_COMPONENTS[universe]
        elif universe == IndexUniverse.SP500:
            tickers = self._fetch_sp500_components()
        elif universe == IndexUniverse.ALL_US:
            tickers = self._fetch_all_us_stocks()
        else:
            # Fallback to S&P 500
            tickers = self._fetch_sp500_components()
        
        # Cache result
        self._cache[cache_key] = tickers
        self._cache_time[cache_key] = datetime.now()
        
        return tickers
    
    def _fetch_sp500_components(self) -> List[str]:
        """
        Fetch S&P 500 components.
        
        In production, this would fetch from Wikipedia, Alpaca, or a data provider.
        """
        # Sample S&P 500 components (top holdings by weight)
        return [
            'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'META', 'BRK.B', 'UNH', 'XOM',
            'LLY', 'JPM', 'JNJ', 'V', 'PG', 'MA', 'AVGO', 'HD', 'CVX', 'MRK',
            'COST', 'ABBV', 'PEP', 'KO', 'ADBE', 'WMT', 'MCD', 'CSCO', 'CRM', 'BAC',
            'PFE', 'ACN', 'TMO', 'NFLX', 'AMD', 'ABT', 'LIN', 'DIS', 'ORCL', 'NKE',
            'DHR', 'TXN', 'CMCSA', 'INTU', 'PM', 'VZ', 'NEE', 'COP', 'WFC', 'RTX',
            'AMGN', 'UNP', 'QCOM', 'LOW', 'HON', 'IBM', 'SPGI', 'BA', 'GE', 'CAT',
            'ELV', 'GS', 'DE', 'NOW', 'AMAT', 'ISRG', 'MS', 'BMY', 'BLK', 'SBUX',
            'BKNG', 'TJX', 'AXP', 'PLD', 'SYK', 'MDLZ', 'LMT', 'ADP', 'ADI', 'GILD',
            'VRTX', 'MMC', 'CVS', 'LRCX', 'SCHW', 'ETN', 'C', 'TMUS', 'MO', 'CI',
            'ZTS', 'CB', 'REGN', 'SO', 'FI', 'EOG', 'BDX', 'DUK', 'CME', 'ITW'
        ]
    
    def _fetch_all_us_stocks(self) -> List[str]:
        """
        Fetch all tradable US stocks.
        
        In production, this would query a data provider API.
        For now, returns a combined list of major indices.
        """
        all_stocks = set()
        
        # Combine major indices
        for universe in [IndexUniverse.DOW30, IndexUniverse.NASDAQ100]:
            if universe in self.SAMPLE_INDEX_COMPONENTS:
                all_stocks.update(self.SAMPLE_INDEX_COMPONENTS[universe])
        
        # Add S&P 500
        all_stocks.update(self._fetch_sp500_components())
        
        return list(all_stocks)
    
    def _apply_filters(
        self, 
        tickers: List[str], 
        config: UniverseFilter
    ) -> List[str]:
        """Apply filtering criteria to ticker list."""
        
        filtered = tickers.copy()
        
        # Sector filtering
        if config.include_sectors:
            filtered = [
                t for t in filtered 
                if (t in self.SECTOR_MAPPING and self.SECTOR_MAPPING[t].value in config.include_sectors)
                or t not in self.SECTOR_MAPPING  # Keep if no mapping
            ]
        
        if config.exclude_sectors:
            filtered = [
                t for t in filtered
                if t not in self.SECTOR_MAPPING 
                or self.SECTOR_MAPPING[t].value not in config.exclude_sectors
            ]
        
        # Price filtering (would need market data)
        # In production: filtered = self._filter_by_price(filtered, config)
        
        # Volume filtering (would need market data)
        # In production: filtered = self._filter_by_volume(filtered, config)
        
        return filtered
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._cache:
            return False
        if key not in self._cache_time:
            return False
        return datetime.now() - self._cache_time[key] < self._cache_duration
    
    async def get_universe_with_data(
        self,
        filter_config: Optional[UniverseFilter] = None,
        include_fundamentals: bool = False
    ) -> pd.DataFrame:
        """
        Get filtered universe with market data.
        
        Args:
            filter_config: Universe filter configuration
            include_fundamentals: Whether to include fundamental data
        
        Returns:
            DataFrame with ticker info and market data
        """
        tickers = self.get_universe(filter_config)
        
        # Build DataFrame with available info
        data = []
        for ticker in tickers:
            entry = {
                'ticker': ticker,
                'sector': self.SECTOR_MAPPING.get(ticker, ''),
            }
            
            if self.data_provider:
                try:
                    # Get quote data
                    quote = await self.data_provider.get_quote(ticker)
                    if quote:
                        entry.update({
                            'price': quote.get('price'),
                            'change_pct': quote.get('change_pct'),
                            'volume': quote.get('volume'),
                            'avg_volume': quote.get('avg_volume'),
                        })
                except Exception as e:
                    self.logger.debug(f"Could not fetch data for {ticker}: {e}")
            
            data.append(entry)
        
        return pd.DataFrame(data)
    
    # ========== Pre-built Universe Factories ==========
    
    @classmethod
    def large_cap_growth(cls) -> UniverseFilter:
        """Pre-built filter for large-cap growth stocks."""
        return UniverseFilter(
            base_universe=IndexUniverse.SP500,
            market_caps=[MarketCap.LARGE, MarketCap.MEGA],
            include_sectors=[
                Sector.INFORMATION_TECHNOLOGY.value,
                Sector.COMMUNICATION_SERVICES.value,
                Sector.CONSUMER_DISCRETIONARY.value,
                Sector.HEALTH_CARE.value,
            ],
            min_avg_volume=500000,
        )
    
    @classmethod
    def small_cap_value(cls) -> UniverseFilter:
        """Pre-built filter for small-cap value stocks."""
        return UniverseFilter(
            base_universe=IndexUniverse.RUSSELL2000,
            market_caps=[MarketCap.SMALL, MarketCap.MICRO],
            min_avg_volume=100000,
        )
    
    @classmethod
    def tech_stocks(cls) -> UniverseFilter:
        """Pre-built filter for technology stocks."""
        return UniverseFilter(
            base_universe=IndexUniverse.NASDAQ100,
            include_sectors=[
                Sector.INFORMATION_TECHNOLOGY.value,
            ],
            min_avg_volume=200000,
        )
    
    @classmethod
    def dividend_stocks(cls) -> UniverseFilter:
        """Pre-built filter for dividend-paying stocks."""
        return UniverseFilter(
            base_universe=IndexUniverse.SP500,
            include_sectors=[
                Sector.UTILITIES.value,
                Sector.REAL_ESTATE.value,
                Sector.CONSUMER_STAPLES.value,
                Sector.FINANCIALS.value,
            ],
            min_avg_volume=100000,
        )
    
    @classmethod
    def momentum_candidates(cls) -> UniverseFilter:
        """Pre-built filter for momentum trading candidates."""
        return UniverseFilter(
            base_universe=IndexUniverse.SP500,
            min_price=10.0,
            max_price=500.0,
            min_avg_volume=500000,
            min_avg_dollar_volume=5000000,
        )


class DynamicUniverseProvider(UniverseProvider):
    """
    Dynamic universe provider with real-time filtering.
    
    Extends UniverseProvider with:
    - Real-time price/volume filtering
    - Technical indicator screening
    - Periodic refresh
    """
    
    def __init__(self, data_provider, refresh_interval: int = 3600):
        super().__init__(data_provider)
        self.refresh_interval = refresh_interval
        self._last_refresh: Optional[datetime] = None
    
    async def get_filtered_universe(
        self,
        base_filter: UniverseFilter,
        technical_filter: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Get universe with real-time filtering.
        
        Args:
            base_filter: Base universe filter
            technical_filter: Technical criteria (e.g., above_sma_50, rsi_below_30)
        
        Returns:
            List of tickers passing all filters
        """
        # Get base universe
        tickers = self.get_universe(base_filter)
        
        if not self.data_provider or not technical_filter:
            return tickers
        
        # Apply real-time filters
        filtered = []
        
        for ticker in tickers:
            try:
                if await self._passes_technical_filter(ticker, technical_filter):
                    filtered.append(ticker)
            except Exception as e:
                self.logger.debug(f"Filter check failed for {ticker}: {e}")
        
        return filtered
    
    async def _passes_technical_filter(
        self,
        ticker: str,
        filters: Dict[str, Any]
    ) -> bool:
        """Check if ticker passes technical filters."""
        
        # Get historical data
        df = await self.data_provider.get_historical(ticker, days=60)
        if df is None or len(df) < 50:
            return False
        
        # Import indicators
        from .algo.indicators import IndicatorLibrary
        
        current_price = df['close'].iloc[-1]
        
        # Check each filter
        if 'above_sma_50' in filters and filters['above_sma_50']:
            sma_50 = IndicatorLibrary.sma(df['close'], 50).iloc[-1]
            if current_price < sma_50:
                return False
        
        if 'rsi_below' in filters:
            rsi = IndicatorLibrary.rsi(df['close'], 14).iloc[-1]
            if rsi >= filters['rsi_below']:
                return False
        
        if 'rsi_above' in filters:
            rsi = IndicatorLibrary.rsi(df['close'], 14).iloc[-1]
            if rsi <= filters['rsi_above']:
                return False
        
        if 'min_volume_ratio' in filters:
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            if df['volume'].iloc[-1] < avg_vol * filters['min_volume_ratio']:
                return False
        
        return True
