"""
RS Hub Router — Sprint 72 / 73 (refactored)
=============================================
/api/rs                — RS leaderboard (full ranking)
/api/rs/leaders        — Top leaders only
/api/rs/transitions    — Emerging + fading tickers
/api/rs/sectors        — RS aggregated by sector
/api/rs/{ticker}       — Individual RS profile
/api/rs/matrix         — RS × Setup quality matrix

Uses RSDataService for market data (batch yfinance, date-aligned).
Uses BriefDataService for signal context (single source of truth).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rs", tags=["rs-hub"])

# Cache for the full leaderboard
_RS_CACHE: Dict[str, Any] = {}
_RS_CACHE_TS: float = 0
_RS_CACHE_TTL = 300  # 5 min


def _get_scan_tickers() -> List[str]:
    """Get tickers from the scanner watchlist."""
    try:
        from src.services.scanner import SCAN_WATCHLIST
        return SCAN_WATCHLIST
    except ImportError:
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
            "AMD", "AVGO", "CRM", "NFLX", "JPM", "V", "UNH",
        ]


def _compute_leaderboard() -> List[Dict]:
    """Compute RS profiles for all scan tickers."""
    from src.engines.rs_hub import (
        RSProfile,
        classify_leadership,
        classify_rs_state,
        compute_final_rank_score,
        compute_rs_quality,
        compute_rs_sustainability,
        compute_rs_tradeability,
        rs_setup_matrix,
        _get_mcap,
        _get_sector,
        _get_sector_etf,
    )
    from src.services.brief_data_service import build_brief_lookup, load_brief
    from src.services.rs_data_service import compute_rs_date_aligned, fetch_closes_batch

    brief_data = load_brief()
    brief_lookup = build_brief_lookup(brief_data)

    tickers = _get_scan_tickers()

    # Batch fetch: all tickers + SPY in one call
    all_tickers = list(set(["SPY"] + tickers))
    closes_map = fetch_closes_batch(all_tickers)

    spy_closes = closes_map.get("SPY")
    if spy_closes is None or len(spy_closes) < 22:
        logger.warning("[RS Hub] No SPY data — returning empty leaderboard")
        return []

    # First pass: compute RS profiles
    sector_rs: Dict[str, List[float]] = {}
    profiles: List[RSProfile] = []

    for ticker in tickers:
        ticker_closes = closes_map.get(ticker)
        if ticker_closes is None or len(ticker_closes) < 22:
            continue

        # Date-aligned RS computation
        rs_data = compute_rs_date_aligned(ticker_closes, spy_closes)

        sector = _get_sector(ticker)
        sector_rs.setdefault(sector, []).append(rs_data["rs_composite"])

        # Signal context from brief
        sig = brief_lookup.get(ticker, {})
        indicators = sig.get("indicators") or {}
        rsi = indicators.get("rsi")
        volume_ok = (indicators.get("volume_ratio", 1.0) or 1.0) >= 1.2
        above_ma = indicators.get("above_ma50", True)

        p = RSProfile(
            ticker=ticker,
            rs_composite=rs_data["rs_composite"],
            rs_1m=rs_data["rs_1m"],
            rs_3m=rs_data["rs_3m"],
            rs_6m=rs_data["rs_6m"],
            rs_slope=rs_data["rs_slope"],
            rs_status=str(rs_data["rs_status"]),
            sector=sector,
            sector_etf=_get_sector_etf(ticker),
            mcap_bucket=_get_mcap(ticker),
            setup_type=sig.get("setup", sig.get("strategy", "—")),
        )

        # Lifecycle state
        p.rs_state = classify_rs_state(
            p.rs_composite, p.rs_slope, p.rs_1m, p.rs_3m
        )

        # Quality layers
        p.rs_quality = compute_rs_quality(p.rs_composite, p.rs_slope)
        p.rs_tradeability = compute_rs_tradeability(
            p.rs_composite, p.rs_slope, rsi, volume_ok, above_ma
        )
        p.rs_sustainability = compute_rs_sustainability(
            p.rs_composite, p.rs_1m, p.rs_3m, p.rs_6m, p.rs_slope
        )

        # RS velocity & acceleration
        p.rs_velocity = abs(p.rs_slope)
        p.rs_acceleration = p.rs_slope

        # Deltas
        p.rs_delta_20d = p.rs_1m - 100
        p.rs_delta_60d = p.rs_3m - 100

        # Action from brief
        for section, tier in [("actionable", "TRADE"), ("watch", "WATCH"), ("review", "LEADER")]:
            if any(item.get("ticker", "").upper() == ticker for item in brief_data.get(section, [])):
                p.action = tier
                break

        # RS × Setup matrix
        setup_quality = sig.get("score", 5) * 10 if sig else 50
        matrix_verdict = rs_setup_matrix(p.rs_quality, setup_quality)
        if p.action == "WAIT":
            p.action = matrix_verdict

        profiles.append(p)

    # Second pass: leadership classification using sector averages
    sector_avgs = {s: sum(v) / len(v) for s, v in sector_rs.items() if v}
    for p in profiles:
        avg = sector_avgs.get(p.sector, 100)
        p.leadership = classify_leadership(p.rs_composite, avg)

    # Sort by rank score
    profiles.sort(key=lambda pr: compute_final_rank_score(pr), reverse=True)
    for i, p in enumerate(profiles, 1):
        p.rank = i

    return [p.to_dict() for p in profiles]


def _get_cached_leaderboard() -> List[Dict]:
    global _RS_CACHE, _RS_CACHE_TS
    now = time.time()
    if _RS_CACHE.get("board") and (now - _RS_CACHE_TS) < _RS_CACHE_TTL:
        return _RS_CACHE["board"]
    board = _compute_leaderboard()
    _RS_CACHE = {"board": board}
    _RS_CACHE_TS = now
    return board


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def rs_leaderboard(
    limit: int = Query(default=50, ge=1, le=200),
    sector: Optional[str] = Query(default=None, description="Filter by sector"),
    mcap: Optional[str] = Query(default=None, description="Filter: Mega, Large, Mid"),
    leadership: Optional[str] = Query(default=None, description="Filter: LEADER, FOLLOWER, LAGGARD"),
    state: Optional[str] = Query(default=None, description="Filter: EMERGING, CONFIRMED_LEADER, etc."),
):
    """RS Leaderboard — all tickers ranked by RS composite with filters."""
    board = _get_cached_leaderboard()

    if sector:
        board = [r for r in board if r["sector"].upper() == sector.upper()]
    if mcap:
        board = [r for r in board if r["mcap_bucket"].upper() == mcap.upper()]
    if leadership:
        board = [r for r in board if r["leadership"] == leadership.upper()]
    if state:
        board = [r for r in board if r["rs_state"] == state.upper()]

    return {
        "count": len(board[:limit]),
        "total": len(board),
        "filters": {"sector": sector, "mcap": mcap, "leadership": leadership, "state": state},
        "board": board[:limit],
    }


@router.get("/leaders")
async def rs_leaders(limit: int = Query(default=20, ge=1, le=50)):
    """Top RS leaders — confirmed + emerging only."""
    board = _get_cached_leaderboard()
    leaders = [
        r for r in board
        if r["leadership"] == "LEADER"
        or r["rs_state"] in ("CONFIRMED_LEADER", "EMERGING")
    ]
    return {"count": len(leaders[:limit]), "leaders": leaders[:limit]}


@router.get("/transitions")
async def rs_transitions():
    """RS state transitions — emerging, fading, extended tickers."""
    board = _get_cached_leaderboard()
    emerging = [r for r in board if r["rs_state"] == "EMERGING"]
    fading = [r for r in board if r["rs_state"] in ("FADING", "BROKEN")]
    extended = [r for r in board if r["rs_state"] == "EXTENDED"]

    return {
        "emerging": emerging, "fading": fading, "extended": extended,
        "emerging_count": len(emerging), "fading_count": len(fading),
        "extended_count": len(extended),
    }


@router.get("/sectors")
async def rs_by_sector():
    """RS aggregated by sector — which sectors produce the most leaders."""
    board = _get_cached_leaderboard()
    sectors: Dict[str, Dict] = {}
    for r in board:
        s = r["sector"]
        if s not in sectors:
            sectors[s] = {
                "sector": s, "etf": r["sector_etf"], "tickers": 0,
                "leaders": 0, "laggards": 0, "avg_rs": 0,
                "top_ticker": "", "top_rs": 0,
            }
        sectors[s]["tickers"] += 1
        sectors[s]["avg_rs"] += r["rs_composite"]
        if r["leadership"] == "LEADER":
            sectors[s]["leaders"] += 1
        if r["leadership"] == "LAGGARD":
            sectors[s]["laggards"] += 1
        if r["rs_composite"] > sectors[s]["top_rs"]:
            sectors[s]["top_rs"] = r["rs_composite"]
            sectors[s]["top_ticker"] = r["ticker"]

    for s in sectors.values():
        if s["tickers"]:
            s["avg_rs"] = round(s["avg_rs"] / s["tickers"], 1)

    result = sorted(sectors.values(), key=lambda x: x["avg_rs"], reverse=True)
    return {"sectors": result, "count": len(result)}


@router.get("/matrix")
async def rs_setup_matrix_view():
    """RS × Setup Quality matrix — TRADE / WAIT / TACTICAL / REJECT."""
    from src.engines.rs_hub import rs_setup_matrix
    from src.services.brief_data_service import load_brief

    board = _get_cached_leaderboard()
    brief = load_brief()

    matrix: Dict[str, List[Dict]] = {
        "TRADE": [], "WAIT": [], "TACTICAL": [], "REJECT": [],
    }

    for r in board:
        setup_score = 50
        for section in ("actionable", "watch", "review"):
            for item in brief.get(section, []):
                if item.get("ticker", "").upper() == r["ticker"]:
                    setup_score = (item.get("score", 5) or 5) * 10
                    break

        verdict = rs_setup_matrix(r["rs_quality"], setup_score)
        matrix[verdict].append({
            "ticker": r["ticker"], "rs_quality": r["rs_quality"],
            "setup_quality": setup_score, "verdict": verdict,
            "rs_state": r["rs_state"], "leadership": r["leadership"],
        })

    return {"matrix": matrix, "counts": {k: len(v) for k, v in matrix.items()}}


@router.get("/{ticker}")
async def rs_ticker_profile(ticker: str):
    """Individual RS profile for a single ticker."""
    ticker = ticker.strip().upper()
    board = _get_cached_leaderboard()

    for r in board:
        if r["ticker"] == ticker:
            return r

    # Not in watchlist — compute on the fly using services
    from src.engines.rs_hub import (
        RSProfile, classify_rs_state, compute_rs_quality,
        compute_rs_sustainability, compute_rs_tradeability,
        _get_mcap, _get_sector, _get_sector_etf,
    )
    from src.services.rs_data_service import compute_rs_date_aligned, fetch_closes_batch

    closes_map = fetch_closes_batch([ticker, "SPY"])
    ticker_closes = closes_map.get(ticker)
    spy_closes = closes_map.get("SPY")

    if ticker_closes is None or spy_closes is None or len(ticker_closes) < 22:
        return {
            "ticker": ticker, "error": "Insufficient data",
            "rs_composite": 100.0, "rs_state": "NEUTRAL", "leadership": "NEUTRAL",
        }

    rs_data = compute_rs_date_aligned(ticker_closes, spy_closes)
    p = RSProfile(
        ticker=ticker,
        rs_composite=rs_data["rs_composite"], rs_1m=rs_data["rs_1m"],
        rs_3m=rs_data["rs_3m"], rs_6m=rs_data["rs_6m"],
        rs_slope=rs_data["rs_slope"], rs_status=str(rs_data["rs_status"]),
        sector=_get_sector(ticker), sector_etf=_get_sector_etf(ticker),
        mcap_bucket=_get_mcap(ticker),
    )
    p.rs_state = classify_rs_state(p.rs_composite, p.rs_slope, p.rs_1m, p.rs_3m)
    p.rs_quality = compute_rs_quality(p.rs_composite, p.rs_slope)
    p.rs_tradeability = compute_rs_tradeability(p.rs_composite, p.rs_slope, None, False, True)
    p.rs_sustainability = compute_rs_sustainability(p.rs_composite, p.rs_1m, p.rs_3m, p.rs_6m, p.rs_slope)
    p.rs_delta_20d = p.rs_1m - 100
    p.rs_delta_60d = p.rs_3m - 100

    return p.to_dict()
