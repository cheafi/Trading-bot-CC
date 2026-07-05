"""
TradingAI Bot - Unified Strategy Registry  (lazy-loaded)

All heavy imports deferred until first use.
"""
from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)

__all__ = [
    "BaseStrategy",
    "AlgoStrategyAdapter",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "get_all_strategies",
]

STRATEGY_REGISTRY: Dict[str, type] = {}
_registry_built = False


def _ensure_registry():
    global _registry_built
    if _registry_built:
        return
    _registry_built = True

    from src.algo.earnings_strategies import (
        EarningsBreakoutStrategy,
        PostEarningsDriftStrategy,
        PreEarningsMomentumStrategy,
    )
    from src.algo.mean_reversion_strategy import (
        MeanReversionStrategy as AlgoMeanRevStrategy,
    )
    from src.algo.momentum_strategy import MomentumBreakoutStrategy
    from src.algo.swing_strategies import (
        ClassicSwingStrategy,
        MomentumRotationStrategy,
        ShortTermMeanReversionStrategy,
        ShortTermTrendFollowingStrategy,
    )
    from src.algo.trend_following_strategy import TrendFollowingStrategy
    from src.algo.vcp_strategy import VCPStrategy
    from src.strategies.algo_adapter import AlgoStrategyAdapter
    from src.strategies.breakout import BreakoutStrategy
    from src.strategies.mean_reversion import MeanReversionStrategy
    from src.strategies.momentum import MomentumStrategy

    for cls in [MomentumStrategy, MeanReversionStrategy, BreakoutStrategy]:
        STRATEGY_REGISTRY[cls.STRATEGY_ID] = cls

    for algo_cls in [
        VCPStrategy, MomentumBreakoutStrategy, AlgoMeanRevStrategy,
        TrendFollowingStrategy, ShortTermTrendFollowingStrategy,
        ClassicSwingStrategy, MomentumRotationStrategy,
        ShortTermMeanReversionStrategy, PreEarningsMomentumStrategy,
        PostEarningsDriftStrategy, EarningsBreakoutStrategy,
    ]:
        sid = algo_cls.STRATEGY_ID
        STRATEGY_REGISTRY[sid] = lambda cfg=None, _a=algo_cls: (
            AlgoStrategyAdapter(_a, cfg)
        )

    logger.debug("Strategy registry built: %d strategies", len(STRATEGY_REGISTRY))


def __getattr__(name):
    if name == "BaseStrategy":
        from src.strategies.base import BaseStrategy
        return BaseStrategy
    if name == "AlgoStrategyAdapter":
        from src.strategies.algo_adapter import AlgoStrategyAdapter
        return AlgoStrategyAdapter
    if name == "STRATEGY_REGISTRY":
        _ensure_registry()
        return STRATEGY_REGISTRY
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_strategy(strategy_id: str, config: dict = None):
    """Instantiate a strategy by its canonical ID."""
    _ensure_registry()
    if strategy_id not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {strategy_id}. "
            f"Available: {sorted(STRATEGY_REGISTRY.keys())}"
        )
    entry = STRATEGY_REGISTRY[strategy_id]
    if callable(entry) and not isinstance(entry, type):
        return entry(config)
    return entry(config)


def get_all_strategies(configs: dict = None) -> list:
    """Instantiate every registered strategy."""
    _ensure_registry()
    configs = configs or {}
    instances = []
    for sid in STRATEGY_REGISTRY:
        try:
            instances.append(get_strategy(sid, configs.get(sid)))
        except Exception as exc:
            logger.warning(f"Could not load strategy {sid}: {exc}")
    return instances
