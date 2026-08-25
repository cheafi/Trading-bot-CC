"""Playbook operator intelligence — dense monitor insight without deploy authority."""

from __future__ import annotations

from typing import Any, Dict, List

from src.services.decision_truth_model import parse_ratio
from src.services.playbook_upgrade_ladder import (
    enrich_row_ladder_fields,
    sort_rows_by_upgrade_proximity,
    upgrade_proximity_score,
)

_MONITOR_STATES = (
    "research",
    "watch",
    "near_miss",
    "pilot_review",
    "deploy_review",
    "avoid",
    "stale",
    "archived",
)

_VIBE_LABELS = (
    "expansion",
    "rotation",
    "crowded_breakout",
    "fragile_breakout",
    "stealth_accumulation",
    "defensive_drift",
    "false_strength",
    "watch_only",
)


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val if val is not None else default)
    except (TypeError, ValueError):
        return default


def _norm_action(row: Dict[str, Any]) -> str:
    return str(row.get("action") or row.get("effective_action") or "WATCH").upper()


def build_operator_insight(
    row: Dict[str, Any], *, board_wait: bool = True
) -> Dict[str, str]:
    """Structured insight strip: Now / Blocker / Upgrade / Risk / Next check."""
    gaps = row.get("upgrade_gaps") or {}
    act = _norm_action(row)
    tb_note = "board still WAIT" if board_wait else "board gate open"
    blocker_parts: List[str] = []
    for key, label in (
        ("exec", "execution"),
        ("timing", "timing"),
        ("thesis", "thesis"),
        ("rr", "R:R"),
        ("data", "data quality"),
    ):
        val = gaps.get(key, "ok")
        if val not in ("ok", "n/a"):
            blocker_parts.append(f"{label} {val}")
    if row.get("rr_below_trade_threshold"):
        blocker_parts.append("R:R below trade gate")
    if not row.get("execution_ready"):
        blocker_parts.append("not execution-ready")
    blocker = " · ".join(blocker_parts) if blocker_parts else "page gate / monitor-only"
    upgrade = str(
        row.get("upgrade_trigger")
        or row.get("alert_trigger")
        or row.get("operator_action")
        or "Confirm volume + timing before upgrade"
    )[:140]
    risk_parts: List[str] = []
    if str(row.get("leader") or "").upper() == "LAGGARD":
        risk_parts.append("sector laggard")
    if _f(row.get("contradiction_score")) >= 0.55:
        risk_parts.append("contradiction elevated")
    if row.get("event_risk") or row.get("earnings"):
        risk_parts.append("event-sensitive")
    risk = " · ".join(risk_parts) if risk_parts else "standard monitor risk"
    next_check = str(
        row.get("alert_trigger") or row.get("operator_action") or "volume + sector rank"
    )[:120]
    now = str(
        row.get("why_here") or row.get("rank_explain", [""])[0]
        if row.get("rank_explain")
        else ""
    )[:140]
    if not now:
        now = f"{act} · {tb_note}"
    return {
        "now": now,
        "blocker": blocker,
        "upgrade": upgrade,
        "risk": risk,
        "next_check": next_check,
    }


def build_evidence_stack(row: Dict[str, Any]) -> Dict[str, Any]:
    """Compact cross-surface evidence — supporting only, not deploy authority."""
    return {
        "board_score": row.get("score"),
        "rs_state": row.get("rs_state") or row.get("leader"),
        "flow_state": row.get("flow_confirmation") or row.get("flow_state"),
        "dossier_state": row.get("dossier_state"),
        "contradiction_score": row.get("contradiction_score"),
        "sector_leadership": row.get("leader") or row.get("sector_alignment_label"),
        "regime_alignment": row.get("sector_alignment") or row.get("regime_alignment"),
        "event_risk": row.get("event_risk") or bool(row.get("earnings")),
        "freshness_tier": row.get("freshness_tier")
        or row.get("evidence_badge")
        or row.get("data_conf_label"),
        "evidence_badge": row.get("evidence_badge"),
    }


