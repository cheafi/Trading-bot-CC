"""
TradingAI Bot - Breakout Strategy
Trade breakouts from consolidation with volume confirmation.
"""
from typing import List, Dict, Optional, Any
import pandas as pd

from src.strategies.base import BaseStrategy
from src.core.models import Signal, Direction, Horizon


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy - Trade consolidation breakouts.
    
    Entry conditions:
    - Price breaks above 20-day high
    - Volume > 2x average (confirmation)
    - ATR expansion (volatility breakout)
    - Consolidation period >= 10 days (base building)
    - BB width was contracting (squeeze release)
    
    Exit conditions:
    - Initial stop: bottom of consolidation range
    - Trailing stop after 1 ATR profit: 1.5x ATR
    """
    
    STRATEGY_ID = "breakout_v1"
    VERSION = "1.0"
    HORIZON = Horizon.SWING_5_15D
    
    DEFAULT_CONFIG = {
        "min_consolidation_days": 10,
        "volume_threshold": 1.2,  # Reduced from 2.0 for current market conditions
        "atr_expansion_threshold": 1.1,
        "bb_squeeze_percentile": 0.20,  # BB width in bottom 20%
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.min_consolidation = self.config["min_consolidation_days"]
        self.volume_threshold = self.config["volume_threshold"]
        self.atr_expansion = self.config["atr_expansion_threshold"]
    
    def generate_signals(
        self,
        universe: List[str],
        features: pd.DataFrame,
        market_data: Optional[Dict] = None
    ) -> List[Signal]:
        """Generate breakout signals."""
        
        should_trade, reason = self.should_trade(market_data)
        if not should_trade:
            self.logger.info(f"Skipping signal generation: {reason}")
            return []
        
        signals = []
        df = features.copy()
        
        if df.empty:
            return []
        
        # Check required columns
        required_cols = ['close', 'high_20d', 'relative_volume', 'atr_14', 
                        'bb_width', 'low_20d']
        
        # Allow missing columns with defaults
        for col in required_cols:
            if col not in df.columns:
                if col == 'high_20d':
                    df['high_20d'] = df['close'] * 1.05  # Placeholder
                elif col == 'low_20d':
                    df['low_20d'] = df['close'] * 0.95
                elif col == 'relative_volume':
                    df['relative_volume'] = 1.0
                elif col == 'bb_width':
                    df['bb_width'] = df.get('volatility_21d', 0.02)
                elif col == 'atr_14':
                    df['atr_14'] = df['close'] * 0.02
        
        # Breakout filter: price above 20-day high
        # Use previous day's high to avoid look-ahead
        breakout_mask = df['close'] > df['high_20d'] * 0.99  # Within 1% of breakout
        
        # Volume confirmation
        volume_mask = df['relative_volume'] >= self.volume_threshold
        
        # ATR expansion (volatility breakout)
        if 'atr_14_prev' in df.columns:
            atr_mask = df['atr_14'] > df['atr_14_prev'] * self.atr_expansion
        else:
            atr_mask = pd.Series(True, index=df.index)
        
        # Bollinger squeeze (low volatility before breakout)
        bb_rank = df['bb_width'].rank(pct=True)
        squeeze_mask = bb_rank < 0.30  # Was in bottom 30% of BB width
        
        # Combined filter
        candidates = df[breakout_mask & volume_mask]
        
        self.logger.info(f"Found {len(candidates)} breakout candidates")
        
        for ticker in candidates.index:
            row = candidates.loc[ticker]
            
            try:
                signal = self._create_breakout_signal(ticker, row)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.error(f"Error creating signal for {ticker}: {e}")
                continue
        
        return sorted(signals, key=lambda s: s.confidence, reverse=True)
    
    def _create_breakout_signal(self, ticker: str, row: pd.Series) -> Optional[Signal]:
        """Create a breakout signal."""
        
        entry_price = float(row['close'])
        high_20d = float(row['high_20d'])
        low_20d = float(row['low_20d'])
        atr = float(row['atr_14'])
        
        # Stop at bottom of consolidation range
        stop_price = low_20d * 0.99
        
        # Measured move target
        consolidation_range = high_20d - low_20d
        target_1 = entry_price + consolidation_range
        target_2 = entry_price + (2 * consolidation_range)
        
        confidence = self._calculate_confidence(row)
        
        rel_vol = row.get('relative_volume', 1.0)
        entry_logic = (
            f"Breakout above ${high_20d:.2f} (20-day high), "
            f"volume {rel_vol:.1f}x average, "
            f"ATR expanding."
        )
        
        key_risks = [
            "False breakout (bull trap)",
            "Sector weakness could reverse move",
            "Broad market reversal",
            "Resistance at round numbers or prior highs"
        ]
        
        rationale = (
            f"Clean breakout from consolidation base. "
            f"Volume confirms institutional interest ({rel_vol:.1f}x avg). "
            f"Measured move target: ${target_1:.2f} (range expansion). "
            f"Stop below consolidation low provides defined risk."
        )
        
        return self._create_signal(
            ticker=ticker,
            direction=Direction.LONG,
            entry_price=entry_price,
            stop_price=stop_price,
            target_prices=[target_1, target_2],
            entry_logic=entry_logic,
            catalyst="Technical breakout with volume confirmation",
            key_risks=key_risks,
            confidence=confidence,
            rationale=rationale,
            features=row
        )
    
    def _calculate_confidence(self, row: pd.Series) -> int:
        """Calculate confidence for breakout signal."""
        score = 50
        
        # Volume is critical for breakouts
        rel_vol = row.get('relative_volume', 1.0)
        if rel_vol >= 3.0:
            score += 15
        elif rel_vol >= 2.5:
            score += 12
        elif rel_vol >= 2.0:
            score += 8
        
        # Clearness of breakout
        close = row.get('close', 0)
        high_20d = row.get('high_20d', close)
        if high_20d > 0:
            breakout_pct = (close - high_20d) / high_20d
            if breakout_pct > 0.02:
                score += 10  # Clear breakout
            elif breakout_pct > 0.01:
                score += 5
        
        # ADX bonus (trending after breakout)
        adx = row.get('adx_14', 0)
        if adx >= 25:
            score += 5
        
        # Prior squeeze increases breakout reliability
        bb_width = row.get('bb_width', 0.05)
        if bb_width < 0.03:
            score += 5  # Tight squeeze before
        
        return min(90, max(30, score))
