"""
Opportunity Scanner — Neal-Style Dual-Engine Screener.

Implements the scoring model from https://nealjai.github.io/Swing_Project/:

  Bull Engine (active in BULL/SIDEWAYS regimes):
    Leadership   = 0.60 × RS + 0.40 × Trend
    Actionability = 0.40 × Breakout + 0.25 × Compression + 0.20 × Volume + 0.15 × Stage
    Final Score  = 100 × (0.55 × Actionability + 0.45 × Leadership)

  Weak Engine (active in BEAR/CHOPPY regimes):
    Leadership   = 0.70 × Trend + 0.30 × Liquidity
    Actionability = 0.45 × Reversal + 0.35 × Extension + 0.20 × Capitulation
    Final Score  = 100 × (0.60 × Actionability + 0.40 × Leadership)

Tags (can stack):
  🏆 Leader     leadership_score_norm  ≥ 0.90
  ⚡ Actionable actionability_score_norm ≥ 0.58
  👀 Watch      0.50 ≤ actionability_score_norm < 0.58

All component scores are normalised via median/MAD + sigmoid before weighting
so one outlier cannot dominate the ranking.

Sprint 114.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Scoring weights (match Neal's published formula) ────────────────────────
_BULL_LEADERSHIP_W = {"rs": 0.60, "trend": 0.40}
_BULL_ACTIONABILITY_W = {
    "breakout": 0.40,
    "compression": 0.25,
    "volume": 0.20,
    "stage": 0.15,
}
_BULL_FINAL_W = {"actionability": 0.55, "leadership": 0.45}

_WEAK_LEADERSHIP_W = {"trend": 0.70, "liquidity": 0.30}
_WEAK_ACTIONABILITY_W = {"reversal": 0.45, "extension": 0.35, "capitulation": 0.20}
_WEAK_FINAL_W = {"actionability": 0.60, "leadership": 0.40}

# ── Convenience ──────────────────────────────────────────────────────────────
_BULL_REGIMES = {"BULL", "SIDEWAYS"}
_WEAK_REGIMES = {"BEAR", "CHOPPY"}

# Tag thresholds
_LEADER_THRESH = 0.90
_ACTIONABLE_THRESH = 0.58
_WATCH_THRESH = 0.50

# Scanner defaults
_DEFAULT_TOP_N = 50
_MIN_PRICE = 5.0  # filter penny stocks
_MIN_AVG_VOL = 200_000  # min 200k avg daily volume
_HISTORY_DAYS = 252  # 1 year for RS calculation
_SPY_CACHE: Dict[str, Any] = {}  # simple module-level cache


@dataclass
class OpportunityCandidate:
    """One ranked candidate from the opportunity scanner."""

    rank: int
    ticker: str
    engine: str  # "bull" or "weak"
    score: float  # 0–100 final score
    leadership_score: float  # 0–100
    actionability_score: float  # 0–100
    # tag booleans
    is_leader: bool = False
    is_actionable: bool = False
    is_watch: bool = False
    # price levels
    close: float = 0.0
    stop_loss: float = 0.0  # close − 2×ATR14
    activation: float = 0.0  # close + 2×ATR14 (TP1)
    atr14: float = 0.0
    # extra context
    rs_score: float = 0.0
    trend_score: float = 0.0
    volume_ratio: float = 1.0
    rsi14: float = 50.0
    above_50sma: bool = False
    above_200sma: bool = False
    # component scores (raw, pre-normalisation)
    raw_components: Dict[str, float] = field(default_factory=dict)

    @property
    def tags(self) -> List[str]:
        t: List[str] = []
        if self.is_leader:
            t.append("🏆")
        if self.is_actionable:
            t.append("⚡")
        elif self.is_watch:
            t.append("👀")
        return t

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "ticker": self.ticker,
            "engine": self.engine,
            "score": round(self.score, 4),
            "leadership_score": round(self.leadership_score, 2),
            "actionability_score": round(self.actionability_score, 2),
            "is_leader": self.is_leader,
            "is_actionable": self.is_actionable,
            "is_watch": self.is_watch,
            "tags": self.tags,
            "close": round(self.close, 2),
            "stop_loss": round(self.stop_loss, 2),
            "activation": round(self.activation, 2),
            "atr14": round(self.atr14, 2),
            "rs_score": round(self.rs_score, 3),
            "trend_score": round(self.trend_score, 3),
            "volume_ratio": round(self.volume_ratio, 2),
            "rsi14": round(self.rsi14, 1),
            "above_50sma": self.above_50sma,
            "above_200sma": self.above_200sma,
        }


@dataclass
class ScannerResult:
    """Full scanner run output including filter funnel stats."""

    engine: str
    regime: str
    universe_size: int
    passed_initial: int
    passed_rs: int
    passed_pattern: int
    candidates_raw: int
    candidates_ranked: int
    top_n: int
    generated_at: str
    candidates: List[OpportunityCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "regime": self.regime,
            "universe_size": self.universe_size,
            "filter_funnel": {
                "initial_universe": self.universe_size,
                "passed_initial_filters": self.passed_initial,
                "passed_rs_filter": self.passed_rs,
                "passed_pattern_filter": self.passed_pattern,
                "final_candidates": self.candidates_ranked,
                "raw_candidates": self.candidates_raw,
            },
            "candidates_raw": self.candidates_raw,
            "candidates_ranked": self.candidates_ranked,
            "top_n": self.top_n,
            "generated_at": self.generated_at,
            "candidates": [c.to_dict() for c in self.candidates],
        }


# ── Normalisation helpers ────────────────────────────────────────────────────


def _sigmoid(x: float) -> float:
    """Logistic sigmoid, maps R → (0, 1)."""
    return 1.0 / (1.0 + math.exp(-x))


def _robust_normalise(values: List[float]) -> List[float]:
    """Median/MAD + sigmoid normalisation (robust to outliers)."""
    if not values:
        return values
    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    if mad < 1e-8:
        return [0.5] * len(values)
    z = (arr - med) / (1.4826 * mad)  # 1.4826 makes MAD consistent with σ
    return [_sigmoid(float(zi)) for zi in z]


# ── Component score computors ────────────────────────────────────────────────


def _rs_score(close_1y: np.ndarray, spy_1y: np.ndarray) -> float:
    """Relative Strength: 1-year return of ticker vs SPY."""
    if len(close_1y) < 2 or len(spy_1y) < 2:
        return 0.0
    n = min(len(close_1y), len(spy_1y))
    ticker_ret = (close_1y[-1] / close_1y[-n] - 1.0) if close_1y[-n] > 0 else 0.0
    spy_ret = (spy_1y[-1] / spy_1y[-n] - 1.0) if spy_1y[-n] > 0 else 0.0
    return float(ticker_ret - spy_ret)


def _trend_score(close: np.ndarray, sma50: np.ndarray, sma200: np.ndarray) -> float:
    """Trend strength: price vs SMA50 vs SMA200 alignment + SMA50 slope."""
    c, s50, s200 = float(close[-1]), float(sma50[-1]), float(sma200[-1])
    score = 0.0
    if c > s50:
        score += 0.40
    if s50 > s200:
        score += 0.35
    if c > s200:
        score += 0.25
    # SMA50 slope over 10 bars
    if len(sma50) >= 10 and float(sma50[-10]) > 0:
        slope = (float(sma50[-1]) - float(sma50[-10])) / float(sma50[-10])
        score += min(0.20, max(-0.10, slope * 5))
    return max(0.0, min(1.0, score))


def _breakout_score(
    close: np.ndarray, bb_pct_b: np.ndarray, rsi14: np.ndarray, vol_ratio: np.ndarray
) -> float:
    """Breakout score: BB %B expansion + RSI thrust + volume."""
    pct_b = float(bb_pct_b[-1])
    rsi = float(rsi14[-1])
    vol = float(vol_ratio[-1])
    score = 0.0
    # Upper band breakout
    if pct_b > 0.80:
        score += 0.45
    elif pct_b > 0.65:
        score += 0.25
    # RSI momentum
    if 55 < rsi < 75:
        score += 0.30
    elif rsi >= 75:
        score += 0.15  # overbought penalty
    # Volume expansion
    if vol > 1.5:
        score += 0.25
    elif vol > 1.2:
        score += 0.12
    return max(0.0, min(1.0, score))


def _compression_score(bb_width: np.ndarray) -> float:
    """Compression (VCP/squeeze): narrow BB width vs its recent range."""
    if len(bb_width) < 20:
        return 0.3
    w = float(bb_width[-1])
    w_max = (
        float(np.percentile(bb_width[-60:], 90))
        if len(bb_width) >= 60
        else float(np.max(bb_width[-20:]))
    )
    if w_max < 1e-8:
        return 0.3
    pct = w / w_max  # 0 = very tight, 1 = widest
    return max(0.0, min(1.0, 1.0 - pct))


def _volume_score(vol_ratio: np.ndarray) -> float:
    """Volume score: recent vol ratio vs 20-day avg."""
    v = float(vol_ratio[-1])
    if v >= 2.0:
        return 1.0
    if v >= 1.5:
        return 0.75
    if v >= 1.2:
        return 0.50
    if v >= 0.8:
        return 0.25
    return 0.05


def _stage_score(close: np.ndarray, sma50: np.ndarray, sma200: np.ndarray) -> float:
    """Weinstein Stage proxy: Stage 2 (markup) scores highest."""
    c, s50, s200 = float(close[-1]), float(sma50[-1]), float(sma200[-1])
    if c > s50 and s50 > s200:
        return 0.90  # Stage 2 uptrend
    if c > s200 and s50 < s200:
        return 0.55  # Stage 1 base
    if c < s50 and s50 < s200:
        return 0.10  # Stage 4 downtrend
    return 0.30  # Stage 3 distribution


def _reversal_score(rsi14: np.ndarray, bb_pct_b: np.ndarray) -> float:
    """Weak engine: RSI reversal from oversold."""
    rsi = float(rsi14[-1])
    pct_b = float(bb_pct_b[-1])
    score = 0.0
    if rsi < 35:
        score += 0.55
    elif rsi < 42:
        score += 0.30
    if pct_b < 0.20:
        score += 0.45
    elif pct_b < 0.35:
        score += 0.25
    return max(0.0, min(1.0, score))


def _extension_score(close: np.ndarray, sma20: np.ndarray) -> float:
    """Weak engine: how far price has fallen from SMA20."""
    c, s20 = float(close[-1]), float(sma20[-1])
    if s20 <= 0:
        return 0.3
    ext = (s20 - c) / s20  # positive = below SMA20
    if ext > 0.12:
        return 1.0
    if ext > 0.07:
        return 0.70
    if ext > 0.03:
        return 0.40
    return 0.10


def _capitulation_score(vol_ratio: np.ndarray, close: np.ndarray) -> float:
    """Weak engine: capitulation = high volume on down day."""
    v = float(vol_ratio[-1])
    if len(close) < 2:
        return 0.3
    daily_ret = (
        (float(close[-1]) - float(close[-2])) / float(close[-2])
        if float(close[-2]) > 0
        else 0.0
    )
    if daily_ret < -0.03 and v > 2.0:
        return 1.0
    if daily_ret < -0.02 and v > 1.5:
        return 0.65
    if daily_ret < -0.01 and v > 1.2:
        return 0.35
    return 0.10


def _liquidity_score(vol_ratio: np.ndarray, close: np.ndarray) -> float:
    """Weak engine: baseline liquidity proxy."""
    return min(1.0, float(vol_ratio[-1]) / 2.0)


# ── Main scorer ──────────────────────────────────────────────────────────────


def _score_ticker(
    ticker: str,
    close: np.ndarray,
    volume: np.ndarray,
    indicators: Dict[str, np.ndarray],
    spy_close: np.ndarray,
    engine: str,
) -> Optional[Dict[str, float]]:
    """Compute all component scores for one ticker. Returns None on error."""
    try:
        sma20 = indicators["sma20"]
        sma50 = indicators["sma50"]
        sma200 = indicators["sma200"]
        rsi14 = indicators["rsi14"]
        vol_r = indicators["vol_ratio"]
        atr14_v = indicators["atr14"]
        bb_pct = indicators["bb_pct_b"]
        bb_w = indicators["bb_width"]

        rs = _rs_score(close, spy_close)
        trend = _trend_score(close, sma50, sma200)

        if engine == "bull":
            breakout = _breakout_score(close, bb_pct, rsi14, vol_r)
            compression = _compression_score(bb_w)
            volume = _volume_score(vol_r)
            stage = _stage_score(close, sma50, sma200)
            raw = {
                "rs": rs,
                "trend": trend,
                "breakout": breakout,
                "compression": compression,
                "volume": volume,
                "stage": stage,
            }
        else:
            reversal = _reversal_score(rsi14, bb_pct)
            extension = _extension_score(close, sma20)
            capitulation = _capitulation_score(vol_r, close)
            liquidity = _liquidity_score(vol_r, close)
            raw = {
                "rs": rs,
                "trend": trend,
                "reversal": reversal,
                "extension": extension,
                "capitulation": capitulation,
                "liquidity": liquidity,
            }

        return {
            "ticker": ticker,
            "close": float(close[-1]),
            "atr14": float(atr14_v[-1]),
            "rsi14": float(rsi14[-1]),
            "vol_ratio": float(vol_r[-1]),
            "above_50sma": bool(float(close[-1]) > float(sma50[-1])),
            "above_200sma": bool(float(close[-1]) > float(sma200[-1])),
            **raw,
        }
    except Exception as exc:
        logger.debug("_score_ticker %s error: %s", ticker, exc)
        return None


# ── Public API ───────────────────────────────────────────────────────────────


async def run_opportunity_scanner(
    regime: str = "BULL",
    top_n: int = _DEFAULT_TOP_N,
    min_price: float = _MIN_PRICE,
    min_vol: int = _MIN_AVG_VOL,
) -> ScannerResult:
    """Run the full dual-engine opportunity scan.

    Args:
        regime:    Current market regime (BULL/BEAR/SIDEWAYS/CHOPPY).
        top_n:     Max candidates to return (default 50).
        min_price: Minimum close price filter.
        min_vol:   Minimum average daily volume filter.

    Returns:
        ScannerResult with ranked candidates + filter funnel stats.
    """
    import yfinance as yf
    from datetime import datetime, timezone

    from src.scanners.us_universe import US_UNIVERSE

    regime_upper = regime.upper()
    engine = "bull" if regime_upper in _BULL_REGIMES else "weak"
    generated_at = datetime.now(timezone.utc).isoformat()

    universe = list(dict.fromkeys(US_UNIVERSE))  # deduplicate
    universe_size = len(universe)

    # ── Step 1: Fetch SPY as benchmark ──────────────────────────────────────
    global _SPY_CACHE
    spy_close: np.ndarray
    now_ts = time.time()
    if _SPY_CACHE.get("ts", 0) > now_ts - 3600:
        spy_close = _SPY_CACHE["close"]
    else:
        try:
            spy_df = await asyncio.to_thread(
                yf.download, "SPY", period="1y", auto_adjust=True, progress=False
            )
            spy_close = spy_df["Close"].to_numpy().flatten()
            _SPY_CACHE = {"close": spy_close, "ts": now_ts}
        except Exception as exc:
            logger.warning("SPY fetch failed: %s", exc)
            spy_close = np.ones(252)

    # ── Step 2: Batch-fetch universe (chunked for rate limits) ──────────────
    chunk_size = 50
    chunks = [universe[i : i + chunk_size] for i in range(0, len(universe), chunk_size)]

    raw_scores: List[Dict[str, float]] = []
    passed_initial = 0

    for chunk in chunks:
        tickers_str = " ".join(chunk)
        try:
            df = await asyncio.to_thread(
                yf.download,
                tickers_str,
                period="1y",
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as exc:
            logger.debug("Chunk download failed: %s", exc)
            continue

        for ticker in chunk:
            try:
                if len(chunk) == 1:
                    close_df = df["Close"]
                    vol_df = df["Volume"]
                else:
                    close_df = df[ticker]["Close"]
                    vol_df = df[ticker]["Volume"]

                close_arr = close_df.dropna().to_numpy().astype(float)
                vol_arr = vol_df.dropna().to_numpy().astype(float)

                if len(close_arr) < 60:
                    continue
                if float(close_arr[-1]) < min_price:
                    continue
                avg_vol = float(np.mean(vol_arr[-20:])) if len(vol_arr) >= 20 else 0.0
                if avg_vol < min_vol:
                    continue

                passed_initial += 1

                from src.services.indicators import compute_indicators

                ind = compute_indicators(close_arr, vol_arr)

                result = _score_ticker(
                    ticker, close_arr, vol_arr, ind, spy_close, engine
                )
                if result:
                    raw_scores.append(result)
            except Exception as exc:
                logger.debug("Ticker %s skipped: %s", ticker, exc)
                continue

    candidates_raw = len(raw_scores)
    if candidates_raw == 0:
        return ScannerResult(
            engine=engine,
            regime=regime_upper,
            universe_size=universe_size,
            passed_initial=0,
            passed_rs=0,
            passed_pattern=0,
            candidates_raw=0,
            candidates_ranked=0,
            top_n=top_n,
            generated_at=generated_at,
            candidates=[],
        )

    # ── Step 3: RS filter (above SPY 1y return) ─────────────────────────────
    passed_rs_list = [s for s in raw_scores if s.get("rs", 0) >= 0]
    passed_rs = len(passed_rs_list)

    # ── Step 4: Pattern filter (above 50 SMA) ───────────────────────────────
    if engine == "bull":
        passed_pattern_list = [s for s in passed_rs_list if s.get("above_50sma", False)]
    else:
        # Weak engine looks for setups below 50 SMA (mean reversion)
        passed_pattern_list = [
            s for s in passed_rs_list if not s.get("above_50sma", True)
        ]
    passed_pattern = len(passed_pattern_list)

    # Fall back to full rs list if pattern filter is too restrictive
    scoring_list = (
        passed_pattern_list if passed_pattern >= max(10, top_n // 5) else passed_rs_list
    )

    # ── Step 5: Normalise components and compute final scores ────────────────
    def _col(key: str) -> List[float]:
        return [s.get(key, 0.0) for s in scoring_list]

    if engine == "bull":
        rs_norm = _robust_normalise(_col("rs"))
        trend_norm = _robust_normalise(_col("trend"))
        brk_norm = _robust_normalise(_col("breakout"))
        cmp_norm = _robust_normalise(_col("compression"))
        vol_norm = _robust_normalise(_col("volume"))
        stg_norm = _robust_normalise(_col("stage"))

        for i, s in enumerate(scoring_list):
            s["_leader_norm"] = (
                rs_norm[i] * _BULL_LEADERSHIP_W["rs"]
                + trend_norm[i] * _BULL_LEADERSHIP_W["trend"]
            )
            s["_actionable_norm"] = (
                brk_norm[i] * _BULL_ACTIONABILITY_W["breakout"]
                + cmp_norm[i] * _BULL_ACTIONABILITY_W["compression"]
                + vol_norm[i] * _BULL_ACTIONABILITY_W["volume"]
                + stg_norm[i] * _BULL_ACTIONABILITY_W["stage"]
            )
            s["_score"] = 100.0 * (
                s["_actionable_norm"] * _BULL_FINAL_W["actionability"]
                + s["_leader_norm"] * _BULL_FINAL_W["leadership"]
            )
    else:
        trend_norm = _robust_normalise(_col("trend"))
        liq_norm = _robust_normalise(_col("liquidity"))
        rev_norm = _robust_normalise(_col("reversal"))
        ext_norm = _robust_normalise(_col("extension"))
        cap_norm = _robust_normalise(_col("capitulation"))

        for i, s in enumerate(scoring_list):
            s["_leader_norm"] = (
                trend_norm[i] * _WEAK_LEADERSHIP_W["trend"]
                + liq_norm[i] * _WEAK_LEADERSHIP_W["liquidity"]
            )
            s["_actionable_norm"] = (
                rev_norm[i] * _WEAK_ACTIONABILITY_W["reversal"]
                + ext_norm[i] * _WEAK_ACTIONABILITY_W["extension"]
                + cap_norm[i] * _WEAK_ACTIONABILITY_W["capitulation"]
            )
            s["_score"] = 100.0 * (
                s["_actionable_norm"] * _WEAK_FINAL_W["actionability"]
                + s["_leader_norm"] * _WEAK_FINAL_W["leadership"]
            )

    # Sort descending by score
    scoring_list.sort(key=lambda x: x["_score"], reverse=True)
    top_list = scoring_list[:top_n]

    # ── Step 6: Build OpportunityCandidate objects ────────────────────────────
    candidates: List[OpportunityCandidate] = []
    for rank, s in enumerate(top_list, start=1):
        close = s["close"]
        atr = s["atr14"]
        ln = s["_leader_norm"]
        an = s["_actionable_norm"]
        c = OpportunityCandidate(
            rank=rank,
            ticker=s["ticker"],
            engine=engine,
            score=round(s["_score"], 4),
            leadership_score=round(ln * 100, 4),
            actionability_score=round(an * 100, 4),
            is_leader=ln >= _LEADER_THRESH,
            is_actionable=an >= _ACTIONABLE_THRESH,
            is_watch=(not (an >= _ACTIONABLE_THRESH)) and an >= _WATCH_THRESH,
            close=close,
            stop_loss=round(close - 2.0 * atr, 2),
            activation=round(close + 2.0 * atr, 2),
            atr14=round(atr, 2),
            rs_score=s.get("rs", 0.0),
            trend_score=s.get("trend", 0.0),
            volume_ratio=s.get("vol_ratio", 1.0),
            rsi14=s.get("rsi14", 50.0),
            above_50sma=s.get("above_50sma", False),
            above_200sma=s.get("above_200sma", False),
        )
        candidates.append(c)

    return ScannerResult(
        engine=engine,
        regime=regime_upper,
        universe_size=universe_size,
        passed_initial=passed_initial,
        passed_rs=passed_rs,
        passed_pattern=passed_pattern,
        candidates_raw=candidates_raw,
        candidates_ranked=len(candidates),
        top_n=top_n,
        generated_at=generated_at,
        candidates=candidates,
    )
