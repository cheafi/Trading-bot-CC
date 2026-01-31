"""
TradingAI Bot - Advanced Pattern Scanner

Implements advanced chart patterns inspired by:
- Mark Minervini's VCP (Volatility Contraction Pattern)
- William O'Neil's CANSLIM methodology
- Richard Wyckoff accumulation/distribution patterns
- IBD relative strength methodology

Patterns included:
- VCP (Volatility Contraction Pattern)
- Cup and Handle
- Double Bottom
- Ascending/Descending Triangles
- Bull/Bear Flags
- Tight consolidation (4-week tight)
- High Tight Flag
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of chart patterns."""
    VCP = "vcp"  # Volatility Contraction Pattern
    CUP_AND_HANDLE = "cup_and_handle"
    DOUBLE_BOTTOM = "double_bottom"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    SYMMETRICAL_TRIANGLE = "symmetrical_triangle"
    BULL_FLAG = "bull_flag"
    BEAR_FLAG = "bear_flag"
    FLAT_BASE = "flat_base"
    HIGH_TIGHT_FLAG = "high_tight_flag"
    CONSOLIDATION = "consolidation"
    BREAKOUT = "breakout"


@dataclass
class PatternMatch:
    """Represents a detected pattern."""
    pattern_type: PatternType
    symbol: str
    confidence: float  # 0-1 confidence score
    start_date: datetime
    end_date: datetime
    pivot_price: float  # Breakout/entry price level
    stop_loss: float
    target_price: Optional[float] = None
    
    # Pattern-specific metrics
    depth_pct: Optional[float] = None  # Pattern depth (for bases)
    width_days: Optional[int] = None  # Pattern width in days
    volume_contraction: Optional[float] = None  # Volume contraction ratio
    volatility_contraction: Optional[float] = None  # Volatility contraction
    
    # Additional context
    rs_rating: Optional[float] = None  # Relative strength rating
    prior_uptrend: Optional[bool] = None  # Whether preceded by uptrend


