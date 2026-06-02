"""
《纳瓦尔宝典》compounding priority — long-term edge vs turnover noise.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

COMPOUNDING_LABELS: Dict[str, str] = {
    "compound": "favor compounding — hold process, avoid churn",
    "turnover_noise": "turnover noise — activity without edge",
    "mixed": "mixed — size down until clarity returns",
}


def evaluate_compounding_priority(
    row: Dict[str, Any],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = context or {}
    action = (row.get("action") or ctx.get("action") or "").upper()
    tb = str(ctx.get("tradeability") or row.get("tradeability") or "").upper()
    deployable = int(ctx.get("deployable_count") or row.get("deployable_count") or 0)
    thesis = float(row.get("thesis_conf") or 0)

    if tb in ("WAIT", "NO_TRADE") or deployable == 0:
        verdict = "compound"
        headline = "Patience compounds — cash and focus are positions"
    elif action in ("TRADE", "PILOT") and thesis >= 0.6:
        verdict = "compound"
        headline = "High-conviction adds compound; avoid adjacent churn"
    elif action in ("WATCH", "WAIT") and thesis < 0.5:
        verdict = "turnover_noise"
        headline = "Watching weak names is turnover noise — cut the list"
    else:
        verdict = "mixed"
        headline = "Mixed — default to less activity until edge is net-positive"

    return {
        "verdict": verdict,
        "headline": headline,
        "label": COMPOUNDING_LABELS[verdict],
    }
