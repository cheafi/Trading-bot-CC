"""
Playbook signal universe — normalize brief rows and merge live scan hits.

Discovery pads a broad universe; Playbook ranked pipeline needs pipeline-ready
signals (score, entry/stop/target). Raw brief JSON without normalization scores
~4.8 and becomes all AVOID — monitor pool collapses to near zero.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from src.utils.numeric_parse import parse_ratio

BRIEF_PIPELINE_SECTIONS: Tuple[str, ...] = (
    "actionable",
    "watch",
    "review",
    "monitor",
    "pilot",
    "near_miss",
    "candidates",
)

# Top up with live scan when brief pool is thin (monitor candidates only).
PLAYBOOK_MIN_SIGNALS_BEFORE_SCAN = 25
PLAYBOOK_SIGNAL_TARGET = 80
PLAYBOOK_LIVE_SCAN_LIMIT = 100


def normalize_brief_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map morning-brief rows to sector_pipeline signal shape."""
    ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
    if not ticker:
        return {}

    rs = float(row.get("rs_score") or row.get("score") or 5.0)
    if rs > 10:
        board_score = min(10.0, max(3.0, rs / 10.0))
    else:
        board_score = min(10.0, max(3.0, rs))

    sig: Dict[str, Any] = {
        "ticker": ticker,
        "score": board_score,
        "rs_score": rs,
        "vol_ratio": float(row.get("vol_ratio") or 1.0),
        "atr_pct": row.get("atr_pct"),
        "near_52w_high": bool(row.get("near_52w_high")),
        "conviction": str(row.get("conviction") or "WATCH").upper(),
        "strategy": str(row.get("strategy") or "brief"),
        "pattern": str(row.get("pattern") or "watchlist"),
        "source": "brief",
    }

    if row.get("sector"):
        sig["sector"] = row.get("sector")

    entry = row.get("entry_price") or row.get("entry") or row.get("price")
    stop = row.get("stop_price") or row.get("stop")
    target = (
        row.get("target_price")
        or row.get("target_2r")
        or row.get("target")
    )
    if entry is not None:
        try:
            entry_f = float(entry)
            sig["entry_price"] = round(entry_f, 2)
        except (TypeError, ValueError):
            entry_f = None
    else:
        entry_f = None

    if stop is not None:
        try:
            stop_f = float(stop)
            sig["stop_price"] = round(stop_f, 2)
        except (TypeError, ValueError):
            stop_f = None
    else:
        stop_f = None

    if target is not None:
        try:
            target_f = float(target)
            sig["target_price"] = round(target_f, 2)
        except (TypeError, ValueError):
            target_f = None
    else:
        target_f = None

    rr = parse_ratio(row.get("risk_reward"), 0.0) or 0.0
    if rr <= 0 and entry_f and stop_f and target_f and entry_f > stop_f:
        risk = entry_f - stop_f
        if risk > 0:
            rr = round((target_f - entry_f) / risk, 1)
    if rr > 0:
        sig["risk_reward"] = rr

    return sig


def load_brief_pipeline_signals(
    brief: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Load brief sections as deduped pipeline signals (higher sections win)."""
    if brief is None:
        from src.services.brief_data_service import load_brief

        brief = load_brief()

    ordered: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for section in BRIEF_PIPELINE_SECTIONS:
        for row in brief.get(section) or []:
            if not isinstance(row, dict):
                continue
            sig = normalize_brief_row(row)
            ticker = sig.get("ticker")
            if not ticker or ticker in seen:
                continue
            sig["brief_section"] = section
            ordered.append(sig)
            seen.add(ticker)
    return ordered


def merge_pipeline_signals(
    primary: List[Dict[str, Any]],
    secondary: List[Dict[str, Any]],
    *,
    target: int = PLAYBOOK_SIGNAL_TARGET,
) -> List[Dict[str, Any]]:
    """Merge signal lists; primary tickers win; cap at target size."""
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for row in primary:
        ticker = str((row or {}).get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        merged.append(row)
        seen.add(ticker)
        if len(merged) >= target:
            return merged

    for row in secondary:
        ticker = str((row or {}).get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        extra = dict(row)
        extra.setdefault("source", "live_scan")
        merged.append(extra)
        seen.add(ticker)
        if len(merged) >= target:
            break
    return merged


ScanFn = Callable[[int], Awaitable[Tuple[List[Dict[str, Any]], Dict[str, Any]]]]


async def load_playbook_signals(
    *,
    scan_fn: Optional[ScanFn] = None,
    scan_limit: int = PLAYBOOK_LIVE_SCAN_LIMIT,
    min_before_scan: int = PLAYBOOK_MIN_SIGNALS_BEFORE_SCAN,
    target: int = PLAYBOOK_SIGNAL_TARGET,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Brief-first playbook universe; optional live scan top-up for monitor pool.

    Does not change deploy authority — only expands ranked/monitor input set.
    """
    meta: Dict[str, Any] = {
        "brief_count": 0,
        "live_scan_count": 0,
        "merged_count": 0,
        "live_scan_used": False,
        "live_scan_degraded": False,
    }

    brief_signals = load_brief_pipeline_signals()
    meta["brief_count"] = len(brief_signals)
    signals = list(brief_signals)

    if len(signals) < min_before_scan and scan_fn is not None:
        try:
            scanned, scan_meta = await scan_fn(scan_limit)
            meta["live_scan_used"] = True
            meta["live_scan_degraded"] = bool(
                (scan_meta or {}).get("_degraded")
            )
            live_rows = [r for r in (scanned or []) if isinstance(r, dict)]
            meta["live_scan_count"] = len(live_rows)
            signals = merge_pipeline_signals(signals, live_rows, target=target)
        except Exception as exc:
            meta["live_scan_error"] = str(exc)[:120]

    meta["merged_count"] = len(signals)
    return signals, meta
