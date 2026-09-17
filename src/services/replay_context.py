"""ReplayContext — authoritative as-of contract for historical decision replay.

Extends the existing /api/live/time-travel single-name replay with a dashboard-wide
replay mode. Never grants deploy authority; live IBKR handoff remains disabled.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict

REPLAY_CACHE_VERSION = "v1"
REPLAY_STORAGE_KEY = "cc_replay_as_of"


def parse_replay_as_of(value: str) -> date:
    """Parse YYYY-MM-DD; raises ValueError on bad input."""
    raw = (value or "").strip()[:10]
    return date.fromisoformat(raw)


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass(frozen=True)
class ReplayContext:
    """Immutable replay session — pass into engines instead of forking them."""

    as_of: date
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    allow_future_data: bool = False
    replay_mode: bool = True

    def validate_no_lookahead(self) -> None:
        """Reject as_of beyond UTC today — no future data in ranking path."""
        if self.as_of > utc_today():
            raise ValueError(
                f"Replay as_of {self.as_of.isoformat()} is in the future — "
                "allow_future_data=false prohibits look-ahead"
            )
        if self.allow_future_data:
            raise ValueError(
                "allow_future_data must remain false for dashboard replay (Phase 1)"
            )

    def cache_key(self) -> str:
        return f"{REPLAY_CACHE_VERSION}:{self.as_of.isoformat()}:{self.session_id[:8]}"

    def dossier_cache_key(self, ticker: str) -> str:
        """Disk cache key for single-name dossier replay (ticker + as_of)."""
        return (
            f"{REPLAY_CACHE_VERSION}:dossier:{ticker.upper()}:{self.as_of.isoformat()}"
        )

    def authority_contract(self) -> Dict[str, Any]:
        """Non-negotiable replay authority — research != deploy, no IBKR handoff."""
        return {
            "replay_mode": True,
            "may_authorize_deploy": False,
            "live_authority": "NONE",
            "authority": "research_only",
            "ibkr_handoff_enabled": False,
            "deploy_open": False,
            "allow_future_data": self.allow_future_data,
            "as_of": self.as_of.isoformat(),
            "session_id": self.session_id,
            "mode_label": "HISTORICAL REPLAY",
            "banner": (
                f"Historical replay as of {self.as_of.isoformat()} — "
                "decisions shown are KNOWN THEN; LIVE AUTHORITY: NONE"
            ),
        }

    def trust_block(self) -> Dict[str, Any]:
        return {
            "mode": "REPLAY",
            "source": "historical_decision_replay",
            "freshness": "HISTORICAL",
            "stale": False,
            "as_of": f"{self.as_of.isoformat()}T16:00:00Z",
            "replay_mode": True,
            "note": (
                "Historical dashboard replay — causal data only through as_of. "
                "Not a live recommendation."
            ),
        }


def build_replay_decision_authority(
    ctx: ReplayContext,
    *,
    tradeability: str = "WAIT",
    should_trade: bool = False,
) -> Dict[str, Any]:
    """Overlay live decision authority with replay suspension — never deploy."""
    from src.services.decision_truth_model import build_decision_authority

    base = build_decision_authority(
        tradeability=tradeability,
        should_trade=should_trade,
        scanner_degraded=False,
        scanner_loading=False,
        data_stale=False,
        fallback_brief=False,
        broker_offline=True,
        engine_off=True,
        exec_blocked=True,
        trust_source="historical_replay",
        ranked_source="historical_replay",
        ranked_stale=False,
    )
    contract = ctx.authority_contract()
    base["authority_level"] = "suspended"
    base["gates_active"] = True
    base["allows_trade_labels"] = False
    base["effective_action_max"] = "NONE"
    base["display_action_max"] = "NONE"
    base["source"] = "historical_replay"
    base["replay_mode"] = True
    base["may_authorize_deploy"] = False
    base["live_authority"] = contract["live_authority"]
    base["degraded"] = True
    base["degraded_copy"] = {
        **(base.get("degraded_copy") or {}),
        "decision_authority_line": "LIVE AUTHORITY: NONE — historical replay only",
        "fallback_board_line": contract["banner"],
        "stale_snapshot_lines": [
            "Historical decision replay",
            "KNOWN THEN decisions may show TRADE",
            "LIVE AUTHORITY: NONE — no IBKR handoff",
        ],
    }
    base["gates"] = {
        **(base.get("gates") or {}),
        "replay_mode": True,
        "broker_offline": True,
        "engine_off": True,
        "exec_blocked": True,
    }
    return base


def apply_replay_row_authority(
    row: Dict[str, Any], ctx: ReplayContext
) -> Dict[str, Any]:
    """Attach historical decision vs live authority on opportunity rows."""
    from src.services.decision_truth_model import apply_authority_to_row

    authority = build_replay_decision_authority(ctx)
    out = apply_authority_to_row(dict(row), authority)
    known = out.get("known_then") or {}
    hist_action = str(
        known.get("action") or out.get("raw_action") or out.get("action") or "WATCH"
    ).upper()
    out["historical_decision"] = hist_action
    out["live_authority"] = "NONE"
    out["deploy_authority"] = False
    out["may_authorize_deploy"] = False
    out["authority"] = "research_only"
    out["authority_label"] = (
        f"HISTORICAL DECISION: {hist_action} · LIVE AUTHORITY: NONE"
    )
    return out
