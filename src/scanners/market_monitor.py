"""
Market Monitor - Comprehensive real-time market monitoring.

Orchestrates all scanners to provide:
- Multi-sector parallel scanning
- Real-time opportunity detection
- Market breadth analysis
- Risk monitoring
"""
import asyncio
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging

from .pattern_scanner import PatternScanner, ChartPattern
from .sector_scanner import SectorScanner, SectorMetrics, SectorRotation, Sector
from .momentum_scanner import MomentumScanner, MomentumAlert
from .volume_scanner import VolumeScanner, VolumeAlert

logger = logging.getLogger(__name__)


@dataclass
class MarketBreadth:
    """Market breadth indicators."""
    timestamp: datetime
    
    # Advance/Decline
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    ad_ratio: float = 1.0
    ad_line: float = 0.0
    
    # New Highs/Lows
    new_highs: int = 0
    new_lows: int = 0
    hl_ratio: float = 1.0
    
    # Percentage metrics
    pct_above_sma20: float = 50.0
    pct_above_sma50: float = 50.0
    pct_above_sma200: float = 50.0
    
    # McClellan indicators
    mcclellan_oscillator: float = 0.0
    mcclellan_summation: float = 0.0
    
    # TRIN (Arms Index)
    trin: float = 1.0
    
    # Overall assessment
    breadth_status: str = "neutral"  # bullish, bearish, neutral
    risk_level: str = "normal"  # low, normal, elevated, high


@dataclass
class MarketSnapshot:
    """Complete market snapshot."""
    timestamp: datetime
    
    # Core data
    breadth: MarketBreadth
    sector_metrics: Dict[Sector, SectorMetrics] = field(default_factory=dict)
    rotation_analysis: Optional[SectorRotation] = None
    
    # Alerts
    pattern_alerts: List[ChartPattern] = field(default_factory=list)
    momentum_alerts: List[MomentumAlert] = field(default_factory=list)
    volume_alerts: List[VolumeAlert] = field(default_factory=list)
    
    # Top movers
    top_gainers: List[Dict] = field(default_factory=list)
    top_losers: List[Dict] = field(default_factory=list)
    volume_leaders: List[Dict] = field(default_factory=list)
    
    # Summary
    market_status: str = "normal"
    key_observations: List[str] = field(default_factory=list)


