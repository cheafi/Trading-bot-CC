"""Paper copy-trading mirror — follow Signal Board leaders (no live orders)."""

from __future__ import annotations

from typing import Any


def paper_copy_leaders(
    board: dict[str, Any] | None = None,
    *,
    limit: int = 5,
    notional: float = 100_000.0,
) -> dict[str, Any]:
    from src.services.signal_board import get_latest

    board = board if board is not None else get_latest() or {}
    buckets = board.get("buckets") or {}
    rows = list(buckets.get("strong_buy") or []) + list(buckets.get("buy") or [])
    rows = [r for r in rows if isinstance(r, dict)][: max(1, min(limit, 20))]
    if not rows:
        return {
            "status": "empty",
            "authority": "paper_copy",
            "execution_permission": False,
            "positions": [],
            "warning": "No Signal Board leaders to mirror",
        }

    weight = 1.0 / len(rows)
    positions = []
    for row in rows:
        entry = float(row.get("entry") or row.get("price") or 0)
        stop = float(row.get("stop") or 0)
        alloc = notional * weight
        shares = round(alloc / entry, 4) if entry > 0 else 0
        risk_pct = row.get("risk_pct")
        positions.append(
            {
                "ticker": row.get("ticker"),
                "side": "LONG",
                "weight_pct": round(weight * 100, 2),
                "notional": round(alloc, 2),
                "shares_hint": shares,
                "entry": entry,
                "stop": stop,
                "target": row.get("target1"),
                "score": row.get("score"),
                "setup": row.get("setup"),
                "risk_pct": risk_pct,
                "mirror_rule": "equal_weight_top_signals",
            }
        )

    return {
        "status": "ok",
        "authority": "paper_copy",
        "execution_permission": False,
        "regime": (board.get("regime") or {}).get("label"),
        "as_of": board.get("generated_at"),
        "notional": notional,
        "positions": positions,
        "note": (
            "One-click copy is paper-only. Connect broker separately; "
            "live mirror requires gates + API key + explicit user confirm."
        ),
    }
