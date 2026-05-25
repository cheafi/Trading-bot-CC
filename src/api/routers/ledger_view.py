"""
Closed-Trade Ledger Viewer
============================
Read-only paginated view of data/closed_trades.jsonl with aggregate stats.

GET /api/ledger/list?limit=100&strategy=&direction=
GET /api/ledger/stats   (aggregate: count, win%, total pnl%, avg R, by-strategy)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from src.api.deps import optional_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

LEDGER_PATH = os.path.join("data", "closed_trades.jsonl")


def _read_all() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not os.path.exists(LEDGER_PATH):
        return rows
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    continue
    except Exception as exc:
        logger.warning("ledger read failed: %s", exc)
    return rows


@router.get("/api/ledger/list", tags=["ledger"])
async def ledger_list(
    limit: int = 100,
    strategy: Optional[str] = None,
    direction: Optional[str] = None,
    ticker: Optional[str] = None,
    _=optional_api_key,
):
    """Return most-recent closed trades (paginated, filterable)."""
    limit = max(1, min(limit, 1000))
    rows = _read_all()
    # Filters
    if strategy:
        s = strategy.lower()
        rows = [r for r in rows if str(r.get("strategy_id", "")).lower() == s]
    if direction:
        d = direction.upper()
        rows = [r for r in rows if str(r.get("direction", "")).upper() == d]
    if ticker:
        t = ticker.upper()
        rows = [r for r in rows if str(r.get("ticker", "")).upper() == t]
    rows.reverse()  # most recent first
    return {
        "ok": True,
        "total": len(rows),
        "limit": limit,
        "rows": rows[:limit],
        "path": LEDGER_PATH,
    }


@router.get("/api/ledger/stats", tags=["ledger"])
async def ledger_stats(_=optional_api_key):
    """Aggregate ledger stats — count, win-rate, expectancy, by-strategy."""
    rows = _read_all()
    if not rows:
        return {"ok": True, "count": 0, "summary": None, "by_strategy": {}}

    def _safe_float(v) -> Optional[float]:
        try:
            return float(v)
        except Exception:
            return None

    pnls = [
        _safe_float(r.get("pnl_pct"))
        for r in rows
        if _safe_float(r.get("pnl_pct")) is not None
    ]
    rs = [
        _safe_float(r.get("r_multiple"))
        for r in rows
        if _safe_float(r.get("r_multiple")) is not None
    ]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    total_pnl = round(sum(pnls), 3) if pnls else 0.0
    avg_pnl = round(sum(pnls) / len(pnls), 3) if pnls else 0.0
    avg_r = round(sum(rs) / len(rs), 3) if rs else None
    win_pnls = [p for p in pnls if p > 0]
    loss_pnls = [p for p in pnls if p < 0]
    avg_win = round(sum(win_pnls) / len(win_pnls), 3) if win_pnls else 0.0
    avg_loss = round(sum(loss_pnls) / len(loss_pnls), 3) if loss_pnls else 0.0
    profit_factor = round(sum(win_pnls) / abs(sum(loss_pnls)), 3) if loss_pnls else None
    expectancy = avg_pnl

    summary = {
        "count": len(rows),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wins / len(pnls) * 100, 2) if pnls else 0.0,
        "total_pnl_pct": total_pnl,
        "avg_pnl_pct": avg_pnl,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "avg_r_multiple": avg_r,
        "profit_factor": profit_factor,
        "expectancy_pct": expectancy,
    }

    # Per-strategy breakdown
    by_strategy: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sid = str(r.get("strategy_id") or "manual")
        bucket = by_strategy.setdefault(
            sid,
            {
                "count": 0,
                "wins": 0,
                "losses": 0,
                "pnl_sum": 0.0,
                "r_sum": 0.0,
                "r_count": 0,
            },
        )
        p = _safe_float(r.get("pnl_pct"))
        r_m = _safe_float(r.get("r_multiple"))
        bucket["count"] += 1
        if p is not None:
            if p > 0:
                bucket["wins"] += 1
            elif p < 0:
                bucket["losses"] += 1
            bucket["pnl_sum"] += p
        if r_m is not None:
            bucket["r_sum"] += r_m
            bucket["r_count"] += 1

    for sid, b in by_strategy.items():
        c = b["count"]
        b["win_rate_pct"] = round(b["wins"] / c * 100, 2) if c else 0.0
        b["avg_pnl_pct"] = round(b["pnl_sum"] / c, 3) if c else 0.0
        b["avg_r"] = round(b["r_sum"] / b["r_count"], 3) if b["r_count"] else None
        # cleanup
        b.pop("pnl_sum", None)
        b.pop("r_sum", None)
        b.pop("r_count", None)

    return {
        "ok": True,
        "count": len(rows),
        "summary": summary,
        "by_strategy": by_strategy,
        "path": LEDGER_PATH,
    }
