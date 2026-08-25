"""
《海龟交易法则》trend-following mode — rules over discretion.

Breakout + ATR risk + pyramiding discipline; losses cut, winners run.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.utils.numeric_parse import coerce_float

TURTLE_LABELS: Dict[str, str] = {
    "no_breakout": "no Donchian breakout — no entry",
    "breakout_weak_volume": "breakout without volume confirmation",
    "atr_stop_required": "ATR stop required — no stop = no trade",
    "unit_size_capped": "unit size capped by N and heat",
    "pyramid_not_allowed": "add unit blocked — max units or heat",
    "trend_aligned": "trend aligned — turtle entry candidate",
    "exit_trailing": "trailing / channel exit — honor system",
}

SYSTEM_N_DEFAULT = 20
MAX_UNITS = 4


def _atr_proxy(row: Dict[str, Any]) -> float:
    struct = row.get("structure") or {}
    return coerce_float(struct.get("atr_pct") or row.get("atr_pct"), 2.5)


def evaluate_turtle_setup(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Heuristic turtle posture from structure + trend fields."""
    struct = row.get("structure") or {}
    above20 = bool(struct.get("above_sma20") or row.get("above_sma20"))
    above50 = bool(struct.get("above_sma50") or row.get("above_sma50"))
    vol_ratio = coerce_float(struct.get("volume_ratio") or row.get("volume_ratio"), 1.0)
    stop = row.get("stop") or row.get("stop_price")
    tb = (tradeability or "").upper()

    labels: List[str] = []
    breakout = above20 and above50 and vol_ratio >= 1.1
    if not breakout:
        labels.append(TURTLE_LABELS["no_breakout"])
    elif vol_ratio < 1.25:
        labels.append(TURTLE_LABELS["breakout_weak_volume"])
    else:
        labels.append(TURTLE_LABELS["trend_aligned"])

    if not stop:
        labels.append(TURTLE_LABELS["atr_stop_required"])

    n_atr = _atr_proxy(row)
    units_allowed = MAX_UNITS if breakout and stop else 0
    if units_allowed < 1:
        labels.append(TURTLE_LABELS["unit_size_capped"])

    entry_ok = breakout and stop and tb in ("TRADE", "SELECTIVE", "STRONG_TRADE")

    return {
        "mode": "turtle",
        "system_n": SYSTEM_N_DEFAULT,
        "atr_pct_proxy": round(n_atr, 2),
        "max_units": MAX_UNITS,
        "units_allowed": units_allowed,
        "labels": labels,
        "entry_ok": entry_ok,
        "headline": labels[-1] if labels else TURTLE_LABELS["no_breakout"],
        "authority": "pilot_only" if entry_ok else "research_only",
        "model_note": "Donchian/ATR heuristics — full OHLC channel engine deferred",
    }


def tags_for_playbook_row(
    row: Dict[str, Any], *, tradeability: str = ""
) -> Dict[str, Any]:
    t = evaluate_turtle_setup(row, tradeability=tradeability)
    return {
        "turtle_tag": t["headline"],
        "turtle_entry_ok": t["entry_ok"],
        "turtle_labels": t["labels"],
        "turtle_units_allowed": t["units_allowed"],
    }
