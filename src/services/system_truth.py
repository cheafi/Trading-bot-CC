"""
SystemTruth — single canonical resolver for freshness, gates, and deploy authority.

cc-header + Dashboard read ONE typed freshness line from this module
(no unscoped DATA FRESH + DATA STALE together).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_FRESHNESS_ORDER = ("CRITICAL", "STALE", "DEGRADED", "FALLBACK", "EXPIRED", "UNKNOWN", "FRESH")

BRIEF_EXPIRE_DAYS = 2


def classify_volatility_state(vix: Optional[float]) -> str:
    """VIX buckets — never crisis below 28."""
    if vix is None:
        return "unavailable"
    v = float(vix)
    if v < 14:
        return "low"
    if v < 20:
        return "normal"
    if v < 28:
        return "elevated"
    if v < 35:
        return "stress"
    return "crisis"


def _typed_from_legacy(tier: str) -> str:
    t = str(tier or "").upper()
    return {
        "FRESH": "fresh",
        "REAL_TIME": "fresh",
        "LIVE": "fresh",
        "STALE": "stale",
        "DEGRADED": "stale",
        "CRITICAL": "unavailable",
        "FALLBACK": "fallback",
        "EXPIRED": "expired",
        "UNKNOWN": "unavailable",
    }.get(t, t.lower() if t else "unavailable")


def _worst_freshness(*tiers: str) -> str:
    clean = [str(t or "").upper() for t in tiers if t]
    if not clean:
        return "UNKNOWN"
    for tier in _FRESHNESS_ORDER:
        if tier in clean:
            return tier
    return clean[0]


def _market_freshness(today: Dict[str, Any], cc_header: Dict[str, Any]) -> str:
    trust = today.get("trust") or {}
    header_tier = str(
        cc_header.get("data_tier")
        or cc_header.get("freshness_tier")
        or cc_header.get("market_data_freshness")
        or ""
    ).upper()
    trust_fresh = str(trust.get("freshness") or "").upper()
    stale = bool(trust.get("stale"))
    if header_tier in _FRESHNESS_ORDER:
        return _typed_from_legacy(header_tier)
    if stale or trust_fresh in ("DEGRADED", "STALE"):
        return "stale" if trust_fresh != "CRITICAL" else "unavailable"
    if trust_fresh in ("REAL_TIME", "LIVE", "FRESH"):
        return "fresh"
    mr = today.get("market_regime") or {}
    if today.get("scanner_degraded"):
        return "stale"
    if not mr:
        return "unavailable"
    return "fresh"


def _brief_freshness(
    today: Dict[str, Any],
    *,
    brief_age_days: Optional[int] = None,
) -> str:
    age = brief_age_days
    if age is None:
        age = int((today.get("brief_status") or {}).get("age_days") or 0)
    if age is not None and int(age) > BRIEF_EXPIRE_DAYS:
        return "expired"
    trust = today.get("trust") or {}
    source = str(trust.get("source") or "").lower()
    if "brief" in source and "fallback" in source:
        return "fallback"
    if today.get("used_brief_fallback"):
        return "fallback"
    ff = today.get("filter_funnel") or {}
    if "brief fallback" in str(ff.get("note") or "").lower():
        return "fallback"
    if "brief-fallback" in source:
        return "fallback"
    tier = str((today.get("brief_status") or {}).get("tier") or "").upper()
    if tier == "CRITICAL":
        return "expired"
    if tier == "STALE":
        return "stale"
    return "fresh"


def _ranked_board_freshness(today: Dict[str, Any]) -> str:
    if _brief_freshness(today) == "expired":
        return "unavailable"
    if today.get("used_brief_fallback"):
        return "fallback"
    if today.get("scanner_degraded"):
        top = today.get("top_5") or today.get("top_ranked") or []
        if not top:
            return "unavailable"
        return "stale"
    top = today.get("top_5") or today.get("top_ranked") or []
    if not top:
        return "unavailable"
    return "fresh"


def _dossier_freshness(cc_header: Dict[str, Any]) -> str:
    tier = str(cc_header.get("dossier_tier") or cc_header.get("data_tier") or "").upper()
    if tier in ("STALE", "CRITICAL"):
        return _typed_from_legacy(tier)
    if cc_header.get("dossier_degraded"):
        return "stale"
    return "fresh"


def _portfolio_freshness(cc_header: Dict[str, Any]) -> str:
    sync = str(cc_header.get("portfolio_sync") or cc_header.get("broker_sync") or "").lower()
    if sync in ("unavailable", "offline", "stale"):
        return sync if sync in ("unavailable", "stale") else "stale"
    if cc_header.get("portfolio_stale"):
        return "stale"
    return "fresh"


def _broker_freshness(today: Dict[str, Any], cc_header: Dict[str, Any]) -> str:
    er = today.get("execution_readiness") or {}
    if er.get("circuit_breaker") or cc_header.get("exec_blocked"):
        return "blocked"
    if er.get("trade_handoff_ready") or cc_header.get("ibkr_ready"):
        return "ready"
    if er.get("broker_connected") or er.get("ibkr_connected") or cc_header.get("ibkr_connected"):
        return "partial"
    return "offline"


def _engine_state(today: Dict[str, Any], ops: Dict[str, Any]) -> str:
    from src.services.authority_engine import resolve_engine_state

    return resolve_engine_state(today, ops)


def _regime_state(today: Dict[str, Any]) -> str:
    mr = today.get("market_regime") or {}
    tb = str(
        mr.get("honest_tradeability")
        or mr.get("tradeability")
        or today.get("tradeability")
        or "WAIT"
    ).upper()
    if not mr.get("should_trade", True):
        return "NO_TRADE"
    return tb


def _volatility_state(today: Dict[str, Any]) -> str:
    mr = today.get("market_regime") or {}
    vix = mr.get("vix")
    if vix is None and mr.get("volatility_label"):
        label = str(mr.get("volatility_label") or "").upper()
        return {
            "LOW": "low",
            "NORMAL": "normal",
            "ELEVATED": "elevated",
            "HIGH": "elevated",
            "STRESS": "stress",
            "CRISIS": "stress",
        }.get(label, "normal")
    return classify_volatility_state(vix if vix is not None else None)


def _breadth_state(today: Dict[str, Any]) -> str:
    mr = today.get("market_regime") or {}
    b = mr.get("breadth")
    if b is None:
        return "unavailable"
    pct = float(b)
    if pct <= 1.0:
        pct *= 100.0
    if pct >= 55:
        return "broad"
    if pct >= 42:
        return "mixed"
    return "narrow"


def _leadership_state(today: Dict[str, Any]) -> str:
    idx = today.get("index_regime_summary") or {}
    tags = idx.get("factor_regime", {}).get("leadership_tags") or idx.get("leadership_tags") or []
    if tags:
        return str(tags[0]).lower()
    mr = today.get("market_regime") or {}
    trend = str(mr.get("trend") or "SIDEWAYS").upper()
    if trend == "UPTREND":
        return "momentum"
    if trend == "DOWNTREND":
        return "defensive"
    return "mixed"


def _board_gate(today: Dict[str, Any]) -> str:
    regime = _regime_state(today)
    if regime == "NO_TRADE":
        return "closed"
    if regime in ("WAIT", "SELECTIVE"):
        return "wait"
    return "open"


def _execution_gate(today: Dict[str, Any]) -> str:
    er = today.get("execution_readiness") or {}
    if er.get("circuit_breaker"):
        return "blocked"
    if er.get("trade_handoff_ready"):
        return "ready"
    if not (er.get("broker_connected") or er.get("ibkr_connected")):
        return "offline"
    return "blocked"


def format_engine_state_display(engine_state: Optional[str] = None) -> str:
    """Never leak 'undefined' — map unknown engine to operator-safe label."""
    raw = str(engine_state or "").strip().lower()
    if not raw or raw == "undefined":
        return "Unknown"
    return {
        "on": "On",
        "off": "Off",
        "unknown": "Unknown",
    }.get(raw, raw.title())


def _runtime_freshness_label(runtime_state: str, engine_state: str) -> str:
    """Scoped Runtime segment for global truth strip."""
    rs = str(runtime_state or "").lower()
    eng = str(engine_state or "").lower()
    if rs in ("warming", "loading"):
        return "Warming"
    if rs == "execution_blocked":
        return "Blocked"
    if rs == "degraded":
        return "Degraded"
    if rs == "unknown" or eng == "unknown" or not eng or eng == "undefined":
        return "Unknown"
    if rs == "engine_off" or eng == "off":
        return "Off"
    if rs in ("engine_on", "live"):
        return "Live"
    return rs.replace("_", " ").title() if rs else "Unknown"


def _deploy_authority(
    today: Dict[str, Any],
    *,
    board_gate: str,
    execution_gate: str,
    brief_freshness: str,
    market_data_freshness: str,
    ranked_board_freshness: str = "fresh",
    broker_freshness: str = "offline",
) -> bool:
    auth = today.get("decision_authority") or {}
    if auth.get("authority_level") != "deploy":
        return False
    if auth.get("gates_active"):
        return False
    if not auth.get("allows_trade_labels"):
        return False
    if board_gate in ("closed", "wait"):
        return False
    if brief_freshness in ("expired", "fallback"):
        return False
    if broker_freshness in ("offline", "blocked"):
        return False
    if ranked_board_freshness in ("stale", "fallback", "unavailable"):
        return False
    if market_data_freshness in ("unavailable", "stale") and today.get("scanner_degraded"):
        return False
    if auth.get("source") in ("fallback_brief", "stale_cache"):
        return False
    deploy_n = int((today.get("qualification_levels") or {}).get("deploy_qualified") or 0)
    exec_n = int(
        today.get("execution_ready_count")
        or (today.get("filter_funnel") or {}).get("execution_ready_setups")
        or 0
    )
    if deploy_n < 1 and exec_n < 1:
        return False
    return board_gate == "open" or (
        board_gate == "wait"
        and exec_n >= 1
        and execution_gate == "ready"
        and not auth.get("gates_active")
    )


def build_reason_codes(
    *,
    market_data_freshness: str,
    ranked_board_freshness: str,
    brief_freshness: str,
    engine_state: str,
    broker_freshness: str,
    regime_state: str,
    board_gate: str,
    execution_gate: str,
    deploy_authority: bool,
    today: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Deduped canonical reason codes — mission panel reads ONLY this list."""
    codes: List[str] = []
    t = today or {}
    auth = t.get("decision_authority") or {}

    if regime_state == "NO_TRADE":
        codes.append("REGIME_NO_TRADE")
    elif board_gate == "wait":
        codes.append("BOARD_WAIT")
    elif board_gate == "closed":
        codes.append("BOARD_CLOSED")

    if market_data_freshness == "unavailable":
        codes.append("DATA_UNAVAILABLE")
    elif market_data_freshness == "stale":
        codes.append("DATA_STALE")

    if brief_freshness == "expired":
        codes.append("BRIEF_EXPIRED")
    elif brief_freshness == "fallback":
        codes.append("FALLBACK_BRIEF")
    elif brief_freshness == "stale":
        codes.append("BRIEF_STALE")

    if ranked_board_freshness == "fallback" and brief_freshness != "expired":
        if "FALLBACK_BRIEF" not in codes:
            codes.append("FALLBACK_BRIEF")
    elif ranked_board_freshness == "stale" and "DATA_STALE" not in codes:
        codes.append("BOARD_STALE")
    elif ranked_board_freshness == "unavailable":
        codes.append("NO_VALID_BOARD")

    if engine_state == "off":
        codes.append("ENGINE_OFF")
    if broker_freshness == "offline":
        codes.append("BROKER_OFFLINE")
    elif broker_freshness == "blocked":
        codes.append("EXEC_BLOCKED")
    if execution_gate == "blocked" and "EXEC_BLOCKED" not in codes:
        codes.append("EXEC_BLOCKED")

    deploy_n = int((t.get("qualification_levels") or {}).get("deploy_qualified") or 0)
    if not deploy_authority and deploy_n < 1:
        codes.append("NO_DEPLOY_QUALIFIED")

    if auth.get("gates_active"):
        gates = auth.get("gates") or {}
        for key, active in gates.items():
            if active:
                code = f"GATE_{str(key).upper()}"
                if code not in codes:
                    codes.append(code)

    seen: set[str] = set()
    out: List[str] = []
    for c in codes:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:8]


