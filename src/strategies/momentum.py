"""
TradingAI Bot - Momentum Strategy
Trend-following strategy that buys stocks with strong positive momentum.
"""
from typing import List, Dict, Optional, Any
import pandas as pd

from src.strategies.base import BaseStrategy
from src.core.models import Signal, Direction, Horizon


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy - Buy winners in uptrends.
    
    Entry conditions:
    - Price > SMA(50) > SMA(200) [uptrend confirmation]
    - 21-day return in top quintile of universe
    - RSI between 50-70 (not overbought)
    - ADX > 25 (trending market)
    - Relative volume > 1.0
    
    Exit conditions:
    - Trailing stop: 2x ATR(14)
    - Price closes below SMA(50)
    - RSI > 80 (overbought)
    """
    
    STRATEGY_ID = "momentum_v1"
    VERSION = "1.0"
    HORIZON = Horizon.SWING_5_15D
    
    # Default parameters
    DEFAULT_CONFIG = {
        "lookback": 21,
        "holding_period": 10,
        "quintile_threshold": 0.80,  # Top 20%
        "atr_multiplier": 2.0,
        "min_adx": 25,
        "rsi_min": 50,
        "rsi_max": 70,
        "min_relative_volume": 1.0,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        # Extract config
        self.lookback = self.config["lookback"]
        self.quintile_threshold = self.config["quintile_threshold"]
        self.atr_multiplier = self.config["atr_multiplier"]
        self.min_adx = self.config["min_adx"]
        self.rsi_min = self.config["rsi_min"]
        self.rsi_max = self.config["rsi_max"]
        self.min_rel_vol = self.config["min_relative_volume"]
    
    def generate_signals(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Optional[Dict] = None
    ) -> List[Signal]:
        """Generate momentum signals."""
        
        # Check if we should trade
        should_trade, reason = self.should_trade(market_data)
        if not should_trade:
            self.logger.info(f"Skipping signal generation: {reason}")
            return []
        
        signals = []
        
        # Filter to universe
        if isinstance(features.index, pd.MultiIndex):
            # If multi-indexed, get latest date
            df = features.copy()
        else:
            df = features[features.index.isin(universe)].copy()
        
        if df.empty:
            return []
        
        # Calculate momentum rank
        if 'return_21d' in df.columns:
            df['momentum_rank'] = df['return_21d'].rank(pct=True)
        else:
            self.logger.warning("return_21d not in features, skipping")
            return []
        
        # Apply filters
        required_cols = ['close', 'sma_50', 'sma_200', 'adx_14', 'rsi_14', 
                        'relative_volume', 'atr_14']
        
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            self.logger.warning(f"Missing required columns: {missing}")
            return []
        
        # Uptrend filter
        uptrend_mask = (
            (df['close'] > df['sma_50']) &
            (df['sma_50'] > df['sma_200'])
        )
        
        # Trend strength filter
        trend_mask = df['adx_14'] > self.min_adx
        
        # Momentum filter
        momentum_mask = df['momentum_rank'] >= self.quintile_threshold
        
        # RSI filter (not overbought)
        rsi_mask = df['rsi_14'].between(self.rsi_min, self.rsi_max)
        
        # Volume filter
        volume_mask = df['relative_volume'] > self.min_rel_vol
        
        # Combined filter
        candidates = df[uptrend_mask & trend_mask & momentum_mask & rsi_mask & volume_mask]
        
        self.logger.info(f"Found {len(candidates)} momentum candidates from {len(df)} tickers")
        
        # Generate signals for candidates
        for ticker in candidates.index:
            row = candidates.loc[ticker]
            
            try:
                signal = self._create_momentum_signal(ticker, row)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.error(f"Error creating signal for {ticker}: {e}")
                continue
        
        # Sort by confidence
        signals = sorted(signals, key=lambda s: s.confidence, reverse=True)
        
        return signals
    
    def _create_momentum_signal(self, ticker: str, row: pd.Series) -> Optional[Signal]:
        """Create a momentum signal from feature row."""
        
        entry_price = float(row['close'])
        atr = float(row['atr_14'])
        
        # Calculate levels
        stop_price = entry_price - (self.atr_multiplier * atr)
        target_1 = entry_price + (1.5 * atr)
        target_2 = entry_price + (3.0 * atr)
        target_3 = entry_price + (5.0 * atr)
        
        # Calculate confidence
        confidence = self._calculate_confidence(row)
        
        # Build entry logic
        ret_21d = row.get('return_21d', 0) * 100
        entry_logic = (
            f"Momentum breakout: price above rising SMAs, "
            f"ADX={row['adx_14']:.1f}, 21d return={ret_21d:.1f}% (top quintile), "
            f"RSI={row['rsi_14']:.1f}"
        )
        
        # Key risks
        key_risks = [
            "Market regime shift to risk-off",
            "Sector rotation away from this name",
            "Momentum reversal / profit-taking",
        ]
        
        # Check for earnings
        if row.get('days_to_earnings', 999) < 10:
            key_risks.append(f"Earnings in {int(row['days_to_earnings'])} days")
        
        # Rationale
        risk_reward = (target_1 - entry_price) / (entry_price - stop_price)
        rationale = (
            f"Strong momentum with price above 50/200 SMAs. "
            f"ADX confirms trend strength. Volume {row['relative_volume']:.1f}x average confirms institutional interest. "
            f"Risk/reward = {risk_reward:.1f}x to first target."
        )
        
        return self._create_signal(
            ticker=ticker,
            direction=Direction.LONG,
            entry_price=entry_price,
            stop_price=stop_price,
            target_prices=[target_1, target_2, target_3],
            entry_logic=entry_logic,
            catalyst="Technical momentum + relative strength",
            key_risks=key_risks,
            confidence=confidence,
            rationale=rationale,
            features=row
        )
    
    def _calculate_confidence(self, row: pd.Series) -> int:
        """Calculate confidence score based on signal quality."""
        score = 50  # Base score
        
        # Momentum rank bonus
        mom_rank = row.get('momentum_rank', 0.5)
        if mom_rank >= 0.95:
            score += 15
        elif mom_rank >= 0.90:
            score += 10
        elif mom_rank >= 0.85:
            score += 5
        
        # Trend strength bonus
        adx = row.get('adx_14', 0)
        if adx >= 40:
            score += 10
        elif adx >= 35:
            score += 7
        elif adx >= 30:
            score += 4
        
        # Volume confirmation bonus
        rel_vol = row.get('relative_volume', 1.0)
        if rel_vol >= 2.0:
            score += 10
        elif rel_vol >= 1.5:
            score += 6
        elif rel_vol >= 1.2:
            score += 3
        
        # Distance from 52-week high bonus
        dist_high = row.get('dist_from_52w_high', 0)
        if dist_high is not None and dist_high > 0.05:
            score += 5  # Room to run
        
        # Sentiment alignment bonus
        sentiment = row.get('news_sentiment_7d', 0)
        if sentiment is not None and sentiment > 30:
            score += 5
        elif sentiment is not None and sentiment < -30:
            score -= 5  # Negative sentiment penalty
        
        # RSI sweet spot bonus
        rsi = row.get('rsi_14', 50)
        if 55 <= rsi <= 65:
            score += 5  # Optimal range
        
        return min(95, max(10, score))  # Clamp to reasonable range
