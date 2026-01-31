"""
TradingAI Bot - Base Strategy Interface (IStrategy)

Inspired by freqtrade's IStrategy pattern with modular design:
- populate_indicators(): Add technical indicators to dataframe
- populate_entry_trend(): Generate entry signals
- populate_exit_trend(): Generate exit signals

Features:
- Dataframe-based signal generation
- Configurable parameters with hyperopt support
- Risk management (stoploss, ROI, trailing stop)
- Optional algo execution (can be manual signal generation only)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class StrategyMode(str, Enum):
    """Strategy execution mode."""
    SIGNAL_ONLY = "signal_only"      # Generate signals for manual trading
    PAPER_TRADE = "paper_trade"       # Execute on paper trading
    LIVE_TRADE = "live_trade"         # Execute on live broker


class TimeFrame(str, Enum):
    """Supported timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


@dataclass
class StrategyConfig:
    """Configuration for a strategy instance."""
    
    # Strategy identification
    name: str
    version: str = "1.0"
    enabled: bool = True
    mode: StrategyMode = StrategyMode.SIGNAL_ONLY
    
    # Timeframe settings
    timeframe: TimeFrame = TimeFrame.D1
    startup_candle_count: int = 50  # Minimum candles needed for indicators
    
    # Risk management
    stoploss: float = -0.05          # 5% stop loss
    trailing_stop: bool = False
    trailing_stop_positive: float = 0.01  # Start trailing at 1% profit
    trailing_stop_positive_offset: float = 0.02
    use_custom_stoploss: bool = False
    
    # ROI (Return on Investment) table - exit at profit targets
    # Keys are time in minutes, values are minimum profit ratio
    minimal_roi: Dict[str, float] = field(default_factory=lambda: {
        "0": 0.10,     # 10% profit anytime
        "30": 0.05,    # 5% after 30 days
        "60": 0.025,   # 2.5% after 60 days
        "90": 0.01     # 1% after 90 days
    })
    
    # Position sizing
    stake_amount: float = 1000.0      # Base stake per trade
    max_open_trades: int = 5
    position_adjustment_enable: bool = False
    
    # Universe filtering
    include_sectors: List[str] = field(default_factory=list)
    exclude_sectors: List[str] = field(default_factory=list)
    min_volume: int = 100000          # Minimum avg daily volume
    min_price: float = 5.0            # Minimum price
    max_price: float = 10000.0        # Maximum price
    min_market_cap: float = 0         # Minimum market cap (0 = no filter)
    
    # Custom parameters
    parameters: Dict[str, Any] = field(default_factory=dict)


class IStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Inspired by freqtrade's IStrategy interface (Interface Version 3).
    
    Strategy Development:
    1. Inherit from IStrategy
    2. Set STRATEGY_ID and configure settings
    3. Implement populate_indicators() to add technical indicators
    4. Implement populate_entry_trend() to set entry signals
    5. Implement populate_exit_trend() to set exit signals
    
    Signal Columns:
    - enter_long: Set to 1 when entry signal for long position
    - exit_long: Set to 1 when exit signal for long position
    - enter_short: Set to 1 when entry signal for short position (if enabled)
    - exit_short: Set to 1 when exit signal for short position
    
    Example:
        class MyStrategy(IStrategy):
            STRATEGY_ID = "my_strategy"
            
            def populate_indicators(self, dataframe, metadata):
                dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
                return dataframe
            
            def populate_entry_trend(self, dataframe, metadata):
                dataframe.loc[
                    dataframe['close'] > dataframe['sma_20'],
                    'enter_long'
                ] = 1
                return dataframe
    """
    
    # Strategy identification (must be overridden)
    STRATEGY_ID: str = "base_strategy"
    INTERFACE_VERSION: int = 3
    VERSION: str = "1.0"
    
    # Default timeframe
    timeframe: TimeFrame = TimeFrame.D1
    
    # Minimum candles needed for startup
    startup_candle_count: int = 50
    
    # Order settings
    order_types: Dict[str, str] = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    # Default stoploss
    stoploss: float = -0.05
    
    # Trailing stop
    trailing_stop: bool = False
    trailing_stop_positive: float = 0.01
    trailing_stop_positive_offset: float = 0.0
    trailing_only_offset_is_reached: bool = False
    
    # Use custom stoploss
    use_custom_stoploss: bool = False
    
    # Minimal ROI table
    minimal_roi: Dict[str, float] = {
        "0": 0.10
    }
    
    # Can short
    can_short: bool = False
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """Initialize strategy with optional configuration."""
        self.config = config or StrategyConfig(name=self.STRATEGY_ID)
        self.logger = logging.getLogger(f"strategy.{self.STRATEGY_ID}")
        
        # Apply config overrides
        if config:
            self._apply_config(config)
    
    def _apply_config(self, config: StrategyConfig):
        """Apply configuration to strategy attributes."""
        if config.timeframe:
            self.timeframe = config.timeframe
        if config.stoploss:
            self.stoploss = config.stoploss
        if config.trailing_stop is not None:
            self.trailing_stop = config.trailing_stop
        if config.minimal_roi:
            self.minimal_roi = config.minimal_roi
    
    # ========== Core Methods to Override ==========
    
    @abstractmethod
    def populate_indicators(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Add indicators to the dataframe.
        
        Args:
            dataframe: OHLCV dataframe with columns [open, high, low, close, volume]
            metadata: Dict with {'ticker': str, 'timeframe': str}
        
        Returns:
            DataFrame with indicator columns added
        
        Example:
            dataframe['sma_20'] = ta.SMA(dataframe['close'], timeperiod=20)
            dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
            return dataframe
        """
        return dataframe
    
    @abstractmethod
    def populate_entry_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Generate entry signals.
        
        Set 'enter_long' column to 1 where entry conditions are met.
        For short strategies, also set 'enter_short' column.
        
        Args:
            dataframe: OHLCV dataframe with indicators added
            metadata: Dict with ticker info
        
        Returns:
            DataFrame with 'enter_long' (and optionally 'enter_short') column
        
        Example:
            dataframe.loc[
                (dataframe['rsi'] < 30) &
                (dataframe['close'] > dataframe['sma_20']),
                'enter_long'
            ] = 1
            return dataframe
        """
        return dataframe
    
    @abstractmethod
    def populate_exit_trend(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Generate exit signals.
        
        Set 'exit_long' column to 1 where exit conditions are met.
        For short strategies, also set 'exit_short' column.
        
        Args:
            dataframe: OHLCV dataframe with indicators added
            metadata: Dict with ticker info
        
        Returns:
            DataFrame with 'exit_long' (and optionally 'exit_short') column
        
        Example:
            dataframe.loc[
                (dataframe['rsi'] > 70),
                'exit_long'
            ] = 1
            return dataframe
        """
        return dataframe
    
    # ========== Optional Methods to Override ==========
    
    def custom_stoploss(
        self,
        ticker: str,
        trade_date: datetime,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> float:
        """
        Custom stoploss logic.
        
        Override to implement dynamic stoploss (e.g., based on ATR).
        Return new stoploss value or original self.stoploss.
        
        Returns:
            Stoploss ratio (e.g., -0.05 for 5% stop)
        """
        return self.stoploss
    
    def custom_exit(
        self,
        ticker: str,
        trade_date: datetime,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> Optional[str]:
        """
        Custom exit logic.
        
        Override to implement custom exit conditions.
        Return exit reason string if should exit, None otherwise.
        """
        return None
    
    def confirm_trade_entry(
        self,
        ticker: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        **kwargs
    ) -> bool:
        """
        Confirm entry trade before execution.
        
        Override to add last-minute checks (e.g., news check, market condition).
        Return True to confirm entry, False to reject.
        """
        return True
    
    def confirm_trade_exit(
        self,
        ticker: str,
        trade_date: datetime,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        exit_reason: str,
        **kwargs
    ) -> bool:
        """
        Confirm exit trade before execution.
        
        Override to add custom exit filters.
        Return True to confirm exit, False to reject.
        """
        return True
    
    def leverage(
        self,
        ticker: str,
        current_time: datetime,
        current_rate: float,
        **kwargs
    ) -> float:
        """
        Return leverage to use for this trade.
        
        Default is 1.0 (no leverage).
        """
        return 1.0
    
    def informative_pairs(self) -> List[Tuple[str, str]]:
        """
        Return list of informative pairs to pre-download.
        
        Override to specify additional pairs/timeframes needed.
        Example: return [("SPY", "1d"), ("QQQ", "1d")]
        """
        return []
    
    # ========== Analysis Methods ==========
    
    def analyze(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Full analysis pipeline: indicators -> entry -> exit.
        
        This is the main entry point for signal generation.
        """
        # Initialize signal columns
        dataframe['enter_long'] = 0
        dataframe['exit_long'] = 0
        if self.can_short:
            dataframe['enter_short'] = 0
            dataframe['exit_short'] = 0
        
        # Check minimum candles
        if len(dataframe) < self.startup_candle_count:
            self.logger.warning(
                f"Insufficient data for {metadata.get('ticker')}: "
                f"{len(dataframe)} < {self.startup_candle_count}"
            )
            return dataframe
        
        # Run analysis pipeline
        dataframe = self.populate_indicators(dataframe, metadata)
        dataframe = self.populate_entry_trend(dataframe, metadata)
        dataframe = self.populate_exit_trend(dataframe, metadata)
        
        return dataframe
    
    def get_latest_signal(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get the latest signal from analyzed dataframe.
        
        Returns dict with signal info:
        {
            'ticker': str,
            'signal_type': 'enter_long' | 'exit_long' | 'enter_short' | 'exit_short' | None,
            'price': float,
            'timestamp': datetime,
            'indicators': Dict  # Key indicator values
        }
        """
        df = self.analyze(dataframe.copy(), metadata)
        
        if df.empty:
            return {'ticker': metadata.get('ticker'), 'signal_type': None}
        
        last_row = df.iloc[-1]
        
        # Determine signal type
        signal_type = None
        if last_row.get('enter_long', 0) == 1:
            signal_type = 'enter_long'
        elif last_row.get('exit_long', 0) == 1:
            signal_type = 'exit_long'
        elif self.can_short and last_row.get('enter_short', 0) == 1:
            signal_type = 'enter_short'
        elif self.can_short and last_row.get('exit_short', 0) == 1:
            signal_type = 'exit_short'
        
        return {
            'ticker': metadata.get('ticker'),
            'signal_type': signal_type,
            'price': last_row.get('close'),
            'timestamp': last_row.name if hasattr(last_row.name, 'strftime') else datetime.now(),
            'strategy': self.STRATEGY_ID,
            'indicators': {
                col: last_row.get(col) 
                for col in df.columns 
                if col not in ['open', 'high', 'low', 'close', 'volume', 'enter_long', 'exit_long', 'enter_short', 'exit_short']
            }
        }
    
    def get_all_signals(
        self, 
        dataframe: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Get all signals from analyzed dataframe.
        
        Returns DataFrame filtered to rows with any signal.
        """
        df = self.analyze(dataframe.copy(), metadata)
        
        # Filter to signal rows
        signal_mask = (
            (df.get('enter_long', 0) == 1) | 
            (df.get('exit_long', 0) == 1)
        )
        if self.can_short:
            signal_mask |= (
                (df.get('enter_short', 0) == 1) | 
                (df.get('exit_short', 0) == 1)
            )
        
        return df[signal_mask]
    
    # ========== Utility Methods ==========
    
    def get_parameters(self) -> Dict[str, Any]:
        """Return strategy parameters for logging/optimization."""
        return {
            'strategy_id': self.STRATEGY_ID,
            'version': self.VERSION,
            'timeframe': self.timeframe.value,
            'stoploss': self.stoploss,
            'trailing_stop': self.trailing_stop,
            'minimal_roi': self.minimal_roi,
            'startup_candle_count': self.startup_candle_count,
            'can_short': self.can_short,
            'custom_params': getattr(self.config, 'parameters', {})
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id='{self.STRATEGY_ID}', version='{self.VERSION}')"