def reason_codes_to_copy(codes: List[str]) -> List[str]:
    """Operator-facing lines derived from canonical codes."""
    _MAP = {
        "REGIME_NO_TRADE": "Regime gate closed — no new risk",
        "BOARD_WAIT": "Board WAIT — monitor only, no deploy",
        "BOARD_CLOSED": "Board closed — preserve capital",
        "DATA_UNAVAILABLE": "Market data unavailable — refresh before sizing",
        "DATA_STALE": "Market data stale — rankings may not reflect live tape",
        "BOARD_STALE": "Ranked board stale — not execution-grade",
        "NO_VALID_BOARD": "No valid ranked board — do nothing",
        "BRIEF_EXPIRED": "Brief expired — not used for ranking",
        "BRIEF_STALE": "Brief stale — confirm before using narrative",
        "FALLBACK_BRIEF": "Brief fallback — not execution-grade board",
        "ENGINE_OFF": "Engine OFF — precomputed board only",
        "BROKER_OFFLINE": "IBKR offline — no handoff",
        "EXEC_BLOCKED": "Execution blocked — breaker or bracket",
        "NO_DEPLOY_QUALIFIED": "No deploy-qualified setups",
    }
    return [_MAP.get(c, c.replace("_", " ").title()) for c in codes]


def _primary_blocker(reason_codes: List[str], reason_copy: List[str]) -> str:
    if reason_copy:
        return reason_copy[0]
    if reason_codes:
        return reason_codes[0].replace("_", " ").title()
    return "No edge today — preserve capital"


