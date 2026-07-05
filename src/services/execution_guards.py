"""Execution guard helpers — circuit breaker and engine state (shared)."""

from __future__ import annotations

from typing import Any, Optional


def circuit_breaker_tripped(engine: Any) -> bool:
    """True when engine circuit breaker is active — not merely present as object."""
    if engine is None:
        return False
    if bool(getattr(engine, "circuit_breaker_triggered", False)):
        return True
    breaker = getattr(engine, "circuit_breaker", None)
    if breaker is None:
        return False
    if isinstance(breaker, bool):
        return breaker
    if hasattr(breaker, "triggered"):
        return bool(getattr(breaker, "triggered", False))
    # Legacy: never treat non-bool breaker object as tripped
    return False


def engine_is_running(engine: Any) -> bool:
    if engine is None:
        return False
    return bool(getattr(engine, "_running", False))
