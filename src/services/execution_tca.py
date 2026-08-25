"""
Execution TCA — per-order transaction-cost analysis ledger.

execution_analytics.py already gives an *aggregate* fill-quality summary
(latency band, median slippage, fill rate) at ops_probe authority. This module
adds what it does not have: an **order-level** TCA ledger and the breakdowns a
desk actually reviews —

  - timestamp chain: signal -> order_send -> first_fill -> final_fill
  - time-to-send / time-to-first-fill / time-to-complete (ms)
  - fill ratio, partial-fill flag, cancel/replace count
  - slippage vs arrival price AND vs interval VWAP (signed: + = adverse)
  - implementation shortfall (Perold: execution cost + opportunity cost)
  - effective-spread proxy
  - algo used, venue, order type, handoff success/failure
  - aggregation by ticker / algo / venue / time-bucket / order-type
  - execution-quality trend + an "execution drag" overlay for strategy health

Authority: ops_probe when fed live IBKR fills; research_only/degraded otherwise.
It NEVER authorizes execution or overrides a board WAIT — it is post-trade
context. Missing timestamps/prices degrade gracefully to None, never a guess.

Persistence: append-only JSONL under data/artifacts/execution_tca.jsonl, matching
the Wave-1 ledger pattern. Deterministic and network-free for CI: callers pass
epoch-millisecond timestamps, so no wall-clock dependency.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from src.services.execution_analytics import evaluate_fill_quality
from src.services.signal_provenance import (
    SIGNAL_EXECUTION_ANALYTICS,
    build_provenance_envelope,
)

DEFAULT_TCA_PATH = os.path.join("data", "artifacts", "execution_tca.jsonl")

# Time buckets by US-session minute-of-day (ET); callers pass session_minute.
TIME_BUCKET_OPEN = "open"          # first 30 min
TIME_BUCKET_MIDDAY = "midday"
TIME_BUCKET_CLOSE = "close"        # last 30 min
TIME_BUCKET_UNKNOWN = "unknown"

AGG_DIMENSIONS = ("ticker", "algo", "venue", "time_bucket", "order_type")


def _side_sign(side: str) -> int:
    """+1 for BUY (paying above arrival is adverse), -1 for SELL."""
    return -1 if str(side).upper() in ("SELL", "SHORT", "SELL_SHORT") else 1


def time_bucket(session_minute: Optional[int]) -> str:
    """Map minute-of-session to a coarse bucket. None -> unknown."""
    if session_minute is None:
        return TIME_BUCKET_UNKNOWN
    try:
        m = int(session_minute)
    except (TypeError, ValueError):
        return TIME_BUCKET_UNKNOWN
    if m < 30:
        return TIME_BUCKET_OPEN
    if m >= 360:  # 6h after open ~ last 30 min of a 6.5h session
        return TIME_BUCKET_CLOSE
    return TIME_BUCKET_MIDDAY


def _bps(numer: float, denom: float) -> Optional[float]:
    if not denom:
        return None
    return round(numer / denom * 10000.0, 1)


def compute_order_tca(order: Dict[str, Any]) -> Dict[str, Any]:
    """Compute per-order TCA metrics. Missing inputs -> None (degraded), not guessed.

    Expected order keys (all optional except side/order_qty):
      ticker, side, algo, venue, order_type, session_minute,
      order_qty, filled_qty, arrival_price, avg_fill_price, interval_vwap,
      midpoint_price, ref_end_price, cancel_replace_count,
      ts_signal, ts_send, ts_first_fill, ts_final_fill   (epoch ms)
    """
    side = order.get("side", "BUY")
    sign = _side_sign(side)
    order_qty = float(order.get("order_qty") or 0)
    filled_qty = float(order.get("filled_qty") or 0)
    arrival = order.get("arrival_price")
    avg_fill = order.get("avg_fill_price")
    vwap = order.get("interval_vwap")
    midpoint = order.get("midpoint_price")
    ref_end = order.get("ref_end_price")

    fill_ratio = round(filled_qty / order_qty, 4) if order_qty > 0 else None
    partial = bool(fill_ratio is not None and 0 < fill_ratio < 1)

    # Signed slippage: positive = adverse (worse) for both sides.
    slip_arrival = None
    if arrival and avg_fill:
        slip_arrival = _bps(sign * (float(avg_fill) - float(arrival)), float(arrival))
    slip_vwap = None
    if vwap and avg_fill:
        slip_vwap = _bps(sign * (float(avg_fill) - float(vwap)), float(vwap))

    # Effective-spread proxy: 2*|fill - mid| / mid (bps). Falls back to None.
    eff_spread = None
    if midpoint and avg_fill:
        eff_spread = _bps(2 * abs(float(avg_fill) - float(midpoint)), float(midpoint))
    elif order.get("spread_bps") is not None:
        eff_spread = round(float(order["spread_bps"]), 1)

    # Implementation shortfall (Perold): exec cost on filled + opp cost on unfilled.
    is_bps = None
    is_complete = False
    if arrival and avg_fill and fill_ratio is not None:
        exec_cost = sign * (float(avg_fill) - float(arrival)) / float(arrival)
        if ref_end:
            opp_cost = sign * (float(ref_end) - float(arrival)) / float(arrival)
            is_complete = True
        else:
            opp_cost = 0.0  # no reference close — opportunity cost unknown
        is_bps = round(
            (fill_ratio * exec_cost + (1 - fill_ratio) * opp_cost) * 10000.0, 1
        )

    # Latency chain (ms).
    def _delta(a: str, b: str) -> Optional[int]:
        ta, tb = order.get(a), order.get(b)
        if ta is None or tb is None:
            return None
        return int(tb) - int(ta)

    latency = {
        "time_to_send_ms": _delta("ts_signal", "ts_send"),
        "time_to_first_fill_ms": _delta("ts_send", "ts_first_fill"),
        "time_to_complete_ms": _delta("ts_send", "ts_final_fill"),
    }

    handoff_ok = bool(order.get("handoff_ok", filled_qty > 0))
    status = evaluate_fill_quality(
        slippage_bps=abs(slip_arrival) if slip_arrival is not None else 0.0,
        fill_rate_pct=(fill_ratio * 100) if fill_ratio is not None else 0.0,
        partial_fill_pct=100.0 if partial else 0.0,
    )
    degraded = arrival is None or avg_fill is None or fill_ratio is None

    return {
        "ticker": str(order.get("ticker", "")).upper(),
        "side": str(side).upper(),
        "algo": order.get("algo", "unknown"),
        "venue": order.get("venue", "unknown"),
        "order_type": order.get("order_type", "unknown"),
        "time_bucket": time_bucket(order.get("session_minute")),
        "fill_ratio": fill_ratio,
        "partial_fill": partial,
        "cancel_replace_count": int(order.get("cancel_replace_count") or 0),
        "slippage_vs_arrival_bps": slip_arrival,
        "slippage_vs_vwap_bps": slip_vwap,
        "effective_spread_bps": eff_spread,
        "implementation_shortfall_bps": is_bps,
        "is_complete": is_complete,
        "latency": latency,
        "handoff_ok": handoff_ok,
        "fill_quality_status": status,
        "degraded": degraded,
        "authorizes_execution": False,
    }


def _mean(vals: List[float]) -> Optional[float]:
    clean = [v for v in vals if v is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def aggregate_tca(orders: List[Dict[str, Any]], by: str = "ticker") -> Dict[str, Any]:
    """Aggregate computed order-TCA rows by a dimension."""
    if by not in AGG_DIMENSIONS:
        by = "ticker"
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for o in orders:
        groups.setdefault(str(o.get(by, "unknown")), []).append(o)
    rows: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        rows.append(
            {
                by: key,
                "n_orders": len(items),
                "mean_is_bps": _mean([i.get("implementation_shortfall_bps") for i in items]),
                "mean_arrival_slip_bps": _mean([i.get("slippage_vs_arrival_bps") for i in items]),
                "mean_vwap_slip_bps": _mean([i.get("slippage_vs_vwap_bps") for i in items]),
                "mean_fill_ratio": _mean([i.get("fill_ratio") for i in items]),
                "handoff_success_rate": round(
                    sum(1 for i in items if i.get("handoff_ok")) / len(items), 3
                ),
                "cancel_replace_total": sum(int(i.get("cancel_replace_count") or 0) for i in items),
            }
        )
    rows.sort(key=lambda r: r["n_orders"], reverse=True)
    return {"dimension": by, "groups": rows}


def execution_quality_trend(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """First-half vs second-half mean IS — improving / stable / deteriorating."""
    series = [o.get("implementation_shortfall_bps") for o in orders if o.get("implementation_shortfall_bps") is not None]
    if len(series) < 4:
        return {"trend": "insufficient_sample", "n": len(series)}
    mid = len(series) // 2
    early, late = _mean(series[:mid]), _mean(series[mid:])
    if early is None or late is None:
        return {"trend": "insufficient_sample", "n": len(series)}
    # Lower IS cost is better; rising cost = deteriorating.
    if late > early + 3:
        trend = "deteriorating"
    elif late < early - 3:
        trend = "improving"
    else:
        trend = "stable"
    return {"trend": trend, "early_mean_is_bps": early, "late_mean_is_bps": late, "n": len(series)}


def execution_drag_overlay(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact 'execution drag' figure for strategy-health surfaces (downgrade-only)."""
    mean_is = _mean([o.get("implementation_shortfall_bps") for o in orders])
    if mean_is is None:
        return {"drag_bps": None, "label": "Execution drag unknown — no fill sample", "degraded": True}
    if mean_is > 20:
        label = "Execution drag heavy — edge eroded by fills"
    elif mean_is > 8:
        label = "Execution drag moderate — watch sizing/urgency"
    else:
        label = "Execution drag light — fills near arrival"
    return {"drag_bps": mean_is, "label": label, "degraded": False, "downgrade_only": True}


