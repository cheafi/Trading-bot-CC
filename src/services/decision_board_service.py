"""Canonical decision board payload — shared by Today, Playbook, and cc-header."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_GATE_LABELS: Dict[str, str] = {
    "regime_wait": "Regime WAIT / NO_TRADE",
    "engine_off": "Engine off",
    "data_stale": "Data stale / degraded",
    "broker_offline": "Broker offline",
    "exec_blocked": "Execution blocked",
    "scanner_loading": "Scanner loading",
    "fallback_brief": "Fallback brief board",
}


def _extract_regime(payload: Dict[str, Any]) -> Dict[str, Any]:
    mr = payload.get("market_regime") or {}
    ba = payload.get("best_action") or {}
    dm = payload.get("decision_model") or {}
    tb = str(
        mr.get("honest_tradeability")
        or mr.get("tradeability")
        or dm.get("honest_tradeability")
        or ba.get("tradeability")
        or "WAIT"
    ).upper()
    return {
        "label": mr.get("label") or mr.get("risk_state") or "NEUTRAL",
        "trend": mr.get("trend") or "SIDEWAYS",
        "tradeability": tb,
        "should_trade": bool(
            mr.get("should_trade", tb not in ("NO_TRADE", "WAIT"))
        ),
        "vix": mr.get("vix"),
        "breadth": mr.get("breadth"),
        "macro_regime": dm.get("macro_regime"),
        "opportunity_quality": dm.get("opportunity_quality"),
        "execution_readiness": dm.get("execution_readiness"),
    }


def _normalize_payload_for_board(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Align playbook-ranked field names with today-shaped payloads."""
    out = dict(payload)
    mr = dict(out.get("market_regime") or {})
    ba = out.get("best_action") or {}
    if not mr.get("tradeability") and ba.get("tradeability"):
        mr["tradeability"] = ba["tradeability"]
    if "should_trade" not in mr and ba.get("tradeability"):
        mr["should_trade"] = str(ba["tradeability"]).upper() not in (
            "NO_TRADE",
            "WAIT",
        )
    if not mr and ba:
        mr = {
            "tradeability": ba.get("tradeability") or "WAIT",
            "should_trade": str(ba.get("tradeability") or "WAIT").upper()
            not in ("NO_TRADE", "WAIT"),
        }
    out["market_regime"] = mr
    if not out.get("execution_readiness") and ba.get("execution_readiness"):
        out["execution_readiness"] = ba["execution_readiness"]
    funnel = out.get("filter_funnel") or {}
    if out.get("deploy_qualified_count") is None and funnel:
        out["deploy_qualified_count"] = funnel.get("deploy_qualified_setups") or funnel.get(
            "execution_ready_setups"
        )
    return out


