"""
TradingAI Bot - Earnings & Event Trading Strategies

Trade the volatility around earnings or major news events,
but hold for days-weeks rather than minutes.

Strategies:
1. PreEarningsMomentumStrategy - Buy strong stocks 2-4 weeks before earnings
2. PostEarningsDriftStrategy - Trade in direction of earnings gap for 2-6 weeks
3. EarningsBreakoutStrategy - Trade breakouts after strong earnings reaction

Event-driven trading requires careful position sizing due to gap risk.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
import logging

from .base_strategy import IStrategy, StrategyConfig, StrategyMode, TimeFrame
from .indicators import IndicatorLibrary as IL

logger = logging.getLogger(__name__)


class EarningsReaction(str, Enum):
    """Type of earnings reaction."""
    STRONG_POSITIVE = "strong_positive"   # Gap up > 5%, high volume
    POSITIVE = "positive"                  # Gap up 2-5%
    NEUTRAL = "neutral"                    # Gap -2% to +2%
    NEGATIVE = "negative"                  # Gap down 2-5%
    STRONG_NEGATIVE = "strong_negative"   # Gap down > 5%


@dataclass
class EarningsEvent:
    """Represents an earnings event."""
    ticker: str
    earnings_date: datetime
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    eps_surprise_pct: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    revenue_surprise_pct: Optional[float] = None
    gap_pct: float = 0.0
    reaction: EarningsReaction = EarningsReaction.NEUTRAL
    volume_ratio: float = 1.0


# ==============================================================================
# Strategy 1: Pre-Earnings Momentum (2-4 weeks before earnings)
# ==============================================================================

class PreEarningsMomentumStrategy(IStrategy):
    """
    Pre-Earnings Momentum Strategy.
    
    Idea: Buy strong stocks 2-4 weeks before earnings if they're trending up
    and options imply high move; exit just before or right after the report.
    
    Rules:
    - Universe: Large, liquid stocks with upcoming earnings
    - Entry: 10-20 trading days before earnings
    - Stock is in uptrend (above 50 MA, rising RS)
    - Relative strength vs market is positive
    - Exit: 1-2 days before earnings OR hold through if conviction high
    
    This strategy captures the "pre-earnings run-up" effect.
    """
    
    STRATEGY_ID = "pre_earnings_momentum"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 100
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.03
    
    # Pre-earnings parameters
    days_before_earnings_min = 10  # Enter 10+ days before
    days_before_earnings_max = 20  # Enter within 20 days
    exit_days_before = 2           # Exit 2 days before earnings
    
    minimal_roi = {
        "0": 0.10,      # 10% anytime
        "10": 0.05,     # 5% after 10 days
        "15": 0.02,     # 2% after 15 days
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add pre-earnings indicators."""
        
        # Trend indicators
        dataframe['sma_20'] = IL.sma(dataframe['close'], 20)
        dataframe['sma_50'] = IL.sma(dataframe['close'], 50)
        dataframe['ema_10'] = IL.ema(dataframe['close'], 10)
        
        # Momentum
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        macd, signal, hist = IL.macd(dataframe['close'])
        dataframe['macd'] = macd
        dataframe['macd_signal'] = signal
        dataframe['macd_hist'] = hist
        
        # Trend strength
        dataframe['trend_score'] = IL.trend_strength_score(dataframe)
        dataframe['momentum_score'] = IL.momentum_score(dataframe)
        
        # Relative strength vs 20-day high
        dataframe['pct_from_20d_high'] = IL.pullback_depth(dataframe, 20)
        
        # Volume trend
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['relative_volume'] = IL.relative_volume(dataframe, 20)
        
        # ADX for trend confirmation
        adx, plus_di, minus_di = IL.adx(dataframe, 14)
        dataframe['adx'] = adx
        dataframe['plus_di'] = plus_di
        dataframe['minus_di'] = minus_di
        
        # Uptrend filter
        dataframe['in_uptrend'] = (
            (dataframe['close'] > dataframe['sma_50']) &
            (dataframe['sma_20'] > dataframe['sma_50']) &
            (dataframe['plus_di'] > dataframe['minus_di'])
        ).astype(int)
        
        # Momentum filter
        dataframe['momentum_rising'] = (
            (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1)) &
            (dataframe['rsi'] > 50) &
            (dataframe['rsi'] < 70)
        ).astype(int)
        
        # Near high (within 5% of recent high)
        dataframe['near_high'] = (dataframe['pct_from_20d_high'] < 5).astype(int)
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate pre-earnings entry signals."""
        
        # For live trading, you would check earnings calendar
        # Here we use technical conditions that tend to precede earnings runs
        
        entry_conditions = (
            (dataframe['in_uptrend'] == 1) &
            (dataframe['momentum_rising'] == 1) &
            (dataframe['near_high'] == 1) &
            (dataframe['trend_score'] >= 60) &        # Strong trend
            (dataframe['adx'] > 20) &                  # Trending, not ranging
            (dataframe['relative_volume'] > 0.8)       # Decent volume
        )
        
        dataframe.loc[entry_conditions, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate pre-earnings exit signals."""
        
        # Exit on momentum breakdown
        momentum_breakdown = (
            (dataframe['macd_hist'] < 0) &
            (dataframe['macd_hist'].shift(1) >= 0) &
            (dataframe['rsi'] < 50)
        )
        
        # Exit on trend break
        trend_break = (
            (dataframe['close'] < dataframe['sma_20']) &
            (dataframe['close'].shift(1) >= dataframe['sma_20'].shift(1))
        )
        
        dataframe.loc[momentum_breakdown | trend_break, 'exit_long'] = 1
        
        return dataframe