def _repair_priority(reason_codes: List[str]) -> List[str]:
    priority = [
        "BROKER_OFFLINE",
        "EXEC_BLOCKED",
        "DATA_UNAVAILABLE",
        "DATA_STALE",
        "BRIEF_EXPIRED",
        "FALLBACK_BRIEF",
        "BOARD_STALE",
        "NO_VALID_BOARD",
        "ENGINE_OFF",
        "NO_DEPLOY_QUALIFIED",
        "BOARD_WAIT",
        "BOARD_CLOSED",
        "REGIME_NO_TRADE",
    ]
    ordered = [c for c in priority if c in reason_codes]
    for c in reason_codes:
        if c not in ordered:
            ordered.append(c)
    return ordered[:5]


def _freshness_label(scope: str, val: str, *, brief_age_days: Optional[int] = None) -> str:
    v = str(val or "unavailable").lower()
    display = {
        "fresh": "Fresh",
        "stale": "Stale",
        "fallback": "Fallback",
        "expired": "Expired",
        "unavailable": "Unavailable",
        "offline": "Offline",
        "blocked": "Blocked",
        "ready": "Ready",
        "partial": "Partial",
    }.get(v, v.title())
    if scope == "Brief" and v == "expired" and brief_age_days is not None:
        display = f"Expired {int(brief_age_days)}d"
    return display


