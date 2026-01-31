"""
TradingAI Bot - Algo Trading Module

Modular algorithmic trading engine inspired by open-source projects:
- freqtrade: Strategy interface pattern (IStrategy)
- backtrader: Cerebro engine architecture
- machine-learning-for-trading: Alpha factor engineering

This module provides:
- IStrategy base class for strategy development
- Strategy registry and manager
- Indicator library (50+ indicators)
- Signal generation framework
- Position sizing and risk management
- Short-term swing trading strategies
- Earnings and event-driven strategies
- Optional algo trading (can be enabled/disabled per strategy)

Strategy Categories:
1. Pattern-Based: VCP, Breakout, Cup & Handle
2. Momentum: Momentum Breakout, Momentum Rotation
3. Mean Reversion: Oversold bounces, Support bounces
4. Trend Following: Trend pullback, Moving average based
5. Swing Trading: Classic swing, Short-term trend following
6. Event-Driven: Pre-earnings momentum, Post-earnings drift
"""

from .base_strategy import IStrategy, StrategyConfig, StrategyMode, TimeFrame
from .strategy_manager import StrategyManager
from .indicators import IndicatorLibrary

# Pattern-based strategies
from .vcp_strategy import VCPStrategy

# Momentum strategies
from .momentum_strategy import MomentumBreakoutStrategy

# Mean reversion strategies
from .mean_reversion_strategy import MeanReversionStrategy

# Trend following strategies
from .trend_following_strategy import TrendFollowingStrategy

# Swing trading strategies
from .swing_strategies import (
    ShortTermTrendFollowingStrategy,
    ClassicSwingStrategy,
    MomentumRotationStrategy,
    ShortTermMeanReversionStrategy,
    SwingStyle,
    SwingTradeConfig,
    SWING_STRATEGIES,
    get_swing_strategy,
    list_swing_strategies,
)

# Earnings and event strategies
from .earnings_strategies import (
    PreEarningsMomentumStrategy,
    PostEarningsDriftStrategy,
    EarningsBreakoutStrategy,
    EarningsEvent,
    EarningsReaction,
    EarningsCalendar,
    EARNINGS_STRATEGIES,
    get_earnings_strategy,
    list_earnings_strategies,
)

# Position sizing and risk management
from .position_manager import (
    PositionManager,
    Position,
    PositionStatus,
    RiskParameters,
    calculate_risk_reward,
    calculate_kelly_fraction,
    suggested_risk_parameters,
)

__all__ = [
    # Core classes
    'IStrategy',
    'StrategyConfig',
    'StrategyMode',
    'TimeFrame',
    'StrategyManager',
    'IndicatorLibrary',
    
    # Pattern strategies
    'VCPStrategy',
    
    # Momentum strategies
    'MomentumBreakoutStrategy',
    'MomentumRotationStrategy',
    
    # Mean reversion strategies
    'MeanReversionStrategy',
    'ShortTermMeanReversionStrategy',
    
    # Trend following strategies
    'TrendFollowingStrategy',
    'ShortTermTrendFollowingStrategy',
    
    # Swing trading strategies
    'ClassicSwingStrategy',
    'SwingStyle',
    'SwingTradeConfig',
    'SWING_STRATEGIES',
    'get_swing_strategy',
    'list_swing_strategies',
    
    # Earnings strategies
    'PreEarningsMomentumStrategy',
    'PostEarningsDriftStrategy',
    'EarningsBreakoutStrategy',
    'EarningsEvent',
    'EarningsReaction',
    'EarningsCalendar',
    'EARNINGS_STRATEGIES',
    'get_earnings_strategy',
    'list_earnings_strategies',
    
    # Position management
    'PositionManager',
    'Position',
    'PositionStatus',
    'RiskParameters',
    'calculate_risk_reward',
    'calculate_kelly_fraction',
    'suggested_risk_parameters',
]

# Strategy registry for easy access
ALL_STRATEGIES = {
    # Pattern
    'vcp': VCPStrategy,
    
    # Momentum
    'momentum_breakout': MomentumBreakoutStrategy,
    'momentum_rotation': MomentumRotationStrategy,
    
    # Mean Reversion
    'mean_reversion': MeanReversionStrategy,
    'short_term_mean_reversion': ShortTermMeanReversionStrategy,
    
    # Trend Following
    'trend_following': TrendFollowingStrategy,
    'short_term_trend_following': ShortTermTrendFollowingStrategy,
    
    # Swing Trading
    'classic_swing': ClassicSwingStrategy,
    
    # Earnings
    'pre_earnings_momentum': PreEarningsMomentumStrategy,
    'post_earnings_drift': PostEarningsDriftStrategy,
    'earnings_breakout': EarningsBreakoutStrategy,
}


def get_strategy(strategy_id: str) -> IStrategy:
    """Get any strategy by ID."""
    if strategy_id not in ALL_STRATEGIES:
        raise ValueError(
            f"Unknown strategy: {strategy_id}. "
            f"Available: {list(ALL_STRATEGIES.keys())}"
        )
    return ALL_STRATEGIES[strategy_id]()


def list_all_strategies() -> dict:
    """List all available strategies by category."""
    return {
        'pattern': ['vcp'],
        'momentum': ['momentum_breakout', 'momentum_rotation'],
        'mean_reversion': ['mean_reversion', 'short_term_mean_reversion'],
        'trend_following': ['trend_following', 'short_term_trend_following'],
        'swing_trading': ['classic_swing'],
        'earnings': ['pre_earnings_momentum', 'post_earnings_drift', 'earnings_breakout'],
    }

