"""
Momentum Scanner - Real-time high-probability opportunity detection.

Scans markets for:
- Momentum breakouts
- Relative strength leaders
- Volume surges
- Gap and go setups
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MomentumSignalType(str, Enum):
    """Types of momentum signals."""
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    GAP_UP = "gap_up"
    GAP_DOWN = "gap_down"
    VOLUME_SURGE = "volume_surge"
    RS_NEW_HIGH = "rs_new_high"
    TREND_ACCELERATION = "trend_acceleration"
    MEAN_REVERSION = "mean_reversion"


@dataclass
class MomentumAlert:
    """Real-time momentum alert."""
    ticker: str
    signal_type: MomentumSignalType
    direction: str  # 'bullish' or 'bearish'
    
    # Price data
    current_price: float
    trigger_price: float
    change_percent: float
    
    # Signal strength
    confidence: float  # 0-100
    volume_confirmation: bool
    trend_aligned: bool
    
    # Context
    detected_at: datetime
    description: str
    
    # Relative metrics
    relative_strength: float = 0.0
    sector: str = ""
    
    # Action levels
    entry_zone: tuple = (0.0, 0.0)  # (low, high)
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)


class MomentumScanner:
    """
    High-probability momentum opportunity scanner.
    
    Features:
    - Real-time breakout detection
    - Volume surge alerts
    - Gap analysis
    - Relative strength rankings
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.min_volume_surge = self.config.get('min_volume_surge', 2.0)
        self.min_gap_percent = self.config.get('min_gap_percent', 2.0)
        self.breakout_threshold = self.config.get('breakout_threshold', 0.02)
        
    def scan_universe(
        self,
        market_data: Dict[str, pd.DataFrame],
        spy_data: Optional[pd.DataFrame] = None
    ) -> List[MomentumAlert]:
        """
        Scan entire universe for momentum opportunities.
        
        Args:
            market_data: Dict of ticker -> OHLCV DataFrame
            spy_data: Optional SPY data for relative strength
            
        Returns:
            List of MomentumAlert objects sorted by confidence
        """
        alerts = []
        
        # Calculate SPY performance for RS
        spy_return = 0
        if spy_data is not None and len(spy_data) >= 21:
            spy_return = (spy_data['close'].iloc[-1] - spy_data['close'].iloc[-21]) / spy_data['close'].iloc[-21] * 100
        
        for ticker, df in market_data.items():
            try:
                ticker_alerts = self._scan_ticker(ticker, df, spy_return)
                alerts.extend(ticker_alerts)
            except Exception as e:
                logger.error(f"Error scanning {ticker}: {e}")
                continue
        
        # Sort by confidence
        alerts.sort(key=lambda x: x.confidence, reverse=True)
        
        return alerts
    
    def _scan_ticker(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_return: float = 0
    ) -> List[MomentumAlert]:
        """Scan a single ticker for momentum signals."""
        alerts = []
        
        if len(df) < 20:
            return alerts
            
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_ = df['open'].values
        volume = df['volume'].values if 'volume' in df.columns else np.ones(len(close))
        
        current_price = close[-1]
        
        # Calculate metrics
        high_20d = np.max(high[-20:])
        low_20d = np.min(low[-20:])
        avg_volume = np.mean(volume[-20:])
        current_volume = volume[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Returns
        return_1d = (close[-1] - close[-2]) / close[-2] * 100 if len(close) >= 2 else 0
        return_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) >= 6 else 0
        return_21d = (close[-1] - close[-22]) / close[-22] * 100 if len(close) >= 22 else 0
        
        # Relative strength
        rs = return_21d - spy_return
        
        # 1. Breakout Detection
        if current_price > high_20d * 0.99:  # Within 1% of 20-day high
            breakout_strength = (current_price - high_20d) / high_20d * 100
            
            alert = MomentumAlert(
                ticker=ticker,
                signal_type=MomentumSignalType.BREAKOUT,
                direction='bullish',
                current_price=current_price,
                trigger_price=high_20d,
                change_percent=breakout_strength,
                confidence=self._calculate_breakout_confidence(df, volume_ratio, breakout_strength),
                volume_confirmation=volume_ratio >= 1.5,
                trend_aligned=return_21d > 0,
                detected_at=datetime.now(),
                description=f"Breaking above 20-day high of ${high_20d:.2f}",
                relative_strength=rs,
                entry_zone=(current_price * 0.99, current_price * 1.01),
                stop_loss=low_20d,
                targets=[
                    current_price + (high_20d - low_20d),
                    current_price + 2 * (high_20d - low_20d)
                ]
            )
            alerts.append(alert)
        
        # Breakdown Detection
        if current_price < low_20d * 1.01:
            breakdown_strength = (low_20d - current_price) / low_20d * 100
            
            alert = MomentumAlert(
                ticker=ticker,
                signal_type=MomentumSignalType.BREAKDOWN,
                direction='bearish',
                current_price=current_price,
                trigger_price=low_20d,
                change_percent=-breakdown_strength,
                confidence=self._calculate_breakout_confidence(df, volume_ratio, breakdown_strength),
                volume_confirmation=volume_ratio >= 1.5,
                trend_aligned=return_21d < 0,
                detected_at=datetime.now(),
                description=f"Breaking below 20-day low of ${low_20d:.2f}",
                relative_strength=rs,
                entry_zone=(current_price * 0.99, current_price * 1.01),
                stop_loss=high_20d,
                targets=[
                    current_price - (high_20d - low_20d),
                    current_price - 2 * (high_20d - low_20d)
                ]
            )
            alerts.append(alert)
        
        # 2. Gap Detection
        if len(open_) >= 2:
            gap_percent = (open_[-1] - close[-2]) / close[-2] * 100
            
            if abs(gap_percent) >= self.min_gap_percent:
                direction = 'bullish' if gap_percent > 0 else 'bearish'
                signal_type = MomentumSignalType.GAP_UP if gap_percent > 0 else MomentumSignalType.GAP_DOWN
                
                alert = MomentumAlert(
                    ticker=ticker,
                    signal_type=signal_type,
                    direction=direction,
                    current_price=current_price,
                    trigger_price=close[-2],
                    change_percent=gap_percent,
                    confidence=min(80, 50 + abs(gap_percent) * 3),
                    volume_confirmation=volume_ratio >= 1.5,
                    trend_aligned=(gap_percent > 0 and return_21d > 0) or (gap_percent < 0 and return_21d < 0),
                    detected_at=datetime.now(),
                    description=f"Gap {'up' if gap_percent > 0 else 'down'} {abs(gap_percent):.1f}%",
                    relative_strength=rs,
                    entry_zone=(low[-1], high[-1]),
                    stop_loss=close[-2] if gap_percent > 0 else close[-2],
                    targets=[current_price * 1.05, current_price * 1.10] if gap_percent > 0 else [current_price * 0.95, current_price * 0.90]
                )
                alerts.append(alert)
        
        # 3. Volume Surge Detection
        if volume_ratio >= self.min_volume_surge:
            direction = 'bullish' if return_1d > 0 else 'bearish'
            
            alert = MomentumAlert(
                ticker=ticker,
                signal_type=MomentumSignalType.VOLUME_SURGE,
                direction=direction,
                current_price=current_price,
                trigger_price=close[-2] if len(close) >= 2 else current_price,
                change_percent=return_1d,
                confidence=min(75, 45 + volume_ratio * 5),
                volume_confirmation=True,
                trend_aligned=True,
                detected_at=datetime.now(),
                description=f"Volume {volume_ratio:.1f}x normal with {return_1d:+.1f}% move",
                relative_strength=rs,
                entry_zone=(current_price * 0.98, current_price * 1.02),
                stop_loss=low[-1] * 0.98 if direction == 'bullish' else high[-1] * 1.02,
                targets=[]
            )
            alerts.append(alert)
        
        # 4. Relative Strength New High
        if rs > 10 and return_21d > 15:  # Significantly outperforming
            alert = MomentumAlert(
                ticker=ticker,
                signal_type=MomentumSignalType.RS_NEW_HIGH,
                direction='bullish',
                current_price=current_price,
                trigger_price=close[-22] if len(close) >= 22 else current_price,
                change_percent=return_21d,
                confidence=min(80, 50 + rs),
                volume_confirmation=volume_ratio >= 1.0,
                trend_aligned=True,
                detected_at=datetime.now(),
                description=f"Strong RS: +{return_21d:.1f}% vs SPY +{spy_return:.1f}%",
                relative_strength=rs,
                entry_zone=(current_price * 0.97, current_price * 1.01),
                stop_loss=current_price * 0.92,
                targets=[current_price * 1.10, current_price * 1.20]
            )
            alerts.append(alert)
        
        # 5. Trend Acceleration
        if len(close) >= 21:
            sma_10 = np.mean(close[-10:])
            sma_20 = np.mean(close[-20:])
            
            # Accelerating uptrend
            if (current_price > sma_10 > sma_20 and
                return_5d > return_21d / 4 and
                return_5d > 3):
                
                alert = MomentumAlert(
                    ticker=ticker,
                    signal_type=MomentumSignalType.TREND_ACCELERATION,
                    direction='bullish',
                    current_price=current_price,
                    trigger_price=sma_10,
                    change_percent=return_5d,
                    confidence=65,
                    volume_confirmation=volume_ratio >= 1.0,
                    trend_aligned=True,
                    detected_at=datetime.now(),
                    description=f"Uptrend accelerating: +{return_5d:.1f}% in 5 days",
                    relative_strength=rs,
                    entry_zone=(sma_10, current_price * 1.02),
                    stop_loss=sma_20 * 0.98,
                    targets=[current_price * 1.08, current_price * 1.15]
                )
                alerts.append(alert)
        
        return alerts
    
    def _calculate_breakout_confidence(
        self,
        df: pd.DataFrame,
        volume_ratio: float,
        breakout_strength: float
    ) -> float:
        """Calculate confidence for breakout signal."""
        confidence = 50
        
        # Volume boost
        if volume_ratio >= 3.0:
            confidence += 20
        elif volume_ratio >= 2.0:
            confidence += 15
        elif volume_ratio >= 1.5:
            confidence += 10
        
        # Breakout strength
        if breakout_strength > 3:
            confidence += 10
        elif breakout_strength > 1:
            confidence += 5
        
        # Trend alignment
        close = df['close'].values
        if len(close) >= 50:
            sma_50 = np.mean(close[-50:])
            if close[-1] > sma_50:
                confidence += 5
        
        return min(95, confidence)
    
    def get_top_movers(
        self,
        market_data: Dict[str, pd.DataFrame],
        n: int = 10
    ) -> Dict:
        """
        Get top gainers and losers.
        """
        gainers = []
        losers = []
        
        for ticker, df in market_data.items():
            if len(df) < 2:
                continue
                
            close = df['close'].values
            change = (close[-1] - close[-2]) / close[-2] * 100
            
            gainers.append((ticker, change, close[-1]))
            losers.append((ticker, change, close[-1]))
        
        gainers.sort(key=lambda x: x[1], reverse=True)
        losers.sort(key=lambda x: x[1])
        
        return {
            'gainers': [
                {'ticker': t, 'change': c, 'price': p}
                for t, c, p in gainers[:n]
            ],
            'losers': [
                {'ticker': t, 'change': c, 'price': p}
                for t, c, p in losers[:n]
            ]
        }
    
    def get_volume_leaders(
        self,
        market_data: Dict[str, pd.DataFrame],
        n: int = 10
    ) -> List[Dict]:
        """Get stocks with highest relative volume."""
        leaders = []
        
        for ticker, df in market_data.items():
            if len(df) < 20 or 'volume' not in df.columns:
                continue
                
            volume = df['volume'].values
            avg_volume = np.mean(volume[-20:])
            current_volume = volume[-1]
            ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            close = df['close'].values
            change = (close[-1] - close[-2]) / close[-2] * 100 if len(close) >= 2 else 0
            
            leaders.append({
                'ticker': ticker,
                'volume_ratio': ratio,
                'change': change,
                'price': close[-1],
                'volume': current_volume
            })
        
        leaders.sort(key=lambda x: x['volume_ratio'], reverse=True)
        
        return leaders[:n]