def format_global_truth_strip(truth: Dict[str, Any]) -> str:
    """Scoped freshness strip — e.g. Market: Fresh · Board: Stale · Brief: Expired 21d · Runtime: Warming."""
    age = truth.get("brief_age_days")
    runtime = truth.get("runtime_freshness") or _runtime_freshness_label(
        str(truth.get("runtime_state") or ""),
        str(truth.get("engine_state") or ""),
    )
    parts = [
        f"Market: {_freshness_label('Market', truth.get('market_data_freshness', 'unavailable'))}",
        f"Board: {_freshness_label('Board', truth.get('ranked_board_freshness', 'unavailable'))}",
        f"Brief: {_freshness_label('Brief', truth.get('brief_freshness', 'unavailable'), brief_age_days=age)}",
        f"Broker: {_freshness_label('Broker', truth.get('broker_freshness', 'offline'))}",
        f"Runtime: {runtime}",
        f"Authority: {'Open' if truth.get('deploy_authority') else 'Blocked'}",
    ]
    return " · ".join(parts)


def format_operator_sentence(truth: Dict[str, Any]) -> str:
    """One clean operator sentence for hero / agent blocker line."""
    regime = str(truth.get("regime_state") or "WAIT").upper()
    blocker = str(truth.get("primary_blocker") or "upgrade conditions not met")
    allowed = (
        "deploy selectively"
        if truth.get("deploy_authority")
        else "monitor only"
    )
    if regime == "NO_TRADE":
        allowed = "monitor only"
    deploy_n = int(truth.get("deploy_qualified_count") or 0)
    qual = f"{deploy_n} deploy-qualified" if deploy_n else "0 deploy-qualified"
    return f"Today {regime} — {blocker} — Allowed: {allowed} — {qual}"


