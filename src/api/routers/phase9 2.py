"""
Phase 9 API Router — New Engine Endpoints.

Exposes the new Phase 9 engines:
1. /api/v9/structure/{ticker} — Chart structure analysis
2. /api/v9/entry-quality/{ticker} — Entry quality filter
3. /api/v9/fundamentals/{ticker} — Real fundamental data
4. /api/v9/earnings/{ticker} — Earnings calendar
5. /api/v9/breakouts — Active breakout monitor
6. /api/v9/portfolio-gate — Portfolio gate check
7. /api/v9/journal — Decision journal
8. /api/v9/calibration — Calibration report
9. /api/v9/expert-records — Expert track records
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v9", tags=["phase-9"])


@router.get("/structure/{ticker}")
async def get_structure(ticker: str, request: Request):
    """Chart structure analysis: HH/HL, S/R, breakout quality."""
    from src.engines.structure_detector import StructureDetector

    ticker = ticker.upper().strip()
    mds = request.app.state.market_data
    try:
        hist = await mds.get_history(ticker, period="1y", interval="1d")
    except Exception as e:
        return {"error": f"Data fetch failed: {e}"}

    if hist is None or hist.empty or len(hist) < 30:
        return {"error": "Insufficient data"}

    c = hist["Close"].values.astype(float)
    h = hist["High"].values.astype(float)
    lo = hist["Low"].values.astype(float)
    v = hist["Volume"].values.astype(float)

    sd = StructureDetector()
    report = sd.analyze(c, h, lo, v)
    return {
        "ticker": ticker,
        **report.to_dict(),
    }


@router.get("/entry-quality/{ticker}")
async def get_entry_quality(
    request: Request,
    ticker: str = "",
    strategy: str = Query(
        "breakout",
        description="momentum/breakout/swing",
    ),
):
    """Entry quality assessment for a ticker."""
    from src.engines.entry_quality import EntryQualityEngine  # noqa: PLC0415
    from src.engines.structure_detector import StructureDetector  # noqa: PLC0415
    from src.services.indicators import compute_indicators  # noqa: PLC0415

    ticker = ticker.upper().strip()
    # Sector lookup: use app.state.scan_watchlist sector map if available
    ticker_sector_map: dict = getattr(request.app.state, "ticker_sector", {})
    mds = request.app.state.market_data
    try:
        hist = await mds.get_history(ticker, period="1y", interval="1d")
    except Exception as e:
        return {"error": f"Data fetch failed: {e}"}

    if hist is None or hist.empty or len(hist) < 60:
        return {"error": "Insufficient data"}

    c = hist["Close"].values.astype(float)
    h = hist["High"].values.astype(float)
    lo = hist["Low"].values.astype(float)
    v = hist["Volume"].values.astype(float)
    i = len(c) - 1

    _ind = compute_indicators(c, v)
    atr_pct = float(_ind["atr_pct"][i])
    entry = round(float(c[i]), 2)
    stop = round(entry * (1 - atr_pct * 2), 2)
    target = round(entry * (1 + atr_pct * 4), 2)

    # Get S/R
    sd = StructureDetector()
    sr = sd.analyze(c, h, lo, v)

    eq = EntryQualityEngine()
    report = eq.assess(
        c,
        h,
        lo,
        v,
        atr_pct,
        entry,
        stop,
        target,
        sr.nearest_resistance,
        sr.nearest_support,
        ticker_sector_map.get(ticker, "unknown"),
    )
    return {
        "ticker": ticker,
        "strategy": strategy,
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        **report.to_dict(),
        "structure": sr.to_dict(),
    }


@router.get("/fundamentals/{ticker}")
async def get_fund(ticker: str):
    """Real fundamental data from yfinance."""
    from src.engines.fundamental_data import get_fundamentals

    ticker = ticker.upper().strip()
    return get_fundamentals(ticker)


@router.get("/earnings/{ticker}")
async def get_earnings(ticker: str):
    """Earnings calendar and blackout check."""
    from src.engines.earnings_calendar import get_earnings_info

    ticker = ticker.upper().strip()
    return get_earnings_info(ticker)


@router.get("/breakouts")
async def get_breakouts():
    """Active breakout monitor status."""
    from src.engines.breakout_monitor import BreakoutMonitor

    monitor = BreakoutMonitor()
    monitor.load()
    return {
        "active": [r.to_dict() for r in monitor.get_active()],
        "recent_failures": [r.to_dict() for r in monitor.get_failures(10)],
        "stats": monitor.get_stats(),
    }


@router.get("/portfolio-gate")
async def portfolio_gate_check(
    ticker: str = Query(..., description="Ticker to check"),
    sector: str = Query("unknown", description="Sector"),
):
    """Check if portfolio gate allows new entry."""
    from src.engines.portfolio_gate import check_portfolio_gate

    ticker = ticker.upper().strip()
    return check_portfolio_gate(ticker, sector, atr_risk_pct=1.0)


@router.get("/journal")
async def get_journal(
    limit: int = Query(50, ge=1, le=200),
):
    """Recent decision journal entries."""
    from src.engines.decision_persistence import get_journal

    journal = get_journal()
    return {
        "entries": journal.get_recent(limit),
        "calibration": journal.get_calibration(),
    }


@router.get("/calibration")
async def get_calibration():
    """Brier score calibration report."""
    from src.engines.decision_persistence import get_journal

    return get_journal().get_calibration()


@router.get("/expert-records")
async def get_expert_records():
    """Expert track records with reliability weights."""
    from src.engines.decision_persistence import get_expert_store

    store = get_expert_store()
    return {
        "experts": store.get_all(),
        "note": ("Weights range 0.5-1.5. " "Equal weight (1.0) until 10+ predictions."),
    }
