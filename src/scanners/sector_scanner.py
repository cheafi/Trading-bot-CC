"""
Sector Scanner - Parallel scanning across different market sectors.

Enables monitoring of multiple sectors, industries, and asset classes
to identify rotation, relative strength, and sector-specific opportunities.
"""
import asyncio
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Sector(str, Enum):
    """Market sectors for scanning."""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    INDUSTRIALS = "industrials"
    ENERGY = "energy"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    MATERIALS = "materials"
    COMMUNICATION = "communication"
    
    # Additional categories
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    FOREX = "forex"
    BONDS = "bonds"
    ETFS = "etfs"


@dataclass
class SectorMetrics:
    """Metrics for a market sector."""
    sector: Sector
    timestamp: datetime
    
    # Performance metrics
    return_1d: float = 0.0
    return_5d: float = 0.0
    return_21d: float = 0.0
    return_63d: float = 0.0
    
    # Relative strength
    relative_strength: float = 0.0  # vs SPY
    rs_rank: int = 0  # 1-11 ranking
    
    # Breadth indicators
    pct_above_sma20: float = 0.0
    pct_above_sma50: float = 0.0
    pct_above_sma200: float = 0.0
    advance_decline_ratio: float = 1.0
    
    # Momentum
    avg_rsi: float = 50.0
    pct_overbought: float = 0.0  # RSI > 70
    pct_oversold: float = 0.0   # RSI < 30
    
    # Volatility
    avg_volatility: float = 0.0
    volatility_rank: int = 0
    
    # Volume
    volume_ratio: float = 1.0  # vs 20-day avg
    
    # Trend
    trend_direction: str = "neutral"  # bullish, bearish, neutral
    trend_strength: float = 50.0


@dataclass
class SectorRotation:
    """Sector rotation analysis."""
    timestamp: datetime
    
    # Leading/lagging sectors
    leading_sectors: List[Sector] = field(default_factory=list)
    lagging_sectors: List[Sector] = field(default_factory=list)
    improving_sectors: List[Sector] = field(default_factory=list)
    weakening_sectors: List[Sector] = field(default_factory=list)
    
    # Rotation phase
    market_phase: str = "unknown"  # early_bull, late_bull, early_bear, late_bear
    defensive_offensive_ratio: float = 1.0
    
    # Recommendations
    overweight: List[Sector] = field(default_factory=list)
    underweight: List[Sector] = field(default_factory=list)
    analysis: str = ""


# Sector ETF mappings
SECTOR_ETFS = {
    Sector.TECHNOLOGY: "XLK",
    Sector.HEALTHCARE: "XLV",
    Sector.FINANCIALS: "XLF",
    Sector.CONSUMER_DISCRETIONARY: "XLY",
    Sector.CONSUMER_STAPLES: "XLP",
    Sector.INDUSTRIALS: "XLI",
    Sector.ENERGY: "XLE",
    Sector.UTILITIES: "XLU",
    Sector.REAL_ESTATE: "XLRE",
    Sector.MATERIALS: "XLB",
    Sector.COMMUNICATION: "XLC",
}

# Sector constituents (top holdings)
SECTOR_STOCKS = {
    Sector.TECHNOLOGY: ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "ACN", "CSCO"],
    Sector.HEALTHCARE: ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY"],
    Sector.FINANCIALS: ["BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "BLK"],
    Sector.CONSUMER_DISCRETIONARY: ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "CMG"],
    Sector.CONSUMER_STAPLES: ["PG", "KO", "PEP", "COST", "WMT", "PM", "MDLZ", "MO", "CL", "KMB"],
    Sector.INDUSTRIALS: ["CAT", "RTX", "HON", "UNP", "BA", "UPS", "DE", "GE", "LMT", "MMM"],
    Sector.ENERGY: ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "PSX", "VLO", "OXY"],
    Sector.UTILITIES: ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
    Sector.REAL_ESTATE: ["PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL", "DLR", "AVB"],
    Sector.MATERIALS: ["LIN", "APD", "SHW", "FCX", "ECL", "NEM", "CTVA", "DOW", "NUE", "VMC"],
    Sector.COMMUNICATION: ["META", "GOOGL", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "ATVI", "EA"],
}


