"""
Swing Analysis Service — Sprint 84
====================================
Extracted from src/api/main.py (was module-level functions, lines ~4144-4460).

These are pure Python functions with no FastAPI/app dependencies — safe to
import anywhere. The v6 swing router imports them directly.

Implements Swing_Project best-practices:
  - Relative Strength vs SPY (RS)
  - VCP (Volatility Contraction Pattern)
  - Volume Quality scoring
  - Pullback Entry engine
  - Distribution Day counting
  - Dual-axis Leadership/Actionability scoring
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── RS vs SPY ────────────────────────────────────────────────────────────────

def compute_rs_vs_spy(stock_closes: List[float], spy_closes: List[float]) -> Dict[str, Any]:
    """Relative Strength vs SPY — leadership filter from Swing_Project."""
    if len(stock_closes) < 90 or len(spy_closes) < 90:
        return {
            "rs_score": 0,
            "rs_trending_up": False,
            "rs_return_20d": 0.0,
            "rs_return_60d": 0.0,
            "rs_return_90d": 0.0,
        }

    def _ret(arr: List[float], n: int) -> float:
        if len(arr) < n + 1 or arr[-n - 1] == 0:
            return 0.0
        return (arr[-1] / arr[-n - 1]) - 1.0

    stock_r20 = _ret(stock_closes, 20)
    stock_r60 = _ret(stock_closes, 60)
    stock_r90 = _ret(stock_closes, 90)
    spy_r20 = _ret(spy_closes, 20)
    spy_r60 = _ret(spy_closes, 60)
    spy_r90 = _ret(spy_closes, 90)

    rs_20 = (stock_r20 - spy_r20) if spy_r20 != 0 else stock_r20
    rs_60 = (stock_r60 - spy_r60) if spy_r60 != 0 else stock_r60
    rs_90 = (stock_r90 - spy_r90) if spy_r90 != 0 else stock_r90

    # RS line = stock/SPY ratio (last 50 bars)
    rs_line = [
        s / b if b > 0 else 0
        for s, b in zip(stock_closes[-50:], spy_closes[-50:])
    ]
    rs_sma10 = sum(rs_line[-10:]) / 10 if len(rs_line) >= 10 else 0
    rs_sma50 = sum(rs_line) / len(rs_line) if rs_line else 0
    rs_trending_up = rs_sma10 > rs_sma50

    rs_score = 0
    if rs_20 > 0:
        rs_score += 1
    if rs_60 > 0:
        rs_score += 1
    if rs_90 > 0:
        rs_score += 1
    if rs_trending_up:
        rs_score += 2

    return {
        "rs_score": rs_score,
        "rs_trending_up": rs_trending_up,
        "rs_return_20d": round(rs_20 * 100, 2),
        "rs_return_60d": round(rs_60 * 100, 2),
        "rs_return_90d": round(rs_90 * 100, 2),
    }


# ── Distribution Days (IBD-style) ─────────────────────────────────────────────

def detect_distribution_days(spy_data: List[Dict], lookback: int = 25) -> Dict[str, Any]:
    """IBD-style distribution day counting.

    A distribution day = SPY down >= 0.2% on higher volume than prior day.
    """
    if len(spy_data) < lookback + 1:
        return {
            "distribution_day_count": 0,
            "ftd_count": 0,
            "regime_pressure": "neutral",
        }

    dd_count = 0
    ftd_count = 0
    for i in range(-lookback, 0):
        if i - 1 < -len(spy_data):
            continue
        today = spy_data[i]
        yesterday = spy_data[i - 1]
        if not today or not yesterday:
            continue
        today_close = today.get("close", 0)
        yesterday_close = yesterday.get("close", 0)
        today_vol = today.get("volume", 0)
        yesterday_vol = yesterday.get("volume", 0)
        if yesterday_close == 0:
            continue
        pct_change = (today_close / yesterday_close) - 1.0
        # Distribution: down >= 0.2% on higher volume
        if pct_change <= -0.002 and today_vol > yesterday_vol:
            dd_count += 1
        # Follow-through: up >= 1.25% on higher volume
        if pct_change >= 0.0125 and today_vol > yesterday_vol:
            ftd_count += 1

    pressure = (
        "heavy_distribution"
        if dd_count >= 5
        else "moderate_distribution" if dd_count >= 3 else "neutral"
    )
    return {
        "distribution_day_count": dd_count,
        "ftd_count": ftd_count,
        "regime_pressure": pressure,
    }


# ── VCP Pattern ───────────────────────────────────────────────────────────────

def detect_vcp_pattern(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float],
) -> Dict[str, Any]:
    """Simplified VCP (Volatility Contraction Pattern) detection.

    Looks for progressively tighter contractions in price range.
    """
    result: Dict[str, Any] = {
        "is_vcp": False,
        "contraction_count": 0,
        "tightness_ratio": 0.0,
        "vcp_score": 0.0,
        "pivot_price": None,
    }
    if len(closes) < 60:
        return result

    window = min(len(closes), 120)
    h = highs[-window:]
    ll = lows[-window:]
    v = volumes[-window:]

    # Find contractions across 6 chunks
    contractions: List[float] = []
    chunk_size = max(10, window // 6)
    for start in range(0, window - chunk_size, chunk_size):
        end = start + chunk_size
        chunk_h = max(h[start:end])
        chunk_l = min(ll[start:end])
        if chunk_h > 0:
            depth = (chunk_h - chunk_l) / chunk_h
            contractions.append(depth)

    if len(contractions) < 2:
        return result

    tightening_count = sum(
        1 for i in range(1, len(contractions)) if contractions[i] < contractions[i - 1]
    )
    tightness_ratio = tightening_count / (len(contractions) - 1)

    # Volume dryup
    recent_vol = sum(v[-10:]) / 10 if len(v) >= 10 else 0
    older_vol = sum(v[-50:-10]) / 40 if len(v) >= 50 else recent_vol
    vol_dryup = recent_vol / older_vol if older_vol > 0 else 1.0

    is_vcp = tightness_ratio >= 0.5 and len(contractions) >= 3 and vol_dryup < 0.8
    vcp_score = min(
        1.0,
        (tightness_ratio * 0.4)
        + (0.3 if vol_dryup < 0.6 else 0.1)
        + (0.3 if len(contractions) >= 4 else 0.15),
    )
    pivot_price = max(highs[-20:]) if is_vcp else None

    return {
        "is_vcp": is_vcp,
        "contraction_count": len(contractions),
        "tightness_ratio": round(tightness_ratio, 3),
        "vcp_score": round(vcp_score, 3),
        "pivot_price": round(pivot_price, 2) if pivot_price else None,
        "volume_dryup_ratio": round(vol_dryup, 3),
    }


# ── Volume Quality ────────────────────────────────────────────────────────────

def compute_volume_quality(volumes: List[float], closes: List[float]) -> Dict[str, Any]:
    """Volume quality scoring from Swing_Project.

    Measures accumulation/distribution patterns.
    """
    if len(volumes) < 50 or len(closes) < 50:
        return {
            "volume_quality_score": 0,
            "up_down_volume_ratio": 1.0,
            "volume_dryup_ratio": 1.0,
            "pocket_pivot_detected": False,
        }

    up_vol = 0.0
    down_vol = 0.0
    for i in range(-20, 0):
        if closes[i] > closes[i - 1]:
            up_vol += volumes[i]
        else:
            down_vol += volumes[i]
    ud_ratio = up_vol / down_vol if down_vol > 0 else 2.0

    sma10_vol = sum(volumes[-10:]) / 10
    sma50_vol = sum(volumes[-50:]) / 50
    dryup = sma10_vol / sma50_vol if sma50_vol > 0 else 1.0

    max_down_vol_10d = 0.0
    for i in range(-10, 0):
        if closes[i] < closes[i - 1]:
            max_down_vol_10d = max(max_down_vol_10d, volumes[i])
    pocket_pivot = bool(
        closes[-1] > closes[-2]
        and volumes[-1] > max_down_vol_10d
        and max_down_vol_10d > 0
    )

    score = 0
    if dryup < 0.6:
        score += 2
    elif dryup < 0.8:
        score += 1
    if ud_ratio > 1.5:
        score += 1
    if ud_ratio > 2.0:
        score += 1
    if pocket_pivot:
        score += 1

    return {
        "volume_quality_score": min(score, 5),
        "up_down_volume_ratio": round(ud_ratio, 3),
        "volume_dryup_ratio": round(dryup, 3),
        "pocket_pivot_detected": pocket_pivot,
    }


# ── Pullback Entry Engine ─────────────────────────────────────────────────────

def detect_pullback_entry(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
    sma20: float,
) -> Dict[str, Any]:
    """Pullback entry engine from Swing_Project.

    Detects post-breakout pullback to SMA20 support with rebound confirmation.
    """
    result: Dict[str, Any] = {
        "pullback_state": "none",
        "entry_ready": False,
        "distance_to_sma20_pct": None,
        "support_rebound": False,
    }
    if len(closes) < 25 or sma20 <= 0:
        return result

    current = closes[-1]
    distance_pct = ((current / sma20) - 1.0) * 100

    high_20d = max(highs[-25:-5]) if len(highs) >= 25 else max(highs)
    was_breakout = any(c >= high_20d * 0.995 for c in closes[-10:-2])
    is_near_support = abs(distance_pct) < 3.0

    recent_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 0
    avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else recent_vol
    vol_quiet = recent_vol < avg_vol

    rebound = closes[-1] > closes[-2] and lows[-1] >= sma20 * 0.98

    if was_breakout and is_near_support and vol_quiet:
        state = "pullback-entry-ready" if rebound else "post-breakout-watch"
    elif was_breakout:
        state = "post-breakout"
    else:
        state = "none"

    return {
        "pullback_state": state,
        "entry_ready": state == "pullback-entry-ready",
        "distance_to_sma20_pct": round(distance_pct, 2),
        "support_rebound": rebound,
    }


# ── Dual-Axis Leadership / Actionability ──────────────────────────────────────

def compute_leadership_actionability(
    rs_data: Dict[str, Any],
    vcp_data: Dict[str, Any],
    vol_data: Dict[str, Any],
    pullback_data: Dict[str, Any],
    rsi: float,
    atr_pct: float,
    close: float,
    sma200: float,
) -> Dict[str, Any]:
    """Dual-axis scoring from Swing_Project.

    Leadership  = RS strength + trend quality.
    Actionability = breakout proximity + compression + volume + setup stage.
    Final score = weighted combination (0-100).
    """
    rs_norm = min(1.0, rs_data.get("rs_score", 0) / 5.0)
    trend_strength = (
        min(1.0, max(0.0, (close / sma200 - 1.0) * 5)) if sma200 > 0 else 0.5
    )
    leadership = rs_norm * 0.6 + trend_strength * 0.4

    vcp_component = vcp_data.get("vcp_score", 0)
    vol_component = min(1.0, vol_data.get("volume_quality_score", 0) / 5.0)

    pullback_stage_score = {
        "pullback-entry-ready": 1.0,
        "post-breakout-watch": 0.8,
        "post-breakout": 0.5,
        "none": 0.2,
    }.get(pullback_data.get("pullback_state", "none"), 0.2)

    actionability = vcp_component * 0.3 + vol_component * 0.3 + pullback_stage_score * 0.4

    final_score = (leadership * 0.45 + actionability * 0.55) * 100

    if leadership >= 0.7 and actionability >= 0.7:
        tag = "leader-actionable"
    elif leadership >= 0.7:
        tag = "leader-watch"
    elif actionability >= 0.7:
        tag = "setup-forming"
    else:
        tag = "early-stage"

    return {
        "leadership_score": round(leadership, 3),
        "actionability_score": round(actionability, 3),
        "final_score": round(final_score, 1),
        "setup_tag": tag,
    }
