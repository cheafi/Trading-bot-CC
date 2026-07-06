"""Best Action Now — capital deployment summary for Playbook / Today surfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.utils.numeric_parse import parse_ratio

_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"})
_PILOT_ACTIONS = frozenset({"PILOT"})
_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"})
_AVOID_ACTIONS = frozenset({"AVOID", "NO_TRADE", "NO_TOUCH", "DO_NOT_TOUCH", "AVOID_NOW"})

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


def _sanitize_copy(
    text: str,
    *,
    deploy_blocked: bool = False,
    brief_expired: bool = False,
    stale: bool = False,
    source: str = "",
) -> str:
    try:
        from src.services.copy_safety import sanitize_for_render

        return sanitize_for_render(
            text,
            {
                "deploy_blocked": deploy_blocked,
                "blocked": deploy_blocked,
                "brief_expired": brief_expired or stale,
                "brief_freshness": "expired" if brief_expired else ("fallback" if "fallback" in (source or "") else "fresh"),
            },
        )
    except Exception:
        return text


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
            "Stale board context — rankings lack deploy authority",
        )
    if not opportunities:
        return "low", "No deploy-qualified setups in pipeline"
    badges = [str(o.get("evidence_badge") or "") for o in opportunities[:5]]
    if any("stale" in b for b in badges):
        return "low", "Stale brief context — not used for deploy decisions"
    avg_data = sum(float(o.get("data_conf") or 0.5) for o in opportunities[:5]) / min(
        5, len(opportunities)
    )
    if avg_data >= 0.7:
        return "medium", "Model output · cross-check live tape"
    return "low", "Raw model output · limited live validation"


def compute_theme_overlap(opportunities: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
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
    deploy_blocked: bool = False,
) -> tuple[str, str]:
    tradeability = (tradeability or "WAIT").upper()
    if deploy_blocked:
        return (
            "hold_cash",
            "Monitor only — deploy blocked; PILOT/WATCH labels are review-only.",
        )
    if not should_trade or tradeability == "NO_TRADE":
        return "hold_cash", "Regime gate closed — protect capital, no new risk."
    if execution_ready_count >= 1 and tradeability in ("STRONG_TRADE", "TRADE"):
        return (
            "deploy_selectively",
            f"{execution_ready_count} execution-ready — size only at 1R with bracket.",
        )
    if pilot_count >= 1 or tradeability == "SELECTIVE":
        return (
            "pilot_only",
            "PILOT / WATCH only — monitor candidates; no full-size deploy until gates clear.",
        )
    if tradeability == "WAIT":
        return (
            "hold_cash",
            "WAIT — no deploy-qualified setups (0 deploy-qualified until all gates pass). "
            "Monitor near-misses; pilot only after manual confirmation.",
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
    deploy_blocked: bool = False,
    brief_expired: bool = False,
) -> Dict[str, Any]:
    """Derive sticky Best Action Now payload from ranked opportunities."""
    tradeability = (tradeability or "WAIT").upper()

    best_trade = None
    best_pilot = None
    best_watch = None
    best_avoid = None
    trade_count = 0
    execution_ready_count = 0
    pilot_count = 0

    for o in opportunities:
        act = _norm_action(o.get("action"))
        tk = o.get("ticker")
        if not tk:
            continue
        conf = float(
            o.get("final_conf")
            or o.get("score", 0) / 10
            if o.get("score")
            else 0.6
        )
        if o.get("execution_ready"):
            execution_ready_count += 1
        if act in _TRADE_ACTIONS:
            trade_count += 1
            if not best_trade and o.get("execution_ready"):
                best_trade = {
                    "ticker": tk,
                    "action": "TRADE",
                    "confidence": round(conf, 2),
                    "entry_price": o.get("entry_price"),
                    "stop_price": o.get("stop_price"),
                    "risk_reward": o.get("risk_reward"),
                    "execution_ready": True,
                }
        if act in _PILOT_ACTIONS and not best_pilot:
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
        should_trade,
        execution_ready_count=execution_ready_count,
        pilot_count=pilot_count,
        deploy_blocked=deploy_blocked or stale or "fallback" in (source or "").lower(),
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
            exec_ready.get("trade_handoff_ready") or (ibkr_connected and bracket_ready)
        )
        exec_ready["ibkr_connected"] = ibkr_connected
        exec_ready["bracket_ready"] = bracket_ready
    except Exception:
        exec_ready = {
            "ibkr_connected": ibkr_connected,
            "mode": ibkr_mode or "paper",
            "bracket_ready": bracket_ready,
            "can_send_order": ibkr_connected and bracket_ready,
        }

    return {
        "capital_stance": capital_stance,
        "risk_posture": _CAPITAL_STANCE_LABELS.get(
            capital_stance, capital_stance.replace("_", " ").title()
        ),
        "stance_one_liner": _sanitize_copy(
            stance_liner,
            deploy_blocked=deploy_blocked,
            brief_expired=brief_expired,
            stale=stale,
            source=source,
        ),
        "best_trade_now": best_trade,
        "best_pilot_now": best_pilot,
        "best_watch_upgrade": best_watch,
        "best_avoid_now": best_avoid,
        "trade_count": trade_count,
        "execution_ready_count": execution_ready_count,
        "pilot_count": pilot_count,
        "evidence_quality": eq,
        "evidence_label": _sanitize_copy(
            eq_label,
            deploy_blocked=deploy_blocked,
            brief_expired=brief_expired,
            stale=stale,
            source=source,
        ),
        "decision_confidence": eq,
        "decision_confidence_label": _decision_confidence_label(
            eq,
            _sanitize_copy(
                eq_label,
                deploy_blocked=deploy_blocked,
                brief_expired=brief_expired,
                stale=stale,
                source=source,
            ),
        ),
        "execution_readiness": exec_ready,
        "regime_label": regime_label,
        "tradeability": tradeability,
        "data_freshness": "STALE" if stale else "FRESH",
        "as_of": as_of or datetime.now(timezone.utc).isoformat() + "Z",
    }


def enrich_ranked_payload(
    payload: Dict[str, Any],
    *,
    authority_first: bool = True,
) -> Dict[str, Any]:
    """Attach best_action + overlap_warning + truth model to playbook ranked."""
    opps = payload.get("opportunities") or []
    stale = bool(payload.get("stale"))
    source = str(payload.get("source") or "")
    tradeability_hint = str(
        payload.get("tradeability")
        or payload.get("board_tradeability")
        or ""
    ).upper()
    try:
        from src.services.ibkr_service import get_ibkr_service, ibkr_authority_gate_snapshot

        gates = ibkr_authority_gate_snapshot()
        ibkr_on = bool(gates.get("connected"))
        exec_blocked = bool(gates.get("circuit_breaker"))
        ibkr_mode = get_ibkr_service()._mode or "paper"
    except Exception:
        ibkr_on = False
        ibkr_mode = "paper"
        exec_blocked = False

    execution_ready_count = sum(1 for o in opps if o.get("execution_ready"))
    pilot_count = sum(1 for o in opps if _norm_action(o.get("action")) in _PILOT_ACTIONS)
    try:
        from src.services.decision_truth_model import compute_honest_tradeability

        tradeability = compute_honest_tradeability(
            should_trade=True,
            execution_ready=execution_ready_count,
            pilot_ready=pilot_count,
            council_high_8=len(
                [o for o in opps if float(o.get("score") or 0) >= 8.0]
            ),
            macro="Neutral",
            opportunity=(
                "Strong"
                if execution_ready_count >= 2
                else "Mixed"
                if execution_ready_count >= 1 or pilot_count >= 1
                else "Weak"
            ),
        )
    except ImportError:
        tradeability = (
            "TRADE"
            if execution_ready_count >= 1
            else "SELECTIVE"
            if pilot_count >= 1
            else "WAIT"
        )
    if tradeability_hint:
        tradeability = tradeability_hint

    board_mode = str(payload.get("board_mode") or "").lower()
    fallback_brief = (
        board_mode == "compressed_fallback"
        or "brief" in source
        or "fallback" in source
    )
    try:
        from src.services.decision_truth_model import build_decision_authority
        from src.services.index_regime import build_index_regime_summary
        from src.services.ranked_board_pipeline import enrich_ranked_board_rows

        authority = build_decision_authority(
            tradeability=tradeability if not fallback_brief else "WAIT",
            should_trade=not fallback_brief,
            scanner_degraded=stale or fallback_brief,
            data_stale=stale,
            fallback_brief=fallback_brief,
            broker_offline=not ibkr_on,
            engine_off=False,
            exec_blocked=exec_blocked,
            ranked_source=source,
            ranked_stale=stale,
            deploy_ideas_count=execution_ready_count,
        )
        payload["decision_authority"] = authority
        index_regime = build_index_regime_summary(
            tradeability=tradeability or "WAIT",
            should_trade=tradeability not in ("NO_TRADE", "WAIT"),
            degraded=stale or "fallback" in source,
        )
        payload["index_regime_summary"] = index_regime
        mr = payload.get("market_regime") or {}
        market_regime = {
            "trend": mr.get("trend") or payload.get("trend") or "SIDEWAYS",
            "tradeability": tradeability,
            "breadth": mr.get("breadth"),
            "vix": mr.get("vix"),
            "should_trade": mr.get("should_trade", not fallback_brief),
        }
        opps = enrich_ranked_board_rows(
            opps,
            decision_authority=authority,
            index_regime=index_regime,
            tradeability=tradeability,
            market_regime=market_regime,
            event_risks=list(payload.get("event_risks") or []),
            authority_first=authority_first,
        )
        payload["opportunities"] = opps
    except Exception:
        pass

    payload["overlap_warning"] = compute_theme_overlap(opps)
    trade_count = sum(1 for o in opps if _norm_action(o.get("action")) in _TRADE_ACTIONS)
    execution_ready_count = sum(1 for o in opps if o.get("execution_ready"))
    pilot_count = sum(1 for o in opps if _norm_action(o.get("action")) in _PILOT_ACTIONS)
    payload["best_action"] = build_best_action(
        opps,
        tradeability=tradeability,
        should_trade=True,
        ibkr_connected=ibkr_on,
        ibkr_mode=ibkr_mode,
        source=source,
        stale=stale,
        deploy_blocked=not ibkr_on or stale or fallback_brief,
        brief_expired=bool(payload.get("brief_expired")),
    )
    _near_miss_missing = (
        "stronger timing, confirmed volume follow-through, "
        "monitor-pipeline support, and execution-ready status"
    )
    _near_miss_horizon = "next 1–3 sessions if conditions improve"
    payload["near_miss"] = []
    for o in opps:
        if _norm_action(o.get("action")) not in _WATCH_ACTIONS:
            continue
        if float(o.get("score") or 0) < 6.0 or o.get("execution_ready"):
            continue
        nm = dict(o)
        if not nm.get("whats_missing") and not nm.get("gaps"):
            nm["whats_missing"] = _near_miss_missing
        if not nm.get("timing_bucket"):
            nm["timing_bucket"] = _near_miss_horizon
        payload["near_miss"].append(nm)
        if len(payload["near_miss"]) >= 8:
            break
    if payload["near_miss"]:
        payload["near_miss"] = sorted(
            payload["near_miss"],
            key=lambda r: (
                len(r.get("gaps") or []),
                -float(r.get("net_edge_score") or r.get("score") or 0),
            ),
        )[:8]
    try:
        from src.services.decision_truth_model import (
            build_avoid_grouped_from_rows,
            build_bucket_quality_from_rows,
        )

        payload["avoid_grouped"] = build_avoid_grouped_from_rows(opps)
        payload["bucket_quality"] = build_bucket_quality_from_rows(opps)
    except ImportError:
        pass
    return payload
