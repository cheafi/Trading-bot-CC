"""
Institutional Router — Benchmark, Relative Value, Data Quality,
Actionable Scanners, Rejection Surface (Sprint 71)
==============================================================

Unified API surface for the 5 institutional-grade features.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request models ──────────────────────────────────────────────────

class RelativeValueRequest(BaseModel):
    ticker: str
    peers: Optional[List[str]] = None
    benchmark: str = "SPY"


class ActionableScanRequest(BaseModel):
    scanner: str = "momentum"
    limit: int = 20


# ── Feature 1: Benchmark-Aware Portfolio ────────────────────────────

@router.get("/api/portfolio/benchmark", tags=["institutional"])
async def portfolio_benchmark(
    request: Request,
    benchmark: str = Query("SPY", description="Benchmark ticker"),
):
    """Benchmark-aware portfolio analysis with attribution."""
    try:
        from src.engines.benchmark_engine import BenchmarkEngine
    except ImportError:
        raise HTTPException(503, "Benchmark engine not available")

    engine = BenchmarkEngine()
    portfolio = getattr(request.app.state, "portfolio", {})
    holdings = portfolio.get("holdings", [])

    if not holdings:
        return {
            "benchmark_ticker": benchmark,
            "portfolio": {},
            "benchmark": {},
            "alpha": 0,
            "holdings": [],
            "contributions": [],
            "rolling_returns": {},
            "message": "No holdings — import a portfolio first",
        }

    result = engine.compute_portfolio_benchmark(
        holdings=holdings,
        benchmark=benchmark,
    )
    return result.to_dict()


@router.get("/api/portfolio/benchmark/{ticker}", tags=["institutional"])
async def holding_benchmark(
    ticker: str,
    request: Request,
    benchmark: str = Query("SPY"),
):
    """Benchmark comparison for a single holding."""
    try:
        from src.engines.benchmark_engine import BenchmarkEngine, SECTOR_BENCHMARKS
    except ImportError:
        raise HTTPException(503, "Benchmark engine not available")

    portfolio = getattr(request.app.state, "portfolio", {})
    holdings = portfolio.get("holdings", [])
    holding = next((h for h in holdings if h.get("ticker") == ticker), None)

    if not holding:
        raise HTTPException(404, f"Holding {ticker} not found in portfolio")

    engine = BenchmarkEngine()
    sector = holding.get("sector", "Unknown")
    bm = SECTOR_BENCHMARKS.get(sector, benchmark)

    result = engine.compute_portfolio_benchmark(
        holdings=[holding],
        benchmark=bm,
    )
    if result.holdings:
        return result.holdings[0].to_dict()
    return {"ticker": ticker, "message": "Insufficient data for benchmark"}


# ── Feature 2: Relative Value Comparison ────────────────────────────

@router.post("/api/relative-value", tags=["institutional"])
async def relative_value(req: RelativeValueRequest, request: Request):
    """Why this stock vs peers / sector / index comparison block."""
    try:
        from src.engines.relative_value_engine import RelativeValueEngine
    except ImportError:
        raise HTTPException(503, "Relative value engine not available")

    mds = getattr(request.app.state, "market_data", None)

    # Gather stock data
    stock_data: Dict[str, Any] = {"ticker": req.ticker}
    peer_data: List[Dict[str, Any]] = []
    sector_data: Dict[str, Any] = {}
    index_data: Dict[str, Any] = {}

    # Try to get fundamentals
    try:
        from src.engines.fundamental_data import get_fundamentals
        fund = await get_fundamentals(req.ticker)
        if fund:
            stock_data["fundamentals"] = fund
    except Exception:
        pass

    # Try to get peer data
    if req.peers:
        for peer_ticker in req.peers[:8]:
            try:
                from src.engines.fundamental_data import get_fundamentals
                peer_fund = await get_fundamentals(peer_ticker)
                if peer_fund:
                    peer_data.append({"ticker": peer_ticker, **peer_fund})
            except Exception:
                pass

    engine = RelativeValueEngine()
    report = engine.compare(
        ticker=req.ticker,
        stock_data=stock_data,
        peer_data=peer_data,
        sector_data=sector_data,
        index_data=index_data,
    )
    return report.to_dict()


# ── Feature 3: Data Quality Transparency ────────────────────────────

@router.get("/api/data-quality/signal/{ticker}", tags=["institutional"])
async def signal_data_quality(ticker: str, request: Request):
    """Data quality report for a specific signal."""
    try:
        from src.engines.data_quality_engine import DataQualityEngine
    except ImportError:
        raise HTTPException(503, "Data quality engine not available")

    # Find signal in app state
    signals = getattr(request.app.state, "signals", [])
    signal = next(
        (s for s in signals if s.get("ticker") == ticker), None
    )
    if not signal:
        raise HTTPException(404, f"No signal found for {ticker}")

    engine = DataQualityEngine()
    report = engine.evaluate_signal_quality(signal)
    return report.to_dict()


@router.get("/api/data-quality/portfolio", tags=["institutional"])
async def portfolio_data_quality(request: Request):
    """Aggregate data quality across all holdings."""
    try:
        from src.engines.data_quality_engine import DataQualityEngine
    except ImportError:
        raise HTTPException(503, "Data quality engine not available")

    engine = DataQualityEngine()
    portfolio = getattr(request.app.state, "portfolio", {})
    holdings = portfolio.get("holdings", [])

    holding_reports = {}
    for h in holdings:
        ticker = h.get("ticker", "")
        if ticker:
            holding_reports[ticker] = engine.evaluate_holding_quality(
                ticker, h
            )

    summary = engine.summarize_portfolio(holding_reports)
    return summary.to_dict()


@router.get("/api/data-quality/escalations", tags=["institutional"])
async def data_quality_escalations(request: Request):
    """List all data quality escalations requiring attention."""
    try:
        from src.engines.data_quality_engine import DataQualityEngine
    except ImportError:
        raise HTTPException(503, "Data quality engine not available")

    engine = DataQualityEngine()
    portfolio = getattr(request.app.state, "portfolio", {})
    holdings = portfolio.get("holdings", [])

    escalations = []
    for h in holdings:
        ticker = h.get("ticker", "")
        if ticker:
            report = engine.evaluate_holding_quality(ticker, h)
            if report.escalation_triggered:
                escalations.append({
                    "ticker": ticker,
                    "state": report.overall_state.value,
                    "severity": report.overall_severity.value,
                    "reasons": report.escalation_reasons,
                })

    return {
        "escalation_count": len(escalations),
        "escalations": escalations,
    }


# ── Feature 4: Actionable Scanner Results ───────────────────────────

@router.post("/api/scanner/actionable", tags=["institutional"])
async def actionable_scanner(req: ActionableScanRequest, request: Request):
    """Run scanner and return only actionable results with evidence."""
    try:
        from src.engines.actionable_scanner import ActionableScannerEngine
    except ImportError:
        raise HTTPException(503, "Actionable scanner engine not available")

    # Get raw scanner results
    raw_results = []
    try:
        if req.scanner == "momentum":
            from src.scanners.momentum_scanner import MomentumScanner
            scanner = MomentumScanner()
            raw = scanner.scan() if hasattr(scanner, "scan") else []
            if isinstance(raw, list):
                raw_results = [
                    r.to_dict() if hasattr(r, "to_dict") else r
                    for r in raw
                ]
        elif req.scanner == "pattern":
            from src.scanners.pattern_scanner import PatternScanner
            scanner = PatternScanner()
            raw = scanner.scan() if hasattr(scanner, "scan") else []
            if isinstance(raw, list):
                raw_results = [
                    r.to_dict() if hasattr(r, "to_dict") else r
                    for r in raw
                ]
    except Exception as e:
        logger.warning("Scanner %s failed: %s", req.scanner, e)

    engine = ActionableScannerEngine()
    output = engine.process_raw_results(
        scanner_name=req.scanner,
        raw_results=raw_results[:req.limit],
    )
    return output.to_dict()


# ── Feature 5: Rejection & Non-Action Surface ───────────────────────

@router.get("/api/rejections", tags=["institutional"])
async def get_rejections(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
):
    """Get rejected ideas with reasoning and counterfactuals."""
    tracker = getattr(request.app.state, "rejection_tracker", None)
    if tracker is None:
        # Return empty state
        return {
            "total_evaluated": 0,
            "total_rejected": 0,
            "rejection_rate": 0,
            "top_rejection_reasons": [],
            "near_misses": [],
            "rejections": [],
            "message": "Rejection tracker not initialized — "
                       "rejections will appear as signals are evaluated",
        }

    summary = tracker.get_summary()
    data = summary.to_dict()
    data["rejections"] = data["rejections"][:limit]
    return data


@router.get("/api/rejections/ticker/{ticker}", tags=["institutional"])
async def get_rejections_for_ticker(ticker: str, request: Request):
    """Get rejection history for a specific ticker."""
    tracker = getattr(request.app.state, "rejection_tracker", None)
    if tracker is None:
        return {"ticker": ticker, "rejections": [], "count": 0}

    records = tracker.get_rejections_for_ticker(ticker)
    return {
        "ticker": ticker,
        "count": len(records),
        "rejections": [r.to_dict() for r in records],
    }


@router.get("/api/rejections/near-misses", tags=["institutional"])
async def get_near_misses(
    request: Request,
    min_score: float = Query(50.0, ge=0, le=100),
):
    """Get near-miss rejections that could become actionable."""
    tracker = getattr(request.app.state, "rejection_tracker", None)
    if tracker is None:
        return {"near_misses": [], "count": 0}

    summary = tracker.get_summary()
    near_misses = [
        r.to_dict() for r in summary.near_misses
        if r.near_miss_score >= min_score
    ]
    return {
        "near_misses": near_misses,
        "count": len(near_misses),
    }


# ── Page routes ─────────────────────────────────────────────────────

@router.get("/institutional", tags=["pages"])
async def institutional_page(request: Request):
    """Render the institutional dashboard page."""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path

    templates = Jinja2Templates(
        directory=Path(__file__).parent.parent / "templates"
    )
    return templates.TemplateResponse(
        "institutional.html", {"request": request}
    )
