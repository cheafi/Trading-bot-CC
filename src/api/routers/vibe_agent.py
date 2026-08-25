"""Vibe Agent API — monitoring / journaling only (no deploy authority)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from src.api.deps import optional_api_key, sanitize_for_json
from src.services.cc_state import attach_page_capability, attach_system_state
from src.services.vibe_agent import (
    agent_status,
    create_calm_down_guardrail,
    evaluate_watch_rules,
    generate_overnight_brief,
    parse_vibe_intent,
    persist_intent_and_rules,
    review_agent_outcome,
)
from src.services.vibe_agent_store import list_alerts, list_journal, list_intents, list_rules, save_rule, update_alert, update_rule
from src.services.vibe_agent_safety import agent_safety_contract

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/vibe-agent", tags=["vibe-agent"])


def _system_state_from_request(request: Request) -> Dict[str, Any]:
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    payload: Dict[str, Any] = {}
    if isinstance(today, dict):
        payload = {
            "cc_state": today.get("cc_state"),
            "decision_authority": today.get("decision_authority"),
            "trust": today.get("trust"),
            "execution_readiness": today.get("execution_readiness"),
        }
    try:
        attach_system_state(payload)
    except Exception:
        payload["system_state"] = {}
    return payload.get("system_state") or {}


def _playbook_state(request: Request) -> Dict[str, Any]:
    cache = getattr(request.app.state, "playbook_ranked_cache", None)
    if isinstance(cache, dict):
        buckets = cache.get("rank_buckets") or {}
        return {
            "monitor_rows": buckets.get("monitor_rows") or [],
            "near_miss": cache.get("near_miss") or [],
        }
    return {}


@router.get("/contract")
async def get_contract(_=optional_api_key):
    return sanitize_for_json(agent_safety_contract())


@router.get("/status")
async def get_status(request: Request, paused: bool = False, _=optional_api_key):
    ss = _system_state_from_request(request)
    body = agent_status(system_state=ss, paused=paused)
    body["safety"] = agent_safety_contract()
    return sanitize_for_json(body)


@router.get("/overnight-brief")
async def get_overnight_brief(request: Request, _=optional_api_key):
    ss = _system_state_from_request(request)
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    brief = generate_overnight_brief(
        system_state=ss,
        today_payload=today if isinstance(today, dict) else {},
        alerts=list_alerts(limit=10),
    )
    payload: Dict[str, Any] = {
        "brief": brief,
        "safety": agent_safety_contract(),
        "cc_state": today.get("cc_state") if isinstance(today, dict) else None,
    }
    attach_system_state(payload)
    attach_page_capability(payload, "agent")
    return sanitize_for_json(payload)


@router.post("/intent/parse")
async def post_parse_intent(body: Dict[str, Any], _=optional_api_key):
    text = str((body or {}).get("text") or "").strip()
    if not text or len(text) > 2000:
        raise HTTPException(status_code=400, detail="text required (max 2000 chars)")
    plan = parse_vibe_intent(text)
    return sanitize_for_json({"plan": plan, "safety": agent_safety_contract()})


@router.post("/intent")
async def post_intent(body: Dict[str, Any], _=optional_api_key):
    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    result = persist_intent_and_rules(text)
    return sanitize_for_json({**result, "safety": agent_safety_contract()})


@router.get("/intents")
async def get_intents(_=optional_api_key):
    return sanitize_for_json({"intents": list_intents(), "safety": agent_safety_contract()})


@router.get("/rules")
async def get_rules(status: Optional[str] = None, _=optional_api_key):
    return sanitize_for_json({"rules": list_rules(status=status), "safety": agent_safety_contract()})


@router.post("/rules")
async def post_rule(body: Dict[str, Any], _=optional_api_key):
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body required")
    rule = save_rule(
        {
            **body,
            "authorityEffect": "none",
            "action": "alert_only",
            "confirmationRequired": True,
            "status": body.get("status") or "active",
        }
    )
    return sanitize_for_json({"rule": rule, "safety": agent_safety_contract()})


@router.patch("/rules/{rule_id}")
async def patch_rule(rule_id: str, body: Dict[str, Any], _=optional_api_key):
    updated = update_rule(rule_id, body or {})
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    return sanitize_for_json({"rule": updated})


@router.get("/evaluate")
async def get_evaluate(request: Request, _=optional_api_key):
    ss = _system_state_from_request(request)
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    freshness = (today.get("trust") or {}) if isinstance(today, dict) else {}
    result = evaluate_watch_rules(
        system_state=ss,
        market_data={"worst_tier": ss.get("data_freshness")},
        playbook_state=_playbook_state(request),
        portfolio_state={},
    )
    return sanitize_for_json({**result, "safety": agent_safety_contract()})


@router.get("/alerts")
async def get_alerts(limit: int = 50, _=optional_api_key):
    return sanitize_for_json({"alerts": list_alerts(limit=limit), "safety": agent_safety_contract()})


@router.patch("/alerts/{alert_id}")
async def patch_alert(alert_id: str, body: Dict[str, Any], _=optional_api_key):
    updated = update_alert(alert_id, body or {})
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return sanitize_for_json({"alert": updated})


@router.get("/journal")
async def get_journal(limit: int = 100, _=optional_api_key):
    return sanitize_for_json({"journal": list_journal(limit=limit), "safety": agent_safety_contract()})


@router.post("/guardrail")
async def post_guardrail(body: Dict[str, Any], request: Request, _=optional_api_key):
    action_type = str((body or {}).get("action_type") or "").strip()
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type required")
    ss = _system_state_from_request(request)
    ctx = (body or {}).get("context") if isinstance((body or {}).get("context"), dict) else {}
    return sanitize_for_json(
        create_calm_down_guardrail(action_type, system_state=ss, context=ctx)
    )


@router.post("/review-outcome")
async def post_review_outcome(body: Dict[str, Any], _=optional_api_key):
    alert_id = str((body or {}).get("alert_id") or "").strip()
    if not alert_id:
        raise HTTPException(status_code=400, detail="alert_id required")
    return sanitize_for_json(
        review_agent_outcome(
            alert_id,
            user_action=str((body or {}).get("user_action") or "ignored"),
            outcome_1d=(body or {}).get("outcome_1d"),
            outcome_5d=(body or {}).get("outcome_5d"),
            outcome_20d=(body or {}).get("outcome_20d"),
            lesson=str((body or {}).get("lesson") or ""),
        )
    )
