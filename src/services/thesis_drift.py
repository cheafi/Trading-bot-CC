"""Thesis drift — compare entry thesis vs current evidence."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_thesis_drift(
    ticker: str,
    *,
    stock_intel: Dict[str, Any],
    pm_memory: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pm = pm_memory or {}
    original = pm.get("original_thesis") or pm.get("why_liked")
    unified = stock_intel.get("unified_decision") or {}
    narrative = stock_intel.get("narrative") or {}
    regime = stock_intel.get("regime") or {}

    weakened: List[str] = []
    improved: List[str] = []
    if (unified.get("label") or "").upper() in ("AVOID", "NO TRADE", "PASS"):
        weakened.append("Unified decision flipped negative")
    if not regime.get("should_trade"):
        weakened.append("Regime gate closed")
    for c in narrative.get("contradictions") or []:
        weakened.append(str(c)[:100])
    if (unified.get("label") or "").upper() == "TRADE":
        improved.append("Trade-grade unified label")
    for w in (narrative.get("bull_case") or [])[:2]:
        improved.append(str(w)[:80])

    drift_score = len(weakened) * 15 - len(improved) * 10
    drift_score = max(0, min(100, 50 + drift_score))
    status = (
        "drifting"
        if drift_score >= 65
        else "stable"
        if drift_score <= 40
        else "watch"
    )
    return {
        "ticker": ticker.upper(),
        "status": status,
        "drift_score": drift_score,
        "original_thesis": original,
        "what_changed": weakened[:4] or ["No material drift detected"],
        "weakened": weakened,
        "improved": improved,
        "invalidates": unified.get("invalidation"),
        "monitor_next": [
            "Regime + breadth",
            "Stop / invalidation level",
            "Next catalyst",
        ],
        "recommended_action": (
            "TRIM or exit review"
            if status == "drifting"
            else "HOLD — monitor"
            if status == "watch"
            else "Hold per thesis"
        ),
    }
