"""GET /api/v7/portfolio-decision — allocator decision console for portfolio tab."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

_BROKER_SYNC_MAX_AGE_SEC = 900.0


def _broker_sync_fresh(last_sync: str) -> bool:
    if not last_sync:
        return False
    try:
        raw = str(last_sync).strip().replace("Z", "+00:00")
        ts = datetime.fromisoformat(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return 0 <= age <= _BROKER_SYNC_MAX_AGE_SEC
    except Exception:
        return False

from fastapi import APIRouter, Depends, Request

from src.api.deps import sanitize_for_json, verify_sensitive_api_key
from src.services.portfolio_decision_console import build_portfolio_decision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7", tags=["v7-surfaces"])

_CACHE_BY_SCOPE: Dict[str, Dict[str, Any]] = {}
_CACHE_TS_BY_SCOPE: Dict[str, float] = {}
_TTL = 60.0
_MAX_CACHE_ENTRIES = 32

# Process-global manual book (see portfolio.py). Not multi-tenant data isolation.
_DEPLOYMENT_MODEL = "single_operator_global_book"


def portfolio_fingerprint() -> str:
    """Revision token for the shared in-process portfolio book."""
    try:
        from src.api.routers import portfolio as _pf

        book = _pf._user_portfolio or {}
        holdings = book.get("holdings") or []
        updated = str(book.get("updated_at") or "")
        source = str(book.get("source") or "")
        return f"{source}:{len(holdings)}:{updated}"
    except Exception:
        return "unavailable"


def verified_principal_hash(api_key: str | None) -> str:
    """One-way operator fingerprint — never store or log raw API keys in cache keys."""
    if not api_key:
        return "anonymous"
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:24]


def portfolio_decision_cache_scope(*, principal_hash: str) -> str:
    """
    Response cache partition for the single shared portfolio book.

    This prevents stale summaries after book updates. It does NOT isolate holdings
    between different authenticated clients — all share `_user_portfolio`.
    """
    raw = f"{principal_hash}|{_DEPLOYMENT_MODEL}|{portfolio_fingerprint()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def fail_closed_should_trade(regime: Dict[str, Any]) -> bool:
    """
    Regime permission for new entries — strict bool True only.

    Not execution authorization; downstream gates still apply.
    """
    if not regime:
        return False
    if "should_trade" not in regime:
        return False
    val = regime.get("should_trade")
    if val is None:
        return False
    if isinstance(val, bool):
        return val is True
    return False


def portfolio_data_boundary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Explicit trust boundary for portfolio tab consumers."""
    book: Dict[str, Any] = {}
    try:
        from src.api.routers import portfolio as _pf

        book = _pf._user_portfolio if isinstance(_pf._user_portfolio, dict) else {}
        source = str(book.get("source") or "manual").lower()
    except Exception:
        source = "manual"

    ibkr = payload.get("ibkr_linkage") if isinstance(payload.get("ibkr_linkage"), dict) else {}
    broker_connected = bool(ibkr.get("broker_connected"))
    sync_quality = str(ibkr.get("sync_quality") or "").lower()
    link_source = str(ibkr.get("portfolio_source") or "").lower()
    book_manual = source in ("manual", "demo-seed", "")
    broker_positions = int(ibkr.get("broker_position_count") or 0)
    local_only_count = int(ibkr.get("local_only_count") or 0)
    book_holdings = len(book.get("holdings") or [])
    position_counts_aligned = (
        broker_positions > 0 and book_holdings == broker_positions
    )

    # Verified only when book source aligns with linkage, no local-only rows,
    # and linkage reports full broker_truth (not flags alone).
    book_aligned_with_broker = (
        link_source == source
        and source in ("ibkr", "futu", "broker")
        and broker_positions > 0
        and local_only_count == 0
    )
    last_sync = str(ibkr.get("last_sync") or "")
    book_account = str(
        book.get("broker_account_id") or book.get("account_id") or ""
    ).strip()
    link_account = str(
        ibkr.get("broker_account_id") or ibkr.get("account_id") or ""
    ).strip()
    account_identity_ok = bool(link_account) and (
        not book_account or book_account.upper() == link_account.upper()
    )
    broker_verified = (
        not book_manual
        and broker_connected
        and sync_quality == "broker_truth"
        and book_aligned_with_broker
        and _broker_sync_fresh(last_sync)
        and account_identity_ok
        and position_counts_aligned
    )
    if broker_verified:
        truth_mode = "BROKER_VERIFIED"
    elif broker_connected:
        truth_mode = "BROKER_UNVERIFIED"
    elif book_manual:
        truth_mode = "MANUAL"
    elif source == "paper":
        truth_mode = "PAPER_SIMULATION"
    else:
        truth_mode = "UNAVAILABLE"

    return {
        "deployment_model": _DEPLOYMENT_MODEL,
        "multi_tenant_data_isolation": False,
        "cache_note": (
            "Response cache tracks book revision only; all authenticated clients "
            "read the same in-process portfolio state."
        ),
        "portfolio_truth_mode": truth_mode,
        "broker_verified": broker_verified,
        "broker_account_identity_verified": account_identity_ok,
        "position_quantity_reconciled": position_counts_aligned,
        "protection_note": (
            "Suggested stop — not submitted to broker. "
            "Stop/target levels are analytical only unless explicitly reconciled."
        ),
        "api_key_exposure_note": (
            "Single-operator deployments may inject API credentials into the dashboard "
            "template; this is not safe for public internet exposure."
        ),
    }


