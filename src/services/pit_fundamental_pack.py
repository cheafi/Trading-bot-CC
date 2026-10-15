"""Point-in-time fundamental context (research — price PIT + disclosure-lagged fundamentals)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.research_safety import sanitize_research_payload

logger = logging.getLogger(__name__)

_FILING_LAG_DAYS = 45


def _parse_as_of(as_of: str) -> Optional[datetime]:
    try:
        return datetime.strptime(str(as_of)[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _yf_fundamental_snapshot(symbol: str, as_of_dt: datetime) -> Dict[str, Any]:
    """Best-effort quarterly fundamentals visible as of as_of (publication lag applied)."""
    try:
        import yfinance as yf
    except ImportError:
        return {"source": "unavailable", "reason": "yfinance_missing"}

    lag_cutoff = (as_of_dt - timedelta(days=_FILING_LAG_DAYS)).date()
    try:
        t = yf.Ticker(symbol)
        qfin = getattr(t, "quarterly_financials", None)
        if qfin is None or getattr(qfin, "empty", True):
            info = t.info or {}
            return {
                "source": "yfinance_info",
                "as_of_visible": str(lag_cutoff),
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "market_cap": info.get("marketCap"),
                "sector": info.get("sector"),
                "note": "Info snapshot; quarterly table empty — treat as provisional.",
            }
        cols = list(qfin.columns)
        picked = None
        for col in cols:
            try:
                col_dt = col.date() if hasattr(col, "date") else col
                if col_dt <= lag_cutoff:
                    picked = col
            except Exception:
                continue
        if picked is None and cols:
            picked = cols[-1]
        row: Dict[str, Any] = {
            "source": "yfinance_quarterly",
            "as_of_visible": str(lag_cutoff),
            "report_period": str(picked)[:10] if picked is not None else None,
        }
        if picked is not None:
            try:
                total_rev = qfin.loc["Total Revenue", picked]
                net_inc = qfin.loc["Net Income", picked]
                row["total_revenue"] = float(total_rev) if total_rev == total_rev else None
                row["net_income"] = float(net_inc) if net_inc == net_inc else None
            except Exception:
                pass
        return row
    except Exception as exc:
        logger.debug("PIT yfinance failed for %s: %s", symbol, exc)
        return {"source": "error", "reason": type(exc).__name__}


def build_pit_fundamental_context(
    symbols: List[str],
    *,
    as_of: Optional[str],
) -> Dict[str, Any]:
    """Attach PIT price posture + lagged fundamental snapshots (research only)."""
    if not as_of:
        return sanitize_research_payload(
            {
                "ok": False,
                "applied": False,
                "reason": "no_as_of",
                "authority": "research_only",
            }
        )
    as_of_dt = _parse_as_of(as_of)
    rows = []
    for sym in symbols[:8]:
        s = str(sym or "").upper().strip()
        if not s:
            continue
        fund = _yf_fundamental_snapshot(s, as_of_dt) if as_of_dt else {}
        rows.append(
            {
                "ticker": s,
                "price_pit": True,
                "fundamental_pit": "yfinance_lagged" if fund.get("source") else "partial",
                "disclosure_lag_days": _FILING_LAG_DAYS,
                "fundamentals": fund,
                "note": (
                    f"Price bars truncated through {as_of[:10]}; "
                    f"fundamentals use reports on/before "
                    f"{as_of[:10]} minus {_FILING_LAG_DAYS}d lag."
                ),
            }
        )
    return sanitize_research_payload(
        {
            "ok": True,
            "applied": True,
            "as_of": str(as_of)[:10],
            "symbols": [r["ticker"] for r in rows],
            "rows": rows,
            "authority": "research_only",
            "execution_permission": False,
        }
    )
