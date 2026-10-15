"""Multi-agent trading teams — investment, quant, crypto, risk (research only)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

ProgressCb = Optional[Callable[[Dict[str, str]], Union[None, Awaitable[None]]]]

from src.services.research_committee import run_committee_review
from src.services.research_safety import sanitize_research_payload


def _progress(step: str, detail: str) -> Dict[str, str]:
    return {"step": step, "detail": detail}


async def run_trading_teams(
    request,
    *,
    question: str,
    draft: Dict[str, Any],
    market_snapshots: Dict[str, Any],
    system_state: Optional[Dict[str, Any]] = None,
    composite_backtest: Optional[Dict[str, Any]] = None,
    progress_callback: ProgressCb = None,
) -> Dict[str, Any]:
    """Multi-team deliberation with persisted-friendly structure."""
    ss = system_state or {}
    progress: List[Dict[str, str]] = []
    teams: List[Dict[str, Any]] = []

    async def _emit(step: str, detail: str) -> None:
        row = _progress(step, detail)
        progress.append(row)
        if progress_callback:
            res = progress_callback(row)
            if res is not None and hasattr(res, "__await__"):
                await res

    await _emit("investment", "Regime + committee on strategy draft")
    committee = run_committee_review(subject=draft, system_state=ss)
    teams.append(
        {
            "id": "investment",
            "label": "Investment team · 投資",
            "stance": committee.get("researchConsensus") or "monitor_only",
            "report": committee.get("summaryEn") or committee.get("summaryZh") or "",
            "agents": committee.get("agents") or [],
            "evidence": [
                f"Universe: {', '.join((draft.get('universe') or [])[:5])}",
                f"Tradeability: {ss.get('tradeability') or 'UNKNOWN'}",
            ],
        }
    )

    await _emit("quant", "Backtest leg summary")
    quant_evidence: List[str] = []
    quant_stance = "neutral"
    if composite_backtest and composite_backtest.get("ok"):
        rc = composite_backtest.get("run_card") or {}
        quant_evidence.append(
            f"Composite return {rc.get('aggregate_return_pct')}% "
            f"({rc.get('ok_count')}/{rc.get('leg_count')} legs)"
        )
        agg = rc.get("aggregate_return_pct")
        if agg is not None and float(agg) > 0:
            quant_stance = "support"
        elif agg is not None and float(agg) < -5:
            quant_stance = "contradiction"
    else:
        quant_evidence.append("No composite backtest — run with run_backtest=true")
        quant_stance = "insufficient_data"
    teams.append(
        {
            "id": "quant",
            "label": "Quant team · 量化",
            "stance": quant_stance,
            "report": "SMA cross composite on draft universe (research engine).",
            "evidence": quant_evidence,
            "legs": (composite_backtest or {}).get("legs") or [],
        }
    )

    await _emit("crypto", "Signal Board crypto leaders")
    crypto_rows: List[Dict[str, Any]] = []
    crypto_stance = "neutral"
    try:
        from src.services.signal_board import get_latest

        board = get_latest()
        for bucket in ("strong_buy", "buy", "watch"):
            for row in (board.get("buckets") or {}).get(bucket) or []:
                if not isinstance(row, dict):
                    continue
                t = str(row.get("ticker") or "")
                if t.endswith("-USD") or t in {"BTC-USD", "ETH-USD"}:
                    crypto_rows.append(
                        {
                            "ticker": t,
                            "score": row.get("score"),
                            "setup": row.get("setup"),
                            "side": row.get("side"),
                        }
                    )
        crypto_rows = crypto_rows[:8]
        if crypto_rows:
            crypto_stance = "support" if len(crypto_rows) >= 2 else "monitor"
    except Exception:
        crypto_stance = "data_unavailable"
    teams.append(
        {
            "id": "crypto",
            "label": "Crypto team · 加密",
            "stance": crypto_stance,
            "report": "Paper signals from Signal Board — not live crypto orders.",
            "evidence": [f"{r['ticker']} score={r.get('score')}" for r in crypto_rows[:5]],
            "leaders": crypto_rows,
        }
    )

    await _emit("macro", "Regime + cross-market context")
    macro_stance = "monitor"
    macro_evidence: List[str] = []
    try:
        from src.services.regime_service import RegimeService

        snap = RegimeService.get()
        label = str(
            (snap or {}).get("label")
            or (snap or {}).get("regime")
            or (snap or {}).get("regime_label")
            or "UNKNOWN"
        )
        macro_evidence.append(f"regime={label}")
        vix = (snap or {}).get("vix") or (snap or {}).get("vix_level")
        if vix is not None:
            macro_evidence.append(f"vix={vix}")
        if "RISK_ON" in label.upper():
            macro_stance = "support"
        elif "RISK_OFF" in label.upper() or "CRISIS" in label.upper():
            macro_stance = "contradiction"
    except Exception:
        macro_evidence.append("regime_service_unavailable")
    for region, rows in (market_snapshots.get("regions") or {}).items():
        ok_rows = [r for r in rows if isinstance(r, dict) and r.get("ok")]
        if ok_rows:
            macro_evidence.append(
                f"{region} avg ret {ok_rows[0].get('period_return_pct')}%"
            )
    teams.append(
        {
            "id": "macro",
            "label": "Macro team · 宏觀",
            "stance": macro_stance,
            "report": "Descriptive regime + regional return context — not a timing signal.",
            "evidence": macro_evidence[:8],
        }
    )

    await _emit("risk", "Gates + shadow journal hints")
    tb = str(ss.get("tradeability") or "WAIT").upper()
    risk_stance = "support" if tb in ("TRADE", "CAUTIOUS") else "contradiction"
    shadow_hint = _latest_shadow_lesson()
    teams.append(
        {
            "id": "risk",
            "label": "Risk team · 風控",
            "stance": risk_stance,
            "report": "Deploy blocked when tradeability is WAIT/NO_TRADE.",
            "evidence": [
                f"tradeability={tb}",
                f"deploy_open={ss.get('deploy_open')}",
                shadow_hint,
            ],
            "market_regions_loaded": list(
                (market_snapshots.get("regions") or {}).keys()
            ),
        }
    )

    support = len([t for t in teams if t.get("stance") == "support"])
    block = len([t for t in teams if t.get("stance") == "contradiction"])
    overall = "research_favorable" if support >= 3 and block == 0 else "monitor_only"
    if block >= 2:
        overall = "research_unfavorable"

    return sanitize_research_payload(
        {
            "question": question[:2000],
            "teams": teams,
            "streaming_progress": progress,
            "consensus": overall,
            "authority": "research_only",
            "execution_permission": False,
        }
    )


def _latest_shadow_lesson() -> str:
    try:
        from src.services.research_store import list_shadow_runs

        runs = list_shadow_runs(limit=1)
        if not runs:
            return "No shadow runs yet — journal trades for behavior diagnostics."
        lessons = runs[0].get("lessons") or runs[0].get("behaviorTags") or []
        if isinstance(lessons, list) and lessons:
            return f"Latest shadow: {lessons[0]}"
    except Exception:
        pass
    return "Shadow account available via /api/v7/research/shadow/analyze"
