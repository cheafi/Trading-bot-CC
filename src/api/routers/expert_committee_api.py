"""Expert committee multi-agent verdict."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from src.api.technical_indicators import compute_indicators
from src.engines.expert_committee import ExpertCommittee

router = APIRouter(prefix="/api/expert-committee", tags=["decision-layer"])
_expert_committee = ExpertCommittee()
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,12}$")


@router.get("/{ticker}")
async def expert_committee_verdict(ticker: str, request: Request):
    """Reliability-weighted consensus from domain experts."""
    symbol = ticker.upper().strip()
    if not _TICKER_RE.match(symbol):
        raise HTTPException(400, "Invalid ticker")

    mds = getattr(request.app.state, "market_data", None)
    if mds is None:
        raise HTTPException(503, "Market data unavailable")

    try:
        hist = await mds.get_history(symbol, period="6mo", interval="1d")
        if hist is None or hist.empty or len(hist) < 60:
            raise HTTPException(404, f"Insufficient data for {symbol}")

        c_col = "Close" if "Close" in hist.columns else "close"
        v_col = "Volume" if "Volume" in hist.columns else "volume"
        close = hist[c_col].values.astype(float)
        volume = hist[v_col].values.astype(float)

        indicators = compute_indicators(close, volume)
        i = len(close) - 1
        trending = bool(
            close[i] > indicators["sma50"][i]
            and indicators["sma50"][i] > indicators["sma200"][i]
        )

        votes = _expert_committee.collect_votes(
            regime="UPTREND" if trending else "SIDEWAYS",
            rsi=float(indicators["rsi"][i]),
            vol_ratio=float(indicators["vol_ratio"][i]),
            trending=trending,
            rr_ratio=2.0,
            atr_pct=float(indicators["atr_pct"][i]),
        )
        verdict = _expert_committee.deliberate(
            votes, regime="UPTREND" if trending else "SIDEWAYS"
        )
        return {
            "ticker": symbol,
            "verdict": verdict.to_dict(),
            "experts": [e.to_dict() for e in _expert_committee.experts],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Expert committee error: {exc}") from exc