def _runtime_state(today: Dict[str, Any], ops: Dict[str, Any], engine_state: str) -> str:
    er = today.get("execution_readiness") or {}
    if ops.get("exec_blocked") or er.get("circuit_breaker"):
        return "execution_blocked"
    if engine_state == "on":
        return "engine_on"
    if engine_state == "off":
        return "engine_off"
    if today.get("scanner_degraded") or today.get("used_brief_fallback"):
        return "degraded"
    if engine_state == "unknown":
        return "unknown"
    return "live"


def typed_freshness_display(truth: Dict[str, Any]) -> str:
    """Scoped freshness line — never mixes generic DATA FRESH + DATA STALE."""
    parts: List[str] = []

    age = truth.get("brief_age_days")
    parts.append(
        f"Market: {_freshness_label('Market', truth.get('market_data_freshness', 'unavailable'))}"
    )
    parts.append(
        f"Board: {_freshness_label('Board', truth.get('ranked_board_freshness', 'unavailable'))}"
    )
    parts.append(
        f"Brief: {_freshness_label('Brief', truth.get('brief_freshness', 'unavailable'), brief_age_days=age)}"
    )
    broker = str(truth.get("broker_freshness") or "offline").lower()
    parts.append(
        f"Broker: {_freshness_label('Broker', 'offline' if broker == 'offline' else broker)}"
    )
    runtime = truth.get("runtime_freshness") or _runtime_freshness_label(
        str(truth.get("runtime_state") or ""),
        str(truth.get("engine_state") or ""),
    )
    parts.append(f"Runtime: {runtime}")
    auth = "Blocked" if not truth.get("deploy_authority") else "Open"
    parts.append(f"Authority: {auth}")
    return " · ".join(parts)


def mission_blockers_from_truth(truth: Dict[str, Any], *, limit: int = 6) -> List[str]:
    """Infra blockers from canonical truth — matches cc-helpers.systemTruthMissionBlockers."""
    if truth.get("agent_blocker_compact"):
        blocker = str(truth.get("primary_blocker") or "").strip()
        if blocker:
            return [blocker]
        copy = truth.get("reason_copy") or reason_codes_to_copy(truth.get("reason_codes") or [])
        return copy[:1]
    copy = truth.get("reason_copy") or reason_codes_to_copy(truth.get("reason_codes") or [])
    return copy[: max(1, int(limit))]


def build_unified_truth_strip(truth: Dict[str, Any]) -> str:
    """Alias for format_global_truth_strip — tests and legacy callers."""
    return format_global_truth_strip(truth)


def resolve_deploy_authority(
    *,
    decision_authority: Optional[Dict[str, Any]] = None,
    execution_ready_count: int = 0,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    brief_expired: bool = False,
) -> bool:
    """Whether deploy_qualified counts may be non-zero (used by funnel finalize)."""
    auth = decision_authority or {}
    tb = (tradeability or "WAIT").upper()
    if not should_trade or tb == "NO_TRADE":
        return False
    if brief_expired:
        return False
    if auth.get("authority_level") != "deploy":
        return False
    if auth.get("gates_active"):
        return False
    if not auth.get("allows_trade_labels"):
        return False
    if auth.get("source") in ("fallback_brief", "stale_cache"):
        return False
    return execution_ready_count >= 1


