"""
TradingAI Bot - Unified Strategy Registry

Single canonical registry consumed by SignalEngine, StrategyOptimizer,
AutoTradingEngine, and the scheduler.

Merges:
  - src.strategies  (BaseStrategy subclasses: momentum_v1, etc.)
  - src.algo        (IStrategy subclasses: vcp, classic_swing, etc.)

IStrategy classes are wrapped in AlgoStrategyAdapter so every strategy
exposes the same generate_signals(universe, features, market_data) API.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.strategies.base import BaseStrategy
from src.strategies.algo_adapter import AlgoStrategyAdapter

# -- Original BaseStrategy implementations --
from src.strategies.momentum import MomentumStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.breakout import BreakoutStrategy

# -- IStrategy implementations (wrapped via adapter) --
from src.algo.vcp_strategy import VCPStrategy
from src.algo.momentum_strategy import MomentumBreakoutStrategy
from src.algo.mean_reversion_strategy import (
    MeanReversionStrategy as AlgoMeanRevStrategy,
)
from src.algo.trend_following_strategy import TrendFollowingStrategy
from src.algo.swing_strategies import (
    ShortTermTrendFollowingStrategy,
    ClassicSwingStrategy,
    MomentumRotationStrategy,
    ShortTermMeanReversionStrategy,
)
from src.algo.earnings_strategies import (
    PreEarningsMomentumStrategy,
    PostEarningsDriftStrategy,
    EarningsBreakoutStrategy,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BaseStrategy",
    "AlgoStrategyAdapter",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "get_all_strategies",
]

# ================================================================
# UNIFIED STRATEGY REGISTRY
#
# Keys are the canonical strategy IDs used everywhere:
#   - RegimeDetector._get_active_strategies()
#   - StrategyOptimizer.STRATEGY_REGISTRY
#   - Signal.strategy_id
# ================================================================
STRATEGY_REGISTRY: Dict[str, type] = {}


def _reg_native(cls):
    """Register a BaseStrategy subclass directly."""
    STRATEGY_REGISTRY[cls.STRATEGY_ID] = cls


def _reg_algo(algo_cls):
    """Register an IStrategy subclass via the adapter factory."""
    sid = algo_cls.STRATEGY_ID
    STRATEGY_REGISTRY[sid] = lambda cfg=None, _a=algo_cls: (
        AlgoStrategyAdapter(_a, cfg)
    )


# -- Native strategies (BaseStrategy) --
_reg_native(MomentumStrategy)          # momentum_v1
_reg_native(MeanReversionStrategy)     # mean_reversion_v1
_reg_native(BreakoutStrategy)          # breakout_v1

# -- Algo strategies (adapted IStrategy) --
_reg_algo(VCPStrategy)                          # vcp
_reg_algo(MomentumBreakoutStrategy)             # momentum_breakout
_reg_algo(AlgoMeanRevStrategy)                  # mean_reversion (algo)
_reg_algo(TrendFollowingStrategy)               # trend_following
_reg_algo(ShortTermTrendFollowingStrategy)      # short_term_trend_following
_reg_algo(ClassicSwingStrategy)                 # classic_swing
_reg_algo(MomentumRotationStrategy)             # momentum_rotation
_reg_algo(ShortTermMeanReversionStrategy)       # short_term_mean_reversion
_reg_algo(PreEarningsMomentumStrategy)          # pre_earnings_momentum
_reg_algo(PostEarningsDriftStrategy)            # post_earnings_drift
_reg_algo(EarningsBreakoutStrategy)             # earnings_breakout


def get_strategy(strategy_id: str, config: dict = None) -> BaseStrategy:
    """Instantiate a strategy by its canonical ID."""
    if strategy_id not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {strategy_id}. "
            f"Available: {sorted(STRATEGY_REGISTRY.keys())}"
        )
    entry = STRATEGY_REGISTRY[strategy_id]
    if callable(entry) and not isinstance(entry, type):
        return entry(config)
    return entry(config)


def get_all_strategies(configs: dict = None) -> List[BaseStrategy]:
    """Instantiate every registered strategy."""
    configs = configs or {}
    instances = []
    for sid in STRATEGY_REGISTRY:
        try:
            instances.append(get_strategy(sid, configs.get(sid)))
        except Exception as exc:
            logger.warning(f"Could not load strategy {sid}: {exc}")
    return instances