class SectorScanner:
    """
    Scans market sectors in parallel to identify:
    - Sector rotation patterns
    - Relative strength leaders/laggards
    - Breadth divergences
    - Sector-specific opportunities
    """
    
    DEFENSIVE_SECTORS = [Sector.UTILITIES, Sector.CONSUMER_STAPLES, Sector.HEALTHCARE]
    CYCLICAL_SECTORS = [Sector.TECHNOLOGY, Sector.CONSUMER_DISCRETIONARY, Sector.FINANCIALS, Sector.INDUSTRIALS]
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.sector_data: Dict[Sector, pd.DataFrame] = {}
        self.metrics_cache: Dict[Sector, SectorMetrics] = {}
        
    async def scan_all_sectors(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> Dict[Sector, SectorMetrics]:
        """
        Scan all sectors in parallel.
        
        Args:
            market_data: Dict of ticker -> OHLCV DataFrame
            
        Returns:
            Dict of Sector -> SectorMetrics
        """
        tasks = []
        
        for sector in Sector:
            if sector in SECTOR_STOCKS:
                task = self._analyze_sector(sector, market_data)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics = {}
        for result in results:
            if isinstance(result, SectorMetrics):
                metrics[result.sector] = result
                self.metrics_cache[result.sector] = result
            elif isinstance(result, Exception):
                logger.error(f"Sector scan error: {result}")
                
        # Calculate relative rankings
        self._calculate_rankings(metrics)
        
        return metrics
    
    async def _analyze_sector(
        self,
        sector: Sector,
        market_data: Dict[str, pd.DataFrame]
    ) -> SectorMetrics:
        """Analyze a single sector."""
        stocks = SECTOR_STOCKS.get(sector, [])
        
        if not stocks:
            return SectorMetrics(sector=sector, timestamp=datetime.now())
        
        # Collect data for sector stocks
        sector_returns_1d = []
        sector_returns_5d = []
        sector_returns_21d = []
        sector_rsi = []
        above_sma20 = 0
        above_sma50 = 0
        above_sma200 = 0
        advances = 0
        declines = 0
        total_volume_ratio = 0
        count = 0
        
        for ticker in stocks:
            if ticker not in market_data:
                continue
                
            df = market_data[ticker]
            if len(df) < 5:
                continue
                
            close = df['close'].values
            volume = df['volume'].values if 'volume' in df.columns else np.ones(len(close))
            
            # Returns
            if len(close) >= 2:
                sector_returns_1d.append((close[-1] - close[-2]) / close[-2] * 100)
            if len(close) >= 6:
                sector_returns_5d.append((close[-1] - close[-6]) / close[-6] * 100)
            if len(close) >= 22:
                sector_returns_21d.append((close[-1] - close[-22]) / close[-22] * 100)
            
            # SMAs
            if len(close) >= 20:
                sma20 = np.mean(close[-20:])
                if close[-1] > sma20:
                    above_sma20 += 1
            if len(close) >= 50:
                sma50 = np.mean(close[-50:])
                if close[-1] > sma50:
                    above_sma50 += 1
            if len(close) >= 200:
                sma200 = np.mean(close[-200:])
                if close[-1] > sma200:
                    above_sma200 += 1
            
            # RSI
            if len(close) >= 15:
                rsi = self._calculate_rsi(close)
                sector_rsi.append(rsi)
            
            # Advance/Decline
            if len(close) >= 2:
                if close[-1] > close[-2]:
                    advances += 1
                else:
                    declines += 1
            
            # Volume ratio
            if len(volume) >= 20:
                avg_vol = np.mean(volume[-20:])
                if avg_vol > 0:
                    total_volume_ratio += volume[-1] / avg_vol
                    
            count += 1
        
        if count == 0:
            return SectorMetrics(sector=sector, timestamp=datetime.now())
        
        # Calculate averages
        avg_return_1d = np.mean(sector_returns_1d) if sector_returns_1d else 0
        avg_return_5d = np.mean(sector_returns_5d) if sector_returns_5d else 0
        avg_return_21d = np.mean(sector_returns_21d) if sector_returns_21d else 0
        avg_rsi = np.mean(sector_rsi) if sector_rsi else 50
        
        # Trend direction
        if avg_return_5d > 1 and avg_return_21d > 3:
            trend = "bullish"
            trend_strength = min(100, 50 + avg_return_21d * 2)
        elif avg_return_5d < -1 and avg_return_21d < -3:
            trend = "bearish"
            trend_strength = min(100, 50 + abs(avg_return_21d) * 2)
        else:
            trend = "neutral"
            trend_strength = 50
        
        return SectorMetrics(
            sector=sector,
            timestamp=datetime.now(),
            return_1d=avg_return_1d,
            return_5d=avg_return_5d,
            return_21d=avg_return_21d,
            pct_above_sma20=above_sma20 / count * 100 if count > 0 else 0,
            pct_above_sma50=above_sma50 / count * 100 if count > 0 else 0,
            pct_above_sma200=above_sma200 / count * 100 if count > 0 else 0,
            advance_decline_ratio=advances / max(declines, 1),
            avg_rsi=avg_rsi,
            pct_overbought=sum(1 for r in sector_rsi if r > 70) / len(sector_rsi) * 100 if sector_rsi else 0,
            pct_oversold=sum(1 for r in sector_rsi if r < 30) / len(sector_rsi) * 100 if sector_rsi else 0,
            volume_ratio=total_volume_ratio / count if count > 0 else 1,
            trend_direction=trend,
            trend_strength=trend_strength
        )
    
    def _calculate_rankings(self, metrics: Dict[Sector, SectorMetrics]) -> None:
        """Calculate relative rankings for sectors."""
        # Sort by 21-day return for RS ranking
        sorted_sectors = sorted(
            metrics.items(),
            key=lambda x: x[1].return_21d,
            reverse=True
        )
        
        for rank, (sector, metric) in enumerate(sorted_sectors, 1):
            metric.rs_rank = rank
    
    def analyze_rotation(
        self,
        metrics: Dict[Sector, SectorMetrics]
    ) -> SectorRotation:
        """
        Analyze sector rotation patterns.
        
        Identifies:
        - Leading sectors (strong and improving)
        - Lagging sectors (weak and declining)
        - Rotation phase (early/late bull/bear)
        """
        rotation = SectorRotation(timestamp=datetime.now())
        
        if not metrics:
            return rotation
        
        # Sort by relative strength
        sorted_by_rs = sorted(
            metrics.items(),
            key=lambda x: x[1].return_21d,
            reverse=True
        )
        
        # Leading: Top 3 by RS with positive momentum
        rotation.leading_sectors = [
            s for s, m in sorted_by_rs[:4]
            if m.return_5d > 0 and m.return_21d > 0
        ]
        
        # Lagging: Bottom 3 by RS with negative momentum
        rotation.lagging_sectors = [
            s for s, m in sorted_by_rs[-4:]
            if m.return_5d < 0 or m.return_21d < 0
        ]
        
        # Improving: Return_5d improving relative to return_21d
        rotation.improving_sectors = [
            s for s, m in metrics.items()
            if m.return_5d > m.return_21d / 4  # Recent outperformance
        ]
        
        # Weakening: Return_5d lagging return_21d
        rotation.weakening_sectors = [
            s for s, m in metrics.items()
            if m.return_5d < m.return_21d / 4 and m.return_21d > 0
        ]
        
        # Market phase analysis
        defensive_avg = np.mean([
            metrics[s].return_21d for s in self.DEFENSIVE_SECTORS
            if s in metrics
        ]) if any(s in metrics for s in self.DEFENSIVE_SECTORS) else 0
        
        cyclical_avg = np.mean([
            metrics[s].return_21d for s in self.CYCLICAL_SECTORS
            if s in metrics
        ]) if any(s in metrics for s in self.CYCLICAL_SECTORS) else 0
        
        rotation.defensive_offensive_ratio = defensive_avg / cyclical_avg if cyclical_avg != 0 else 1
        
        # Determine market phase
        if cyclical_avg > 5 and defensive_avg > 0:
            rotation.market_phase = "early_bull"
        elif cyclical_avg > 0 and defensive_avg > cyclical_avg:
            rotation.market_phase = "late_bull"
        elif cyclical_avg < -5 and defensive_avg < 0:
            rotation.market_phase = "early_bear"
        elif cyclical_avg < 0 and defensive_avg > cyclical_avg:
            rotation.market_phase = "late_bear"
        else:
            rotation.market_phase = "transition"
        
        # Recommendations
        if rotation.market_phase == "early_bull":
            rotation.overweight = [Sector.TECHNOLOGY, Sector.CONSUMER_DISCRETIONARY, Sector.FINANCIALS]
            rotation.underweight = [Sector.UTILITIES, Sector.CONSUMER_STAPLES]
        elif rotation.market_phase == "late_bull":
            rotation.overweight = [Sector.ENERGY, Sector.MATERIALS, Sector.INDUSTRIALS]
            rotation.underweight = [Sector.TECHNOLOGY, Sector.CONSUMER_DISCRETIONARY]
        elif rotation.market_phase == "early_bear":
            rotation.overweight = [Sector.UTILITIES, Sector.HEALTHCARE, Sector.CONSUMER_STAPLES]
            rotation.underweight = [Sector.TECHNOLOGY, Sector.FINANCIALS]
        elif rotation.market_phase == "late_bear":
            rotation.overweight = [Sector.TECHNOLOGY, Sector.CONSUMER_DISCRETIONARY]
            rotation.underweight = [Sector.ENERGY, Sector.MATERIALS]
        
        # Generate analysis
        rotation.analysis = self._generate_rotation_analysis(rotation, metrics)
        
        return rotation
    
    def _generate_rotation_analysis(
        self,
        rotation: SectorRotation,
        metrics: Dict[Sector, SectorMetrics]
    ) -> str:
        """Generate human-readable rotation analysis."""
        lines = []
        
        lines.append(f"📊 **Sector Rotation Analysis** - {rotation.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"**Market Phase:** {rotation.market_phase.replace('_', ' ').title()}")
        lines.append("")
        
        if rotation.leading_sectors:
            leaders = [s.value.replace('_', ' ').title() for s in rotation.leading_sectors]
            lines.append(f"🚀 **Leading Sectors:** {', '.join(leaders)}")
        
        if rotation.lagging_sectors:
            laggards = [s.value.replace('_', ' ').title() for s in rotation.lagging_sectors]
            lines.append(f"📉 **Lagging Sectors:** {', '.join(laggards)}")
        
        lines.append("")
        lines.append("**Recommendations:**")
        
        if rotation.overweight:
            ow = [s.value.replace('_', ' ').title() for s in rotation.overweight]
            lines.append(f"  ✅ Overweight: {', '.join(ow)}")
        
        if rotation.underweight:
            uw = [s.value.replace('_', ' ').title() for s in rotation.underweight]
            lines.append(f"  ⚠️ Underweight: {', '.join(uw)}")
        
        return "\n".join(lines)
    
    def get_sector_heatmap(
        self,
        metrics: Dict[Sector, SectorMetrics]
    ) -> pd.DataFrame:
        """
        Generate sector heatmap data for visualization.
        """
        data = []
        
        for sector, m in metrics.items():
            data.append({
                'Sector': sector.value.replace('_', ' ').title(),
                '1D %': round(m.return_1d, 2),
                '5D %': round(m.return_5d, 2),
                '21D %': round(m.return_21d, 2),
                'RS Rank': m.rs_rank,
                'Trend': m.trend_direction,
                'RSI': round(m.avg_rsi, 1),
                '% > SMA50': round(m.pct_above_sma50, 1),
                'Volume': round(m.volume_ratio, 2)
            })
        
        return pd.DataFrame(data).sort_values('RS Rank')
    
    def _calculate_rsi(self, close: np.ndarray, period: int = 14) -> float:
        """Calculate RSI."""
        deltas = np.diff(close)
        gain = np.where(deltas > 0, deltas, 0)
        loss = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
