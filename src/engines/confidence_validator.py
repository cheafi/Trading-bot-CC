"""
Confidence Validator — Sprint 99
==================================
Proves that higher conviction tier actually predicts better trade outcomes.

Buckets closed trades from closed_trades.jsonl by:
  • Conviction tier  : TRADE / LEADER / WATCH (mapped from setup_grade A/B/C)
  • Regime at entry  : BULL / BEAR / SIDEWAYS / CHOPPY / unknown
  • Strategy family  : momentum / breakout / mean_revert / defensive / other

For each bucket reports:
  • count
  • win_rate (% trades with r_multiple > 0)
  • avg_r   (mean r_multiple)
  • median_r
  • expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
  • best / worst trade

Overall validation: does tier A > B > C in avg_r?
  Emits validation_pass: True/False with evidence string.

Usage
-----
    from src.engines.confidence_validator import ConfidenceValidator
    cv = ConfidenceValidator()
    report = cv.run()
    print(report["validation_pass"])
"""

from __future__ import annotations

import json
import logging
import os
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CLOSED_TRADES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "closed_trades.jsonl"
)

# Map setup_grade → conviction tier (fallback when conviction field absent)
_GRADE_TIER_MAP = {
    "A": "TRADE",
    "B": "LEADER",
    "C": "WATCH",
    "D": "WATCH",
}

# Canonicalise regime strings
_REGIME_NORM = {
    "uptrend": "BULL",
    "bull": "BULL",
    "bull_trending": "BULL",
    "rising": "BULL",
    "bear": "BEAR",
    "downtrend": "BEAR",
    "bear_trending": "BEAR",
    "falling": "BEAR",
    "crisis": "BEAR",
    "sideways": "SIDEWAYS",
    "side": "SIDEWAYS",
    "range": "SIDEWAYS",
    "choppy": "CHOPPY",
    "chop": "CHOPPY",
}

_TIER_RANK = {"TRADE": 3, "LEADER": 2, "WATCH": 1}


def _norm_regime(r: str) -> str:
    if not r:
        return "unknown"
    key = r.strip().lower()
    return _REGIME_NORM.get(key, key.upper()[:10])


def _norm_strategy(s: str) -> str:
    if not s:
        return "other"
    sl = s.strip().lower()
    if "mom" in sl:
        return "momentum"
    if "break" in sl:
        return "breakout"
    if "mean" in sl or "revert" in sl or "reversion" in sl:
        return "mean_revert"
    if "def" in sl or "bearish" in sl:
        return "defensive"
    return sl[:20]


def _bucket_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"count": 0}
    rs = [float(t.get("r_multiple", 0.0)) for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    win_rate = len(wins) / len(rs) if rs else 0.0
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = abs(statistics.mean(losses)) if losses else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    return {
        "count": len(rs),
        "win_rate": round(win_rate, 3),
        "avg_r": round(statistics.mean(rs), 3),
        "median_r": round(statistics.median(rs), 3),
        "avg_win_r": round(avg_win, 3),
        "avg_loss_r": round(-avg_loss, 3),
        "expectancy": round(expectancy, 3),
        "best_r": round(max(rs), 2),
        "worst_r": round(min(rs), 2),
    }


class ConfidenceValidator:
    """Validates that conviction tier predicts trade outcomes."""

    def __init__(self, trades_path: Optional[str] = None) -> None:
        self._path = trades_path or _CLOSED_TRADES_PATH

    def _load_trades(self) -> List[Dict[str, Any]]:
        trades: List[Dict[str, Any]] = []
        if not os.path.exists(self._path):
            logger.warning("closed_trades.jsonl not found at %s", self._path)
            return trades
        seen: set = set()
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    t = json.loads(line)
                    # deduplicate by key fields
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

    def _enrich(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add normalised tier / regime / strategy fields."""
        enriched = []
        for t in trades:
            tc = dict(t)
            # conviction tier
            grade = tc.get("setup_grade", "")
            tier = tc.get("conviction", "") or _GRADE_TIER_MAP.get(
                grade.upper(), "WATCH"
            )
            tc["_tier"] = tier.upper() if tier else "WATCH"
            tc["_regime"] = _norm_regime(tc.get("regime_at_entry", ""))
            tc["_strategy"] = _norm_strategy(tc.get("strategy_id", ""))
            enriched.append(tc)
        return enriched

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """
        Build validation report.

        Returns
        -------
        {
          "validation_pass": bool,
          "evidence": str,
          "by_tier": {...},
          "by_regime": {...},
          "by_strategy": {...},
          "sample_size": int,
          "note": str          # if insufficient data
        }
        """
        raw = self._load_trades()
        if not raw:
            return {
                "validation_pass": False,
                "evidence": "No trade data",
                "by_tier": {},
                "by_regime": {},
                "by_strategy": {},
                "sample_size": 0,
                "note": "Load real trade history to enable confidence validation.",
            }

        trades = self._enrich(raw)
        sample_size = len(trades)

        # ── By tier ───────────────────────────────────────────────────────────
        tier_buckets: Dict[str, List] = defaultdict(list)
        for t in trades:
            tier_buckets[t["_tier"]].append(t)

        by_tier = {tier: _bucket_stats(lst) for tier, lst in tier_buckets.items()}

        # Validation: TRADE avg_r > LEADER avg_r > WATCH avg_r
        tier_avgs = {
            tier: by_tier[tier].get("avg_r", 0.0)
            for tier in ["TRADE", "LEADER", "WATCH"]
            if tier in by_tier
        }
        ordered_tiers = sorted(
            tier_avgs.items(), key=lambda kv: _TIER_RANK.get(kv[0], 0), reverse=True
        )

        if len(ordered_tiers) >= 2:
            monotone = all(
                ordered_tiers[i][1] >= ordered_tiers[i + 1][1]
                for i in range(len(ordered_tiers) - 1)
            )
            validation_pass = monotone
            if monotone:
                summary_parts = [f"{t}: {v:+.2f}R" for t, v in ordered_tiers]
                evidence = "✅ Conviction predicts outcomes: " + " > ".join(
                    summary_parts
                )
            else:
                summary_parts = [f"{t}: {v:+.2f}R" for t, v in ordered_tiers]
                evidence = "⚠️ Conviction ordering broken: " + " | ".join(summary_parts)
        else:
            validation_pass = False
            evidence = f"Insufficient tier diversity ({len(ordered_tiers)} tier(s) found, need ≥2)"

        # ── By regime ─────────────────────────────────────────────────────────
        regime_buckets: Dict[str, List] = defaultdict(list)
        for t in trades:
            regime_buckets[t["_regime"]].append(t)
        by_regime = {r: _bucket_stats(lst) for r, lst in regime_buckets.items()}

        # ── By strategy family ────────────────────────────────────────────────
        strat_buckets: Dict[str, List] = defaultdict(list)
        for t in trades:
            strat_buckets[t["_strategy"]].append(t)
        by_strategy = {s: _bucket_stats(lst) for s, lst in strat_buckets.items()}

        note = ""
        if sample_size < 30:
            note = (
                f"⚠ Only {sample_size} trades — results directional only. "
                "Need ≥30 resolved trades for statistical significance."
            )

        return {
            "validation_pass": validation_pass,
            "evidence": evidence,
            "by_tier": by_tier,
            "by_regime": by_regime,
            "by_strategy": by_strategy,
            "sample_size": sample_size,
            "note": note,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_validator: Optional[ConfidenceValidator] = None


def get_confidence_validator() -> ConfidenceValidator:
    global _validator
    if _validator is None:
        _validator = ConfidenceValidator()
    return _validator
