"""
Trade Review Router — Sprint 115 (P0)
======================================
Recent trades, win/loss review summary, and trade journal.
Reads from data/closed_trades.jsonl.

Endpoints:
  GET /api/v7/trades/recent       — latest closed trades
  GET /api/v7/trades/review       — win/loss review summary
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/trades", tags=["trades"])

_TRADES_FILE = Path("data/closed_trades.jsonl")


def _load_closed_trades() -> List[Dict[str, Any]]:
    """Load all closed trades from JSONL file."""
    if not _TRADES_FILE.exists():
        return []
    trades = []
    for line in _TRADES_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            trades.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return trades


@router.get("/recent")
async def recent_trades(
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """Latest closed trades with P&L and metadata."""
    trades = _load_closed_trades()
    # Sort by exit_time descending
    trades.sort(key=lambda t: t.get("exit_time", ""), reverse=True)
    recent = trades[: int(limit)]

    total_pnl = sum(t.get("pnl_pct", 0) for t in recent)
    winners = [t for t in recent if t.get("pnl_pct", 0) > 0]
    losers = [t for t in recent if t.get("pnl_pct", 0) < 0]

    return {
        "trades": recent,
        "count": len(recent),
        "total_count": len(trades),
        "summary": {
            "avg_pnl_pct": round(total_pnl / len(recent), 2) if recent else 0,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": round(len(winners) / len(recent) * 100, 1) if recent else 0,
        },
    }


@router.get("/review")
async def trade_review() -> Dict[str, Any]:
    """
    Win/loss review summary — top win/loss reasons, strategy performance,
    repeated patterns, improvement ideas.
    """
    trades = _load_closed_trades()
    if not trades:
        return {"message": "No closed trades yet", "review": {}}

    winners = [t for t in trades if t.get("pnl_pct", 0) > 0]
    losers = [t for t in trades if t.get("pnl_pct", 0) < 0]
    flat = [t for t in trades if t.get("pnl_pct", 0) == 0]

    # Strategy breakdown
    strategy_stats: Dict[str, Dict] = {}
    for t in trades:
        sid = t.get("strategy_id", "unknown")
        s = strategy_stats.setdefault(
            sid, {"wins": 0, "losses": 0, "total_pnl": 0, "trades": 0, "total_r": 0}
        )
        s["trades"] += 1
        s["total_pnl"] += t.get("pnl_pct", 0)
        s["total_r"] += t.get("r_multiple", 0)
        if t.get("pnl_pct", 0) > 0:
            s["wins"] += 1
        elif t.get("pnl_pct", 0) < 0:
            s["losses"] += 1

    for sid, s in strategy_stats.items():
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else 0
        s["avg_pnl"] = round(s["total_pnl"] / s["trades"], 2) if s["trades"] else 0
        s["avg_r"] = round(s["total_r"] / s["trades"], 2) if s["trades"] else 0

    # Sort strategies by avg P&L
    best_strategies = sorted(
        strategy_stats.items(), key=lambda x: x[1]["avg_pnl"], reverse=True
    )
    worst_strategies = sorted(strategy_stats.items(), key=lambda x: x[1]["avg_pnl"])

    # Setup grade breakdown
    grade_stats: Dict[str, Dict] = {}
    for t in trades:
        grade = t.get("setup_grade", "?")
        g = grade_stats.setdefault(
            grade, {"wins": 0, "losses": 0, "trades": 0, "total_pnl": 0}
        )
        g["trades"] += 1
        g["total_pnl"] += t.get("pnl_pct", 0)
        if t.get("pnl_pct", 0) > 0:
            g["wins"] += 1
        elif t.get("pnl_pct", 0) < 0:
            g["losses"] += 1

    for g in grade_stats.values():
        g["win_rate"] = round(g["wins"] / g["trades"] * 100, 1) if g["trades"] else 0
        g["avg_pnl"] = round(g["total_pnl"] / g["trades"], 2) if g["trades"] else 0

    # Regime breakdown
    regime_stats: Dict[str, Dict] = {}
    for t in trades:
        regime = t.get("regime_at_entry", "UNKNOWN") or "UNKNOWN"
        r = regime_stats.setdefault(
            regime, {"wins": 0, "losses": 0, "trades": 0, "total_pnl": 0}
        )
        r["trades"] += 1
        r["total_pnl"] += t.get("pnl_pct", 0)
        if t.get("pnl_pct", 0) > 0:
            r["wins"] += 1
        elif t.get("pnl_pct", 0) < 0:
            r["losses"] += 1

    for r in regime_stats.values():
        r["win_rate"] = round(r["wins"] / r["trades"] * 100, 1) if r["trades"] else 0
        r["avg_pnl"] = round(r["total_pnl"] / r["trades"], 2) if r["trades"] else 0

    # Top winners/losers
    top_winners = sorted(winners, key=lambda t: t.get("pnl_pct", 0), reverse=True)[:5]
    top_losers = sorted(losers, key=lambda t: t.get("pnl_pct", 0))[:5]

    # Insights
    insights = []
    if best_strategies:
        best_name, best_s = best_strategies[0]
        insights.append(
            f"Best strategy: {best_name} (avg {best_s['avg_pnl']:+.1f}%, win rate {best_s['win_rate']}%)"
        )
    if worst_strategies:
        worst_name, worst_s = worst_strategies[0]
        if worst_s["avg_pnl"] < 0:
            insights.append(
                f"Worst strategy: {worst_name} (avg {worst_s['avg_pnl']:+.1f}%) — review or retire"
            )
    if grade_stats.get("A", {}).get("win_rate", 0) > grade_stats.get("C", {}).get(
        "win_rate", 0
    ):
        insights.append("A-grade setups outperform C-grade — increase selectivity")
    avg_winner = (
        sum(t.get("pnl_pct", 0) for t in winners) / len(winners) if winners else 0
    )
    avg_loser = (
        abs(sum(t.get("pnl_pct", 0) for t in losers) / len(losers)) if losers else 0
    )
    if avg_winner and avg_loser:
        payoff = round(avg_winner / avg_loser, 2)
        insights.append(
            f"Payoff ratio: {payoff}:1 (avg win {avg_winner:+.1f}% vs avg loss {-avg_loser:.1f}%)"
        )

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "flat": len(flat),
        "win_rate": round(len(winners) / len(trades) * 100, 1) if trades else 0,
        "avg_pnl_pct": (
            round(sum(t.get("pnl_pct", 0) for t in trades) / len(trades), 2)
            if trades
            else 0
        ),
        "strategy_breakdown": dict(best_strategies),
        "grade_breakdown": grade_stats,
        "regime_breakdown": regime_stats,
        "top_winners": top_winners,
        "top_losers": top_losers,
        "insights": insights,
    }
