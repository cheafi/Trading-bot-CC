"""Best Action Now — capital deployment summary for Playbook / Today surfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "TRADE_NOW", "STRONG_TRADE"})
_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"})
_AVOID_ACTIONS = frozenset({"AVOID", "NO_TRADE", "NO_TOUCH", "DO_NOT_TOUCH", "AVOID_NOW"})

_SEMI_TICKERS = frozenset(
    {
        "NVDA",
        "AMD",
        "AVGO",
        "INTC",
        "TSM",
        "QCOM",
        "MU",
        "LRCX",
        "AMAT",
        "KLAC",
        "MRVL",
        "ASML",
        "ARM",
        "ON",
        "MCHP",
    }
)


def _norm_action(action: Optional[str]) -> str:
    return (action or "WATCH").upper().strip()


def _evidence_quality(
    opportunities: List[Dict[str, Any]],
    *,
    source: str = "",
    stale: bool = False,
) -> tuple[str, str]:
    if stale or "fallback" in (source or ""):
        return "low", "Stale or fallback data — verify before sizing"
    if not opportunities:
        return "low", "No ranked opportunities"
    badges = [str(o.get("evidence_badge") or "") for o in opportunities[:5]]
    if any("stale" in b for b in badges):
        return "low", "Stale brief fallback"
    avg_data = sum(float(o.get("data_conf") or 0.5) for o in opportunities[:5]) / min(
        5, len(opportunities)
    )
    if avg_data >= 0.7:
        return "medium", "Model output · cross-check live tape"
    return "low", "Raw model output · limited live validation"


def compute_theme_overlap(opportunities: List[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
    """Warn when top ranks cluster in semis / same sector bucket."""
    top = opportunities[:limit]
    semi = [o for o in top if (o.get("ticker") or "").upper() in _SEMI_TICKERS]
    buckets: Dict[str, int] = {}
    for o in top:
        b = (o.get("sector_type") or o.get("sector_bucket") or "other").upper()
        buckets[b] = buckets.get(b, 0) + 1
    dominant = max(buckets.items(), key=lambda x: x[1]) if buckets else ("", 0)
    warnings: List[str] = []
    if len(semi) >= 4:
        warnings.append(
            f"Semiconductor cluster: {len(semi)}/{len(top)} top names "
            f"({', '.join(x['ticker'] for x in semi[:5])})"
        )
    if dominant[1] >= 5 and dominant[0]:
        warnings.append(
            f"Sector concentration: {dominant[1]} names in {dominant[0].replace('_', ' ')}"
        )
    return {
        "semi_count": len(semi),
        "dominant_sector": dominant[0],
        "dominant_count": dominant[1],
        "warnings": warnings,
        "level": "high" if len(warnings) >= 2 else "medium" if warnings else "low",
    }


def build_best_action(
    opportunities: List[Dict[str, Any]],
    *,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    regime_label: str = "",
    ibkr_connected: bool = False,
    ibkr_mode: str = "paper",
    source: str = "",
    stale: bool = False,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive sticky Best Action Now payload from ranked opportunities."""
    tradeability = (tradeability or "WAIT").upper()
    if not should_trade:
        capital_stance = "hold_cash"
        stance_liner = "Regime gate closed — protect capital, no new risk."
    elif tradeability in ("NO_TRADE",):
        capital_stance = "hold_cash"
        stance_liner = "NO TRADE day — cash is a position."
    elif tradeability in ("STRONG_TRADE", "TRADE"):
        capital_stance = "deploy_selectively"
        stance_liner = f"{tradeability} environment — size only A-grade setups at 1R."
    elif tradeability == "SELECTIVE":
        capital_stance = "deploy_selectively"
        stance_liner = "Selective deployment — high bar for new entries."
    else:
        capital_stance = "deploy_selectively"
        stance_liner = f"{tradeability or 'WAIT'} — monitor triggers, do not chase."

    best_trade = None
    best_watch = None
    best_avoid = None

    for o in opportunities:
        act = _norm_action(o.get("action"))
        tk = o.get("ticker")
        if not tk:
            continue
        conf = float(o.get("final_conf") or o.get("score", 0) / 10 if o.get("score") else 0.6)
        if act in _TRADE_ACTIONS and not best_trade:
            best_trade = {
                "ticker": tk,
                "action": act,
                "confidence": round(conf, 2),
                "entry_price": o.get("entry_price"),
                "stop_price": o.get("stop_price"),
            }
        if act in _WATCH_ACTIONS and not best_watch:
            upgrade = o.get("upgrade_trigger") or o.get("entry_trigger") or ""
            if upgrade or act == "WATCH":
                best_watch = {
                    "ticker": tk,
                    "action": act,
                    "trigger": upgrade or "Reclaim entry zone on volume",
                    "confidence": round(conf, 2),
                }
        if act in _AVOID_ACTIONS and not best_avoid:
            best_avoid = {
                "ticker": tk,
                "action": act,
                "reason": o.get("avoid_reason")
                or o.get("invalidation")
                or "Regime or setup mismatch",
            }

    eq, eq_label = _evidence_quality(opportunities, source=source, stale=stale)
    bracket_ready = bool(
        best_trade
        and best_trade.get("entry_price")
        and best_trade.get("stop_price")
        and float(best_trade["entry_price"]) > float(best_trade["stop_price"])
    )

    try:
        from src.services.execution_readiness import build_execution_readiness

        exec_ready = build_execution_readiness(
            ibkr_connected=ibkr_connected,
            ibkr_mode=ibkr_mode or "paper",
            bracket_ready=bracket_ready,
        )
        exec_ready["can_send_order"] = bool(
            exec_ready.get("trade_handoff_ready") or (ibkr_connected and bracket_ready)
        )
        exec_ready["ibkr_connected"] = ibkr_connected
        exec_ready["bracket_ready"] = bracket_ready
    except Exception:
        exec_ready = {
            "ibkr_connected": ibkr_connected,
            "mode": ibkr_mode or "paper",
            "bracket_ready": bracket_ready,
            "can_send_order": ibkr_connected and bracket_ready,
        }

    return {
        "capital_stance": capital_stance,
        "stance_one_liner": stance_liner,
        "best_trade_now": best_trade,
        "best_watch_upgrade": best_watch,
        "best_avoid_now": best_avoid,
        "evidence_quality": eq,
        "evidence_label": eq_label,
        "execution_readiness": exec_ready,
        "regime_label": regime_label,
        "tradeability": tradeability,
        "data_freshness": "STALE" if stale else "FRESH",
        "as_of": as_of or datetime.now(timezone.utc).isoformat() + "Z",
    }


def enrich_ranked_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach best_action + overlap_warning to playbook ranked response."""
    opps = payload.get("opportunities") or []
    stale = bool(payload.get("stale"))
    source = str(payload.get("source") or "")
    try:
        from src.services.ibkr_service import get_ibkr_service

        st = get_ibkr_service().status()
        ibkr_on = bool(st.get("connected"))
        ibkr_mode = st.get("mode") or "paper"
    except Exception:
        ibkr_on = False
        ibkr_mode = "paper"

    payload["overlap_warning"] = compute_theme_overlap(opps)
    payload["best_action"] = build_best_action(
        opps,
        tradeability="SELECTIVE" if opps else "WAIT",
        should_trade=True,
        ibkr_connected=ibkr_on,
        ibkr_mode=ibkr_mode,
        source=source,
        stale=stale,
    )
    return payload
