"""
TradingAI Bot - Strategy Manager

Inspired by freqtrade and backtrader's strategy management:
- Strategy registry and discovery
- Configuration management
- Signal aggregation across strategies
- Optional algo execution routing
"""
import importlib
import pkgutil
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
import pandas as pd
from datetime import datetime
import logging

from .base_strategy import IStrategy, StrategyConfig, StrategyMode

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Registry for discovering and managing strategies.
    
    Strategies can be registered manually or auto-discovered from modules.
    """
    
    _strategies: Dict[str, Type[IStrategy]] = {}
    
    @classmethod
    def register(cls, strategy_class: Type[IStrategy]) -> None:
        """Register a strategy class."""
        strategy_id = strategy_class.STRATEGY_ID
        cls._strategies[strategy_id] = strategy_class
        logger.info(f"Registered strategy: {strategy_id}")
    
    @classmethod
    def get(cls, strategy_id: str) -> Optional[Type[IStrategy]]:
        """Get a strategy class by ID."""
        return cls._strategies.get(strategy_id)
    
    @classmethod
    def list_strategies(cls) -> List[str]:
        """List all registered strategy IDs."""
        return list(cls._strategies.keys())
    
    @classmethod
    def get_all(cls) -> Dict[str, Type[IStrategy]]:
        """Get all registered strategies."""
        return cls._strategies.copy()
    
    @classmethod
    def discover(cls, module_path: str = "src.algo") -> None:
        """
        Auto-discover strategies from a module path.
        
        Searches for classes that inherit from IStrategy.
        """
        try:
            module = importlib.import_module(module_path)
            
            # Get the module's directory
            if hasattr(module, '__path__'):
                for importer, modname, ispkg in pkgutil.iter_modules(module.__path__):
                    try:
                        submodule = importlib.import_module(f"{module_path}.{modname}")
                        
                        # Look for IStrategy subclasses
                        for name in dir(submodule):
                            obj = getattr(submodule, name)
                            if (
                                isinstance(obj, type) and 
                                issubclass(obj, IStrategy) and 
                                obj is not IStrategy and
                                obj.STRATEGY_ID != "base_strategy"
                            ):
                                cls.register(obj)
                    except Exception as e:
                        logger.debug(f"Could not import {modname}: {e}")
                        
        except Exception as e:
            logger.warning(f"Strategy discovery failed: {e}")


class StrategyManager:
    """
    Manages multiple strategies for signal generation and execution.
    
    Features:
    - Load and configure multiple strategies
    - Run strategies in parallel or sequence
    - Aggregate signals from multiple strategies
    - Route signals to appropriate execution mode
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.active_strategies: Dict[str, IStrategy] = {}
        self.logger = logging.getLogger(__name__)
    
    def load_strategy(
        self, 
        strategy_id: str, 
        config: Optional[StrategyConfig] = None
    ) -> Optional[IStrategy]:
        """
        Load a strategy by ID with optional configuration.
        
        Args:
            strategy_id: Strategy identifier
            config: Optional strategy configuration
        
        Returns:
            Initialized strategy instance or None if not found
        """
        strategy_class = StrategyRegistry.get(strategy_id)
        
        if strategy_class is None:
            self.logger.error(f"Strategy not found: {strategy_id}")
            return None
        
        try:
            strategy = strategy_class(config=config)
            self.active_strategies[strategy_id] = strategy
            self.logger.info(f"Loaded strategy: {strategy_id}")
            return strategy
        except Exception as e:
            self.logger.error(f"Failed to load strategy {strategy_id}: {e}")
            return None
    
    def load_strategies(
        self, 
        strategy_configs: List[Dict[str, Any]]
    ) -> Dict[str, IStrategy]:
        """
        Load multiple strategies from configuration list.
        
        Args:
            strategy_configs: List of strategy configuration dicts
                [{'strategy_id': 'vcp', 'enabled': True, 'parameters': {...}}]
        
        Returns:
            Dict of loaded strategy instances
        """
        loaded = {}
        
        for cfg in strategy_configs:
            strategy_id = cfg.get('strategy_id')
            if not strategy_id:
                continue
            
            if not cfg.get('enabled', True):
                self.logger.info(f"Strategy {strategy_id} is disabled, skipping")
                continue
            
            # Build StrategyConfig
            config = StrategyConfig(
                name=strategy_id,
                enabled=cfg.get('enabled', True),
                mode=StrategyMode(cfg.get('mode', 'signal_only')),
                parameters=cfg.get('parameters', {})
            )
            
            strategy = self.load_strategy(strategy_id, config)
            if strategy:
                loaded[strategy_id] = strategy
        
        return loaded
    
    def unload_strategy(self, strategy_id: str) -> bool:
        """Unload a strategy from active set."""
        if strategy_id in self.active_strategies:
            del self.active_strategies[strategy_id]
            self.logger.info(f"Unloaded strategy: {strategy_id}")
            return True
        return False
    
    def get_strategy(self, strategy_id: str) -> Optional[IStrategy]:
        """Get an active strategy by ID."""
        return self.active_strategies.get(strategy_id)
    
    def list_active_strategies(self) -> List[str]:
        """List IDs of currently active strategies."""
        return list(self.active_strategies.keys())
    
    def run_strategy(
        self,
        strategy_id: str,
        dataframe: pd.DataFrame,
        metadata: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Run a single strategy on data.
        
        Args:
            strategy_id: Strategy to run
            dataframe: OHLCV data
            metadata: Ticker info {'ticker': str, 'timeframe': str}
        
        Returns:
            DataFrame with signals
        """
        strategy = self.get_strategy(strategy_id)
        if strategy is None:
            self.logger.error(f"Strategy not active: {strategy_id}")
            return dataframe
        
        return strategy.analyze(dataframe.copy(), metadata)
    
    def run_all_strategies(
        self,
        dataframe: pd.DataFrame,
        metadata: Dict[str, Any],
        aggregate: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Run all active strategies on data.
        
        Args:
            dataframe: OHLCV data
            metadata: Ticker info
            aggregate: Whether to add aggregated signal columns
        
        Returns:
            Dict mapping strategy_id to result DataFrame
        """
        results = {}
        
        for strategy_id, strategy in self.active_strategies.items():
            try:
                result = strategy.analyze(dataframe.copy(), metadata)
                results[strategy_id] = result
            except Exception as e:
                self.logger.error(f"Strategy {strategy_id} failed: {e}")
        
        if aggregate and results:
            # Add aggregated signals to original dataframe
            dataframe['signal_count'] = 0
            dataframe['strategies_bullish'] = ''
            
            for strategy_id, result in results.items():
                if 'enter_long' in result.columns:
                    dataframe['signal_count'] += result['enter_long']
                    mask = result['enter_long'] == 1
                    dataframe.loc[mask, 'strategies_bullish'] += f"{strategy_id},"
            
            results['_aggregated'] = dataframe
        
        return results
    
    def get_latest_signals(
        self,
        ticker: str,
        dataframe: pd.DataFrame,
        strategies: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get latest signals from specified strategies.
        
        Args:
            ticker: Stock ticker
            dataframe: OHLCV data
            strategies: List of strategy IDs (None = all active)
        
        Returns:
            List of signal dicts
        """
        signals = []
        strategies_to_run = strategies or list(self.active_strategies.keys())
        
        for strategy_id in strategies_to_run:
            strategy = self.get_strategy(strategy_id)
            if strategy is None:
                continue
            
            metadata = {'ticker': ticker, 'timeframe': strategy.timeframe.value}
            signal = strategy.get_latest_signal(dataframe.copy(), metadata)
            
            if signal.get('signal_type'):
                signals.append(signal)
        
        return signals
    
    def scan_universe(
        self,
        universe_data: Dict[str, pd.DataFrame],
        strategies: Optional[List[str]] = None,
        min_strategies: int = 2  # Require 2+ strategy agreement for better signal quality
    ) -> List[Dict[str, Any]]:
        """
        Scan a universe of stocks with multiple strategies.
        
        Args:
            universe_data: Dict mapping ticker to OHLCV DataFrame
            strategies: List of strategy IDs to use (None = all active)
            min_strategies: Minimum strategies that must signal
        
        Returns:
            List of candidates with signals from multiple strategies
        """
        candidates = []
        strategies_to_run = strategies or list(self.active_strategies.keys())
        
        for ticker, df in universe_data.items():
            ticker_signals = []
            
            for strategy_id in strategies_to_run:
                strategy = self.get_strategy(strategy_id)
                if strategy is None:
                    continue
                
                try:
                    metadata = {'ticker': ticker, 'timeframe': strategy.timeframe.value}
                    signal = strategy.get_latest_signal(df.copy(), metadata)
                    
                    if signal.get('signal_type') == 'enter_long':
                        ticker_signals.append({
                            'strategy': strategy_id,
                            'price': signal.get('price'),
                            'indicators': signal.get('indicators', {})
                        })
                except Exception as e:
                    self.logger.debug(f"Strategy {strategy_id} failed on {ticker}: {e}")
            
            if len(ticker_signals) >= min_strategies:
                candidates.append({
                    'ticker': ticker,
                    'price': df['close'].iloc[-1],
                    'signal_count': len(ticker_signals),
                    'strategies': ticker_signals,
                    'strategy_names': [s['strategy'] for s in ticker_signals]
                })
        
        # Sort by signal count
        candidates.sort(key=lambda x: x['signal_count'], reverse=True)
        
        return candidates
    
    def get_strategy_stats(self) -> Dict[str, Dict]:
        """Get statistics for all active strategies."""
        stats = {}
        
        for strategy_id, strategy in self.active_strategies.items():
            stats[strategy_id] = {
                'version': strategy.VERSION,
                'timeframe': strategy.timeframe.value,
                'stoploss': strategy.stoploss,
                'trailing_stop': strategy.trailing_stop,
                'can_short': strategy.can_short,
                'startup_candles': strategy.startup_candle_count,
                'minimal_roi': strategy.minimal_roi,
                'mode': strategy.config.mode.value if strategy.config else 'signal_only',
                'parameters': strategy.get_parameters()
            }
        
        return stats


# Auto-register built-in strategies
def _register_builtin_strategies():
    """Register ALL built-in strategies including swing and earnings."""
    strategy_imports = [
        ('vcp_strategy', 'VCPStrategy'),
        ('momentum_strategy', 'MomentumBreakoutStrategy'),
        ('mean_reversion_strategy', 'MeanReversionStrategy'),
        ('trend_following_strategy', 'TrendFollowingStrategy'),
    ]
    
    for module_name, class_name in strategy_imports:
        try:
            import importlib
            mod = importlib.import_module(f'.{module_name}', package='src.algo')
            cls = getattr(mod, class_name)
            StrategyRegistry.register(cls)
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not register {class_name}: {e}")
    
    # Register swing strategies
    try:
        from .swing_strategies import (
            ShortTermTrendFollowingStrategy,
            ClassicSwingStrategy,
            MomentumRotationStrategy,
            ShortTermMeanReversionStrategy,
        )
        for cls in [
            ShortTermTrendFollowingStrategy,
            ClassicSwingStrategy,
            MomentumRotationStrategy,
            ShortTermMeanReversionStrategy,
        ]:
            StrategyRegistry.register(cls)
    except ImportError as e:
        logger.debug(f"Could not register swing strategies: {e}")
    
    # Register earnings strategies
    try:
        from .earnings_strategies import (
            PreEarningsRunUpStrategy,
            PostEarningsDriftStrategy,
            EarningsBreakoutStrategy,
        )
        for cls in [
            PreEarningsRunUpStrategy,
            PostEarningsDriftStrategy,
            EarningsBreakoutStrategy,
        ]:
            StrategyRegistry.register(cls)
    except ImportError as e:
        logger.debug(f"Could not register earnings strategies: {e}")


# Auto-register on module import
_register_builtin_strategies()
