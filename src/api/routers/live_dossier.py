"""Live single-stock research dossier."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import math

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.api.live_state import fetch_regime_state
from src.core.risk_limits import SIGNAL_THRESHOLDS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live"])


def _finite(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _round(x, nd):
    return None if x is None else round(x, nd)


@router.get("/dossier/{ticker}")
async def live_dossier(ticker: str, request: Request):
    """Phase 2: Deep single-stock research dossier.

    Returns: snapshot, technicals, factor chips, support/resistance,
    trade plan, counter-thesis, WHY BUY / WHY STOP, historical analogs.
    """
    ticker = validate_ticker(ticker)
    mds = request.app.state.market_data

    q_raw = await mds.get_quote(ticker)
    if q_raw is None:
        raise HTTPException(404, f"No data for {ticker}")

    price = q_raw["price"]
    change_pct = q_raw["change_pct"]
    prev_close = round(price - q_raw.get("change", 0), 2)
    volume = q_raw.get("volume", 0)

    # ── Technical analysis via history ──
    # Every indicator stays None unless computed from enough real bars.
    rsi = None
    sma20 = sma50 = sma200 = None
    above_sma20 = above_sma50 = above_sma200 = None
    vol_ratio = None
    high_52w = low_52w = None
    atr = None
    support = resistance = None
    bbands_upper = bbands_lower = None
    macd_signal = None
    daily_returns = []
    support_dist_pct = None
    resistance_dist_pct = None
    technicals_error = None

    try:
        hist = await mds.get_history(ticker, period="1y", interval="1d")
        if hist is None or len(hist) < 20:
            technicals_error = "insufficient_history"
        else:
            c = "Close" if "Close" in hist.columns else "close"
            h = "High" if "High" in hist.columns else "high"
            lo = "Low" if "Low" in hist.columns else "low"
            v = "Volume" if "Volume" in hist.columns else "volume"
            close = hist[c]
            highs = hist[h]
            lows = hist[lo]

            # SMAs
            sma20 = _finite(close.rolling(20).mean().iloc[-1])
            above_sma20 = None if sma20 is None else price > sma20
            if len(close) >= 50:
                sma50 = _finite(close.rolling(50).mean().iloc[-1])
                above_sma50 = None if sma50 is None else price > sma50
            if len(close) >= 200:
                sma200 = _finite(close.rolling(200).mean().iloc[-1])
                above_sma200 = None if sma200 is None else price > sma200

            # RSI(14); a window with no losses is a genuine 100.
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            g, l_ = _finite(gain.iloc[-1]), _finite(loss.iloc[-1])
            if g is not None and l_ is not None:
                rsi = 100.0 if l_ == 0 else 100 - (100 / (1 + g / l_))

            # ATR(14) — true range is the max of the three ranges.
            prior_close = close.shift(1)
            tr = pd.concat(
                [highs - lows, (highs - prior_close).abs(), (lows - prior_close).abs()],
                axis=1,
            ).max(axis=1, skipna=False)
            atr = _finite(tr.rolling(14).mean().iloc[-1])
            if atr is not None and atr <= 0:
                atr = None

            # Volume ratio
            if v in hist.columns:
                vol_avg = _finite(hist[v].rolling(20).mean().iloc[-1])
                vol_now = _finite(hist[v].iloc[-1])
                if vol_avg and vol_avg > 0 and vol_now is not None:
                    vol_ratio = vol_now / vol_avg

            # 52-week range
            high_52w = _finite(highs.max())
            low_52w = _finite(lows.min())

            # Support / Resistance — swing pivots (not naive 20-day low/high)
            # Find swing lows (local minima) and swing highs (local maxima)
            _lookback = min(120, len(lows))
            _lows_arr = lows.iloc[-_lookback:].values.astype(float)
            _highs_arr = highs.iloc[-_lookback:].values.astype(float)
            _close_arr = close.iloc[-_lookback:].values.astype(float)

            swing_supports = []
            swing_resistances = []
            for i in range(2, len(_lows_arr) - 2):
                if _lows_arr[i] <= min(
                    _lows_arr[i - 1],
                    _lows_arr[i - 2],
                    _lows_arr[i + 1],
                    _lows_arr[i + 2],
                ):
                    swing_supports.append(float(_lows_arr[i]))
                if _highs_arr[i] >= max(
                    _highs_arr[i - 1],
                    _highs_arr[i - 2],
                    _highs_arr[i + 1],
                    _highs_arr[i + 2],
                ):
                    swing_resistances.append(float(_highs_arr[i]))

            # Nearest support = highest swing low BELOW current price
            support_candidates = [s for s in swing_supports if s < price * 0.995]
            support = (
                max(support_candidates)
                if support_candidates
                else float(lows.iloc[-20:].min())
            )

            # Nearest resistance = lowest swing high ABOVE current price
            resistance_candidates = [r for r in swing_resistances if r > price * 1.005]
            resistance = (
                min(resistance_candidates)
                if resistance_candidates
                else float(highs.iloc[-20:].max())
            )

            support = _finite(support)
            resistance = _finite(resistance)

            # Distance % from price
            if support is not None and price:
                support_dist_pct = round((price - support) / price * 100, 2)
            if resistance is not None and price:
                resistance_dist_pct = round((resistance - price) / price * 100, 2)

            # Bollinger Bands
            bb_sma = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            bbands_upper = _finite((bb_sma + 2 * bb_std).iloc[-1])
            bbands_lower = _finite((bb_sma - 2 * bb_std).iloc[-1])

            # MACD signal needs a seeded slow EMA (26) plus signal line (9).
            if len(close) >= 35:
                ema12 = close.ewm(span=12).mean()
                ema26 = close.ewm(span=26).mean()
                macd_line = ema12 - ema26
                signal_line = macd_line.ewm(span=9).mean()
                m, s_ = _finite(macd_line.iloc[-1]), _finite(signal_line.iloc[-1])
                if m is not None and s_ is not None:
                    macd_signal = "BULLISH" if m > s_ else "BEARISH"

            # Daily returns for analog engine
            daily_returns = close.pct_change().dropna().tolist()[-60:]
    except Exception as exc:
        technicals_error = "computation_failed"
        logger.warning("live dossier technicals failed for %s: %s", ticker, exc)

    # ── Factor chips ── (missing inputs show N/A and never count as signal)
    factors = []

    def _fc(name, val, pos):
        factors.append(
            {"name": name, "value": "N/A" if val is None else val, "signal": pos}
        )

    def _ma_chip(name, above):
        if above is None:
            _fc(name, None, "unavailable")
        else:
            _fc(name, "Above" if above else "Below", "positive" if above else "negative")

    if rsi is None:
        _fc("RSI", None, "unavailable")
    else:
        _fc(
            "RSI",
            round(rsi, 1),
            (
                "positive"
                if rsi < SIGNAL_THRESHOLDS.rsi_near_oversold
                else "negative" if rsi > SIGNAL_THRESHOLDS.rsi_overbought else "neutral"
            ),
        )
    _ma_chip("MA20", above_sma20)
    _ma_chip("MA50", above_sma50)
    if sma200 is not None:
        _ma_chip("MA200", above_sma200)
    if vol_ratio is None:
        _fc("Volume", None, "unavailable")
    else:
        _fc(
            "Volume",
            f"{vol_ratio:.1f}x avg",
            (
                "positive"
                if vol_ratio > SIGNAL_THRESHOLDS.volume_surge_threshold
                else "neutral"
            ),
        )
    if macd_signal is None:
        _fc("MACD", None, "unavailable")
    else:
        _fc("MACD", macd_signal, "positive" if macd_signal == "BULLISH" else "negative")
    if bbands_upper is None or bbands_lower is None:
        _fc("BBands", None, "unavailable")
    else:
        _fc(
            "BBands",
            f"{'Upper' if price > bbands_upper else 'Lower' if price < bbands_lower else 'Mid'}",
            (
                "negative"
                if price > bbands_upper
                else "positive" if price < bbands_lower else "neutral"
            ),
        )
    pos_count = sum(1 for f in factors if f["signal"] == "positive")
    neg_count = sum(1 for f in factors if f["signal"] == "negative")

    # ── WHY BUY / RISK FACTORS ──
    why_buy = []
    why_stop = []
    if technicals_error:
        why_stop.append(
            f"⚠️ Technicals unavailable ({technicals_error}) — no indicator-based view"
        )
    if rsi is not None and rsi < SIGNAL_THRESHOLDS.rsi_near_oversold:
        why_buy.append(f"RSI {rsi:.0f} — oversold territory, mean reversion potential")
    if above_sma20 and above_sma50:
        why_buy.append("Trend aligned — price above both 20 & 50-day moving averages")
    elif above_sma20:
        why_buy.append("Short-term uptrend — price above 20-day MA")
    if macd_signal == "BULLISH":
        why_buy.append("MACD bullish crossover — momentum shifting upward")
    if vol_ratio is not None and vol_ratio > SIGNAL_THRESHOLDS.volume_strong_surge:
        why_buy.append(
            f"Volume surge {vol_ratio:.1f}x average — institutional accumulation signal"
        )
    if bbands_lower is not None and price < bbands_lower:
        why_buy.append(
            f"Below lower Bollinger Band (${bbands_lower:.2f}) — potential bounce zone"
        )
    if above_sma200:
        why_buy.append("Above 200-day MA — long-term uptrend intact")
    if not why_buy:
        why_buy.append("No strong bullish catalyst — monitoring for setup development")

    if rsi is not None and rsi > SIGNAL_THRESHOLDS.rsi_overbought:
        why_stop.append(
            f"⚠️ RSI {rsi:.0f} (overbought >70) — pullback risk elevated, consider waiting for RSI to cool"
        )
    if above_sma50 is False:
        why_stop.append(
            f"⚠️ Below 50-day MA (${sma50:.2f}) — intermediate trend bearish, buying against the trend"
        )
    if above_sma200 is False:
        why_stop.append(
            f"⚠️ Below 200-day MA (${sma200:.2f}) — long-term trend is down"
        )
    if macd_signal == "BEARISH":
        why_stop.append(
            "⚠️ MACD bearish — momentum fading, new entries carry higher risk"
        )
    if bbands_upper is not None and price > bbands_upper:
        why_stop.append(
            f"⚠️ Above upper Bollinger Band (${bbands_upper:.2f}) — extended {round((price/bbands_upper-1)*100,1)}% beyond normal range"
        )
    # Support distance context
    if support and price:
        _s_dist = round((price - support) / price * 100, 1)
        if _s_dist > 10:
            why_stop.append(
                f"🛑 Nearest support ${support:.2f} is {_s_dist}% below — wide stop needed, poor risk/reward"
            )
        elif _s_dist > 5:
            why_stop.append(
                f"⚠️ Support at ${support:.2f} ({_s_dist}% below) — moderate risk distance"
            )
        else:
            why_stop.append(
                f"✅ Support nearby at ${support:.2f} ({_s_dist}% below) — tight stop possible"
            )
    why_stop.append(
        "📅 Check earnings calendar — earnings/ex-div/macro events may override technicals"
    )

    # ── Historical analogs (simplified: similar RSI + trend setups) ──
    analogs = []
    if daily_returns and len(daily_returns) >= 30:
        import numpy as np

        rets = np.array(daily_returns)
        # Look at 5-day / 10-day / 20-day forward returns from similar conditions
        current_5d_mom = float(np.sum(rets[-5:])) if len(rets) >= 5 else 0
        for window_name, fwd_days in [("5D", 5), ("10D", 10), ("20D", 20)]:
            if len(rets) > fwd_days + 5:
                fwd_rets = []
                for i in range(5, len(rets) - fwd_days):
                    mom_i = float(np.sum(rets[i - 5 : i]))
                    if abs(mom_i - current_5d_mom) < 0.03:  # similar setup
                        fwd_rets.append(float(np.sum(rets[i : i + fwd_days])))
                if fwd_rets:
                    analogs.append(
                        {
                            "window": window_name,
                            "sample_size": len(fwd_rets),
                            "median_return": round(float(np.median(fwd_rets)) * 100, 2),
                            "win_rate": round(
                                sum(1 for r in fwd_rets if r > 0) / len(fwd_rets) * 100,
                                1,
                            ),
                            "worst": round(float(min(fwd_rets)) * 100, 2),
                            "best": round(float(max(fwd_rets)) * 100, 2),
                        }
                    )

    # ── Trade plan ──
    # ATR projection only; structure-based levels and action gating live in
    # /api/dossier/{ticker}/plan. Without ATR there is no plan.
    from src.utils.numeric_parse import normalize_trade_plan

    if atr is None or not price:
        trade_plan = {
            "status": "UNAVAILABLE",
            "note": "No ATR — trade levels unavailable",
        }
    else:
        risk_per_share = round(atr * 1.5, 2)
        stop = round(price - risk_per_share, 2)
        target_1r = round(price + risk_per_share * 2, 2)
        trade_plan = normalize_trade_plan(
            {
                "status": "PROJECTION",
                "entry_zone": [round(price, 2), round(price, 2)],
                "target_1r": target_1r,
                "target_2r": round(price + risk_per_share * 3, 2),
                "stop": stop,
                "risk_per_share": risk_per_share,
                "rr_ratio": round((target_1r - price) / (price - stop), 2),
                "invalidation": (
                    f"Close below ${support:.2f}"
                    if support is not None
                    else f"Close below ${stop:.2f}"
                ),
                "note": "ATR projection (1.5×ATR stop, 2R/3R targets) — not a validated signal",
            }
        )

    # ── Regime context ──
    regime = await fetch_regime_state(request)
    regime_label = regime.regime
    should_trade = regime.should_trade

    # ── AI-powered analysis ──
    ai_analysis = None
    try:
        from src.services.ai_service import get_ai_service

        _ai = get_ai_service()
        if _ai.is_configured and technicals_error is None and atr is not None:
            _tech = {
                "price": price,
                "change_pct": change_pct,
                "rsi": rsi,
                "sma20": sma20,
                "sma50": sma50,
                "sma200": sma200,
                "above_sma20": above_sma20,
                "above_sma50": above_sma50,
                "above_sma200": above_sma200,
                "vol_ratio": vol_ratio,
                "atr": atr,
                "macd_signal": macd_signal,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "support": support,
                "resistance": resistance,
            }
            _reg = {"label": regime_label, "should_trade": should_trade}
            ai_analysis = await _ai.analyze_dossier(ticker, _tech, trade_plan, _reg)
    except Exception as _ai_exc:
        logger.debug("AI dossier analysis unavailable: %s", _ai_exc)

    return sanitize_for_json(
        {
            "symbol": ticker,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "prev_close": prev_close,
            "volume": volume,
            "technicals": {
                "rsi": _round(rsi, 1),
                "sma20": _round(sma20, 2),
                "sma50": _round(sma50, 2),
                "sma200": _round(sma200, 2),
                "above_sma20": above_sma20,
                "above_sma50": above_sma50,
                "above_sma200": above_sma200,
                "atr": _round(atr, 2),
                "volume_ratio": _round(vol_ratio, 2),
                "macd_signal": macd_signal,
                "bbands_upper": _round(bbands_upper, 2),
                "bbands_lower": _round(bbands_lower, 2),
                "support": _round(support, 2),
                "support_dist_pct": support_dist_pct,
                "resistance": _round(resistance, 2),
                "resistance_dist_pct": resistance_dist_pct,
                "high_52w": _round(high_52w, 2),
                "low_52w": _round(low_52w, 2),
                "error": technicals_error,
            },
            "factors": factors,
            "factor_summary": {
                "positive": pos_count,
                "negative": neg_count,
                "net": pos_count - neg_count,
            },
            "why_buy": why_buy,
            "why_stop": why_stop,
            "trade_plan": trade_plan,
            "analogs": analogs,
            "regime": {
                "label": regime_label,
                "should_trade": should_trade,
            },
            "ai_analysis": ai_analysis,
            "trust": {
                "mode": (
                    "PAPER"
                    if getattr(request.app.state, "engine", None)
                    and getattr(request.app.state.engine, "dry_run", True)
                    else "LIVE"
                ),
                "source": "market_data_service + computed",
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
        }
    )


