"""
RS Hub Engine — Sprint 72
===========================
Relative Strength ranking engine providing:
  - RS leaderboard across all scan tickers
  - Leader / Follower / Laggard classification
  - RS lifecycle state (Emerging → Confirmed → Extended → Fading → Broken)
  - RS quality / tradeability / sustainability scoring
  - Sector-level RS aggregation
  - RS + setup quality matrix
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ── RS Lifecycle States ──────────────────────────────────────────────────────

RS_STATES = {
    "EMERGING":          "RS turning positive, early leadership signal",
    "CONFIRMED_LEADER":  "RS sustained above 120 for 20+ days",
    "MATURE_LEADER":     "RS high but slope flattening",
    "EXTENDED":          "RS very high, risk of mean reversion",
    "FADING":            "RS declining from leadership",
    "BROKEN":            "RS dropped below 95 from leadership",
    "LAGGARD":           "RS consistently below benchmark",
    "NEUTRAL":           "RS near benchmark, no edge",
}


@dataclass
class RSProfile:
    """Full RS profile for one ticker."""
    ticker: str = ""
    rank: int = 0

    # Core RS values
    rs_composite: float = 100.0
    rs_1m: float = 100.0
    rs_3m: float = 100.0
    rs_6m: float = 100.0
    rs_slope: float = 0.0
    rs_status: str = "NEUTRAL"

    # Lifecycle state
    rs_state: str = "NEUTRAL"

    # Leadership classification
    leadership: str = "NEUTRAL"  # LEADER / FOLLOWER / LAGGARD

    # Quality layers (0-100)
    rs_quality: float = 50.0       # How strong is RS
    rs_tradeability: float = 50.0  # Is it tradeable now
    rs_sustainability: float = 50.0  # Will it persist

    # Context
    sector: str = "—"
    sector_etf: str = "SPY"
    mcap_bucket: str = "—"
    setup_type: str = "—"
    action: str = "WAIT"

    # Deltas
    rs_delta_20d: float = 0.0
    rs_delta_60d: float = 0.0

    # RS velocity & acceleration
    rs_velocity: float = 0.0       # slope magnitude
    rs_acceleration: float = 0.0   # slope change

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "rank": self.rank,
            "rs_composite": self.rs_composite,
            "rs_1m": self.rs_1m,
            "rs_3m": self.rs_3m,
            "rs_6m": self.rs_6m,
            "rs_slope": self.rs_slope,
            "rs_status": self.rs_status,
            "rs_state": self.rs_state,
            "rs_state_desc": RS_STATES.get(self.rs_state, ""),
            "leadership": self.leadership,
            "rs_quality": round(self.rs_quality, 1),
            "rs_tradeability": round(self.rs_tradeability, 1),
            "rs_sustainability": round(self.rs_sustainability, 1),
            "sector": self.sector,
            "sector_etf": self.sector_etf,
            "mcap_bucket": self.mcap_bucket,
            "setup_type": self.setup_type,
            "action": self.action,
            "rs_delta_20d": round(self.rs_delta_20d, 1),
            "rs_delta_60d": round(self.rs_delta_60d, 1),
            "rs_velocity": round(self.rs_velocity, 2),
            "rs_acceleration": round(self.rs_acceleration, 2),
        }


# ── Sector / MCap mappings ──────────────────────────────────────────────────

SECTOR_MAP: Dict[str, str] = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AVGO": "Technology", "ORCL": "Technology", "CRM": "Technology",
    "AMD": "Technology", "CSCO": "Technology", "ADBE": "Technology",
    "INTC": "Technology", "TXN": "Technology", "QCOM": "Technology",
    "INTU": "Technology", "AMAT": "Technology", "NOW": "Technology",
    "META": "Communication", "GOOGL": "Communication", "NFLX": "Communication",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary", "NKE": "Consumer Discretionary",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
    "MS": "Financials", "V": "Financials", "MA": "Financials",
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "LLY": "Healthcare", "MRK": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "LIN": "Materials", "APD": "Materials",
    "NEE": "Utilities", "DUK": "Utilities",
    "PLD": "Real Estate", "AMT": "Real Estate",
    "CAT": "Industrials", "BA": "Industrials", "GE": "Industrials",
    "HON": "Industrials", "UPS": "Industrials",
    "PG": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "WMT": "Consumer Staples",
}

SECTOR_ETF_MAP: Dict[str, str] = {
    "Technology": "XLK", "Communication": "XLC",
    "Consumer Discretionary": "XLY", "Financials": "XLF",
    "Healthcare": "XLV", "Energy": "XLE", "Materials": "XLB",
    "Utilities": "XLU", "Real Estate": "XLRE",
    "Industrials": "XLI", "Consumer Staples": "XLP",
}

# Semis get SMH override
_SEMI_TICKERS = {"NVDA", "AMD", "INTC", "AVGO", "TXN", "QCOM", "AMAT", "TSM", "MU"}

MCAP_BUCKETS: Dict[str, str] = {
    "AAPL": "Mega", "MSFT": "Mega", "NVDA": "Mega", "GOOGL": "Mega",
    "AMZN": "Mega", "META": "Mega", "TSLA": "Large", "JPM": "Large",
    "V": "Large", "UNH": "Large", "JNJ": "Large", "XOM": "Large",
    "PG": "Large", "HD": "Large", "MA": "Large", "BAC": "Large",
    "AVGO": "Large", "LLY": "Large", "ABBV": "Large", "CRM": "Large",
    "AMD": "Large", "NFLX": "Large", "ORCL": "Large", "GS": "Large",
    "ADBE": "Large", "QCOM": "Large", "CSCO": "Large", "CAT": "Large",
}


def _get_sector(ticker: str) -> str:
    return SECTOR_MAP.get(ticker, "Other")


def _get_sector_etf(ticker: str) -> str:
    if ticker in _SEMI_TICKERS:
        return "SMH"
    sector = _get_sector(ticker)
    return SECTOR_ETF_MAP.get(sector, "SPY")


def _get_mcap(ticker: str) -> str:
    return MCAP_BUCKETS.get(ticker, "Mid")


# ── Core RS Engine ───────────────────────────────────────────────────────────

def classify_rs_state(
    composite: float,
    slope: float,
    rs_1m: float,
    rs_3m: float,
) -> str:
    """Determine RS lifecycle state."""
    if composite < 80:
        return "LAGGARD"
    if composite < 95:
        return "BROKEN" if slope < -2 else "NEUTRAL"
    if composite < 105:
        return "EMERGING" if slope > 3 else "NEUTRAL"
    if composite < 120:
        if slope > 2:
            return "EMERGING"
        return "FADING" if slope < -2 else "CONFIRMED_LEADER"
    # composite >= 120
    if slope > 2:
        return "CONFIRMED_LEADER"
    if slope > 0:
        return "EXTENDED" if composite > 150 else "MATURE_LEADER"
    return "FADING" if slope < -3 else "MATURE_LEADER"


def classify_leadership(composite: float, sector_avg: float) -> str:
    """Leader / Follower / Laggard relative to sector."""
    if composite >= 115 and composite > sector_avg + 10:
        return "LEADER"
    return "FOLLOWER" if composite >= 95 else "LAGGARD"


def compute_rs_quality(composite: float, slope: float) -> float:
    """0-100: How strong is RS right now."""
    base = min(50, max(0, (composite - 80) * 1.25))
    slope_bonus = min(30, max(0, slope * 5))
    consistency = 20 if composite > 110 and slope >= 0 else 10 if composite > 100 else 0
    return min(100, base + slope_bonus + consistency)


def compute_rs_tradeability(
    composite: float,
    slope: float,
    rsi: Optional[float],
    volume_ok: bool,
    above_ma: bool,
) -> float:
    """0-100: Is this RS strength tradeable right now."""
    score = 0.0
    # RS base (0-30)
    if composite >= 105:
        score += 30
    elif composite >= 95:
        score += 15

    # Slope positive (0-20)
    if slope > 0:
        score += min(20, slope * 4)

    # RSI timing (0-20)
    if rsi and 45 <= rsi <= 70:
        score += 20
    elif rsi and 35 <= rsi <= 75:
        score += 10

    # Volume (0-15)
    if volume_ok:
        score += 15

    # Above MA (0-15)
    if above_ma:
        score += 15

    return min(100, score)


def compute_rs_sustainability(
    composite: float,
    rs_1m: float,
    rs_3m: float,
    rs_6m: float,
    slope: float,
) -> float:
    """0-100: Will this RS persist."""
    score = 0.0

    # Multi-timeframe alignment (0-40)
    if rs_1m >= 105 and rs_3m >= 105 and rs_6m >= 105:
        score += 40
    elif rs_1m >= 100 and rs_3m >= 100:
        score += 25
    elif rs_3m >= 105:
        score += 15

    # Slope stability (0-30)
    if 0 <= slope <= 5:
        score += 30  # steady leadership
    elif slope > 5:
        score += 15  # accelerating — might exhaust
    elif slope > -2:
        score += 20

    # Not extended (0-30)
    if composite < 150:
        score += 30
    elif composite < 180:
        score += 15

    return min(100, score)


def compute_final_rank_score(profile: RSProfile) -> float:
    """
    Weighted final rank score:
      0.30 * RS quality
    + 0.20 * RS trend (slope normalized)
    + 0.15 * sector strength (leadership-based)
    + 0.15 * setup quality (tradeability + sustainability avg)
    + 0.10 * liquidity (mcap-based proxy)
    + 0.10 * timing quality (tradeability)
    - penalties
    """
    slope_norm = min(100, max(0, (profile.rs_slope + 10) * 5))

    # Sector score: LEADER in a strong sector > follower in weak sector
    sector_score = (
        80 if profile.leadership == "LEADER" else
        50 if profile.leadership == "FOLLOWER" else 20
    )
    # Setup score: derived from tradeability + sustainability
    setup_score = (profile.rs_tradeability + profile.rs_sustainability) / 2
    # Liquidity proxy: large/mega caps more liquid
    liquidity_score = (
        80 if profile.mcap_bucket == "Mega" else
        65 if profile.mcap_bucket == "Large" else 45
    )

    score = (
        0.30 * profile.rs_quality
        + 0.20 * slope_norm
        + 0.15 * sector_score
        + 0.15 * setup_score
        + 0.10 * liquidity_score
        + 0.10 * profile.rs_tradeability
    )

    # Penalties
    _state_penalties = {"EXTENDED": 10, "FADING": 15, "BROKEN": 25}
    score -= _state_penalties.get(profile.rs_state, 0)
    if profile.leadership == "LAGGARD":
        score -= 10

    return max(0, min(100, score))


# ── Setup + RS Matrix ────────────────────────────────────────────────────────

def rs_setup_matrix(rs_quality: float, setup_quality: float) -> str:
    """
    RS × Setup matrix verdict:
      High RS + High Setup → TRADE / WATCH
      High RS + Low Setup  → WAIT
      Low RS  + High Setup → TACTICAL ONLY
      Low RS  + Low Setup  → REJECT
    """
    rs_high = rs_quality >= 60
    setup_high = setup_quality >= 60

    if rs_high:
        return "TRADE" if setup_high else "WAIT"
    return "TACTICAL" if setup_high else "REJECT"
