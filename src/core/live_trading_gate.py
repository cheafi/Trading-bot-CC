"""Fail-closed live trading gate for unattended Docker orchestrators.

Live execution requires ALL of (exact, case-sensitive):
  - LIVE_TRADING=1
  - IB_MODE=live
  - IB_API_PORT=4003
  - LIVE_TRADING_ACCOUNT contains the broker account id (comma-separated allow-list)

Default is paper by construction when any requirement is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

LIVE_IB_API_PORT = "4003"


@dataclass(frozen=True)
class LiveTradingAuthorisation:
    """Immutable live-trading authorisation snapshot."""

    live_allowed: bool
    paper_by_construction: bool
    reason: str
    missing: tuple[str, ...]
    account: str = ""
    account_allowed: bool = False


# Backward-compatible alias for existing imports/tests.
LiveTradingGateResult = LiveTradingAuthorisation


def _parse_allowed_accounts() -> tuple[str, ...]:
    raw = os.environ.get("LIVE_TRADING_ACCOUNT", "")
    return tuple(part.strip().upper() for part in raw.split(",") if part.strip())


def evaluate_live_trading_gate(
    *,
    account: str = "",
) -> LiveTradingAuthorisation:
    """Evaluate env-only live gate. Account checked when provided."""
    live_trading = os.environ.get("LIVE_TRADING", "") == "1"
    ib_mode_live = os.environ.get("IB_MODE", "") == "live"
    port_ok = os.environ.get("IB_API_PORT", "") == LIVE_IB_API_PORT
    allowed_accounts = _parse_allowed_accounts()
    acct = str(account or "").strip().upper()

    missing: list[str] = []
    if not live_trading:
        missing.append("LIVE_TRADING=1")
    if not ib_mode_live:
        missing.append("IB_MODE=live")
    if not port_ok:
        missing.append(f"IB_API_PORT={LIVE_IB_API_PORT}")

    env_ok = live_trading and ib_mode_live and port_ok
    if not env_ok:
        return LiveTradingAuthorisation(
            live_allowed=False,
            paper_by_construction=True,
            reason="paper_by_construction",
            missing=tuple(missing),
            account=acct,
            account_allowed=False,
        )

    if not allowed_accounts:
        missing.append("LIVE_TRADING_ACCOUNT=<allow-listed account>")
        return LiveTradingAuthorisation(
            live_allowed=False,
            paper_by_construction=True,
            reason="paper_by_construction",
            missing=tuple(missing),
            account=acct,
            account_allowed=False,
        )

    if acct:
        if acct in allowed_accounts:
            return LiveTradingAuthorisation(
                live_allowed=True,
                paper_by_construction=False,
                reason="live_gate_confirmed",
                missing=(),
                account=acct,
                account_allowed=True,
            )
        missing.append(f"LIVE_TRADING_ACCOUNT must include {acct}")
        return LiveTradingAuthorisation(
            live_allowed=False,
            paper_by_construction=True,
            reason="paper_by_construction",
            missing=tuple(missing),
            account=acct,
            account_allowed=False,
        )

    # Boot-time: env triple + allow-list configured (account checked per order).
    return LiveTradingAuthorisation(
        live_allowed=True,
        paper_by_construction=False,
        reason="live_gate_confirmed",
        missing=(),
        account="",
        account_allowed=False,
    )


def authorize_live_order(account: str) -> LiveTradingAuthorisation:
    """Full live authorisation at order boundary (env + account allow-list)."""
    return evaluate_live_trading_gate(account=account)


def assert_live_gate_or_paper(*, live_requested: bool) -> bool:
    """
    Return True for paper (dry_run). When live is requested but the gate fails,
    raise SystemExit(1).
    """
    gate = evaluate_live_trading_gate()
    if live_requested and not gate.live_allowed:
        missing = ", ".join(gate.missing) or "unknown"
        raise SystemExit(
            f"Live trading refused — missing gate requirements: {missing}. "
            "Default is paper by construction."
        )
    return not gate.live_allowed
