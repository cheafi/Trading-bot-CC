"""Research pipeline API — Strategy Lab, Shadow Account, Reports (no deploy authority)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from src.api.deps import optional_api_key, sanitize_for_json
from src.services.cc_state import attach_page_capability, attach_system_state
from src.services.reports_library import create_report_from_shadow, export_report, list_reports as list_report_rows
from src.services.research_committee import run_committee_review
from src.services.research_pipeline import run_research_pipeline
from src.services.research_safety import pipeline_step_labels, research_safety_contract
from src.services.research_store import (
    get_report,
    get_strategy_draft,
    list_backtest_runs,
    list_memory,
    list_shadow_runs,
    list_strategy_drafts,
    save_shadow_run,
    save_strategy_draft,
)
from src.services.shadow_account import analyze_shadow_account
from src.services.strategy_builder import build_strategy_draft_record, parse_strategy_prompt
from src.services.strategy_export import export_pine_draft, export_python_pseudo, export_strategy_contract_json
from src.services.validation_lab import run_validation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v7/research", tags=["research-pipeline"])


def _system_state_from_request(request: Request) -> Dict[str, Any]:
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    payload: Dict[str, Any] = {}
    if isinstance(today, dict):
        payload = {"cc_state": today.get("cc_state")}
    try:
        attach_system_state(payload)
    except Exception:
        payload["system_state"] = {}
    return payload.get("system_state") or {}


def _attach_capability(payload: Dict[str, Any], tab: str, request: Request) -> None:
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    if isinstance(today, dict) and today.get("cc_state"):
        payload.setdefault("cc_state", today.get("cc_state"))
    attach_system_state(payload)
    attach_page_capability(payload, tab)


@router.get("/contract")
async def get_contract(surface: str = "research", _=optional_api_key):
    return sanitize_for_json(research_safety_contract(surface=surface))


@router.get("/pipeline/steps")
async def get_pipeline_steps(_=optional_api_key):
    return sanitize_for_json(
        {"steps": pipeline_step_labels(), "safety": research_safety_contract(surface="strategy-lab")}
    )


@router.post("/strategy/parse")
async def post_strategy_parse(body: Dict[str, Any], _=optional_api_key):
    prompt = str((body or {}).get("prompt") or "").strip()
    if not prompt or len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="prompt required (max 4000 chars)")
    draft = parse_strategy_prompt(prompt)
    return sanitize_for_json({"draft": draft, "safety": research_safety_contract(surface="strategy-lab")})


@router.post("/strategy")
async def post_strategy_save(body: Dict[str, Any], _=optional_api_key):
    prompt = str((body or {}).get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    draft = save_strategy_draft(build_strategy_draft_record(prompt))
    return sanitize_for_json({"draft": draft, "safety": research_safety_contract(surface="strategy-lab")})


@router.get("/strategy")
async def get_strategies(limit: int = 30, _=optional_api_key):
    return sanitize_for_json(
        {"drafts": list_strategy_drafts(limit=limit), "safety": research_safety_contract(surface="strategy-lab")}
    )


@router.get("/strategy/{draft_id}")
async def get_strategy(draft_id: str, _=optional_api_key):
    draft = get_strategy_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return sanitize_for_json({"draft": draft})


@router.post("/validate")
async def post_validate(body: Dict[str, Any], request: Request, _=optional_api_key):
    draft_id = str((body or {}).get("draft_id") or "").strip()
    draft = get_strategy_draft(draft_id) if draft_id else None
    if not draft and (body or {}).get("draft"):
        draft = (body or {}).get("draft")
    if not draft:
        raise HTTPException(status_code=400, detail="draft_id or draft required")
    ss = _system_state_from_request(request)
    metrics = (body or {}).get("metrics") if isinstance((body or {}).get("metrics"), dict) else {}
    validation = run_validation(
        strategy_draft=draft,
        backtest_metrics=metrics,
        data_quality=str(ss.get("data_freshness") or "FRESH"),
        system_state=ss,
    )
    from src.services.reports_library import create_report_from_validation

    report = create_report_from_validation(validation, strategy_draft=draft, authority_state=ss)
    if validation.get("verdict") in ("Overfit risk", "Retire / do not use") or any(
        "stale" in str(w).lower() for w in (validation.get("warnings") or [])
    ):
        try:
            from src.notifications.discord_dispatch import push_notice

            push_notice(
                title=f"Strategy validation · {validation.get('verdict')}",
                message="\n".join(validation.get("warnings") or [])[:500],
                severity="warning",
                event_type="validation",
                meta={"draft_id": draft.get("id")},
            )
        except Exception:
            pass
    payload = {"validation": validation, "report": report, "safety": research_safety_contract()}
    _attach_capability(payload, "strategy-lab", request)
    return sanitize_for_json(payload)


@router.post("/pipeline")
async def post_pipeline(body: Dict[str, Any], request: Request, _=optional_api_key):
    prompt = str((body or {}).get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    ss = _system_state_from_request(request)
    metrics = (body or {}).get("metrics") if isinstance((body or {}).get("metrics"), dict) else None
    steps = (body or {}).get("steps") if isinstance((body or {}).get("steps"), list) else None
    result = run_research_pipeline(prompt=prompt, system_state=ss, backtest_metrics=metrics, steps=steps)
    payload = {**result, "safety": research_safety_contract(surface="strategy-lab")}
    _attach_capability(payload, "strategy-lab", request)
    return sanitize_for_json(payload)


@router.post("/committee/review")
async def post_committee(body: Dict[str, Any], request: Request, _=optional_api_key):
    subject = (body or {}).get("subject") if isinstance((body or {}).get("subject"), dict) else {}
    if not subject and (body or {}).get("draft_id"):
        subject = get_strategy_draft(str(body.get("draft_id"))) or {}
    if not subject:
        raise HTTPException(status_code=400, detail="subject or draft_id required")
    ss = _system_state_from_request(request)
    review = run_committee_review(subject=subject, system_state=ss)
    return sanitize_for_json({"review": review, "safety": research_safety_contract()})


@router.post("/shadow/analyze")
async def post_shadow(body: Dict[str, Any], request: Request, _=optional_api_key):
    trades = (body or {}).get("trades")
    if not isinstance(trades, list) or not trades:
        raise HTTPException(status_code=400, detail="trades list required")
    source = str((body or {}).get("source") or "manual_journal")
    analysis = analyze_shadow_account(trades=trades, source=source)
    saved = save_shadow_run(analysis)
    analysis["id"] = saved["id"]
    ss = _system_state_from_request(request)
    report = create_report_from_shadow(analysis, authority_state=ss)
    tags = analysis.get("behaviorTags") or []
    if tags:
        try:
            from src.notifications.discord_dispatch import push_notice

            push_notice(
                title="Shadow Account · 行為診斷",
                message="\n".join(analysis.get("lessons") or tags),
                severity="warning" if any(
                    t in tags
                    for t in (
                        "revenge_trading",
                        "chasing_extension",
                        "average_down_without_rule",
                    )
                )
                else "info",
                event_type="shadow_analysis",
                meta={"tags": ", ".join(tags), "pnl_delta": analysis.get("pnlDifference")},
            )
        except Exception:
            pass
    payload = {"shadow": analysis, "report": report, "safety": research_safety_contract(surface="shadow")}
    _attach_capability(payload, "shadow", request)
    return sanitize_for_json(payload)


@router.get("/shadow")
async def get_shadow_runs(limit: int = 20, _=optional_api_key):
    return sanitize_for_json(
        {"runs": list_shadow_runs(limit=limit), "safety": research_safety_contract(surface="shadow")}
    )


@router.get("/reports")
async def get_reports(request: Request, limit: int = 30, _=optional_api_key):
    payload = {"reports": list_report_rows(limit=limit), "safety": research_safety_contract(surface="reports")}
    _attach_capability(payload, "reports", request)
    return sanitize_for_json(payload)


@router.get("/reports/{report_id}")
async def get_report_detail(report_id: str, _=optional_api_key):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return sanitize_for_json({"report": report, "safety": research_safety_contract(surface="reports")})


@router.get("/reports/{report_id}/export")
async def get_report_export(report_id: str, fmt: str = "markdown", _=optional_api_key):
    content = export_report(report_id, fmt)
    if not content:
        raise HTTPException(status_code=404, detail="Report not found")
    media = "text/markdown" if fmt == "markdown" else "application/json" if fmt == "json" else "text/html"
    if fmt == "pine":
        media = "text/plain"
    return PlainTextResponse(content=content, media_type=media)


@router.get("/memory")
async def get_memory(limit: int = 50, item_type: Optional[str] = None, _=optional_api_key):
    return sanitize_for_json(
        {"memory": list_memory(limit=limit, item_type=item_type), "safety": research_safety_contract()}
    )


@router.get("/backtest-runs")
async def get_backtest_runs(limit: int = 30, _=optional_api_key):
    return sanitize_for_json({"runs": list_backtest_runs(limit=limit)})


@router.post("/export/pine")
async def post_export_pine(body: Dict[str, Any], _=optional_api_key):
    draft = (body or {}).get("draft") if isinstance((body or {}).get("draft"), dict) else {}
    if not draft and (body or {}).get("draft_id"):
        draft = get_strategy_draft(str(body.get("draft_id"))) or {}
    if not draft:
        raise HTTPException(status_code=400, detail="draft or draft_id required")
    code = draft.get("generatedCode") or export_pine_draft(
        entry_rules=draft.get("entryRules"),
        exit_rules=draft.get("exitRules"),
        regime_filters=draft.get("regimeFilters"),
    )
    if "RESEARCH DRAFT ONLY" not in code:
        code = export_pine_draft(
            entry_rules=draft.get("entryRules"),
            exit_rules=draft.get("exitRules"),
            regime_filters=draft.get("regimeFilters"),
        )
    return sanitize_for_json({"pine": code, "safety": research_safety_contract()})