class ExecutionTcaLedger:
    """Append-only JSONL store of computed order-TCA rows."""

    def __init__(self, path: str = DEFAULT_TCA_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    def record_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        row = compute_order_tca(order)
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        return row

    def orders(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        out: List[Dict[str, Any]] = []
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out


def build_execution_tca_context(
    orders: Optional[List[Dict[str, Any]]] = None,
    *,
    ibkr_connected: bool = False,
    report_dimension: str = "algo",
) -> Dict[str, Any]:
    """Research/ops-only TCA payload wrapped in the provenance envelope.

    Authority: ops_probe when fed live fills + connected; research_only and
    degraded otherwise. Never authorizes execution (deploy_from_signal_alone=False).
    """
    computed = [compute_order_tca(o) if "fill_ratio" not in o else o for o in (orders or [])]
    degraded = not computed or not ibkr_connected
    body = {
        "orders_sampled": len(computed),
        "report_by_algo": aggregate_tca(computed, by="algo"),
        "report_by_ticker": aggregate_tca(computed, by="ticker"),
        "report_custom": aggregate_tca(computed, by=report_dimension),
        "handoff_by_venue": aggregate_tca(computed, by="venue"),
        "handoff_by_time_bucket": aggregate_tca(computed, by="time_bucket"),
        "quality_trend": execution_quality_trend(computed),
        "execution_drag": execution_drag_overlay(computed),
        "ibkr_connected": ibkr_connected,
        "authorizes_execution": False,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_EXECUTION_ANALYTICS,
        source="execution_tca" if computed else "execution_tca-empty",
        degraded=degraded,
        data_mode="ops_probe" if (ibkr_connected and computed) else "research_only",
        extra=body,
    )
