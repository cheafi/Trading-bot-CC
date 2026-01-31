"""
TradingAI Bot - Short-Term Swing Trading Strategies

Comprehensive swing trading framework for 2 days to 8 weeks holding periods.

Strategies included:
1. ShortTermTrendFollowingStrategy - Ride existing trends for 2-8 weeks
2. ClassicSwingStrategy - Capture swings from support to resistance (2-4 weeks)
3. MomentumRotationStrategy - Rotate into strongest stocks (1-8 weeks)
4. ShortTermMeanReversionStrategy - Bet on sharp moves reverting (days to 2-3 weeks)

Key indicators used:
- Moving Averages (SMA/EMA): 10, 20, 50, 200-day for trend
- RSI: Momentum and overbought/oversold
- MACD: Trend confirmation
- Bollinger Bands: Volatility and extremes
- Volume/OBV: Move confirmation
- Stochastic: Short-term momentum
- ATR: Stop/target placement
- Fibonacci: Pullback levels
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
import logging

from .base_strategy import IStrategy, StrategyConfig, StrategyMode, TimeFrame
from .indicators import IndicatorLibrary as IL

logger = logging.getLogger(__name__)


class SwingStyle(str, Enum):
    """Swing trading style preference."""
    TREND_PULLBACK = "trend_pullback"       # Buy dips in uptrends
    BREAKOUT = "breakout"                    # Buy breakouts from consolidation
    MEAN_REVERSION = "mean_reversion"        # Buy oversold, sell overbought
    MOMENTUM = "momentum"                     # Buy strongest, sell weakest


@dataclass
class SwingTradeConfig:
    """Configuration specific to swing trading."""
    
    # Holding period limits
    min_hold_days: int = 3              # Minimum days to hold
    max_hold_days: int = 40             # Maximum days (2 months = 40 trading days)
    
    # Risk management per trade
    risk_per_trade_pct: float = 1.0     # Risk 1% of capital per trade
    max_open_positions: int = 5
    max_sector_exposure: float = 0.40   # Max 40% in one sector
    
    # Profit targets
    reward_risk_ratio: float = 2.0      # Target 2:1 R/R minimum
    profit_target_pct: Optional[float] = None  # Optional fixed target
    
    # Stop loss
    use_atr_stop: bool = True
    atr_stop_multiplier: float = 2.0    # 2x ATR stop
    fixed_stop_pct: float = 0.05        # 5% fixed stop if not using ATR
    
    # Trailing stop
    use_trailing_stop: bool = True
    trailing_activation_pct: float = 0.03  # Activate at 3% profit
    trailing_distance_pct: float = 0.02    # Trail by 2%
    
    # Volume requirements
    min_relative_volume: float = 0.5    # At least 50% of average volume
    volume_confirmation: bool = True     # Require volume on entry
    
    # Entry timing
    entry_on_pullback: bool = True      # Wait for pullback vs breakout
    pullback_days_min: int = 2          # Minimum pullback length
    pullback_days_max: int = 7          # Maximum pullback length


# ==============================================================================
# Strategy 1: Short-Term Trend Following (2-8 weeks)
# ==============================================================================

class ShortTermTrendFollowingStrategy(IStrategy):
    """
    Short-Term Trend Following Strategy.
    
    Idea: Ride a move that's already started in a strong stock for 2-8 weeks,
    then exit before bigger trend risk hits.
    
    Setup:
    - Universe: Liquid US large/mid caps or ETFs
    - Trend filter: Price above 50-day MA, 50-day above 200-day
    - Entry: Buy after 3-7 day pullback that holds above 50-day MA,
             shows bullish reversal candle or breaks back above 10-20 day MA
    - Exit: 
        - Time-based: Close after 10-40 trading days
        - Price-based: Target 2-3R or exit if closes below 50-day MA
    - Risk: 0.5-1% of capital per position
    """
    
    STRATEGY_ID = "short_term_trend_following"
    VERSION = "1.0"
    
    # Strategy parameters
    timeframe = TimeFrame.D1
    startup_candle_count = 200
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.02
    
    # Trend parameters
    ma_short = 10
    ma_medium = 20
    ma_long = 50
    ma_trend = 200
    
    # Pullback parameters
    pullback_min_days = 3
    pullback_max_days = 7
    
    # Time-based exit
    min_hold_days = 10
    max_hold_days = 40
    
    # ROI targets
    minimal_roi = {
        "0": 0.15,      # 15% anytime
        "20": 0.08,     # 8% after 20 days
        "40": 0.03,     # 3% after 40 days (max hold)
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add trend and pullback indicators."""
        
        # Moving averages for trend
        dataframe['sma_10'] = IL.sma(dataframe['close'], self.ma_short)
        dataframe['sma_20'] = IL.sma(dataframe['close'], self.ma_medium)
        dataframe['sma_50'] = IL.sma(dataframe['close'], self.ma_long)
        dataframe['sma_200'] = IL.sma(dataframe['close'], self.ma_trend)
        dataframe['ema_20'] = IL.ema(dataframe['close'], self.ma_medium)
        
        # Pullback detection
        dataframe['pullback_days'] = IL.pullback_days(dataframe)
        dataframe['pullback_depth'] = IL.pullback_depth(dataframe, lookback=20)
        
        # Bullish reversal patterns
        dataframe['bullish_reversal'] = IL.is_bullish_reversal(dataframe)
        dataframe['hammer'] = IL.is_hammer(dataframe)
        dataframe['engulfing'] = IL.is_bullish_engulfing(dataframe)
        
        # Momentum confirmation
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        macd, signal, hist = IL.macd(dataframe['close'])
        dataframe['macd'] = macd
        dataframe['macd_signal'] = signal
        dataframe['macd_hist'] = hist
        dataframe['macd_cross_up'] = (
            (dataframe['macd'] > dataframe['macd_signal']) & 
            (dataframe['macd'].shift(1) <= dataframe['macd_signal'].shift(1))
        ).astype(int)
        
        # ATR for stops
        dataframe['atr'] = IL.atr(dataframe, 14)
        
        # Volume confirmation
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['relative_volume'] = IL.relative_volume(dataframe, 20)
        
        # Trend strength
        dataframe['trend_score'] = IL.trend_strength_score(dataframe)
        adx, plus_di, minus_di = IL.adx(dataframe, 14)
        dataframe['adx'] = adx
        dataframe['plus_di'] = plus_di
        dataframe['minus_di'] = minus_di
        
        # MA break condition
        dataframe['breaks_above_ema20'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['close'].shift(1) <= dataframe['ema_20'].shift(1))
        ).astype(int)
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate entry signals for trend pullback."""
        
        # Uptrend conditions (primary filter)
        uptrend = (
            (dataframe['close'] > dataframe['sma_50']) &      # Price above 50 MA
            (dataframe['sma_50'] > dataframe['sma_200']) &    # 50 MA above 200 MA
            (dataframe['sma_20'] > dataframe['sma_50']) &     # 20 MA above 50 MA
            (dataframe['adx'] > 20)                            # Trending (not ranging)
        )
        
        # Pullback conditions
        valid_pullback = (
            (dataframe['pullback_days'] >= self.pullback_min_days) &
            (dataframe['pullback_days'] <= self.pullback_max_days) &
            (dataframe['close'] > dataframe['sma_50'])  # Still above 50 MA
        )
        
        # Entry triggers
        reversal_trigger = (
            dataframe['bullish_reversal'] == 1
        )
        
        breakout_trigger = (
            dataframe['breaks_above_ema20'] == 1
        )
        
        # RSI coming out of oversold area (but not too oversold for uptrend)
        rsi_trigger = (
            (dataframe['rsi'] > 30) &
            (dataframe['rsi'] < 50) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1))  # RSI rising
        )
        
        # Volume confirmation (not required but helps)
        volume_ok = dataframe['relative_volume'] > 0.5
        
        # Combined entry signal
        dataframe.loc[
            uptrend & valid_pullback & 
            (reversal_trigger | breakout_trigger | rsi_trigger) &
            volume_ok,
            'enter_long'
        ] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate exit signals."""
        
        # Price-based exit: Close below 50 MA
        trend_break = (
            (dataframe['close'] < dataframe['sma_50']) &
            (dataframe['close'].shift(1) >= dataframe['sma_50'].shift(1))
        )
        
        # Momentum exhaustion
        momentum_exhaustion = (
            (dataframe['rsi'] > 70) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1)) &  # RSI turning down
            (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1))  # MACD weakening
        )
        
        # MACD bearish cross
        macd_cross_down = (
            (dataframe['macd'] < dataframe['macd_signal']) &
            (dataframe['macd'].shift(1) >= dataframe['macd_signal'].shift(1))
        )
        
        # Combined exit signal
        dataframe.loc[
            trend_break | (momentum_exhaustion & macd_cross_down),
            'exit_long'
        ] = 1
        
        return dataframe