def _build_gate_reasons(
    *,
    decision_authority: Dict[str, Any],
    unlock_deploy: Optional[Dict[str, Any]],
    system_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    reasons: List[Dict[str, Any]] = []
    seen: set[str] = set()
    gates = decision_authority.get("gates") or {}
    for key, active in gates.items():
        if not active:
            continue
        seen.add(str(key))
        reasons.append(
            {
                "key": key,
                "active": True,
                "source": "authority_gate",
                "label": _GATE_LABELS.get(str(key), str(key).replace("_", " ").title()),
            }
        )
    for cond in (unlock_deploy or {}).get("conditions") or []:
        key = str(cond.get("key") or "")
        if cond.get("met") or key in seen:
            continue
        seen.add(key)
        reasons.append(
            {
                "key": key,
                "active": True,
                "source": "unlock_deploy",
                "label": str(cond.get("label") or key),
                "detail": cond.get("detail"),
            }
        )
    if not reasons and not system_state.get("deploy_open"):
        compact = str(system_state.get("blocker_compact") or "").strip()
        if compact:
            reasons.append(
                {
                    "key": "blocker",
                    "active": True,
                    "source": "system_state",
                    "label": compact,
                }
            )
    return reasons


def _build_gate_snapshot(
    *,
    system_state: Dict[str, Any],
    decision_authority: Dict[str, Any],
    unlock_deploy: Dict[str, Any],
) -> Dict[str, Any]:
    """Sprint 115 — gate snapshot for attribution chain."""
    return {
        "deploy_open": bool(system_state.get("deploy_open")),
        "tradeability": system_state.get("tradeability"),
        "gates_active": bool(decision_authority.get("gates_active")),
        "authority_level": decision_authority.get("authority_level"),
        "unlock_deploy": bool(unlock_deploy.get("unlocked")),
        "blocker_compact": system_state.get("blocker_compact"),
    }


def _build_board_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Attach decision_id + attribution_root_ref to top board rows."""
    from src.services.attribution_tree import enrich_board_row_attribution

    rows = list(payload.get("top_5") or payload.get("opportunities") or [])[:12]
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        enriched = enrich_board_row_attribution(row)
        out.append(
            {
                "ticker": enriched.get("ticker"),
                "rank": enriched.get("rank"),
                "action": enriched.get("action"),
                "decision_id": enriched.get("decision_id"),
                "attribution_root_ref": enriched.get("attribution_root_ref"),
                "artifact_id": enriched.get("artifact_id"),
                "alpha_id": enriched.get("alpha_id"),
            }
        )
    return out


def decision_board_hash(board: Dict[str, Any]) -> str:
    """Stable hash for polling — deploy_open + gate fingerprint."""
    fingerprint = {
        "deploy_open": bool(board.get("deploy_open")),
        "tradeability": board.get("tradeability"),
        "gates_active": (board.get("deploy_authority") or {}).get("gates_active"),
        "unlock_unlocked": (board.get("unlock_deploy") or {}).get("unlocked"),
        "stale": bool(board.get("stale")),
        "degraded": bool(board.get("degraded")),
    }
    raw = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_decision_board(
    payload: Dict[str, Any],
    *,
    ops: Optional[Dict[str, Any]] = None,
    source: str = "today",
) -> Dict[str, Any]:
    """
    Single canonical decision board block for Today / Playbook / header polling.

    Uses operator_state_contract + decision_truth_model — does not weaken gates.
    """
    from src.services.cc_state import attach_system_state

    normalized = _normalize_payload_for_board(payload)
    if not normalized.get("cc_state"):
        from src.services.cc_state import build_cc_state

        mr = normalized.get("market_regime") or {}
        tb = str(mr.get("tradeability") or "WAIT").upper()
        normalized["cc_state"] = build_cc_state(
            tradeability=tb,
            should_trade=bool(mr.get("should_trade", tb not in ("NO_TRADE", "WAIT"))),
            decision_authority=normalized.get("decision_authority") or {},
            execution_readiness=normalized.get("execution_readiness") or {},
            surface_authority=normalized.get("surface_authority"),
            trust=normalized.get("trust") if isinstance(normalized.get("trust"), dict) else None,
        )
    if not normalized.get("system_state"):
        attach_system_state(normalized)

    system_state = dict(normalized.get("system_state") or {})
    decision_authority = dict(normalized.get("decision_authority") or {})
    unlock_deploy = dict(normalized.get("unlock_deploy") or {})
    trust = normalized.get("trust") if isinstance(normalized.get("trust"), dict) else {}

    stale = bool(
        trust.get("stale")
        or normalized.get("stale")
        or normalized.get("cached")
        or (normalized.get("trust") or {}).get("freshness") == "DEGRADED"
    )
    degraded = bool(
        decision_authority.get("degraded")
        or decision_authority.get("gates_active")
        or stale
        or system_state.get("fallback_mode")
    )

    regime = _extract_regime(normalized)
    gate_reasons = _build_gate_reasons(
        decision_authority=decision_authority,
        unlock_deploy=unlock_deploy,
        system_state=system_state,
    )

    bdr_summary = normalized.get("bdr_summary")
    if not bdr_summary and source in ("today", "board", "header"):
        try:
            from src.services.bdr_operator_summary import build_bdr_from_today_payload

            bdr_summary = build_bdr_from_today_payload(normalized, ops=ops)
        except Exception:
            bdr_summary = None

    deploy_authority = {
        "authority_level": decision_authority.get("authority_level"),
        "gates_active": bool(decision_authority.get("gates_active")),
        "allows_trade_labels": bool(decision_authority.get("allows_trade_labels")),
        "effective_action_max": decision_authority.get("effective_action_max"),
        "display_action_max": decision_authority.get("display_action_max"),
        "source": decision_authority.get("source"),
        "degraded": bool(decision_authority.get("degraded")),
        "gates": decision_authority.get("gates") or {},
    }

    as_of = (
        normalized.get("generated_at")
        or trust.get("as_of")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    board: Dict[str, Any] = {
        "deploy_open": bool(system_state.get("deploy_open")),
        "deploy_authority": deploy_authority,
        "unlock_deploy": unlock_deploy,
        "bdr_summary": bdr_summary,
        "gate_reasons": gate_reasons,
        "gate_snapshot": _build_gate_snapshot(
            system_state=system_state,
            decision_authority=decision_authority,
            unlock_deploy=unlock_deploy,
        ),
        "board_rows": _build_board_rows(normalized),
        "regime": regime,
        "stale": stale,
        "degraded": degraded,
        "system_state": system_state,
        "tradeability": system_state.get("tradeability") or regime.get("tradeability"),
        "decision_authority": decision_authority,
        "as_of": as_of,
        "source": source,
    }
    board["decision_board_hash"] = decision_board_hash(board)
    return board


def attach_decision_board(
    payload: Dict[str, Any],
    *,
    ops: Optional[Dict[str, Any]] = None,
    source: str = "today",
) -> Dict[str, Any]:
    """Attach decision_board to a today/playbook payload; sync system_state."""
    board = build_decision_board(payload, ops=ops, source=source)
    payload["decision_board"] = board
    payload["decision_board_hash"] = board["decision_board_hash"]
    if board.get("system_state"):
        payload["system_state"] = board["system_state"]
    return payload
