"""
TradingAI Bot - Multi-Market Universe Scanner

Covers: US, Hong Kong, Japan, and Crypto markets.

Features:
- Dynamic universe construction per market
- Real-time screening with multi-factor scoring
- Sector/industry classification
- Liquidity and volatility filters
- Cross-market correlation analysis
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd

from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MarketRegion(str, Enum):
    US = "us"
    HK = "hk"
    JP = "jp"
    CRYPTO = "crypto"


@dataclass
class UniverseAsset:
    """An asset in the trading universe."""
    ticker: str
    name: str
    market: MarketRegion
    sector: str = ""
    industry: str = ""
    market_cap: float = 0.0
    avg_volume: float = 0.0
    price: float = 0.0
    # Screening scores
    momentum_score: float = 0.0
    quality_score: float = 0.0
    value_score: float = 0.0
    composite_score: float = 0.0


# ---------------------------------------------------------------------------
# Predefined universes by market
# ---------------------------------------------------------------------------

US_MEGA_CAPS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B",
    "UNH", "JNJ", "V", "MA", "HD", "PG", "COST", "ABBV", "MRK", "PEP",
    "KO", "LLY", "AVGO", "TMO", "ACN", "MCD", "CSCO", "DHR", "ABT",
    "TXN", "NEE", "PM", "UNP", "RTX", "HON", "LOW", "COP", "AMAT",
]

# Sprint 32: expanded mid-cap + value + sector leaders
US_MID_CAPS = [
    # Semiconductors
    "MRVL", "ON", "NXPI", "KLAC", "LRCX", "MPWR", "SWKS", "QCOM",
    # Software / Cloud
    "NOW", "INTU", "ADBE", "CRM", "WDAY", "TEAM", "HUBS", "VEEV",
    "BILL", "PAYC", "PCTY", "GTLB", "MDB", "ESTC", "CFLT", "DKNG",
    # Fintech / Financials
    "GS", "MS", "JPM", "BAC", "WFC", "C", "SCHW", "BX", "KKR",
    "AXP", "PYPL", "FIS", "FISV", "GPN",
    # Healthcare / Biotech
    "ISRG", "REGN", "VRTX", "GILD", "AMGN", "BIIB", "MRNA", "BMY",
    "ZTS", "EW", "DXCM", "ALGN", "IDXX", "SYK", "MDT", "BSX",
    # Industrials / Defense
    "CAT", "DE", "GE", "LMT", "NOC", "GD", "BA", "MMM",
    "EMR", "ETN", "ITW", "PH", "ROK", "FTV",
    # Energy
    "XOM", "CVX", "SLB", "EOG", "PXD", "DVN", "OXY", "MPC",
    "PSX", "VLO", "HAL",
    # Consumer / Retail
    "NKE", "SBUX", "TGT", "WMT", "LULU", "DG", "DLTR", "ROST",
    "TJX", "CMG", "YUM", "DPZ", "WYNN", "MGM", "MAR", "HLT",
    # Media / Communication
    "DIS", "NFLX", "CMCSA", "PARA", "WBD", "SPOT", "ROKU",
    # REITs / Real Estate
    "AMT", "CCI", "PLD", "EQIX", "O", "SPG",
    # Utilities / Staples (defensive)
    "SO", "DUK", "AEP", "D", "SRE", "CL", "GIS", "K", "HSY",
]

US_GROWTH = [
    "NVDA", "AMD", "SMCI", "ARM", "PLTR", "CRWD", "PANW", "SNOW",
    "DDOG", "NET", "ZS", "MNDY", "TTD", "SHOP", "MELI", "SE",
    "NU", "COIN", "SQ", "SOFI", "HOOD", "AFRM",
    "UBER", "LYFT", "DASH", "ABNB", "RBLX", "U",
    # Sprint 32: additional growth
    "IONQ", "RGTI", "QUBT", "APP", "RDDT", "DUOL",
    "TOST", "CAVA", "BROS", "GRAB", "RIVN", "LCID",
    "JOBY", "LUNR", "RKLB", "ASTS", "SOUN", "AI",
    "PATH", "S", "OKTA", "DOCN", "DT", "GLBE",
]

US_SECTOR_ETFS = [
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLC", "XLY", "XLP",
    "XLRE", "XLU", "XLB", "SPY", "QQQ", "IWM", "DIA",
]

HK_MAJOR = [
    "0700.HK",  # Tencent
    "9988.HK",  # Alibaba
    "9618.HK",  # JD.com
    "3690.HK",  # Meituan
    "9999.HK",  # NetEase
    "1810.HK",  # Xiaomi
    "2020.HK",  # Anta Sports
    "0388.HK",  # HKEX
    "0005.HK",  # HSBC
    "1299.HK",  # AIA
    "0941.HK",  # China Mobile
    "2318.HK",  # Ping An
    "0027.HK",  # Galaxy Entertainment
    "1928.HK",  # Sands China
    "0883.HK",  # CNOOC
    "0175.HK",  # Geely Auto
    "2269.HK",  # WuXi Bio
    "9626.HK",  # Bilibili
    "0981.HK",  # SMIC
    "3968.HK",  # China Merchants Bank
    "2388.HK",  # BOC Hong Kong
    "0001.HK",  # CK Hutchison
    "0016.HK",  # Sun Hung Kai
    "1211.HK",  # BYD
    "9868.HK",  # XPeng
    "2015.HK",  # Li Auto
    "9866.HK",  # NIO
]

JP_MAJOR = [
    "7203.T",   # Toyota
    "6758.T",   # Sony
    "6861.T",   # Keyence
    "9984.T",   # SoftBank Group
    "6098.T",   # Recruit
    "8306.T",   # MUFG
    "7741.T",   # HOYA
    "9433.T",   # KDDI
    "4063.T",   # Shin-Etsu Chemical
    "6501.T",   # Hitachi
    "4568.T",   # Daiichi Sankyo
    "6902.T",   # Denso
    "7974.T",   # Nintendo
    "8035.T",   # Tokyo Electron
    "6857.T",   # Advantest
    "4519.T",   # Chugai Pharma
    "6367.T",   # Daikin
    "4661.T",   # Oriental Land
    "6954.T",   # Fanuc
    "7267.T",   # Honda
]

CRYPTO_MAJOR = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT",
    "MATIC", "LINK", "UNI", "AAVE", "MKR", "LDO", "ARB",
    "OP", "APT", "SUI", "SEI", "TIA", "NEAR", "ATOM",
    "DOGE", "SHIB", "PEPE",
]


# ---------------------------------------------------------------------------
# Universe builder
# ---------------------------------------------------------------------------

class MultiMarketUniverse:
    """
    Builds and maintains the trading universe across all markets.
    """

    def __init__(self):
        self.assets: Dict[str, UniverseAsset] = {}
        self._initialized = False

    def build_universe(
        self,
        markets: Optional[List[MarketRegion]] = None,
        include_etfs: bool = True,
    ) -> List[UniverseAsset]:
        """Build the full trading universe."""
        if markets is None:
            markets = [MarketRegion.US, MarketRegion.HK, MarketRegion.JP, MarketRegion.CRYPTO]

        assets: List[UniverseAsset] = []

        if MarketRegion.US in markets:
            for t in US_MEGA_CAPS + US_MID_CAPS + US_GROWTH:
                assets.append(UniverseAsset(
                    ticker=t, name=t, market=MarketRegion.US, sector="Equity",
                ))
            if include_etfs:
                for t in US_SECTOR_ETFS:
                    assets.append(UniverseAsset(
                        ticker=t, name=t, market=MarketRegion.US, sector="ETF",
                    ))

        if MarketRegion.HK in markets:
            for t in HK_MAJOR:
                assets.append(UniverseAsset(
                    ticker=t, name=t, market=MarketRegion.HK, sector="HK Equity",
                ))

        if MarketRegion.JP in markets:
            for t in JP_MAJOR:
                assets.append(UniverseAsset(
                    ticker=t, name=t, market=MarketRegion.JP, sector="JP Equity",
                ))

        if MarketRegion.CRYPTO in markets:
            for t in CRYPTO_MAJOR:
                assets.append(UniverseAsset(
                    ticker=t, name=t, market=MarketRegion.CRYPTO, sector="Crypto",
                ))

        # Deduplicate
        seen = set()
        unique = []
        for a in assets:
            if a.ticker not in seen:
                seen.add(a.ticker)
                unique.append(a)
                self.assets[a.ticker] = a

        self._initialized = True
        logger.info(
            f"Universe built: {len(unique)} assets "
            f"(US: {sum(1 for a in unique if a.market == MarketRegion.US)}, "
            f"HK: {sum(1 for a in unique if a.market == MarketRegion.HK)}, "
            f"JP: {sum(1 for a in unique if a.market == MarketRegion.JP)}, "
            f"Crypto: {sum(1 for a in unique if a.market == MarketRegion.CRYPTO)})"
        )
        return unique

    def get_tickers_by_market(self, market: MarketRegion) -> List[str]:
        return [a.ticker for a in self.assets.values() if a.market == market]

    def get_all_tickers(self) -> List[str]:
        return list(self.assets.keys())


# ---------------------------------------------------------------------------
# Multi-factor screener
# ---------------------------------------------------------------------------

class MultiFactorScreener:
    """
    Screens the universe using multiple factors:
    - Momentum (price returns, RSI, MACD)
    - Quality (volume, volatility, trend strength)
    - Value (relative to sector peers)
    - Composite score for ranking
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def screen(
        self,
        df: pd.DataFrame,
        universe: List[UniverseAsset],
        top_n: int = 30,
    ) -> List[UniverseAsset]:
        """
        Screen and rank assets by composite score.
        
        Args:
            df: DataFrame with columns [ticker, close, volume, rsi, adx, sma_50, ...]
            universe: List of UniverseAsset to screen
            top_n: Number of top assets to return
        """
        if df.empty:
            return universe[:top_n]

        ticker_map = {a.ticker: a for a in universe}

        for _, row in df.iterrows():
            ticker = row.get("ticker", "")
            if ticker not in ticker_map:
                continue

            asset = ticker_map[ticker]
            close = row.get("close", 0)
            sma_50 = row.get("sma_50", close)
            rsi = row.get("rsi", 50)
            adx = row.get("adx", 20)
            rel_vol = row.get("relative_volume", 1.0)

            # Momentum score: price above SMA + RSI in sweet spot
            above_sma = (close / sma_50 - 1) * 100 if sma_50 > 0 else 0
            rsi_score = 100 - abs(rsi - 60)  # peaks at RSI=60
            asset.momentum_score = (above_sma * 0.4 + rsi_score * 0.6)

            # Quality: strong trend + good volume
            asset.quality_score = (adx * 0.5 + min(rel_vol, 3.0) * 33 * 0.5)

            # Composite
            asset.composite_score = (
                asset.momentum_score * 0.5
                + asset.quality_score * 0.3
                + asset.value_score * 0.2
            )
            asset.price = close

        # Sort by composite score
        ranked = sorted(
            ticker_map.values(),
            key=lambda a: a.composite_score,
            reverse=True,
        )

        self.logger.info(f"Screened {len(ranked)} assets, top {top_n} selected")
        return ranked[:top_n]


