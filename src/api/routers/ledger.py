"""
Trade Ledger Writer
====================
Appends a single closed-trade row to data/closed_trades.jsonl.
Triggered by frontend when a bracket reaches terminal state (parent filled +
one OCA child filled), or via manual POST.

Row schema matches existing ledger consumers (StrategyHealthService et al.):
  ticker, direction, entry_price, exit_price,
  entry_time, exit_time, strategy_id, pnl_pct, r_multiple,
  regime_at_entry, setup_grade, hold_days, source
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.deps import optional_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

LEDGER_PATH = os.path.join("data", "closed_trades.jsonl")


class CloseTradeRequest(BaseModel):
    ticker: str
    direction: str = "LONG"  # LONG | SHORT
    entry_price: float
    exit_price: float
    shares: float = 1.0
    entry_time: str = ""  # ISO; defaults to now if blank
    exit_time: str = ""
    strategy_id: str = "manual"
    stop_price: float = 0.0  # used to compute R-multiple
    regime_at_entry: str = ""
    setup_grade: str = ""
    source: str = "ibkr_bracket"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post("/api/ledger/close-trade", tags=["ledger"])
async def ledger_close_trade(
    req: CloseTradeRequest, request: Request, _=optional_api_key
):
    """Append a single closed trade row to closed_trades.jsonl."""
    entry = req.entry_time or _utc_now_iso()
    exit_t = req.exit_time or _utc_now_iso()
    direction = req.direction.upper() if req.direction else "LONG"
    sign = 1 if direction == "LONG" else -1
    # pnl pct from entry
    pnl_pct = (
        round((req.exit_price - req.entry_price) / req.entry_price * 100 * sign, 3)
        if req.entry_price > 0
        else 0.0
    )
    # R-multiple if stop was supplied
    r_multiple = None
    if req.stop_price > 0 and req.entry_price > 0:
        risk_per_share = abs(req.entry_price - req.stop_price)
        if risk_per_share > 1e-9:
            r_multiple = round(
                (req.exit_price - req.entry_price) * sign / risk_per_share, 3
            )
    # hold days
    hold_days = None
    try:
        dt_in = datetime.fromisoformat(entry.replace("Z", "+00:00"))
        dt_out = datetime.fromisoformat(exit_t.replace("Z", "+00:00"))
        hold_days = round((dt_out - dt_in).total_seconds() / 86400.0, 3)
    except Exception:
        pass

    row: Dict[str, Any] = {
        "ticker": req.ticker.upper().strip(),
        "direction": direction,
        "entry_price": float(req.entry_price),
        "exit_price": float(req.exit_price),
        "shares": float(req.shares),
        "entry_time": entry,
        "exit_time": exit_t,
        "strategy_id": req.strategy_id or "manual",
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,
        "regime_at_entry": req.regime_at_entry or "",
        "setup_grade": req.setup_grade or "",
        "hold_days": hold_days,
        "source": req.source or "manual",
        "logged_at": _utc_now_iso(),
    }

    try:
        os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
        with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception as exc:
        logger.exception("ledger write failed: %s", exc)
        return {"ok": False, "error": str(exc), "row": row}

    return {"ok": True, "row": row, "ledger_path": LEDGER_PATH}
