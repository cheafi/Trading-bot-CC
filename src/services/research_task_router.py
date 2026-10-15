"""Route Vibe-Trading tasks to CC X research handlers."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.services.broker_journal_parser import parse_broker_journal
from src.services.research_skills import get_skill
from src.services.research_store import list_memory
from src.services.research_task_catalog import catalog_payload
from src.services.shadow_account import analyze_shadow_account
from src.services.strategy_builder import build_strategy_draft_record
from src.services.research_document_reader import read_documents_batch
from src.services.validation_lab import run_validation

ProgressCallback = Optional[Callable[[Dict[str, Any]], Awaitable[None]]]


async def _emit_progress(
    cb: ProgressCallback, step: str, detail: str = ""
) -> None:
    if cb:
        await cb({"step": step, "detail": detail})


def _merge_document_context(
    prompt: str, body: Dict[str, Any]
) -> tuple[str, Optional[Dict[str, Any]]]:
    files = body.get("files")
    if not isinstance(files, list) or not files:
        return prompt, None
    docs = read_documents_batch(files)
    chunks: List[str] = []
    for row in docs.get("files") or []:
        if isinstance(row, dict) and row.get("ok") and row.get("excerpt"):
            chunks.append(f"[{row.get('filename')}]\n{row['excerpt'][:2000]}")
    if not chunks:
        return prompt, docs
    merged = prompt + "\n\n--- Attached documents ---\n" + "\n".join(chunks)[:12000]
    return merged, docs


async def run_research_task(
    request,
    *,
    task: str,
    prompt: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    progress_callback: ProgressCallback = None,
) -> Dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    skill_id = body.get("skill_id")
    if skill_id:
        skill = get_skill(str(skill_id))
        if skill:
            task = str(skill.get("task") or task)
            if not prompt and skill.get("prompt_template"):
                prompt = str(skill["prompt_template"])

    t = str(task or "").strip().lower()
    await _emit_progress(progress_callback, "task", t)

    if t == "catalog":
        return catalog_payload()

    if t in ("ask_question", "ask", "analyst_teams"):
        from src.services.vibe_trading_workspace import run_vibe_workspace

        text = str(prompt or body.get("prompt") or "").strip()
        if not text:
            raise ValueError("prompt required")
        merged_prompt, docs = _merge_document_context(text, body)
        as_of = body.get("as_of")
        if as_of is not None:
            as_of = str(as_of).strip()[:10] or None
        await _emit_progress(progress_callback, "workspace", "Vibe workspace + teams")
        out = await run_vibe_workspace(
            request,
            merged_prompt,
            regions=body.get("regions"),
            run_backtest=bool(body.get("run_backtest", True)),
            persist=bool(body.get("persist", True)),
            as_of=as_of,
            progress_callback=progress_callback,
        )
        out["task"] = t
        if docs:
            out["documents"] = docs
        if t in ("ask_question", "ask"):
            prior = list_memory(limit=5, item_type="vibe_session")
            out["session_context"] = {"recent_memory": prior, "reusable": True}
        return out

    if t in ("backtest_idea", "backtest"):
        from src.services.composite_backtest import run_composite_backtest
        from src.services.cross_market_loader import resolve_symbols_from_prompt

        text = str(prompt or body.get("prompt") or "").strip()
        if not text:
            raise ValueError("prompt required")
        await _emit_progress(progress_callback, "intent", "Strategy draft")
        draft = build_strategy_draft_record(text)
        symbols = body.get("symbols") or resolve_symbols_from_prompt(text)
        mds = request.app.state.market_data
        as_of = body.get("as_of")
        if as_of is not None:
            as_of = str(as_of).strip()[:10] or None
        await _emit_progress(progress_callback, "backtest", "Composite + PIT context")
        composite = await run_composite_backtest(
            mds,
            symbols,
            period=str(body.get("period") or "1y"),
            as_of=as_of,
        )
        metrics = {}
        rc = composite.get("run_card") or {}
        if rc.get("aggregate_return_pct") is not None:
            metrics["total_return_pct"] = rc["aggregate_return_pct"]
        await _emit_progress(progress_callback, "validate", "Validation lab")
        validation = run_validation(strategy_draft=draft, backtest_metrics=metrics)
        from src.services.backtest_benchmark_context import attach_benchmark_to_backtest

        period = str(body.get("period") or "1y")
        bench = await attach_benchmark_to_backtest(
            mds, period=period, run_card=rc
        )
        from src.services.strategy_export import (
            export_mt5_mql5_stub,
            export_pine_draft,
            export_tdx_formula,
        )

        code = {
            "pine": export_pine_draft(
                name="CC_Research",
                entry_rules=draft.get("entryRules"),
                exit_rules=draft.get("exitRules"),
                regime_filters=draft.get("regimeFilters"),
            ),
            "tdx": export_tdx_formula(draft),
            "mt5_mql5": export_mt5_mql5_stub(draft),
        }
        return {
            "task": t,
            "strategy_draft": draft,
            "strategy_code": code,
            "composite_backtest": composite,
            "validation": validation,
            "validation_artifacts": validation.get("warnings"),
            "run_card": rc,
            "benchmark_context": bench,
            "authority": "research_only",
        }

    if t in ("review_trades", "shadow", "review"):
        await _emit_progress(progress_callback, "journal", "Parse broker journal")
        journal = parse_broker_journal(
            text=body.get("journal_text") or body.get("text"),
            fmt=body.get("fmt"),
            use_local_closed=bool(body.get("use_local_closed")),
            limit=int(body.get("limit") or 100),
        )
        trades = journal.get("trades") or []
        if not trades:
            raise ValueError("no trades parsed — provide journal_text or use_local_closed")
        await _emit_progress(progress_callback, "shadow", "Behavior vs rules")
        shadow = analyze_shadow_account(
            trades=trades,
            rules=journal.get("extracted_rules"),
            source=str(body.get("source") or journal.get("source") or "journal"),
        )
        return {
            "task": t,
            "journal": journal,
            "shadow": shadow,
            "authority": "research_only",
        }

    if t in ("institutional_intel", "institutional"):
        from src.services.institutional_intel import institutional_intel_bundle

        ticker = str(body.get("ticker") or prompt or "SPY").strip().upper()
        await _emit_progress(progress_callback, "institutional", ticker)
        return await institutional_intel_bundle(
            ticker=ticker,
            factor_query=body.get("factor_query"),
            etf=body.get("etf"),
        )

    if t == "alpha_zoo":
        from src.services.alpha_zoo_bench import bench_alphas_zoo

        mds = request.app.state.market_data
        ticker = str(body.get("ticker") or prompt or "SPY").strip().upper()
        limit = int(body.get("compute_limit") or 478)
        limit = max(5, min(limit, 478))
        await _emit_progress(
            progress_callback, "alpha_zoo", f"IC bench {limit}/478 on {ticker}"
        )
        return await bench_alphas_zoo(
            mds, ticker, period=str(body.get("period") or "2y"), compute_limit=limit
        )

    raise ValueError(f"unknown task: {task}")
