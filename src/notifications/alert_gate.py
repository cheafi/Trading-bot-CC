"""Validated-only gate for outbound trade-signal alerts.

A setup is pushed to a channel only when its strategy's evidence grade is
VALIDATED. Unknown strategy, missing evidence or any lookup error withholds
the alert. Informational messages (risk, exits, reports) are not gated here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

ALERTABLE_GRADE = "VALIDATED"


def strategy_of(signal: Any, default: Optional[str] = None) -> Optional[str]:
    for key in ("strategy_id", "strategy"):
        val = (
            signal.get(key) if isinstance(signal, dict) else getattr(signal, key, None)
        )
        if isinstance(val, str) and val.strip():
            return val.strip()
    return default


def _grade(strategy_id: Optional[str], cache: Dict[Optional[str], str]) -> str:
    if strategy_id not in cache:
        grade = "NO_BACKTEST"
        if strategy_id:
            try:
                from src.services.strategy_health_service import evidence_for_strategy

                grade = str(evidence_for_strategy(strategy_id).get("grade") or grade)
            except Exception as exc:
                logger.warning("alert gate: evidence lookup failed: %s", exc)
                grade = "UNAVAILABLE"
        cache[strategy_id] = grade
    return cache[strategy_id]


def filter_validated(
    signals: Iterable[Any], default_strategy: Optional[str] = None
) -> Tuple[List[Any], Dict[str, int]]:
    """Split signals into (alertable, withheld-count-by-grade)."""
    cache: Dict[Optional[str], str] = {}
    keep: List[Any] = []
    withheld: Dict[str, int] = {}
    for sig in signals or []:
        grade = _grade(strategy_of(sig, default_strategy), cache)
        if grade == ALERTABLE_GRADE:
            keep.append(sig)
        else:
            withheld[grade] = withheld.get(grade, 0) + 1
    if withheld:
        logger.info("alert gate withheld %s", withheld)
    return keep, withheld


def withheld_note(withheld: Dict[str, int]) -> str:
    n = sum(withheld.values())
    detail = ", ".join(f"{g} {c}" for g, c in sorted(withheld.items()))
    return f"{n} setup(s) withheld — strategy evidence not VALIDATED ({detail})"
