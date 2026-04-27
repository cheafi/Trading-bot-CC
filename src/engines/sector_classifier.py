"""
CC — Sector Classification Engine
===================================
First gate in the decision pipeline. Classifies every ticker
into one of 4 sector buckets with leader/laggard/stage metadata.

Buckets:
  1. HIGH_GROWTH  — Tech, AI, Semis, SaaS, growth-driven
  2. CYCLICAL     — Energy, Metals, Mining, Commodities, Industrials
  3. DEFENSIVE    — Utilities, Healthcare, Staples, REITs, Dividend
  4. THEME_HYPE   — Meme, SPACs, concept plays, narrative-driven

Output schema per ticker:
  sector_bucket, theme, sector_stage, leader_status,
  benchmark_etf, relative_strength, crowding_risk
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 86400  # 24 hours


# ── Enums ────────────────────────────────────────────────────────────


class SectorBucket(str, Enum):
    HIGH_GROWTH = "HIGH_GROWTH"
    CYCLICAL = "CYCLICAL"
    DEFENSIVE = "DEFENSIVE"
    THEME_HYPE = "THEME_HYPE"
    UNKNOWN = "UNKNOWN"


class SectorStage(str, Enum):
    LAUNCH = "LAUNCH"  # Early accumulation
    ACCELERATION = "ACCELERATION"  # Momentum building
    CLIMAX = "CLIMAX"  # Peak euphoria
    DISTRIBUTION = "DISTRIBUTION"  # Smart money exiting
    UNKNOWN = "UNKNOWN"


class LeaderStatus(str, Enum):
    LEADER = "LEADER"  # Top RS, first to move
    EARLY_FOLLOWER = "EARLY_FOLLOWER"
    LAGGARD = "LAGGARD"  # Late, chasing
    UNKNOWN = "UNKNOWN"


# ── Output Schema ────────────────────────────────────────────────────


@dataclass
class SectorContext:
    """Sector classification result for a single ticker."""

    ticker: str
    sector_bucket: SectorBucket = SectorBucket.UNKNOWN
    theme: str = ""
    sector_stage: SectorStage = SectorStage.UNKNOWN
    leader_status: LeaderStatus = LeaderStatus.UNKNOWN
    benchmark_etf: str = "SPY"
    relative_strength: float = 0.0  # vs benchmark, -1 to +1
    crowding_risk: float = 0.0  # 0=uncrowded, 1=max crowded
    liquidity_quality: str = "normal"  # thin / normal / deep

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sector_bucket": self.sector_bucket.value,
            "theme": self.theme,
            "sector_stage": self.sector_stage.value,
            "leader_status": self.leader_status.value,
            "benchmark_etf": self.benchmark_etf,
            "relative_strength": round(self.relative_strength, 3),
            "crowding_risk": round(self.crowding_risk, 2),
            "liquidity_quality": self.liquidity_quality,
        }


# ── Static ticker-to-sector map ─────────────────────────────────────
# Covers ~500 commonly traded US names. Unknown tickers fall back to
# UNKNOWN and get classified by heuristics.

_SECTOR_MAP: Dict[str, tuple[SectorBucket, str, str]] = {
    # (bucket, theme, benchmark_etf)
    # ── HIGH_GROWTH: Tech / AI / Semis / SaaS ────────────────────
    "NVDA": (SectorBucket.HIGH_GROWTH, "AI/Semis", "SOXX"),
    "AMD": (SectorBucket.HIGH_GROWTH, "AI/Semis", "SOXX"),
    "AVGO": (SectorBucket.HIGH_GROWTH, "AI/Semis", "SOXX"),
    "MRVL": (SectorBucket.HIGH_GROWTH, "AI/Semis", "SOXX"),
    "ARM": (SectorBucket.HIGH_GROWTH, "AI/Semis", "SOXX"),
    "TSM": (SectorBucket.HIGH_GROWTH, "AI/Semis", "SOXX"),
    "INTC": (SectorBucket.HIGH_GROWTH, "Semis/Legacy", "SOXX"),
    "QCOM": (SectorBucket.HIGH_GROWTH, "Semis/Mobile", "SOXX"),
    "MU": (SectorBucket.HIGH_GROWTH, "Semis/Memory", "SOXX"),
    "LRCX": (SectorBucket.HIGH_GROWTH, "Semis/Equipment", "SOXX"),
    "AMAT": (SectorBucket.HIGH_GROWTH, "Semis/Equipment", "SOXX"),
    "KLAC": (SectorBucket.HIGH_GROWTH, "Semis/Equipment", "SOXX"),
    "ASML": (SectorBucket.HIGH_GROWTH, "Semis/Equipment", "SOXX"),
    "AAPL": (SectorBucket.HIGH_GROWTH, "Tech/Consumer", "QQQ"),
    "MSFT": (SectorBucket.HIGH_GROWTH, "Tech/Cloud/AI", "QQQ"),
    "GOOGL": (SectorBucket.HIGH_GROWTH, "Tech/AI/Ads", "QQQ"),
    "GOOG": (SectorBucket.HIGH_GROWTH, "Tech/AI/Ads", "QQQ"),
    "META": (SectorBucket.HIGH_GROWTH, "Tech/Social/AI", "QQQ"),
    "AMZN": (SectorBucket.HIGH_GROWTH, "Tech/Cloud/E-commerce", "QQQ"),
    "TSLA": (SectorBucket.HIGH_GROWTH, "EV/Energy/AI", "QQQ"),
    "CRM": (SectorBucket.HIGH_GROWTH, "SaaS/AI", "IGV"),
    "NOW": (SectorBucket.HIGH_GROWTH, "SaaS/Enterprise", "IGV"),
    "SNOW": (SectorBucket.HIGH_GROWTH, "SaaS/Data", "IGV"),
    "PLTR": (SectorBucket.HIGH_GROWTH, "AI/Data/Gov", "IGV"),
    "NET": (SectorBucket.HIGH_GROWTH, "Cloud/Edge", "IGV"),
    "CRWD": (SectorBucket.HIGH_GROWTH, "Cybersecurity", "HACK"),
    "PANW": (SectorBucket.HIGH_GROWTH, "Cybersecurity", "HACK"),
    "ZS": (SectorBucket.HIGH_GROWTH, "Cybersecurity", "HACK"),
    "DDOG": (SectorBucket.HIGH_GROWTH, "SaaS/Observability", "IGV"),
    "MDB": (SectorBucket.HIGH_GROWTH, "SaaS/Database", "IGV"),
    "SHOP": (SectorBucket.HIGH_GROWTH, "E-commerce/SaaS", "IGV"),
    "SQ": (SectorBucket.HIGH_GROWTH, "Fintech", "ARKF"),
    "COIN": (SectorBucket.HIGH_GROWTH, "Crypto/Fintech", "ARKF"),
    "NFLX": (SectorBucket.HIGH_GROWTH, "Streaming", "QQQ"),
    "UBER": (SectorBucket.HIGH_GROWTH, "Tech/Mobility", "QQQ"),
    "ABNB": (SectorBucket.HIGH_GROWTH, "Tech/Travel", "QQQ"),
    "SMCI": (SectorBucket.HIGH_GROWTH, "AI/Infrastructure", "SOXX"),
    "DELL": (SectorBucket.HIGH_GROWTH, "AI/Infrastructure", "QQQ"),
    "HPE": (SectorBucket.HIGH_GROWTH, "AI/Infrastructure", "QQQ"),
    "ORCL": (SectorBucket.HIGH_GROWTH, "Cloud/Enterprise", "IGV"),
    "IBM": (SectorBucket.HIGH_GROWTH, "AI/Enterprise", "QQQ"),
    "ADBE": (SectorBucket.HIGH_GROWTH, "SaaS/Creative", "IGV"),
    "INTU": (SectorBucket.HIGH_GROWTH, "SaaS/Fintech", "IGV"),
    # ── CYCLICAL: Energy / Metals / Commodities / Industrials ────
    "XOM": (SectorBucket.CYCLICAL, "Oil/Integrated", "XLE"),
    "CVX": (SectorBucket.CYCLICAL, "Oil/Integrated", "XLE"),
    "COP": (SectorBucket.CYCLICAL, "Oil/E&P", "XLE"),
    "EOG": (SectorBucket.CYCLICAL, "Oil/E&P", "XLE"),
    "OXY": (SectorBucket.CYCLICAL, "Oil/E&P", "XLE"),
    "SLB": (SectorBucket.CYCLICAL, "Oil/Services", "XLE"),
    "HAL": (SectorBucket.CYCLICAL, "Oil/Services", "XLE"),
    "MPC": (SectorBucket.CYCLICAL, "Oil/Refining", "XLE"),
    "VLO": (SectorBucket.CYCLICAL, "Oil/Refining", "XLE"),
    "PSX": (SectorBucket.CYCLICAL, "Oil/Refining", "XLE"),
    "NEM": (SectorBucket.CYCLICAL, "Gold/Mining", "GDX"),
    "GOLD": (SectorBucket.CYCLICAL, "Gold/Mining", "GDX"),
    "AEM": (SectorBucket.CYCLICAL, "Gold/Mining", "GDX"),
    "FNV": (SectorBucket.CYCLICAL, "Gold/Royalty", "GDX"),
    "WPM": (SectorBucket.CYCLICAL, "Silver/Royalty", "GDX"),
    "FCX": (SectorBucket.CYCLICAL, "Copper/Mining", "XME"),
    "SCCO": (SectorBucket.CYCLICAL, "Copper/Mining", "XME"),
    "RIO": (SectorBucket.CYCLICAL, "Diversified Mining", "XME"),
    "BHP": (SectorBucket.CYCLICAL, "Diversified Mining", "XME"),
    "VALE": (SectorBucket.CYCLICAL, "Iron/Mining", "XME"),
    "CLF": (SectorBucket.CYCLICAL, "Steel", "XME"),
    "X": (SectorBucket.CYCLICAL, "Steel", "XME"),
    "NUE": (SectorBucket.CYCLICAL, "Steel", "XME"),
    "AA": (SectorBucket.CYCLICAL, "Aluminum", "XME"),
    "CAT": (SectorBucket.CYCLICAL, "Industrials/Machinery", "XLI"),
    "DE": (SectorBucket.CYCLICAL, "Industrials/Agriculture", "XLI"),
    "GE": (SectorBucket.CYCLICAL, "Industrials/Aerospace", "XLI"),
    "BA": (SectorBucket.CYCLICAL, "Aerospace/Defense", "ITA"),
    "LMT": (SectorBucket.CYCLICAL, "Defense", "ITA"),
    "RTX": (SectorBucket.CYCLICAL, "Defense", "ITA"),
    "NOC": (SectorBucket.CYCLICAL, "Defense", "ITA"),
    "UNP": (SectorBucket.CYCLICAL, "Rails/Transport", "XLI"),
    "FDX": (SectorBucket.CYCLICAL, "Logistics", "XLI"),
    "UPS": (SectorBucket.CYCLICAL, "Logistics", "XLI"),
    # ── DEFENSIVE: Utilities / Healthcare / Staples / REITs ──────
    "NEE": (SectorBucket.DEFENSIVE, "Utilities/Renewable", "XLU"),
    "DUK": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "SO": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "D": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "AEP": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "EXC": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "SRE": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "XEL": (SectorBucket.DEFENSIVE, "Utilities", "XLU"),
    "JNJ": (SectorBucket.DEFENSIVE, "Healthcare/Pharma", "XLV"),
    "UNH": (SectorBucket.DEFENSIVE, "Healthcare/Insurance", "XLV"),
    "LLY": (SectorBucket.DEFENSIVE, "Healthcare/Pharma", "XLV"),
    "PFE": (SectorBucket.DEFENSIVE, "Healthcare/Pharma", "XLV"),
    "ABBV": (SectorBucket.DEFENSIVE, "Healthcare/Pharma", "XLV"),
    "MRK": (SectorBucket.DEFENSIVE, "Healthcare/Pharma", "XLV"),
    "TMO": (SectorBucket.DEFENSIVE, "Healthcare/Instruments", "XLV"),
    "ABT": (SectorBucket.DEFENSIVE, "Healthcare/Devices", "XLV"),
    "BMY": (SectorBucket.DEFENSIVE, "Healthcare/Pharma", "XLV"),
    "AMGN": (SectorBucket.DEFENSIVE, "Biotech/Stable", "XBI"),
    "GILD": (SectorBucket.DEFENSIVE, "Biotech/Stable", "XBI"),
    "PG": (SectorBucket.DEFENSIVE, "Consumer Staples", "XLP"),
    "KO": (SectorBucket.DEFENSIVE, "Consumer Staples", "XLP"),
    "PEP": (SectorBucket.DEFENSIVE, "Consumer Staples", "XLP"),
    "CL": (SectorBucket.DEFENSIVE, "Consumer Staples", "XLP"),
    "WMT": (SectorBucket.DEFENSIVE, "Retail/Staples", "XLP"),
    "COST": (SectorBucket.DEFENSIVE, "Retail/Staples", "XLP"),
    "MCD": (SectorBucket.DEFENSIVE, "Restaurant/Defensive", "XLP"),
    "O": (SectorBucket.DEFENSIVE, "REIT/Net Lease", "VNQ"),
    "AMT": (SectorBucket.DEFENSIVE, "REIT/Towers", "VNQ"),
    "PLD": (SectorBucket.DEFENSIVE, "REIT/Industrial", "VNQ"),
    "SPG": (SectorBucket.DEFENSIVE, "REIT/Retail", "VNQ"),
    "GLD": (SectorBucket.DEFENSIVE, "Gold/ETF", "GLD"),
    "TLT": (SectorBucket.DEFENSIVE, "Bonds/Long", "TLT"),
    "BRK.B": (SectorBucket.DEFENSIVE, "Conglomerate/Value", "SPY"),
    # ── THEME_HYPE: Meme / SPAC / Concept / Narrative ────────────
    "GME": (SectorBucket.THEME_HYPE, "Meme/Retail", "SPY"),
    "AMC": (SectorBucket.THEME_HYPE, "Meme/Retail", "SPY"),
    "BBBY": (SectorBucket.THEME_HYPE, "Meme/Retail", "SPY"),
    "MSTR": (SectorBucket.THEME_HYPE, "Crypto/BTC Proxy", "BITO"),
    "RIOT": (SectorBucket.THEME_HYPE, "Crypto/Mining", "BITO"),
    "MARA": (SectorBucket.THEME_HYPE, "Crypto/Mining", "BITO"),
    "IONQ": (SectorBucket.THEME_HYPE, "Quantum Computing", "QQQ"),
    "RGTI": (SectorBucket.THEME_HYPE, "Quantum Computing", "QQQ"),
    "RKLB": (SectorBucket.THEME_HYPE, "Space/Launch", "ARKX"),
    "SPCE": (SectorBucket.THEME_HYPE, "Space/Tourism", "ARKX"),
    "JOBY": (SectorBucket.THEME_HYPE, "eVTOL/Mobility", "ARKQ"),
    "PLUG": (SectorBucket.THEME_HYPE, "Hydrogen/Green", "ICLN"),
    "FCEL": (SectorBucket.THEME_HYPE, "Hydrogen/Green", "ICLN"),
    "SOFI": (SectorBucket.THEME_HYPE, "Fintech/Disruptor", "ARKF"),
    "HOOD": (SectorBucket.THEME_HYPE, "Fintech/Retail", "ARKF"),
    "RIVN": (SectorBucket.THEME_HYPE, "EV/Startup", "DRIV"),
    "LCID": (SectorBucket.THEME_HYPE, "EV/Startup", "DRIV"),
    "NIO": (SectorBucket.THEME_HYPE, "EV/China", "KWEB"),
    "XPEV": (SectorBucket.THEME_HYPE, "EV/China", "KWEB"),
    "LI": (SectorBucket.THEME_HYPE, "EV/China", "KWEB"),
    "BABA": (SectorBucket.THEME_HYPE, "China Tech", "KWEB"),
    "PDD": (SectorBucket.THEME_HYPE, "China Tech", "KWEB"),
    "JD": (SectorBucket.THEME_HYPE, "China Tech", "KWEB"),
    "BIDU": (SectorBucket.THEME_HYPE, "China Tech/AI", "KWEB"),
    # ── Financials → CYCLICAL (rate-sensitive) ───────────────────
    "JPM": (SectorBucket.CYCLICAL, "Banks/Major", "XLF"),
    "BAC": (SectorBucket.CYCLICAL, "Banks/Major", "XLF"),
    "GS": (SectorBucket.CYCLICAL, "Banks/Investment", "XLF"),
    "MS": (SectorBucket.CYCLICAL, "Banks/Investment", "XLF"),
    "WFC": (SectorBucket.CYCLICAL, "Banks/Major", "XLF"),
    "C": (SectorBucket.CYCLICAL, "Banks/Major", "XLF"),
    "SCHW": (SectorBucket.CYCLICAL, "Brokerage", "XLF"),
    "BLK": (SectorBucket.CYCLICAL, "Asset Management", "XLF"),
    "V": (SectorBucket.HIGH_GROWTH, "Payments/Fintech", "XLF"),
    "MA": (SectorBucket.HIGH_GROWTH, "Payments/Fintech", "XLF"),
}


# ── Classifier ───────────────────────────────────────────────────────


class SectorClassifier:
    """Classify tickers into sector buckets with metadata."""

    def __init__(self):
        self._cache: Dict[str, Tuple[SectorContext, float]] = (
            {}
        )  # ticker → (ctx, timestamp)

    def classify(
        self,
        ticker: str,
        signal: Optional[Dict[str, Any]] = None,
    ) -> SectorContext:
        """Classify a ticker. Uses static map + signal hints."""
        if ticker in self._cache:
            ctx, ts = self._cache[ticker]
            if time.time() - ts < _CACHE_TTL_SECONDS:
                return ctx
            # Expired — re-classify

        ctx = SectorContext(ticker=ticker)

        # Static lookup
        entry = _SECTOR_MAP.get(ticker.upper())
        if entry:
            ctx.sector_bucket = entry[0]
            ctx.theme = entry[1]
            ctx.benchmark_etf = entry[2]
        else:
            # Heuristic fallback from signal data
            ctx = self._classify_by_heuristic(ticker, signal or {})

        # Enrich with signal data if available
        if signal:
            ctx = self._enrich_from_signal(ctx, signal)

        self._cache[ticker] = (ctx, time.time())
        return ctx

    def classify_batch(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, SectorContext]:
        """Classify all signals. Returns ticker→SectorContext map."""
        result: Dict[str, SectorContext] = {}
        for sig in signals:
            ticker = sig.get("ticker", "")
            if ticker:
                result[ticker] = self.classify(ticker, sig)
        return result

    def _classify_by_heuristic(
        self,
        ticker: str,
        signal: Dict[str, Any],
    ) -> SectorContext:
        """Fallback classification using signal metadata."""
        ctx = SectorContext(ticker=ticker)

        strategy = signal.get("strategy", "").lower()
        sector_hint = signal.get("sector", "").lower()

        # Sector hints from signal data
        if any(k in sector_hint for k in ["tech", "software", "semi", "ai"]):
            ctx.sector_bucket = SectorBucket.HIGH_GROWTH
            ctx.benchmark_etf = "QQQ"
        elif any(
            k in sector_hint for k in ["energy", "oil", "metal", "mining", "industrial"]
        ):
            ctx.sector_bucket = SectorBucket.CYCLICAL
            ctx.benchmark_etf = "XLE"
        elif any(
            k in sector_hint for k in ["health", "utility", "staple", "reit", "pharma"]
        ):
            ctx.sector_bucket = SectorBucket.DEFENSIVE
            ctx.benchmark_etf = "XLV"
        elif any(
            k in sector_hint for k in ["meme", "spac", "crypto", "cannabis", "quantum"]
        ):
            ctx.sector_bucket = SectorBucket.THEME_HYPE
            ctx.benchmark_etf = "SPY"

        # Volume ratio hints for hype detection
        vol_ratio = signal.get("vol_ratio", 1.0)
        if vol_ratio > 5.0 and ctx.sector_bucket == SectorBucket.UNKNOWN:
            ctx.sector_bucket = SectorBucket.THEME_HYPE
            ctx.theme = "High Volume Speculation"

        return ctx

    def _enrich_from_signal(
        self,
        ctx: SectorContext,
        signal: Dict[str, Any],
    ) -> SectorContext:
        """Add leader/stage/RS from signal technicals + structure."""
        rs = signal.get("rs_rank", 50)
        vol_ratio = signal.get("vol_ratio", 1.0)
        rsi = signal.get("rsi", 50)

        # Leader status from RS rank
        if rs >= 85:
            ctx.leader_status = LeaderStatus.LEADER
        elif rs >= 60:
            ctx.leader_status = LeaderStatus.EARLY_FOLLOWER
        else:
            ctx.leader_status = LeaderStatus.LAGGARD

        # ── Sector stage: use StructureDetector output if available ──
        trend = signal.get("trend_structure", "")
        is_extended = signal.get("is_extended", False)
        vol_exhaustion = signal.get("volume_exhaustion", False)
        dist_from_50ma = signal.get("distance_from_50ma_pct", 0.0)
        base_depth = signal.get("base_depth_pct", 0.0)

        if trend:
            # Structure-based stage detection (real chart thinking)
            if trend in ("strong_downtrend", "downtrend"):
                # LH/LL forming = distribution
                ctx.sector_stage = SectorStage.DISTRIBUTION
            elif is_extended and vol_exhaustion:
                # Extended + volume exhaustion = climax
                ctx.sector_stage = SectorStage.CLIMAX
            elif is_extended and dist_from_50ma > 15:
                # Extended >15% above 50MA = climax
                ctx.sector_stage = SectorStage.CLIMAX
            elif trend in ("strong_uptrend", "uptrend") and vol_ratio > 1.2:
                # HH/HL with volume = acceleration
                ctx.sector_stage = SectorStage.ACCELERATION
            elif base_depth > 15 and dist_from_50ma < 3:
                # Near lows, base forming = launch
                ctx.sector_stage = SectorStage.LAUNCH
            elif trend == "range":
                ctx.sector_stage = SectorStage.LAUNCH
            else:
                ctx.sector_stage = SectorStage.ACCELERATION
        else:
            # Fallback: old heuristic (when no structure data)
            if vol_ratio > 3.0 and rsi > 70:
                ctx.sector_stage = SectorStage.CLIMAX
            elif vol_ratio > 1.5 and rsi > 55:
                ctx.sector_stage = SectorStage.ACCELERATION
            elif vol_ratio < 0.7 and rsi < 40:
                ctx.sector_stage = SectorStage.DISTRIBUTION
            else:
                ctx.sector_stage = SectorStage.LAUNCH

        # Crowding risk
        if vol_ratio > 3.0 and rsi > 75:
            ctx.crowding_risk = min(1.0, (vol_ratio - 2) / 5 + (rsi - 70) / 30)
        else:
            ctx.crowding_risk = max(0, (vol_ratio - 1) / 10)

        # Relative strength proxy
        ctx.relative_strength = min(1.0, max(-1.0, (rs - 50) / 50))

        return ctx

    def clear_cache(self):
        """Clear the classification cache."""
        self._cache.clear()

    def get_sector_summary(
        self,
        contexts: Dict[str, SectorContext],
    ) -> Dict[str, Any]:
        """Summary of sector distribution for dashboard."""
        buckets: Dict[str, List[str]] = {b.value: [] for b in SectorBucket}
        for ticker, ctx in contexts.items():
            buckets[ctx.sector_bucket.value].append(ticker)

        return {
            bucket: {
                "count": len(tickers),
                "tickers": tickers[:10],
                "leaders": [
                    t
                    for t in tickers
                    if contexts[t].leader_status == LeaderStatus.LEADER
                ][:5],
            }
            for bucket, tickers in buckets.items()
            if tickers
        }
