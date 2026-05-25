"""Live single-stock research dossier."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.api.live_state import fetch_regime_state
from src.core.risk_limits import SIGNAL_THRESHOLDS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live"])


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
    rsi = 50.0
    sma20 = sma50 = sma200 = 0.0
    above_sma20 = above_sma50 = above_sma200 = False
    vol_ratio = 1.0
    high_52w = low_52w = price
    atr = 0.0
    support = resistance = price
    bbands_upper = bbands_lower = price
    macd_signal = "NEUTRAL"
    daily_returns = []
    support_dist_pct = 0.0
    resistance_dist_pct = 0.0

    try:
        hist = await mds.get_history(ticker, period="1y", interval="1d")
        if hist is not None and len(hist) >= 20:
            c = "Close" if "Close" in hist.columns else "close"
            h = "High" if "High" in hist.columns else "high"
            lo = "Low" if "Low" in hist.columns else "low"
            v = "Volume" if "Volume" in hist.columns else "volume"
            close = hist[c]
            highs = hist[h]
            lows = hist[lo]

            # SMAs
            sma20 = float(close.rolling(20).mean().iloc[-1])
            above_sma20 = price > sma20
            if len(close) >= 50:
                sma50 = float(close.rolling(50).mean().iloc[-1])
                above_sma50 = price > sma50
            if len(close) >= 200:
                sma200 = float(close.rolling(200).mean().iloc[-1])
                above_sma200 = price > sma200

            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi_s = 100 - (100 / (1 + rs))
            rsi = float(rsi_s.iloc[-1]) if not rsi_s.empty else 50

            # ATR(14)
            tr = (
                (highs - lows)
                .combine_first((highs - close.shift(1)).abs())
                .combine_first((lows - close.shift(1)).abs())
            )
            atr = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else 0

            # Volume ratio
            vol_avg = float(hist[v].rolling(20).mean().iloc[-1])
            vol_now = float(hist[v].iloc[-1])
            vol_ratio = vol_now / vol_avg if vol_avg > 0 else 1.0

            # 52-week range
            high_52w = float(highs.max())
            low_52w = float(lows.min())

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

            # Distance % from price
            support_dist_pct = (
                round((price - support) / price * 100, 2) if support and price else 0
            )
            resistance_dist_pct = (
                round((resistance - price) / price * 100, 2)
                if resistance and price
                else 0
            )

            # Bollinger Bands
            bb_sma = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            bbands_upper = float((bb_sma + 2 * bb_std).iloc[-1])
            bbands_lower = float((bb_sma - 2 * bb_std).iloc[-1])

            # MACD signal
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            macd_signal = (
                "BULLISH"
                if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1])
                else "BEARISH"
            )

            # Daily returns for analog engine
            daily_returns = close.pct_change().dropna().tolist()[-60:]
    except Exception:
        pass

    # ── Factor chips ──
    factors = []
    _fc = lambda name, val, pos: factors.append(
        {"name": name, "value": val, "signal": pos}
    )
    _fc(
        "RSI",
        round(rsi, 1),
        (
            "positive"
            if rsi < SIGNAL_THRESHOLDS.rsi_near_oversold
            else "negative" if rsi > SIGNAL_THRESHOLDS.rsi_overbought else "neutral"
        ),
    )
    _fc(
        "MA20",
        f"{'Above' if above_sma20 else 'Below'}",
        "positive" if above_sma20 else "negative",
    )
    _fc(
        "MA50",
        f"{'Above' if above_sma50 else 'Below'}",
        "positive" if above_sma50 else "negative",
    )
    if sma200:
        _fc(
            "MA200",
            f"{'Above' if above_sma200 else 'Below'}",
            "positive" if above_sma200 else "negative",
        )
    _fc(
        "Volume",
        f"{vol_ratio:.1f}x avg",
        (
            "positive"
            if vol_ratio > SIGNAL_THRESHOLDS.volume_surge_threshold
            else "neutral"
        ),
    )
    _fc("MACD", macd_signal, "positive" if macd_signal == "BULLISH" else "negative")
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
    if rsi < SIGNAL_THRESHOLDS.rsi_near_oversold:
        why_buy.append(f"RSI {rsi:.0f} — oversold territory, mean reversion potential")
    if above_sma20 and above_sma50:
        why_buy.append("Trend aligned — price above both 20 & 50-day moving averages")
    elif above_sma20:
        why_buy.append("Short-term uptrend — price above 20-day MA")
    if macd_signal == "BULLISH":
        why_buy.append("MACD bullish crossover — momentum shifting upward")
    if vol_ratio > SIGNAL_THRESHOLDS.volume_strong_surge:
        why_buy.append(
            f"Volume surge {vol_ratio:.1f}x average — institutional accumulation signal"
        )
    if price < bbands_lower:
        why_buy.append(
            f"Below lower Bollinger Band (${bbands_lower:.2f}) — potential bounce zone"
        )
    if above_sma200:
        why_buy.append("Above 200-day MA — long-term uptrend intact")
    if not why_buy:
        why_buy.append("No strong bullish catalyst — monitoring for setup development")

    if rsi > SIGNAL_THRESHOLDS.rsi_overbought:
        why_stop.append(
            f"⚠️ RSI {rsi:.0f} (overbought >70) — pullback risk elevated, consider waiting for RSI to cool"
        )
    if not above_sma50:
        why_stop.append(
            f"⚠️ Below 50-day MA (${sma50:.2f}) — intermediate trend bearish, buying against the trend"
        )
    if not above_sma200 and sma200:
        why_stop.append(
            f"⚠️ Below 200-day MA (${sma200:.2f}) — long-term trend is down"
        )
    if macd_signal == "BEARISH":
        why_stop.append(
            "⚠️ MACD bearish — momentum fading, new entries carry higher risk"
        )
    if price > bbands_upper:
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
    risk_per_share = round(atr * 1.5, 2) if atr else round(price * 0.05, 2)
    trade_plan = {
        "entry_zone": [round(price * 0.98, 2), round(price * 1.01, 2)],
        "target_1r": round(price + risk_per_share * 2, 2),
        "target_2r": round(price + risk_per_share * 3, 2),
        "stop": round(price - risk_per_share, 2),
        "risk_per_share": risk_per_share,
        "rr_ratio": "1:2",
        "invalidation": f"Close below ${support:.2f}",
        "note": "ATR-based plan" if atr else "Percentage-based estimate",
    }

    # ── Regime context ──
    regime = await fetch_regime_state(request)
    regime_label = regime.regime
    should_trade = regime.should_trade

    # ── AI-powered analysis ──
    ai_analysis = None
    try:
        from src.services.ai_service import get_ai_service

        _ai = get_ai_service()
        if _ai.is_configured:
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
                "rsi": round(rsi, 1),
                "sma20": round(sma20, 2),
                "sma50": round(sma50, 2),
                "sma200": round(sma200, 2) if sma200 else None,
                "above_sma20": above_sma20,
                "above_sma50": above_sma50,
                "above_sma200": above_sma200,
                "atr": round(atr, 2),
                "volume_ratio": round(vol_ratio, 2),
                "macd_signal": macd_signal,
                "bbands_upper": round(bbands_upper, 2),
                "bbands_lower": round(bbands_lower, 2),
                "support": round(support, 2),
                "support_dist_pct": support_dist_pct,
                "resistance": round(resistance, 2),
                "resistance_dist_pct": resistance_dist_pct,
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
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


