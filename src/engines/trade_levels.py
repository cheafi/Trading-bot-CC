"""
src/engines/trade_levels.py — Deterministic trade plan from OHLCV
==================================================================

Produces the numbers a trade decision card shows: support / resistance,
entry reference, stop, targets and reward-to-risk. Every level carries the
method that produced it so the operator can see *why* a price is on the chart.

Design rules
------------
* **Deterministic.** Same bars in, same plan out. No LLM input.
* **Nothing is invented.** Levels are derived from supplied bars. Missing or
  malformed bars yield an explicit non-OK status with no levels, never a
  percentage-of-price placeholder.
* **A plan is not an order.** ``entry`` is a reference price (the last close
  unless the operator overrides it). The stop is a suggestion and is never
  submitted to a broker by this module.
* **Overrides recalculate, they do not execute.** Operator-supplied entry,
  stop or targets replace the computed ones and the risk numbers are
  recomputed; nothing else happens.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from src.core.price_validation import validate_price, validate_stop_placement
from src.engines.strategy_evidence import EvidenceGrade

__all__ = [
    "MIN_BARS",
    "PriceLevel",
    "atr",
    "classify_setup_action",
    "compute_trade_plan",
    "detect_support_resistance",
]

MIN_BARS = 30
ATR_PERIOD = 14
PIVOT_WINDOW = 3
SR_LOOKBACK = 120
CLUSTER_ATR_MULT = 0.5
STOP_BUFFER_ATR = 0.25
FALLBACK_STOP_ATR = 2.0
MIN_RR_FOR_SETUP = 2.0
MAX_LEVELS_PER_SIDE = 3

STOP_NOTE = "Suggested stop — not submitted to broker."


@dataclass(frozen=True)
class PriceLevel:
    price: float
    kind: str  # "support" | "resistance"
    touches: int
    bars_since_touch: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "price": round(self.price, 4),
            "kind": self.kind,
            "touches": self.touches,
            "bars_since_touch": self.bars_since_touch,
        }


def _finite_positive(values: Sequence[Any]) -> bool:
    return all(validate_price(v)[0] for v in values)


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = ATR_PERIOD,
) -> float | None:
    """Wilder ATR. ``None`` when there are not enough bars."""
    n = len(closes)
    if n < period + 1:
        return None
    trs = []
    for i in range(1, n):
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    value = sum(trs[:period]) / period
    for tr in trs[period:]:
        value = (value * (period - 1) + tr) / period
    return value


def _pivots(
    values: Sequence[float], window: int, *, high: bool
) -> list[tuple[int, float]]:
    out = []
    for i in range(window, len(values) - window):
        v = values[i]
        neighbours = list(values[i - window : i]) + list(values[i + 1 : i + window + 1])
        if high and all(v > x for x in neighbours):
            out.append((i, v))
        elif not high and all(v < x for x in neighbours):
            out.append((i, v))
    return out


def _cluster(
    pivots: list[tuple[int, float]], tolerance: float, last_index: int
) -> list[tuple[float, int, int]]:
    """Group pivots within ``tolerance`` of each other.

    Returns ``(mean_price, touches, bars_since_last_touch)`` per cluster.
    """
    if not pivots:
        return []
    ordered = sorted(pivots, key=lambda p: p[1])
    clusters: list[list[tuple[int, float]]] = [[ordered[0]]]
    for idx, px in ordered[1:]:
        if px - clusters[-1][-1][1] <= tolerance:
            clusters[-1].append((idx, px))
        else:
            clusters.append([(idx, px)])
    result = []
    for c in clusters:
        mean_px = sum(p for _, p in c) / len(c)
        latest = max(i for i, _ in c)
        result.append((mean_px, len(c), last_index - latest))
    return result


def detect_support_resistance(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    reference_price: float | None = None,
    lookback: int = SR_LOOKBACK,
    pivot_window: int = PIVOT_WINDOW,
    max_levels: int = MAX_LEVELS_PER_SIDE,
) -> tuple[list[PriceLevel], list[PriceLevel]]:
    """Swing-pivot support/resistance, clustered by ATR-scaled tolerance.

    Supports are returned nearest-first below ``reference_price`` and
    resistances nearest-first above it. Empty lists mean no structure was
    found — callers must not substitute a placeholder level.
    """
    n = len(closes)
    if n < MIN_BARS:
        return [], []
    start = max(0, n - lookback)
    h, lo, c = list(highs[start:]), list(lows[start:]), list(closes[start:])
    a = atr(h, lo, c)
    if a is None or a <= 0:
        return [], []
    ref = closes[-1] if reference_price is None else reference_price
    tol = a * CLUSTER_ATR_MULT
    last = len(c) - 1

    raw_res = _cluster(_pivots(h, pivot_window, high=True), tol, last)
    raw_sup = _cluster(_pivots(lo, pivot_window, high=False), tol, last)
    # A swing high below price has become support, and vice versa, so both
    # pivot families feed both sides.
    levels = [(p, t, b) for p, t, b in raw_res + raw_sup]

    supports = sorted(
        (PriceLevel(p, "support", t, b) for p, t, b in levels if p < ref),
        key=lambda lv: ref - lv.price,
    )
    resistances = sorted(
        (PriceLevel(p, "resistance", t, b) for p, t, b in levels if p > ref),
        key=lambda lv: lv.price - ref,
    )
    return _dedupe(supports, tol)[:max_levels], _dedupe(resistances, tol)[:max_levels]


def _dedupe(levels: list[PriceLevel], tol: float) -> list[PriceLevel]:
    out: list[PriceLevel] = []
    for lv in levels:
        if any(abs(lv.price - kept.price) <= tol for kept in out):
            continue
        out.append(lv)
    return out


def _level(price: float | None, method: str) -> dict[str, Any] | None:
    if price is None:
        return None
    return {"price": round(price, 4), "method": method}


def compute_trade_plan(
    bars: Sequence[dict[str, Any]],
    *,
    direction: str = "long",
    entry: float | None = None,
    stop: float | None = None,
    targets: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Build a deterministic plan from daily bars.

    ``bars`` are dicts with ``high``, ``low``, ``close`` and optionally
    ``time``. ``entry`` / ``stop`` / ``targets`` are operator overrides.
    """
    direction = "short" if str(direction).lower() == "short" else "long"
    base: dict[str, Any] = {
        "direction": direction,
        "status": "OK",
        "reason_codes": [],
        "as_of": None,
        "last_close": None,
        "atr": None,
        "support": [],
        "resistance": [],
        "entry": None,
        "stop": None,
        "targets": [],
        "risk_per_share": None,
        "reward_risk": None,
        "overrides": {
            "entry": entry is not None,
            "stop": stop is not None,
            "targets": bool(targets),
        },
        "stop_note": STOP_NOTE,
    }

    if len(bars) < MIN_BARS:
        base["status"] = "INSUFFICIENT_HISTORY"
        base["reason_codes"] = [f"BARS_BELOW_{MIN_BARS}"]
        return base
    try:
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]
        closes = [float(b["close"]) for b in bars]
    except (KeyError, TypeError, ValueError):
        base["status"] = "INVALID_DATA"
        base["reason_codes"] = ["BAR_FIELDS_MISSING"]
        return base
    if not (_finite_positive(highs) and _finite_positive(lows) and _finite_positive(closes)):
        base["status"] = "INVALID_DATA"
        base["reason_codes"] = ["BAR_PRICE_INVALID"]
        return base

    base["as_of"] = bars[-1].get("time")
    last_close = closes[-1]
    a = atr(highs, lows, closes)
    base["last_close"] = round(last_close, 4)
    base["atr"] = round(a, 4) if a is not None else None
    if a is None or a <= 0:
        base["status"] = "INSUFFICIENT_HISTORY"
        base["reason_codes"] = ["ATR_UNAVAILABLE"]
        return base

    for name, value in (("ENTRY", entry), ("STOP", stop)):
        if value is not None and not validate_price(value)[0]:
            base["status"] = "INVALID_OVERRIDE"
            base["reason_codes"] = [f"{name}_{validate_price(value)[1]}"]
            return base
    clean_targets = [float(t) for t in (targets or []) if validate_price(t)[0]]
    if targets and len(clean_targets) != len(list(targets)):
        base["status"] = "INVALID_OVERRIDE"
        base["reason_codes"] = ["TARGET_PRICE_INVALID"]
        return base

    entry_px = float(entry) if entry is not None else last_close
    entry_method = "USER" if entry is not None else "LAST_CLOSE"
    supports, resistances = detect_support_resistance(
        highs, lows, closes, reference_price=entry_px
    )
    base["support"] = [lv.to_dict() for lv in supports]
    base["resistance"] = [lv.to_dict() for lv in resistances]
    base["entry"] = _level(entry_px, entry_method)

    long = direction == "long"
    protective = supports if long else resistances
    objectives = resistances if long else supports
    sign = 1 if long else -1

    if stop is not None:
        stop_px, stop_method = float(stop), "USER"
    elif protective:
        stop_px = protective[0].price - sign * STOP_BUFFER_ATR * a
        stop_method = f"{'SUPPORT' if long else 'RESISTANCE'}_BUFFER_{STOP_BUFFER_ATR}ATR"
    else:
        stop_px = entry_px - sign * FALLBACK_STOP_ATR * a
        stop_method = f"ATR_{FALLBACK_STOP_ATR}X"
    base["stop"] = _level(stop_px, stop_method)

    ok, code = validate_stop_placement(
        entry_price=entry_px, stop_price=stop_px, direction=direction
    )
    if not ok or stop_px <= 0:
        base["status"] = "INVALID_STOP"
        base["reason_codes"] = [code if not ok else "STOP_PRICE_NON_POSITIVE"]
        return base

    risk = abs(entry_px - stop_px)
    base["risk_per_share"] = round(risk, 4)

    if clean_targets:
        tgt = [(t, "USER") for t in clean_targets]
    else:
        tgt = [(lv.price, "STRUCTURE") for lv in objectives[:2]]
        if not tgt:
            tgt = [(entry_px + sign * MIN_RR_FOR_SETUP * risk, f"{MIN_RR_FOR_SETUP:g}R_PROJECTION")]

    targets_out = []
    for px, method in tgt:
        reward = (px - entry_px) * sign
        targets_out.append(
            {
                "price": round(px, 4),
                "method": method,
                "reward_risk": round(reward / risk, 2) if risk > 0 else None,
            }
        )
    base["targets"] = targets_out
    first_rr = targets_out[0]["reward_risk"] if targets_out else None
    base["reward_risk"] = first_rr
    if first_rr is None or first_rr <= 0:
        base["status"] = "INVALID_TARGET"
        base["reason_codes"] = ["TARGET_WRONG_SIDE"]
    return base