def unified_freshness_tier(
    market_data_freshness: str,
    brief_freshness: str,
    ranked_board_freshness: str = "fresh",
) -> str:
    """Legacy worst-tier for backward compat — maps typed → legacy uppercase."""
    typed_worst = "fresh"
    order = ("unavailable", "expired", "fallback", "stale", "fresh")
    for val in (market_data_freshness, brief_freshness, ranked_board_freshness):
        v = str(val or "").lower()
        if v in order and order.index(v) < order.index(typed_worst):
            typed_worst = v
    legacy = {
        "fresh": "FRESH",
        "stale": "STALE",
        "fallback": "FALLBACK",
        "expired": "EXPIRED",
        "unavailable": "CRITICAL",
    }
    return legacy.get(typed_worst, typed_worst.upper())


def build_morning_decision_line(
    truth: Dict[str, Any],
    *,
    best_candidate: str = "",
) -> str:
    regime = str(truth.get("regime_state") or "WAIT").upper()
    allowed = "deploy selectively" if truth.get("deploy_authority") else "monitor only"
    if regime == "NO_TRADE":
        allowed = "monitor only"
    blocker = truth.get("primary_blocker") or "upgrade conditions not met"
    candidate = (best_candidate or "").strip() or "none"
    return (
        f"Today: {regime} · Reason: {blocker} · "
        f"Allowed: {allowed} · Best candidate: {candidate}"
    )


def system_truth_line(truth: Optional[Dict[str, Any]] = None) -> str:
    """Canonical typed freshness line for cc-header / data contract strip."""
    t = truth or {}
    if t.get("typed_freshness_display"):
        return str(t["typed_freshness_display"])
    return typed_freshness_display(t)


