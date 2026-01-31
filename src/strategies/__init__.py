"""
TradingAI Bot - Strategies Module
"""
from src.strategies.base import BaseStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.breakout import BreakoutStrategy

__all__ = [
    "BaseStrategy",
    "MomentumStrategy",
    "MeanReversionStrategy",
    "BreakoutStrategy",
]

# Strategy registry for easy lookup
STRATEGY_REGISTRY = {
    "momentum_v1": MomentumStrategy,
    "mean_reversion_v1": MeanReversionStrategy,
    "breakout_v1": BreakoutStrategy,
}


def get_strategy(strategy_id: str, config: dict = None) -> BaseStrategy:
    """Get a strategy instance by ID."""
    if strategy_id not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_id}. Available: {list(STRATEGY_REGISTRY.keys())}")
    
    return STRATEGY_REGISTRY[strategy_id](config)


def get_all_strategies(configs: dict = None) -> list[BaseStrategy]:
    """Get instances of all registered strategies."""
    configs = configs or {}
    return [
        cls(configs.get(strategy_id))
        for strategy_id, cls in STRATEGY_REGISTRY.items()
    ]
