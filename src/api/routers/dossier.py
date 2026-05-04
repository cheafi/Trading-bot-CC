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
    "NVDA": "SMH", "AMD": "SMH", "INTC": "SMH", "TSM": "SMH", "AVGO": "SMH",
    "AAPL": "XLK", "MSFT": "XLK", "GOOGL": "XLK", "META": "XLK", "CRM": "XLK",
    "AMZN": "XLY", "TSLA": "XLY",
    "JPM": "XLF", "BAC": "XLF", "GS": "XLF", "MS": "XLF",
    "JNJ": "XLV", "UNH": "XLV", "PFE": "XLV", "ABBV": "XLV",
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE",
    "LIN": "XLB", "APD": "XLB",
    "NEE": "XLU", "DUK": "XLU",
    "PLD": "XLRE", "AMT": "XLRE",
    "CAT": "XLI", "BA": "XLI", "GE": "XLI", "HON": "XLI",
    "PG": "XLP", "KO": "XLP", "PEP": "XLP", "WMT": "XLP",
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
        70 if (rsi and 45 <= rsi <= 70) else
        50 if (rsi and rsi < 45) else
        30 if (rsi and rsi > 75) else 50
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
            "overall": round((thesis_score + timing_score + execution_score + data_score) / 4),
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
