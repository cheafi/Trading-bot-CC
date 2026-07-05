"""Parse numeric values and risk-reward ratio strings safely."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

_RATIO_SEP = re.compile(r"[:/]")
_NUMERIC = re.compile(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$")


def parse_numeric(value: Any, default: float = 0.0) -> float:
    """Coerce ints/floats/numeric strings; return default on failure."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return default
    if _NUMERIC.match(text):
        try:
            return float(text)
        except (TypeError, ValueError):
            return default
    parsed = parse_ratio(text, default=None)
    return parsed if parsed is not None else default


def parse_ratio(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """
    Parse risk-reward values.

    Accepts:
    - numeric (2.0, "2.5")
    - colon ratios ("1:2" → 2.0 reward per 1 risk)
    - slash ratios ("1/2" → 0.5)
    """
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return default

    if _NUMERIC.match(text):
        try:
            return float(text)
        except (TypeError, ValueError):
            return default

    if ":" in text:
        parts = [p.strip() for p in text.split(":") if p.strip()]
    elif "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
    else:
        parts = []

    if len(parts) == 2:
        try:
            left = float(parts[0])
            right = float(parts[1])
        except (TypeError, ValueError):
            return default
        if left <= 0 or right <= 0:
            return default
        if ":" in text:
            # "1:2" → 1 unit risk for 2 reward → RR = 2.0
            return round(right / left, 2)
        # "1/2" → fractional RR value
        return round(left / right, 2)

    return default


def coerce_float(value: Any, default: float = 0.0) -> float:
    """Never raise on ratio strings — alias for parse_numeric."""
    return parse_numeric(value, default)


def normalize_trade_plan(trade_plan: Any) -> Dict[str, Any]:
    """
    Ensure trade_plan R:R fields are numeric.

    live_dossier exposes rr_ratio (float) and rr_ratio_label (e.g. "1:2").
    Downstream code must not call float() on the label string.
    """
    if not isinstance(trade_plan, dict):
        return {}
    tp = dict(trade_plan)
    raw = tp.get("rr_ratio")
    if raw is None and tp.get("rr_ratio_label"):
        raw = tp.get("rr_ratio_label")
    parsed = parse_ratio(raw, default=None)
    if parsed is not None and parsed > 0:
        tp["rr_ratio"] = parsed
    elif isinstance(raw, str) and ":" in str(raw):
        tp.pop("rr_ratio", None)
    return tp