def resolve_system_truth(
    today: Optional[Dict[str, Any]] = None,
    cc_header: Optional[Dict[str, Any]] = None,
    ops: Optional[Dict[str, Any]] = None,
    *,
    ops_console: Optional[Dict[str, Any]] = None,
    brief_age_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Single canonical resolver — wire into /api/v7/today as system_truth."""
    t = today or {}
    header = cc_header or {}
    o = ops_console or ops or {}

    if brief_age_days is not None:
        t = {**t, "brief_status": {**(t.get("brief_status") or {}), "age_days": brief_age_days}}

    market_data_freshness = _market_freshness(t, header)
    brief_freshness = _brief_freshness(t, brief_age_days=brief_age_days)
    ranked_board_freshness = _ranked_board_freshness(t)
    dossier_freshness = _dossier_freshness(header)
    portfolio_freshness = _portfolio_freshness(header)
    broker_freshness = _broker_freshness(t, header)
    freshness_tier = unified_freshness_tier(
        market_data_freshness, brief_freshness, ranked_board_freshness
    )
    engine_state = _engine_state(t, o)
    runtime_state = _runtime_state(t, o, engine_state)
    regime_state = _regime_state(t)
    volatility_state = _volatility_state(t)
    breadth_state = _breadth_state(t)
    leadership_state = _leadership_state(t)
    board_gate = _board_gate(t)
    execution_gate = _execution_gate(t)
    deploy_auth = _deploy_authority(
        t,
        board_gate=board_gate,
        execution_gate=execution_gate,
        brief_freshness=brief_freshness,
        market_data_freshness=market_data_freshness,
        ranked_board_freshness=ranked_board_freshness,
        broker_freshness=broker_freshness,
    )
    engine_display = format_engine_state_display(engine_state)
    runtime_freshness = _runtime_freshness_label(runtime_state, engine_state)
    deploy_authority_label = "open" if deploy_auth else "blocked"
    tradeability_authority_line = ""
    if regime_state.upper() == "SELECTIVE" and (
        ranked_board_freshness in ("stale", "fallback")
        or market_data_freshness == "stale"
    ):
        tradeability_authority_line = (
            "Tradeability: Selective candidate review only · Deploy authority: Blocked"
        )
    reason_codes = build_reason_codes(
        market_data_freshness=market_data_freshness,
        ranked_board_freshness=ranked_board_freshness,
        brief_freshness=brief_freshness,
        engine_state=engine_state,
        broker_freshness=broker_freshness,
        regime_state=regime_state,
        board_gate=board_gate,
        execution_gate=execution_gate,
        deploy_authority=deploy_auth,
        today=t,
    )
    reason_copy = reason_codes_to_copy(reason_codes)
    primary_blocker = _primary_blocker(reason_codes, reason_copy)
    repair_priority = _repair_priority(reason_codes)

    qual = t.get("qualification_levels") or {}
    funnel = t.get("filter_funnel") or {}
    deploy_n = int(qual.get("deploy_qualified") or funnel.get("deploy_qualified_setups") or 0)
    if not deploy_auth:
        deploy_n = 0
    watch_n = int(qual.get("watch_qualified") or qual.get("setup_qualified") or funnel.get("watch_qualified_setups") or 0)
    setup_n = int(qual.get("setup_qualified") or watch_n)
    trade_n = int(qual.get("trade_qualified") or 0)
    exec_n = int(qual.get("execution_qualified") or 0)

    from src.services.playbook_truth import format_playbook_qualification_line

    qualification_line = format_playbook_qualification_line(
        setup_qualified=setup_n,
        trade_qualified=trade_n,
        execution_qualified=exec_n,
        deploy_qualified=deploy_n,
        deploy_authority=deploy_auth,
        regime_state=regime_state,
    )
    brief_expired = brief_freshness == "expired"
    brief_expired_copy = (
        f"Brief expired {int(brief_age_days or (t.get('brief_status') or {}).get('age_days') or 0)}d — excluded from ranking and narrative."
        if brief_expired
        else ""
    )

    td = t.get("todays_decision") or {}
    best = (
        (td.get("best_trade") or {}).get("ticker")
        or (td.get("best_watch") or {}).get("ticker")
        or ""
    )
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    truth_body = {
        "market_data_freshness": market_data_freshness,
        "ranked_board_freshness": ranked_board_freshness,
        "brief_freshness": brief_freshness,
        "brief_age_days": brief_age_days or (t.get("brief_status") or {}).get("age_days"),
        "dossier_freshness": dossier_freshness,
        "portfolio_freshness": portfolio_freshness,
        "broker_freshness": broker_freshness,
        "runtime_state": runtime_state,
        "regime_state": regime_state,
        "volatility_state": volatility_state,
        "breadth_state": breadth_state,
        "leadership_state": leadership_state,
        "board_gate": board_gate,
        "execution_gate": execution_gate,
        "deploy_authority": deploy_auth,
        "reason_codes": reason_codes,
        "reason_copy": reason_copy,
        "primary_blocker": primary_blocker,
        "repair_priority": repair_priority,
        "freshness_tier": freshness_tier,
        "engine_state": engine_state,
        "engine_state_display": engine_display,
        "runtime_freshness": runtime_freshness,
        "deploy_authority_label": deploy_authority_label,
        "tradeability_authority_line": tradeability_authority_line,
        "broker_state": broker_freshness,
        "deploy_qualified_count": deploy_n,
        "setup_qualified_count": setup_n,
        "trade_qualified_count": trade_n,
        "execution_qualified_count": exec_n,
        "qualification_line": qualification_line,
        "watch_qualified_count": watch_n,
        "brief_expired": brief_expired,
        "brief_expired_copy": brief_expired_copy,
        "hide_brief_narrative": brief_expired,
        "scoped_freshness": {
            "market_data": market_data_freshness,
            "ranked_board": ranked_board_freshness,
            "brief": brief_freshness,
            "dossier": dossier_freshness,
            "portfolio": portfolio_freshness,
            "broker": broker_freshness,
        },
        "timestamp": ts,
    }
    truth_body["typed_freshness_display"] = typed_freshness_display(truth_body)
    truth_body["truth_strip"] = format_global_truth_strip(truth_body)
    truth_body["operator_sentence"] = format_operator_sentence(truth_body)
    truth_body["morning_decision_line"] = build_morning_decision_line(
        truth_body, best_candidate=str(best)
    )
    return truth_body