class MarketMonitor:
    """
    Central market monitoring system.
    
    Coordinates all scanners to provide comprehensive
    real-time market intelligence.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Initialize scanners
        self.pattern_scanner = PatternScanner(config)
        self.sector_scanner = SectorScanner(config)
        self.momentum_scanner = MomentumScanner(config)
        self.volume_scanner = VolumeScanner(config)
        
        # State
        self.last_snapshot: Optional[MarketSnapshot] = None
        self.ad_line_history: List[float] = []
        
    async def scan_market(
        self,
        market_data: Dict[str, pd.DataFrame],
        spy_data: Optional[pd.DataFrame] = None
    ) -> MarketSnapshot:
        """
        Perform comprehensive market scan.
        
        Runs all scanners in parallel and aggregates results.
        """
        timestamp = datetime.now()
        
        # Run scanners in parallel
        breadth_task = asyncio.create_task(
            asyncio.to_thread(self._calculate_breadth, market_data)
        )
        
        sector_task = self.sector_scanner.scan_all_sectors(market_data)
        
        pattern_task = asyncio.create_task(
            asyncio.to_thread(self._scan_patterns, market_data)
        )
        
        momentum_task = asyncio.create_task(
            asyncio.to_thread(self.momentum_scanner.scan_universe, market_data, spy_data)
        )
        
        volume_task = asyncio.create_task(
            asyncio.to_thread(self.volume_scanner.scan_universe, market_data)
        )
        
        movers_task = asyncio.create_task(
            asyncio.to_thread(self.momentum_scanner.get_top_movers, market_data, 10)
        )
        
        volume_leaders_task = asyncio.create_task(
            asyncio.to_thread(self.momentum_scanner.get_volume_leaders, market_data, 10)
        )
        
        # Wait for all tasks
        results = await asyncio.gather(
            breadth_task,
            sector_task,
            pattern_task,
            momentum_task,
            volume_task,
            movers_task,
            volume_leaders_task,
            return_exceptions=True
        )
        
        breadth = results[0] if not isinstance(results[0], Exception) else MarketBreadth(timestamp=timestamp)
        sector_metrics = results[1] if not isinstance(results[1], Exception) else {}
        pattern_alerts = results[2] if not isinstance(results[2], Exception) else []
        momentum_alerts = results[3] if not isinstance(results[3], Exception) else []
        volume_alerts = results[4] if not isinstance(results[4], Exception) else []
        movers = results[5] if not isinstance(results[5], Exception) else {'gainers': [], 'losers': []}
        volume_leaders = results[6] if not isinstance(results[6], Exception) else []
        
        # Analyze sector rotation
        rotation = self.sector_scanner.analyze_rotation(sector_metrics) if sector_metrics else None
        
        # Determine market status
        market_status = self._assess_market_status(breadth, sector_metrics)
        
        # Generate key observations
        observations = self._generate_observations(
            breadth, sector_metrics, rotation,
            pattern_alerts, momentum_alerts, volume_alerts
        )
        
        snapshot = MarketSnapshot(
            timestamp=timestamp,
            breadth=breadth,
            sector_metrics=sector_metrics,
            rotation_analysis=rotation,
            pattern_alerts=pattern_alerts[:20],  # Top 20
            momentum_alerts=momentum_alerts[:20],
            volume_alerts=volume_alerts[:20],
            top_gainers=movers.get('gainers', []),
            top_losers=movers.get('losers', []),
            volume_leaders=volume_leaders,
            market_status=market_status,
            key_observations=observations
        )
        
        self.last_snapshot = snapshot
        
        return snapshot
    
    def _calculate_breadth(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> MarketBreadth:
        """Calculate market breadth indicators."""
        breadth = MarketBreadth(timestamp=datetime.now())
        
        advances = 0
        declines = 0
        unchanged = 0
        new_highs = 0
        new_lows = 0
        above_sma20 = 0
        above_sma50 = 0
        above_sma200 = 0
        total = 0
        
        for ticker, df in market_data.items():
            if len(df) < 2:
                continue
                
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            
            # Advance/Decline
            if close[-1] > close[-2] * 1.001:
                advances += 1
            elif close[-1] < close[-2] * 0.999:
                declines += 1
            else:
                unchanged += 1
            
            # New Highs/Lows (52-week)
            if len(close) >= 252:
                if close[-1] >= np.max(high[:252]):
                    new_highs += 1
                if close[-1] <= np.min(low[:252]):
                    new_lows += 1
            
            # SMA analysis
            if len(close) >= 20 and close[-1] > np.mean(close[-20:]):
                above_sma20 += 1
            if len(close) >= 50 and close[-1] > np.mean(close[-50:]):
                above_sma50 += 1
            if len(close) >= 200 and close[-1] > np.mean(close[-200:]):
                above_sma200 += 1
            
            total += 1
        
        if total == 0:
            return breadth
        
        breadth.advances = advances
        breadth.declines = declines
        breadth.unchanged = unchanged
        breadth.ad_ratio = advances / max(declines, 1)
        
        # Update A/D line
        ad_value = advances - declines
        if self.ad_line_history:
            breadth.ad_line = self.ad_line_history[-1] + ad_value
        else:
            breadth.ad_line = ad_value
        self.ad_line_history.append(breadth.ad_line)
        
        breadth.new_highs = new_highs
        breadth.new_lows = new_lows
        breadth.hl_ratio = new_highs / max(new_lows, 1)
        
        breadth.pct_above_sma20 = above_sma20 / total * 100
        breadth.pct_above_sma50 = above_sma50 / total * 100
        breadth.pct_above_sma200 = above_sma200 / total * 100
        
        # McClellan Oscillator (simplified)
        if len(self.ad_line_history) >= 39:
            ema_19 = self._ema(self.ad_line_history, 19)
            ema_39 = self._ema(self.ad_line_history, 39)
            breadth.mcclellan_oscillator = ema_19 - ema_39
        
        # TRIN (simplified)
        adv_volume = advances  # Would need actual volume data
        dec_volume = declines
        if dec_volume > 0 and declines > 0:
            breadth.trin = (advances / declines) / (adv_volume / max(dec_volume, 1))
        
        # Assess breadth status
        if breadth.ad_ratio > 2 and breadth.pct_above_sma50 > 70:
            breadth.breadth_status = "bullish"
            breadth.risk_level = "low"
        elif breadth.ad_ratio < 0.5 and breadth.pct_above_sma50 < 30:
            breadth.breadth_status = "bearish"
            breadth.risk_level = "elevated"
        else:
            breadth.breadth_status = "neutral"
            breadth.risk_level = "normal"
        
        return breadth
    
    def _scan_patterns(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> List[ChartPattern]:
        """Scan all tickers for chart patterns."""
        all_patterns = []
        
        for ticker, df in market_data.items():
            try:
                patterns = self.pattern_scanner.scan_patterns(df, ticker)
                all_patterns.extend(patterns)
            except Exception as e:
                logger.error(f"Pattern scan error for {ticker}: {e}")
                continue
        
        # Sort by confidence
        all_patterns.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_patterns
    
    def _assess_market_status(
        self,
        breadth: MarketBreadth,
        sector_metrics: Dict[Sector, SectorMetrics]
    ) -> str:
        """Assess overall market status."""
        signals = []
        
        # Breadth signals
        if breadth.ad_ratio > 2:
            signals.append('bullish')
        elif breadth.ad_ratio < 0.5:
            signals.append('bearish')
        
        if breadth.pct_above_sma200 > 70:
            signals.append('bullish')
        elif breadth.pct_above_sma200 < 30:
            signals.append('bearish')
        
        # Sector signals
        if sector_metrics:
            avg_return = np.mean([m.return_21d for m in sector_metrics.values()])
            if avg_return > 5:
                signals.append('bullish')
            elif avg_return < -5:
                signals.append('bearish')
        
        # Determine status
        bullish_count = signals.count('bullish')
        bearish_count = signals.count('bearish')
        
        if bullish_count >= 2:
            return 'risk_on'
        elif bearish_count >= 2:
            return 'risk_off'
        else:
            return 'neutral'
    
    def _generate_observations(
        self,
        breadth: MarketBreadth,
        sector_metrics: Dict[Sector, SectorMetrics],
        rotation: Optional[SectorRotation],
        patterns: List[ChartPattern],
        momentum: List[MomentumAlert],
        volume: List[VolumeAlert]
    ) -> List[str]:
        """Generate key market observations."""
        observations = []
        
        # Breadth observations
        if breadth.ad_ratio > 2:
            observations.append(f"🟢 Strong breadth: {breadth.advances} advances vs {breadth.declines} declines")
        elif breadth.ad_ratio < 0.5:
            observations.append(f"🔴 Weak breadth: {breadth.advances} advances vs {breadth.declines} declines")
        
        if breadth.new_highs > breadth.new_lows * 3:
            observations.append(f"📈 New highs dominating: {breadth.new_highs} highs vs {breadth.new_lows} lows")
        elif breadth.new_lows > breadth.new_highs * 3:
            observations.append(f"📉 New lows dominating: {breadth.new_lows} lows vs {breadth.new_highs} highs")
        
        # Sector observations
        if rotation:
            if rotation.leading_sectors:
                leaders = [s.value.replace('_', ' ').title() for s in rotation.leading_sectors[:3]]
                observations.append(f"🚀 Leading sectors: {', '.join(leaders)}")
            
            observations.append(f"📊 Market phase: {rotation.market_phase.replace('_', ' ').title()}")
        
        # Pattern observations
        if patterns:
            bullish_patterns = sum(1 for p in patterns if p.direction == 'bullish')
            bearish_patterns = sum(1 for p in patterns if p.direction == 'bearish')
            observations.append(f"📐 Patterns detected: {bullish_patterns} bullish, {bearish_patterns} bearish")
        
        # Momentum observations
        if momentum:
            breakouts = sum(1 for m in momentum if m.signal_type.value == 'breakout')
            if breakouts > 5:
                observations.append(f"💥 Multiple breakouts detected: {breakouts} stocks")
        
        # Volume observations
        if volume:
            accumulation = sum(1 for v in volume if v.signal_type.value == 'accumulation')
            distribution = sum(1 for v in volume if v.signal_type.value == 'distribution')
            if accumulation > distribution * 2:
                observations.append(f"💰 Accumulation dominance: {accumulation} vs {distribution} distribution")
            elif distribution > accumulation * 2:
                observations.append(f"⚠️ Distribution dominance: {distribution} vs {accumulation} accumulation")
        
        return observations[:10]  # Limit to 10 observations
    
    def _ema(self, data: List[float], period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return np.mean(data)
        
        multiplier = 2 / (period + 1)
        ema = data[0]
        
        for value in data[1:]:
            ema = (value - ema) * multiplier + ema
        
        return ema
    
    def get_market_summary(self) -> str:
        """Get formatted market summary."""
        if not self.last_snapshot:
            return "No market data available."
        
        snap = self.last_snapshot
        lines = []
        
        lines.append(f"📊 **Market Summary** - {snap.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"**Status:** {snap.market_status.upper()}")
        lines.append("")
        lines.append("**Breadth:**")
        lines.append(f"  • A/D Ratio: {snap.breadth.ad_ratio:.2f}")
        lines.append(f"  • % Above SMA50: {snap.breadth.pct_above_sma50:.1f}%")
        lines.append(f"  • New Highs/Lows: {snap.breadth.new_highs}/{snap.breadth.new_lows}")
        lines.append("")
        
        if snap.key_observations:
            lines.append("**Key Observations:**")
            for obs in snap.key_observations:
                lines.append(f"  {obs}")
        
        return "\n".join(lines)
    
    def get_actionable_alerts(
        self,
        min_confidence: float = 65
    ) -> List[Dict]:
        """Get actionable trading alerts."""
        if not self.last_snapshot:
            return []
        
        alerts = []
        
        # High-confidence patterns
        for pattern in self.last_snapshot.pattern_alerts:
            if pattern.confidence >= min_confidence:
                alerts.append({
                    'type': 'pattern',
                    'ticker': pattern.ticker,
                    'signal': pattern.pattern_type.value,
                    'direction': pattern.direction,
                    'confidence': pattern.confidence,
                    'entry': pattern.entry_price,
                    'target': pattern.target_price,
                    'stop': pattern.stop_loss,
                    'description': pattern.pattern_description[:100]
                })
        
        # High-confidence momentum
        for mom in self.last_snapshot.momentum_alerts:
            if mom.confidence >= min_confidence:
                alerts.append({
                    'type': 'momentum',
                    'ticker': mom.ticker,
                    'signal': mom.signal_type.value,
                    'direction': mom.direction,
                    'confidence': mom.confidence,
                    'entry': mom.current_price,
                    'targets': mom.targets,
                    'stop': mom.stop_loss,
                    'description': mom.description
                })
        
        # Sort by confidence
        alerts.sort(key=lambda x: x['confidence'], reverse=True)
        
        return alerts[:20]
