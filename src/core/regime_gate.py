"""
src/core/regime_gate.py — single fail-closed reading of a regime's trade permission
==================================================================================

Regime payloads arrive as dicts or objects from several producers. Many call
sites used ``regime.get("should_trade", True)``, which turns a *missing* key
into permission to trade. This helper is the one place that answers "may we
trade?" and it only says yes when the payload explicitly says so and is
backed by real data.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["regime_allows_trading"]


def _read(regime: Any, key: str) -> Any:
    if isinstance(regime, Mapping):
        return regime.get(key)
    return getattr(regime, key, None)


def regime_allows_trading(regime: Any) -> bool:
    """True only for an explicit, non-synthetic, non-unverified permission."""
    if regime is None:
        return False
    if _read(regime, "synthetic") is True:
        return False
    if _read(regime, "verified") is False:
        return False
    value = _read(regime, "should_trade")
    if value is None or isinstance(value, str):
        return False
    return bool(value)