# ---------------------------------------------------------------------------
# Cross-market correlation monitor
# ---------------------------------------------------------------------------

class CrossMarketMonitor:
    """
    Monitors cross-market correlations and regime shifts.
    
    - US/HK correlation (China tech often correlates with US tech)
    - Crypto/tech correlation
    - Yen strength → JP stock impact
    - Global risk-on/risk-off signals
    """

    def __init__(self):
        self._correlation_window = 60  # trading days

    def compute_correlations(
        self, returns: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """Compute pairwise correlation matrix from return series."""
        df = pd.DataFrame(returns)
        return df.corr()

    def detect_regime_divergence(
        self,
        us_returns: pd.Series,
        hk_returns: pd.Series,
        jp_returns: pd.Series,
        crypto_returns: pd.Series,
    ) -> Dict[str, Any]:
        """Detect when markets are diverging (opportunity or risk signal)."""
        all_returns = pd.DataFrame({
            "US": us_returns,
            "HK": hk_returns,
            "JP": jp_returns,
            "Crypto": crypto_returns,
        }).dropna()

        if len(all_returns) < 20:
            return {"status": "insufficient_data"}

        corr = all_returns.corr()
        avg_corr = corr.values[np.triu_indices_from(corr.values, 1)].mean()

        # Rolling correlation trend
        rolling_corr = all_returns["US"].rolling(20).corr(all_returns["HK"])
        corr_trend = "rising" if rolling_corr.iloc[-5:].mean() > rolling_corr.iloc[-20:-5].mean() else "falling"

        return {
            "status": "ok",
            "avg_cross_correlation": round(float(avg_corr), 3),
            "correlation_trend": corr_trend,
            "us_hk_corr": round(float(corr.loc["US", "HK"]), 3),
            "us_crypto_corr": round(float(corr.loc["US", "Crypto"]), 3),
            "regime": (
                "risk_on" if avg_corr > 0.6
                else "risk_off" if avg_corr < 0.2
                else "diverging"
            ),
        }
