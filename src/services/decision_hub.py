"""Platform decision hub — cross-tab decision system (not info widgets)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STYLE_BUCKETS = {
    "momentum": ("momentum", "breakout", "trend", "leader"),
    "mean_reversion": ("mean_reversion", "reversion", "dip", "pullback"),
    "defensive": ("defensive", "quality", "dividend"),
}


def _pick_best_by_style(
    rows: List[Dict[str, Any]], keywords: tuple[str, ...]
) -> Optional[Dict[str, Any]]:
    for row in rows:
        strat = (row.get("strategy") or row.get("setup_family") or "").lower()
        sect = (row.get("sector_type") or row.get("sector_bucket") or "").lower()
        if any(k in strat or k in sect for k in keywords):
            return {
                "ticker": row.get("ticker"),
                "action": row.get("action"),
                "score": row.get("score") or row.get("final_conf"),
                "risk_reward": row.get("risk_reward"),
                "reason": (row.get("why_now") or row.get("upgrade_trigger") or "")[:120],
            }
    return None


def _best_rr(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best = None
    best_rr = 0.0
    for row in rows:
        rr = float(row.get("risk_reward") or 0)
        if rr > best_rr:
            best_rr = rr
            best = row
    if not best:
        return None
    return {
        "ticker": best.get("ticker"),
        "action": best.get("action"),
        "risk_reward": best_rr,
        "score": best.get("score"),
    }


def build_monitoring_system(
    *,
    today: Dict[str, Any],
    market_posture: Dict[str, Any],
) -> Dict[str, Any]:
    """Four-class institutional monitor framework."""
    regime = today.get("market_regime") or {}
    vix = regime.get("vix")
    breadth = regime.get("breadth")
    stock_rules: List[Dict[str, str]] = []
    for nm in (today.get("near_miss") or [])[:3]:
        stock_rules.append(
            {
                "class": "stock",
                "rule": f"Upgrade watch {nm.get('ticker')}",
                "detail": nm.get("upgrade_trigger", ""),
            }
        )
    portfolio_rules = [
        {
            "class": "portfolio",
            "rule": "Position size vs 1R stop",
            "detail": "Resize if stop widens >15%",
        },
        {
            "class": "portfolio",
            "rule": "Sector concentration",
            "detail": "Review if >35% in one bucket",
        },
    ]
    market_rules: List[Dict[str, str]] = []
    if vix is not None:
        market_rules.append(
            {
                "class": "market",
                "rule": f"VIX {vix}",
                "detail": "Reduce size if VIX >25; pause momentum adds",
            }
        )
    if breadth is not None:
        market_rules.append(
            {
                "class": "market",
                "rule": f"Breadth {breadth}%",
                "detail": "Broad deploy needs breadth >50%",
            }
        )
    smart_money_rules = [
        {
            "class": "smart_money",
            "rule": "Insider cluster buy",
            "detail": "Form 4 cluster — confirm with price/volume",
        },
        {
            "class": "smart_money",
            "rule": "13F adds (lagged)",
            "detail": "Do not trade 13F alone — 45–90d lag",
        },
    ]
    return {
        "stock": stock_rules,
        "portfolio": portfolio_rules,
        "market": market_rules,
        "smart_money": smart_money_rules,
        "posture": market_posture.get("deploy_posture"),
    }


def build_user_roles_guide() -> Dict[str, Any]:
    """Which surface for which persona."""
    return {
        "discretionary_pm": ["today", "command", "dossier", "signals"],
        "allocator": ["funds", "today", "portfolio"],
        "risk_officer": ["ops", "portfolio", "funds"],
        "analyst": ["dossier", "signals", "flow"],
        "execution_trader": ["ibkr", "portfolio", "ops"],
        "research_analyst": ["dossier", "flow", "signals"],
    }


async def build_decision_hub(request) -> Dict[str, Any]:
    """
    Unified decision payload for all main tabs.
    Answers: deploy? best idea? avoid? posture? monitor?
    """
    # Fast path only: never call today_summary here (avoids duplicate heavy work with /api/v7/today).
    today: Dict[str, Any] = getattr(request.app.state, "today_v7_cache", None) or {}

    top5 = today.get("top_5") or []
    avoid_raw = today.get("avoid_now") or today.get("avoid") or []
    best_action = today.get("best_action") or {}
    regime = today.get("market_regime") or {}
    tradeability = regime.get("tradeability") or "WAIT"
    should_trade = bool(regime.get("should_trade", True))

    scan_cache = getattr(request.app.state, "scan_cache", {}) or {}
    scanned = list(scan_cache.get("recs", []))[:30]
    ranked_rows: List[Dict[str, Any]] = []
    for t in top5:
        ranked_rows.append(
            {
                "ticker": t.get("ticker"),
                "action": t.get("action"),
                "score": t.get("score"),
                "risk_reward": t.get("risk_reward"),
                "strategy": t.get("strategy"),
                "why_now": t.get("why_now"),
                "sector_type": t.get("sector_bucket"),
            }
        )
    for s in scanned:
        if s.get("ticker") and s.get("score", 0) >= 6.5:
            ranked_rows.append(
                {
                    "ticker": s.get("ticker"),
                    "action": "WATCH",
                    "score": s.get("score"),
                    "risk_reward": s.get("risk_reward"),
                    "strategy": s.get("strategy", ""),
                }
            )

    best_idea = None
    if top5:
        t0 = top5[0]
        best_idea = {
            "ticker": t0.get("ticker"),
            "action": t0.get("action"),
            "score": t0.get("score"),
            "reason": (
                t0.get("why_now")[0]
                if isinstance(t0.get("why_now"), list) and t0.get("why_now")
                else t0.get("why_now")
            ),
        }
    elif best_action.get("best_trade_now"):
        bt = best_action["best_trade_now"]
        best_idea = {
            "ticker": bt.get("ticker"),
            "action": bt.get("action", "WATCH"),
            "reason": best_action.get("stance_one_liner"),
        }

    avoid_now: List[Dict[str, Any]] = []
    for a in avoid_raw[:5]:
        if isinstance(a, str):
            avoid_now.append({"ticker": "—", "reason": a, "category": "regime"})
        else:
            avoid_now.append(
                {
                    "ticker": a.get("ticker", "—"),
                    "reason": a.get("reason", ""),
                    "category": a.get("category", "filter"),
                }
            )
    for t in top5:
        if (t.get("action") or "").upper() in ("AVOID", "NO_TRADE"):
            avoid_now.append(
                {
                    "ticker": t.get("ticker"),
                    "reason": t.get("invalidation") or "Action gate: avoid",
                    "category": "signal",
                }
            )

    market_posture = {
        "regime_label": regime.get("trend") or regime.get("label"),
        "tradeability": tradeability,
        "should_trade": should_trade,
        "deploy_posture": (
            "DEPLOY_SELECTIVE"
            if should_trade and tradeability in ("WAIT", "SELECTIVE")
            else "NO_DEPLOY"
            if not should_trade or tradeability == "NO_TRADE"
            else "DEPLOY"
        ),
        "vix": regime.get("vix"),
        "breadth": regime.get("breadth"),
        "confidence": regime.get("confidence"),
    }

    decision_strip = {
        "best_idea_now": best_idea,
        "best_risk_reward_now": _best_rr(ranked_rows),
        "best_momentum_now": _pick_best_by_style(ranked_rows, _STYLE_BUCKETS["momentum"]),
        "best_mean_reversion_now": _pick_best_by_style(
            ranked_rows, _STYLE_BUCKETS["mean_reversion"]
        ),
        "avoid_now": avoid_now[:5],
        "market_posture_now": market_posture,
        "deploy_reduce_wait": (
            "WAIT"
            if tradeability in ("WAIT", "SELECTIVE") and not top5
            else "REDUCE"
            if tradeability == "NO_TRADE"
            else "DEPLOY"
            if top5
            else "WAIT"
        ),
        "capital_stance": best_action.get("capital_stance"),
        "stance_one_liner": best_action.get("stance_one_liner"),
    }

    try:
        from src.services.execution_readiness import build_execution_readiness

        execution = build_execution_readiness()
    except Exception:
        execution = {}

    fund_console = {}
    fund_cache = getattr(request.app.state, "fund_cards_cache", None)
    if isinstance(fund_cache, dict) and fund_cache.get("cards"):
        try:
            from src.services.fund_manager_console import build_fund_console_payload

            fund_console = build_fund_console_payload(
                cards=fund_cache.get("cards") or [],
                regime=str(fund_cache.get("regime") or ""),
                benchmark="SPY",
                execution_readiness=execution,
                market_regime_label=f"{regime.get('trend', '')} · {tradeability}",
                tradeability=tradeability,
                best_action_liner=best_action.get("stance_one_liner", ""),
                vix=float(regime.get("vix")) if regime.get("vix") is not None else None,
                breadth=float(regime.get("breadth"))
                if regime.get("breadth") is not None
                else None,
            )
        except Exception:
            logger.debug("decision_hub fund_console failed", exc_info=True)

    from src.services.decision_bar import bar_from_today
    from src.services.monitors_store import evaluate_monitors

    warming = not bool(today)
    decision_bar = bar_from_today(today, decision_strip)
    monitor_alerts = evaluate_monitors(today=today)
    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "warming": warming,
        "decision_bar": decision_bar,
        "decision_strip": decision_strip,
        "best_action": best_action,
        "market_posture": market_posture,
        "monitoring": build_monitoring_system(today=today, market_posture=market_posture),
        "monitor_alerts": monitor_alerts,
        "evidence_platform": {
            "regime": today.get("trust", {}).get("freshness", "REAL_TIME"),
            "signals": "model_engine",
            "funds": "model_backtest",
            "label": "Mixed — funds are backtest; signals are model output",
        },
        "fund_allocator": fund_console.get("allocator_decision") or {},
        "execution_readiness": execution,
        "user_roles": build_user_roles_guide(),
        "near_miss": today.get("near_miss") or [],
        "top_5": top5,
    }