def classify_monitor_state(row: Dict[str, Any]) -> str:
    """Paper/monitor state machine label — no live execution."""
    act = _norm_action(row)
    if act in ("AVOID", "NO_TRADE", "BLOCKED"):
        return "avoid"
    if row.get("stale") or str(row.get("freshness_tier") or "").upper() in (
        "STALE",
        "CRITICAL",
    ):
        return "stale"
    bucket = str(row.get("ladder_bucket") or "")
    if bucket == "deploy_ready" and row.get("execution_ready"):
        return "deploy_review"
    if act == "PILOT" or bucket == "pilot_ready":
        return "pilot_review"
    if float(row.get("score") or 0) >= 6 and not row.get("execution_ready"):
        return "near_miss"
    if act in ("WATCH", "MONITOR"):
        return "watch"
    return "research"


def _watch_score(row: Dict[str, Any]) -> float:
    score = _f(row.get("score"))
    thesis = _f(row.get("thesis_conf"))
    timing = _f(row.get("timing_conf"))
    prox = max(0.0, 100.0 - upgrade_proximity_score(row))
    return round(min(100.0, score * 8 + thesis * 20 + timing * 15 + prox * 0.35), 1)


def _upgrade_probability(row: Dict[str, Any]) -> float:
    prox = upgrade_proximity_score(row)
    return round(max(0.0, min(0.95, 1.0 - prox / 120.0)), 2)


def build_watch_intelligence_row(row: Dict[str, Any]) -> Dict[str, Any]:
    gaps = row.get("upgrade_gaps") or {}
    return {
        "ticker": row.get("ticker"),
        "watch_score": _watch_score(row),
        "upgrade_probability": _upgrade_probability(row),
        "trigger_proximity": gaps,
        "monitor_state": classify_monitor_state(row),
        "monitoring_priority": row.get("ladder_bucket") or "watch_upgrade",
        "alert_worthy": _upgrade_probability(row) >= 0.55
        or gaps.get("timing") not in ("ok", "n/a", None),
    }


def _queue_for_row(row: Dict[str, Any]) -> str:
    gaps = row.get("upgrade_gaps") or {}
    state = classify_monitor_state(row)
    if state == "avoid":
        return "dead_remove"
    if state == "stale":
        return "needs_data_refresh"
    if gaps.get("exec") not in ("ok", None) and gaps.get("thesis") == "ok":
        return "needs_broker_only"
    if gaps.get("timing") not in ("ok", "n/a", None) and gaps.get("thesis") == "ok":
        return "needs_timing"
    if gaps.get("thesis") not in ("ok", None):
        return "needs_thesis"
    if gaps.get("data") not in ("ok", None):
        return "needs_data_refresh"
    if _upgrade_probability(row) >= 0.6:
        return "near_trigger"
    if float(row.get("vol_ratio") or 0) < 1.0:
        return "needs_volume"
    return "early_setup"


