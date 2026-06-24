from __future__ import annotations

from typing import Any, Dict, List, Optional


def _norm_tradeability(tradeability: str) -> str:
    tb = str(tradeability or "WAIT").upper().strip()
    return tb or "WAIT"


def build_execution_ladder_state(
    execution_readiness: Optional[Dict[str, Any]] = None,
    *,
    board_blocked: bool = False,
    board_reason: str = "",
) -> Dict[str, Any]:
    ex = execution_readiness or {}

    gateway_reachable = bool(ex.get("gateway_reachable"))
    broker_connected = bool(ex.get("broker_connected") or ex.get("ibkr_connected"))
    api_port_open = bool(ex.get("api_port_open"))
    bracket_ready = bool(ex.get("bracket_ready") or ex.get("bracket_order_ready"))
    handoff_ready = bool(ex.get("trade_handoff_ready"))
    engine_running = bool(ex.get("engine_running"))
    circuit_breaker = bool(ex.get("circuit_breaker"))
    monitoring_only = bool(ex.get("monitoring_only"))

    blockers: List[Dict[str, Any]] = []

    if not gateway_reachable:
        blockers.append({"domain": "broker", "code": "GATEWAY_DOWN", "label": "Gateway unreachable"})
    elif not api_port_open and not broker_connected:
        blockers.append({"domain": "broker", "code": "IBAPI_MISSING", "label": "IB API port closed"})
    elif gateway_reachable and not broker_connected:
        blockers.append({"domain": "broker", "code": "SESSION_INACTIVE", "label": "Session inactive"})

    if circuit_breaker:
        blockers.append({"domain": "engine", "code": "CIRCUIT_BREAKER", "label": "Circuit breaker"})
    elif not engine_running:
        blockers.append({"domain": "engine", "code": "ENGINE_OFF", "label": "Engine off"})

    if board_blocked:
        blockers.append(
            {
                "domain": "board",
                "code": "HANDOFF_BLOCKED",
                "label": board_reason or "Board gate blocks execution",
            }
        )

    if circuit_breaker:
        state = "EXEC_BLOCKED"
    elif not engine_running:
        state = "ENGINE_OFF"
    elif not gateway_reachable:
        state = "GATEWAY_DOWN"
    elif not api_port_open and not broker_connected:
        state = "IBAPI_MISSING"
    elif gateway_reachable and not broker_connected:
        state = "SESSION_INACTIVE"
    elif board_blocked:
        state = "HANDOFF_BLOCKED"
    elif handoff_ready:
        state = "HANDOFF_READY"
    elif bracket_ready:
        state = "BRACKET_READY"
    elif monitoring_only or broker_connected:
        state = "CONNECTED"
    else:
        state = "DISCONNECTED"

    return {
        "state": state,
        "broker_connected": broker_connected,
        "gateway_reachable": gateway_reachable,
        "api_port_open": api_port_open,
        "engine_running": engine_running,
        "circuit_breaker": circuit_breaker,
        "bracket_ready": bracket_ready,
        "handoff_ready": handoff_ready,
        "monitoring_only": monitoring_only,
        "blockers": blockers,
        "label": str(ex.get("readiness_label") or ""),
        "level": str(ex.get("level") or ""),
    }


