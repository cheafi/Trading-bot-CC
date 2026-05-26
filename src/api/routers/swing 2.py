"""
V6 Swing Analysis Router — Sprint 84
======================================
Extracted from main.py (was 6 inline @app.get/post routes, lines ~1210-1410).

Endpoints:
    GET  /api/v6/rs-strength/{ticker}
    GET  /api/v6/vcp-scan/{ticker}
    GET  /api/v6/swing-analysis/{ticker}
    POST /api/v6/swing-batch
    GET  /api/v6/distribution-days
    POST /api/v6/shadow-resolve
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Request

from src.services.swing_analysis import (
    compute_leadership_actionability,
    compute_rs_vs_spy,
    compute_volume_quality,
    detect_distribution_days,
    detect_pullback_entry,
    detect_vcp_pattern,
)

router = APIRouter(prefix="/api/v6", tags=["v6-swing"])


@router.get("/rs-strength/{ticker}")
async def api_rs_strength(ticker: str):
    """Relative Strength vs SPY for a single ticker."""
    ticker = ticker.upper()
    try:
        import yfinance as yf

        stock, spy = await asyncio.gather(
            asyncio.to_thread(
                yf.download, ticker, period="6mo", progress=False, auto_adjust=True
            ),
            asyncio.to_thread(
                yf.download, "SPY", period="6mo", progress=False, auto_adjust=True
            ),
        )
        if stock.empty or spy.empty:
            return {"ticker": ticker, "error": "no data"}

        stock_closes = stock["Close"].dropna().values.flatten().tolist()
        spy_closes = spy["Close"].dropna().values.flatten().tolist()

        rs = compute_rs_vs_spy(stock_closes, spy_closes)
        return {"ticker": ticker, **rs}
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


@router.get("/vcp-scan/{ticker}")
async def api_vcp_scan(ticker: str):
    """VCP (Volatility Contraction Pattern) scan for a ticker."""
    ticker = ticker.upper()
    try:
        import yfinance as yf

        df = await asyncio.to_thread(
            yf.download, ticker, period="1y", progress=False, auto_adjust=True
        )
        if df.empty:
            return {"ticker": ticker, "error": "no data"}

        highs = df["High"].dropna().values.flatten().tolist()
        lows = df["Low"].dropna().values.flatten().tolist()
        closes = df["Close"].dropna().values.flatten().tolist()
        volumes = df["Volume"].dropna().values.flatten().tolist()

        vcp = detect_vcp_pattern(highs, lows, closes, volumes)
        vol_quality = compute_volume_quality(volumes, closes)
        return {"ticker": ticker, **vcp, **vol_quality}
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


@router.get("/swing-analysis/{ticker}")
async def api_swing_analysis(ticker: str):
    """Full swing analysis: RS, VCP, volume quality, pullback detection,
    and dual-axis Leadership/Actionability scoring (Swing_Project methodology).
    """
    ticker = ticker.upper()
    try:
        import yfinance as yf

        df, spy_df = await asyncio.gather(
            asyncio.to_thread(
                yf.download, ticker, period="1y", progress=False, auto_adjust=True
            ),
            asyncio.to_thread(
                yf.download, "SPY", period="1y", progress=False, auto_adjust=True
            ),
        )
        if df.empty:
            return {"ticker": ticker, "error": "no data"}

        closes = df["Close"].dropna().values.flatten().tolist()
        highs = df["High"].dropna().values.flatten().tolist()
        lows = df["Low"].dropna().values.flatten().tolist()
        volumes = df["Volume"].dropna().values.flatten().tolist()
        spy_closes = (
            spy_df["Close"].dropna().values.flatten().tolist()
            if not spy_df.empty
            else closes
        )

        rs = compute_rs_vs_spy(closes, spy_closes)
        vcp = detect_vcp_pattern(highs, lows, closes, volumes)
        vol_q = compute_volume_quality(volumes, closes)

        sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        sma200 = (
            sum(closes[-200:]) / 200
            if len(closes) >= 200
            else sum(closes) / len(closes)
        )

        pullback = detect_pullback_entry(closes, highs, lows, volumes, sma20)

        # Simplified RSI (14-period)
        rsi = 50.0
        if len(closes) >= 15:
            gains, losses = [], []
            for i in range(1, min(15, len(closes))):
                delta = closes[-i] - closes[-i - 1]
                (gains if delta > 0 else losses).append(abs(delta))
            avg_gain = sum(gains) / 14 if gains else 0.001
            avg_loss = sum(losses) / 14 if losses else 0.001
            rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        atr_pct = 0.0
        if len(closes) >= 2 and closes[-1] > 0:
            trs = []
            for i in range(-14, 0):
                if i - 1 >= -len(closes):
                    tr = max(
                        highs[i] - lows[i],
                        abs(highs[i] - closes[i - 1]),
                        abs(lows[i] - closes[i - 1]),
                    )
                    trs.append(tr)
            atr_pct = (sum(trs) / len(trs) / closes[-1] * 100) if trs else 0

        la = compute_leadership_actionability(
            rs, vcp, vol_q, pullback, rsi, atr_pct, closes[-1], sma200
        )

        return {
            "ticker": ticker,
            "close": round(closes[-1], 2),
            "sma20": round(sma20, 2),
            "sma200": round(sma200, 2),
            "rsi": round(rsi, 1),
            "atr_pct": round(atr_pct, 2),
            "relative_strength": rs,
            "vcp_pattern": vcp,
            "volume_quality": vol_q,
            "pullback_entry": pullback,
            "scoring": la,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


@router.post("/swing-batch")
async def api_swing_batch(request: Request):
    """Batch swing analysis for multiple tickers. Returns ranked by final_score."""
    try:
        body = await request.json()
        tickers = body.get("tickers", [])
        if not tickers:
            return {"error": "provide tickers list"}
        results = []
        for t in tickers[:20]:
            r = await api_swing_analysis(t)
            if "error" not in r:
                results.append(r)
        results.sort(
            key=lambda x: x.get("scoring", {}).get("final_score", 0), reverse=True
        )
        return {"count": len(results), "candidates": results}
    except Exception as e:
        return {"error": str(e)}


@router.get("/distribution-days")
async def api_distribution_days():
    """IBD-style distribution day count for SPY (last 25 trading days)."""
    try:
        import yfinance as yf

        spy = await asyncio.to_thread(
            yf.download, "SPY", period="3mo", progress=False, auto_adjust=True
        )
        if spy.empty:
            return {"error": "no SPY data"}

        spy_data = []
        for _, row in spy.iterrows():
            spy_data.append(
                {
                    "close": float(
                        row["Close"].item()
                        if hasattr(row["Close"], "item")
                        else row["Close"]
                    ),
                    "volume": float(
                        row["Volume"].item()
                        if hasattr(row["Volume"], "item")
                        else row["Volume"]
                    ),
                }
            )
        dd = detect_distribution_days(spy_data)
        return {"benchmark": "SPY", **dd}
    except Exception as e:
        return {"error": str(e)}


@router.post("/shadow-resolve", summary="Auto-resolve expired shadow predictions")
async def shadow_resolve(request: Request):
    """Check actual prices for all expired predictions and mark results."""
    from src.engines.shadow_tracker import shadow_tracker

    mds = request.app.state.market_data
    result = await shadow_tracker.auto_resolve(mds)
    return result
