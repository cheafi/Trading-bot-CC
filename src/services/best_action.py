"""Best Action Now — capital deployment summary for Playbook / Today surfaces."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"})
_PILOT_ACTIONS = frozenset({"PILOT"})
_WATCH_ACTIONS = frozenset(
    {"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"}
)
_AVOID_ACTIONS = frozenset(
    {"AVOID", "NO_TRADE", "NO_TOUCH", "DO_NOT_TOUCH", "AVOID_NOW"}
)

_SEMI_TICKERS = frozenset(
    {
        "NVDA",
        "AMD",
        "AVGO",
        "INTC",
        "TSM",
        "QCOM",
        "MU",
        "LRCX",
        "AMAT",
        "KLAC",
        "MRVL",
        "ASML",
        "ARM",
        "ON",
        "MCHP",
    }
)


def _norm_action(action: Optional[str]) -> str:
    return (action or "WATCH").upper().strip()


_CAPITAL_STANCE_LABELS = {
    "hold_cash": "Hold cash",
    "deploy_selectively": "Deploy selectively",
    "pilot_only": "Pilot only",
}


def _decision_confidence_label(quality: str, detail: str) -> str:
    q = (quality or "low").lower()
    tier = {"high": "High", "medium": "Medium", "low": "Low"}.get(q, "Low")
    return f"{tier} — {detail}" if detail else tier


def _evidence_quality(
    opportunities: List[Dict[str, Any]],
    *,
    source: str = "",
    stale: bool = False,
) -> tuple[str, str]:
    if stale or "fallback" in (source or ""):
        return (
            "low",
            "Fallback / stale-context board — rankings lack normal deploy authority",
        )
    if not opportunities:
        return "low", "No deploy-qualified setups in pipeline"
    badges = [str(o.get("evidence_badge") or "") for o in opportunities[:5]]
    if any("stale" in b for b in badges):
        return "low", "Stale brief fallback"
    avg_data = sum(float(o.get("data_conf") or 0.5) for o in opportunities[:5]) / min(
        5, len(opportunities)
    )
    if avg_data >= 0.7:
        return "medium", "Model output · cross-check live tape"
    return "low", "Raw model output · limited live validation"


def compute_theme_overlap(
    opportunities: List[Dict[str, Any]], limit: int = 10
) -> Dict[str, Any]:
    """Warn when top ranks cluster in semis / same sector bucket."""
    top = opportunities[:limit]
    semi = [o for o in top if (o.get("ticker") or "").upper() in _SEMI_TICKERS]
    buckets: Dict[str, int] = {}
    for o in top:
        b = (o.get("sector_type") or o.get("sector_bucket") or "other").upper()
        buckets[b] = buckets.get(b, 0) + 1
    dominant = max(buckets.items(), key=lambda x: x[1]) if buckets else ("", 0)
    warnings: List[str] = []
    if len(semi) >= 4:
        warnings.append(
            f"Semiconductor cluster: {len(semi)}/{len(top)} top names "
            f"({', '.join(x['ticker'] for x in semi[:5])})"
        )
    if dominant[1] >= 5 and dominant[0]:
        warnings.append(
            f"Sector concentration: {dominant[1]} names in {dominant[0].replace('_', ' ')}"
        )
    return {
        "semi_count": len(semi),
        "dominant_sector": dominant[0],
        "dominant_count": dominant[1],
        "warnings": warnings,
        "level": "high" if len(warnings) >= 2 else "medium" if warnings else "low",
    }


def _capital_stance(
    tradeability: str,
    should_trade: bool,
    *,
    execution_ready_count: int,
    pilot_count: int,
) -> tuple[str, str]:
    tradeability = (tradeability or "WAIT").upper()
    if tradeability == "WAIT":
        return (
            "hold_cash",
            "WAIT — no deploy-qualified setups and no broker handoff. "
            "Monitor near-misses and queue alerts; no new risk.",
        )
    if not should_trade or tradeability in ("WAIT", "NO_TRADE"):
        return "hold_cash", "Regime gate closed — protect capital, no new risk."
    if execution_ready_count >= 1 and tradeability in ("STRONG_TRADE", "TRADE"):
        return (
            "deploy_selectively",
            f"{execution_ready_count} execution-ready — size only at 1R with bracket.",
        )
    if pilot_count >= 1 or tradeability == "SELECTIVE":
        return (
            "pilot_only",
            "PILOT / WATCH only — half size max; no full-size deploy.",
        )
    return (
        "hold_cash",
        f"{tradeability} — watch triggers; do not chase.",
    )


def build_best_action(
    opportunities: List[Dict[str, Any]],
    *,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    regime_label: str = "",
    ibkr_connected: bool = False,
    ibkr_mode: str = "paper",
    source: str = "",
    stale: bool = False,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive sticky Best Action Now payload from ranked opportunities."""
    tradeability = (tradeability or "WAIT").upper()
    from src.services.decision_truth_model import resolve_active_data_source

    board_open = bool(
        should_trade
        and tradeability not in ("WAIT", "NO_TRADE")
        and resolve_active_data_source(ranked_source=source, stale=stale) == "live"
    )

    best_trade = None
    best_pilot = None
    best_watch = None
    best_avoid = None
    trade_count = 0
    execution_ready_count = 0
    pilot_count = 0

    for o in opportunities:
        act = _norm_action(o.get("effective_action") or o.get("action"))
        tk = o.get("ticker")
        if not tk:
            continue
        conf = float(
            o.get("final_conf") or o.get("score", 0) / 10 if o.get("score") else 0.6
        )
        if (
            board_open
            and o.get("execution_ready")
            and act in _TRADE_ACTIONS | _PILOT_ACTIONS
        ):
            execution_ready_count += 1
        if act in _TRADE_ACTIONS:
            trade_count += 1
            if board_open and not best_trade and o.get("execution_ready"):
                best_trade = {
                    "ticker": tk,
                    "action": "TRADE",
                    "confidence": round(conf, 2),
                    "entry_price": o.get("entry_price"),
                    "stop_price": o.get("stop_price"),
                    "risk_reward": o.get("risk_reward"),
                    "execution_ready": True,
                }
        if board_open and act in _PILOT_ACTIONS and not best_pilot:
            pilot_count += 1
            best_pilot = {
                "ticker": tk,
                "action": "PILOT",
                "confidence": round(conf, 2),
                "entry_price": o.get("entry_price"),
                "stop_price": o.get("stop_price"),
                "why_pilot": o.get("why_pilot"),
                "risk_reward": o.get("risk_reward"),
            }
        if act in _WATCH_ACTIONS and not best_watch:
            upgrade = o.get("upgrade_trigger") or o.get("entry_trigger") or ""
            if upgrade or act == "WATCH":
                best_watch = {
                    "ticker": tk,
                    "action": act,
                    "trigger": upgrade or "Reclaim entry zone on volume",
                    "confidence": round(conf, 2),
                }
        if act in _AVOID_ACTIONS and not best_avoid:
            best_avoid = {
                "ticker": tk,
                "action": act,
                "reason": o.get("avoid_reason")
                or o.get("invalidation")
                or "Regime or setup mismatch",
            }

    capital_stance, stance_liner = _capital_stance(
        tradeability,
        board_open,
        execution_ready_count=execution_ready_count,
        pilot_count=pilot_count,
    )

    eq, eq_label = _evidence_quality(opportunities, source=source, stale=stale)
    bracket_ready = bool(
        best_trade
        and best_trade.get("entry_price")
        and best_trade.get("stop_price")
        and float(best_trade["entry_price"]) > float(best_trade["stop_price"])
    )

    try:
        from src.services.execution_readiness import build_execution_readiness

        exec_ready = build_execution_readiness(
            ibkr_connected=ibkr_connected,
            ibkr_mode=ibkr_mode or "paper",
            bracket_ready=bracket_ready,
        )
        exec_ready["can_send_order"] = bool(
            exec_ready.get("trade_handoff_ready") and board_open and bracket_ready
        )
        exec_ready.setdefault("ibkr_connected", ibkr_connected)
        exec_ready["bracket_ready"] = bracket_ready
    except Exception:
        logger.warning("Execution readiness unavailable; handoff denied", exc_info=True)
        exec_ready = {
            "ibkr_connected": ibkr_connected,
            "mode": ibkr_mode or "paper",
            "bracket_ready": bracket_ready,
            "trade_handoff_ready": False,
            "can_send_order": False,
        }

    return {
        "capital_stance": capital_stance,
        "risk_posture": _CAPITAL_STANCE_LABELS.get(
            capital_stance, capital_stance.replace("_", " ").title()
        ),
        "stance_one_liner": stance_liner,
        "best_trade_now": best_trade,
        "best_pilot_now": best_pilot,
        "best_watch_upgrade": best_watch,
        "best_avoid_now": best_avoid,
        "trade_count": trade_count,
        "execution_ready_count": execution_ready_count,
        "pilot_count": pilot_count,
        "evidence_quality": eq,
        "evidence_label": eq_label,
        "decision_confidence": eq,
        "decision_confidence_label": _decision_confidence_label(eq, eq_label),
        "execution_readiness": exec_ready,
        "regime_label": regime_label,
        "tradeability": tradeability,
        "data_freshness": "STALE" if stale else "FRESH",
        "as_of": as_of or datetime.now(timezone.utc).isoformat() + "Z",
    }