class AdvancedPatternScanner:
    """
    Advanced pattern detection engine.
    
    Features:
    - Multiple pattern detection algorithms
    - Scoring and ranking
    - Integration with relative strength
    """
    
    def __init__(
        self,
        min_pattern_days: int = 15,
        max_pattern_days: int = 65,
        min_prior_uptrend: float = 0.3,  # 30% minimum prior gain
        max_base_depth: float = 0.35,  # 35% max drawdown in base
    ):
        """
        Initialize scanner.
        
        Args:
            min_pattern_days: Minimum days for a valid pattern
            max_pattern_days: Maximum days for a pattern
            min_prior_uptrend: Minimum prior uptrend before pattern
            max_base_depth: Maximum acceptable base depth
        """
        self.min_pattern_days = min_pattern_days
        self.max_pattern_days = max_pattern_days
        self.min_prior_uptrend = min_prior_uptrend
        self.max_base_depth = max_base_depth
    
    def scan(
        self,
        price_data: Dict[str, pd.DataFrame],
        patterns: Optional[List[PatternType]] = None,
        min_confidence: float = 0.6
    ) -> List[PatternMatch]:
        """
        Scan universe for patterns.
        
        Args:
            price_data: Dict mapping ticker to OHLCV DataFrame
            patterns: List of pattern types to scan for (all if None)
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of PatternMatch objects sorted by confidence
        """
        if patterns is None:
            patterns = list(PatternType)
        
        results = []
        
        for symbol, df in price_data.items():
            if len(df) < 252:  # Need at least 1 year of data
                continue
            
            try:
                for pattern_type in patterns:
                    matches = self._detect_pattern(symbol, df, pattern_type)
                    for match in matches:
                        if match.confidence >= min_confidence:
                            results.append(match)
            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results
    
    def _detect_pattern(
        self,
        symbol: str,
        df: pd.DataFrame,
        pattern_type: PatternType
    ) -> List[PatternMatch]:
        """Detect specific pattern type."""
        
        if pattern_type == PatternType.VCP:
            return self._detect_vcp(symbol, df)
        elif pattern_type == PatternType.CUP_AND_HANDLE:
            return self._detect_cup_and_handle(symbol, df)
        elif pattern_type == PatternType.DOUBLE_BOTTOM:
            return self._detect_double_bottom(symbol, df)
        elif pattern_type == PatternType.FLAT_BASE:
            return self._detect_flat_base(symbol, df)
        elif pattern_type == PatternType.HIGH_TIGHT_FLAG:
            return self._detect_high_tight_flag(symbol, df)
        elif pattern_type == PatternType.CONSOLIDATION:
            return self._detect_consolidation(symbol, df)
        elif pattern_type == PatternType.BULL_FLAG:
            return self._detect_bull_flag(symbol, df)
        elif pattern_type == PatternType.ASCENDING_TRIANGLE:
            return self._detect_ascending_triangle(symbol, df)
        else:
            return []
    
    def _detect_vcp(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """
        Detect Volatility Contraction Pattern (VCP).
        
        VCP Criteria (Mark Minervini):
        1. Stock must be in a Stage 2 uptrend
        2. Series of contracting price ranges
        3. Volume dries up in later contractions
        4. At least 2-3 contractions
        5. Each contraction is shallower than the previous
        """
        results = []
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Check for Stage 2 uptrend (Trend Template)
        if not self._check_trend_template(df):
            return results
        
        # Look for contractions in recent data
        lookback = 65  # About 3 months
        recent_data = df.tail(lookback)
        
        if len(recent_data) < self.min_pattern_days:
            return results
        
        # Find local highs and lows
        contractions = self._find_contractions(recent_data)
        
        if len(contractions) < 2:
            return results
        
        # Check if contractions are getting tighter
        is_tightening = self._check_tightening(contractions)
        
        if not is_tightening:
            return results
        
        # Check volume contraction
        vol_contraction = self._check_volume_contraction(recent_data)
        
        # Calculate confidence score
        confidence = 0.5
        
        if len(contractions) >= 3:
            confidence += 0.15
        if is_tightening:
            confidence += 0.15
        if vol_contraction < 0.7:  # Volume down 30%+
            confidence += 0.1
        if self._check_tight_range(recent_data, days=5):
            confidence += 0.1
        
        # Calculate levels
        recent_high = recent_data['high'].max()
        recent_low = recent_data['low'].min()
        current_price = close.iloc[-1]
        
        pivot_price = recent_high
        depth_pct = (recent_high - recent_low) / recent_high
        
        # Stop loss at recent low or ATR-based
        atr = self._calculate_atr(df, period=14)
        stop_loss = max(recent_low, current_price - 2 * atr)
        
        # Target at 20% above pivot or measured move
        target_price = pivot_price * 1.20
        
        pattern = PatternMatch(
            pattern_type=PatternType.VCP,
            symbol=symbol,
            confidence=min(confidence, 1.0),
            start_date=recent_data.index[0],
            end_date=recent_data.index[-1],
            pivot_price=pivot_price,
            stop_loss=stop_loss,
            target_price=target_price,
            depth_pct=depth_pct,
            width_days=len(recent_data),
            volume_contraction=vol_contraction,
            volatility_contraction=contractions[-1][1] / contractions[0][1] if contractions[0][1] > 0 else 1.0,
            prior_uptrend=True
        )
        
        results.append(pattern)
        return results
    
    def _detect_cup_and_handle(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """
        Detect Cup and Handle pattern.
        
        Criteria:
        1. U-shaped cup (not V-shaped)
        2. Depth between 12-35%
        3. Handle forms in upper half of cup
        4. Handle drifts down slightly
        5. Volume contracts in handle
        """
        results = []
        
        close = df['close']
        lookback = 126  # About 6 months for cup
        
        if len(df) < lookback:
            return results
        
        recent = df.tail(lookback)
        
        # Find potential cup structure
        cup = self._find_cup_structure(recent)
        
        if cup is None:
            return results
        
        left_lip, bottom, right_lip, handle_low = cup
        
        # Check depth (12-35%)
        depth = (left_lip - bottom) / left_lip
        if depth < 0.12 or depth > 0.35:
            return results
        
        # Check if U-shaped (not V)
        if not self._is_u_shaped(recent, bottom):
            return results
        
        # Check handle in upper half
        if handle_low < bottom + 0.5 * (right_lip - bottom):
            return results
        
        # Calculate confidence
        confidence = 0.5
        
        if 0.15 <= depth <= 0.30:  # Ideal depth
            confidence += 0.15
        if self._check_volume_pattern_cup(recent, cup):
            confidence += 0.15
        if self._is_u_shaped(recent, bottom):
            confidence += 0.1
        
        # Price levels
        current = close.iloc[-1]
        pivot = right_lip
        stop_loss = handle_low * 0.95
        target = right_lip + (right_lip - bottom)  # Measured move
        
        pattern = PatternMatch(
            pattern_type=PatternType.CUP_AND_HANDLE,
            symbol=symbol,
            confidence=min(confidence, 1.0),
            start_date=recent.index[0],
            end_date=recent.index[-1],
            pivot_price=pivot,
            stop_loss=stop_loss,
            target_price=target,
            depth_pct=depth,
            width_days=len(recent),
        )
        
        results.append(pattern)
        return results
    
    def _detect_double_bottom(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """
        Detect Double Bottom pattern.
        
        Criteria:
        1. Two distinct lows at similar levels
        2. Peak between bottoms (neckline)
        3. Second bottom may be slightly higher
        4. Volume higher on second test or breakout
        """
        results = []
        
        close = df['close']
        low = df['low']
        volume = df['volume']
        
        lookback = 63  # About 3 months
        recent = df.tail(lookback)
        
        if len(recent) < 20:
            return results
        
        # Find two distinct lows
        bottoms = self._find_local_minima(recent['low'], min_separation=10)
        
        if len(bottoms) < 2:
            return results
        
        # Take the two most recent significant bottoms
        bottom1_idx, bottom1_price = bottoms[-2]
        bottom2_idx, bottom2_price = bottoms[-1]
        
        # Bottoms should be within 3% of each other
        if abs(bottom2_price - bottom1_price) / bottom1_price > 0.03:
            return results
        
        # Find neckline (peak between bottoms)
        between_section = recent.iloc[bottom1_idx:bottom2_idx+1]
        if len(between_section) < 3:
            return results
        
        neckline = between_section['high'].max()
        neckline_idx = between_section['high'].idxmax()
        
        # Neckline should be at least 5% above bottoms
        if (neckline - bottom1_price) / bottom1_price < 0.05:
            return results
        
        # Calculate confidence
        confidence = 0.5
        
        # Bottoms are very close in price
        if abs(bottom2_price - bottom1_price) / bottom1_price < 0.02:
            confidence += 0.15
        
        # Volume higher on second bottom (shows accumulation)
        vol1 = volume.iloc[bottom1_idx]
        vol2 = volume.iloc[bottom2_idx]
        if vol2 > vol1:
            confidence += 0.1
        
        # Second bottom slightly higher (better sign)
        if bottom2_price > bottom1_price:
            confidence += 0.1
        
        # Pattern levels
        pivot = neckline
        stop_loss = min(bottom1_price, bottom2_price) * 0.98
        target = neckline + (neckline - min(bottom1_price, bottom2_price))
        
        pattern = PatternMatch(
            pattern_type=PatternType.DOUBLE_BOTTOM,
            symbol=symbol,
            confidence=min(confidence, 0.95),
            start_date=recent.index[0],
            end_date=recent.index[-1],
            pivot_price=pivot,
            stop_loss=stop_loss,
            target_price=target,
            depth_pct=(neckline - bottom1_price) / neckline,
            width_days=bottom2_idx - bottom1_idx,
        )
        
        results.append(pattern)
        return results
    
    def _detect_flat_base(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """
        Detect Flat Base pattern.
        
        Criteria (William O'Neil):
        1. Tight consolidation
        2. Less than 15% depth
        3. Usually after a prior base breakout
        4. At least 5 weeks long
        """
        results = []
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        lookback = 35  # About 7 weeks
        recent = df.tail(lookback)
        
        if len(recent) < 25:
            return results
        
        # Calculate range
        range_high = recent['high'].max()
        range_low = recent['low'].min()
        depth = (range_high - range_low) / range_high
        
        # Depth must be less than 15%
        if depth > 0.15:
            return results
        
        # Check if preceded by advance
        prior = df.iloc[-lookback-63:-lookback]  # 3 months before base
        if len(prior) < 20:
            return results
        
        prior_advance = (prior['close'].iloc[-1] - prior['close'].iloc[0]) / prior['close'].iloc[0]
        if prior_advance < 0.15:  # Needs at least 15% prior advance
            return results
        
        # Calculate confidence
        confidence = 0.5
        
        if depth < 0.10:
            confidence += 0.2
        if prior_advance > 0.25:
            confidence += 0.15
        if self._check_volume_contraction(recent) < 0.6:
            confidence += 0.1
        
        current = close.iloc[-1]
        pivot = range_high
        stop_loss = range_low * 0.98
        target = pivot * 1.20
        
        pattern = PatternMatch(
            pattern_type=PatternType.FLAT_BASE,
            symbol=symbol,
            confidence=min(confidence, 0.95),
            start_date=recent.index[0],
            end_date=recent.index[-1],
            pivot_price=pivot,
            stop_loss=stop_loss,
            target_price=target,
            depth_pct=depth,
            width_days=len(recent),
        )
        
        results.append(pattern)
        return results
    
    def _detect_high_tight_flag(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """
        Detect High Tight Flag pattern.
        
        Criteria (William O'Neil):
        1. Stock doubles (100%+ gain) in 4-8 weeks
        2. Corrects no more than 10-25%
        3. Forms a tight flag pattern
        4. One of the most powerful patterns
        """
        results = []
        
        close = df['close']
        
        # Look for 100%+ move in 40 days
        lookback = 60
        if len(df) < lookback + 20:
            return results
        
        # Find rapid advance
        for i in range(20, 45):
            start_price = close.iloc[-lookback]
            peak_price = close.iloc[-lookback+i:-lookback+i+5].max()
            gain = (peak_price - start_price) / start_price
            
            if gain >= 1.0:  # 100%+ gain
                # Check for tight flag after
                flag_section = df.iloc[-lookback+i+5:]
                if len(flag_section) < 10:
                    continue
                
                flag_high = flag_section['high'].max()
                flag_low = flag_section['low'].min()
                correction = (flag_high - flag_low) / flag_high
                
                # Correction must be 10-25%
                if 0.10 <= correction <= 0.25:
                    confidence = 0.7  # High confidence pattern
                    
                    if correction < 0.20:
                        confidence += 0.1
                    if self._check_volume_contraction(flag_section) < 0.5:
                        confidence += 0.1
                    
                    pivot = flag_high
                    stop_loss = flag_low * 0.97
                    target = pivot * 1.50  # HTF often leads to big moves
                    
                    pattern = PatternMatch(
                        pattern_type=PatternType.HIGH_TIGHT_FLAG,
                        symbol=symbol,
                        confidence=min(confidence, 0.95),
                        start_date=df.index[-lookback],
                        end_date=df.index[-1],
                        pivot_price=pivot,
                        stop_loss=stop_loss,
                        target_price=target,
                        depth_pct=correction,
                        width_days=len(flag_section),
                    )
                    results.append(pattern)
                    break
        
        return results
    
    def _detect_consolidation(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """Detect tight consolidation / 4-week tight pattern."""
        results = []
        
        close = df['close']
        lookback = 20  # 4 weeks
        
        recent = df.tail(lookback)
        if len(recent) < 15:
            return results
        
        # Calculate weekly closes (approx)
        weekly_closes = close.iloc[::5].tail(4)
        
        if len(weekly_closes) < 4:
            return results
        
        # Check if weekly closes are within 2%
        max_close = weekly_closes.max()
        min_close = weekly_closes.min()
        range_pct = (max_close - min_close) / max_close
        
        if range_pct > 0.02:  # More than 2% range
            return results
        
        confidence = 0.6
        if range_pct < 0.015:
            confidence += 0.15
        if self._check_volume_contraction(recent) < 0.5:
            confidence += 0.1
        
        pivot = recent['high'].max()
        stop_loss = recent['low'].min() * 0.98
        target = pivot * 1.15
        
        pattern = PatternMatch(
            pattern_type=PatternType.CONSOLIDATION,
            symbol=symbol,
            confidence=min(confidence, 0.90),
            start_date=recent.index[0],
            end_date=recent.index[-1],
            pivot_price=pivot,
            stop_loss=stop_loss,
            target_price=target,
            depth_pct=range_pct,
            width_days=len(recent),
        )
        results.append(pattern)
        return results
    
    def _detect_bull_flag(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """
        Detect Bull Flag pattern.
        
        Criteria:
        1. Strong upward move (pole)
        2. Consolidation that slopes slightly down
        3. Volume decreases during flag
        4. Breakout on volume
        """
        results = []
        
        close = df['close']
        lookback = 30
        
        if len(df) < lookback + 20:
            return results
        
        recent = df.tail(lookback)
        
        # Find pole (strong move up)
        for pole_len in range(5, 15):
            pole_section = df.iloc[-lookback:-lookback+pole_len]
            pole_gain = (pole_section['close'].iloc[-1] - pole_section['close'].iloc[0]) / pole_section['close'].iloc[0]
            
            if pole_gain >= 0.15:  # At least 15% pole
                # Check for flag (slight downward or sideways drift)
                flag_section = df.iloc[-lookback+pole_len:]
                if len(flag_section) < 5:
                    continue
                
                flag_trend = np.polyfit(range(len(flag_section)), flag_section['close'].values, 1)[0]
                
                # Flag should be slightly down or flat
                if flag_trend > 0:  # Upward = not a flag
                    continue
                
                flag_depth = (flag_section['high'].max() - flag_section['low'].min()) / flag_section['high'].max()
                
                if flag_depth > 0.10:  # Flag too deep
                    continue
                
                confidence = 0.55
                if pole_gain > 0.25:
                    confidence += 0.15
                if flag_depth < 0.05:
                    confidence += 0.1
                if self._check_volume_contraction(flag_section) < 0.6:
                    confidence += 0.1
                
                pivot = flag_section['high'].max()
                stop_loss = flag_section['low'].min() * 0.98
                target = pivot + (pole_section['close'].iloc[-1] - pole_section['close'].iloc[0])  # Measured move
                
                pattern = PatternMatch(
                    pattern_type=PatternType.BULL_FLAG,
                    symbol=symbol,
                    confidence=min(confidence, 0.90),
                    start_date=pole_section.index[0],
                    end_date=flag_section.index[-1],
                    pivot_price=pivot,
                    stop_loss=stop_loss,
                    target_price=target,
                    depth_pct=flag_depth,
                    width_days=len(flag_section),
                )
                results.append(pattern)
                break
        
        return results
    
    def _detect_ascending_triangle(self, symbol: str, df: pd.DataFrame) -> List[PatternMatch]:
        """Detect Ascending Triangle pattern."""
        results = []
        
        high = df['high']
        low = df['low']
        lookback = 40
        
        recent = df.tail(lookback)
        if len(recent) < 20:
            return results
        
        # Find horizontal resistance (multiple touches at similar level)
        highs = recent['high'].values
        resistance_candidates = self._find_horizontal_level(highs, tolerance=0.02)
        
        if not resistance_candidates:
            return results
        
        resistance = max(resistance_candidates)
        
        # Check for rising lows (higher lows)
        lows = self._find_local_minima(recent['low'], min_separation=5)
        
        if len(lows) < 3:
            return results
        
        # Check if lows are ascending
        low_prices = [l[1] for l in lows]
        if not all(low_prices[i] <= low_prices[i+1] for i in range(len(low_prices)-1)):
            return results
        
        confidence = 0.6
        
        # More touches at resistance = higher confidence
        touches = sum(1 for h in highs if abs(h - resistance) / resistance < 0.02)
        if touches >= 3:
            confidence += 0.15
        
        pivot = resistance
        stop_loss = low_prices[-1] * 0.98
        triangle_height = resistance - low_prices[0]
        target = resistance + triangle_height
        
        pattern = PatternMatch(
            pattern_type=PatternType.ASCENDING_TRIANGLE,
            symbol=symbol,
            confidence=min(confidence, 0.85),
            start_date=recent.index[0],
            end_date=recent.index[-1],
            pivot_price=pivot,
            stop_loss=stop_loss,
            target_price=target,
            width_days=len(recent),
        )
        results.append(pattern)
        return results
    
    # ========== Helper Methods ==========
    
    def _check_trend_template(self, df: pd.DataFrame) -> bool:
        """
        Check Mark Minervini's Trend Template criteria.
        
        1. Price above 50 & 200-day MA
        2. 50-day MA above 200-day MA
        3. 200-day MA trending up for at least 1 month
        4. Price at least 25% above 52-week low
        5. Price within 25% of 52-week high
        """
        close = df['close']
        
        if len(df) < 252:
            return False
        
        current = close.iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1]
        sma_200_1m_ago = close.rolling(200).mean().iloc[-21]
        
        high_52w = close.rolling(252).max().iloc[-1]
        low_52w = close.rolling(252).min().iloc[-1]
        
        # Check criteria
        if current < sma_50 or current < sma_200:
            return False
        if sma_50 < sma_200:
            return False
        if sma_200 < sma_200_1m_ago:
            return False
        if (current - low_52w) / low_52w < 0.25:
            return False
        if (high_52w - current) / high_52w > 0.25:
            return False
        
        return True
    
    def _find_contractions(self, df: pd.DataFrame) -> List[Tuple[int, float]]:
        """Find price contractions (volatility contractions)."""
        contractions = []
        close = df['close']
        high = df['high']
        low = df['low']
        
        window = 10
        for i in range(0, len(df) - window, window // 2):
            section = df.iloc[i:i+window]
            range_pct = (section['high'].max() - section['low'].min()) / section['high'].max()
            contractions.append((i, range_pct))
        
        return contractions
    
    def _check_tightening(self, contractions: List[Tuple[int, float]]) -> bool:
        """Check if contractions are getting tighter over time."""
        if len(contractions) < 2:
            return False
        
        ranges = [c[1] for c in contractions]
        
        # Each contraction should be smaller than average of previous
        for i in range(1, len(ranges)):
            if ranges[i] >= np.mean(ranges[:i]) * 1.1:  # Allow 10% tolerance
                continue  # Not strictly tightening, but close
        
        # Overall trend should be down
        return ranges[-1] < ranges[0] * 0.8  # Last contraction < 80% of first
    
    def _check_volume_contraction(self, df: pd.DataFrame) -> float:
        """Calculate volume contraction ratio."""
        if len(df) < 20:
            return 1.0
        
        vol = df['volume']
        recent_avg = vol.tail(10).mean()
        prior_avg = vol.head(10).mean()
        
        if prior_avg > 0:
            return recent_avg / prior_avg
        return 1.0
    
    def _check_tight_range(self, df: pd.DataFrame, days: int = 5) -> bool:
        """Check for tight price range in recent days."""
        recent = df.tail(days)
        range_pct = (recent['high'].max() - recent['low'].min()) / recent['high'].max()
        return range_pct < 0.03  # Less than 3% range
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]
    
    def _find_cup_structure(self, df: pd.DataFrame) -> Optional[Tuple[float, float, float, float]]:
        """Find cup and handle structure. Returns (left_lip, bottom, right_lip, handle_low)."""
        close = df['close']
        low = df['low']
        
        # Find left lip (high near start)
        left_section = df.head(20)
        left_lip = left_section['high'].max()
        
        # Find bottom (lowest point in middle)
        middle_section = df.iloc[15:-15]
        if len(middle_section) < 10:
            return None
        bottom = middle_section['low'].min()
        
        # Find right lip (high near end but before handle)
        right_section = df.iloc[-30:-10]
        if len(right_section) < 5:
            return None
        right_lip = right_section['high'].max()
        
        # Find handle low
        handle_section = df.tail(10)
        handle_low = handle_section['low'].min()
        
        # Validate structure
        if bottom > min(left_lip, right_lip) * 0.9:  # Cup not deep enough
            return None
        if abs(left_lip - right_lip) / left_lip > 0.05:  # Lips too uneven
            return None
        
        return (left_lip, bottom, right_lip, handle_low)
    
    def _is_u_shaped(self, df: pd.DataFrame, bottom: float) -> bool:
        """Check if cup is U-shaped (not V-shaped)."""
        close = df['close']
        
        # Find where bottom occurs
        bottom_idx = df['low'].idxmin()
        bottom_pos = df.index.get_loc(bottom_idx)
        
        # Count days near bottom
        near_bottom_count = sum(1 for p in close if abs(p - bottom) / bottom < 0.05)
        
        # U-shaped should have multiple days near bottom
        return near_bottom_count >= 5
    
    def _check_volume_pattern_cup(self, df: pd.DataFrame, cup: Tuple) -> bool:
        """Check volume pattern for cup and handle."""
        volume = df['volume']
        
        # Volume should be high at left lip, dry up at bottom, increase on right side
        third = len(df) // 3
        
        left_vol = volume.head(third).mean()
        middle_vol = volume.iloc[third:2*third].mean()
        right_vol = volume.tail(third).mean()
        
        return middle_vol < left_vol and right_vol > middle_vol
    
    def _find_local_minima(
        self, 
        series: pd.Series, 
        min_separation: int = 5
    ) -> List[Tuple[int, float]]:
        """Find local minima in a series."""
        minima = []
        values = series.values
        
        for i in range(min_separation, len(values) - min_separation):
            if values[i] == min(values[i-min_separation:i+min_separation+1]):
                # Check if far enough from last minimum
                if not minima or i - minima[-1][0] >= min_separation:
                    minima.append((i, values[i]))
        
        return minima
    
    def _find_horizontal_level(
        self, 
        prices: np.ndarray, 
        tolerance: float = 0.02
    ) -> List[float]:
        """Find horizontal support/resistance levels."""
        levels = []
        
        # Cluster prices
        sorted_prices = sorted(prices)
        current_cluster = [sorted_prices[0]]
        
        for price in sorted_prices[1:]:
            if abs(price - current_cluster[-1]) / current_cluster[-1] < tolerance:
                current_cluster.append(price)
            else:
                if len(current_cluster) >= 3:  # At least 3 touches
                    levels.append(np.mean(current_cluster))
                current_cluster = [price]
        
        if len(current_cluster) >= 3:
            levels.append(np.mean(current_cluster))
        
        return levels
