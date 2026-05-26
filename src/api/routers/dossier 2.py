"""
Symbol Dossier Router — Sprint 72
===================================
/api/dossier/{ticker} — Full trader decision card:
  - quick decision (action, conviction, setup)
  - confidence breakdown (thesis / timing / execution / data)
  - benchmark delta (vs SPY, sector ETF)
  - regime context
  - invalidation level + targets
  - similar historical cases
  - entry / stop / R:R
  - data quality flag (real vs synthetic)

No live market calls here — pulls from cached regime + brief data.
Heavy data (benchmark delta) is computed on demand and cached 5 min.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dossier", tags=["dossier"])

_DOSSIER_CACHE: Dict[str, tuple[float, Dict]] = {}
_CACHE_TTL = 300  # 5 minutes

# Sector ETF map
_SECTOR_ETF: Dict[str, str] = {
    "NVDA": "SMH",
    "AMD": "SMH",
    "INTC": "SMH",
    "TSM": "SMH",
    "AVGO": "SMH",
    "AAPL": "XLK",
    "MSFT": "XLK",
    "GOOGL": "XLK",
    "META": "XLK",
    "CRM": "XLK",
    "AMZN": "XLY",
    "TSLA": "XLY",
    "JPM": "XLF",
    "BAC": "XLF",
    "GS": "XLF",
    "MS": "XLF",
    "JNJ": "XLV",
    "UNH": "XLV",
    "PFE": "XLV",
    "ABBV": "XLV",
    "XOM": "XLE",
    "CVX": "XLE",
    "COP": "XLE",
    "LIN": "XLB",
    "APD": "XLB",
    "NEE": "XLU",
    "DUK": "XLU",
    "PLD": "XLRE",
    "AMT": "XLRE",
    "CAT": "XLI",
    "BA": "XLI",
    "GE": "XLI",
    "HON": "XLI",
    "PG": "XLP",
    "KO": "XLP",
    "PEP": "XLP",
    "WMT": "XLP",
}


def _load_brief_data() -> Dict:
    from src.services.brief_data_service import load_brief

    return load_brief()


def _find_signal_in_brief(ticker: str, brief_data: Dict) -> tuple[Dict, str]:
    """Return (signal_item, section_name) from brief data."""
    for section in ("actionable", "watch", "review"):
        for item in brief_data.get(section, []):
            if item.get("ticker", "").upper() == ticker:
                return item, section
    return {}, "unknown"


def _conviction_tier(score: float) -> str:
    """Map brief score (0-10) to conviction tier."""
    if score >= 8:
        return "TRADE"
    elif score >= 7:
        return "TRADE_CANDIDATE"
    elif score >= 6:
        return "LEADER"
    elif score >= 3:
        return "WATCH"
    return "WAIT"


def _build_dossier(ticker: str) -> Dict[str, Any]:
    from src.services.regime_service import RegimeService

    ticker = ticker.upper()
    regime = RegimeService.get()
    brief_data = _load_brief_data()
    signal, section = _find_signal_in_brief(ticker, brief_data)

    indicators = signal.get("indicators") or {}
    score = signal.get("score", signal.get("conviction", 0))

    # ── Quick Decision Card ──
    action = _conviction_tier(score)
    if not regime.get("should_trade", True):
        action = "NO_TRADE" if action == "TRADE" else action
        gate = "BLOCKED"
    else:
        gate = "ALLOWED"

    # ── Confidence Breakdown ──
    rsi = indicators.get("rsi")
    rs = indicators.get("rs")
    volume_ok = indicators.get("volume_ratio", 1.0) >= 1.2
    above_ma = indicators.get("above_ma50", True)

    thesis_score = min(score * 5, 100) if score else 0
    timing_score = (
        70
        if (rsi and 45 <= rsi <= 70)
        else 50 if (rsi and rsi < 45) else 30 if (rsi and rsi > 75) else 50
    )
    execution_score = 80 if (volume_ok and above_ma) else 50 if above_ma else 30
    data_score = 40 if regime.get("synthetic") else 85

    # ── Benchmark Context ──
    sector_etf = _SECTOR_ETF.get(ticker, "SPY")

    # ── Setup Info ──
    setup = signal.get("setup", signal.get("strategy", "—"))
    note = signal.get("note", signal.get("thesis", "—"))
    catalyst = signal.get("due_date") or signal.get("catalyst_date")

    # ── Risk Levels (from signal if available) ──
    entry = signal.get("entry")
    stop = signal.get("stop")
    target = signal.get("target")

    rr = None
    if entry and stop and target:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = round(reward / risk, 2) if risk > 0 else None

    # ── Historical Similar Cases ──
    similar_cases: List[Dict] = signal.get("similar_cases", [])

    return {
        "ticker": ticker,
        "date": brief_data.get("date"),
        # Quick decision
        "decision": {
            "action": action,
            "conviction_score": score,
            "conviction_tier": _conviction_tier(score),
            "setup": setup,
            "note": note,
            "catalyst": catalyst,
            "regime_gate": gate,
        },
        # Confidence breakdown
        "confidence": {
            "thesis": round(thesis_score),
            "timing": timing_score,
            "execution": execution_score,
            "data": data_score,
            "overall": round(
                (thesis_score + timing_score + execution_score + data_score) / 4
            ),
        },
        # Indicators
        "indicators": {
            "rsi": rsi,
            "rs_vs_spy": rs,
            "volume_ratio": indicators.get("volume_ratio"),
            "above_ma50": above_ma,
        },
        # Benchmark
        "benchmark": {
            "sector_etf": sector_etf,
            "note": f"Compare {ticker} vs SPY and {sector_etf} for relative strength context.",
        },
        # Regime context
        "regime": {
            "trend": regime.get("trend", "UNKNOWN"),
            "vix": regime.get("vix", regime.get("vix_level", 18.0)),
            "vix_regime": regime.get("vix_regime", "NORMAL"),
            "risk_score": regime.get("risk_score", 50),
            "should_trade": regime.get("should_trade", True),
        },
        # Risk levels
        "risk": {
            "entry": entry,
            "stop": stop,
            "target": target,
            "rr_ratio": rr,
            "rr_min_required": "2:1 for WATCH, 3:1 for TRADE",
            "stop_rule": "Hard stop at 1R; trail only after +1R profit",
        },
        # Historical analogs
        "similar_cases": similar_cases[:5],
        # Source section in brief
        "source_section": section,
        "synthetic": regime.get("synthetic", False),
        "disclaimer": "Not financial advice. Paper/simulation only unless stated otherwise.",
    }


@router.get("/{ticker}")
async def symbol_dossier(ticker: str):
    """
    Full trader symbol dossier — decision card, confidence breakdown,
    benchmark context, regime gate, R:R, similar historical cases.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker required")

    # Check cache
    cached = _DOSSIER_CACHE.get(ticker)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]

    dossier = _build_dossier(ticker)
    _DOSSIER_CACHE[ticker] = (time.time(), dossier)
    return dossier


