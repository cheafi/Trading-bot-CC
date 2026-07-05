"""Top leaders / smart-money confirmation — supplemental overlay for Funds tab."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.stock_universe import CORE_WATCHLIST


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _signal_row(
    *,
    signal: str,
    strength: str,
    source: str,
    lag: str,
    confidence: str,
    use_case: str,
    tickers: List[str] | None = None,
    manager_name: str = "",
    filing_action: str = "",
    sleeve_relevance: str = "",
    confirms: str = "",
    conflicts: str = "",
) -> Dict[str, Any]:
    return {
        "signal": signal,
        "strength": strength,
        "source": source,
        "lag": lag,
        "confidence": confidence,
        "use_case": use_case,
        "tickers": tickers or [],
        "manager_name": manager_name,
        "filing_action": filing_action,
        "sleeve_relevance": sleeve_relevance,
        "confirms": confirms,
        "conflicts": conflicts,
    }


def build_leaders_snapshot(
    *,
    tickers: List[str] | None = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Smart-money confirmation overlay — confirm only, not buy signals.
    Wire 13F / insider / options feeds for production.
    """
    universe = tickers or CORE_WATCHLIST[:20]
    rows: List[Dict[str, Any]] = []
    for i, t in enumerate(universe[:limit]):
        rows.append(
            {
                "ticker": t,
                "leader_overlap_count": 1 if i % 4 == 0 else 0,
                "quality_bucket": "tier_1" if i % 5 == 0 else "tier_2",
                "accumulation_trend": "watch" if i % 3 == 0 else "neutral",
                "crowding_score": min(100, 20 + i * 3),
                "signal_quality": "delayed_filing",
                "usefulness": "supplemental_only",
            }
        )
    repeated = [r for r in rows if r["leader_overlap_count"] >= 1][:5]
    adds_tickers = [r["ticker"] for r in rows if r["accumulation_trend"] == "watch"][:3]

    smart_money = {
        "title": "Smart money · confirm-only overlay",
        "signals": [
            _signal_row(
                signal="13F adds",
                strength="weak" if adds_tickers else "none",
                source="SEC 13F delta (stub)",
                lag="45–90d",
                confidence="low" if adds_tickers else "n/a",
                use_case="Confirm only — lagged institutional accumulation",
                tickers=adds_tickers,
                manager_name="Institutional 13F filers (aggregate)",
                filing_action="add" if adds_tickers else "flat",
                sleeve_relevance="Leader / Balanced — growth confirmation",
                confirms="Momentum sleeve thesis if overlap with holdings",
                conflicts="Tactical defensive sleeve if crowding high",
            ),
            _signal_row(
                signal="Insider cluster buy",
                strength="none",
                source="Form 4 cluster scan (stub)",
                lag="1–5d",
                confidence="n/a",
                use_case="Timing confirm — not standalone entry",
                manager_name="Corporate insiders",
                filing_action="none",
                sleeve_relevance="Single-name confirm for Leader picks",
                confirms="Entry timing on held names",
                conflicts="None observed",
            ),
            _signal_row(
                signal="Options call sweep",
                strength="moderate" if adds_tickers else "none",
                source="Unusual options flow (stub)",
                lag="0–1d",
                confidence="medium" if adds_tickers else "low",
                use_case="Watch for stock follow-through before sizing",
                tickers=adds_tickers,
                manager_name="Market makers / aggressive buyers",
                filing_action="n/a",
                sleeve_relevance="Tactical timing overlay",
                confirms="Near-term bullish bias on watched tickers",
                conflicts="Defensive sleeve if vol spike without follow-through",
            ),
            _signal_row(
                signal="Influencer",
                strength="low signal",
                source="Social sentiment overlay (stub)",
                lag="0d",
                confidence="low",
                use_case="Watch only — do not size on influencer alone",
                manager_name="Social / influencer accounts",
                filing_action="n/a",
                sleeve_relevance="None — noise filter",
                confirms="—",
                conflicts="Can conflict with fund-lab quant picks",
            ),
        ],
    }

    return {
        "as_of": _now(),
        "repeated_accumulation": repeated,
        "newly_discovered": adds_tickers,
        "broadly_trimmed": [],
        "rows": rows,
        "smart_money": smart_money,
        "evidence": {
            "basis": "placeholder_universe_scan",
            "label": "Confirm-only overlay · wire 13F / insider / options feeds",
        },
    }
