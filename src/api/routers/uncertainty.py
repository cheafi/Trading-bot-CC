"""Conformal prediction uncertainty bands."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from src.engines.conformal_predictor import (
    ConformalPredictor,
    reliability_bucket,
    reliability_note,
)

router = APIRouter(prefix="/api/uncertainty", tags=["decision-layer"])
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,12}$")


@router.get("/{ticker}")
async def ticker_uncertainty(ticker: str, request: Request):
    """90% conformal prediction interval for a ticker."""
    symbol = ticker.upper().strip()
    if not _TICKER_RE.match(symbol):
        raise HTTPException(400, "Invalid ticker")

    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        raise HTTPException(503, "Market data unavailable")

    try:
        hist = await mds.get_history(symbol, period="1y", interval="1d")
        if hist is None or hist.empty or len(hist) < 60:
            raise HTTPException(404, f"Insufficient data for {symbol}")

        c_col = "Close" if "Close" in hist.columns else "close"
        close = hist[c_col].values.astype(float)

        cp = ConformalPredictor(confidence_level=0.90)
        cp.calibrate_from_returns(close, horizon_days=20)

        current = float(close[-1])
        target_5pct = round(current * 1.05, 2)
        interval = cp.predict(target_5pct)

        return {
            "ticker": symbol,
            "current_price": round(current, 2),
            "prediction_interval": interval.to_dict(),
            "calibration": cp.summary(),
            "reliability": reliability_bucket(cp.sample_size),
            "reliability_note": reliability_note(cp.sample_size),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Uncertainty error: {exc}") from exc