def enrich_ranked_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach best_action + overlap_warning + truth model to playbook ranked."""
    opps = payload.get("opportunities") or []
    stale = bool(
        payload.get("stale") or payload.get("cached") or payload.get("refreshing")
    )
    source = str(payload.get("source") or "")
    incoming_authority = payload.get("decision_authority") or {}
    incoming_gates = incoming_authority.get("gates") or {}
    board_state = (payload.get("cc_state") or {}).get("tradeability_state") or {}
    board_inputs = (payload, board_state, incoming_authority)
    board_labels = [
        str(value).upper()
        for value in (
            payload.get("tradeability"),
            payload.get("board_tradeability"),
            board_state.get("tradeability"),
            incoming_authority.get("tradeability"),
        )
        if value
    ]
    tradeability_hint = (
        "NO_TRADE"
        if "NO_TRADE" in board_labels
        else "WAIT" if "WAIT" in board_labels else next(iter(board_labels), "")
    )
    board_veto = any(
        item.get("should_trade") is False or item.get("deploy_blocked")
        for item in board_inputs
    ) or bool(incoming_gates.get("regime_wait"))
    if board_veto and tradeability_hint != "NO_TRADE":
        tradeability_hint = "WAIT"
    try:
        from src.services.ibkr_service import (
            get_ibkr_service,
            ibkr_authority_gate_snapshot,
        )

        gates = ibkr_authority_gate_snapshot()
        ibkr_on = bool(gates.get("connected"))
        exec_blocked = bool(gates.get("circuit_breaker"))
        ibkr_mode = get_ibkr_service()._mode or "paper"
    except Exception:
        ibkr_on = False
        ibkr_mode = "paper"
        exec_blocked = False

    try:
        from src.services.cost_adjusted_ranker import enrich_opportunity_rows
        from src.services.index_regime import build_index_regime_summary

        index_regime = build_index_regime_summary(
            tradeability=tradeability_hint or "WAIT",
            should_trade=tradeability_hint not in ("NO_TRADE", "WAIT"),
            degraded=stale or "fallback" in source,
        )
        opps = enrich_opportunity_rows(
            opps,
            index_regime=index_regime,
            tradeability=tradeability_hint,
        )
        payload["opportunities"] = opps
        payload["index_regime_summary"] = index_regime
    except Exception:
        pass

    payload["overlap_warning"] = compute_theme_overlap(opps)
    execution_ready_count = sum(1 for o in opps if o.get("execution_ready"))
    pilot_count = sum(
        1 for o in opps if _norm_action(o.get("action")) in _PILOT_ACTIONS
    )
    board_tb = tradeability_hint
    try:
        from src.services.decision_truth_model import compute_honest_tradeability

        tradeability = compute_honest_tradeability(
            should_trade=board_tb not in ("WAIT", "NO_TRADE"),
            execution_ready=execution_ready_count,
            pilot_ready=pilot_count,
            council_high_8=len([o for o in opps if float(o.get("score") or 0) >= 8.0]),
            macro="Neutral",
            opportunity=(
                "Strong"
                if execution_ready_count >= 2
                else (
                    "Mixed"
                    if execution_ready_count >= 1 or pilot_count >= 1
                    else "Weak"
                )
            ),
        )
    except ImportError:
        tradeability = (
            "TRADE"
            if execution_ready_count >= 1
            else "SELECTIVE" if pilot_count >= 1 else "WAIT"
        )
    # Page-level board gate beats opportunity-derived tradeability.
    if board_tb in ("WAIT", "NO_TRADE"):
        tradeability = board_tb
        should_trade_board = False
    elif board_tb:
        tradeability = board_tb
        should_trade_board = board_tb not in ("WAIT", "NO_TRADE")
    else:
        should_trade_board = str(tradeability).upper() not in ("WAIT", "NO_TRADE")
    authority_source = incoming_authority.get("source") or (
        "stale_cache" if stale else "live"
    )
    staged_rows = {}
    try:
        from src.services.decision_truth_model import (
            apply_authority_to_rows,
            build_decision_authority,
            resolve_active_data_source,
        )
        from src.services.playbook_near_miss import (
            PLAYBOOK_NEAR_MISS_LIMIT,
            build_playbook_near_miss_rows,
        )

        board_mode = str(payload.get("board_mode") or "").lower()
        fallback_brief = (
            board_mode == "compressed_fallback"
            or "brief" in source.lower()
            or "fallback" in source.lower()
            or bool(payload.get("compressed"))
        )
        authority_source = resolve_active_data_source(
            ranked_source=source, stale=stale, fallback_brief=fallback_brief
        )
        if authority_source == "live":
            authority_source = incoming_authority.get("source") or authority_source
        authority = build_decision_authority(
            tradeability=tradeability if not fallback_brief else "WAIT",
            should_trade=should_trade_board and not fallback_brief,
            scanner_degraded=stale or fallback_brief,
            scanner_loading=bool(incoming_gates.get("scanner_loading")),
            data_stale=stale or bool(incoming_gates.get("data_stale")),
            fallback_brief=(
                fallback_brief or bool(incoming_gates.get("fallback_brief"))
            ),
            broker_offline=(not ibkr_on or bool(incoming_gates.get("broker_offline"))),
            engine_off=bool(incoming_gates.get("engine_off")),
            exec_blocked=(exec_blocked or bool(incoming_gates.get("exec_blocked"))),
            ranked_source=authority_source,
            ranked_stale=stale,
            deploy_ideas_count=execution_ready_count,
        )
        # Enrichment may add vetoes, never clear upstream restrictions.
        authority["gates"] = {
            **incoming_gates,
            **{
                key: bool(value or incoming_gates.get(key))
                for key, value in authority["gates"].items()
            },
        }
        authority["gates_active"] = bool(
            authority["gates_active"]
            or incoming_authority.get("gates_active")
            or any(authority["gates"].values())
        )
        incoming_restricted = bool(incoming_authority) and (
            incoming_authority.get("allows_trade_labels") is False
            or incoming_authority.get("authority_level", "deploy") != "deploy"
            or incoming_authority.get("effective_action_max", "DEPLOY") != "DEPLOY"
            or incoming_authority.get("source", "live") != "live"
        )
        if incoming_restricted or authority["gates_active"]:
            authority["allows_trade_labels"] = False
            authority["degraded"] = True
            if incoming_restricted:
                authority["authority_level"] = (
                    "suspended"
                    if "suspended"
                    in (
                        authority["authority_level"],
                        incoming_authority.get("authority_level"),
                    )
                    else "research"
                )
                ceilings = {"NONE": 0, "RESEARCH": 1, "WATCH": 2, "DEPLOY": 3}
                ceiling = incoming_authority.get("effective_action_max", "RESEARCH")
                authority["effective_action_max"] = min(
                    (authority["effective_action_max"], ceiling),
                    key=lambda value: ceilings.get(value, 0),
                )
                if authority["effective_action_max"] == "DEPLOY":
                    authority["effective_action_max"] = "RESEARCH"
            elif authority["authority_level"] == "deploy":
                authority["authority_level"] = "research"
                authority["effective_action_max"] = "RESEARCH"
            authority["display_action_max"] = authority["effective_action_max"]
            authority["counter_source"] = authority["source"]
            authority["degraded_copy"]["system_mode"] = "degraded"
            authority["degraded_copy"]["decision_authority_line"] = (
                "Decision authority: suspended"
                if authority["authority_level"] == "suspended"
                else "Decision authority: research-only"
            )
        authority["data_source_mismatch"] = bool(
            authority.get("data_source_mismatch")
            or incoming_authority.get("data_source_mismatch")
        )
        if incoming_authority.get("data_source_mismatch_detail"):
            authority["data_source_mismatch_detail"] = incoming_authority[
                "data_source_mismatch_detail"
            ]
        if incoming_authority.get("council_count") is not None:
            authority["council_count"] = incoming_authority["council_count"]
        staged_rows = {
            "opportunities": opps,
            "near_miss": build_playbook_near_miss_rows(
                deepcopy(opps), limit=PLAYBOOK_NEAR_MISS_LIMIT
            ),
        }
        if "near_miss_rows" in payload:
            staged_rows["near_miss_rows"] = payload["near_miss_rows"] or []
        staged_rows = {
            key: apply_authority_to_rows(deepcopy(rows), authority)
            for key, rows in staged_rows.items()
        }
        for rows in staged_rows.values():
            for row in rows:
                row["execution_ready"] = bool(
                    row.get("execution_ready")
                    and authority["allows_trade_labels"]
                    and not authority["gates_active"]
                    and _norm_action(row.get("effective_action") or row.get("action"))
                    in _TRADE_ACTIONS | _PILOT_ACTIONS
                )
        authority["deploy_ideas_count"] = sum(
            1 for row in staged_rows["opportunities"] if row.get("execution_ready")
        )
        payload.update({**staged_rows, "decision_authority": authority})
        opps = staged_rows["opportunities"]
        should_trade_board = should_trade_board and bool(
            authority["allows_trade_labels"]
        )
    except Exception:
        logger.warning("Row authority unavailable; board handoff denied", exc_info=True)
        should_trade_board = False
        # Neither canonical construction nor application can be trusted here.
        # Use the canonical suspended/NONE contract without retrying either.
        authority = {
            "council_count": None,
            "data_source_mismatch": False,
            "data_source_mismatch_detail": "",
            **deepcopy(incoming_authority),
            "source": authority_source,
            "authority_level": "suspended",
            "effective_action_max": "NONE",
            "display_action_max": "NONE",
            "allows_trade_labels": False,
            "gates": {
                "regime_wait": tradeability in ("WAIT", "NO_TRADE"),
                "engine_off": False,
                "data_stale": stale,
                "broker_offline": not ibkr_on,
                "scanner_loading": False,
                "fallback_brief": authority_source == "fallback_brief",
                **incoming_gates,
                "exec_blocked": True,
            },
            "gates_active": True,
            "degraded": True,
            "deploy_ideas_count": 0,
        }
        authority["counter_source"] = authority["source"]
        snapshot_lines = {
            "stale_cache": [
                "Historical snapshot only",
                "Not suitable for execution decisions",
                "Refresh required for decision use",
            ],
            "fallback_brief": [
                "Fallback board",
                "Reference plan only",
                "No deploy authority",
            ],
        }.get(authority_source, [])
        authority["degraded_copy"] = {
            **deepcopy(incoming_authority.get("degraded_copy") or {}),
            "system_mode": "degraded",
            "decision_authority_line": "Decision authority: suspended",
            "fallback_board_line": (
                "Fallback board: informational only · reference plan · "
                "no deploy authority"
                if authority_source == "fallback_brief"
                else " · ".join(snapshot_lines)
            ),
            "stale_snapshot_lines": snapshot_lines,
        }
        denied_rows = {}
        for key in ("opportunities", "near_miss", "near_miss_rows"):
            rows = (
                opps
                if key == "opportunities"
                else payload.get(key, staged_rows.get(key))
            )
            if rows is None:
                continue
            denied_rows[key] = []
            for original in rows:
                row = deepcopy(original)
                row.setdefault("raw_action", row.get("action"))
                row.update(
                    action="NONE",
                    effective_action="NONE",
                    effective_grade="NONE",
                    execution_ready=False,
                    pilot_state="BLOCKED",
                    authority_downgraded=True,
                    action_reason=("Row authority unavailable — no deploy authority"),
                    decision_authority={
                        "source": authority["source"],
                        "effective_action_max": "NONE",
                        "allows_trade_labels": False,
                    },
                )
                for flag in ("can_send_order", "trade_handoff_ready"):
                    if flag in row:
                        row[flag] = False
                if isinstance(row.get("trade_bar"), dict):
                    row["trade_bar"].update(
                        execution_ready=False, passes_trade_bar=False
                    )
                denied_rows[key].append(row)
        payload.update({**denied_rows, "decision_authority": authority})
        opps = denied_rows["opportunities"]
    try:
        from src.services.decision_truth_model import (
            build_avoid_grouped_from_rows,
            build_bucket_quality_from_rows,
        )

        payload["avoid_grouped"] = build_avoid_grouped_from_rows(opps)
        payload["bucket_quality"] = build_bucket_quality_from_rows(opps)
    except ImportError:
        pass
    payload["best_action"] = build_best_action(
        opps,
        tradeability=tradeability,
        should_trade=should_trade_board,
        regime_label=board_tb or tradeability,
        ibkr_connected=ibkr_on,
        ibkr_mode=ibkr_mode,
        source=source,
        stale=stale,
    )
    return payload
