"""
Research integrations — Lean / AI-Trader / backtrader inspired surfaces.

All endpoints are research or paper-only unless explicitly gated elsewhere.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.api.deps import optional_api_key, sanitize_for_json, verify_api_key
from src.api.deps import validate_ticker
from src.research.backtrader_bridge import run_sma_cross_backtest
from src.services.agent_instant_bus import instant_agent_message
from src.services.copy_trading_paper import paper_copy_leaders
from src.services.ml_research_feedback import apply_backtrader_outcomes
from src.services.research_store import list_shadow_runs
from src.services.signal_sync import build_sync_export, import_sync_payload
from src.services.alpha_manifest import load_manifest, manifest_summary
from src.services.alpha_zoo_cache import (
    cached_zoo_fresh,
    load_cached_zoo,
    refresh_alpha_zoo_cache,
)
from src.services.alpha_universe_bench import bench_alphas_universe
from src.services.alpha_zoo_bench import bench_alphas_for_ticker, bench_alphas_zoo
from src.services.broker_journal_parser import parse_broker_journal
from src.services.correlation_regime_timeline import build_correlation_regime_timeline
from src.services.research_document_reader import (
    analyze_image,
    read_document,
    read_documents_batch,
)
from src.services.research_skills import list_skills, upsert_skill
from src.services.research_console_bootstrap import bootstrap_research_console
from src.services.research_task_catalog import catalog_payload
from src.services.research_task_router import run_research_task
from src.services.im_research_bridge import dispatch_research_to_im
from src.services.institutional_intel import institutional_intel_bundle
from src.services.research_mcp_tools import mcp_tool_catalog
from src.services.strategy_export import export_mt5_mql5_stub, export_tdx_formula
from src.services.strategy_builder import build_strategy_draft_record
from src.services.vibe_trading_workspace import (
    build_shadow_audit_export,
    run_vibe_workspace,
)

router = APIRouter(prefix="/api/v7/research", tags=["research-integrations"])


class InstantAgentBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    agent_id: Optional[str] = Field(None, max_length=64)


class SignalImportBody(BaseModel):
    payload: dict[str, Any]


class VibeWorkspaceBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    regions: Optional[list[str]] = Field(
        None, description="US, HK, CRYPTO, UK, IN, KR, CA, FUTURES"
    )
    run_backtest: bool = True
    persist: bool = True


class ResearchTaskBody(BaseModel):
    task: str = Field(..., min_length=1, max_length=64)
    prompt: Optional[str] = Field(None, max_length=8000)
    payload: Optional[dict[str, Any]] = None
    im_channel: Optional[str] = Field(None, description="discord | roadmap channels")


class ImDispatchBody(BaseModel):
    task: str = Field(..., min_length=1, max_length=64)
    channel: str = Field("discord", max_length=32)
    result: dict[str, Any] = Field(default_factory=dict)


class DocumentReadBody(BaseModel):
    filename: str = Field(..., min_length=1, max_length=256)
    content_b64: str = Field(..., min_length=1)


class DocumentsBatchBody(BaseModel):
    files: list[dict[str, str]] = Field(..., max_length=5)


class ImageAnalyzeBody(BaseModel):
    filename: str = Field(..., min_length=1, max_length=256)
    content_b64: str = Field(..., min_length=1)
    question: Optional[str] = Field(None, max_length=2000)


class SkillUpsertBody(BaseModel):
    skill_id: Optional[str] = Field(None, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    task: str = Field(..., min_length=1, max_length=64)
    steps: list[str] = Field(default_factory=list, max_length=20)
    prompt_template: Optional[str] = Field(None, max_length=4000)


@router.get("/tasks/catalog")
async def research_tasks_catalog(_: bool = Depends(optional_api_key)) -> dict[str, Any]:
    return sanitize_for_json(catalog_payload())


@router.get("/console/bootstrap")
async def research_console_bootstrap(
    request: Request,
    refresh: bool = Query(False, description="Bypass 5m console cache"),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    """PM-grade Research Console context — one round trip for Strategy Lab."""
    return sanitize_for_json(
        await bootstrap_research_console(request, force_refresh=refresh)
    )


@router.post("/task")
async def research_task(
    request: Request,
    body: ResearchTaskBody,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    try:
        result = await run_research_task(
            request,
            task=body.task,
            prompt=body.prompt,
            payload=body.payload,
        )
        if body.im_channel:
            result["im_dispatch"] = await dispatch_research_to_im(
                result, task=body.task, channel=body.im_channel
            )
        return sanitize_for_json(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/im/dispatch")
async def research_im_dispatch(
    body: ImDispatchBody,
    _: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    return sanitize_for_json(
        await dispatch_research_to_im(
            body.result, task=body.task, channel=body.channel
        )
    )


@router.get("/mcp/tools")
async def research_mcp_tools(_: bool = Depends(optional_api_key)) -> dict[str, Any]:
    return sanitize_for_json(mcp_tool_catalog())


@router.get("/institutional/intel")
async def institutional_intel(
    ticker: str = Query("SPY"),
    factor_query: Optional[str] = Query(None),
    etf: Optional[str] = Query(None),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    sym = validate_ticker(ticker)
    return sanitize_for_json(
        await institutional_intel_bundle(
            ticker=sym, factor_query=factor_query, etf=etf
        )
    )


@router.post("/export/tdx")
async def export_tdx(body: dict[str, Any], _: bool = Depends(optional_api_key)) -> dict[str, Any]:
    draft = body.get("draft") if isinstance(body.get("draft"), dict) else None
    if not draft and body.get("prompt"):
        draft = build_strategy_draft_record(str(body.get("prompt")))
    if not draft:
        raise HTTPException(400, "draft or prompt required")
    return sanitize_for_json({"tdx": export_tdx_formula(draft), "authority": "research_only"})


@router.post("/export/mt5")
async def export_mt5(body: dict[str, Any], _: bool = Depends(optional_api_key)) -> dict[str, Any]:
    draft = body.get("draft") if isinstance(body.get("draft"), dict) else None
    if not draft and body.get("prompt"):
        draft = build_strategy_draft_record(str(body.get("prompt")))
    if not draft:
        raise HTTPException(400, "draft or prompt required")
    return sanitize_for_json(
        {"mql5": export_mt5_mql5_stub(draft), "authority": "research_only"}
    )


@router.websocket("/ws/session")
async def research_ws_session(websocket: WebSocket) -> None:
    """WebSocket research runtime — streams progress then result JSON."""
    await websocket.accept()
    try:
        msg = await websocket.receive_json()
        if not isinstance(msg, dict):
            await websocket.send_json({"step": "error", "detail": "invalid_payload"})
            return
        task = str(msg.get("task") or "ask_question")
        prompt = msg.get("prompt")
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        await websocket.send_json({"step": "accepted", "task": task})
        from types import SimpleNamespace

        app = getattr(websocket, "app", None) or websocket.scope.get("app")
        if app is None:
            await websocket.send_json({"step": "error", "detail": "app_state_unavailable"})
            return
        fake_request = SimpleNamespace(app=app)

        async def _progress(row: dict) -> None:
            await websocket.send_json(
                {
                    "event": "progress",
                    "phase": row.get("step"),
                    "detail": row.get("detail"),
                }
            )

        result = await run_research_task(
            fake_request,
            task=task,
            prompt=str(prompt) if prompt is not None else None,
            payload=payload,
            progress_callback=_progress,
        )
        await websocket.send_json({"step": "done", "result": result})
    except WebSocketDisconnect:
        return
    except ValueError as exc:
        await websocket.send_json({"step": "error", "detail": str(exc)})
    except Exception as exc:
        await websocket.send_json({"step": "error", "detail": type(exc).__name__})


@router.post("/documents/read")
async def documents_read_one(
    body: DocumentReadBody,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    try:
        return sanitize_for_json(
            read_document(filename=body.filename, content_b64=body.content_b64)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/documents/read-batch")
async def documents_read_batch(
    body: DocumentsBatchBody,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    return sanitize_for_json(read_documents_batch(body.files))


@router.post("/documents/analyze-image")
async def documents_analyze_image(
    body: ImageAnalyzeBody,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    try:
        return sanitize_for_json(
            analyze_image(
                filename=body.filename,
                content_b64=body.content_b64,
                question=body.question,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/journal/parse")
async def journal_parse(
    body: dict[str, Any],
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    return sanitize_for_json(
        parse_broker_journal(
            text=body.get("journal_text") or body.get("text"),
            fmt=body.get("fmt"),
            use_local_closed=bool(body.get("use_local_closed")),
            limit=int(body.get("limit") or 100),
        )
    )


@router.get("/skills")
async def research_skills_list(_: bool = Depends(optional_api_key)) -> dict[str, Any]:
    return sanitize_for_json({"skills": list_skills(), "authority": "research_only"})


@router.post("/skills")
async def research_skills_upsert(
    body: SkillUpsertBody,
    _: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        row = upsert_skill(
            skill_id=body.skill_id,
            name=body.name,
            task=body.task,
            steps=body.steps,
            prompt_template=body.prompt_template,
        )
        return sanitize_for_json({"skill": row})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/correlation/regime-timeline")
async def correlation_regime_timeline(
    request: Request,
    tickers: str = Query("SPY,QQQ,IWM,TLT,GLD,BTC-USD"),
    period: str = Query("6mo"),
    window: int = Query(40, ge=20, le=120),
    step: int = Query(5, ge=1, le=20),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    symbols = [validate_ticker(t.strip()) for t in tickers.split(",") if t.strip()]
    mds = request.app.state.market_data
    return sanitize_for_json(
        await build_correlation_regime_timeline(
            mds, symbols, period=period, window=window, step=step
        )
    )


@router.post("/alpha/bench")
async def alpha_bench(
    request: Request,
    ticker: str = Query("SPY"),
    period: str = Query("2y"),
    limit: int = Query(25, ge=1, le=120),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    sym = validate_ticker(ticker)
    mds = request.app.state.market_data
    return sanitize_for_json(
        await bench_alphas_for_ticker(mds, sym, period=period, limit=limit)
    )


@router.get("/alpha/manifest")
async def alpha_manifest(
    limit: int = Query(478, ge=1, le=478),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    return sanitize_for_json({**manifest_summary(), "sample": load_manifest(limit=min(limit, 50))})


@router.post("/alpha/bench-zoo")
async def alpha_bench_zoo(
    request: Request,
    ticker: str = Query("SPY"),
    period: str = Query("2y"),
    compute_limit: int = Query(478, ge=5, le=478),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    sym = validate_ticker(ticker)
    mds = request.app.state.market_data
    return sanitize_for_json(
        await bench_alphas_zoo(mds, sym, period=period, compute_limit=compute_limit)
    )


@router.get("/alpha/bench-zoo/latest")
async def alpha_bench_zoo_latest(_: bool = Depends(optional_api_key)) -> dict[str, Any]:
    row = load_cached_zoo()
    if not row:
        return sanitize_for_json(
            {
                "ok": False,
                "error": "no_cache",
                "hint": "POST /alpha/bench-zoo/refresh or run research_nightly_stub",
            }
        )
    return sanitize_for_json({**row, "fresh": cached_zoo_fresh()})


@router.post("/alpha/bench-zoo/refresh")
async def alpha_bench_zoo_refresh(
    request: Request,
    ticker: str = Query("SPY"),
    compute_limit: int = Query(478, ge=10, le=478),
    _: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    sym = validate_ticker(ticker)
    mds = request.app.state.market_data
    return sanitize_for_json(
        await refresh_alpha_zoo_cache(mds, ticker=sym, compute_limit=compute_limit)
    )


@router.post("/alpha/bench-universe")
async def alpha_bench_universe(
    request: Request,
    period: str = Query("1y"),
    tickers: Optional[str] = Query(None, description="Comma-separated; default Signal Board"),
    limit: int = Query(10, ge=1, le=25),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    mds = request.app.state.market_data
    syms = None
    if tickers:
        syms = [validate_ticker(t.strip()) for t in tickers.split(",") if t.strip()]
    return sanitize_for_json(
        await bench_alphas_universe(mds, tickers=syms, period=period, limit=limit)
    )


@router.post("/vibe/workspace")
async def vibe_workspace(
    request: Request,
    body: VibeWorkspaceBody,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    """Vibe-Trading style session: NL prompt → teams → composite run card → memory."""
    try:
        return sanitize_for_json(
            await run_vibe_workspace(
                request,
                body.prompt,
                regions=body.regions,
                run_backtest=body.run_backtest,
                persist=body.persist,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/backtest/composite")
async def backtest_composite(
    request: Request,
    tickers: str = Query(..., description="Comma-separated symbols"),
    period: str = Query("1y"),
    as_of: Optional[str] = Query(None, description="PIT truncate YYYY-MM-DD"),
    persist: bool = Query(False),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    from src.services.composite_backtest import run_composite_backtest
    from src.services.research_store import save_backtest_run

    symbols = [validate_ticker(t.strip()) for t in tickers.split(",") if t.strip()]
    if not symbols:
        raise HTTPException(400, "tickers required")
    mds = request.app.state.market_data
    result = await run_composite_backtest(mds, symbols, period=period, as_of=as_of)
    if persist and result.get("run_card"):
        saved = save_backtest_run(
            {"source": "composite_api", "run_card": result["run_card"], "legs": result.get("legs")}
        )
        result["saved_run_id"] = saved.get("id")
    return sanitize_for_json(result)


@router.get("/shadow/audit/{run_id}")
async def shadow_audit_export(
    run_id: str,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    for row in list_shadow_runs(limit=100):
        if str(row.get("id")) == run_id:
            return sanitize_for_json(build_shadow_audit_export(row))
    raise HTTPException(404, "shadow run not found")


@router.post("/agent/instant")
async def agent_instant(
    request: Request,
    body: InstantAgentBody,
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    """One message → intent plan + committee debate + signal sync envelope."""
    try:
        return sanitize_for_json(
            await instant_agent_message(
                request, body.message, agent_id=body.agent_id
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/signals/sync/export")
async def signals_sync_export(
    request: Request,
    agent_id: Optional[str] = Query(None),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    engine_recs = []
    engine = getattr(request.app.state, "engine", None)
    if engine:
        for rec in list(getattr(engine, "_cached_recommendations", []) or [])[:30]:
            if isinstance(rec, dict):
                engine_recs.append(rec)
            elif hasattr(rec, "to_dict"):
                engine_recs.append(rec.to_dict())
    return sanitize_for_json(
        build_sync_export(engine_recs=engine_recs, agent_id=agent_id)
    )


@router.post("/signals/sync/import")
async def signals_sync_import(
    body: SignalImportBody,
    _: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return sanitize_for_json(import_sync_payload(body.payload))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/copy-trading/paper-leaders")
async def copy_trading_paper_leaders(
    limit: int = Query(5, ge=1, le=20),
    notional: float = Query(100_000.0, ge=1000.0, le=10_000_000.0),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    return sanitize_for_json(paper_copy_leaders(limit=limit, notional=notional))


@router.post("/backtest/backtrader")
async def backtest_backtrader(
    request: Request,
    ticker: str = Query(...),
    period: str = Query("1y"),
    fast: int = Query(10, ge=3, le=50),
    slow: int = Query(30, ge=5, le=200),
    apply_ml: bool = Query(
        False, description="Nudge MetaEnsemble from aggregate backtest (research only)"
    ),
    _: bool = Depends(optional_api_key),
) -> dict[str, Any]:
    sym = validate_ticker(ticker)
    mds = request.app.state.market_data
    hist = await mds.get_history(sym, period=period, interval="1d")
    if hist is None or hist.empty:
        raise HTTPException(400, f"No history for {sym}")
    result = run_sma_cross_backtest(hist, fast=fast, slow=slow)
    if apply_ml and result.get("ok"):
        result["ml_feedback"] = apply_backtrader_outcomes(
            result, ticker=sym, strategy_id=result.get("strategy", "sma")
        )
    return sanitize_for_json(result)


@router.post("/ml/feedback/backtest")
async def ml_feedback_backtest(
    request: Request,
    ticker: str = Query("SPY"),
    period: str = Query("1y"),
    _: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    sym = validate_ticker(ticker)
    mds = request.app.state.market_data
    hist = await mds.get_history(sym, period=period, interval="1d")
    if hist is None or hist.empty:
        raise HTTPException(400, f"No history for {sym}")
    bt = run_sma_cross_backtest(hist)
    feedback = apply_backtrader_outcomes(bt, ticker=sym)
    return sanitize_for_json({"backtest": bt, "ml_feedback": feedback})
