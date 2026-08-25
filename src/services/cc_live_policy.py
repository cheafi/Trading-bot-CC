"""CC live-only policy — refuse brief/stale/mock when CC_LIVE_DATA_ONLY=1."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def cc_live_data_only_enabled() -> bool:
    """True when CC must not serve brief-fallback, disk snapshot, or mock boards."""
    return os.environ.get("CC_LIVE_DATA_ONLY", "").strip().lower() in _TRUTHY


def _suspended_authority(*, reason: str) -> Dict[str, Any]:
    return {
        "source": "live_unavailable",
        "authority_level": "suspended",
        "deploy_authority": False,
        "gates_active": True,
        "gates": {
            "regime_wait": True,
            "fallback_brief": False,
            "scanner_loading": True,
            "data_stale": True,
            "live_only_blocked": True,
        },
        "effective_action_max": "NONE",
        "allows_trade_labels": False,
        "live_only": True,
        "detail": reason,
    }


def build_live_unavailable_today_payload(*, reason: str) -> Dict[str, Any]:
    """Explicit Today response when live scanner path is required but unavailable."""
    now = datetime.now(timezone.utc)
    authority = _suspended_authority(reason=reason)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "narrative": (
            "Live-only mode — scanner cache empty and brief fallback disabled. "
            "Run engine cycle or wait for live scan."
        ),
        "market_regime": {
            "label": "NEUTRAL",
            "risk_state": "NEUTRAL",
            "should_trade": False,
            "confidence": 0.0,
            "tradeability": "WAIT",
            "summary": reason,
            "trend": "SIDEWAYS",
            "volatility": "NORMAL",
            "score": 0,
            "vix": None,
            "breadth": None,
            "entropy": None,
        },
        "market_pulse": {},
        "top_5": [],
        "near_miss": [],
        "filter_funnel": {
            "universe": 0,
            "signals_triggered": 0,
            "score_above_6": 0,
            "actionable_above_7": 0,
            "high_conviction_above_8": 0,
            "note": reason,
        },
        "best_setup_family": None,
        "family_breakdown": {},
        "avoid": [reason],
        "what_changed": [reason],
        "event_risks": [],
        "sector_summary": {},
        "action_summary": {},
        "ai_narrative": None,
        "decision_authority": authority,
        "todays_decision": {
            "day_state": "LIVE_UNAVAILABLE",
            "hero_label": "Live scan required",
            "deploy_posture": "WAIT",
            "deploy_label": "Live-only — no fallback board",
            "can_deploy_today": False,
        },
        "trust": {
            "mode": "PAPER",
            "source": "live-unavailable",
            "freshness": "UNAVAILABLE",
            "stale": True,
            "reason": reason,
            "live_only": True,
            "ai_powered": False,
            "as_of": now.isoformat() + "Z",
        },
        "live_only_blocked": True,
        "generated_at": now.isoformat() + "Z",
    }


def build_live_unavailable_ranked(*, reason: str) -> Dict[str, Any]:
    """Playbook/ranked shape when live pipeline required but unavailable."""
    saved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "count": 0,
        "opportunities": [],
        "near_miss": [],
        "avoid_grouped": {"total": 0, "groups": []},
        "rejection_clusters": [],
        "filter_funnel": {
            "universe_scanned": 0,
            "watch_qualified_setups": 0,
            "deploy_qualified_setups": 0,
            "high_score_setups": 0,
            "execution_ready_setups": 0,
        },
        "cached": False,
        "stale": False,
        "source": "live-unavailable",
        "warning": reason,
        "board_mode": "live_unavailable",
        "board_mode_label": "Live board unavailable",
        "board_message": reason,
        "board_explanation": (
            "CC_LIVE_DATA_ONLY is set — brief and disk snapshot fallbacks are disabled. "
            "Retry with refresh=true or run an engine cycle."
        ),
        "snapshot_timestamp": saved_at,
        "live_only_blocked": True,
        "trust": {
            "stale": True,
            "source": "live-unavailable",
            "live_only": True,
            "reason": reason,
        },
        "decision_authority": _suspended_authority(reason=reason),
    }
