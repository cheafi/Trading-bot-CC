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

_LAZY = {
    "StrategyManager": ".strategy_manager",
    "IndicatorLibrary": ".indicators",
    "VCPStrategy": ".vcp_strategy",
    "MomentumBreakoutStrategy": ".momentum_strategy",
    "MeanReversionStrategy": ".mean_reversion_strategy",
    "TrendFollowingStrategy": ".trend_following_strategy",
    "ShortTermTrendFollowingStrategy": ".swing_strategies",
    "ClassicSwingStrategy": ".swing_strategies",
    "MomentumRotationStrategy": ".swing_strategies",
    "ShortTermMeanReversionStrategy": ".swing_strategies",
    "SwingStyle": ".swing_strategies",
    "SwingTradeConfig": ".swing_strategies",
    "SWING_STRATEGIES": ".swing_strategies",
    "get_swing_strategy": ".swing_strategies",
    "list_swing_strategies": ".swing_strategies",
    "PreEarningsMomentumStrategy": ".earnings_strategies",
    "PostEarningsDriftStrategy": ".earnings_strategies",
    "EarningsBreakoutStrategy": ".earnings_strategies",
    "EarningsEvent": ".earnings_strategies",
    "EarningsReaction": ".earnings_strategies",
    "EarningsCalendar": ".earnings_strategies",
    "EARNINGS_STRATEGIES": ".earnings_strategies",
    "get_earnings_strategy": ".earnings_strategies",
    "list_earnings_strategies": ".earnings_strategies",
    "PositionManager": ".position_manager",
    "Position": ".position_manager",
    "PositionStatus": ".position_manager",
    "RiskParameters": ".position_manager",
    "calculate_risk_reward": ".position_manager",
    "calculate_kelly_fraction": ".position_manager",
    "suggested_risk_parameters": ".position_manager",
}

__all__ = [
    "IStrategy",
    "StrategyConfig",
    "StrategyMode",
    "TimeFrame",
    *_LAZY,
    "ALL_STRATEGIES",
    "get_strategy",
    "list_all_strategies",
]

_all_strategies_cache = None


def _build_all_strategies():
    global _all_strategies_cache
    if _all_strategies_cache is not None:
        return _all_strategies_cache
    import importlib

    _all_strategies_cache = {}
    for sid, mod_attr in [
        ("vcp", ("VCPStrategy", ".vcp_strategy")),
        ("momentum_breakout", ("MomentumBreakoutStrategy", ".momentum_strategy")),
        ("mean_reversion", ("MeanReversionStrategy", ".mean_reversion_strategy")),
        ("trend_following", ("TrendFollowingStrategy", ".trend_following_strategy")),
        (
            "short_term_trend_following",
            ("ShortTermTrendFollowingStrategy", ".swing_strategies"),
        ),
        ("classic_swing", ("ClassicSwingStrategy", ".swing_strategies")),
        ("momentum_rotation", ("MomentumRotationStrategy", ".swing_strategies")),
        (
            "short_term_mean_reversion",
            ("ShortTermMeanReversionStrategy", ".swing_strategies"),
        ),
        (
            "pre_earnings_momentum",
            ("PreEarningsMomentumStrategy", ".earnings_strategies"),
        ),
        ("post_earnings_drift", ("PostEarningsDriftStrategy", ".earnings_strategies")),
        ("earnings_breakout", ("EarningsBreakoutStrategy", ".earnings_strategies")),
    ]:
        attr, modname = mod_attr
        cls = getattr(importlib.import_module(modname, __name__), attr)
        _all_strategies_cache[sid] = cls
    return _all_strategies_cache


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name], __name__)
        return getattr(mod, name)
    if name == "ALL_STRATEGIES":
        return _build_all_strategies()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_strategy(strategy_id: str) -> IStrategy:
    """Get any strategy by ID."""
    strategies = _build_all_strategies()
    if strategy_id not in strategies:
        raise ValueError(
            f"Unknown strategy: {strategy_id}. " f"Available: {list(strategies.keys())}"
        )
    return strategies[strategy_id]()


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