# ── Trade Advice Engine (Sprint 115) ──────────────────────────────────────


def _compute_trade_advice(
    ticker: str,
    buy_price: float,
    current_price: float,
    dossier: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Given a user's buy price, the current price, and the full dossier context,
    produce a concrete trade suggestion: BUY MORE / HOLD / TRIM / SELL / EXIT.
    """
    pnl_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
    pnl_dollar = current_price - buy_price

    # Extract context
    regime = dossier.get("regime", {})
    decision = dossier.get("decision", {})
    confidence = dossier.get("confidence", {})
    risk = dossier.get("risk", {})
    indicators = dossier.get("indicators", {})

    conviction = decision.get("conviction_tier", "WAIT")
    gate = decision.get("regime_gate", "ALLOWED")
    rsi = indicators.get("rsi")
    rs_spy = indicators.get("rs_vs_spy")
    overall_conf = confidence.get("overall", 50)

    stop = risk.get("stop")
    target = risk.get("target")
    entry = risk.get("entry")

    # ── Compute R-multiple if stop is known ──
    risk_per_share = abs(buy_price - stop) if stop and stop < buy_price else None
    r_multiple = (
        (pnl_dollar / risk_per_share) if risk_per_share and risk_per_share > 0 else None
    )

    # ── Decision logic ──
    action = "HOLD"
    reasons = []
    warnings = []

    # EXIT conditions (highest priority)
    if gate == "BLOCKED":
        action = "EXIT"
        reasons.append("Regime gate BLOCKED — no new longs, consider exiting")
    elif stop and current_price <= stop:
        action = "EXIT"
        reasons.append(f"Price ${current_price:.2f} hit stop ${stop:.2f} — hard exit")
    elif pnl_pct <= -8:
        action = "EXIT"
        reasons.append(f"Loss of {pnl_pct:.1f}% exceeds max tolerance — cut loss")
    elif rsi and rsi > 80 and pnl_pct > 15:
        action = "SELL"
        reasons.append(f"RSI {rsi:.0f} overbought + {pnl_pct:.1f}% gain — take profit")

    # TRIM conditions
    elif r_multiple and r_multiple >= 3:
        action = "TRIM"
        reasons.append(f"At {r_multiple:.1f}R — lock partial profit (sell 1/3)")
    elif pnl_pct > 20 and rsi and rsi > 70:
        action = "TRIM"
        reasons.append(f"+{pnl_pct:.1f}% with RSI {rsi:.0f} — trim 25-50%")

    # BUY MORE conditions
    elif conviction in ("TRADE", "TRADE_CANDIDATE", "LEADER") and gate == "ALLOWED":
        if pnl_pct > 0 and pnl_pct < 5 and overall_conf >= 65:
            action = "BUY MORE"
            reasons.append(
                f"Conviction {conviction}, early profit, confidence {overall_conf}% — add to winner"
            )
        elif pnl_pct < 0 and pnl_pct > -3 and overall_conf >= 70 and (rsi and rsi < 40):
            action = "BUY MORE"
            reasons.append(
                f"Pullback {pnl_pct:.1f}% into support, RSI {rsi:.0f} oversold — scale in"
            )
        else:
            action = "HOLD"
            reasons.append(f"Conviction {conviction}, gate clear — maintain position")
    else:
        action = "HOLD"
        reasons.append(f"Conviction {conviction} — no immediate action needed")

    # ── Warnings ──
    if regime.get("synthetic"):
        warnings.append("⚠ SYNTHETIC regime data — lower confidence")
    if overall_conf < 50:
        warnings.append(
            f"Low overall confidence ({overall_conf}%) — size conservatively"
        )
    if rs_spy and rs_spy < 0:
        warnings.append(f"Underperforming SPY (RS {rs_spy:.1f}) — watch closely")

    # ── Target prices ──
    sell_target = (
        target
        if target
        else (buy_price * 1.15 if pnl_pct < 15 else current_price * 1.05)
    )
    stop_price = stop if stop else buy_price * 0.93

    return {
        "ticker": ticker,
        "buy_price": round(buy_price, 2),
        "current_price": round(current_price, 2),
        "pnl_pct": round(pnl_pct, 2),
        "pnl_dollar": round(pnl_dollar, 2),
        "r_multiple": round(r_multiple, 2) if r_multiple else None,
        "action": action,
        "reasons": reasons,
        "warnings": warnings,
        "suggestion": {
            "target_price": round(sell_target, 2) if sell_target else None,
            "stop_price": round(stop_price, 2) if stop_price else None,
            "conviction": conviction,
            "regime_gate": gate,
            "confidence": overall_conf,
        },
        "comment": " | ".join(reasons + warnings) if warnings else " | ".join(reasons),
    }


@router.get("/{ticker}/trade-advice")
async def trade_advice(ticker: str, buy_price: float):
    """
    Given a user's buy price, return trade suggestion for the position.
    Uses current market price from yfinance and dossier context.
    """
    import asyncio
    import yfinance as yf

    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker required")
    if buy_price <= 0:
        raise HTTPException(status_code=400, detail="buy_price must be positive")

    # Get current price
    def _get_price():
        t = yf.Ticker(ticker)
        info = t.fast_info
        return getattr(info, "last_price", None) or getattr(
            info, "previous_close", None
        )

    current_price = await asyncio.to_thread(_get_price)
    if not current_price:
        raise HTTPException(status_code=404, detail=f"Cannot fetch price for {ticker}")

    # Get dossier context
    cached = _DOSSIER_CACHE.get(ticker)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        dossier = cached[1]
    else:
        dossier = _build_dossier(ticker)
        _DOSSIER_CACHE[ticker] = (time.time(), dossier)

    advice = _compute_trade_advice(ticker, buy_price, current_price, dossier)
    return advice
