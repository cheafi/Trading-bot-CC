"""
Instant agent integration — one message in, structured research out.

Inspired by AI-Trader agent hooks + Lean algorithm lifecycle (Initialize → Signal).
Monitoring / research only; never grants execution permission.
"""

from __future__ import annotations

from typing import Any

from src.services.copy_trading_paper import paper_copy_leaders
from src.services.signal_sync import build_sync_export
from src.services.vibe_agent import parse_vibe_intent


async def instant_agent_message(
    request,
    message: str,
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    text = str(message or "").strip()
    if not text:
        raise ValueError("message required")

    plan = parse_vibe_intent(text)
    tickers = plan.get("assets") or plan.get("tickers") or []
    debate: list[dict[str, Any]] = []
    consensus: dict[str, Any] | None = None

    if tickers:
        symbol = str(tickers[0]).upper()
        if not symbol.endswith("-USD") and symbol in {"BTC", "ETH", "SOL"}:
            symbol = f"{symbol}-USD"
        try:
            from src.api.routers.expert_committee_api import expert_committee_verdict

            verdict_payload = await expert_committee_verdict(symbol, request)
            consensus = verdict_payload.get("verdict")
            debate = [
                {
                    "expert": e.get("name"),
                    "stance": e.get("stance"),
                    "confidence": e.get("confidence"),
                }
                for e in (verdict_payload.get("experts") or [])
                if isinstance(e, dict)
            ]
        except Exception as exc:
            consensus = {"error": type(exc).__name__, "ticker": symbol}

    engine_recs = []
    engine = getattr(request.app.state, "engine", None)
    if engine:
        for rec in list(getattr(engine, "_cached_recommendations", []) or [])[:10]:
            if hasattr(rec, "to_dict"):
                engine_recs.append(rec.to_dict())
            elif isinstance(rec, dict):
                engine_recs.append(rec)

    sync = build_sync_export(engine_recs=engine_recs, agent_id=agent_id)
    copy_mirror = paper_copy_leaders(limit=5)

    return {
        "ok": True,
        "authority": "research_only",
        "execution_permission": False,
        "agent_id": agent_id or "anonymous",
        "message_received": text[:500],
        "intent_plan": plan,
        "collective_intelligence": {
            "debate": debate,
            "consensus": consensus,
            "note": "Multi-agent committee + Signal Board; not a trade instruction",
        },
        "signal_sync": sync,
        "paper_copy_mirror": copy_mirror,
        "markets": {
            "equity": True,
            "crypto": True,
            "forex": False,
            "options": False,
            "futures": False,
            "note": "Forex/options/futures: roadmap — use paper signals + external broker",
        },
        "lean_lifecycle_hint": {
            "initialize": "Load universe, set cash, attach data feeds",
            "on_data": "Consume sync envelope signals; gates decide orders",
            "on_end": "Export learning outcomes to /api/v7/ml/feedback/backtest",
        },
    }
