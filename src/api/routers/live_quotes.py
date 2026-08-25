"""Live quote, sparkline, perf-vs-SPY, and strategy list endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json, validate_ticker

router = APIRouter(prefix="/api/live", tags=["live"])


@router.get("/quote/{ticker}")
async def live_quote(ticker: str, request: Request):
    """Live quote for any ticker. Public, no auth."""
    symbol = validate_ticker(ticker)
    mds = request.app.state.market_data
    q_raw = await mds.get_quote(symbol)
    if q_raw is None:
        raise HTTPException(404, f"No data for {symbol}")

    q = {
        "symbol": symbol,
        "price": q_raw["price"],
        "change_pct": q_raw["change_pct"],
        "prev_close": round(q_raw["price"] - q_raw.get("change", 0), 2),
        "volume": q_raw.get("volume", 0),
    }

    try:
        hist = await mds.get_history(symbol, period="3mo", interval="1d")
        if hist is not None and len(hist) >= 20:
            c_col = "Close" if "Close" in hist.columns else "close"
            close = hist[c_col]
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = (
                float(close.rolling(50).mean().iloc[-1])
                if len(close) >= 50
                else 0
            )
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50
            v_col = "Volume" if "Volume" in hist.columns else "volume"
            vol_avg = float(hist[v_col].rolling(20).mean().iloc[-1])
            vol_now = float(hist[v_col].iloc[-1])
            vol_ratio = vol_now / vol_avg if vol_avg > 0 else 1.0
            q["sma20"] = round(sma20, 2)
            q["sma50"] = round(sma50, 2)
            q["rsi"] = round(rsi, 1)
            q["volume_ratio"] = round(vol_ratio, 2)
            q["above_sma20"] = q["price"] > sma20
            q["above_sma50"] = q["price"] > sma50 if sma50 else None
    except Exception:
        pass

    return {
        "quote": q,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/spark/{ticker}")
async def live_spark(
    ticker: str,
    request: Request,
    days: int = Query(20, ge=5, le=60),
):
    """Return last N closing prices for inline sparkline rendering."""
    symbol = validate_ticker(ticker)
    mds = request.app.state.market_data
    hist = await mds.get_history(symbol, period="3mo", interval="1d")
    if hist is None or hist.empty:
        return {"ticker": symbol, "prices": [], "change_pct": 0}
    c_col = "Close" if "Close" in hist.columns else "close"
    closes = hist[c_col].values.astype(float)[-days:]
    prices = [round(float(v), 2) for v in closes if not np.isnan(v)]
    change = (
        round((prices[-1] / prices[0] - 1) * 100, 2)
        if len(prices) >= 2 and prices[0] > 0
        else 0
    )
    return {"ticker": symbol, "prices": prices, "change_pct": change}


@router.get("/perf-vs-spy/{ticker}")
async def live_perf_vs_spy(
    ticker: str,
    request: Request,
    period: str = Query("1y", description="6mo/1y/2y/5y"),
):
    """Stock vs SPY normalized equity and period breakdowns."""
    symbol = validate_ticker(ticker)
    mds = request.app.state.market_data

    stock_hist = await mds.get_history(symbol, period=period, interval="1d")
    spy_hist = await mds.get_history("SPY", period=period, interval="1d")
    if stock_hist is None or stock_hist.empty or spy_hist is None or spy_hist.empty:
        return {"error": "Insufficient data"}

    s_col = "Close" if "Close" in stock_hist.columns else "close"
    b_col = "Close" if "Close" in spy_hist.columns else "close"
    stock_close = stock_hist[s_col].dropna()
    spy_close = spy_hist[b_col].dropna()
    common = stock_close.index.intersection(spy_close.index)
    if len(common) < 20:
        return {"error": "Insufficient overlapping data"}
    stock_close = stock_close.loc[common]
    spy_close = spy_close.loc[common]

    s_vals = stock_close.values.astype(float)
    b_vals = spy_close.values.astype(float)
    s_norm = s_vals / s_vals[0] * 100
    b_norm = b_vals / b_vals[0] * 100

    n = len(common)
    step = max(1, n // 200)
    equity_stock = []
    equity_spy = []
    for j in range(0, n, step):
        ts = int(common[j].timestamp()) if hasattr(common[j], "timestamp") else j
        equity_stock.append({"time": ts, "value": round(float(s_norm[j]), 2)})
        equity_spy.append({"time": ts, "value": round(float(b_norm[j]), 2)})
    ts_last = (
        int(common[-1].timestamp())
        if hasattr(common[-1], "timestamp")
        else n - 1
    )
    equity_stock.append({"time": ts_last, "value": round(float(s_norm[-1]), 2)})
    equity_spy.append({"time": ts_last, "value": round(float(b_norm[-1]), 2)})

    s_daily = np.diff(s_vals) / s_vals[:-1]
    b_daily = np.diff(b_vals) / b_vals[:-1]

    def _period_return(vals):
        return (
            round((vals[-1] / vals[0] - 1) * 100, 2)
            if len(vals) >= 2 and vals[0] > 0
            else 0.0
        )

    monthly = []
    stock_series = pd.Series(s_vals, index=common)
    spy_series = pd.Series(b_vals, index=common)
    stock_monthly = stock_series.resample("ME").last().dropna()
    spy_monthly = spy_series.resample("ME").last().dropna()
    s_mo_ret = stock_monthly.pct_change().dropna() * 100
    b_mo_ret = spy_monthly.pct_change().dropna() * 100
    for dt in s_mo_ret.index:
        if dt in b_mo_ret.index:
            sr = round(float(s_mo_ret[dt]), 2)
            br = round(float(b_mo_ret[dt]), 2)
            monthly.append(
                {
                    "period": dt.strftime("%Y-%m"),
                    "stock": sr,
                    "spy": br,
                    "alpha": round(sr - br, 2),
                }
            )

    quarterly = []
    stock_qtr = stock_series.resample("QE").last().dropna()
    spy_qtr = spy_series.resample("QE").last().dropna()
    s_q_ret = stock_qtr.pct_change().dropna() * 100
    b_q_ret = spy_qtr.pct_change().dropna() * 100
    for dt in s_q_ret.index:
        if dt in b_q_ret.index:
            sr = round(float(s_q_ret[dt]), 2)
            br = round(float(b_q_ret[dt]), 2)
            q_label = f"{dt.year} Q{(dt.month - 1) // 3 + 1}"
            quarterly.append(
                {
                    "period": q_label,
                    "stock": sr,
                    "spy": br,
                    "alpha": round(sr - br, 2),
                }
            )

    yearly = []
    stock_yr = stock_series.resample("YE").last().dropna()
    spy_yr = spy_series.resample("YE").last().dropna()
    s_y_ret = stock_yr.pct_change().dropna() * 100
    b_y_ret = spy_yr.pct_change().dropna() * 100
    for dt in s_y_ret.index:
        if dt in b_y_ret.index:
            sr = round(float(s_y_ret[dt]), 2)
            br = round(float(b_y_ret[dt]), 2)
            yearly.append(
                {
                    "period": str(dt.year),
                    "stock": sr,
                    "spy": br,
                    "alpha": round(sr - br, 2),
                }
            )

    total_stock = _period_return(s_vals)
    total_spy = _period_return(b_vals)
    n_years = len(s_daily) / 252.0 if len(s_daily) > 0 else 1.0
    ann_stock = (
        round(((s_vals[-1] / s_vals[0]) ** (1 / n_years) - 1) * 100, 2)
        if n_years > 0 and s_vals[0] > 0
        else 0.0
    )
    ann_spy = (
        round(((b_vals[-1] / b_vals[0]) ** (1 / n_years) - 1) * 100, 2)
        if n_years > 0 and b_vals[0] > 0
        else 0.0
    )
    s_vol = (
        round(float(np.std(s_daily) * np.sqrt(252) * 100), 2)
        if len(s_daily) > 10
        else 0.0
    )
    b_vol = (
        round(float(np.std(b_daily) * np.sqrt(252) * 100), 2)
        if len(b_daily) > 10
        else 0.0
    )
    s_sharpe = (
        round(float(np.mean(s_daily) / np.std(s_daily) * np.sqrt(252)), 2)
        if len(s_daily) > 10 and np.std(s_daily) > 0
        else 0.0
    )
    b_sharpe = (
        round(float(np.mean(b_daily) / np.std(b_daily) * np.sqrt(252)), 2)
        if len(b_daily) > 10 and np.std(b_daily) > 0
        else 0.0
    )

    def _max_dd(vals):
        peak = vals[0]
        mdd = 0.0
        for v in vals:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100 if peak > 0 else 0
            if dd < mdd:
                mdd = dd
        return round(mdd, 2)

    win_months = sum(1 for m in monthly if m["alpha"] > 0)
    total_months = len(monthly) if monthly else 1
    beta = 0.0
    correlation = 0.0
    if len(s_daily) > 20 and len(b_daily) > 20:
        min_len = min(len(s_daily), len(b_daily))
        cov = np.cov(s_daily[:min_len], b_daily[:min_len])
        if cov[1][1] > 0:
            beta = round(float(cov[0][1] / cov[1][1]), 2)
        corr = np.corrcoef(s_daily[:min_len], b_daily[:min_len])
        correlation = round(float(corr[0][1]), 2)

    return sanitize_for_json(
        {
            "ticker": symbol,
            "period": period,
            "equity_stock": equity_stock,
            "equity_spy": equity_spy,
            "summary": {
                "total_return": {
                    "stock": total_stock,
                    "spy": total_spy,
                    "alpha": round(total_stock - total_spy, 2),
                },
                "annualized": {
                    "stock": ann_stock,
                    "spy": ann_spy,
                    "alpha": round(ann_stock - ann_spy, 2),
                },
                "volatility": {"stock": s_vol, "spy": b_vol},
                "sharpe": {"stock": s_sharpe, "spy": b_sharpe},
                "max_drawdown": {
                    "stock": _max_dd(s_vals),
                    "spy": _max_dd(b_vals),
                },
                "beta": beta,
                "correlation": correlation,
                "win_months": win_months,
                "total_months": total_months,
                "win_rate_vs_spy": (
                    round(win_months / total_months * 100, 1)
                    if total_months > 0
                    else 0
                ),
            },
            "monthly": monthly[-24:],
            "quarterly": quarterly[-12:],
            "yearly": yearly,
            "days": len(common),
        }
    )


@router.get("/strategies")
async def live_strategies():
    """List available backtest strategies."""
    return {
        "strategies": [
            {
                "id": "swing",
                "name": "Swing Trading",
                "description": "2-10 day holds, RSI reversals + SMA crossovers",
                "best_regime": "NEUTRAL / LOW_VOL",
            },
            {
                "id": "breakout",
                "name": "Breakout / VCP",
                "description": "Volume-confirmed breakouts from consolidation",
                "best_regime": "RISK_ON / UPTREND",
            },
            {
                "id": "momentum",
                "name": "Momentum",
                "description": "Trend-following with 20/50 SMA alignment",
                "best_regime": "RISK_ON / UPTREND",
            },
            {
                "id": "mean_reversion",
                "name": "Mean Reversion",
                "description": "Buy oversold dips, sell overbought rallies",
                "best_regime": "NEUTRAL / SIDEWAYS",
            },
            {
                "id": "all",
                "name": "All Strategies",
                "description": "Run all 4 strategies and rank by Sharpe ratio",
                "best_regime": "Any",
            },
        ],
    }