# ==============================================================================
# Strategy 2: Classic Swing Trading (2 days to 4 weeks)
# ==============================================================================

class ClassicSwingStrategy(IStrategy):
    """
    Classic Swing Trading Strategy.
    
    Idea: Capture one "swing" from support to resistance in a trend.
    
    Bullish Swing:
    - Identify stock in uptrend on daily chart
    - Wait for pullback to support (prior swing low, 20 MA, lower BB)
    - Entry trigger: Bullish reversal + RSI coming out of oversold
    - Stop: Just below support/swing low
    - Target: Previous swing high or 2R
    - Hold: 3-15 trading days, <1 month
    """
    
    STRATEGY_ID = "classic_swing"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 100
    stoploss = -0.03
    trailing_stop = True
    can_short = True  # Allow short swings
    
    minimal_roi = {
        "0": 0.10,      # 10% anytime
        "15": 0.05,     # 5% after 15 days
        "25": 0.02,     # 2% after 25 days
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add swing trading indicators."""
        
        # Moving averages
        dataframe['sma_20'] = IL.sma(dataframe['close'], 20)
        dataframe['sma_50'] = IL.sma(dataframe['close'], 50)
        dataframe['ema_10'] = IL.ema(dataframe['close'], 10)
        
        # Bollinger Bands for support/resistance
        bb_upper, bb_middle, bb_lower = IL.bollinger_bands(dataframe['close'], 20, 2.0)
        dataframe['bb_upper'] = bb_upper
        dataframe['bb_middle'] = bb_middle
        dataframe['bb_lower'] = bb_lower
        dataframe['bb_width'] = IL.bollinger_bandwidth(dataframe['close'], 20)
        
        # Swing highs/lows
        swing_highs, swing_lows = IL.swing_highs_lows(dataframe, swing_period=5)
        dataframe['swing_high'] = swing_highs
        dataframe['swing_low'] = swing_lows
        
        # Fill swing levels (last known swing)
        dataframe['last_swing_high'] = dataframe['swing_high'].ffill()
        dataframe['last_swing_low'] = dataframe['swing_low'].ffill()
        
        # RSI for momentum
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        dataframe['rsi_oversold'] = (dataframe['rsi'] < 30).astype(int)
        dataframe['rsi_overbought'] = (dataframe['rsi'] > 70).astype(int)
        dataframe['rsi_rising'] = (dataframe['rsi'] > dataframe['rsi'].shift(1)).astype(int)
        dataframe['rsi_falling'] = (dataframe['rsi'] < dataframe['rsi'].shift(1)).astype(int)
        
        # Stochastic for oversold/overbought
        stoch_k, stoch_d = IL.stochastic(dataframe, 14, 3)
        dataframe['stoch_k'] = stoch_k
        dataframe['stoch_d'] = stoch_d
        dataframe['stoch_cross_up'] = (
            (stoch_k > stoch_d) & (stoch_k.shift(1) <= stoch_d.shift(1)) &
            (stoch_k < 30)  # Cross up from oversold
        ).astype(int)
        dataframe['stoch_cross_down'] = (
            (stoch_k < stoch_d) & (stoch_k.shift(1) >= stoch_d.shift(1)) &
            (stoch_k > 70)  # Cross down from overbought
        ).astype(int)
        
        # Candlestick patterns
        dataframe['bullish_reversal'] = IL.is_bullish_reversal(dataframe)
        dataframe['hammer'] = IL.is_hammer(dataframe)
        
        # ATR for stops
        dataframe['atr'] = IL.atr(dataframe, 14)
        
        # Volume
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['volume_spike'] = IL.volume_breakout(dataframe, threshold=1.5)
        
        # Trend direction
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['sma_50']) &
            (dataframe['sma_20'] > dataframe['sma_50'])
        ).astype(int)
        
        dataframe['downtrend'] = (
            (dataframe['close'] < dataframe['sma_50']) &
            (dataframe['sma_20'] < dataframe['sma_50'])
        ).astype(int)
        
        # Distance from support/resistance
        dataframe['near_support'] = (
            (dataframe['close'] <= dataframe['bb_lower'] * 1.02) |
            (dataframe['close'] <= dataframe['last_swing_low'] * 1.02)
        ).astype(int)
        
        dataframe['near_resistance'] = (
            (dataframe['close'] >= dataframe['bb_upper'] * 0.98) |
            (dataframe['close'] >= dataframe['last_swing_high'] * 0.98)
        ).astype(int)
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate swing entry signals."""
        
        # === LONG SWING ===
        # Condition: Uptrend + pullback to support + reversal signal
        long_conditions = (
            (dataframe['uptrend'] == 1) &
            (dataframe['near_support'] == 1) &
            (
                (dataframe['rsi'] < 40) |  # Oversold or approaching
                (dataframe['stoch_k'] < 30)
            ) &
            (
                (dataframe['bullish_reversal'] == 1) |
                (dataframe['stoch_cross_up'] == 1) |
                (dataframe['rsi_rising'] == 1)
            )
        )
        
        dataframe.loc[long_conditions, 'enter_long'] = 1
        
        # === SHORT SWING ===
        # Condition: Downtrend + rally to resistance + reversal signal
        short_conditions = (
            (dataframe['downtrend'] == 1) &
            (dataframe['near_resistance'] == 1) &
            (
                (dataframe['rsi'] > 60) |
                (dataframe['stoch_k'] > 70)
            ) &
            (
                (dataframe['stoch_cross_down'] == 1) |
                (dataframe['rsi_falling'] == 1)
            )
        )
        
        dataframe.loc[short_conditions, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate swing exit signals."""
        
        # === EXIT LONG ===
        # At resistance OR momentum fading
        exit_long_conditions = (
            (dataframe['near_resistance'] == 1) |
            (
                (dataframe['rsi'] > 70) &
                (dataframe['rsi_falling'] == 1)
            ) |
            (dataframe['stoch_cross_down'] == 1)
        )
        
        dataframe.loc[exit_long_conditions, 'exit_long'] = 1
        
        # === EXIT SHORT ===
        # At support OR momentum fading
        exit_short_conditions = (
            (dataframe['near_support'] == 1) |
            (
                (dataframe['rsi'] < 30) &
                (dataframe['rsi_rising'] == 1)
            ) |
            (dataframe['stoch_cross_up'] == 1)
        )
        
        dataframe.loc[exit_short_conditions, 'exit_short'] = 1
        
        return dataframe


# ==============================================================================
# Strategy 3: Short-Term Momentum Rotation (1-8 weeks)
# ==============================================================================

class MomentumRotationStrategy(IStrategy):
    """
    Short-Term Momentum Rotation Strategy.
    
    Idea: Rotate into the strongest stocks/ETFs for several weeks at a time.
    
    Rules:
    - Weekly: Rank basket by 4-8 week performance + price vs MAs
    - Buy top 5-10 names meeting filters (liquid, not extremely extended)
    - Hold 2-8 weeks unless:
        - Break trailing stop (close below 20 MA), or
        - Drop out of top momentum ranks
    
    This is systematic momentum investing compressed to 1-2 months.
    """
    
    STRATEGY_ID = "momentum_rotation"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 150
    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.05
    trailing_stop_positive_offset = 0.03
    
    # Momentum parameters
    momentum_lookback_short = 20   # 4 weeks
    momentum_lookback_long = 40    # 8 weeks
    top_percentile = 0.20          # Top 20% momentum
    rebalance_period_days = 5      # Weekly rebalance
    
    minimal_roi = {
        "0": 0.20,      # 20% anytime
        "30": 0.10,     # 10% after 30 days
        "40": 0.05,     # 5% after 40 days
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add momentum ranking indicators."""
        
        # Moving averages
        dataframe['sma_10'] = IL.sma(dataframe['close'], 10)
        dataframe['sma_20'] = IL.sma(dataframe['close'], 20)
        dataframe['sma_50'] = IL.sma(dataframe['close'], 50)
        dataframe['ema_20'] = IL.ema(dataframe['close'], 20)
        
        # Momentum metrics
        dataframe['mom_4w'] = dataframe['close'].pct_change(self.momentum_lookback_short) * 100
        dataframe['mom_8w'] = dataframe['close'].pct_change(self.momentum_lookback_long) * 100
        dataframe['mom_12w'] = dataframe['close'].pct_change(60) * 100
        
        # Combined momentum score (weight recent more)
        dataframe['momentum_score'] = IL.momentum_score(dataframe)
        
        # Trend alignment score
        dataframe['trend_score'] = IL.trend_strength_score(dataframe)
        
        # Combined ranking score
        dataframe['rank_score'] = (
            dataframe['momentum_score'] * 0.6 +  # 60% momentum
            dataframe['trend_score'] * 0.4       # 40% trend alignment
        )
        
        # Price vs MAs (filter)
        dataframe['above_all_mas'] = (
            (dataframe['close'] > dataframe['sma_10']) &
            (dataframe['close'] > dataframe['sma_20']) &
            (dataframe['close'] > dataframe['sma_50'])
        ).astype(int)
        
        # Not too extended (within 10% of 20 MA)
        dataframe['pct_from_sma20'] = (dataframe['close'] - dataframe['sma_20']) / dataframe['sma_20'] * 100
        dataframe['not_extended'] = (dataframe['pct_from_sma20'] < 10).astype(int)
        
        # RSI not overbought
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        dataframe['rsi_ok'] = (dataframe['rsi'] < 75).astype(int)
        
        # Volume
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['volume_ok'] = (dataframe['volume'] > dataframe['volume_sma'] * 0.5).astype(int)
        
        # ADX for trend confirmation
        adx, plus_di, minus_di = IL.adx(dataframe, 14)
        dataframe['adx'] = adx
        
        # Weekly rebalance flag (every 5 trading days)
        dataframe['day_count'] = range(len(dataframe))
        dataframe['is_rebalance_day'] = (dataframe['day_count'] % self.rebalance_period_days == 0).astype(int)
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate momentum rotation entries."""
        
        # Entry conditions
        high_momentum = dataframe['momentum_score'] > dataframe['momentum_score'].rolling(50).quantile(0.80)
        
        basic_filters = (
            (dataframe['above_all_mas'] == 1) &
            (dataframe['not_extended'] == 1) &
            (dataframe['rsi_ok'] == 1) &
            (dataframe['volume_ok'] == 1)
        )
        
        trending = dataframe['adx'] > 20
        
        # Enter on rebalance days when conditions met
        entry_conditions = (
            high_momentum &
            basic_filters &
            trending &
            (dataframe['is_rebalance_day'] == 1)
        )
        
        dataframe.loc[entry_conditions, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate momentum rotation exits."""
        
        # Exit 1: Close below 20 MA (trailing stop)
        close_below_20ma = (
            (dataframe['close'] < dataframe['sma_20']) &
            (dataframe['close'].shift(1) >= dataframe['sma_20'].shift(1))
        )
        
        # Exit 2: Momentum deteriorating significantly
        momentum_weak = (
            (dataframe['momentum_score'] < dataframe['momentum_score'].rolling(50).quantile(0.40)) &
            (dataframe['momentum_score'] < dataframe['momentum_score'].shift(5))  # Getting weaker
        )
        
        # Exit 3: Trend break
        trend_break = (
            (dataframe['close'] < dataframe['sma_50']) &
            (dataframe['close'].shift(1) >= dataframe['sma_50'].shift(1))
        )
        
        # Exit on rebalance days if momentum drops
        exit_on_rebalance = (
            (dataframe['is_rebalance_day'] == 1) &
            momentum_weak
        )
        
        dataframe.loc[
            close_below_20ma | trend_break | exit_on_rebalance,
            'exit_long'
        ] = 1
        
        return dataframe


# ==============================================================================
# Strategy 4: Short-Term Mean Reversion (days to 2-3 weeks)
# ==============================================================================

class ShortTermMeanReversionStrategy(IStrategy):
    """
    Short-Term Mean Reversion Strategy.
    
    Idea: Bet that sharp, emotional moves revert toward the recent average.
    
    Rules:
    - Scan for stocks with strong long-term uptrend (above 200 MA)
    - That fell 3-5 days in a row, down 6-12% from recent high
    - RSI < 30 (oversold), positive intraday reversal
    - Buy near low of setup day or next open
    - Exit on:
        - Return to 10-20 MA
        - 1-2R profit
        - Max 10-12 trading days
    
    Very time-bounded, fits perfectly in <2 months.
    """
    
    STRATEGY_ID = "short_term_mean_reversion"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 200
    stoploss = -0.06
    trailing_stop = False  # Fixed target for mean reversion
    
    # Mean reversion parameters
    min_down_days = 3
    max_down_days = 5
    min_drawdown_pct = 6.0
    max_drawdown_pct = 12.0
    max_hold_days = 12
    
    minimal_roi = {
        "0": 0.08,       # 8% anytime
        "5": 0.05,       # 5% after 5 days
        "10": 0.02,      # 2% after 10 days
        "12": 0.0,       # Close at breakeven after 12 days
    }
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add mean reversion indicators."""
        
        # Long-term trend (must be in uptrend)
        dataframe['sma_200'] = IL.sma(dataframe['close'], 200)
        dataframe['sma_50'] = IL.sma(dataframe['close'], 50)
        dataframe['sma_20'] = IL.sma(dataframe['close'], 20)
        dataframe['sma_10'] = IL.sma(dataframe['close'], 10)
        
        # Pullback metrics
        dataframe['pullback_days'] = IL.pullback_days(dataframe)
        dataframe['pullback_depth'] = IL.pullback_depth(dataframe, lookback=20)
        
        # RSI for oversold
        dataframe['rsi'] = IL.rsi(dataframe['close'], 14)
        dataframe['rsi_2'] = IL.rsi(dataframe['close'], 2)  # Short-term RSI
        
        # Stochastic for extreme oversold
        stoch_k, stoch_d = IL.stochastic(dataframe, 14, 3)
        dataframe['stoch_k'] = stoch_k
        dataframe['stoch_d'] = stoch_d
        
        # Bollinger Bands for extreme moves
        bb_upper, bb_middle, bb_lower = IL.bollinger_bands(dataframe['close'], 20, 2.0)
        dataframe['bb_upper'] = bb_upper
        dataframe['bb_middle'] = bb_middle
        dataframe['bb_lower'] = bb_lower
        dataframe['below_bb_lower'] = (dataframe['close'] < bb_lower).astype(int)
        
        # Candlestick patterns
        dataframe['bullish_reversal'] = IL.is_bullish_reversal(dataframe)
        dataframe['hammer'] = IL.is_hammer(dataframe)
        dataframe['doji'] = IL.is_doji(dataframe)
        
        # ATR for volatility
        dataframe['atr'] = IL.atr(dataframe, 14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100
        
        # Volume spike on selloff (capitulation)
        dataframe['volume_sma'] = IL.volume_sma(dataframe, 20)
        dataframe['relative_volume'] = IL.relative_volume(dataframe, 20)
        dataframe['high_volume'] = (dataframe['relative_volume'] > 1.5).astype(int)
        
        # Distance from mean
        dataframe['pct_from_sma10'] = (dataframe['close'] - dataframe['sma_10']) / dataframe['sma_10'] * 100
        dataframe['pct_from_sma20'] = (dataframe['close'] - dataframe['sma_20']) / dataframe['sma_20'] * 100
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate mean reversion entry signals."""
        
        # 1. Long-term uptrend (required filter)
        in_uptrend = (
            (dataframe['close'] > dataframe['sma_200']) &
            (dataframe['sma_50'] > dataframe['sma_200'])
        )
        
        # 2. Sharp selloff (3-5 consecutive down days)
        valid_selloff = (
            (dataframe['pullback_days'] >= self.min_down_days) &
            (dataframe['pullback_days'] <= self.max_down_days)
        )
        
        # 3. Drawdown in target range (6-12%)
        valid_drawdown = (
            (dataframe['pullback_depth'] >= self.min_drawdown_pct) &
            (dataframe['pullback_depth'] <= self.max_drawdown_pct)
        )
        
        # 4. Oversold condition
        oversold = (
            (dataframe['rsi'] < 30) |
            (dataframe['rsi_2'] < 10) |
            (dataframe['stoch_k'] < 20) |
            (dataframe['below_bb_lower'] == 1)
        )
        
        # 5. Reversal signal (bullish candle)
        reversal_signal = (
            (dataframe['bullish_reversal'] == 1) |
            (dataframe['hammer'] == 1) |
            (
                (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
                (dataframe['close'] > dataframe['open'])  # Green candle
            )
        )
        
        # Combined entry
        entry_conditions = (
            in_uptrend &
            valid_selloff &
            valid_drawdown &
            oversold &
            reversal_signal
        )
        
        dataframe.loc[entry_conditions, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate mean reversion exit signals."""
        
        # Exit 1: Price returns to 10-20 MA (mean reversion complete)
        back_to_mean = (
            (dataframe['close'] >= dataframe['sma_10']) &
            (dataframe['close'].shift(1) < dataframe['sma_10'].shift(1))
        )
        
        # Exit 2: Price returns to 20 MA
        back_to_sma20 = (
            (dataframe['close'] >= dataframe['sma_20']) &
            (dataframe['close'].shift(1) < dataframe['sma_20'].shift(1))
        )
        
        # Exit 3: RSI no longer oversold
        rsi_normalized = (
            (dataframe['rsi'] > 50) &
            (dataframe['rsi'].shift(1) <= 50)
        )
        
        # Exit 4: Momentum reversal complete (back to middle BB)
        back_to_bb_middle = (
            (dataframe['close'] >= dataframe['bb_middle']) &
            (dataframe['close'].shift(1) < dataframe['bb_middle'].shift(1))
        )
        
        # Combined exit
        dataframe.loc[
            back_to_mean | back_to_sma20 | rsi_normalized | back_to_bb_middle,
            'exit_long'
        ] = 1
        
        return dataframe


# ==============================================================================
# Strategy Registry - Register all swing strategies
# ==============================================================================

SWING_STRATEGIES = {
    'short_term_trend_following': ShortTermTrendFollowingStrategy,
    'classic_swing': ClassicSwingStrategy,
    'momentum_rotation': MomentumRotationStrategy,
    'short_term_mean_reversion': ShortTermMeanReversionStrategy,
}


def get_swing_strategy(strategy_id: str) -> IStrategy:
    """Get a swing trading strategy by ID."""
    if strategy_id not in SWING_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}. Available: {list(SWING_STRATEGIES.keys())}")
    return SWING_STRATEGIES[strategy_id]()


def list_swing_strategies() -> List[str]:
    """List all available swing trading strategies."""
    return list(SWING_STRATEGIES.keys())
