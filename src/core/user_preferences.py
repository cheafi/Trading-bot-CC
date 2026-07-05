"""
User Preferences — Output Mode System (Sprint 38).

Supports three output verbosity levels:
  - QUICK:     Ticker + direction + price only
  - PRO:       Full card with scores, regime, explanation
  - EXPLAINER: Everything in PRO + why-now narrative,
               scenario plan, risk breakdown

Each Discord user can toggle their mode via ``/mode``.
The preference is stored in-memory (per bot session).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class OutputMode(str, Enum):
    QUICK = "quick"
    PRO = "pro"
    EXPLAINER = "explainer"


# Default mode for new users
DEFAULT_MODE = OutputMode.PRO

# What each mode includes
MODE_FIELDS = {
    OutputMode.QUICK: {
        "ticker", "direction", "entry_price",
        "stop_price", "trade_decision",
    },
    OutputMode.PRO: {
        "ticker", "direction", "entry_price",
        "stop_price", "trade_decision",
        "composite_score", "signal_confidence",
        "setup_grade", "regime_label",
        "strategy_id", "risk_reward_ratio",
        "horizon", "trust",
    },
    OutputMode.EXPLAINER: {
        "ticker", "direction", "entry_price",
        "stop_price", "trade_decision",
        "composite_score", "signal_confidence",
        "setup_grade", "regime_label",
        "strategy_id", "risk_reward_ratio",
        "horizon", "trust",
        # Explanation layer
        "why_now", "scenario_plan", "evidence",
        "event_risk", "portfolio_fit", "key_risks",
        "why_not_trade", "better_alternative",
        "approval_status", "approval_flags",
    },
}

MODE_DESCRIPTIONS = {
    OutputMode.QUICK: (
        "\u26a1 **Quick** \u2014 just ticker, direction, price"
    ),
    OutputMode.PRO: (
        "\U0001f4ca **Pro** \u2014 scores, regime, trust badges"
    ),
    OutputMode.EXPLAINER: (
        "\U0001f4d6 **Explainer** \u2014 full narrative "
        "with why-now, scenarios, risks"
    ),
}


@dataclass
class UserPreferences:
    """Per-user preferences."""
    user_id: str = ""
    mode: OutputMode = DEFAULT_MODE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "mode": self.mode.value,
        }


class UserPreferenceManager:
    """
    Manages per-user output preferences.

    In-memory for now. Can be backed by DB later.

    Usage::

        mgr = UserPreferenceManager()
        mgr.set_mode("user123", OutputMode.QUICK)
        mode = mgr.get_mode("user123")
        filtered = mgr.filter_output(rec_dict, "user123")
    """

    def __init__(self):
        self._prefs: Dict[str, UserPreferences] = {}

    def get_mode(self, user_id: str) -> OutputMode:
        """Get user's output mode."""
        pref = self._prefs.get(user_id)
        return pref.mode if pref else DEFAULT_MODE

    def set_mode(
        self, user_id: str, mode: OutputMode,
    ) -> OutputMode:
        """Set user's output mode. Returns the new mode."""
        if user_id not in self._prefs:
            self._prefs[user_id] = UserPreferences(
                user_id=user_id,
            )
        self._prefs[user_id].mode = mode
        logger.info(
            "User %s mode set to %s", user_id, mode.value,
        )
        return mode

    def cycle_mode(self, user_id: str) -> OutputMode:
        """Cycle to next mode: quick → pro → explainer → quick."""
        current = self.get_mode(user_id)
        order = [
            OutputMode.QUICK,
            OutputMode.PRO,
            OutputMode.EXPLAINER,
        ]
        idx = order.index(current)
        next_mode = order[(idx + 1) % len(order)]
        return self.set_mode(user_id, next_mode)

    def filter_output(
        self,
        rec_dict: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """Filter a recommendation dict to user's mode.

        Returns a copy with only the fields appropriate
        for the user's verbosity level.
        """
        mode = self.get_mode(user_id)
        allowed = MODE_FIELDS.get(mode, MODE_FIELDS[DEFAULT_MODE])
        return {
            k: v for k, v in rec_dict.items()
            if k in allowed
        }

    def get_mode_description(
        self, user_id: str,
    ) -> str:
        """Get description of current mode."""
        mode = self.get_mode(user_id)
        return MODE_DESCRIPTIONS.get(mode, "Unknown mode")

    @property
    def active_users(self) -> int:
        return len(self._prefs)


# Singleton
_manager: Optional[UserPreferenceManager] = None


def get_preference_manager() -> UserPreferenceManager:
    """Get the global preference manager."""
    global _manager
    if _manager is None:
        _manager = UserPreferenceManager()
    return _manager
