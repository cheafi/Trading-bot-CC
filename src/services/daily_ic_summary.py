"""Daily IC 5-min summary — one-page Mission / Market / Portfolio / Capital / One Belief."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_daily_ic_summary(
    *,
    board: Optional[Dict[str, Any]] = None,
    belief_item: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compose Daily IC one-pager from decision board SSOT — research_only display.

    Does not grant deploy authority; human deploy only.
    """
    board = board or {}
    system = board.get("system_state") or {}
    regime = board.get("regime") or board.get("market_regime") or {}
    best_action = board.get("best_action") or {}
    sleeve = board.get("sleeve_summary") or {}
    td = board.get("todays_decision") or {}

    deploy_open = bool(system.get("deploy_open"))
    tradeability = str(
        system.get("tradeability")
        or regime.get("tradeability")
        or board.get("tradeability")
        or "WAIT"
    ).upper()

    mission = {
        "deploy_open": deploy_open,
        "deploy_label": "OPEN · 可部署" if deploy_open else "BLOCKED · 封鎖",
        "tradeability": tradeability,
        "posture": str(td.get("deploy_posture") or best_action.get("capital_stance") or "WAIT"),
        "stance_one_liner": str(
            best_action.get("stance_one_liner")
            or td.get("stance_one_liner")
            or td.get("deploy_label")
            or "Patience is the active decision on WAIT days."
        )[:240],
    }

    market = {
        "regime": str(regime.get("regime") or regime.get("trend") or "—"),
        "trend": str(regime.get("trend") or regime.get("trend_regime") or "—"),
        "tradeability": tradeability,
        "vix": regime.get("vix"),
        "breadth_pct": regime.get("breadth"),
        "macro": (board.get("decision_model") or {}).get("macro_regime"),
        "headline": str(
            (board.get("decision_model") or {}).get("guidance")
            or (regime.get("tradeability") and f"Tradeability {tradeability}")
            or "—"
        )[:200],
    }

    active_sleeve = sleeve.get("active_today") or sleeve.get("fund_manager") or {}
    portfolio = {
        "best_trade": (best_action.get("best_trade_now") or td.get("best_trade") or {}).get(
            "ticker"
        ),
        "best_watch": (
            best_action.get("best_watch_upgrade") or td.get("best_watch") or {}
        ).get("ticker"),
        "near_miss_count": len(board.get("near_miss") or []),
        "deploy_qualified": int(
            (board.get("opportunity_verdict") or {}).get("deploy_qualified_count")
            or td.get("execution_ready_count")
            or 0
        ),
        "sleeve_name": active_sleeve.get("display_name")
        or active_sleeve.get("active_sleeve_name"),
        "sleeve_gate_status": active_sleeve.get("gate_status"),
        "sleeve_stance": active_sleeve.get("stance") or active_sleeve.get("sleeve_action_now"),
    }

    try:
        from src.services.marginal_roc import build_marginal_roc_ladder

        roc = build_marginal_roc_ladder(deploy_open=deploy_open)
    except Exception:
        roc = {"headline": "Marginal ROC unavailable", "ladder": []}

    capital = {
        "cash_hurdle_bps": roc.get("cash_hurdle_bps"),
        "headline": str(roc.get("headline") or "—")[:200],
        "top_ladder": (roc.get("ladder") or [])[:3],
    }

    belief = belief_item or {}
    one_belief = {
        "ticker": belief.get("ticker"),
        "thesis": str(belief.get("thesis") or "")[:240] or None,
        "kill_condition": str(belief.get("kill_condition") or "")[:160] or None,
        "status": belief.get("status") or ("due" if belief.get("ticker") else "none"),
        "headline": (
            f"{belief.get('ticker')}: {str(belief.get('thesis') or '')[:80]}"
            if belief.get("ticker")
            else "No belief due — review forward outcomes when marks arrive."
        ),
    }

    sections = [mission, market, portfolio, capital, one_belief]
    filled = sum(1 for s in sections if any(v for v in s.values() if v not in (None, "", "—")))

    return {
        "status": "stub",
        "authority": "research_only",
        "may_authorize_deploy": False,
        "headline": "Daily IC · 每日投委 — 5 min one-pager (display only)",
        "mission": mission,
        "market": market,
        "portfolio": portfolio,
        "capital": capital,
        "one_belief": one_belief,
        "completion_pct": min(100, int(filled / 5 * 100)),
        "generated_at": _utc_now_iso(),
    }
