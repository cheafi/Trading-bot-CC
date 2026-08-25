"""Today dashboard insights — near-miss, funnel diagnosis, monitor triggers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

_AVOID_CATEGORIES = (
    "regime",
    "breadth",
    "earnings_risk",
    "failed_breakout",
    "stretched_vol",
    "insider_cluster",
    "low_rr",
    "concentration",
)


def build_avoid_now_engine(
    *,
    regime_label: str,
    should_trade: bool,
    tradeability: str,
    vix: float,
    breadth: float,
    confidence: float,
    council_results: Optional[List[Any]] = None,
    scanned: Optional[List[Dict[str, Any]]] = None,
    top5: Optional[List[Dict[str, Any]]] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    Categorized avoid list — not gossip, evidence-typed for PM / decision hub.
    """
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _add(ticker: str, reason: str, category: str, severity: str = "medium"):
        key = f"{ticker}:{category}"
        if key in seen or len(items) >= limit:
            return
        seen.add(key)
        items.append(
            {
                "ticker": ticker,
                "reason": reason,
                "category": category,
                "severity": severity,
            }
        )

    if not should_trade:
        _add("—", "Regime gate closed — no new risk", "regime", "high")
    if regime_label == "RISK_OFF":
        _add("—", "Risk-off regime — avoid aggressive momentum", "regime", "high")
    if tradeability in ("NO_TRADE", "WAIT") and not should_trade:
        _add("—", f"Tradeability {tradeability} — observe only", "regime", "medium")
    if vix > 28:
        _add(
            "—",
            f"VIX {vix:.0f} — elevated; avoid full-size adds",
            "stretched_vol",
            "high",
        )
    if breadth < 40:
        _add(
            "—",
            f"Breadth {breadth:.0f}% — narrow market; avoid broad deploy",
            "breadth",
            "medium",
        )
    if confidence < 0.4:
        _add("—", "Low regime confidence — size down", "regime", "medium")

    for cr in council_results or []:
        try:
            pr = cr.pipeline
            sig = pr.signal
            ticker = (sig.get("ticker") or "").upper()
            if not ticker:
                continue
            act = (pr.decision.action or "").upper()
            if act not in ("AVOID", "NO_TRADE", "PASS"):
                continue
            struct = sig.get("structure") or {}
            if struct.get("is_extended"):
                _add(
                    ticker,
                    "Extended from support — failed breakout risk",
                    "failed_breakout",
                    "medium",
                )
            earn = sig.get("earnings") or {}
            if earn.get("in_blackout"):
                _add(ticker, "Earnings blackout window", "earnings_risk", "high")
            elif (earn.get("days_to_earnings") or 999) <= 3:
                _add(
                    ticker,
                    f"Earnings in {earn.get('days_to_earnings')}d",
                    "earnings_risk",
                    "high",
                )
            from src.services.decision_truth_model import (
                _pipeline_invalidation,
                _pipeline_risk_reward,
            )

            rr = _pipeline_risk_reward(pr)
            if 0 < rr < 2.0:
                _add(ticker, f"R:R {rr:.1f} below 2.0 gate", "low_rr", "medium")
            inv = _pipeline_invalidation(pr)
            if inv:
                _add(ticker, inv[:100], "regime", "medium")
        except Exception:
            continue

    for sig in scanned or []:
        ticker = (sig.get("ticker") or "").upper()
        if not ticker:
            continue
        struct = sig.get("structure") or {}
        if struct.get("is_extended") and ticker not in {i["ticker"] for i in items}:
            _add(ticker, "Scanner: extended structure", "failed_breakout", "low")
        earn = sig.get("earnings") or {}
        if earn.get("in_blackout"):
            _add(ticker, "Earnings blackout (scanner)", "earnings_risk", "high")

    for t in top5 or []:
        if (t.get("action") or "").upper() in ("AVOID", "NO_TRADE"):
            _add(
                t.get("ticker", "—"),
                t.get("invalidation") or "Top list avoid gate",
                "regime",
                "medium",
            )

    return items


def build_regime_wait_explanation(
    *,
    trend_label: str,
    tradeability: str,
    trade_count: int,
    actionable: int,
    should_trade: bool,
    vix: float,
    breadth: float,
) -> List[str]:
    """Explain UPTREND + WAIT without sounding contradictory."""
    lines: List[str] = []
    if trend_label == "UPTREND" and tradeability in ("WAIT", "SELECTIVE"):
        lines.append(
            "Broad trend is supportive — uptrend is the backdrop, not a deploy signal."
        )
        lines.append(
            "No name passed full action rules (score ≥8, thesis+timing ≥65%, R:R ≥2.5, regime gate)."
        )
        if actionable > 0:
            lines.append(
                f"{actionable} setup(s) scored ≥7.0 but failed timing, execution, or R:R gates."
            )
        else:
            lines.append(
                "Scanner found no names above actionable score threshold today."
            )
    elif not should_trade:
        lines.append(
            "Regime gate is closed — capital preservation overrides individual setups."
        )
    elif trade_count > 0:
        lines.append(f"{trade_count} TRADE-ready name(s) — deploy selectively at 1R.")
    else:
        lines.append(f"Tradeability: {tradeability} — patience is the active decision.")
    if vix > 22:
        lines.append(
            f"VIX {vix:.0f} — elevated vol; size down or wait for compression."
        )
    if breadth < 40:
        lines.append(f"Breadth {breadth:.0f}% — narrow participation; leaders only.")
    return lines[:5]


