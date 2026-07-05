"""Live chart OHLCV + pattern signals for lightweight-charts."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Query, Request

from src.api.deps import validate_ticker

router = APIRouter(prefix="/api/live", tags=["live"])


@router.get("/chart/{ticker}")
async def live_chart_data(
    ticker: str,
    request: Request,
    period: str = Query("6mo", description="1mo/3mo/6mo/1y"),
    signals: bool = Query(False, description="Include pattern signal markers"),
    benchmark: bool = Query(False, description="Include SPY comparison curve"),
):
    """Return OHLCV candle data + optional pattern signals + benchmark curve."""
    ticker = validate_ticker(ticker)
    mds = request.app.state.market_data
    hist = await mds.get_history(ticker, period=period, interval="1d")
    if hist is None or hist.empty:
        return {"candles": [], "sma20": [], "sma50": [], "signals": [], "benchmark": []}
    c_col = "Close" if "Close" in hist.columns else "close"
    o_col = "Open" if "Open" in hist.columns else "open"
    h_col = "High" if "High" in hist.columns else "high"
    l_col = "Low" if "Low" in hist.columns else "low"
    v_col = "Volume" if "Volume" in hist.columns else "volume"
    candles = []
    for idx_dt, row in hist.iterrows():
        ts = int(idx_dt.timestamp()) if hasattr(idx_dt, "timestamp") else 0
        candles.append(
            {
                "time": ts,
                "open": round(float(row[o_col]), 2),
                "high": round(float(row[h_col]), 2),
                "low": round(float(row[l_col]), 2),
                "close": round(float(row[c_col]), 2),
                "volume": int(row[v_col]) if not np.isnan(row[v_col]) else 0,
            }
        )
    # SMA overlays
    close_arr = hist[c_col].values.astype(float)
    high_arr = hist[h_col].values.astype(float)
    low_arr = hist[l_col].values.astype(float)
    vol_arr = hist[v_col].values.astype(float)
    sma20_data = []
    sma50_data = []
    sma20_arr = np.full(len(close_arr), np.nan)
    sma50_arr = np.full(len(close_arr), np.nan)
    for j in range(len(candles)):
        t = candles[j]["time"]
        if j >= 19:
            v20 = float(np.mean(close_arr[j - 19 : j + 1]))
            sma20_arr[j] = v20
            sma20_data.append({"time": t, "value": round(v20, 2)})
        if j >= 49:
            v50 = float(np.mean(close_arr[j - 49 : j + 1]))
            sma50_arr[j] = v50
            sma50_data.append({"time": t, "value": round(v50, 2)})

    # ── Pattern signal detection ──
    sig_list = []
    if signals and len(close_arr) >= 50:
        # RSI(14)
        deltas = np.diff(close_arr)
        gain = np.where(deltas > 0, deltas, 0.0)
        loss = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.zeros(len(close_arr))
        avg_loss = np.zeros(len(close_arr))
        rsi_arr = np.full(len(close_arr), 50.0)
        if len(gain) >= 14:
            avg_gain[14] = np.mean(gain[:14])
            avg_loss[14] = np.mean(loss[:14])
            for k in range(15, len(close_arr)):
                avg_gain[k] = (avg_gain[k - 1] * 13 + gain[k - 1]) / 14
                avg_loss[k] = (avg_loss[k - 1] * 13 + loss[k - 1]) / 14
                rs = avg_gain[k] / avg_loss[k] if avg_loss[k] > 0 else 100.0
                rsi_arr[k] = 100.0 - (100.0 / (1.0 + rs))

        # Volume average (20-day)
        vol_sma20 = np.full(len(vol_arr), np.nan)
        for k in range(19, len(vol_arr)):
            vol_sma20[k] = np.mean(vol_arr[k - 19 : k + 1])

        for j in range(50, len(candles)):
            t = candles[j]["time"]
            p = close_arr[j]
            # 1) Golden Cross (SMA20 > SMA50, prior bar SMA20 <= SMA50)
            if (
                not np.isnan(sma20_arr[j])
                and not np.isnan(sma50_arr[j])
                and not np.isnan(sma20_arr[j - 1])
                and not np.isnan(sma50_arr[j - 1])
            ):
                if sma20_arr[j] > sma50_arr[j] and sma20_arr[j - 1] <= sma50_arr[j - 1]:
                    sig_list.append(
                        {
                            "time": t,
                            "position": "belowBar",
                            "color": "#00d4aa",
                            "shape": "arrowUp",
                            "text": "Golden ✕",
                            "price": round(p, 2),
                            "type": "golden_cross",
                        }
                    )
                # 2) Death Cross
                if sma20_arr[j] < sma50_arr[j] and sma20_arr[j - 1] >= sma50_arr[j - 1]:
                    sig_list.append(
                        {
                            "time": t,
                            "position": "aboveBar",
                            "color": "#ff5c5c",
                            "shape": "arrowDown",
                            "text": "Death ✕",
                            "price": round(p, 2),
                            "type": "death_cross",
                        }
                    )
            # 3) RSI oversold bounce (RSI crossed back above 30)
            if j >= 15 and rsi_arr[j] > 30 and rsi_arr[j - 1] <= 30:
                sig_list.append(
                    {
                        "time": t,
                        "position": "belowBar",
                        "color": "#58a6ff",
                        "shape": "circle",
                        "text": "RSI↑30",
                        "price": round(p, 2),
                        "type": "rsi_oversold_bounce",
                    }
                )
            # 4) RSI overbought reversal (RSI crossed below 70)
            if j >= 15 and rsi_arr[j] < 70 and rsi_arr[j - 1] >= 70:
                sig_list.append(
                    {
                        "time": t,
                        "position": "aboveBar",
                        "color": "#fbbf24",
                        "shape": "circle",
                        "text": "RSI↓70",
                        "price": round(p, 2),
                        "type": "rsi_overbought_reversal",
                    }
                )
            # 5) Volume breakout (price at 20-day high + volume > 2x average)
            if j >= 20 and not np.isnan(vol_sma20[j]) and vol_sma20[j] > 0:
                high_20 = np.max(high_arr[j - 20 : j])
                if high_arr[j] > high_20 and vol_arr[j] > vol_sma20[j] * 2.0:
                    sig_list.append(
                        {
                            "time": t,
                            "position": "belowBar",
                            "color": "#bc8cff",
                            "shape": "arrowUp",
                            "text": "Vol BO",
                            "price": round(p, 2),
                            "type": "volume_breakout",
                        }
                    )
            # 6) Pullback to SMA20 in uptrend (close touches SMA20 ±1%, SMA20>SMA50)
            if (
                not np.isnan(sma20_arr[j])
                and not np.isnan(sma50_arr[j])
                and sma20_arr[j] > sma50_arr[j]
            ):
                dist_pct = abs(p - sma20_arr[j]) / sma20_arr[j]
                if dist_pct < 0.01 and low_arr[j] <= sma20_arr[j] * 1.005:
                    sig_list.append(
                        {
                            "time": t,
                            "position": "belowBar",
                            "color": "#00d4aa",
                            "shape": "circle",
                            "text": "PB20",
                            "price": round(p, 2),
                            "type": "pullback_sma20",
                        }
                    )

    # ── Benchmark comparison (SPY) ──
    bench_data = []
    if benchmark and candles:
        try:
            spy_hist = await mds.get_history("SPY", period=period, interval="1d")
            if spy_hist is not None and not spy_hist.empty:
                spy_c = "Close" if "Close" in spy_hist.columns else "close"
                spy_close = spy_hist[spy_c]
                # Normalize both to 100 at start
                stock_base = close_arr[0] if close_arr[0] > 0 else 1.0
                spy_vals = spy_close.values.astype(float)
                spy_base = spy_vals[0] if spy_vals[0] > 0 else 1.0
                stock_norm = []
                for j in range(len(candles)):
                    stock_norm.append(
                        {
                            "time": candles[j]["time"],
                            "value": round(close_arr[j] / stock_base * 100, 2),
                        }
                    )
                for idx_dt, val in spy_close.items():
                    ts = int(idx_dt.timestamp()) if hasattr(idx_dt, "timestamp") else 0
                    bench_data.append(
                        {"time": ts, "value": round(float(val) / spy_base * 100, 2)}
                    )
        except Exception:
            pass  # Benchmark is optional — don't fail the chart

    return {
        "candles": candles,
        "sma20": sma20_data,
        "sma50": sma50_data,
        "signals": sig_list,
        "benchmark": bench_data,
        "stock_norm": (
            [
                {
                    "time": candles[j]["time"],
                    "value": round(
                        close_arr[j] / (close_arr[0] if close_arr[0] > 0 else 1) * 100,
                        2,
                    ),
                }
                for j in range(len(candles))
            ]
            if benchmark
            else []
        ),
    }