def build_cc_state(
    *,
    tradeability: str,
    should_trade: bool,
    decision_authority: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    surface_authority: Any = None,
    trust: Optional[Dict[str, Any]] = None,
    dossier_freshness: str = "",
) -> Dict[str, Any]:
    tb = _norm_tradeability(tradeability)
    da = decision_authority or {}
    trust_obj = trust if isinstance(trust, dict) else {}

    board_state = str(da.get("authority_level") or "").lower()
    if board_state == "deploy" and not bool(da.get("gates_active")):
        board_state = "DEPLOY"
    elif board_state == "suspended":
        board_state = "SUSPENDED"
    else:
        board_state = "RESEARCH_ONLY"

    board_blocked = board_state != "DEPLOY" or tb in ("WAIT", "NO_TRADE") or not should_trade
    board_reason = (
        "Regime gate: WAIT"
        if tb == "WAIT"
        else "Regime gate: NO_TRADE"
        if tb == "NO_TRADE"
        else "Decision authority not deploy"
        if board_state != "DEPLOY"
        else "Board gate blocks deploy"
    )

    execution_state = build_execution_ladder_state(
        execution_readiness,
        board_blocked=board_blocked,
        board_reason=board_reason,
    )

    market_tier = "STALE" if bool(trust_obj.get("stale")) else "FRESH"
    board_src = str(da.get("source") or "")
    board_tier = (
        "STALE"
        if board_src in ("stale_cache", "fallback_brief") or bool(da.get("degraded"))
        else "FRESH"
    )
    exec_state = str(execution_state.get("state") or "")
    execution_tier = (
        "CRITICAL"
        if exec_state == "EXEC_BLOCKED"
        else "STALE"
        if exec_state
        in (
            "ENGINE_OFF",
            "GATEWAY_DOWN",
            "IBAPI_MISSING",
            "SESSION_INACTIVE",
            "HANDOFF_BLOCKED",
            "DISCONNECTED",
        )
        else "FRESH"
    )
    tiers = [
        ("market", market_tier),
        ("board", board_tier),
        ("dossier", dossier_freshness or ""),
        ("execution", execution_tier),
    ]
    worst_tier = "FRESH"
    worst_domain = ""
    for domain, tier in tiers:
        if tier == "CRITICAL":
            worst_tier = "CRITICAL"
            worst_domain = domain
            break
        if tier == "STALE" and worst_tier != "CRITICAL":
            worst_tier = "STALE"
            worst_domain = worst_domain or domain

    return {
        "tradeability_state": {
            "tradeability": tb,
            "should_trade": bool(should_trade),
        },
        "board_decision_state": {
            **da,
            "state": board_state,
        },
        "execution_state": execution_state,
        "surface_authority": surface_authority,
        "freshness_state": {
            "market": market_tier,
            "board": board_tier,
            "dossier": dossier_freshness or "",
            "execution": execution_tier,
            "worst_tier": worst_tier,
            "worst_domain": worst_domain,
            "board_source": board_src,
            "as_of": str(trust_obj.get("as_of") or ""),
        },
    }


def attach_system_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach system_state to any payload that already has cc_state."""
    from src.services.operator_state_contract import build_system_state

    cs = payload.get("cc_state") if isinstance(payload.get("cc_state"), dict) else {}
    da = payload.get("decision_authority") or cs.get("board_decision_state") or {}
    tb = str(
        (cs.get("tradeability_state") or {}).get("tradeability")
        or payload.get("tradeability")
        or da.get("tradeability")
        or "WAIT"
    )
    should_trade = bool((cs.get("tradeability_state") or {}).get("should_trade"))
    payload["system_state"] = build_system_state(
        tradeability=tb,
        should_trade=should_trade,
        cc_state=cs,
        execution_readiness=payload.get("execution_readiness"),
        trust=payload.get("trust"),
        decision_authority=da if isinstance(da, dict) else {},
    )
    return payload


def attach_page_capability(
    payload: Dict[str, Any],
    tab: str,
    *,
    fetch_state: str = "ok",
    mock_only: bool = False,
) -> Dict[str, Any]:
    """Attach page_capability for a UI tab (requires system_state on payload)."""
    from src.services.operator_state_contract import build_page_capability, resolve_tab_id

    if not payload.get("system_state"):
        attach_system_state(payload)
    tab_key = resolve_tab_id(tab)
    payload["page_capability"] = build_page_capability(
        tab_key,
        system_state=payload.get("system_state") or {},
        fetch_state=fetch_state,
        mock_only=mock_only,
    )
    return payload
