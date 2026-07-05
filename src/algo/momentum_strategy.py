"""
TradingAI Bot - Momentum Breakout Strategy

Combines momentum and breakout criteria for high-probability entries.

This strategy looks for:
1. Strong relative strength (outperforming market)
2. Price breaking out of consolidation
3. Volume confirmation on breakout
4. Positive momentum indicators
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime

from .base_strategy import IStrategy, StrategyConfig, TimeFrame
from .indicators import IndicatorLibrary


class MomentumBreakoutStrategy(IStrategy):
    """
    Momentum Breakout Strategy.
    
    Entry Criteria:
    - RSI between 50-70 (strong but not overbought)
    - Price above 20-day and 50-day EMA
    - MACD histogram positive and rising
    - Breaking above recent consolidation high
    - Volume above average
    - Relative strength positive
    
    Exit Criteria:
    - RSI > 80 (overbought)
    - Price closes below 20-day EMA
    - MACD histogram turns negative
    """
    
    STRATEGY_ID = "momentum_breakout"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 50
    
    stoploss = -0.06  # 6% stop
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05  # Activate trailing after 5% profit
    
    minimal_roi = {
        "0": 0.20,    # 20% anytime
        "10": 0.12,   # 12% after 10 days
        "20": 0.08,   # 8% after 20 days
        "40": 0.04    # 4% after 40 days
    }
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        
        params = getattr(config, 'parameters', {}) if config else {}
        
        self.rsi_entry_low = params.get('rsi_entry_low', 50)
        self.rsi_entry_high = params.get('rsi_entry_high', 70)
        self.rsi_exit = params.get('rsi_exit', 80)
        self.breakout_lookback = params.get('breakout_lookback', 20)
        self.min_volume_ratio = params.get('min_volume_ratio', 1.2)
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add momentum indicators."""
        
        # EMAs
        dataframe['ema_9'] = IndicatorLibrary.ema(dataframe['close'], 9)
        dataframe['ema_20'] = IndicatorLibrary.ema(dataframe['close'], 20)
        dataframe['ema_50'] = IndicatorLibrary.ema(dataframe['close'], 50)
        
        # RSI
        dataframe['rsi'] = IndicatorLibrary.rsi(dataframe['close'], 14)
        
        # MACD
        macd, signal, hist = IndicatorLibrary.macd(dataframe['close'])
        dataframe['macd'] = macd
        dataframe['macd_signal'] = signal
        dataframe['macd_hist'] = hist
        dataframe['macd_hist_rising'] = dataframe['macd_hist'] > dataframe['macd_hist'].shift(1)
        
        # ADX for trend strength
        adx_val, plus_di, minus_di = IndicatorLibrary.adx(dataframe, 14)
        dataframe['adx'] = adx_val
        dataframe['plus_di'] = plus_di
        dataframe['minus_di'] = minus_di
        
        # ATR for volatility
        dataframe['atr'] = IndicatorLibrary.atr(dataframe, 14)
        
        # Stochastic
        stoch_k, stoch_d = IndicatorLibrary.stochastic(dataframe)
        dataframe['stoch_k'] = stoch_k
        dataframe['stoch_d'] = stoch_d
        
        # Volume
        dataframe['vol_sma'] = IndicatorLibrary.volume_sma(dataframe, 20)
        dataframe['rel_volume'] = dataframe['volume'] / dataframe['vol_sma']
        
        # Recent high (for breakout detection)
        dataframe['recent_high'] = dataframe['high'].rolling(self.breakout_lookback).max()
        dataframe['recent_low'] = dataframe['low'].rolling(self.breakout_lookback).min()
        
        # Consolidation range
        dataframe['consolidation_range'] = (
            dataframe['recent_high'] - dataframe['recent_low']
        ) / dataframe['recent_high']
        
        # Momentum (Rate of Change)
        dataframe['roc_10'] = IndicatorLibrary.roc(dataframe['close'], 10)
        dataframe['roc_20'] = IndicatorLibrary.roc(dataframe['close'], 20)
        
        # Trend conditions
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50'])
        )
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate momentum breakout entry signals."""
        
        if 'enter_long' not in dataframe.columns:
            dataframe['enter_long'] = 0
        
        conditions = (
            # RSI in momentum zone (not oversold, not overbought)
            (dataframe['rsi'] >= self.rsi_entry_low) &
            (dataframe['rsi'] <= self.rsi_entry_high) &
            
            # Price above EMAs (uptrend) - 2 consecutive closes
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['close'].shift(1) > dataframe['ema_20'].shift(1)) &
            (dataframe['close'] > dataframe['ema_50']) &
            
            # EMA alignment
            (dataframe['ema_9'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50']) &
            
            # ADX confirms trend strength (avoid choppy markets)
            (dataframe['adx'] > 20) &
            (dataframe['plus_di'] > dataframe['minus_di']) &
            
            # MACD positive and rising
            (dataframe['macd_hist'] > 0) &
            (dataframe['macd_hist_rising'] == True) &
            
            # Breaking above recent high
            (dataframe['close'] > dataframe['recent_high'].shift(1)) &
            
            # Volume confirmation (1.5x for stronger signal)
            (dataframe['rel_volume'] >= 1.5) &
            
            # Positive momentum
            (dataframe['roc_10'] > 0)
        )
        
        dataframe.loc[conditions, 'enter_long'] = 1
        dataframe.loc[conditions, 'enter_tag'] = 'momentum_breakout'
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate exit signals."""
        
        if 'exit_long' not in dataframe.columns:
            dataframe['exit_long'] = 0
        
        exit_conditions = (
            # Overbought
            (dataframe['rsi'] > self.rsi_exit)
        ) | (
            # Lost uptrend - require 2 consecutive closes below EMA20
            (dataframe['close'] < dataframe['ema_20']) &
            (dataframe['close'].shift(1) < dataframe['ema_20'].shift(1))
        ) | (
            # MACD crossed below signal with ADX declining
            (dataframe['macd'] < dataframe['macd_signal']) &
            (dataframe['macd'].shift(1) >= dataframe['macd_signal'].shift(1)) &
            (dataframe['adx'] < dataframe['adx'].shift(3))
        )
        
        dataframe.loc[exit_conditions, 'exit_long'] = 1
        dataframe.loc[exit_conditions, 'exit_tag'] = 'momentum_exit'
        
        return dataframe
