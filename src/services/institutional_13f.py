"""
Institutional 13F sponsorship — quarterly lag, crowdedness hints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_INSTITUTIONAL_13F,
    build_provenance_envelope,
)

CHANGE_NEW_POSITION = "new_position"
CHANGE_ADDED = "added"
CHANGE_REDUCED = "reduced"
CHANGE_EXITED = "exited"
CHANGE_UNCHANGED = "unchanged"

LAG_LABEL_STANDARD = "standard_quarterly_lag"
LAG_LABEL_AMENDED = "amended_filing_lag"
LAG_LABEL_STALE = "stale_vs_price"

CROWDEDNESS_LOW = "low_sponsorship"
CROWDEDNESS_MODERATE = "moderate_crowded"
CROWDEDNESS_HIGH = "high_crowded"


def classify_13f_change(
    *,
    shares_prev: float,
    shares_curr: float,
    value_curr_usd: float,
) -> str:
    if shares_prev <= 0 and shares_curr > 0:
        return CHANGE_NEW_POSITION
    if shares_curr <= 0 and shares_prev > 0:
        return CHANGE_EXITED
    if shares_curr > shares_prev * 1.05:
        return CHANGE_ADDED
    if shares_curr < shares_prev * 0.95:
        return CHANGE_REDUCED
    return CHANGE_UNCHANGED


def crowdedness_hint(
    *,
    holder_count: int,
    top10_pct_float: float,
) -> str:
    if holder_count < 5 or top10_pct_float < 0.08:
        return CROWDEDNESS_LOW
    if top10_pct_float >= 0.25:
        return CROWDEDNESS_HIGH
    return CROWDEDNESS_MODERATE


def _mock_holders(ticker: str) -> List[Dict[str, Any]]:
    sym = ticker.upper()
    return [
        {
            "filer": "Illustrative Growth Fund",
            "change_type": CHANGE_ADDED,
            "shares_prev": 1_200_000,
            "shares_curr": 1_450_000,
            "value_curr_usd": 285_000_000,
            "report_period": "2025-Q4",
            "filed_lag_days": 52,
        },
        {
            "filer": "Illustrative Index Tracker",
            "change_type": CHANGE_UNCHANGED,
            "shares_prev": 8_000_000,
            "shares_curr": 8_050_000,
            "value_curr_usd": 1_580_000_000,
            "report_period": "2025-Q4",
            "filed_lag_days": 48,
        },
    ]


def build_institutional_context(
    ticker: str,
    *,
    degraded: bool = False,
) -> Dict[str, Any]:
    sym = ticker.upper().strip()
    now = datetime.now(timezone.utc).isoformat()
    holders = _mock_holders(sym)
    top10_pct = 0.18
    hint = crowdedness_hint(holder_count=len(holders), top10_pct_float=top10_pct)

    body = {
        "ticker": sym,
        "holders": holders,
        "lag_label": LAG_LABEL_STANDARD,
        "lag_copy": "13F reflects prior quarter — not real-time positioning",
        "crowdedness": hint,
        "top10_pct_float_est": top10_pct,
        "sponsorship_verdict": (
            "Added sponsorship (lagged)"
            if any(h["change_type"] == CHANGE_ADDED for h in holders)
            else "Mixed / unchanged (lagged)"
        ),
        "data_tier": "mock",
        "monitor_trigger_type": "13f_sponsorship",
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_INSTITUTIONAL_13F,
        source="mock-13f-stub",
        as_of=now,
        degraded=degraded or True,
        extra=body,
    )
