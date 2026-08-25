"""Real-Time Alpha Monitor — Produced/Lost/Preserved/Missed KPIs (Sprint 118)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_CLOSED_TRADES = _DATA_DIR / "closed_trades.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_closed_trades_today() -> List[Dict[str, Any]]:
    if not _CLOSED_TRADES.is_file():
        return []
    today = datetime.now(timezone.utc).date().isoformat()
    rows: List[Dict[str, Any]] = []
    for line in _CLOSED_TRADES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        exit_time = str(row.get("exit_time") or row.get("closed_at") or "")
        if exit_time.startswith(today):
            rows.append(row)
    return rows


def build_alpha_monitor_kpis(
    *,
    deploy_missed_count: int = 0,
    deploy_deferred_count: int = 0,
    lessons_captured: int = 0,
) -> Dict[str, Any]:
    """Daily alpha KPIs — not signal counts."""
    closed = _load_closed_trades_today()
    produced_bps = sum(float(t.get("pnl_pct") or 0) * 100 for t in closed if float(t.get("pnl_pct") or 0) > 0)
    lost_bps = sum(abs(float(t.get("pnl_pct") or 0) * 100) for t in closed if float(t.get("pnl_pct") or 0) < 0)
    preserved_bps = max(produced_bps - lost_bps, 0.0)

    return {
        "as_of": _utcnow_iso(),
        "authority": "research_only",
        "alpha_produced_today_bps": round(produced_bps, 2),
        "alpha_lost_bps": round(lost_bps, 2),
        "alpha_preserved_bps": round(preserved_bps, 2),
        "alpha_missed_bps": round(float(deploy_missed_count) * 25.0, 2),
        "alpha_deferred_bps": round(float(deploy_deferred_count) * 15.0, 2),
        "alpha_learned_count": lessons_captured,
        "closed_trades_today": len(closed),
    }