def classify_setup_action(
    plan: dict[str, Any],
    *,
    evidence_grade: EvidenceGrade | str | None,
    regime_allowed: bool | None,
) -> dict[str, Any]:
    """Map a plan + evidence + regime to BUY SETUP / WAIT / WATCH / NO TRADE.

    ``BUY SETUP`` is a proposal for review, never an order. Only a VALIDATED
    evidence grade can produce it; AI or score inputs are deliberately not
    accepted here.
    """
    try:
        grade = EvidenceGrade(evidence_grade) if evidence_grade else EvidenceGrade.NO_BACKTEST
    except ValueError:
        grade = EvidenceGrade.NO_BACKTEST
    reasons: list[str] = []

    if plan.get("status") != "OK":
        return {"action": "NO TRADE", "reasons": [plan.get("status", "NO_PLAN")]}
    if regime_allowed is False:
        return {"action": "NO TRADE", "reasons": ["REGIME_BLOCKED"]}

    rr = plan.get("reward_risk")
    if regime_allowed is None:
        reasons.append("REGIME_UNVERIFIED")
    if rr is None or not math.isfinite(rr) or rr < MIN_RR_FOR_SETUP:
        reasons.append(f"RR_BELOW_{MIN_RR_FOR_SETUP:g}")
    if reasons:
        return {"action": "WAIT", "reasons": reasons}
    if not grade.is_actionable:
        return {"action": "WATCH", "reasons": [f"EVIDENCE_{grade.value}"]}
    label = "BUY SETUP" if plan.get("direction") != "short" else "SHORT SETUP"
    return {"action": label, "reasons": ["REQUIRES_OPERATOR_APPROVAL"]}