def _cache_evict_expired(now: float) -> None:
    expired = [
        scope
        for scope, ts in list(_CACHE_TS_BY_SCOPE.items())
        if now - ts >= _TTL
    ]
    for scope in expired:
        _CACHE_BY_SCOPE.pop(scope, None)
        _CACHE_TS_BY_SCOPE.pop(scope, None)


def _cache_get(scope: str, now: float) -> Tuple[bool, Dict[str, Any] | None]:
    ts = _CACHE_TS_BY_SCOPE.get(scope, 0.0)
    if scope in _CACHE_BY_SCOPE and now - ts >= _TTL:
        _CACHE_BY_SCOPE.pop(scope, None)
        _CACHE_TS_BY_SCOPE.pop(scope, None)
        return False, None
    payload = _CACHE_BY_SCOPE.get(scope)
    if payload and now - ts < _TTL:
        return True, payload
    return False, None


def _cache_put(scope: str, payload: Dict[str, Any], now: float) -> None:
    _cache_evict_expired(now)
    while len(_CACHE_BY_SCOPE) >= _MAX_CACHE_ENTRIES and _CACHE_TS_BY_SCOPE:
        oldest = min(_CACHE_TS_BY_SCOPE, key=_CACHE_TS_BY_SCOPE.get)
        _CACHE_BY_SCOPE.pop(oldest, None)
        _CACHE_TS_BY_SCOPE.pop(oldest, None)
    _CACHE_BY_SCOPE[scope] = payload
    _CACHE_TS_BY_SCOPE[scope] = now


@router.get("/portfolio-decision")
async def portfolio_decision(
    request: Request,
    _: bool = Depends(verify_sensitive_api_key),
):
    """Portfolio decision summary + attribution + monitor + sleeves (authenticated)."""
    api_key = request.headers.get("X-API-Key")
    principal = verified_principal_hash(api_key)
    now = time.time()
    scope = portfolio_decision_cache_scope(principal_hash=principal)
    hit, cached = _cache_get(scope, now)
    if hit and cached is not None:
        return cached

    payload = await build_portfolio_decision(request)
    payload["portfolio_data_boundary"] = portfolio_data_boundary(payload)
    try:
        from src.services.cc_state import build_cc_state

        today = getattr(request.app.state, "today_v7_cache", None) or {}
        decision_authority = today.get("decision_authority") or {}
        regime = today.get("market_regime") or {}
        tradeability = str(regime.get("tradeability") or "WAIT")
        should_trade = fail_closed_should_trade(
            regime if isinstance(regime, dict) else {}
        )
        trust = today.get("trust") if isinstance(today.get("trust"), dict) else None
        payload["cc_state"] = build_cc_state(
            tradeability=tradeability,
            should_trade=should_trade,
            decision_authority=decision_authority if isinstance(decision_authority, dict) else {},
            execution_readiness=payload.get("execution") or {},
            surface_authority=None,
            trust=trust,
        )
    except Exception:
        pass
    out = sanitize_for_json(payload)
    if isinstance(out, dict) and out.get("portfolio_data_boundary"):
        _cache_put(scope, out, now)
    return out
