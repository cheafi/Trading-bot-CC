"""
TradingAI Bot - Base Strategy Class
All strategies inherit from this base class.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any
import pandas as pd
import logging

from src.core.models import Signal, Direction, Horizon, Invalidation, Target


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Each strategy must implement:
    - STRATEGY_ID: Unique identifier
    - HORIZON: Default time horizon for signals
    - generate_signals(): Main signal generation logic
    """
    
    STRATEGY_ID: str = "base"
    VERSION: str = "1.0"
    HORIZON: Horizon = Horizon.SWING_5_15D
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"strategy.{self.STRATEGY_ID}")
    
    @abstractmethod
    def generate_signals(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Optional[Dict] = None
    ) -> List[Signal]:
        """
        Generate trading signals for the universe.
        
        Args:
            universe: List of tickers to consider
            features: DataFrame with pre-computed features (indexed by ticker)
            market_data: Optional market-level data (VIX, breadth, etc.)
        
        Returns:
            List of Signal objects
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Return strategy parameters for logging/backtesting."""
        return self.config.copy()
    
    def should_trade(self, market_data: Optional[Dict] = None) -> tuple[bool, str]:
        """
        Check if strategy should generate signals given market conditions.
        Override in subclass for strategy-specific checks.
        
        Returns:
            (should_trade, reason)
        """
        if market_data is None:
            return True, "No market data to check"
        
        # Default checks
        vix = market_data.get('vix', 0)
        if vix > 40:
            return False, f"VIX too high ({vix})"
        
        return True, "OK"
    
    def _calculate_confidence(self, row: pd.Series) -> int:
        """
        Calculate confidence score (0-100) for a signal.
        Override in subclass for strategy-specific scoring.
        """
        return 50  # Base confidence
    
    def _create_signal(
        self,
        ticker: str,
        direction: Direction,
        entry_price: float,
        stop_price: float,
        target_prices: List[float],
        entry_logic: str,
        catalyst: str,
        key_risks: List[str],
        confidence: int,
        rationale: str,
        features: Optional[pd.Series] = None
    ) -> Signal:
        """Helper to create a properly formatted Signal object."""
        
        # Calculate risk/reward
        risk = abs(entry_price - stop_price)
        reward = abs(target_prices[0] - entry_price) if target_prices else 0
        risk_reward = reward / risk if risk > 0 else 0
        
        # Create targets with position allocation
        targets = []
        remaining = 100
        for i, price in enumerate(target_prices[:3]):
            pct = 50 if i < len(target_prices) - 1 else remaining
            remaining -= pct
            targets.append(Target(price=price, pct_position=pct))
        
        return Signal(
            generated_at=datetime.utcnow(),
            ticker=ticker,
            direction=direction,
            horizon=self.HORIZON,
            entry_price=entry_price,
            entry_type="market",
            invalidation=Invalidation(
                stop_price=stop_price,
                stop_type="HARD",
                condition=None
            ),
            targets=targets,
            entry_logic=entry_logic[:200],
            catalyst=catalyst,
            key_risks=key_risks[:5],
            confidence=min(95, max(0, confidence)),  # Cap at 95, never 100
            rationale=rationale[:500],
            risk_reward_ratio=risk_reward,
            strategy_id=self.STRATEGY_ID,
            strategy_version=self.VERSION,
            feature_snapshot=features.to_dict() if features is not None else None
        )
