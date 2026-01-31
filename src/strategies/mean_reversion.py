"""
TradingAI Bot - Mean Reversion Strategy
Buy oversold stocks in uptrends, expecting bounce back to mean.
"""
from typing import List, Dict, Optional, Any
import pandas as pd

from src.strategies.base import BaseStrategy
from src.core.models import Signal, Direction, Horizon


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy - Buy oversold bounces.
    
    Entry conditions (LONG):
    - Price > SMA(200) [still in long-term uptrend]
    - RSI(14) < 30 OR price < lower Bollinger Band
    - Z-score of 21-day return < -2.0
    - No negative catalyst (earnings miss, guidance cut)
    - VIX not in panic mode (< 35)
    
    Exit conditions:
    - RSI > 50 (mean reversion complete)
    - Close above SMA(20)
    - Time stop: 5 trading days
    """
    
    STRATEGY_ID = "mean_reversion_v1"
    VERSION = "1.0"
    HORIZON = Horizon.SWING_1_5D
    
    DEFAULT_CONFIG = {
        "zscore_threshold": -2.0,
        "rsi_threshold": 30,
        "max_vix": 35,
        "time_stop_days": 5,
        "min_dist_to_sma200": 0.0,  # Must be above SMA200
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.zscore_threshold = self.config["zscore_threshold"]
        self.rsi_threshold = self.config["rsi_threshold"]
        self.max_vix = self.config["max_vix"]
    
    def should_trade(self, market_data: Optional[Dict] = None) -> tuple[bool, str]:
        """Check if conditions allow mean reversion trading."""
        should, reason = super().should_trade(market_data)
        if not should:
            return should, reason
        
        if market_data is None:
            return True, "No market data to check"
        
        # Mean reversion doesn't work in panic selling
        vix = market_data.get('vix', 0)
        if vix > self.max_vix:
            return False, f"VIX {vix} > {self.max_vix}, too volatile for mean reversion"
        
        # Check if market is crashing
        spx_change = market_data.get('spx_change_pct', 0)
        if spx_change < -3.0:
            return False, f"Market down {spx_change}%, don't catch falling knives"
        
        return True, "OK"
    
    def generate_signals(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Optional[Dict] = None
    ) -> List[Signal]:
        """Generate mean reversion signals."""
        
        should_trade, reason = self.should_trade(market_data)
        if not should_trade:
            self.logger.info(f"Skipping signal generation: {reason}")
            return []
        
        signals = []
        df = features.copy()
        
        if df.empty:
            return []
        
        # Check required columns
        required_cols = ['close', 'sma_200', 'sma_20', 'rsi_14', 'bb_lower', 
                        'return_21d', 'atr_14']
        
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            self.logger.warning(f"Missing required columns: {missing}")
            return []
        
        # Calculate z-score of 21-day returns
        mean_return = df['return_21d'].mean()
        std_return = df['return_21d'].std()
        
        if std_return > 0:
            df['zscore_21d'] = (df['return_21d'] - mean_return) / std_return
        else:
            df['zscore_21d'] = 0
        
        # Long-term uptrend filter (price above SMA200)
        uptrend_mask = df['close'] > df['sma_200']
        
        # Oversold filter
        rsi_oversold = df['rsi_14'] < self.rsi_threshold
        bb_oversold = df['close'] < df['bb_lower']
        oversold_mask = rsi_oversold | bb_oversold
        
        # Z-score filter
        zscore_mask = df['zscore_21d'] < self.zscore_threshold
        
        # Combined filter
        candidates = df[uptrend_mask & oversold_mask & zscore_mask]
        
        self.logger.info(f"Found {len(candidates)} mean reversion candidates")
        
        for ticker in candidates.index:
            row = candidates.loc[ticker]
            
            try:
                signal = self._create_mean_reversion_signal(ticker, row)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.error(f"Error creating signal for {ticker}: {e}")
                continue
        
        return sorted(signals, key=lambda s: s.confidence, reverse=True)
    
    def _create_mean_reversion_signal(self, ticker: str, row: pd.Series) -> Optional[Signal]:
        """Create a mean reversion signal."""
        
        entry_price = float(row['close'])
        sma_20 = float(row['sma_20'])
        low_20d = row.get('low_20d', entry_price * 0.95)
        
        # Stop below recent swing low
        stop_price = float(low_20d) * 0.97
        
        # Target is reversion to SMA(20)
        target_price = sma_20
        
        # Confidence based on severity of oversold condition
        confidence = self._calculate_confidence(row)
        
        zscore = row['zscore_21d']
        rsi = row['rsi_14']
        
        entry_logic = (
            f"Oversold bounce: RSI={rsi:.1f}, Z-score={zscore:.2f}. "
            f"Price {((entry_price/row['sma_200'])-1)*100:.1f}% above SMA200 (uptrend intact)."
        )
        
        key_risks = [
            "Continued selling pressure",
            "Negative news/catalyst not yet priced in",
            "Market-wide selloff could override individual stock dynamics",
            "False bottom - may need to retest lows"
        ]
        
        rationale = (
            f"Statistically oversold with Z-score {zscore:.2f} (< -2.0 threshold). "
            f"Long-term uptrend intact (above SMA200). "
            f"Historical mean reversion typically occurs within 3-5 days. "
            f"Target mean reversion to SMA(20) at ${sma_20:.2f}."
        )
        
        return self._create_signal(
            ticker=ticker,
            direction=Direction.LONG,
            entry_price=entry_price,
            stop_price=stop_price,
            target_prices=[target_price],
            entry_logic=entry_logic,
            catalyst="Statistical mean reversion to SMA(20)",
            key_risks=key_risks,
            confidence=confidence,
            rationale=rationale,
            features=row
        )
    
    def _calculate_confidence(self, row: pd.Series) -> int:
        """Calculate confidence for mean reversion signal."""
        score = 45  # Lower base than momentum (more risk)
        
        # Deeper oversold = higher confidence
        zscore = row.get('zscore_21d', 0)
        if zscore < -3.0:
            score += 15
        elif zscore < -2.5:
            score += 10
        elif zscore < -2.0:
            score += 5
        
        # RSI bonus
        rsi = row.get('rsi_14', 50)
        if rsi < 20:
            score += 10
        elif rsi < 25:
            score += 7
        elif rsi < 30:
            score += 4
        
        # Distance above SMA200 (stronger uptrend = safer mean reversion)
        dist_sma200 = row.get('dist_from_sma200', 0)
        if dist_sma200 is not None and dist_sma200 > 0.10:
            score += 10
        elif dist_sma200 is not None and dist_sma200 > 0.05:
            score += 5
        
        # Volume surge on selloff (could be capitulation)
        rel_vol = row.get('relative_volume', 1.0)
        if rel_vol >= 2.0:
            score += 5  # High volume on down move = capitulation
        
        # Sentiment - contrarian
        sentiment = row.get('news_sentiment_7d', 0)
        if sentiment is not None and sentiment < -50:
            score += 5  # Very negative sentiment is contrarian bullish
        
        return min(85, max(20, score))  # Cap lower for mean reversion
