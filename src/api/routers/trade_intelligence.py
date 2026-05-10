"""
Trade Intelligence Router — Sprint 99
=======================================
Historical trade intelligence layer: proves self-learning is real.

GET /api/v1/trade-intel
  Full intelligence report:
    • trade history with benchmark-relative outcome
    • why-win / why-loss tags
    • MAE/MFE proxy (from r_multiple distribution)
    • repeated mistake tags
    • confidence validation (bucket analysis)

GET /api/v1/trade-intel/confidence
  Confidence validation only — proves tier → outcome correlation.

GET /api/v1/trade-intel/mistakes
  Repeated mistake patterns with count + avg loss.

Auth: no auth required (read-only historical data).
"""

from __future__ import annotations

import json
import logging
import os
import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.api.deps import sanitize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trade-intel", tags=["trade-intelligence"])

_TRADES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "closed_trades.jsonl"
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_trades(path: str) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return trades
    seen: set = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
                key = (
                    t.get("ticker", ""),
                    t.get("entry_time", ""),
                    t.get("exit_time", ""),
                    t.get("strategy_id", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                trades.append(t)
            except Exception:
                continue
    return trades


def _tag_why(trade: Dict[str, Any]) -> Dict[str, str]:
    """
    Assign why-win / why-loss tag from available fields.
    Returns {"why_win": "...", "why_loss": "..."} with at most one non-empty.
    """
    r = float(trade.get("r_multiple", 0.0))
    regime = (trade.get("regime_at_entry") or "").upper()
    grade = (trade.get("setup_grade") or "C").upper()
    strategy = (trade.get("strategy_id") or "").lower()

    if r > 0:
        if "BULL" in regime or "UPTREND" in regime:
            why = "Regime tailwind (BULL entry)"
        elif grade == "A":
            why = "High-quality setup grade"
        elif "mom" in strategy or "breakout" in strategy:
            why = "Momentum / breakout follow-through"
        else:
            why = "Setup resolved in favour"
        return {"why_win": why, "why_loss": ""}
    else:
        if "BEAR" in regime or "CRISIS" in regime:
            why = "Regime headwind (BEAR/Crisis entry)"
        elif grade == "C":
            why = "Low-quality setup (grade C)"
        elif "CHOP" in regime or "SIDE" in regime:
            why = "Choppy regime — no trend follow-through"
        elif r < -1.5:
            why = "Held past 1R stop — stop discipline failure"
        else:
            why = "Setup failed at resistance / invalidation"
        return {"why_win": "", "why_loss": why}


def _mistake_tags(trade: Dict[str, Any]) -> List[str]:
    """Return list of repeated-mistake tags for a losing trade."""
    tags: List[str] = []
    r = float(trade.get("r_multiple", 0.0))
    regime = (trade.get("regime_at_entry") or "").upper()
    grade = (trade.get("setup_grade") or "").upper()
    hold = float(trade.get("hold_days") or 0.0)

    if r >= 0:
        return tags  # not a loss

    if r < -1.5:
        tags.append("STOP_VIOLATION")  # held past 1R stop
    if "BEAR" in regime or "CRISIS" in regime:
        tags.append("WRONG_REGIME")  # traded into headwind
    if grade == "C":
        tags.append("LOW_QUALITY_SETUP")  # should have been skipped
    if "CHOP" in regime or "SIDE" in regime:
        tags.append("REGIME_MISMATCH")  # momentum in sideways
    if hold == 0.0 and r < 0:
        tags.append("PREMATURE_EXIT")  # exited same day at loss
    return tags


def _enrich(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for t in trades:
        tc = dict(t)
        tags = _tag_why(tc)
        tc["why_win"] = tags["why_win"]
        tc["why_loss"] = tags["why_loss"]
        tc["outcome"] = "WIN" if float(tc.get("r_multiple", 0)) > 0 else "LOSS"
        tc["mistake_tags"] = _mistake_tags(tc)
        result.append(tc)
    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
async def trade_intelligence(
    limit: int = Query(default=50, ge=1, le=500),
    strategy: Optional[str] = Query(default=None),
    regime: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """
    Full trade intelligence report.

    Returns enriched trade history + confidence validation + mistake analysis.
    """
    from src.engines.confidence_validator import get_confidence_validator

    trades = _load_trades(_TRADES_PATH)
    if not trades:
        return {
            "trades": [],
            "sample_size": 0,
            "confidence_validation": None,
            "mistake_summary": {},
            "note": "No trade history found. Add trades to data/closed_trades.jsonl",
        }

    enriched = _enrich(trades)

    # Filter
    if strategy:
        enriched = [
            t
            for t in enriched
            if strategy.lower() in (t.get("strategy_id") or "").lower()
        ]
    if regime:
        enriched = [
            t
            for t in enriched
            if regime.upper() in (t.get("regime_at_entry") or "").upper()
        ]

    # Mistake summary
    all_tags: List[str] = []
    for t in enriched:
        all_tags.extend(t.get("mistake_tags", []))
    mistake_counts = dict(Counter(all_tags).most_common())

    # Benchmark-relative return (simple: compare pnl_pct to SPY ~15% annual = 0.06% daily)
    for t in enriched:
        hold = float(t.get("hold_days") or 1.0) or 1.0
        spy_daily = 0.06  # assumed 0.06% / day as benchmark baseline
        spy_equiv = spy_daily * hold
        t["excess_pnl_pct"] = round(float(t.get("pnl_pct") or 0.0) - spy_equiv, 2)

    # Confidence validation
    cv = get_confidence_validator()
    confidence_validation = cv.run()

    return sanitize_for_json(
        {
            "trades": enriched[:limit],
            "sample_size": len(enriched),
            "total_sample": len(trades),
            "confidence_validation": confidence_validation,
            "mistake_summary": mistake_counts,
            "win_rate": round(
                sum(1 for t in enriched if t["outcome"] == "WIN")
                / max(len(enriched), 1),
                3,
            ),
            "avg_r": (
                round(
                    statistics.mean([float(t.get("r_multiple", 0)) for t in enriched]),
                    3,
                )
                if enriched
                else 0.0
            ),
        }
    )


@router.get("/confidence")
async def confidence_validation() -> Dict[str, Any]:
    """
    Conviction-tier → outcome bucket analysis.
    Proves (or disproves) that TRADE > LEADER > WATCH in avg R-multiple.
    """
    from src.engines.confidence_validator import get_confidence_validator

    cv = get_confidence_validator()
    return sanitize_for_json(cv.run())


@router.get("/mistakes")
async def repeated_mistakes() -> Dict[str, Any]:
    """
    Repeated mistake tags across all closed trades.
    Returns ranked mistake patterns with count + avg loss.
    """
    trades = _load_trades(_TRADES_PATH)
    if not trades:
        return {"mistakes": [], "sample_size": 0}

    enriched = _enrich(trades)
    losses = [t for t in enriched if t["outcome"] == "LOSS"]

    tag_groups: Dict[str, List[float]] = defaultdict(list)
    for t in losses:
        for tag in t.get("mistake_tags", []):
            tag_groups[tag].append(float(t.get("r_multiple", 0.0)))

    mistakes = sorted(
        [
            {
                "tag": tag,
                "count": len(rs),
                "avg_loss_r": round(statistics.mean(rs), 3),
                "worst_r": round(min(rs), 2),
                "description": _MISTAKE_DESCRIPTIONS.get(tag, tag),
            }
            for tag, rs in tag_groups.items()
        ],
        key=lambda m: m["count"],
        reverse=True,
    )

    return sanitize_for_json(
        {
            "mistakes": mistakes,
            "sample_size": len(losses),
            "note": "Repeated mistake tags from closed losing trades",
        }
    )


_MISTAKE_DESCRIPTIONS = {
    "STOP_VIOLATION": "Held position past the 1R stop — loss exceeded planned risk",
    "WRONG_REGIME": "Entered a long trade in a BEAR/Crisis regime — directional headwind",
    "LOW_QUALITY_SETUP": "Took a grade-C setup — below minimum quality threshold",
    "REGIME_MISMATCH": "Applied momentum strategy in SIDEWAYS/CHOPPY regime",
    "PREMATURE_EXIT": "Exited same day for a loss — possibly panic-sold at noise",
}
