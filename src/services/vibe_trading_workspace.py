"""Vibe-Trading workspace — NL research → teams → composite backtest → memory."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from src.services.research_memory_recall import attach_session_recall

from src.services.composite_backtest import attach_run_card_to_draft, run_composite_backtest
from src.services.cross_market_loader import (
    fetch_cross_market_snapshots,
    resolve_symbols_from_prompt,
)
from src.services.research_safety import sanitize_research_payload
from src.services.research_store import save_backtest_run, save_memory_item, save_report
from src.services.strategy_builder import build_strategy_draft_record, parse_strategy_prompt
from src.services.vibe_agent import parse_vibe_intent
from src.services.vibe_trading_teams import run_trading_teams


def _system_state_from_request(request) -> Dict[str, Any]:
    today = getattr(request.app.state, "today_v7_cache", None) or {}
    payload: Dict[str, Any] = {}
    if isinstance(today, dict):
        payload = {"cc_state": today.get("cc_state")}
    try:
        from src.services.cc_state import attach_system_state

        attach_system_state(payload)
    except Exception:
        pass
    ss = payload.get("system_state") if isinstance(payload.get("system_state"), dict) else {}
    return ss or {}


async def run_vibe_workspace(
    request,
    prompt: str,
    *,
    regions: Optional[List[str]] = None,
    run_backtest: bool = True,
    persist: bool = True,
    as_of: Optional[str] = None,
    progress_callback: Optional[
        Callable[[Dict[str, str]], Union[None, Awaitable[None]]]
    ] = None,
) -> Dict[str, Any]:
    """Self-improving research session (persisted memory + run card when enabled)."""
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("prompt required")

    mds = request.app.state.market_data
    ss = _system_state_from_request(request)

    if progress_callback:
        res = progress_callback({"step": "intent", "detail": "Parsing NL prompt"})
        if res is not None and hasattr(res, "__await__"):
            await res

    intent = parse_vibe_intent(text)
    draft = build_strategy_draft_record(text)
    draft["source"] = "vibe_workspace"
    parsed = parse_strategy_prompt(text)
    symbols = resolve_symbols_from_prompt(text)
    if parsed.get("universe"):
        for u in parsed["universe"]:
            if u not in symbols:
                symbols.insert(0, u)
    symbols = symbols[:10]

    if progress_callback:
        res = progress_callback({"step": "cross_market", "detail": "Loading regions"})
        if res is not None and hasattr(res, "__await__"):
            await res
    market = await fetch_cross_market_snapshots(mds, regions=regions)
    composite: Optional[Dict[str, Any]] = None
    if run_backtest and symbols:
        if progress_callback:
            res = progress_callback({"step": "backtest", "detail": "Composite run card"})
            if res is not None and hasattr(res, "__await__"):
                await res
        pit = str(as_of).strip()[:10] if as_of else None
        composite = await run_composite_backtest(mds, symbols, as_of=pit)
        draft = attach_run_card_to_draft(draft, composite.get("run_card") or {})

    teams = await run_trading_teams(
        request,
        question=text,
        draft=draft,
        market_snapshots=market,
        system_state=ss,
        composite_backtest=composite,
        progress_callback=progress_callback,
    )

    self_improve = _self_improve_notes(intent, teams, composite)
    report_row: Optional[Dict[str, Any]] = None
    backtest_row: Optional[Dict[str, Any]] = None
    memory_row: Optional[Dict[str, Any]] = None

    if persist:
        memory_row = save_memory_item(
            {
                "type": "vibe_session",
                "prompt": text[:4000],
                "intent_type": intent.get("intent_type"),
                "consensus": teams.get("consensus"),
                "symbols": symbols,
                "lessons": self_improve,
            }
        )
        if composite and composite.get("run_card"):
            backtest_row = save_backtest_run(
                {
                    "source": "vibe_workspace",
                    "run_card": composite["run_card"],
                    "legs": composite.get("legs"),
                }
            )
        report_row = save_report(
            {
                "type": "vibe_team_report",
                "title": f"Vibe session · {text[:80]}",
                "teams": teams.get("teams"),
                "consensus": teams.get("consensus"),
                "draft_id": draft.get("id"),
            }
        )

    payload = sanitize_research_payload(
        {
            "ok": True,
            "authority": "research_only",
            "execution_permission": False,
            "prompt": text[:500],
            "intent": intent,
            "strategy_draft": draft,
            "cross_market": market,
            "composite_backtest": composite,
            "teams": teams,
            "self_improve": self_improve,
            "persisted": {
                "memory_id": (memory_row or {}).get("id"),
                "backtest_run_id": (backtest_row or {}).get("id"),
                "report_id": (report_row or {}).get("id"),
            }
            if persist
            else None,
            "exports": {
                "shadow_audit": "/api/v7/research/shadow",
                "strategy_pine": "/api/v7/research/strategy/export/pine",
                "signal_sync": "/api/v7/research/signals/sync/export",
            },
        }
    )
    return attach_session_recall(payload, text)


def _self_improve_notes(
    intent: Dict[str, Any],
    teams: Dict[str, Any],
    composite: Optional[Dict[str, Any]],
) -> List[str]:
    notes: List[str] = []
    consensus = teams.get("consensus")
    if consensus == "research_unfavorable":
        notes.append("Reduce size or WAIT — multi-team consensus unfavorable.")
    elif consensus == "monitor_only":
        notes.append("Continue monitoring; gates or data not ready for action.")
    if composite and not composite.get("ok"):
        notes.append("Repair market data for composite backtest legs.")
    if intent.get("intent_type") == "portfolio_risk":
        notes.append("Prioritize shadow journal vs rule-based ideal path.")
    if not notes:
        notes.append("Session logged — compare next run to prior memory entries.")
    return notes


def build_shadow_audit_export(shadow_run: Dict[str, Any]) -> Dict[str, Any]:
    """Exportable audit bundle for shadow analysis (no deploy authority)."""
    tags = shadow_run.get("behaviorTags") or shadow_run.get("behavior_tags") or []
    return sanitize_research_payload(
        {
            "schema": "cc.shadow_audit.v1",
            "id": shadow_run.get("id"),
            "sourceJournal": shadow_run.get("sourceJournal"),
            "behaviorTags": tags,
            "lessons": shadow_run.get("lessons") or [],
            "pnlDifference": shadow_run.get("pnlDifference"),
            "diagnostics": shadow_run.get("behaviorDiagnostics") or [],
            "strategy_code_hint": (
                "Export Pine/JSON from strategy draft after committee review."
            ),
            "authority": "research_only",
        }
    )
