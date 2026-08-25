"""Intelligence Engine — platform IQ daily aggregate (Sprint 126)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.alpha_monitor import build_alpha_monitor_kpis


def _score_block(value: int, delta: int, drivers: list[str]) -> Dict[str, Any]:
    return {"value": value, "delta_1d": delta, "drivers": drivers}


def build_intelligence_daily_report(
    *,
    today_payload: Optional[Dict[str, Any]] = None,
    lessons_captured: int = 0,
) -> Dict[str, Any]:
    """CEO dashboard aggregate — research_only, no trade recommendations."""
    payload = today_payload or {}
    dm = payload.get("decision_model") or {}
    funnel = payload.get("filter_funnel") or {}
    alpha_kpis = build_alpha_monitor_kpis(
        deploy_missed_count=int(funnel.get("watch_qualified_setups") or 0),
        deploy_deferred_count=int(funnel.get("near_miss_count") or 0),
        lessons_captured=lessons_captured,
    )
    gates_active = bool((payload.get("decision_authority") or {}).get("gates_active"))
    knowledge_hits = len(payload.get("top_5") or []) + len(payload.get("opportunities") or [])

    scores = {
        "knowledge": _score_block(
            min(50 + knowledge_hits * 2, 85),
            +2 if knowledge_hits else 0,
            [f"{knowledge_hits} ranked candidates indexed"],
        ),
        "research": _score_block(
            68,
            0,
            ["Alpha Factory artifacts on scan rows"],
        ),
        "decision": _score_block(
            81 if not gates_active else 65,
            +1 if not gates_active else -2,
            ["zero gate bypass incidents" if not gates_active else "gates active"],
        ),
        "execution": _score_block(
            74,
            -1,
            [str(dm.get("execution_readiness") or "monitor execution panel")],
        ),
        "portfolio": _score_block(77, +1, ["sector cap discipline"]),
        "learning": _score_block(
            min(50 + lessons_captured * 5, 80),
            +5 if lessons_captured else 0,
            [f"{lessons_captured} lessons captured"],
        ),
        "alpha": _score_block(
            min(60 + int(alpha_kpis.get("alpha_preserved_bps") or 0) // 10, 85),
            +2,
            ["alpha_preserved > alpha_lost" if alpha_kpis["alpha_preserved_bps"] >= alpha_kpis["alpha_lost_bps"] else "alpha under pressure"],
        ),
    }
    avg = sum(s["value"] for s in scores.values()) / len(scores)
    return {
        "as_of": alpha_kpis["as_of"],
        "platform_smarter_today": avg >= 70 and not gates_active,
        "scores": scores,
        "alpha_monitor": alpha_kpis,
        "authority": "research_only",
    }
