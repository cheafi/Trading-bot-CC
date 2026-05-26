"""
Fund Portfolio Router — Sprint 94 / Sprint 105
===============================================
REST API for per-fund holdings, trade log, performance history,
cross-fund comparison, and live paper-position P&L tracker.

Endpoints:
  GET /api/v7/funds                              — list all funds with latest metrics
  GET /api/v7/funds/{fund_id}/holdings           — current holdings snapshot
  GET /api/v7/funds/{fund_id}/trades             — recent trade log
  GET /api/v7/funds/{fund_id}/performance        — daily NAV history
  GET /api/v7/funds/{fund_id}/positions          — open paper positions + live P&L (Sprint 105)
  GET /api/v7/funds/positions/all               — all open positions across sleeves (Sprint 105)
  GET /api/v7/funds/compare                      — side-by-side metrics for all funds
  GET /api/v7/funds/daily-coverage               — which fund selected each daily rec
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from src.services.fund_lab_service import FundLabService
from src.services.fund_persistence import (
    get_holdings,
    get_performance_history,
    get_trade_log,
)

router = APIRouter(prefix="/api/v7/funds", tags=["funds"])

_FUND_IDS = list(
    FundLabService.FUND_UNIVERSES.keys()
)  # FUND_ALPHA, FUND_PENDA, FUND_CAT

_FUND_META: Dict[str, Dict[str, Any]] = {
    name: {
        "id": name,
        "display_name": name.replace("FUND_", "").title(),
        "thesis": spec["thesis"],
        "style": spec.get("style", {}),
    }
    for name, spec in FundLabService.FUND_UNIVERSES.items()
}


@router.get("")
async def list_funds() -> List[Dict[str, Any]]:
    """Return metadata + latest persisted performance for all 3 funds."""
    result = []
    for fid in _FUND_IDS:
        meta = dict(_FUND_META.get(fid, {"id": fid}))
        history = get_performance_history(fid, days=1)
        meta["latest_performance"] = history[0] if history else None
        meta["holdings_count"] = len(get_holdings(fid))
        result.append(meta)
    return result


@router.get("/compare")
async def compare_funds(days: int = Query(default=30, ge=1, le=365)) -> Dict[str, Any]:
    """Side-by-side performance comparison for all 3 funds."""
    comparison: Dict[str, Any] = {}
    for fid in _FUND_IDS:
        history = get_performance_history(fid, days=days)
        holdings = get_holdings(fid)
        comparison[fid] = {
            "display_name": _FUND_META.get(fid, {}).get("display_name", fid),
            "thesis": _FUND_META.get(fid, {}).get("thesis", ""),
            "style_stop_r": _FUND_META.get(fid, {}).get("style", {}).get("stop_r"),
            "style_target_r": _FUND_META.get(fid, {}).get("style", {}).get("target_r"),
            "style_turnover": _FUND_META.get(fid, {}).get("style", {}).get("turnover"),
            "performance_days": len(history),
            "latest": history[0] if history else None,
            "holdings": holdings,
        }
    return {"funds": comparison, "days_requested": days}


@router.get("/daily-coverage")
async def daily_coverage() -> Dict[str, Any]:
    """
    Cross-reference: for each fund, list today's holdings.
    Shows which fund(s) hold each ticker — the 'daily rec → fund selection' map.
    """
    ticker_map: Dict[str, List[str]] = {}
    fund_holdings: Dict[str, List[Dict]] = {}

    for fid in _FUND_IDS:
        holdings = get_holdings(fid)
        fund_holdings[fid] = holdings
        for h in holdings:
            t = h.get("ticker", "")
            if t:
                ticker_map.setdefault(t, []).append(fid)

    # Build coverage list sorted by number of funds holding the ticker
    coverage = [
        {
            "ticker": ticker,
            "held_by": funds,
            "fund_count": len(funds),
            "conviction": "HIGH" if len(funds) >= 2 else "SINGLE",
        }
        for ticker, funds in sorted(ticker_map.items(), key=lambda x: -len(x[1]))
    ]

    return {
        "coverage": coverage,
        "fund_holdings": fund_holdings,
        "multi_fund_tickers": [c for c in coverage if c["fund_count"] >= 2],
    }


@router.get("/{fund_id}/holdings")
async def fund_holdings(
    fund_id: str,
    date_key: str = Query(default=None, description="YYYY-MM-DD, defaults to today"),
) -> Dict[str, Any]:
    """Current holdings snapshot for one fund."""
    fid = fund_id.upper()
    if fid not in _FUND_IDS:
        return {"error": f"Unknown fund: {fid}", "valid_ids": _FUND_IDS}
    holdings = get_holdings(fid, date_key=date_key)
    meta = _FUND_META.get(fid, {})
    return {
        "fund_id": fid,
        "display_name": meta.get("display_name", fid),
        "thesis": meta.get("thesis", ""),
        "date_key": date_key,
        "holdings": holdings,
        "count": len(holdings),
    }


@router.get("/{fund_id}/trades")
async def fund_trades(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    """Recent trade log for one fund."""
    fid = fund_id.upper()
    if fid not in _FUND_IDS:
        return {"error": f"Unknown fund: {fid}", "valid_ids": _FUND_IDS}
    trades = get_trade_log(fid, limit=limit)
    return {"fund_id": fid, "trades": trades, "count": len(trades)}


@router.get("/{fund_id}/performance")
async def fund_performance(
    fund_id: str,
    days: int = Query(default=30, ge=1, le=365),
) -> Dict[str, Any]:
    """Daily NAV history for one fund."""
    fid = fund_id.upper()
    if fid not in _FUND_IDS:
        return {"error": f"Unknown fund: {fid}", "valid_ids": _FUND_IDS}
    history = get_performance_history(fid, days=days)
    return {
        "fund_id": fid,
        "display_name": _FUND_META.get(fid, {}).get("display_name", fid),
        "history": history,
        "days": len(history),
    }


# ── Live Paper-Position P&L (Sprint 105) ──────────────────────────────────


@router.get("/positions/all")
async def all_open_positions() -> Dict[str, Any]:
    """Open paper positions across all fund sleeves with unrealised P&L."""
    from src.services.fund_persistence import get_open_paper_positions  # noqa: PLC0415

    all_pos: List[Dict[str, Any]] = []
    for fid in _FUND_IDS:
        positions = get_open_paper_positions(fid)
        for p in positions:
            p["fund_id"] = fid
            p["display_name"] = _FUND_META.get(fid, {}).get("display_name", fid)
        all_pos.extend(positions)

    total_pnl = sum(p.get("unrealised_pnl", 0.0) or 0.0 for p in all_pos)
    return {
        "total_open": len(all_pos),
        "total_unrealised_pnl": round(total_pnl, 2),
        "positions": all_pos,
    }


@router.get("/{fund_id}/positions")
async def fund_open_positions(fund_id: str) -> Dict[str, Any]:
    """Open paper positions for one fund sleeve with entry date, stop, target, unrealised P&L."""
    from src.services.fund_persistence import get_open_paper_positions  # noqa: PLC0415

    fid = fund_id.upper()
    if fid not in _FUND_IDS:
        return {"error": f"Unknown fund: {fid}", "valid_ids": _FUND_IDS}
    positions = get_open_paper_positions(fid)

    total_pnl = sum(p.get("unrealised_pnl", 0.0) or 0.0 for p in positions)
    total_cost = sum(
        (p.get("entry_price", 0) or 0) * (p.get("shares", 0) or 0) for p in positions
    )
    return {
        "fund_id": fid,
        "display_name": _FUND_META.get(fid, {}).get("display_name", fid),
        "open_positions": len(positions),
        "total_cost_basis": round(total_cost, 2),
        "total_unrealised_pnl": round(total_pnl, 2),
        "positions": positions,
    }
