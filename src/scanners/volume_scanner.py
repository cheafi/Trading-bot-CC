"""
Volume Scanner - Volume-based analysis and alerts.

Analyzes volume patterns to identify:
- Accumulation/Distribution
- Volume climax patterns
- Unusual activity
- Institutional footprints
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VolumeSignal(str, Enum):
    """Types of volume signals."""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    CLIMAX_TOP = "climax_top"
    CLIMAX_BOTTOM = "climax_bottom"
    BREAKOUT_VOLUME = "breakout_volume"
    DRY_UP = "dry_up"
    INSTITUTIONAL = "institutional"


@dataclass
class VolumeAlert:
    """Volume-based alert."""
    ticker: str
    signal_type: VolumeSignal
    direction: str
    
    current_volume: int
    avg_volume: int
    volume_ratio: float
    
    price: float
    price_change: float
    
    confidence: float
    detected_at: datetime
    description: str
    
    # Additional metrics
    obv_trend: str = "neutral"
    money_flow: float = 0.0
    smart_money_indicator: float = 0.0


class VolumeScanner:
    """
    Scans for volume-based trading opportunities.
    
    Features:
    - Volume spike detection
    - Accumulation/distribution analysis
    - On-Balance Volume trends
    - Money flow analysis
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.spike_threshold = self.config.get('spike_threshold', 2.5)
        self.dry_up_threshold = self.config.get('dry_up_threshold', 0.3)
        
    def scan_universe(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> List[VolumeAlert]:
        """Scan universe for volume signals."""
        alerts = []
        
        for ticker, df in market_data.items():
            try:
                ticker_alerts = self._analyze_volume(ticker, df)
                alerts.extend(ticker_alerts)
            except Exception as e:
                logger.error(f"Error analyzing {ticker} volume: {e}")
                continue
        
        alerts.sort(key=lambda x: x.confidence, reverse=True)
        return alerts
    
    def _analyze_volume(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> List[VolumeAlert]:
        """Analyze volume for a single ticker."""
        alerts = []
        
        if len(df) < 30 or 'volume' not in df.columns:
            return alerts
            
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        current_price = close[-1]
        current_volume = volume[-1]
        avg_volume = np.mean(volume[-20:])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        price_change = (close[-1] - close[-2]) / close[-2] * 100 if len(close) >= 2 else 0
        
        # Calculate indicators
        obv = self._calculate_obv(close, volume)
        obv_trend = "up" if obv[-1] > obv[-10] else "down" if obv[-1] < obv[-10] else "neutral"
        
        money_flow = self._calculate_money_flow(high, low, close, volume)
        
        # Smart Money Indicator (volume-weighted price movement)
        smi = self._calculate_smart_money(close, volume)
        
        # 1. Volume Spike Analysis
        if volume_ratio >= self.spike_threshold:
            # Determine if accumulation or distribution
            if price_change > 0.5:
                signal_type = VolumeSignal.ACCUMULATION
                direction = 'bullish'
                desc = f"Heavy accumulation: {volume_ratio:.1f}x volume on +{price_change:.1f}% move"
            elif price_change < -0.5:
                signal_type = VolumeSignal.DISTRIBUTION
                direction = 'bearish'
                desc = f"Heavy distribution: {volume_ratio:.1f}x volume on {price_change:.1f}% move"
            else:
                signal_type = VolumeSignal.INSTITUTIONAL
                direction = 'neutral'
                desc = f"Unusual volume: {volume_ratio:.1f}x normal, minimal price movement"
            
            alerts.append(VolumeAlert(
                ticker=ticker,
                signal_type=signal_type,
                direction=direction,
                current_volume=int(current_volume),
                avg_volume=int(avg_volume),
                volume_ratio=volume_ratio,
                price=current_price,
                price_change=price_change,
                confidence=min(85, 50 + volume_ratio * 5),
                detected_at=datetime.now(),
                description=desc,
                obv_trend=obv_trend,
                money_flow=money_flow,
                smart_money_indicator=smi
            ))
        
        # 2. Climax Detection
        if volume_ratio >= 3.0:
            # Climax top: huge volume + up day after sustained rally
            if price_change > 0 and np.sum(close[-10:-1] > close[-11:-2]) >= 7:
                alerts.append(VolumeAlert(
                    ticker=ticker,
                    signal_type=VolumeSignal.CLIMAX_TOP,
                    direction='bearish',
                    current_volume=int(current_volume),
                    avg_volume=int(avg_volume),
                    volume_ratio=volume_ratio,
                    price=current_price,
                    price_change=price_change,
                    confidence=70,
                    detected_at=datetime.now(),
                    description="Potential climax top: exhaustion volume after rally",
                    obv_trend=obv_trend,
                    money_flow=money_flow,
                    smart_money_indicator=smi
                ))
            
            # Climax bottom: huge volume + down day after sustained decline
            elif price_change < 0 and np.sum(close[-10:-1] < close[-11:-2]) >= 7:
                alerts.append(VolumeAlert(
                    ticker=ticker,
                    signal_type=VolumeSignal.CLIMAX_BOTTOM,
                    direction='bullish',
                    current_volume=int(current_volume),
                    avg_volume=int(avg_volume),
                    volume_ratio=volume_ratio,
                    price=current_price,
                    price_change=price_change,
                    confidence=70,
                    detected_at=datetime.now(),
                    description="Potential climax bottom: capitulation volume after decline",
                    obv_trend=obv_trend,
                    money_flow=money_flow,
                    smart_money_indicator=smi
                ))
        
        # 3. Volume Dry-Up (potential breakout setup)
        if volume_ratio <= self.dry_up_threshold:
            # Low volume consolidation
            recent_range = (np.max(high[-5:]) - np.min(low[-5:])) / close[-5] * 100
            
            if recent_range < 3:  # Tight consolidation
                alerts.append(VolumeAlert(
                    ticker=ticker,
                    signal_type=VolumeSignal.DRY_UP,
                    direction='neutral',
                    current_volume=int(current_volume),
                    avg_volume=int(avg_volume),
                    volume_ratio=volume_ratio,
                    price=current_price,
                    price_change=price_change,
                    confidence=55,
                    detected_at=datetime.now(),
                    description=f"Volume dry-up: {volume_ratio:.2f}x normal in tight {recent_range:.1f}% range",
                    obv_trend=obv_trend,
                    money_flow=money_flow,
                    smart_money_indicator=smi
                ))
        
        # 4. Breakout Volume Confirmation
        high_20d = np.max(high[-20:])
        low_20d = np.min(low[-20:])
        
        if current_price > high_20d * 0.99 and volume_ratio >= 1.5:
            alerts.append(VolumeAlert(
                ticker=ticker,
                signal_type=VolumeSignal.BREAKOUT_VOLUME,
                direction='bullish',
                current_volume=int(current_volume),
                avg_volume=int(avg_volume),
                volume_ratio=volume_ratio,
                price=current_price,
                price_change=price_change,
                confidence=min(80, 55 + volume_ratio * 5),
                detected_at=datetime.now(),
                description=f"Breakout with {volume_ratio:.1f}x volume confirmation",
                obv_trend=obv_trend,
                money_flow=money_flow,
                smart_money_indicator=smi
            ))
        
        return alerts
    
    def _calculate_obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """Calculate On-Balance Volume."""
        obv = np.zeros(len(close))
        obv[0] = volume[0]
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        return obv
    
    def _calculate_money_flow(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        period: int = 14
    ) -> float:
        """Calculate Money Flow Index."""
        typical_price = (high + low + close) / 3
        raw_money_flow = typical_price * volume
        
        positive_flow = 0
        negative_flow = 0
        
        for i in range(-period, 0):
            if typical_price[i] > typical_price[i-1]:
                positive_flow += raw_money_flow[i]
            else:
                negative_flow += raw_money_flow[i]
        
        if negative_flow == 0:
            return 100
        
        money_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_ratio))
        
        return mfi
    
    def _calculate_smart_money(
        self,
        close: np.ndarray,
        volume: np.ndarray
    ) -> float:
        """
        Calculate Smart Money Indicator.
        
        Compares opening action (retail) vs closing action (institutional).
        Positive = smart money accumulating
        Negative = smart money distributing
        """
        if len(close) < 20:
            return 0.0
        
        # Simplification: compare volume on up days vs down days
        changes = np.diff(close[-20:])
        volumes = volume[-19:]
        
        up_volume = np.sum(volumes[changes > 0])
        down_volume = np.sum(volumes[changes < 0])
        
        total = up_volume + down_volume
        if total == 0:
            return 0
        
        return (up_volume - down_volume) / total * 100
    
    def get_accumulation_distribution(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> List[Dict]:
        """
        Rank stocks by accumulation/distribution.
        
        Returns list sorted by A/D score.
        """
        scores = []
        
        for ticker, df in market_data.items():
            if len(df) < 30 or 'volume' not in df.columns:
                continue
                
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values
            
            # A/D Line
            clv = ((close - low) - (high - close)) / (high - low + 0.0001)
            ad_line = np.cumsum(clv * volume)
            
            # Score based on recent A/D trend
            ad_change = (ad_line[-1] - ad_line[-21]) / abs(ad_line[-21] + 1) * 100
            
            scores.append({
                'ticker': ticker,
                'ad_score': ad_change,
                'status': 'accumulation' if ad_change > 5 else 'distribution' if ad_change < -5 else 'neutral',
                'price': close[-1],
                'price_change_21d': (close[-1] - close[-21]) / close[-21] * 100 if len(close) >= 21 else 0
            })
        
        scores.sort(key=lambda x: x['ad_score'], reverse=True)
        
        return scores