def build_watch_queues(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    queues: Dict[str, List[Dict[str, Any]]] = {
        "near_trigger": [],
        "early_setup": [],
        "needs_volume": [],
        "needs_thesis": [],
        "needs_timing": [],
        "needs_broker_only": [],
        "needs_data_refresh": [],
        "dead_remove": [],
    }
    for row in rows:
        if not row.get("ticker"):
            continue
        key = _queue_for_row(row)
        entry = {
            "ticker": row.get("ticker"),
            "watch_score": _watch_score(row),
            "upgrade_probability": _upgrade_probability(row),
            "operator_action": row.get("operator_action"),
            "alert_trigger": row.get("alert_trigger"),
        }
        queues.setdefault(key, []).append(entry)
    for key in queues:
        queues[key] = sorted(
            queues[key], key=lambda r: -float(r.get("watch_score") or 0)
        )[:8]
    return queues


def build_ai_vibe(
    *,
    tradeability: str,
    deploy_count: int,
    watch_count: int,
    opportunities: List[Dict[str, Any]],
    regime_label: str = "",
) -> Dict[str, Any]:
    """Rule-based monitor-only tape feel — never grants deploy authority."""
    tb = str(tradeability or "WAIT").upper()
    leaders = sum(
        1 for r in opportunities if str(r.get("leader") or "").upper() == "LEADER"
    )
    laggards = sum(
        1 for r in opportunities if str(r.get("leader") or "").upper() == "LAGGARD"
    )
    n = max(len(opportunities), 1)
    leader_ratio = leaders / n
    if tb in ("WAIT", "NO_TRADE") or deploy_count < 1:
        vibe = "watch_only"
        guidance = "wait"
        summary = "WAIT posture — stalk upgrades, do not press deploy."
    elif leader_ratio >= 0.45 and deploy_count >= 1:
        vibe = "expansion"
        guidance = "probe"
        summary = "Leadership broadening — probe only if deploy gate open."
    elif laggards / n >= 0.4:
        vibe = "defensive_drift"
        guidance = "avoid"
        summary = "Sector laggards dominate — defensive monitor bias."
    elif watch_count >= deploy_count * 3:
        vibe = "stealth_accumulation"
        guidance = "stalk"
        summary = "Thick watch pool, thin deploy — stalk triggers."
    else:
        vibe = "rotation"
        guidance = "stalk"
        summary = "Mixed tape — rotation monitor session."
    if str(regime_label).upper() in ("RISK_OFF", "CRISIS"):
        vibe = "false_strength"
        guidance = "avoid"
        summary = "Risk-off regime — treat strength as fragile."
    return {
        "vibe": vibe,
        "guidance": guidance,
        "summary": summary,
        "monitor_only": True,
        "authority": "research_supporting",
        "labels": list(_VIBE_LABELS),
    }


def build_board_posture(
    *,
    tradeability: str,
    deploy_count: int,
    pilot_count: int,
    board_wait: bool,
) -> Dict[str, Any]:
    """Unified copy truth — fixes SELECTIVE header vs WAIT board mismatch."""
    tb = str(tradeability or "WAIT").upper()
    if deploy_count >= 1:
        effective = "DEPLOY_OPEN"
        copy_line = (
            f"{tb} · {deploy_count} deploy-qualified — page gate may still apply."
        )
    elif tb == "SELECTIVE" and pilot_count >= 1:
        effective = "SELECTIVE_MONITOR"
        copy_line = "SELECTIVE regime · pilot names exist but zero deploy-qualified — monitor only."
    elif board_wait or tb in ("WAIT", "NO_TRADE"):
        effective = "WAIT"
        copy_line = "WAIT · no deploy-qualified setups — monitor session only."
    else:
        effective = "MONITOR"
        copy_line = f"{tb} · monitor ranking only until deploy gate opens."
    return {
        "tradeability_label": tb,
        "effective_posture": effective,
        "deploy_open": deploy_count >= 1,
        "copy_line": copy_line,
    }


def build_operator_sections(
    rows: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Layered operator board sections."""
    sorted_rows = sort_rows_by_upgrade_proximity([r for r in rows if r.get("ticker")])

    def _pick(pred, limit: int = 5) -> List[Dict[str, Any]]:
        out = [r for r in sorted_rows if pred(r)]
        return out[:limit]

    return {
        "deploy_candidates": _pick(
            lambda r: (
                r.get("ladder_bucket") == "deploy_ready" and r.get("execution_ready")
            )
        ),
        "pilot_candidates": _pick(lambda r: r.get("ladder_bucket") == "pilot_ready"),
        "watch_upgrades": _pick(lambda r: r.get("ladder_bucket") == "watch_upgrade"),
        "blocked_high_conviction": _pick(
            lambda r: (
                _f(r.get("thesis_conf")) >= 0.65
                and _norm_action(r) not in ("AVOID", "NO_TRADE")
            )
        ),
        "fastest_improving": sorted_rows[:5],
        "sector_leaders": _pick(
            lambda r: str(r.get("leader") or "").upper() == "LEADER"
        ),
        "best_rr": sorted(
            [r for r in sorted_rows if parse_ratio(r.get("risk_reward"), 0) or 0],
            key=lambda r: -(parse_ratio(r.get("risk_reward"), 0) or 0),
        )[:5],
        "monitor_queue": sorted_rows[:12],
        "event_sensitive": _pick(
            lambda r: bool(r.get("earnings") or r.get("event_risk"))
        ),
        "contradiction_heavy": _pick(lambda r: _f(r.get("contradiction_score")) >= 0.5),
    }


def build_paper_automation_stub(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Paper-only queue — not live, not deploy authority."""
    queue = []
    for row in rows[:6]:
        if not row.get("ticker"):
            continue
        queue.append(
            {
                "ticker": row.get("ticker"),
                "draft_action": "paper_watch"
                if classify_monitor_state(row) != "deploy_review"
                else "paper_review",
                "expected_r": parse_ratio(row.get("risk_reward"), 0),
                "entry_note": row.get("operator_action"),
                "mode": "PAPER_ONLY",
            }
        )
    return {
        "mode": "PAPER_ONLY",
        "live_disabled": True,
        "queue": queue,
        "disclaimer": "Paper automation drafts only — not live execution.",
    }


def build_monitor_auto_actions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Paper/monitor-only promote / downgrade / alert suggestions — no live orders."""
    actions: List[Dict[str, Any]] = []
    for row in rows:
        ticker = row.get("ticker")
        if not ticker:
            continue
        wi = row.get("watch_intelligence") or {}
        state = str(row.get("monitor_state") or "watch")
        prob = float(wi.get("upgrade_probability") or 0)
        if state in ("avoid", "stale", "archived"):
            continue
        if prob >= 0.62 and state in ("watch", "near_miss", "research"):
            actions.append(
                {
                    "ticker": ticker,
                    "action": "auto_promote_watch",
                    "reason": "trigger proximity improved",
                    "upgrade_probability": prob,
                    "paper_only": True,
                }
            )
        elif prob < 0.22 and state in ("near_miss", "pilot_review"):
            actions.append(
                {
                    "ticker": ticker,
                    "action": "auto_downgrade",
                    "reason": "thesis/timing proximity weakened",
                    "upgrade_probability": prob,
                    "paper_only": True,
                }
            )
        if wi.get("alert_worthy"):
            actions.append(
                {
                    "ticker": ticker,
                    "action": "alert",
                    "reason": str(
                        row.get("alert_trigger")
                        or row.get("operator_action")
                        or "monitor state change"
                    )[:120],
                    "paper_only": True,
                }
            )
    return actions[:24]


def build_auto_execution_stub(
    *,
    deploy_open: bool,
    broker_ready: bool,
    data_fresh: bool,
    degraded: bool,
) -> Dict[str, Any]:
    """Future-safe auto-trading architecture — disabled unless all gates open."""
    gates = {
        "board_gate_open": deploy_open,
        "broker_ready": broker_ready,
        "data_fresh": data_fresh,
        "not_degraded": not degraded,
        "kill_switch_off": True,
    }
    enabled = all(gates.values())
    return {
        "enabled": enabled,
        "mode": "disabled",
        "policy": "disabled_until_all_gates",
        "gates": gates,
        "modules": [
            "signal_validation",
            "broker_readiness",
            "bracket_builder",
            "risk_sizing",
            "order_simulation",
            "order_approval_policy",
            "execution_audit_trail",
            "kill_switch",
            "max_daily_loss_guard",
            "regime_guard",
            "stale_data_guard",
            "duplicate_order_guard",
            "contradiction_guard",
            "paper_live_separation",
        ],
    }


def enrich_playbook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach operator intelligence to ranked Playbook payload."""
    opps = list(payload.get("opportunities") or [])
    near = list(payload.get("near_miss") or [])
    funnel = payload.get("filter_funnel") or {}
    ba = payload.get("best_action") or {}
    tb = str(ba.get("tradeability") or payload.get("tradeability") or "WAIT")
    deploy = int(
        funnel.get("deploy_qualified_setups")
        or funnel.get("execution_ready_setups")
        or 0
    )
    watch = int(funnel.get("watch_qualified_setups") or 0)
    pilot = int(ba.get("pilot_count") or 0)
    board_wait = deploy < 1 or tb.upper() in ("WAIT", "NO_TRADE")
    degraded = bool(
        payload.get("degraded")
        or payload.get("stale")
        or payload.get("instant_degraded")
        or str(payload.get("board_mode") or "").endswith("fallback")
    )
    ex = ba.get("execution_readiness") or {}
    broker_ready = str(ex.get("readiness_label") or "").lower() in (
        "ready",
        "connected",
        "paper_ready",
    )

    enriched: List[Dict[str, Any]] = []
    for row in opps:
        r = enrich_row_ladder_fields(dict(row))
        r["operator_insight"] = build_operator_insight(r, board_wait=board_wait)
        r["evidence_stack"] = build_evidence_stack(r)
        r["watch_intelligence"] = build_watch_intelligence_row(r)
        r["monitor_state"] = classify_monitor_state(r)
        enriched.append(r)
    payload["opportunities"] = enriched

    enriched_near: List[Dict[str, Any]] = []
    for row in near:
        r = enrich_row_ladder_fields(dict(row))
        r["operator_insight"] = build_operator_insight(r, board_wait=True)
        r["watch_intelligence"] = build_watch_intelligence_row(r)
        r["monitor_state"] = classify_monitor_state(r)
        if not r.get("whats_missing"):
            r["whats_missing"] = r["operator_insight"].get("blocker", "")
        enriched_near.append(r)
    payload["near_miss"] = enriched_near

    all_monitor = enriched + enriched_near
    payload["operator_board"] = build_operator_sections(enriched)
    payload["watch_queues"] = build_watch_queues(all_monitor)
    payload["watch_intelligence_summary"] = {
        "count": len(all_monitor),
        "alert_worthy": sum(
            1
            for r in all_monitor
            if (r.get("watch_intelligence") or {}).get("alert_worthy")
        ),
        "top_watch": sorted(
            [r.get("watch_intelligence") or {} for r in all_monitor],
            key=lambda x: -float(x.get("watch_score") or 0),
        )[:5],
    }
    payload["ai_vibe"] = build_ai_vibe(
        tradeability=tb,
        deploy_count=deploy,
        watch_count=watch,
        opportunities=enriched,
        regime_label=str((payload.get("market_regime") or {}).get("label") or ""),
    )
    payload["board_posture"] = build_board_posture(
        tradeability=tb,
        deploy_count=deploy,
        pilot_count=pilot,
        board_wait=board_wait,
    )
    payload["paper_automation"] = build_paper_automation_stub(enriched)
    payload["monitor_auto_actions"] = build_monitor_auto_actions(all_monitor)
    from src.services.operator_state_contract import build_playbook_rank_buckets

    payload["rank_buckets"] = build_playbook_rank_buckets(enriched, enriched_near)
    payload["auto_execution"] = build_auto_execution_stub(
        deploy_open=deploy >= 1,
        broker_ready=broker_ready,
        data_fresh=not degraded,
        degraded=degraded,
    )
    try:
        from src.services.buy_signal_summary import attach_buy_signal_to_rows

        payload["opportunities"] = attach_buy_signal_to_rows(payload.get("opportunities") or [])
        payload["near_miss"] = attach_buy_signal_to_rows(payload.get("near_miss") or [])
    except Exception:
        pass
    return payload
