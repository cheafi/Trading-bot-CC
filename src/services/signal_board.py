"""
Signal Board — hourly BUY / SELL paper signals across S&P 500 + Nasdaq-100 + ETFs.

Four Questions (AGENTS.md):
  Know    — one ranked list of triggered long/short setups with entry/stop/targets.
  Doubt   — every signal carries its invalidation level and a running track record.
  Act     — exit/trim alerts on current holdings.
  Remove  — replaces the padded "coverage" board for daily use.

Signals are paper ideas only. They never send orders and do not change any
execution gate (broker / engine / circuit breaker gates stay authoritative).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    from zoneinfo import ZoneInfo

    _ET = ZoneInfo("America/New_York")
except (ImportError, KeyError):  # pragma: no cover - tzdata missing
    _ET = timezone(timedelta(hours=-5))

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_PATH = _REPO_ROOT / "data" / "universe_signal_board.json"
HOLDINGS_PATH = _REPO_ROOT / "data" / "portfolio_local_holdings.json"
STORE_DIR = _REPO_ROOT / "data" / "signal_board"
LATEST_PATH = STORE_DIR / "latest.json"

BENCHMARK = "SPY"
MIN_BARS = 130
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 20_000_000.0
MIN_ATR_PCT = 0.6  # below this the price is pinned (e.g. pending cash takeover)
DOWNLOAD_CHUNK = 100
BUCKET_CAP = 10
SECTOR_CAP_PER_BUCKET = 3
TRACK_RECORD_DAYS = 60

STRONG_THRESHOLD = 85.0
SIGNAL_THRESHOLD = 70.0
REGIME_HEADWIND_PENALTY = 10.0
STRONG_RS_PERCENTILE = 70.0
MAX_RISK_PCT = 10.0

BUCKET_ORDER = ("strong_buy", "buy", "sell", "strong_sell")
AUTHORITY = {
    "label": "Paper signal",
    "note": (
        "Not an order and not execution permission. Broker, engine and "
        "risk gates still decide whether anything can be traded."
    ),
}
METHOD = {
    "universe": (
        "S&P 500 + Nasdaq-100 + liquid ETFs (price >= $5, 20d $ volume >= $20M, "
        f"daily range >= {MIN_ATR_PCT}% so pinned takeover targets are skipped)"
    ),
    "score": (
        "0-100 = trend (40) + relative strength vs SPY percentile (25) + "
        "momentum (10) + setup trigger (25) - overbought/extended penalties"
    ),
    "triggers": {
        "BUY": "20-day breakout on volume, or pullback-bounce off 20/50-day SMA in an uptrend",
        "SELL": "20-day breakdown on volume, or failed rally into 20/50-day SMA in a downtrend",
    },
    "buckets": (
        f"Strong >= {STRONG_THRESHOLD:.0f} with RS top/bottom {100 - STRONG_RS_PERCENTILE:.0f}%, "
        f"Signal >= {SIGNAL_THRESHOLD:.0f}; trigger required; "
        f"+{REGIME_HEADWIND_PENALTY:.0f} threshold against the SPY regime"
    ),
    "plan": (
        "Stop = recent 10-day swing +/- 0.25 ATR (1-3 ATR). Target 1 = 2R, Target 2 = 3R. "
        f"Ideas risking more than {MAX_RISK_PCT:.0f}% to the stop are dropped."
    ),
}


# ── Pure feature / scoring functions ─────────────────────────────────────────


@dataclass
class Features:
    ticker: str
    close: float
    prev_close: float
    sma20: float
    sma50: float
    sma200: float
    rsi: float
    atr: float
    vol_ratio: float
    dollar_volume: float
    ret_1d: float
    ret_1m: float
    ret_3m: float
    ret_6m: float
    hi20_prev: float
    lo20_prev: float
    hi52: float
    lo52: float
    swing_low10: float
    swing_high10: float
    recent_low3: float
    recent_high3: float
    chandelier_long: float
    rs_raw: float
    last_bar: str = ""

    @property
    def dist_sma20_atr(self) -> float:
        return (self.close - self.sma20) / self.atr if self.atr > 0 else 0.0


def _wilder_rsi(close: np.ndarray, period: int = 14) -> float:
    if len(close) <= period:
        return 50.0
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g = gains[:period].mean()
    avg_l = losses[:period].mean()
    for g, lo in zip(gains[period:], losses[period:]):
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + lo) / period
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    return float(100.0 - 100.0 / (1.0 + avg_g / avg_l))


def _true_atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> float:
    prev = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    return float(tr[-period:].mean())


def _pct(close: np.ndarray, lookback: int) -> float:
    if len(close) <= lookback or close[-1 - lookback] <= 0:
        return 0.0
    return float(close[-1] / close[-1 - lookback] - 1.0) * 100.0


def compute_features(
    ticker: str,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    bench_close: np.ndarray | None = None,
    volume_scale: float = 1.0,
    last_bar: str = "",
) -> Features | None:
    """Latest-bar features. Returns None when history is too short or invalid."""
    mask = np.isfinite(close) & np.isfinite(high) & np.isfinite(low) & (close > 0)
    high, low, close = high[mask], low[mask], close[mask]
    volume = np.nan_to_num(volume[mask], nan=0.0)
    if len(close) < MIN_BARS:
        return None

    atr = _true_atr(high, low, close)
    if atr <= 0:
        return None
    vol_base = float(volume[-21:-1].mean()) if len(volume) > 21 else 0.0
    vol_today = float(volume[-1]) * max(volume_scale, 1.0)
    vol_ratio = vol_today / vol_base if vol_base > 0 else 1.0

    hi22 = float(high[-22:].max())
    rs_raw = 0.0
    if bench_close is not None and len(bench_close) >= 64:
        b = bench_close[np.isfinite(bench_close)]
        rs_raw = (
            0.25 * (_pct(close, 21) - _pct(b, 21))
            + 0.40 * (_pct(close, 63) - _pct(b, 63))
            + 0.35 * (_pct(close, 126) - _pct(b, 126))
        )

    return Features(
        ticker=ticker,
        close=float(close[-1]),
        prev_close=float(close[-2]),
        sma20=float(close[-20:].mean()),
        sma50=float(close[-50:].mean()),
        sma200=float(close[-200:].mean()),
        rsi=_wilder_rsi(close[-120:]),
        atr=atr,
        vol_ratio=vol_ratio,
        dollar_volume=float((close[-20:] * volume[-20:]).mean()),
        ret_1d=_pct(close, 1),
        ret_1m=_pct(close, 21),
        ret_3m=_pct(close, 63),
        ret_6m=_pct(close, 126),
        hi20_prev=float(high[-21:-1].max()),
        lo20_prev=float(low[-21:-1].min()),
        hi52=float(high[-252:].max()),
        lo52=float(low[-252:].min()),
        swing_low10=float(low[-10:].min()),
        swing_high10=float(high[-10:].max()),
        recent_low3=float(low[-3:].min()),
        recent_high3=float(high[-3:].max()),
        chandelier_long=hi22 - 3.0 * atr,
        rs_raw=rs_raw,
        last_bar=last_bar,
    )


def is_liquid(f: Features) -> bool:
    return (
        f.close >= MIN_PRICE
        and f.dollar_volume >= MIN_DOLLAR_VOLUME
        and f.atr / f.close * 100 >= MIN_ATR_PCT
    )


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """Cross-sectional percentile (0-100) per key; ties share the average rank."""
    if not values:
        return {}
    keys = list(values)
    arr = np.array([values[k] for k in keys], dtype=float)
    order = arr.argsort()
    ranks = np.empty(len(arr), dtype=float)
    ranks[order] = np.arange(len(arr), dtype=float)
    for v in np.unique(arr):
        idx = np.where(arr == v)[0]
        if len(idx) > 1:
            ranks[idx] = ranks[idx].mean()
    denom = max(len(arr) - 1, 1)
    return {k: float(r / denom * 100.0) for k, r in zip(keys, ranks)}


def classify_regime(spy: Features | None) -> dict[str, Any]:
    if spy is None:
        return {
            "label": "UNKNOWN",
            "note": "SPY data unavailable — no regime adjustment",
        }
    if spy.close > spy.sma50 > spy.sma200:
        label, note = (
            "RISK_ON",
            "SPY above rising 50/200-day — longs favoured, shorts need +10",
        )
    elif spy.close < spy.sma200 and spy.sma50 < spy.sma200:
        label, note = (
            "RISK_OFF",
            "SPY below 200-day downtrend — shorts favoured, longs need +10",
        )
    else:
        label, note = "NEUTRAL", "SPY mixed vs 50/200-day — no threshold adjustment"
    return {
        "label": label,
        "note": note,
        "spy_close": round(spy.close, 2),
        "spy_sma50": round(spy.sma50, 2),
        "spy_sma200": round(spy.sma200, 2),
    }


def _tested_support(f: Features) -> bool:
    """Low of the last 3 bars came within 0.5 ATR of the 20/50-day and price closed back above it."""
    band = 0.5 * f.atr
    return any(
        abs(f.recent_low3 - level) <= band and f.close > level
        for level in (f.sma20, f.sma50)
    )


def _tested_resistance(f: Features) -> bool:
    band = 0.5 * f.atr
    return any(
        abs(f.recent_high3 - level) <= band and f.close < level
        for level in (f.sma20, f.sma50)
    )


def score_long(f: Features, rs_pct: float) -> tuple[float, str, list[str]]:
    score = 0.0
    why: list[str] = []
    if f.close > f.sma200:
        score += 15
    if f.sma50 > f.sma200:
        score += 10
    if f.close > f.sma50:
        score += 10
    if f.close > f.sma20:
        score += 5
    if f.close > f.sma50 > f.sma200:
        why.append("Uptrend: above rising 50/200-day")
    score += rs_pct * 0.25
    if rs_pct >= 80:
        why.append(f"Relative strength top {100 - rs_pct:.0f}% vs SPY")
    if f.ret_3m > 0:
        score += 5
    if f.hi52 > 0 and f.close >= f.hi52 * 0.85:
        score += 5
        if f.close >= f.hi52 * 0.97:
            why.append("Near 52-week high")

    setup = ""
    if f.close > f.hi20_prev and f.vol_ratio >= 1.5:
        score += 25
        setup = "Breakout"
        why.append(f"20-day breakout on {f.vol_ratio:.1f}x volume")
    elif f.close > f.hi20_prev and f.vol_ratio >= 1.0:
        score += 15
        setup = "Breakout"
        why.append("20-day breakout (volume average)")
    elif (
        f.close > f.sma50 > f.sma200
        and f.close > f.prev_close
        and 40 <= f.rsi <= 60
        and _tested_support(f)
    ):
        score += 20
        setup = "Pullback bounce"
        why.append("Bounced off 20/50-day support in uptrend")

    if f.rsi > 75:
        score -= 15
        why.append(f"Overbought RSI {f.rsi:.0f} — chase risk")
    if f.dist_sma20_atr > 4:
        score -= 15
        why.append(f"Extended {f.dist_sma20_atr:.1f} ATR above 20-day")
    return max(0.0, min(100.0, score)), setup, why


def score_short(f: Features, rs_pct: float) -> tuple[float, str, list[str]]:
    score = 0.0
    why: list[str] = []
    if f.close < f.sma200:
        score += 15
    if f.sma50 < f.sma200:
        score += 10
    if f.close < f.sma50:
        score += 10
    if f.close < f.sma20:
        score += 5
    if f.close < f.sma50 < f.sma200:
        why.append("Downtrend: below falling 50/200-day")
    score += (100.0 - rs_pct) * 0.25
    if rs_pct <= 20:
        why.append(f"Relative strength bottom {rs_pct:.0f}% vs SPY")
    if f.ret_3m < 0:
        score += 5
    if f.hi52 > 0 and f.close <= f.hi52 * 0.75:
        score += 5
        if f.lo52 > 0 and f.close <= f.lo52 * 1.03:
            why.append("Near 52-week low")

    setup = ""
    if f.close < f.lo20_prev and f.vol_ratio >= 1.5:
        score += 25
        setup = "Breakdown"
        why.append(f"20-day breakdown on {f.vol_ratio:.1f}x volume")
    elif f.close < f.lo20_prev and f.vol_ratio >= 1.0:
        score += 15
        setup = "Breakdown"
        why.append("20-day breakdown (volume average)")
    elif (
        f.close < f.sma50 < f.sma200
        and f.close < f.prev_close
        and 40 <= f.rsi <= 60
        and _tested_resistance(f)
    ):
        score += 20
        setup = "Failed rally"
        why.append("Rejected at 20/50-day resistance in downtrend")

    if f.rsi < 25:
        score -= 15
        why.append(f"Oversold RSI {f.rsi:.0f} — squeeze risk")
    if f.dist_sma20_atr < -4:
        score -= 15
        why.append(f"Extended {-f.dist_sma20_atr:.1f} ATR below 20-day")
    return max(0.0, min(100.0, score)), setup, why


def trade_plan(f: Features, side: str) -> dict[str, float]:
    """Entry at last price; structural stop clamped to 1-3 ATR; targets at 2R / 3R."""
    entry = f.close
    if side == "BUY":
        stop = f.swing_low10 - 0.25 * f.atr
        stop = min(max(stop, entry - 3.0 * f.atr), entry - 1.0 * f.atr)
        risk = entry - stop
        t1, t2 = entry + 2 * risk, entry + 3 * risk
    else:
        stop = f.swing_high10 + 0.25 * f.atr
        stop = max(min(stop, entry + 3.0 * f.atr), entry + 1.0 * f.atr)
        risk = stop - entry
        t1, t2 = entry - 2 * risk, entry - 3 * risk
    return {
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target1": round(t1, 2),
        "target2": round(t2, 2),
        "risk_pct": round(risk / entry * 100, 2) if entry else 0.0,
        "rr_target1": 2.0,
        "rr_target2": 3.0,
    }


def bucket_for(
    score: float,
    setup: str,
    side: str,
    regime: str,
    rs_pct: float = 50.0,
    risk_pct: float = 0.0,
) -> str | None:
    if not setup or risk_pct > MAX_RISK_PCT:
        return None
    headwind = (side == "BUY" and regime == "RISK_OFF") or (
        side == "SELL" and regime == "RISK_ON"
    )
    bump = REGIME_HEADWIND_PENALTY if headwind else 0.0
    rs_ok = (
        rs_pct >= STRONG_RS_PERCENTILE
        if side == "BUY"
        else rs_pct <= 100 - STRONG_RS_PERCENTILE
    )
    if score >= STRONG_THRESHOLD + bump and rs_ok:
        return "strong_buy" if side == "BUY" else "strong_sell"
    if score >= SIGNAL_THRESHOLD + bump:
        return "buy" if side == "BUY" else "sell"
    return None


def holding_alert(
    f: Features, short_score: float, short_setup: str, avg_cost: float | None
) -> dict[str, Any]:
    """EXIT / TRIM / HOLD for a held long position."""
    reasons: list[str] = []
    action = "HOLD"
    trail = round(f.chandelier_long, 2)
    if f.close < f.chandelier_long:
        action = "EXIT"
        reasons.append(f"Closed below trailing stop {trail} (22-day high - 3 ATR)")
    if short_setup == "Breakdown":
        action = "EXIT"
        reasons.append("20-day breakdown")
    if f.close < f.sma50 and short_score >= 55:
        action = "EXIT"
        reasons.append("Lost 50-day with weak relative strength")
    if action == "HOLD" and (f.rsi > 78 or f.dist_sma20_atr > 4):
        action = "TRIM"
        reasons.append(
            f"Stretched: RSI {f.rsi:.0f}, {f.dist_sma20_atr:.1f} ATR above 20-day — take partial profit"
        )
    if action == "HOLD":
        reasons.append("Trend intact above trailing stop")
    pnl_pct = None
    if avg_cost and avg_cost > 0:
        pnl_pct = round((f.close / avg_cost - 1) * 100, 2)
    return {
        "ticker": f.ticker,
        "action": action,
        "price": round(f.close, 2),
        "trailing_stop": trail,
        "pnl_pct": pnl_pct,
        "rsi": round(f.rsi, 1),
        "reasons": reasons,
    }


@dataclass
class BoardInputs:
    features: dict[str, Features]
    sectors: dict[str, str]
    benchmark: Features | None
    holdings: list[dict[str, Any]] = field(default_factory=list)


def _signal_row(
    f: Features,
    side: str,
    bucket: str,
    score: float,
    setup: str,
    why: list[str],
    rs_pct: float,
    sector: str,
) -> dict[str, Any]:
    plan = trade_plan(f, side)
    if side == "BUY":
        invalidation = f"Close below {plan['stop']} invalidates the long"
    else:
        invalidation = f"Close above {plan['stop']} invalidates the short"
    return {
        "ticker": f.ticker,
        "sector": sector,
        "side": side,
        "bucket": bucket,
        "score": round(score, 1),
        "setup": setup,
        "price": round(f.close, 2),
        "change_1d_pct": round(f.ret_1d, 2),
        **plan,
        "why": why,
        "invalidation": invalidation,
        "rsi": round(f.rsi, 1),
        "rs_percentile": round(rs_pct, 0),
        "volume_ratio": round(f.vol_ratio, 2),
        "authority": AUTHORITY["label"],
    }


def _cap_by_sector(
    rows: list[dict[str, Any]], cap: int, per_sector: int
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    per: dict[str, int] = {}
    for r in rows:
        s = r.get("sector") or "Unknown"
        if per.get(s, 0) >= per_sector:
            continue
        per[s] = per.get(s, 0) + 1
        out.append(r)
        if len(out) >= cap:
            break
    return out


def build_board(inputs: BoardInputs) -> dict[str, Any]:
    """Rank all liquid names into BUY/SELL buckets + watchlists + holding alerts."""
    liquid = {t: f for t, f in inputs.features.items() if is_liquid(f)}
    rs_pct = percentile_ranks({t: f.rs_raw for t, f in liquid.items()})
    regime = classify_regime(inputs.benchmark)

    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in BUCKET_ORDER}
    watch_long: list[dict[str, Any]] = []
    watch_short: list[dict[str, Any]] = []
    short_scores: dict[str, tuple[float, str]] = {}

    for t, f in liquid.items():
        sector = inputs.sectors.get(t, "Unknown")
        pct = rs_pct.get(t, 50.0)
        ls, lsetup, lwhy = score_long(f, pct)
        ss, ssetup, swhy = score_short(f, pct)
        short_scores[t] = (ss, ssetup)

        lb = bucket_for(
            ls, lsetup, "BUY", regime["label"], pct, trade_plan(f, "BUY")["risk_pct"]
        )
        sb = bucket_for(
            ss, ssetup, "SELL", regime["label"], pct, trade_plan(f, "SELL")["risk_pct"]
        )
        if lb and (not sb or ls >= ss):
            buckets[lb].append(_signal_row(f, "BUY", lb, ls, lsetup, lwhy, pct, sector))
        elif sb:
            buckets[sb].append(
                _signal_row(f, "SELL", sb, ss, ssetup, swhy, pct, sector)
            )
        elif ls >= SIGNAL_THRESHOLD and not lsetup:
            watch_long.append(
                {
                    "ticker": t,
                    "sector": sector,
                    "score": round(ls, 1),
                    "price": round(f.close, 2),
                    "why": lwhy,
                    "wait_for": f"Break above {round(f.hi20_prev, 2)} on volume or pullback to 20-day {round(f.sma20, 2)}",
                }
            )
        elif ss >= SIGNAL_THRESHOLD and not ssetup:
            watch_short.append(
                {
                    "ticker": t,
                    "sector": sector,
                    "score": round(ss, 1),
                    "price": round(f.close, 2),
                    "why": swhy,
                    "wait_for": f"Break below {round(f.lo20_prev, 2)} on volume or failed rally at 20-day {round(f.sma20, 2)}",
                }
            )

    totals = {b: len(rows) for b, rows in buckets.items()}
    for b in BUCKET_ORDER:
        buckets[b].sort(key=lambda r: (-r["score"], -r["volume_ratio"]))
        buckets[b] = _cap_by_sector(buckets[b], BUCKET_CAP, SECTOR_CAP_PER_BUCKET)
    watch_long.sort(key=lambda r: -r["score"])
    watch_short.sort(key=lambda r: -r["score"])

    holdings_out: list[dict[str, Any]] = []
    for h in inputs.holdings:
        t = str(h.get("ticker") or "").upper()
        f = inputs.features.get(t)
        if f is None:
            holdings_out.append(
                {"ticker": t, "action": "NO DATA", "reasons": ["No price history"]}
            )
            continue
        ss, ssetup = short_scores.get(t) or score_short(f, rs_pct.get(t, 50.0))[:2]
        avg_cost = h.get("avg_cost") or h.get("entry_price")
        holdings_out.append(
            holding_alert(f, ss, ssetup, float(avg_cost) if avg_cost else None)
        )
    order = {"EXIT": 0, "TRIM": 1, "HOLD": 2, "NO DATA": 3}
    holdings_out.sort(key=lambda r: order.get(r["action"], 9))

    top_buy = (buckets["strong_buy"] or buckets["buy"] or [None])[0]
    top_sell = (buckets["strong_sell"] or buckets["sell"] or [None])[0]
    return {
        "regime": regime,
        "buckets": buckets,
        "bucket_totals": totals,
        "watch": {
            "long": _cap_by_sector(watch_long, BUCKET_CAP, SECTOR_CAP_PER_BUCKET),
            "short": _cap_by_sector(watch_short, BUCKET_CAP, SECTOR_CAP_PER_BUCKET),
        },
        "holdings": holdings_out,
        "headline": {
            "top_buy": top_buy["ticker"] if top_buy else None,
            "top_sell": top_sell["ticker"] if top_sell else None,
            "buy_count": totals["strong_buy"] + totals["buy"],
            "sell_count": totals["strong_sell"] + totals["sell"],
            "exit_alerts": sum(1 for h in holdings_out if h.get("action") == "EXIT"),
        },
        "universe": {"with_data": len(inputs.features), "liquid": len(liquid)},
    }


# ── Track record ─────────────────────────────────────────────────────────────


def evaluate_signal(
    side: str,
    entry: float,
    stop: float,
    target: float,
    highs: Sequence[float],
    lows: Sequence[float],
    last_close: float,
) -> dict[str, Any]:
    """Walk bars after the signal day. Stop is checked first on a bar that hits both."""
    risk = abs(entry - stop)
    if risk <= 0:
        return {"status": "invalid", "r": 0.0}
    for hi, lo in zip(highs, lows):
        if side == "BUY":
            if lo <= stop:
                return {"status": "stopped", "r": -1.0}
            if hi >= target:
                return {"status": "target", "r": round((target - entry) / risk, 2)}
        else:
            if hi >= stop:
                return {"status": "stopped", "r": -1.0}
            if lo <= target:
                return {"status": "target", "r": round((entry - target) / risk, 2)}
    move = (last_close - entry) if side == "BUY" else (entry - last_close)
    return {"status": "open", "r": round(move / risk, 2)}


def summarize_track_record(results: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [r for r in results if r["status"] in ("target", "stopped")]
    wins = [r for r in closed if r["status"] == "target"]
    by_bucket: dict[str, dict[str, Any]] = {}
    for r in results:
        b = by_bucket.setdefault(
            r["bucket"], {"signals": 0, "closed": 0, "wins": 0, "total_r": 0.0}
        )
        b["signals"] += 1
        if r["status"] in ("target", "stopped"):
            b["closed"] += 1
            b["total_r"] += r["r"]
            if r["status"] == "target":
                b["wins"] += 1
    for b in by_bucket.values():
        b["win_rate"] = round(b["wins"] / b["closed"] * 100, 1) if b["closed"] else None
        b["avg_r"] = round(b["total_r"] / b["closed"], 2) if b["closed"] else None
        b["total_r"] = round(b["total_r"], 2)
    return {
        "window_days": TRACK_RECORD_DAYS,
        "signals": len(results),
        "closed": len(closed),
        "open": sum(1 for r in results if r["status"] == "open"),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_r_closed": round(sum(r["r"] for r in closed) / len(closed), 2)
        if closed
        else None,
        "by_bucket": by_bucket,
        "note": "Target 1 (2R) vs stop; stop wins ties. Needs a few sessions of history to be meaningful.",
    }


# ── Market session helpers ───────────────────────────────────────────────────


def market_session(now: datetime | None = None) -> dict[str, Any]:
    now_et = (now or datetime.now(timezone.utc)).astimezone(_ET)
    open_t = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    weekday = now_et.weekday() < 5
    is_open = weekday and open_t <= now_et < close_t
    elapsed = (
        (now_et - open_t).total_seconds() / (close_t - open_t).total_seconds()
        if is_open
        else 1.0
    )
    return {
        "is_open": is_open,
        "now_et": now_et.isoformat(timespec="minutes"),
        "session_fraction": round(max(0.1, min(1.0, elapsed)), 3),
        "trading_day": now_et.date().isoformat(),
    }


# ── IO: universe, holdings, download, persistence ────────────────────────────


def load_universe(path: Path = UNIVERSE_PATH) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        s["ticker"]: s.get("sector") or "Unknown"
        for s in data.get("symbols", [])
        if s.get("ticker")
    }


def load_holdings(path: Path = HOLDINGS_PATH) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("holdings") if isinstance(data, dict) else data
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("ticker")]


def _download_chunk(tickers: list[str]) -> dict[str, dict[str, np.ndarray]]:
    import yfinance as yf

    df = yf.download(
        tickers,
        period="1y",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
        auto_adjust=True,
    )
    out: dict[str, dict[str, np.ndarray]] = {}
    if df is None or df.empty:
        return out
    for t in tickers:
        try:
            sub = df[t] if len(tickers) > 1 else df
            sub = sub.dropna(subset=["Close"])
            if sub.empty:
                continue
            out[t] = {
                "high": sub["High"].to_numpy(dtype=float),
                "low": sub["Low"].to_numpy(dtype=float),
                "close": sub["Close"].to_numpy(dtype=float),
                "volume": sub["Volume"].to_numpy(dtype=float),
                "dates": [d.strftime("%Y-%m-%d") for d in sub.index],
            }
        except (KeyError, ValueError):
            continue
    return out


async def download_history(tickers: list[str]) -> dict[str, dict[str, np.ndarray]]:
    frames: dict[str, dict[str, np.ndarray]] = {}
    for i in range(0, len(tickers), DOWNLOAD_CHUNK):
        chunk = tickers[i : i + DOWNLOAD_CHUNK]
        try:
            frames.update(await asyncio.to_thread(_download_chunk, chunk))
        except Exception as exc:
            logger.warning(
                "[SignalBoard] download chunk %d failed: %s", i // DOWNLOAD_CHUNK, exc
            )
    return frames


def _record_signals(board: dict[str, Any], trading_day: str) -> None:
    """Append first occurrence per (day, ticker, side) to the monthly ledger."""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    ledger = STORE_DIR / f"signals_{trading_day[:7]}.jsonl"
    seen = set()
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            seen.add((r.get("date"), r.get("ticker"), r.get("side")))
    new_lines = []
    for b in BUCKET_ORDER:
        for s in board["buckets"][b]:
            key = (trading_day, s["ticker"], s["side"])
            if key in seen:
                continue
            seen.add(key)
            new_lines.append(
                json.dumps(
                    {
                        "date": trading_day,
                        "ticker": s["ticker"],
                        "side": s["side"],
                        "bucket": b,
                        "score": s["score"],
                        "setup": s["setup"],
                        "entry": s["entry"],
                        "stop": s["stop"],
                        "target1": s["target1"],
                        "recorded_at": board["generated_at"],
                    }
                )
            )
    if new_lines:
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(new_lines) + "\n")


def _load_ledger(since: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not STORE_DIR.exists():
        return rows
    for p in sorted(STORE_DIR.glob("signals_*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if date.fromisoformat(r["date"]) >= since:
                    rows.append(r)
            except (ValueError, KeyError):
                continue
    return rows


def compute_track_record(
    frames: dict[str, dict[str, Any]], today: str
) -> dict[str, Any]:
    since = date.fromisoformat(today) - timedelta(days=TRACK_RECORD_DAYS)
    results = []
    for r in _load_ledger(since):
        if r["date"] >= today:
            continue
        fr = frames.get(r["ticker"])
        if not fr:
            continue
        idx = [i for i, d in enumerate(fr["dates"]) if d > r["date"]]
        if not idx:
            continue
        start = idx[0]
        res = evaluate_signal(
            r["side"],
            r["entry"],
            r["stop"],
            r["target1"],
            fr["high"][start:],
            fr["low"][start:],
            float(fr["close"][-1]),
        )
        results.append({**res, "bucket": r.get("bucket", "?")})
    return summarize_track_record(results)


# ── Orchestration ────────────────────────────────────────────────────────────

_LATEST: dict[str, Any] = {}
_BUILD_LOCK = asyncio.Lock()


def _clean(obj: Any) -> Any:
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


async def refresh_signal_board(source: str = "manual") -> dict[str, Any]:
    """Download, score, persist. Serialised; concurrent callers get the fresh result."""
    global _LATEST
    async with _BUILD_LOCK:
        t0 = time.time()
        sectors = load_universe()
        tickers = list(dict.fromkeys([BENCHMARK, *sectors]))
        session = market_session()
        frames = await download_history(tickers)
        vol_scale = 1.0 / session["session_fraction"] if session["is_open"] else 1.0

        bench = frames.get(BENCHMARK)
        bench_close = bench["close"] if bench else None
        feats: dict[str, Features] = {}
        for t, fr in frames.items():
            f = compute_features(
                t,
                fr["high"],
                fr["low"],
                fr["close"],
                fr["volume"],
                bench_close=bench_close,
                volume_scale=vol_scale,
                last_bar=fr["dates"][-1] if fr["dates"] else "",
            )
            if f is not None:
                feats[t] = f
        bench_f = feats.pop(BENCHMARK, None)
        if BENCHMARK in sectors and bench_f is not None:
            feats[BENCHMARK] = bench_f

        board = build_board(BoardInputs(feats, sectors, bench_f, load_holdings()))
        now = datetime.now(timezone.utc)
        last_bar = bench_f.last_bar if bench_f else ""
        board.update(
            {
                "status": "ok",
                "generated_at": now.isoformat(timespec="seconds"),
                "source": source,
                "as_of_bar": last_bar,
                "session": session,
                "partial_bar": session["is_open"],
                "next_refresh_at": (
                    now + timedelta(seconds=_next_interval(session))
                ).isoformat(timespec="seconds"),
                "authority": AUTHORITY,
                "method": METHOD,
                "elapsed_s": round(time.time() - t0, 1),
            }
        )
        board["universe"].update({"requested": len(tickers), "downloaded": len(frames)})
        try:
            board["track_record"] = compute_track_record(frames, session["trading_day"])
        except Exception as exc:
            logger.warning("[SignalBoard] track record failed: %s", exc)
            board["track_record"] = summarize_track_record([])
        board = _clean(board)
        try:
            _record_signals(board, session["trading_day"])
            STORE_DIR.mkdir(parents=True, exist_ok=True)
            LATEST_PATH.write_text(json.dumps(board), encoding="utf-8")
        except OSError as exc:
            logger.warning("[SignalBoard] persist failed: %s", exc)
        _LATEST = board
        h = board["headline"]
        logger.info(
            "[SignalBoard] %s: %d/%d liquid, %d BUY, %d SELL, %d exit alerts in %.1fs",
            source,
            board["universe"]["liquid"],
            len(tickers),
            h["buy_count"],
            h["sell_count"],
            h["exit_alerts"],
            board["elapsed_s"],
        )
        return board


def get_latest() -> dict[str, Any]:
    global _LATEST
    if not _LATEST and LATEST_PATH.exists():
        try:
            _LATEST = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
            _LATEST["source"] = "disk_cache"
        except (OSError, ValueError):
            _LATEST = {}
    return _LATEST


def is_refreshing() -> bool:
    return _BUILD_LOCK.locked()


def _next_interval(session: dict[str, Any]) -> int:
    return 3600 if session["is_open"] else 4 * 3600


async def signal_board_loop(initial_delay: float = 90.0) -> None:
    """Hourly in US market hours, every 4h otherwise. Never raises."""
    await asyncio.sleep(initial_delay)
    while True:
        session = market_session()
        try:
            await refresh_signal_board(
                source="hourly" if session["is_open"] else "off_hours"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[SignalBoard] refresh failed: %s", exc)
        await asyncio.sleep(_next_interval(market_session()))
