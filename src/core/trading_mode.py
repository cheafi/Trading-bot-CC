"""Resolve paper vs live execution mode — fail-closed dual gate.

Live trading requires BOTH:
  1. Explicit CLI flag (--live)
  2. Environment confirmation (LIVE_TRADING=1 or TRADING_ENV=live)

Partial or ambiguous live intent defaults to paper and may exit non-zero.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionModeResolution:
    dry_run: bool
    mode: str
    ambiguous: bool
    reason: str


def _live_env_confirmed() -> bool:
    live = os.environ.get("LIVE_TRADING", "").strip().lower()
    if live in ("1", "true", "yes"):
        return True
    return os.environ.get("TRADING_ENV", "").strip().lower() == "live"


def _legacy_dry_run_false() -> bool:
    """DRY_RUN=false alone must not enable live trading."""
    val = os.environ.get("DRY_RUN", "").strip().lower()
    return val in ("false", "0", "no")


def resolve_execution_mode(*, live_cli: bool = False) -> ExecutionModeResolution:
    """Resolve execution mode. Default is paper (dry_run=True)."""
    live_env = _live_env_confirmed()
    legacy_live = _legacy_dry_run_false()

    if live_cli and live_env:
        return ExecutionModeResolution(
            dry_run=False,
            mode="LIVE",
            ambiguous=False,
            reason="dual_gate_confirmed",
        )

    if live_cli or live_env or legacy_live:
        parts: list[str] = []
        if live_cli:
            parts.append("--live")
        if live_env:
            parts.append("LIVE_TRADING=1 or TRADING_ENV=live")
        if legacy_live:
            parts.append("DRY_RUN=false")
        reason = (
            "Ambiguous live trading intent ("
            + ", ".join(parts)
            + "). Live requires BOTH --live AND LIVE_TRADING=1 (or TRADING_ENV=live)."
        )
        logger.error(reason)
        return ExecutionModeResolution(
            dry_run=True,
            mode="PAPER",
            ambiguous=True,
            reason=reason,
        )

    return ExecutionModeResolution(
        dry_run=True,
        mode="PAPER",
        ambiguous=False,
        reason="default_paper",
    )


def resolve_dry_run(*, live_cli: bool = False) -> bool:
    """Return True for paper mode. Exits process on ambiguous live intent."""
    resolution = resolve_execution_mode(live_cli=live_cli)
    if resolution.ambiguous:
        raise SystemExit(1)
    return resolution.dry_run