# ==============================================================================
# Strategy 2: Post-Earnings Drift (PEAD - 2-6 weeks after earnings)
# ==============================================================================

class PostEarningsDriftStrategy(IStrategy):
    """
    Post-Earnings Drift Strategy (PEAD).
    
    Idea: After an earnings surprise with big gap and volume, trade in the 
    direction of the gap for 2-6 weeks while the market "reprices" the stock.
    
    Academic research shows stocks continue drifting in the direction of 
    earnings surprises for 60+ days.
    
    Rules:
    - Only trade large, liquid names
    - Enter on first pullback after the gap
    - Stop inside the gap
    - Target 2-3R or fixed time (20 trading days)
    - Reduce position size because gaps can be violent
    """
    
    STRATEGY_ID = "post_earnings_drift"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 100
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.04
    can_short = True  # Can trade negative gaps too
    
    # PEAD parameters
    min_gap_pct = 3.0           # Minimum gap to qualify
    max_gap_pct = 15.0          # Maximum gap (too risky above)
    min_volume_ratio = 2.0       # At least 2x average volume on gap day
    pullback_entry_days = 5      # Enter on pullback within 5 days
    max_hold_days = 30           # 6 weeks max
    
    minimal_roi = {
        "0": 0.15,      # 15% anytime
        "15": 0.08,     # 8% after 15 days
        "30": 0.04,     # 4% after 30 days
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add post-earnings drift indicators."""
        
        # Gap detection
        dataframe['gap_pct'] = (
            (dataframe['open'] - dataframe['close'].shift(1)) / 
            dataframe['close'].shift(1) * 100
        )
        
        # Volume ratio
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Detect significant gaps (potential earnings reactions)
        dataframe['gap_up'] = (
            (dataframe['gap_pct'] >= self.min_gap_pct) &
            (dataframe['gap_pct'] <= self.max_gap_pct) &
            (dataframe['volume_ratio'] >= self.min_volume_ratio)
        ).astype(int)
        
        dataframe['gap_down'] = (
            (dataframe['gap_pct'] <= -self.min_gap_pct) &
            (dataframe['gap_pct'] >= -self.max_gap_pct) &
            (dataframe['volume_ratio'] >= self.min_volume_ratio)
        ).astype(int)
        
        # Track days since gap
        dataframe['days_since_gap_up'] = 0
        dataframe['days_since_gap_down'] = 0
        dataframe['gap_up_price'] = np.nan
        dataframe['gap_down_price'] = np.nan
        
        # Fill in days since gap and gap prices
        gap_up_price = np.nan
        gap_down_price = np.nan
        days_since_up = 999
        days_since_down = 999
        
        for i in range(len(dataframe)):
            if dataframe['gap_up'].iloc[i] == 1:
                days_since_up = 0
                gap_up_price = dataframe['open'].iloc[i]
            elif days_since_up < 999:
                days_since_up += 1
            
            if dataframe['gap_down'].iloc[i] == 1:
                days_since_down = 0
                gap_down_price = dataframe['open'].iloc[i]
            elif days_since_down < 999:
                days_since_down += 1
            
            dataframe.iloc[i, dataframe.columns.get_loc('days_since_gap_up')] = days_since_up
            dataframe.iloc[i, dataframe.columns.get_loc('days_since_gap_down')] = days_since_down
            dataframe.iloc[i, dataframe.columns.get_loc('gap_up_price')] = gap_up_price
            dataframe.iloc[i, dataframe.columns.get_loc('gap_down_price')] = gap_down_price
        
        # Moving averages
        dataframe['sma_10'] = IL.sma(dataframe['close'], 10)
        dataframe['sma_20'] = IL.sma(dataframe['close'], 20)
        dataframe['ema_10'] = IL.ema(dataframe['close'], 10)
        
        # RSI for pullback detection
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        
        # ATR for stops
        dataframe['atr'] = IL.atr(dataframe, 14)
        
        # Pullback from gap high/low
        dataframe['pullback_from_gap_high'] = 0.0
        dataframe['rally_from_gap_low'] = 0.0
        
        # For gap up: calculate pullback from post-gap high
        # For gap down: calculate rally from post-gap low
        for i in range(len(dataframe)):
            if 0 < dataframe['days_since_gap_up'].iloc[i] <= self.pullback_entry_days:
                # Find high since gap
                start_idx = max(0, i - dataframe['days_since_gap_up'].iloc[i])
                post_gap_high = dataframe['high'].iloc[start_idx:i+1].max()
                current = dataframe['close'].iloc[i]
                dataframe.iloc[i, dataframe.columns.get_loc('pullback_from_gap_high')] = (
                    (post_gap_high - current) / post_gap_high * 100
                )
            
            if 0 < dataframe['days_since_gap_down'].iloc[i] <= self.pullback_entry_days:
                start_idx = max(0, i - dataframe['days_since_gap_down'].iloc[i])
                post_gap_low = dataframe['low'].iloc[start_idx:i+1].min()
                current = dataframe['close'].iloc[i]
                dataframe.iloc[i, dataframe.columns.get_loc('rally_from_gap_low')] = (
                    (current - post_gap_low) / post_gap_low * 100
                )
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate post-earnings drift entry signals."""
        
        # === LONG: After gap up ===
        # Entry on first pullback within entry window
        long_conditions = (
            (dataframe['days_since_gap_up'] >= 1) &
            (dataframe['days_since_gap_up'] <= self.pullback_entry_days) &
            (dataframe['pullback_from_gap_high'] >= 2) &   # At least 2% pullback
            (dataframe['pullback_from_gap_high'] <= 6) &   # Not more than 6%
            (dataframe['close'] > dataframe['gap_up_price']) &  # Still above gap
            (dataframe['rsi'] < 60) &                      # Not overbought
            (dataframe['close'] > dataframe['sma_10'])     # Still uptrending
        )
        
        dataframe.loc[long_conditions, 'enter_long'] = 1
        
        # === SHORT: After gap down ===
        short_conditions = (
            (dataframe['days_since_gap_down'] >= 1) &
            (dataframe['days_since_gap_down'] <= self.pullback_entry_days) &
            (dataframe['rally_from_gap_low'] >= 2) &
            (dataframe['rally_from_gap_low'] <= 6) &
            (dataframe['close'] < dataframe['gap_down_price']) &
            (dataframe['rsi'] > 40) &
            (dataframe['close'] < dataframe['sma_10'])
        )
        
        dataframe.loc[short_conditions, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate post-earnings drift exit signals."""
        
        # === EXIT LONG ===
        # Gap filled (price back below gap open)
        gap_filled_long = (
            (dataframe['close'] < dataframe['gap_up_price']) &
            (dataframe['close'].shift(1) >= dataframe['gap_up_price'].shift(1))
        )
        
        # Momentum fading
        momentum_fade_long = (
            (dataframe['rsi'] > 70) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1))
        )
        
        dataframe.loc[gap_filled_long | momentum_fade_long, 'exit_long'] = 1
        
        # === EXIT SHORT ===
        gap_filled_short = (
            (dataframe['close'] > dataframe['gap_down_price']) &
            (dataframe['close'].shift(1) <= dataframe['gap_down_price'].shift(1))
        )
        
        momentum_fade_short = (
            (dataframe['rsi'] < 30) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1))
        )
        
        dataframe.loc[gap_filled_short | momentum_fade_short, 'exit_short'] = 1
        
        return dataframe


# ==============================================================================
# Strategy 3: Earnings Breakout (post-earnings base breakout)
# ==============================================================================

class EarningsBreakoutStrategy(IStrategy):
    """
    Earnings Breakout Strategy.
    
    Idea: After strong earnings, wait for the stock to consolidate and form
    a base, then trade the breakout to new highs.
    
    Rules:
    - Strong earnings reaction (gap up + high volume)
    - Stock consolidates for 5-15 days forming a base
    - Buy breakout to new highs above the consolidation
    - Stop below the consolidation low
    - Target 2R or trailing stop
    
    This is the "VCP after earnings" pattern.
    """
    
    STRATEGY_ID = "earnings_breakout"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 100
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.02
    
    # Earnings breakout parameters
    min_gap_pct = 3.0
    min_volume_ratio = 2.0
    consolidation_min_days = 5
    consolidation_max_days = 15
    max_consolidation_depth = 0.10  # Max 10% pullback in base
    
    minimal_roi = {
        "0": 0.12,      # 12% anytime
        "15": 0.06,     # 6% after 15 days
        "30": 0.03,     # 3% after 30 days
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add earnings breakout indicators."""
        
        # Gap detection
        dataframe['gap_pct'] = (
            (dataframe['open'] - dataframe['close'].shift(1)) / 
            dataframe['close'].shift(1) * 100
        )
        
        # Volume
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Earnings gap
        dataframe['earnings_gap'] = (
            (dataframe['gap_pct'] >= self.min_gap_pct) &
            (dataframe['volume_ratio'] >= self.min_volume_ratio)
        ).astype(int)
        
        # Track post-earnings high and consolidation
        dataframe['post_earnings_high'] = np.nan
        dataframe['consolidation_low'] = np.nan
        dataframe['days_since_earnings'] = 999
        dataframe['in_consolidation'] = 0
        
        post_earnings_high = np.nan
        consolidation_low = np.nan
        days_since = 999
        
        for i in range(len(dataframe)):
            if dataframe['earnings_gap'].iloc[i] == 1:
                days_since = 0
                post_earnings_high = dataframe['high'].iloc[i]
                consolidation_low = dataframe['low'].iloc[i]
            elif days_since < 999:
                days_since += 1
                # Update high if new high made
                if dataframe['high'].iloc[i] > post_earnings_high:
                    post_earnings_high = dataframe['high'].iloc[i]
                # Update low for consolidation
                if days_since > 1 and dataframe['low'].iloc[i] < consolidation_low:
                    consolidation_low = dataframe['low'].iloc[i]
            
            dataframe.iloc[i, dataframe.columns.get_loc('post_earnings_high')] = post_earnings_high
            dataframe.iloc[i, dataframe.columns.get_loc('consolidation_low')] = consolidation_low
            dataframe.iloc[i, dataframe.columns.get_loc('days_since_earnings')] = days_since
        
        # Consolidation depth
        dataframe['consolidation_depth'] = (
            (dataframe['post_earnings_high'] - dataframe['consolidation_low']) /
            dataframe['post_earnings_high']
        )
        
        # Is in valid consolidation?
        dataframe['in_consolidation'] = (
            (dataframe['days_since_earnings'] >= self.consolidation_min_days) &
            (dataframe['days_since_earnings'] <= self.consolidation_max_days) &
            (dataframe['consolidation_depth'] <= self.max_consolidation_depth) &
            (dataframe['consolidation_depth'] > 0.02)  # At least some pullback
        ).astype(int)
        
        # Volatility contraction in base
        dataframe['atr'] = IL.atr(dataframe, 14)
        dataframe['atr_5'] = IL.atr(dataframe, 5)
        dataframe['volatility_contracting'] = (
            dataframe['atr_5'] < dataframe['atr'] * 0.9
        ).astype(int)
        
        # Volume drying up
        dataframe['volume_drying'] = (
            dataframe['volume'] < dataframe['volume_sma'] * 0.7
        ).astype(int)
        
        # Breakout detection
        dataframe['breakout'] = (
            (dataframe['close'] > dataframe['post_earnings_high']) &
            (dataframe['close'].shift(1) <= dataframe['post_earnings_high'].shift(1)) &
            (dataframe['volume_ratio'] > 1.2)  # Volume on breakout
        ).astype(int)
        
        # RSI
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        
        # Trend
        dataframe['sma_20'] = IL.sma(dataframe['close'], 20)
        dataframe['above_sma20'] = (dataframe['close'] > dataframe['sma_20']).astype(int)
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate earnings breakout entry signals."""
        
        # Entry conditions:
        # 1. Was in valid consolidation
        # 2. Breaking out above post-earnings high
        # 3. Volume confirmation
        # 4. Volatility was contracting (base was tight)
        
        entry_conditions = (
            (dataframe['in_consolidation'].shift(1) == 1) &  # Was consolidating
            (dataframe['breakout'] == 1) &                    # Breaking out
            (dataframe['volatility_contracting'].shift(1) == 1) &  # Tight base
            (dataframe['above_sma20'] == 1) &                 # Uptrending
            (dataframe['rsi'] < 75)                           # Not too extended
        )
        
        dataframe.loc[entry_conditions, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate earnings breakout exit signals."""
        
        # Failed breakout (back below breakout level)
        failed_breakout = (
            (dataframe['close'] < dataframe['post_earnings_high']) &
            (dataframe['close'].shift(1) >= dataframe['post_earnings_high'].shift(1))
        )
        
        # RSI overextended
        overextended = (
            (dataframe['rsi'] > 80) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1))
        )
        
        dataframe.loc[failed_breakout | overextended, 'exit_long'] = 1
        
        return dataframe


