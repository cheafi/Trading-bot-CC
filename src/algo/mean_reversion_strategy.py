"""
TradingAI Bot - Mean Reversion Strategy

Looks for oversold conditions with reversal signals.

This strategy looks for:
1. Oversold RSI with bullish divergence
2. Price at lower Bollinger Band
3. Stochastic oversold and crossing up
4. Volume spike on reversal candle
5. Support level confluence
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from .base_strategy import IStrategy, StrategyConfig, TimeFrame
from .indicators import IndicatorLibrary


class MeanReversionStrategy(IStrategy):
    """
    Mean Reversion Strategy.
    
    Trades bounces from oversold conditions back to mean.
    
    Entry Criteria:
    - RSI < 30 (oversold)
    - Price at or below lower Bollinger Band
    - Stochastic K crossing above D from oversold
    - Hammer or bullish engulfing candle
    - Volume above average
    
    Exit Criteria:
    - RSI > 60 (approaching overbought)
    - Price reaches middle Bollinger Band
    - Profit target hit
    """
    
    STRATEGY_ID = "mean_reversion"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 30
    
    stoploss = -0.04  # Tighter stop for mean reversion
    trailing_stop = False  # Take profits at target
    
    minimal_roi = {
        "0": 0.10,    # 10% anytime (target upper BB, not just middle)
        "5": 0.06,    # 6% after 5 days
        "10": 0.04,   # 4% after 10 days
        "20": 0.02    # 2% after 20 days
    }
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        
        params = getattr(config, 'parameters', {}) if config else {}
        
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_exit = params.get('rsi_exit', 60)
        self.stoch_oversold = params.get('stoch_oversold', 20)
        self.bb_period = params.get('bb_period', 20)
        self.bb_std = params.get('bb_std', 2.0)
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add mean reversion indicators."""
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = IndicatorLibrary.bollinger_bands(
            dataframe['close'], self.bb_period, self.bb_std
        )
        dataframe['bb_upper'] = bb_upper
        dataframe['bb_middle'] = bb_middle
        dataframe['bb_lower'] = bb_lower
        dataframe['bb_width'] = IndicatorLibrary.bollinger_bandwidth(
            dataframe['close'], self.bb_period
        )
        
        # RSI
        dataframe['rsi'] = IndicatorLibrary.rsi(dataframe['close'], 14)
        
        # Stochastic
        stoch_k, stoch_d = IndicatorLibrary.stochastic(dataframe, 14, 3)
        dataframe['stoch_k'] = stoch_k
        dataframe['stoch_d'] = stoch_d
        dataframe['stoch_cross_up'] = (
            (dataframe['stoch_k'] > dataframe['stoch_d']) &
            (dataframe['stoch_k'].shift(1) <= dataframe['stoch_d'].shift(1))
        )
        
        # CCI
        dataframe['cci'] = IndicatorLibrary.cci(dataframe, 20)
        
        # Williams %R
        dataframe['williams_r'] = IndicatorLibrary.williams_r(dataframe, 14)
        
        # Volume
        dataframe['vol_sma'] = IndicatorLibrary.volume_sma(dataframe, 20)
        dataframe['rel_volume'] = dataframe['volume'] / dataframe['vol_sma']
        
        # Candlestick patterns
        dataframe['body'] = abs(dataframe['close'] - dataframe['open'])
        dataframe['upper_wick'] = dataframe['high'] - dataframe[['close', 'open']].max(axis=1)
        dataframe['lower_wick'] = dataframe[['close', 'open']].min(axis=1) - dataframe['low']
        
        # Hammer pattern
        dataframe['hammer'] = (
            (dataframe['lower_wick'] > 2 * dataframe['body']) &
            (dataframe['upper_wick'] < dataframe['body'] * 0.5) &
            (dataframe['close'] > dataframe['open'])  # Bullish
        )
        
        # Bullish engulfing
        dataframe['engulfing_bullish'] = (
            (dataframe['close'].shift(1) < dataframe['open'].shift(1)) &  # Prev bearish
            (dataframe['close'] > dataframe['open']) &  # Current bullish
            (dataframe['open'] < dataframe['close'].shift(1)) &  # Open below prev close
            (dataframe['close'] > dataframe['open'].shift(1))  # Close above prev open
        )
        
        # Distance from lower band
        dataframe['dist_from_lower_bb'] = (
            (dataframe['close'] - dataframe['bb_lower']) / dataframe['close']
        )
        
        # SMA 200 as regime filter (only mean-revert in uptrends)
        dataframe['sma_200'] = IndicatorLibrary.sma(dataframe['close'], 200)
        dataframe['in_uptrend'] = dataframe['sma_200'].diff(20) > 0
        
        # Money Flow Index for institutional buying confirmation
        dataframe['mfi'] = IndicatorLibrary.mfi(dataframe, 14)
        
        # RSI 2-period for short-term oversold (Connors RSI)
        dataframe['rsi_2'] = IndicatorLibrary.rsi(dataframe['close'], 2)
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate mean reversion entry signals."""
        
        if 'enter_long' not in dataframe.columns:
            dataframe['enter_long'] = 0
        
        # Count oversold indicators (require at least 2)
        oversold_count = (
            (dataframe['rsi'] < self.rsi_oversold).astype(int) +
            (dataframe['stoch_k'] < self.stoch_oversold).astype(int) +
            (dataframe['williams_r'] < -80).astype(int) +
            (dataframe['cci'] < -100).astype(int) +
            (dataframe['rsi_2'] < 10).astype(int)
        )
        oversold = oversold_count >= 2  # At least 2 must confirm
        
        # Reversal signal (need at least one)
        reversal = (
            (dataframe['hammer'] == True) |
            (dataframe['engulfing_bullish'] == True) |
            (dataframe['stoch_cross_up'] == True)
        )
        
        # At or below lower Bollinger Band
        at_lower_band = dataframe['close'] <= dataframe['bb_lower'] * 1.02
        
        # Volume confirmation - need ABOVE average for reversal conviction
        volume_ok = dataframe['rel_volume'] > 1.2
        
        # Regime filter: SMA200 must be rising (don't catch falling knives)
        regime_ok = dataframe['in_uptrend'] | (dataframe['close'] > dataframe['sma_200'])
        
        # Combined entry
        conditions = oversold & reversal & at_lower_band & volume_ok & regime_ok
        
        dataframe.loc[conditions, 'enter_long'] = 1
        dataframe.loc[conditions, 'enter_tag'] = 'mean_reversion_entry'
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate exit signals."""
        
        if 'exit_long' not in dataframe.columns:
            dataframe['exit_long'] = 0
        
        # Exit at mean or overbought
        exit_conditions = (
            # RSI reaching overbought zone (extended from 60 to 70 for bigger R)
            (dataframe['rsi'] > 70)
        ) | (
            # Price reached upper half of Bollinger Band (better target than middle)
            (dataframe['close'] > (dataframe['bb_middle'] + dataframe['bb_upper']) / 2)
        ) | (
            # Stochastic overbought with cross down
            (dataframe['stoch_k'] > 80) &
            (dataframe['stoch_k'] < dataframe['stoch_d']) &
            (dataframe['stoch_k'].shift(1) >= dataframe['stoch_d'].shift(1))
        )
        
        dataframe.loc[exit_conditions, 'exit_long'] = 1
        dataframe.loc[exit_conditions, 'exit_tag'] = 'mean_target_reached'
        
        return dataframe
