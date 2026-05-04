"""
Historical Analog Matcher — Sprint 69
========================================
Finds similar past trades from closed_trades.jsonl to populate
VCPAction.similar_cases and provide pattern confidence.

Similarity based on: strategy, regime, setup_grade, direction.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_TRADES_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "data",
    "closed_trades.jsonl",
)


def load_closed_trades(
    path: str = "",
) -> List[Dict[str, Any]]:
    """Load closed trades from JSONL file."""
    if not path:
        path = _TRADES_PATH  # read at call-time so test monkey-patches work
    trades: List[Dict[str, Any]] = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))
    except FileNotFoundError:
        logger.debug("No closed trades file at %s", path)
    except Exception as e:
        logger.warning("Error loading closed trades: %s", e)
    return trades


def find_similar_cases(
    strategy: str,
    regime: str = "",
    grade: str = "",
    direction: str = "LONG",
    trades: List[Dict[str, Any]] | None = None,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Find historical trades similar to the current setup.

    Matching priority:
      1. Same strategy (required)
      2. Same regime (+2 score)
      3. Same/similar grade (+1 score)
      4. Same direction (+1 score)

    Returns list of dicts with trade info + similarity_score.
    """
    if trades is None:
        trades = load_closed_trades()

    if not trades:
        return []

    scored = []
    strategy_lower = strategy.lower()

    for trade in trades:
        t_strat = trade.get("strategy_id", "").lower()
        # Strategy must match
        if t_strat != strategy_lower:
            continue

        score = 0

        # Regime match
        t_regime = trade.get("regime_at_entry", "")
        if regime and t_regime == regime:
            score += 2

        # Grade match (exact=+1, adjacent=+0.5)
        t_grade = trade.get("setup_grade", "")
        if grade and t_grade:
            if t_grade == grade:
                score += 1
            elif _grade_distance(grade, t_grade) <= 1:
                score += 0.5

        # Direction match
        t_dir = trade.get("direction", "LONG")
        if t_dir == direction:
            score += 1

        scored.append(
            {
                "ticker": trade.get("ticker", ""),
                "strategy": t_strat,
                "pnl_pct": round(trade.get("pnl_pct", 0), 2),
                "r_multiple": round(trade.get("r_multiple", 0), 2),
                "regime": t_regime,
                "grade": t_grade,
                "hold_days": trade.get("hold_days", 0),
                "similarity_score": score,
            }
        )

    # Sort by similarity desc, then by recency
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:max_results]


def analog_summary(
    cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Summarize historical analogs."""
    if not cases:
        return {
            "count": 0,
            "avg_pnl": 0,
            "win_rate": 0,
            "message": "No historical analogs found",
        }

    wins = [c for c in cases if c["pnl_pct"] > 0]
    avg_pnl = sum(c["pnl_pct"] for c in cases) / len(cases)
    win_rate = len(wins) / len(cases) * 100

    return {
        "count": len(cases),
        "avg_pnl": round(avg_pnl, 2),
        "win_rate": round(win_rate, 1),
        "avg_r": round(sum(c["r_multiple"] for c in cases) / len(cases), 2),
        "message": (
            f"{len(cases)} similar trades: "
            f"{win_rate:.0f}% win rate, "
            f"avg {avg_pnl:+.1f}%"
        ),
    }


_GRADE_ORDER = [
    "F",
    "D",
    "C",
    "C+",
    "B-",
    "B",
    "B+",
    "A-",
    "A",
    "A+",
]


def _grade_distance(g1: str, g2: str) -> int:
    """Distance between two grades."""
    try:
        i1 = _GRADE_ORDER.index(g1)
        i2 = _GRADE_ORDER.index(g2)
        return abs(i1 - i2)
    except ValueError:
        return 99