# ==============================================================================
# Strategy Registry
# ==============================================================================

EARNINGS_STRATEGIES = {
    'pre_earnings_momentum': PreEarningsMomentumStrategy,
    'post_earnings_drift': PostEarningsDriftStrategy,
    'earnings_breakout': EarningsBreakoutStrategy,
}


def get_earnings_strategy(strategy_id: str) -> IStrategy:
    """Get an earnings trading strategy by ID."""
    if strategy_id not in EARNINGS_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}. Available: {list(EARNINGS_STRATEGIES.keys())}")
    return EARNINGS_STRATEGIES[strategy_id]()


def list_earnings_strategies() -> List[str]:
    """List all available earnings trading strategies."""
    return list(EARNINGS_STRATEGIES.keys())


# ==============================================================================
# Earnings Calendar Integration (placeholder for future implementation)
# ==============================================================================

class EarningsCalendar:
    """
    Earnings calendar integration for event-based trading.
    
    In production, this would connect to:
    - Polygon.io
    - Financial Modeling Prep
    - Yahoo Finance
    - Alpha Vantage
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
        # Cache of upcoming earnings
        self._earnings_cache: Dict[str, EarningsEvent] = {}
    
    def get_upcoming_earnings(
        self,
        tickers: List[str],
        days_ahead: int = 30
    ) -> Dict[str, EarningsEvent]:
        """
        Get upcoming earnings for a list of tickers.
        
        Returns dict of ticker -> EarningsEvent
        """
        # Placeholder - would call API in production
        self.logger.info(f"Would fetch earnings for {len(tickers)} tickers, {days_ahead} days ahead")
        return {}
    
    def get_recent_earnings(
        self,
        tickers: List[str],
        days_back: int = 30
    ) -> Dict[str, EarningsEvent]:
        """
        Get recent earnings for a list of tickers.
        
        Returns dict of ticker -> EarningsEvent
        """
        # Placeholder - would call API in production
        self.logger.info(f"Would fetch recent earnings for {len(tickers)} tickers, {days_back} days back")
        return {}
    
    def get_earnings_date(self, ticker: str) -> Optional[datetime]:
        """Get next earnings date for a ticker."""
        if ticker in self._earnings_cache:
            return self._earnings_cache[ticker].earnings_date
        return None
    
    def days_until_earnings(self, ticker: str) -> Optional[int]:
        """Get days until next earnings for a ticker."""
        earnings_date = self.get_earnings_date(ticker)
        if earnings_date:
            return (earnings_date - datetime.now()).days
        return None
