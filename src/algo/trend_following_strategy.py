"""
TradingAI Bot - Trend Following Strategy

Classic trend following with pyramiding support.

Based on Richard Dennis's Turtle Trading rules with modern enhancements:
- Breakout of N-day high/low
- ATR-based position sizing and stops
- Pyramiding on strength
- Trailing exits
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from .base_strategy import IStrategy, StrategyConfig, TimeFrame
from .indicators import IndicatorLibrary


class TrendFollowingStrategy(IStrategy):
    """
    Trend Following Strategy (Turtle Trading inspired).
    
    Entry Criteria:
    - Price breaks 20-day high (System 1) or 55-day high (System 2)
    - ADX > 25 (strong trend)
    - Supertrend bullish
    - Moving averages aligned
    
    Position Sizing:
    - Based on ATR (volatility-adjusted)
    - Risk 1-2% per trade
    
    Exit Criteria:
    - Price breaks 10-day low (System 1) or 20-day low (System 2)
    - Trailing stop at 2x ATR
    """
    
    STRATEGY_ID = "trend_following"
    VERSION = "1.0"
    
    timeframe = TimeFrame.D1
    startup_candle_count = 55
    
    stoploss = -0.10  # Wide stop for trend following
    trailing_stop = True
    trailing_stop_positive = 0.05
    trailing_stop_positive_offset = 0.07  # Activate trailing after 7% profit
    
    use_custom_stoploss = True  # Use ATR-based stop
    
    minimal_roi = {
        "0": 0.50,    # 50% is great (let winners run longer)
        "30": 0.30,   # 30% after 30 days
        "60": 0.20,   # 20% after 60 days
        "90": 0.10    # 10% after 90 days
    }
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config)
        
        params = getattr(config, 'parameters', {}) if config else {}
        
        self.breakout_period = params.get('breakout_period', 20)  # System 1
        self.exit_period = params.get('exit_period', 10)
        self.atr_period = params.get('atr_period', 20)
        self.atr_multiplier = params.get('atr_multiplier', 2.0)
        self.min_adx = params.get('min_adx', 25)
    
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add trend following indicators."""
        
        # Donchian Channels (Turtle Trading)
        dataframe['donchian_high'] = dataframe['high'].rolling(self.breakout_period).max()
        dataframe['donchian_low'] = dataframe['low'].rolling(self.breakout_period).min()
        dataframe['donchian_mid'] = (dataframe['donchian_high'] + dataframe['donchian_low']) / 2
        
        # Exit channel (shorter period)
        dataframe['exit_high'] = dataframe['high'].rolling(self.exit_period).max()
        dataframe['exit_low'] = dataframe['low'].rolling(self.exit_period).min()
        
        # ATR for position sizing and stops
        dataframe['atr'] = IndicatorLibrary.atr(dataframe, self.atr_period)
        dataframe['atr_stop'] = dataframe['close'] - (self.atr_multiplier * dataframe['atr'])
        
        # Moving averages
        dataframe['sma_20'] = IndicatorLibrary.sma(dataframe['close'], 20)
        dataframe['sma_50'] = IndicatorLibrary.sma(dataframe['close'], 50)
        dataframe['sma_100'] = IndicatorLibrary.sma(dataframe['close'], 100)
        
        # EMA for trend direction
        dataframe['ema_21'] = IndicatorLibrary.ema(dataframe['close'], 21)
        
        # Supertrend
        supertrend, direction = IndicatorLibrary.supertrend(dataframe, 10, 3.0)
        dataframe['supertrend'] = supertrend
        dataframe['supertrend_dir'] = direction  # 1 = bullish, -1 = bearish
        
        # ADX (proper calculation from indicator library)
        adx_val, plus_di, minus_di = IndicatorLibrary.adx(dataframe, 14)
        dataframe['adx'] = adx_val
        dataframe['plus_di'] = plus_di
        dataframe['minus_di'] = minus_di
        
        # Trend strength
        dataframe['trend_strength'] = abs(dataframe['plus_di'] - dataframe['minus_di'])
        
        # MA alignment
        dataframe['ma_aligned'] = (
            (dataframe['sma_20'] > dataframe['sma_50']) &
            (dataframe['sma_50'] > dataframe['sma_100'])
        )
        
        # Breakout detection
        dataframe['breakout_up'] = dataframe['close'] > dataframe['donchian_high'].shift(1)
        dataframe['breakout_down'] = dataframe['close'] < dataframe['donchian_low'].shift(1)
        
        # Volatility regime
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        dataframe['vol_regime'] = pd.cut(
            dataframe['atr_pct'].rolling(20).mean(),
            bins=[0, 0.01, 0.02, 0.04, 1],
            labels=['low', 'normal', 'high', 'extreme']
        )
        
        return dataframe
    
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate trend following entry signals."""
        
        if 'enter_long' not in dataframe.columns:
            dataframe['enter_long'] = 0
        
        # Turtle System 1 entry
        conditions = (
            # Breakout above Donchian high
            (dataframe['breakout_up'] == True) &
            
            # Strong trend (ADX)
            (dataframe['adx'] > self.min_adx) &
            
            # +DI > -DI (uptrend)
            (dataframe['plus_di'] > dataframe['minus_di']) &
            
            # Supertrend bullish
            (dataframe['supertrend_dir'] == 1) &
            
            # MAs aligned or price above key MAs
            (
                (dataframe['ma_aligned'] == True) |
                (dataframe['close'] > dataframe['sma_50'])
            ) &
            
            # Not in extreme volatility (optional filter)
            (dataframe['vol_regime'] != 'extreme')
        )
        
        dataframe.loc[conditions, 'enter_long'] = 1
        dataframe.loc[conditions, 'enter_tag'] = 'turtle_breakout'
        
        return dataframe
    
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate exit signals."""
        
        if 'exit_long' not in dataframe.columns:
            dataframe['exit_long'] = 0
        
        # Turtle exit: break below exit channel low
        exit_conditions = (
            (dataframe['close'] < dataframe['exit_low'].shift(1))
        ) | (
            # Supertrend turns bearish AND confirmed by close below SMA20
            (dataframe['supertrend_dir'] == -1) &
            (dataframe['supertrend_dir'].shift(1) == 1) &
            (dataframe['close'] < dataframe['sma_20'])
        ) | (
            # ADX declining significantly (trend weakening) - relaxed to 20% over 10 bars
            (dataframe['adx'] < dataframe['adx'].shift(10) * 0.8) &
            (dataframe['adx'] < 20)  # Only exit on ADX weakness if ADX is low
        )
        
        dataframe.loc[exit_conditions, 'exit_long'] = 1
        dataframe.loc[exit_conditions, 'exit_tag'] = 'turtle_exit'
        
        return dataframe
    
    def custom_stoploss(
        self,
        ticker: str,
        trade_date,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> float:
        """
        ATR-based trailing stoploss.
        
        Chandelier Exit: Trail stop at 2x ATR below highest high since entry.
        """
        dataframe = kwargs.get('dataframe')
        if dataframe is None or len(dataframe) == 0:
            return self.stoploss
        
        # Get ATR-based stop distance
        atr = dataframe['atr'].iloc[-1]
        current_price = dataframe['close'].iloc[-1]
        
        if atr > 0 and current_price > 0:
            # Stop at 2x ATR below current price
            atr_stop_pct = -(self.atr_multiplier * atr) / current_price
            
            # Minimum -10%, maximum -3%
            return max(-0.10, min(-0.03, atr_stop_pct))
        
        return self.stoploss
    
    def calculate_position_size(
        self,
        account_value: float,
        risk_per_trade: float,
        entry_price: float,
        stop_price: float
    ) -> int:
        """
        Turtle-style position sizing based on N (ATR).
        
        Position = (Account * Risk %) / (N * Point Value)
        
        Args:
            account_value: Total account value
            risk_per_trade: Risk percentage (e.g., 0.02 for 2%)
            entry_price: Entry price
            stop_price: Stop loss price
        
        Returns:
            Number of shares to buy
        """
        risk_amount = account_value * risk_per_trade
        risk_per_share = abs(entry_price - stop_price)
        
        if risk_per_share > 0:
            shares = int(risk_amount / risk_per_share)
            return max(1, shares)
        
        return 0