def build_no_setup_diagnosis(
    council_results: List[Any],
    *,
    scanner_degraded: bool = False,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    validated_count: int = 0,
    deployable_count: int = 0,
    execution_readiness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Why no deploy today — failure bucket counts + blocker tree."""
    buckets = {
        "failed_regime": 0,
        "failed_timing": 0,
        "failed_rr": 0,
        "failed_execution": 0,
        "failed_score": 0,
        "failed_freshness": 1 if scanner_degraded else 0,
        "failed_data": 0,
    }
    for cr in council_results or []:
        try:
            pr = cr.pipeline
            act = (pr.decision.action or "").upper()
            if act in ("TRADE", "BUY", "BUY_ON_DIP"):
                continue
            timing = float(pr.confidence.timing)
            thesis = float(pr.confidence.thesis)
            execution = float(pr.confidence.execution)
            from src.services.decision_truth_model import _pipeline_risk_reward

            rr = _pipeline_risk_reward(pr)
            if act in ("NO_TRADE", "AVOID"):
                buckets["failed_regime"] += 1
            elif timing < 0.5:
                buckets["failed_timing"] += 1
            elif rr > 0 and rr < 2.5:
                buckets["failed_rr"] += 1
            elif execution < 0.4:
                buckets["failed_execution"] += 1
            elif pr.fit.final_score < 7.0:
                buckets["failed_score"] += 1
            elif thesis < 0.65:
                buckets["failed_timing"] += 1
            else:
                buckets["failed_score"] += 1
        except Exception:
            continue
    total = sum(buckets.values())
    only_freshness = (
        scanner_degraded
        and buckets.get("failed_freshness", 0) >= 1
        and sum(v for k, v in buckets.items() if k != "failed_freshness") == 0
    )
    if only_freshness:
        headline = (
            "Scanner cache warming — not a regime veto. "
            "Wait for prewarm or open Discovery to refresh."
        )
    elif total:
        headline = "No deploy candidate passed action rules"
    else:
        headline = "Scanner still warming — diagnosis unavailable"

    ex = execution_readiness or {}
    tb = (tradeability or "WAIT").upper()
    regime_blocked = not should_trade or tb == "NO_TRADE"
    freshness_blocked = scanner_degraded or bool(buckets.get("failed_freshness"))
    timing_blocked = buckets.get("failed_timing", 0) > 0
    rr_blocked = buckets.get("failed_rr", 0) > 0
    execution_blocked = (
        buckets.get("failed_execution", 0) > 0
        or not ex.get("broker_connected")
        or not ex.get("trade_handoff_ready")
    )

    blocker_tree = {
        "regime": {"blocked": regime_blocked, "label": "Regime gate"},
        "freshness": {"blocked": freshness_blocked, "label": "Data freshness"},
        "timing": {"blocked": timing_blocked, "label": "Timing confirmation"},
        "rr": {"blocked": rr_blocked, "label": "R:R ≥2.5"},
        "execution": {"blocked": execution_blocked, "label": "Execution / broker"},
    }
    primary_blocker = ""
    if regime_blocked:
        primary_blocker = f"Regime {tb} — no full deploy today"
    elif deployable_count < 1 and validated_count < 1 and freshness_blocked:
        primary_blocker = "Scanner warming — watch-qualified setups not ready yet"
    elif deployable_count < 1 and rr_blocked:
        primary_blocker = "Names scanned but R:R below full-size gate"
    elif deployable_count < 1 and timing_blocked:
        primary_blocker = "Setups lack timing confirmation for deploy"
    elif deployable_count < 1 and execution_blocked:
        primary_blocker = "Broker or bracket not ready for handoff"
    elif deployable_count < 1:
        primary_blocker = "No name passed watch-qualified + deploy-qualified bar"
    else:
        primary_blocker = headline

    return {
        "breakdown": buckets,
        "total_evaluated": total,
        "scanner_degraded": scanner_degraded,
        "headline": headline,
        "blocker_tree": blocker_tree,
        "validated_count": validated_count,
        "watch_qualified_count": validated_count,
        "deployable_count": deployable_count,
        "primary_blocker": primary_blocker,
    }


def build_unlock_deploy(
    *,
    tradeability: str,
    should_trade: bool,
    deployable_count: int,
    scanner_degraded: bool,
    execution_readiness: Optional[Dict[str, Any]] = None,
    watch_qualified_count: int = 0,
    validated_count: Optional[int] = None,
    scan_ranked_count: int = 0,
) -> Dict[str, Any]:
    """Conditions required before full deploy unlocks."""
    from src.services.decision_truth_model import format_board_quality_detail

    ex = execution_readiness or {}
    tb = (tradeability or "WAIT").upper()
    wq = int(
        watch_qualified_count
        if watch_qualified_count is not None
        else (validated_count or 0)
    )
    sr = max(0, int(scan_ranked_count or 0))
    broker_ready = bool(
        ex.get("trade_handoff_ready")
        or (ex.get("broker_connected") and ex.get("bracket_order_ready"))
    )
    regime_ok = should_trade and tb in ("SELECTIVE", "TRADE", "STRONG_TRADE")
    watch_ok = wq >= 1
    freshness_ok = not scanner_degraded
    board_quality_ok = watch_ok and freshness_ok
    conditions = [
        {
            "key": "regime",
            "label": "可交易性升至 SELECTIVE+ · Tradeability improves to SELECTIVE+",
            "met": regime_ok,
            "detail": f"Current: {tb}",
        },
        {
            "key": "deployable",
            "label": "至少 1 個 deploy-qualified · At least 1 deploy-qualified setup",
            "met": deployable_count >= 1,
            "detail": f"{deployable_count} deploy-qualified",
        },
        {
            "key": "broker",
            "label": "券商 handoff 就緒 · Broker handoff is live",
            "met": broker_ready,
            "detail": ex.get("unified_label") or ex.get("readiness_label") or "Offline",
        },
        {
            "key": "board",
            "label": "板面質素支持風險 · Board-level quality supports risk",
            "met": board_quality_ok,
            "detail": format_board_quality_detail(
                wq, scan_ranked=sr, scanner_degraded=scanner_degraded
            ),
        },
    ]
    unlocked = all(c["met"] for c in conditions)
    remaining = [c["label"] for c in conditions if not c["met"]]
    board_present = wq >= 1 or deployable_count >= 1 or sr >= 1
    if unlocked:
        status_line = (
            "現況：四項齊備 — 送出前確認 size 同 bracket · "
            "Current status: all conditions met — confirm size and brackets before send."
        )
    elif board_present and deployable_count < 1:
        status_line = (
            "現況：有板面、無 deploy · Current status: board present, deploy absent."
        )
    elif not board_present:
        status_line = (
            "現況：板面薄、無 deploy · Current status: board thin, deploy absent."
        )
    else:
        status_line = "現況：deploy 閘門未清 · Current status: deploy gate not cleared."
    return {
        "unlocked": unlocked,
        "conditions": conditions,
        "remaining": remaining,
        "summary": status_line if not unlocked else status_line,
        "intro": (
            "解鎖 deploy 須四項齊備：tradeability SELECTIVE+、≥1 deploy-qualified、"
            "live broker handoff、≥1 watch-qualified（僅 scan-ranked 不足） · "
            "Unlock deploy requires all 4 conditions together: "
            "tradeability SELECTIVE+, ≥1 deploy-qualified setup, live broker handoff, "
            "and ≥1 watch-qualified name on fresh data (scan-ranked alone does not qualify)."
        ),
    }


def _timing_bucket(timing_conf: float, score: float) -> str:
    if timing_conf >= 0.55:
        return "intraday"
    if score >= 6.5:
        return "1-3d"
    return "1-2w"


def _near_miss_gate_distance(row: Dict[str, Any]) -> tuple:
    """Sort key: fewer gaps first, then higher score (closest to deploy gate)."""
    gaps = row.get("gaps") or []
    return (
        len(gaps),
        -float(row.get("score") or 0),
        -float(row.get("final_conf") or 0),
    )


def best_net_edge_from_opportunities(
    rows: Optional[List[Dict[str, Any]]],
) -> Optional[float]:
    """Best net edge after cost drag across opportunity rows — ranking humility only."""
    from src.services.cost_adjusted_edge import compute_net_edge, infer_burdens_from_row

    best: Optional[float] = None
    for row in rows or []:
        raw = row.get("raw_score")
        if raw is None:
            raw = row.get("score")
        if raw is None:
            continue
        burdens = infer_burdens_from_row(row)
        edge = compute_net_edge(
            float(raw),
            turnover_burden=burdens["turnover_burden"],
            spread_burden=burdens["spread_burden"],
            action=row.get("action"),
            extended=bool(row.get("extended") or row.get("timing_extended")),
            partial_data=bool(row.get("partial")),
        )
        net = float(edge["net_edge_score"])
        if best is None or net > best:
            best = net
    return best


def build_near_miss_candidates(
    council_results: List[Any],
    top5_tickers: Set[str],
    *,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Dedicated near-miss board — always WATCH, with upgrade/invalidation."""
    rows: List[Dict[str, Any]] = []
    for cr in council_results or []:
        try:
            pr = cr.pipeline
            sig = pr.signal
            ticker = sig.get("ticker") or ""
            if not ticker or ticker in top5_tickers:
                continue
            from src.services.decision_truth_model import (
                _pipeline_risk_reward,
                is_execution_ready,
                refine_action,
            )

            if is_execution_ready(cr):
                continue
            action = refine_action(cr)
            if action in ("TRADE", "AVOID", "NO_TRADE"):
                continue
            action = "WATCH"
            score = float(pr.fit.final_score)
            if score < 6.0:
                continue
            timing = float(pr.confidence.timing)
            thesis = float(pr.confidence.thesis)
            rr = _pipeline_risk_reward(pr)
            gaps: List[str] = []
            if timing < 0.5:
                gaps.append("timing")
            if thesis < 0.65:
                gaps.append("thesis")
            if rr > 0 and rr < 2.5:
                gaps.append("R:R")
            if float(pr.confidence.execution) < 0.4:
                gaps.append("execution")
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            target = sig.get("target_price")
            expl = getattr(pr, "explanation", None)
            trigger = pr.decision.entry_trigger or (
                getattr(expl, "upgrade_trigger", None) if expl else None
            )
            if not trigger:
                if gaps:
                    trigger = f"Fix {gaps[0]} — reclaim entry on volume"
                elif entry and stop:
                    trigger = (
                        f"Hold above ${float(entry):.2f} with stop ${float(stop):.2f}"
                    )
                else:
                    trigger = "Await trigger confirmation"
            distance_parts: List[str] = []
            if timing < 0.5:
                distance_parts.append(f"timing +{int(max(0, (0.5 - timing) * 100))}pts")
            if thesis < 0.65:
                distance_parts.append(
                    f"thesis +{int(max(0, (0.65 - thesis) * 100))}pts"
                )
            if rr > 0 and rr < 2.5:
                distance_parts.append(f"R:R need {2.5 - rr:.1f}")
            distance_to_pass = (
                " · ".join(distance_parts)
                if distance_parts
                else "At gate — review sizing"
            )
            whats_missing = (
                ", ".join(gaps) if gaps else "At gate — confirm volume and R:R"
            )
            rows.append(
                {
                    "ticker": ticker,
                    "action": action,
                    "score": round(score, 1),
                    "final_conf": round(float(pr.confidence.final), 2),
                    "gaps": gaps,
                    "whats_missing": whats_missing,
                    "upgrade_trigger": trigger,
                    "distance_to_pass": distance_to_pass,
                    "invalidation": inv
                    if (
                        inv := (getattr(expl, "invalidation", None) if expl else None)
                        or getattr(pr.decision, "invalidation", None)
                    )
                    else (f"Below ${float(stop):.2f}" if stop else ""),
                    "invalidation_price": stop,
                    "entry_price": entry,
                    "stop_price": stop,
                    "target_price": target,
                    "risk_reward": round(rr, 1) if rr else None,
                    "timing_bucket": _timing_bucket(timing, score),
                    "why_not": (
                        getattr(expl, "why_not_stronger", None) or gaps
                        if expl
                        else gaps
                    ),
                }
            )
        except Exception:
            continue
    rows.sort(key=_near_miss_gate_distance)
    return rows[:limit]


_OPPORTUNITY_MONITOR_TYPES = frozenset(
    {
        "structure",
        "volume",
        "event_clear",
        "insider_cluster",
        "13f_sponsorship",
        "strategy_health",
        "cluster_deploy",
        "cluster_pilot",
        "cluster_watch",
        "cluster_near_miss",
        "cluster_blocked_cost",
        "cluster_blocked_dd",
    }
)


def _dd_pct_from_underwater_curve(underwater: List[float]) -> Optional[float]:
    """Current book DD % from equity underwater series — omitted at peak (no fake DD)."""
    if not underwater:
        return None
    cur = float(underwater[-1])
    if cur >= 0:
        return None
    dd = abs(cur)
    return round(dd, 2) if dd > 0 else None


async def load_equity_dd_pct_for_hints(request) -> Optional[float]:
    """
    Book DD from portfolio equity underwater — same source as drawdown-sizing UI.

    Omitted when no holdings or series unavailable (no synthetic DD).
    """
    if request is None:
        return None
    try:
        from src.api.routers.portfolio import _user_portfolio
        from src.services.portfolio_equity import build_portfolio_equity_series

        holdings = _user_portfolio.get("holdings") or []
        if not holdings:
            return None
        eq = await build_portfolio_equity_series(request, holdings, period="6mo")
        if not eq.get("has_series"):
            return None
        return _dd_pct_from_underwater_curve(eq.get("underwater_curve") or [])
    except Exception:
        return None


def resolve_book_dd_utilization_for_hints(
    *,
    fallback_or_stale: bool = False,
    equity_dd_pct: Optional[float] = None,
) -> Optional[float]:
    """
    Live book drawdown utilization for quant cluster hints — monitor/research only.

    Uses portfolio heat when populated; falls back to equity underwater (drawdown-sizing
    path) when heat DD is empty. Omitted on brief fallback or stale scanner.
    """
    if fallback_or_stale:
        return None
    current_dd = 0.0
    try:
        from src.engines.portfolio_heat import get_portfolio_heat_engine

        snap = get_portfolio_heat_engine().snapshot()
        current_dd = float(getattr(snap, "max_drawdown_pct", 0) or 0)
    except Exception:
        current_dd = 0.0
    if current_dd <= 0 and equity_dd_pct is not None and equity_dd_pct > 0:
        current_dd = float(equity_dd_pct)
    if current_dd <= 0:
        return None
    try:
        from src.core.risk_limits import RISK

        budget_pct = float(RISK.max_drawdown_pct) * 100.0
        if budget_pct <= 0:
            return None
        return round(min(100.0, max(0.0, current_dd / budget_pct * 100.0)), 1)
    except Exception:
        return None


def near_miss_gap_count(row: Dict[str, Any]) -> int:
    """Count deploy gate gaps on a near-miss row."""
    return len(row.get("gaps") or [])


def prior_near_miss_gap_map(
    prior_rows: Optional[List[Dict[str, Any]]],
) -> Dict[str, int]:
    """Ticker → prior gap count from last playbook snapshot — monitor-only."""
    out: Dict[str, int] = {}
    for row in prior_rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        out[ticker] = near_miss_gap_count(row)
    return out


def format_monitor_upgrade_gap_alert(
    row: Dict[str, Any],
    *,
    prior_gap_count: Optional[int] = None,
) -> Optional[str]:
    """Backend monitor copy when near-miss gate gap count drops — not deploy authority."""
    gaps = row.get("gaps") or []
    gap_n = len(gaps)
    ticker = str(row.get("ticker") or "—")
    if prior_gap_count is not None and prior_gap_count > gap_n:
        return (
            f"Monitor upgrade alert — {ticker} gate gaps dropped "
            f"({prior_gap_count}→{gap_n}); still not deploy"
        )
    if gap_n == 1:
        return (
            f"Monitor upgrade alert — {ticker} single gate gap ({gaps[0]}); "
            "closest upgrade — not deploy"
        )
    if gap_n == 0:
        return f"Monitor upgrade alert — {ticker} at gate — confirm volume; not deploy"
    return None


def detect_monitor_upgrade_gap_alerts(
    near_miss: List[Dict[str, Any]],
    *,
    prior_near_miss: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Monitor upgrade alerts when gap count drops vs prior snapshot or single-gap lead."""
    prior_map = prior_near_miss_gap_map(prior_near_miss)
    alerts: List[Dict[str, Any]] = []
    for nm in near_miss or []:
        if not isinstance(nm, dict):
            continue
        ticker = str(nm.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        gap_n = near_miss_gap_count(nm)
        prior_n = prior_map.get(ticker)
        msg = format_monitor_upgrade_gap_alert(nm, prior_gap_count=prior_n)
        if not msg:
            continue
        improved = prior_n is not None and prior_n > gap_n
        if improved or gap_n <= 1:
            alerts.append(
                {
                    "type": "monitor_upgrade_alert",
                    "label": f"Upgrade alert: {ticker}",
                    "detail": msg,
                    "horizon": "intraday",
                    "monitoring_only": True,
                    "gap_count": gap_n,
                    "prior_gap_count": prior_n,
                    "gap_improved": improved,
                }
            )
    return alerts[:3]


def build_opportunity_recheck_heuristic(
    *,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    prior_near_miss: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Auto-recheck stale near-miss rows — monitor-only, no deploy trigger."""
    prior_map = prior_near_miss_gap_map(prior_near_miss)
    hints: List[Dict[str, Any]] = []
    for nm in near_miss or []:
        if not isinstance(nm, dict):
            continue
        ticker = str(nm.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        gap_n = near_miss_gap_count(nm)
        gaps = nm.get("gaps") or []
        prior_n = prior_map.get(ticker)
        if prior_n is None:
            if gap_n >= 2:
                hints.append(
                    {
                        "ticker": ticker,
                        "hint": (
                            f"{ticker} — recheck {', '.join(gaps[:2])} on next poll; "
                            "monitor upgrade only"
                        ),
                        "recheck_horizon": "intraday",
                        "monitor_only": True,
                        "may_authorize_deploy": False,
                    }
                )
            continue
        if gap_n >= prior_n:
            focus = gaps[0] if gaps else "gate"
            hints.append(
                {
                    "ticker": ticker,
                    "hint": (
                        f"{ticker} recycle watch — gap count unchanged ({gap_n}); "
                        f"reconfirm {focus}"
                    ),
                    "recheck_horizon": "intraday",
                    "monitor_only": True,
                    "may_authorize_deploy": False,
                }
            )
    return hints[:5]


def _near_miss_monitor_gap_suffix(row: Dict[str, Any]) -> str:
    """Backend monitor copy when near-miss gate gaps tighten — not deploy authority."""
    gaps = row.get("gaps") or []
    gap_n = len(gaps)
    if gap_n == 0:
        return "at gate — confirm volume; not deploy"
    if gap_n == 1:
        return f"closest upgrade — 1 gate gap ({gaps[0]})"
    return f"{gap_n} gate gaps — monitor upgrade, not deploy"


def build_quant_cluster_hints(
    *,
    tradeability: str = "WAIT",
    deploy_qualified_count: int = 0,
    best_net_score: Optional[float] = None,
    dd_utilization_pct: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Daily opportunity cluster labels — monitoring only, not deploy authority.

    deploy/pilot labels describe board-adjacent posture; board gate still required.
    """
    hints: List[Dict[str, Any]] = []
    tb = str(tradeability or "").upper()
    net = best_net_score
    dd_util = dd_utilization_pct

    if dd_util is not None and dd_util >= 85:
        hints.append(
            {
                "type": "cluster_blocked_dd",
                "label": "Blocked by DD budget",
                "detail": f"Drawdown utilization {dd_util:.0f}% — sizing templates blocked in research",
                "horizon": "daily",
                "cluster": "blocked-by-dd",
            }
        )
    if net is not None and net < 6.0:
        hints.append(
            {
                "type": "cluster_blocked_cost",
                "label": "Blocked by cost drag",
                "detail": f"Best net edge {net:.1f} after cost — demote ranking, not a veto alone",
                "horizon": "intraday",
                "cluster": "blocked-by-cost",
            }
        )
    if tb == "WAIT":
        hints.append(
            {
                "type": "cluster_watch",
                "label": "Watch cluster",
                "detail": "Board WAIT — near-miss and monitors only",
                "horizon": "daily",
                "cluster": "watch",
            }
        )
        hints.append(
            {
                "type": "cluster_near_miss",
                "label": "Near-miss cluster",
                "detail": "Closest upgrades — still not deploy without tradeability lift",
                "horizon": "intraday",
                "cluster": "near-miss",
            }
        )
    elif deploy_qualified_count >= 1 and tb in ("TRADE", "SELECTIVE"):
        hints.append(
            {
                "type": "cluster_deploy",
                "label": "Deploy cluster (board-gated)",
                "detail": f"{deploy_qualified_count} execution-ready — Dashboard gate still required",
                "horizon": "intraday",
                "cluster": "deploy",
            }
        )
    else:
        hints.append(
            {
                "type": "cluster_pilot",
                "label": "Pilot cluster",
                "detail": "Selective posture — half-size research template only",
                "horizon": "daily",
                "cluster": "pilot",
            }
        )
    return hints


def build_monitor_triggers(
    *,
    market_pulse: Dict[str, Any],
    near_miss: List[Dict[str, Any]],
    vix: float,
    breadth: float,
    tradeability: str,
    opportunity_hints: Optional[List[Dict[str, Any]]] = None,
    quant_cluster_hints: Optional[List[Dict[str, Any]]] = None,
    prior_near_miss: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """What to watch when there are zero deploy setups."""
    triggers: List[Dict[str, Any]] = []
    for alert in detect_monitor_upgrade_gap_alerts(
        near_miss, prior_near_miss=prior_near_miss
    ):
        triggers.append(alert)
    if near_miss:
        nm = near_miss[0]
        detail = str(nm.get("upgrade_trigger") or "").strip()
        dist = str(nm.get("distance_to_pass") or "").strip()
        if dist:
            detail = f"{detail} · {dist}" if detail else dist
        if not detail:
            detail = str(nm.get("whats_missing") or "Monitor upgrade — not deploy")
        gap_suffix = _near_miss_monitor_gap_suffix(nm)
        if gap_suffix:
            detail = f"{detail} · {gap_suffix}" if detail else gap_suffix
        triggers.append(
            {
                "type": "near_miss",
                "label": f"Upgrade watch: {nm['ticker']}",
                "detail": detail,
                "horizon": "intraday",
                "monitoring_only": True,
            }
        )
    leaders = (market_pulse or {}).get("sector_leaders") or []
    if leaders:
        l0 = leaders[0]
        triggers.append(
            {
                "type": "sector",
                "label": f"Sector leader: {l0.get('name', '—')}",
                "detail": f"+{l0.get('change_pct', 0):.2f}% — rotation signal",
                "horizon": "daily",
            }
        )
    if vix > 20:
        triggers.append(
            {
                "type": "vix",
                "label": "VIX threshold",
                "detail": f"VIX {vix:.1f} — reduce size if >25",
                "horizon": "daily",
            }
        )
    if breadth < 45:
        triggers.append(
            {
                "type": "breadth",
                "label": "Breadth recovery",
                "detail": f"Breadth {breadth:.0f}% — need >50% for broad deploy",
                "horizon": "weekly",
            }
        )
    if tradeability == "WAIT":
        triggers.append(
            {
                "type": "regime",
                "label": "Regime upgrade",
                "detail": "Tradeability must move to SELECTIVE/TRADE with ≥1 passing setup",
                "horizon": "daily",
            }
        )
    for hint in list(opportunity_hints or []) + list(quant_cluster_hints or []):
        t = str(hint.get("type") or "")
        if t not in _OPPORTUNITY_MONITOR_TYPES:
            continue
        triggers.append(
            {
                "type": t,
                "label": str(hint.get("label") or f"Monitor: {t}"),
                "detail": str(
                    hint.get("detail")
                    or "Opportunity context — monitoring only, not deploy"
                ),
                "horizon": str(hint.get("horizon") or "weekly"),
                "monitoring_only": True,
                "cluster": hint.get("cluster"),
            }
        )
    return triggers[:8]


def build_evidence_badges(
    *,
    scanner_degraded: bool = False,
    regime_synthetic: bool = False,
    ai_powered: bool = False,
    fund_evidence: str = "model_backtest",
) -> Dict[str, Any]:
    """Evidence quality tags for major dashboard surfaces."""
    return {
        "regime": {
            "badge": "fallback"
            if regime_synthetic
            else ("stale" if scanner_degraded else "live"),
            "label": (
                "Regime: synthetic fallback"
                if regime_synthetic
                else (
                    "Regime: degraded scanner"
                    if scanner_degraded
                    else "Regime: live engine"
                )
            ),
        },
        "scanner": {
            "badge": "stale" if scanner_degraded else "live",
            "label": "Scanner degraded" if scanner_degraded else "Scanner live",
        },
        "funds": {
            "badge": fund_evidence,
            "label": "Fund α: model backtest — not live P&L",
        },
        "ai": {
            "badge": "experimental" if ai_powered else "no_track_record",
            "label": (
                "AI: experimental — non-decision"
                if ai_powered
                else "AI: no track record — commentary only"
            ),
        },
    }


_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"})
_PILOT_ACTIONS = frozenset({"PILOT"})
_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER"})
_AVOID_ACTIONS = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE"})


def _norm_action(action: Optional[str]) -> str:
    return (action or "WATCH").upper().strip()


def _pick_best(
    rows: List[Dict[str, Any]],
    actions: frozenset,
    *,
    execution_ready_only: bool = False,
) -> Optional[Dict[str, Any]]:
    for o in rows:
        act = _norm_action(o.get("action"))
        tk = o.get("ticker")
        if not tk or act not in actions:
            continue
        if execution_ready_only and not o.get("execution_ready"):
            continue
        return {
            "ticker": tk,
            "action": act,
            "score": o.get("score"),
            "final_conf": o.get("final_conf") or o.get("confidence"),
            "risk_reward": o.get("risk_reward"),
            "entry_price": o.get("entry_price"),
            "stop_price": o.get("stop_price"),
            "execution_ready": bool(o.get("execution_ready")),
            "upgrade_trigger": o.get("upgrade_trigger")
            or (o.get("explanation") or {}).get("upgrade_trigger"),
            "why_pilot": o.get("why_pilot"),
        }
    return None


def _deploy_posture(
    *,
    tradeability: str,
    should_trade: bool,
    has_trade: bool,
    has_pilot: bool,
    execution_ready: int,
) -> str:
    """Unified PM taxonomy: AVOID / WAIT / WATCH / PILOT / TRADE / SCALE."""
    tb = (tradeability or "WAIT").upper()
    if not should_trade or tb == "NO_TRADE":
        return "AVOID"
    if has_trade and execution_ready >= 2 and tb == "STRONG_TRADE":
        return "SCALE"
    if has_trade:
        return "TRADE"
    if has_pilot or tb == "SELECTIVE":
        return "PILOT"
    if tb in ("WAIT", "SELECTIVE"):
        return "WATCH"
    return "WAIT"


def _derive_day_state(
    *,
    tradeability: str,
    should_trade: bool,
    execution_ready_count: int,
    has_pilot: bool,
    has_watch: bool,
) -> str:
    """Headline taxonomy for dashboard honesty."""
    tb = (tradeability or "WAIT").upper()
    if not should_trade or tb == "NO_TRADE":
        return "NO_TRADE_DAY"
    if execution_ready_count >= 1:
        if execution_ready_count >= 2 and tb == "STRONG_TRADE":
            return "A_GRADE_TRADE_DAY"
        return "TRADE_DAY"
    if has_pilot or has_watch or tb in ("SELECTIVE", "WAIT"):
        return "PILOT_WATCH_DAY"
    return "NO_TRADE_DAY"


def build_todays_decision(
    *,
    tradeability: str,
    should_trade: bool,
    trend_label: str,
    decision_model: Optional[Dict[str, Any]],
    best_action: Optional[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    near_miss: Optional[List[Dict[str, Any]]],
    no_setup_diagnosis: Optional[Dict[str, Any]],
    regime_wait_explanation: Optional[List[str]],
    execution_readiness: Optional[Dict[str, Any]],
    event_risks: Optional[List[str]],
    narrative: str = "",
    execution_ready_count: int = 0,
    decision_authority: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single primary decision card — answers deploy / best trade / watch / pilot / why not.
    """
    ba = best_action or {}
    dm = decision_model or {}
    trade_rows = [
        o for o in opportunities if _norm_action(o.get("action")) in _TRADE_ACTIONS
    ]
    pilot_rows = [
        o for o in opportunities if _norm_action(o.get("action")) in _PILOT_ACTIONS
    ]
    watch_rows = [
        o for o in opportunities if _norm_action(o.get("action")) in _WATCH_ACTIONS
    ]

    exec_ready_count = execution_ready_count or sum(
        1 for o in opportunities if o.get("execution_ready")
    )
    best_trade = (
        ba.get("best_trade_now")
        if (ba.get("best_trade_now") or {}).get("execution_ready")
        else None
    )
    if not best_trade:
        best_trade = _pick_best(
            opportunities, _TRADE_ACTIONS, execution_ready_only=True
        )
    best_pilot = ba.get("best_pilot_now") or _pick_best(opportunities, _PILOT_ACTIONS)
    best_watch = (
        ba.get("best_watch_upgrade")
        or _pick_best(opportunities, _WATCH_ACTIONS)
        or (near_miss[0] if near_miss else None)
        or _pick_best(watch_rows, _WATCH_ACTIONS)
    )

    has_trade = bool(best_trade) and exec_ready_count >= 1
    has_pilot = bool(best_pilot)
    has_watch = bool(best_watch)
    day_state = _derive_day_state(
        tradeability=tradeability,
        should_trade=should_trade,
        execution_ready_count=exec_ready_count,
        has_pilot=has_pilot,
        has_watch=has_watch,
    )
    posture = _deploy_posture(
        tradeability=tradeability,
        should_trade=should_trade,
        has_trade=has_trade,
        has_pilot=has_pilot,
        execution_ready=exec_ready_count,
    )

    can_deploy = posture in ("TRADE", "SCALE") and should_trade and has_trade
    deploy_label = {
        "AVOID": "Do not deploy",
        "WAIT": "Wait — preserve capital",
        "WATCH": "Watch only — no new risk",
        "PILOT": "Pilot only — half size, not full deploy",
        "TRADE": "Deploy selectively — A-grade at 1R",
        "SCALE": "Scale selectively — multiple execution-ready",
    }.get(posture, "Wait")
    if day_state == "PILOT_WATCH_DAY" and posture in ("WATCH", "PILOT", "WAIT"):
        deploy_label = "Pilot / watch day — no full-size deploy"
    elif day_state == "NO_TRADE_DAY":
        deploy_label = "No-trade day — patience is the decision"
    hero_label = {
        "A_GRADE_TRADE_DAY": "#1 TRADE TODAY",
        "TRADE_DAY": "#1 TRADE TODAY",
        "PILOT_WATCH_DAY": "#1 WATCH/PILOT CANDIDATE",
        "NO_TRADE_DAY": "",
    }.get(day_state, "")

    hero_label = _apply_hero_authority(hero_label, decision_authority)

    why_not: List[str] = []
    if regime_wait_explanation:
        why_not.extend(regime_wait_explanation[:3])
    if not has_trade and no_setup_diagnosis:
        why_not.append(
            no_setup_diagnosis.get("primary_blocker")
            or no_setup_diagnosis.get("headline", "")
        )
    if dm.get("guidance"):
        why_not.append(str(dm["guidance"]))
    if not why_not:
        why_not.append(
            "No name passed full TRADE bar (thesis+timing, R:R ≥2.5, execution-ready)."
        )

    risk_blockers: List[str] = []
    if event_risks:
        risk_blockers.extend(event_risks[:4])
    ex = execution_readiness or ba.get("execution_readiness") or {}
    if not ex.get("broker_connected") and not ex.get("ibkr_connected"):
        risk_blockers.append("Broker offline — ENGINE OFF blocks live handoff")
    elif ex.get("readiness_label"):
        if "blocked" in str(ex.get("level", "")).lower():
            risk_blockers.append(f"Execution: {ex.get('readiness_label')}")
    if not ex.get("bracket_order_ready") and not ex.get("bracket_ready"):
        risk_blockers.append("Bracket not ready — cannot send protected order")
    if dm.get("macro_regime") == "Hostile":
        risk_blockers.append(f"Macro hostile — {dm.get('macro_detail', '')[:80]}")
    if dm.get("opportunity_quality") == "Weak":
        risk_blockers.append(f"Board weak — {dm.get('opportunity_detail', '')[:80]}")

    exec_label = dm.get("execution_readiness") or ex.get("readiness_label") or "—"
    if ex.get("paper_or_live"):
        exec_label = f"{exec_label} · {(ex.get('paper_or_live') or 'paper').upper()}"

    if decision_authority and decision_authority.get("source") == "fallback_brief":
        deploy_label = "Brief fallback — informational watch only"
        can_deploy = False

    return {
        "day_state": day_state,
        "hero_label": hero_label,
        "deploy_posture": posture,
        "deploy_label": deploy_label,
        "can_deploy_today": can_deploy,
        "execution_ready_count": exec_ready_count,
        "regime": {
            "trend": trend_label,
            "tradeability": tradeability,
            "macro": dm.get("macro_regime"),
            "opportunity": dm.get("opportunity_quality"),
        },
        "best_trade": best_trade,
        "best_watch": best_watch,
        "best_pilot": best_pilot,
        "trade_count": len(trade_rows),
        "pilot_count": len(pilot_rows),
        "watch_count": len(watch_rows),
        "why_not_aggressive": [w for w in why_not if w][:5],
        "risk_blockers": [r for r in risk_blockers if r][:6],
        "execution_readiness_label": exec_label,
        "capital_stance": ba.get("capital_stance"),
        "stance_one_liner": ba.get("stance_one_liner"),
        "narrative_snippet": (narrative or "")[:280],
        "headline": (
            f"{deploy_label} · Best TRADE: {(best_trade or {}).get('ticker') or 'None'}"
            f" · Watch: {(best_watch or {}).get('ticker') or '—'}"
        ),
    }


def _apply_hero_authority(label: str, authority: Optional[Dict[str, Any]]) -> str:
    if not authority or not label:
        return label
    if authority.get("authority_level") == "suspended":
        return (
            "Top fallback candidate"
            if authority.get("source") == "fallback_brief"
            else ""
        )
    if authority.get("gates_active") or not authority.get("allows_trade_labels"):
        if "TRADE" in label.upper():
            return "#1 WATCH TODAY"
    return label


def build_sleeve_summary(
    cards: List[Dict[str, Any]],
    regime: str = "",
    *,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Deployability-aware sleeve strip (replaces alpha-only optics)."""
    if not cards:
        return {
            "strongest_live": None,
            "active_today": None,
            "fund_manager": None,
            "cards": [],
            "note": "Load funds for sleeve deploy state",
        }
    active = [c for c in cards if c.get("gate_status") == "ACTIVE"]
    sorted_cards = sorted(
        cards,
        key=lambda c: (-(c.get("regime_fit") or 0), -(c.get("excess_return_pct") or 0)),
    )
    strongest = sorted_cards[0] if sorted_cards else None
    controller = next((c for c in cards if c.get("controls_capital")), strongest)
    strongest_training = max(
        cards, key=lambda c: c.get("excess_return_pct") or 0, default=None
    )

    def _card_strip(c: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not c:
            return None
        return {
            "id": c.get("id"),
            "display_name": c.get("display_name"),
            "gate_status": c.get("gate_status"),
            "stance": c.get("stance") or c.get("fund_manager_stance"),
            "mode": c.get("mode", "training"),
            "controls_capital": bool(c.get("controls_capital")),
            "regime_fit": c.get("regime_fit"),
            "excess_return_pct": c.get("excess_return_pct"),
            "max_drawdown_pct": c.get("max_drawdown_pct"),
            "equity_curve_20": c.get("equity_curve_20") or [],
            "evidence_badge": c.get("evidence_badge", "model_backtest"),
            "status_reason": c.get("status_reason"),
            "evidence_quality": c.get("evidence_quality"),
            "last_change": c.get("last_change") or c.get("last_rebalance"),
            "upgrade_trigger": c.get("upgrade_trigger") or c.get("next_trigger"),
            "top_monitored": c.get("top_monitored") or [],
            "deployability": c.get("deployability"),
        }

    live_sleeves = [c for c in cards if (c.get("mode") or "").lower() == "live"]
    strongest_live_card = (
        max(live_sleeves, key=lambda c: c.get("regime_fit") or 0, default=None)
        if live_sleeves
        else strongest
    )
    evidence_q = (controller or {}).get("evidence_quality") or "model_backtest"
    allocation_reason = (controller or {}).get("status_reason") or (
        f"Regime fit {(controller or {}).get('regime_fit', 0)}% · "
        f"gate {(controller or {}).get('gate_status', '—')}"
        if controller
        else ""
    )
    risk_budget = (
        f"Max DD {(controller or {}).get('max_drawdown_pct', '—')}% · "
        f"cash reserve per allocator"
        if controller
        else "—"
    )
    sleeve_action = (controller or {}).get("stance") or "NEUTRAL"
    if (controller or {}).get("gate_status") == "PAUSED":
        sleeve_action = "PAUSE"
    elif (controller or {}).get("gate_status") == "REDUCED":
        sleeve_action = "REDUCE"

    leader_names = [
        (s.get("name") or s.get("symbol") or "")
        for s in (sector_leaders or [])[:3]
        if s
    ]
    sector_rotation = (
        f"Rotate toward {', '.join(leader_names)} — active sleeve favors "
        f"names with sector tailwind"
        if leader_names
        else "No clear sector leadership — sleeve stays balanced"
    )
    monitored = (controller or {}).get("top_monitored") or []
    top_adds = [
        m.get("ticker") or m.get("symbol")
        for m in monitored[:3]
        if isinstance(m, dict) and (m.get("ticker") or m.get("symbol"))
    ]
    if not top_adds and monitored:
        top_adds = [str(m) for m in monitored[:3]]
    activation = (controller or {}).get("upgrade_trigger") or (
        "Gate → ACTIVE when regime fit ≥70% and drawdown within budget"
        if controller
        else ""
    )

    return {
        "strongest_live": _card_strip(strongest_live_card or strongest),
        "strongest_training": _card_strip(strongest_training),
        "active_today": _card_strip(controller),
        "fund_manager": {
            "active_sleeve_id": (controller or {}).get("id"),
            "active_sleeve_name": (controller or {}).get("display_name"),
            "stance": (controller or {}).get("stance", "NEUTRAL"),
            "mode": (controller or {}).get("mode", "training"),
            "controls_capital": bool((controller or {}).get("controls_capital")),
            "regime_fit": (controller or {}).get("regime_fit"),
            "evidence_quality": evidence_q,
            "allocation_reason": allocation_reason,
            "risk_budget": risk_budget,
            "sleeve_action_now": sleeve_action,
            "upgrade_trigger": (controller or {}).get("upgrade_trigger"),
            "sector_rotation_note": sector_rotation,
            "leading_sector_implication": (
                f"Leading sectors ({', '.join(leader_names)}) support "
                f"{(controller or {}).get('display_name', 'active sleeve')} "
                f"overweight when gate is ACTIVE"
                if leader_names
                else "No sector leadership edge for sleeve tilt today"
            ),
            "top_adds": top_adds,
            "top_trims": [],
            "activation_trigger": activation,
        },
        "active_count": len(active),
        "paused_count": len([c for c in cards if c.get("gate_status") == "PAUSED"]),
        "cards": [_card_strip(c) for c in sorted_cards[:6] if _card_strip(c)],
        "regime": regime,
        "stance": (
            f"Active: {(controller or {}).get('display_name')} · "
            f"{(controller or {}).get('stance', 'NEUTRAL')} · "
            f"{(controller or {}).get('gate_status', '—')}"
            if controller
            else "No sleeve data"
        ),
    }


def merge_brief_board_fallback(
    top5: List[Dict[str, Any]],
    near_miss: List[Dict[str, Any]],
    *,
    scanner_degraded: bool,
    top_limit: int = 5,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    """Seed WATCH / near-miss rows from morning brief when live scanner is empty."""
    from src.services.cc_live_policy import cc_live_data_only_enabled

    if cc_live_data_only_enabled():
        return top5, near_miss, False
    if top5 or not scanner_degraded:
        return top5, near_miss, False
    try:
        from src.services.playbook_board_fallback import build_compressed_fallback

        fb = build_compressed_fallback(max(30, top_limit))
    except Exception:
        return top5, near_miss, False

    opps = fb.get("opportunities") or []
    fb_near = fb.get("near_miss") or []
    if not opps and not fb_near:
        return top5, near_miss, False

    from src.services.decision_truth_model import assemble_confidence_breakdown

    merged_top: List[Dict[str, Any]] = []
    for i, row in enumerate(opps[:top_limit]):
        why = row.get("why_now")
        base = {
            "rank": i + 1,
            "ticker": row.get("ticker"),
            "strategy": row.get("setup") or "brief_watch",
            "score": row.get("score", 0),
            "grade": row.get("grade", "C"),
            "timing": "Developing",
            "action": "WATCH",
            "raw_action": row.get("action") or "WATCH",
            "action_reason": (
                "Morning brief fallback — reference plan only · indicative levels · "
                "monitor zone · no deploy authority"
            ),
            "why_now": [why] if isinstance(why, str) and why else (why or []),
            "entry_price": row.get("entry_price"),
            "target_price": row.get("target_price"),
            "stop_price": row.get("stop_price"),
            "risk_reward": row.get("risk_reward"),
            "invalidation": row.get("invalidation"),
            "execution_ready": False,
            "confidence_fallback_only": True,
            "card_display_mode": "reference_only",
            "levels_indicative_only": True,
            "deploy_authority": False,
            "monitor_zone_only": True,
            "evidence_badge": row.get("evidence_badge") or "brief-fallback",
            "thesis_conf": 0,
            "timing_conf": 0,
            "exec_conf": 0,
            "data_conf": 0,
        }
        conf = assemble_confidence_breakdown(base)
        base["confidence_breakdown"] = conf
        base["final_conf"] = conf.get("final")
        merged_top.append(base)

    merged_near = list(near_miss)
    if not merged_near and fb_near:
        merged_near = fb_near[:3]

    return merged_top, merged_near, True
