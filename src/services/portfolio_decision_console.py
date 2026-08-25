"""Portfolio decision console — allocator-grade layer on top of holdings analytics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_SINGLE_PCT = 0.12
_DRIFT_REBALANCE_PCT = 0.05
_SECTOR_CAP_PCT = 0.40
_HEAT_TARGET_PCT = 6.0
_BENCHMARK_MIN_POSITIONS = 3
_BENCHMARK_MIN_OBSERVATIONS = 20

_LOCAL_ONLY_COPY = (
    "Local book only — not broker truth. All exposure, stop, and rebalance "
    "instructions below are based on manually tracked positions. Confirm actual "
    "broker holdings before acting."
)
_BROKER_OFFLINE_COPY = (
    "Execution truth not confirmed. Portfolio is based on local manual entries, "
    "not broker-synced positions. Confirm actual broker state before acting on "
    "trim / stop / exposure instructions."
)
_HEAT_BREACH_COPY = (
    "Planned heat is no longer the right primary metric here. The stop has already "
    "been breached, so '0.00R planned risk' can be misleading. Show this state as "
    "unmanaged post-breach risk, not zero risk."
)
_ALLOC_MONITOR_COPY = (
    "Policy breach — current position exceeds portfolio rules. Current weight should "
    "be compared against policy max / target, not against an implicit 100% target."
)
_BENCHMARK_DISCLAIMER_COPY = (
    "Performance statistics are unstable with a one-name local-only book. Treat alpha, "
    "beta, and benchmark-relative path as illustrative only until broker sync and "
    "broader portfolio depth exist."
)
_SLEEVE_COLLAPSE_COPY = (
    "Sleeve research available below — current position risk takes priority"
)


def _position_price(position: Dict[str, Any]) -> float:
    return float(position.get("current_price") or position.get("entry_price") or 0)


def _position_stop(position: Dict[str, Any]) -> float:
    return float(
        position.get("stop_price")
        or position.get("stop")
        or position.get("current_stop")
        or position.get("initial_stop")
        or 0
    )


def _is_stop_breached(position: Dict[str, Any]) -> bool:
    """LONG book: price at or below stop means breach."""
    stop = _position_stop(position)
    px = _position_price(position)
    if stop <= 0 or px <= 0:
        return False
    if position.get("risk_status") == "STOP BREACHED":
        return True
    return px <= stop


def _open_r_multiple(position: Dict[str, Any]) -> Optional[float]:
    if position.get("unrealized_r") is not None:
        try:
            return float(position["unrealized_r"])
        except (TypeError, ValueError):
            pass
    entry = float(position.get("entry_price") or position.get("avg_cost") or 0)
    stop = _position_stop(position)
    px = _position_price(position)
    if entry <= 0 or stop <= 0 or px <= 0:
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    return round((px - entry) / risk, 2)


def _sleeve_owner_label(position: Dict[str, Any]) -> str:
    """Never leak raw booleans into sleeve column."""
    sleeve = position.get("sleeve")
    if isinstance(sleeve, bool):
        return "core book" if not sleeve else "sleeve deploy"
    if sleeve is not None and str(sleeve).strip():
        text = str(sleeve).strip()
        if text.lower() in ("true", "false"):
            return "core book" if text.lower() == "false" else "sleeve deploy"
        return text
    strategy = position.get("strategy_id")
    if strategy:
        return str(strategy)
    return "core book"


def _format_deploy_label(
    deploy_capital: Any,
    deploy_posture: Optional[str] = None,
) -> str:
    """Human-readable sleeve deploy label — never leak raw booleans."""
    if isinstance(deploy_capital, bool):
        if deploy_capital:
            posture = (deploy_posture or "selective_deploy").replace("_", " ")
            return f"Deploy · {posture}"
        return "Preserve cash · no sleeve deploy"
    if deploy_capital is not None and str(deploy_capital).strip():
        text = str(deploy_capital).replace("_", " ")
        if text.lower() in ("true", "false"):
            return _format_deploy_label(text.lower() == "true", deploy_posture)
        return text
    if deploy_posture:
        return str(deploy_posture).replace("_", " ")
    return ""


def compute_portfolio_heat(
    positions: List[Dict[str, Any]],
    *,
    equity: Optional[float] = None,
) -> Dict[str, Any]:
    """Portfolio heat with explicit stop-coverage and stop-breach semantics."""
    total = equity or _total_value(positions) or 1.0
    heat_dollars = 0.0
    with_stop = 0
    without_stop = 0
    stop_breached: List[Dict[str, Any]] = []
    post_breach_open_r = 0.0
    for p in positions:
        px = _position_price(p)
        stop = _position_stop(p)
        sh = float(p.get("shares") or p.get("quantity") or 0)
        if _is_stop_breached(p):
            open_r = _open_r_multiple(p)
            ticker = p.get("ticker") or "—"
            stop_breached.append(
                {
                    "ticker": ticker,
                    "open_r": open_r,
                    "current_price": round(px, 2) if px else None,
                    "stop_price": round(stop, 2) if stop else None,
                }
            )
            if open_r is not None:
                post_breach_open_r += open_r
            if stop > 0:
                with_stop += 1
            continue
        if px > 0 and stop > 0 and sh > 0:
            heat_dollars += max(0.0, (px - stop) * sh)
            with_stop += 1
        else:
            without_stop += 1
    heat_pct = (heat_dollars / total) * 100 if total else 0.0
    heat_r = heat_dollars / max(1.0, total * 0.01)
    coverage = (with_stop / len(positions) * 100) if positions else 0.0
    breached_count = len(stop_breached)
    breached_tickers = [b["ticker"] for b in stop_breached if b.get("ticker")]
    if breached_count:
        heat_available = False
        quality = "stop_breached"
        quality_label = "Stop breached — exit risk unmanaged"
        heat_display = "POST-BREACH"
        heat_warning = _HEAT_BREACH_COPY
        heat_model = "disabled_stop_breach"
    elif without_stop and with_stop:
        heat_available = with_stop > 0 and heat_dollars > 0
        quality = "partial"
        quality_label = "Risk model partial until stop is added"
        heat_display = None
        heat_warning = None
        heat_model = "planned_risk_partial"
    elif without_stop and positions:
        heat_available = False
        quality = "unavailable"
        quality_label = "Heat unavailable — stop not set"
        heat_display = None
        heat_warning = None
        heat_model = "unavailable"
    elif with_stop:
        heat_available = True
        quality = "measured"
        quality_label = "Measured — all positions have stops"
        heat_display = None
        heat_warning = None
        heat_model = "planned_risk"
    else:
        heat_available = False
        quality = "empty"
        quality_label = "No open positions"
        heat_display = None
        heat_warning = None
        heat_model = "empty"
    return {
        "heat_dollars": round(heat_dollars, 2) if not breached_count else None,
        "heat_pct": round(heat_pct, 3) if heat_available else None,
        "heat_r": round(heat_r, 3) if heat_available else None,
        "with_stop": with_stop,
        "without_stop": without_stop,
        "stop_coverage_pct": round(coverage, 1),
        "heat_available": heat_available,
        "heat_quality": quality,
        "heat_quality_label": quality_label,
        "heat_display": heat_display,
        "heat_warning": heat_warning,
        "heat_model": heat_model,
        "stop_breached_count": breached_count,
        "stop_breached_tickers": breached_tickers,
        "stop_breached_positions": stop_breached,
        "post_breach_open_r": round(post_breach_open_r, 2),
        "post_breach_note": (
            "Open risk collapsed to 0 only because stop is already breached; "
            "position is now realized decision risk, not protected planned risk."
            if breached_count
            else None
        ),
    }


def build_ibkr_linkage(
    *,
    source: str,
    execution: Dict[str, Any],
    positions: List[Dict[str, Any]],
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Broker truth vs local model separation for portfolio tab."""
    broker_connected = bool(execution.get("broker_connected"))
    mode = (execution.get("mode") or "manual").lower()
    src = (source or "manual").lower()
    broker_positions = sum(1 for p in positions if (p.get("source") or "").lower() == "broker")
    local_only = sum(
        1
        for p in positions
        if (p.get("source") or src) != "broker" and not p.get("broker_synced")
    )
    if broker_connected and local_only and broker_positions:
        pill = "MIXED STALE"
    elif broker_connected and local_only:
        pill = "MIXED"
    elif broker_connected or src == "ibkr":
        pill = "IBKR LIVE" if mode == "live" else "IBKR PAPER"
    else:
        pill = "MANUAL"
    sync_quality = (
        "broker_truth"
        if broker_connected and not local_only
        else "mixed_local_broker"
        if broker_connected and local_only
        else "local_only"
    )
    return {
        "source_pill": pill,
        "portfolio_source": src,
        "broker_connected": broker_connected,
        "broker_mode": mode,
        "last_sync": execution.get("last_heartbeat") or updated_at,
        "sync_quality": sync_quality,
        "sync_lag_note": (
            "Broker session active"
            if broker_connected
            else "Not connected — local model only"
        ),
        "broker_position_count": broker_positions,
        "local_only_count": local_only,
        "unsynced_count": local_only,
        "broker_truth": broker_connected and not local_only,
        "local_model_note": (
            "Broker is source of truth"
            if broker_connected and not local_only
            else "Mixed local + broker — reconcile stops"
            if broker_connected and local_only
            else "Local book — connect IBKR for broker truth"
        ),
        "local_only_banner": _LOCAL_ONLY_COPY if sync_quality == "local_only" else None,
        "broker_offline_banner": (
            _BROKER_OFFLINE_COPY
            if sync_quality in ("local_only", "mixed_local_broker") and not broker_connected
            else _BROKER_OFFLINE_COPY
            if sync_quality == "local_only"
            else None
        ),
        "execution_warning": (
            _BROKER_OFFLINE_COPY
            if not (broker_connected and not local_only)
            else None
        ),
    }


def _total_value(positions: List[Dict[str, Any]]) -> float:
    return sum(float(p.get("market_value") or 0) for p in positions)


def build_allocation_monitor(
    positions: List[Dict[str, Any]],
    *,
    max_single_pct: float = _MAX_SINGLE_PCT,
    custom_targets: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Current vs policy cap (default) with excess and secondary equal-weight drift."""
    n = len(positions)
    if n == 0:
        return []
    total = _total_value(positions) or 1.0
    eq_target = 1.0 / n
    policy_pct = round(max_single_pct * 100, 0)
    custom = custom_targets or {}
    rows: List[Dict[str, Any]] = []
    for p in sorted(positions, key=lambda x: -(float(x.get("market_value") or 0))):
        ticker = str(p.get("ticker") or "—")
        mv = float(p.get("market_value") or 0)
        current = mv / total if total else 0.0
        current_pct = round(current * 100, 2)
        custom_tgt = custom.get(ticker.upper())
        if custom_tgt is not None:
            target = float(custom_tgt) / 100.0 if custom_tgt > 1 else float(custom_tgt)
            target_type = "custom"
            display_target_pct = round(target * 100, 2)
        else:
            target = max_single_pct
            target_type = "policy_cap"
            display_target_pct = policy_pct
        excess = max(0.0, current - max_single_pct)
        excess_pct = round(excess * 100, 2)
        eq_drift = current - eq_target
        eq_drift_pct = round(eq_drift * 100, 2)
        if current > max_single_pct:
            action = "TRIM URGENT" if current >= 0.5 or n == 1 else "TRIM"
            priority = "critical" if current >= 0.5 or n == 1 else "high"
            tier = "critical"
            reason = (
                f"Policy breach — {current_pct:.1f}% vs {policy_pct:.0f}% max "
                f"(excess +{excess_pct:.1f}%)"
            )
            action_size = excess_pct
            urgency = "now"
        elif eq_drift > _DRIFT_REBALANCE_PCT:
            action = "TRIM"
            priority = "medium"
            tier = "secondary"
            reason = "Overweight vs equal-weight target"
            action_size = abs(eq_drift_pct)
            urgency = "today"
        elif eq_drift < -_DRIFT_REBALANCE_PCT:
            action = "ADD"
            priority = "medium"
            tier = "secondary"
            reason = "Underweight vs equal-weight target"
            action_size = abs(eq_drift_pct)
            urgency = "today"
        else:
            action = "HOLD"
            priority = "low"
            tier = "secondary"
            reason = "Within drift band"
            action_size = 0.0
            urgency = "next rebalance"
        rows.append(
            {
                "asset": ticker,
                "current_weight_pct": current_pct,
                "policy_max_pct": policy_pct,
                "target_weight_pct": display_target_pct,
                "target_type": target_type,
                "excess_pct": excess_pct,
                "drift_pct": eq_drift_pct,
                "action_required": action,
                "priority": priority,
                "tier": tier,
                "reason": reason,
                "rationale": reason,
                "policy_note": _ALLOC_MONITOR_COPY if current > max_single_pct else None,
                "trigger": (
                    f"Excess +{excess_pct:.1f}% vs {policy_pct:.0f}% cap"
                    if current > max_single_pct
                    else f"Drift ≥ {_DRIFT_REBALANCE_PCT * 100:.0f}%"
                    if abs(eq_drift) >= _DRIFT_REBALANCE_PCT
                    else "Within band"
                ),
                "urgency": urgency,
                "sleeve_owner": _sleeve_owner_label(p),
                "action_size_pct": round(action_size, 2) if action != "HOLD" else 0.0,
                "recommended_action": action.replace(" URGENT", ""),
                "estimated_trade_hint": (
                    f"~{action_size:.1f}% of portfolio"
                    if action != "HOLD"
                    else "—"
                ),
            }
        )
    return rows


def build_return_attribution(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Contribution to return / drawdown proxy by holding."""
    total = _total_value(positions) or 1.0
    contrib_return: List[Dict[str, Any]] = []
    contrib_risk: List[Dict[str, Any]] = []
    for p in positions:
        w = float(p.get("market_value") or 0) / total
        pnl_pct = float(p.get("pnl_pct") or 0)
        contrib = round(w * pnl_pct, 3)
        contrib_return.append(
            {
                "asset": p.get("ticker"),
                "weight_pct": round(w * 100, 2),
                "return_pct": pnl_pct,
                "contribution_pct": contrib,
            }
        )
        # Vol proxy: large weight + negative pnl = drawdown contributor
        dd_score = round(w * max(0, -pnl_pct), 3)
        contrib_risk.append(
            {
                "asset": p.get("ticker"),
                "weight_pct": round(w * 100, 2),
                "vol_contribution_proxy": round(w * abs(pnl_pct), 3),
                "drawdown_contribution_proxy": dd_score,
            }
        )
    contrib_return.sort(key=lambda x: -abs(x["contribution_pct"]))
    contrib_risk.sort(key=lambda x: -x["drawdown_contribution_proxy"])
    top = contrib_return[0] if contrib_return else None
    drag = min(contrib_return, key=lambda x: x["contribution_pct"]) if contrib_return else None
    return {
        "by_return": contrib_return,
        "by_risk": contrib_risk,
        "top_contributor": top,
        "top_detractor": drag,
        "allocation_effect_note": "Equal-weight target; drift drives rebalance urgency",
        "selection_effect_note": "Per-name pnl% × weight — simplified attribution",
    }


def build_regime_fit(
    regime: Dict[str, Any],
    positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Macro regime overlay for portfolio posture."""
    tradeability = regime.get("tradeability") or "WAIT"
    trend = regime.get("trend") or regime.get("label") or "NEUTRAL"
    vix = regime.get("vix")
    breadth = regime.get("breadth")
    score = 50
    if tradeability in ("STRONG_TRADE", "TRADE"):
        score += 20
    if tradeability in ("NO_TRADE",):
        score -= 30
    if breadth is not None and float(breadth) > 50:
        score += 10
    if vix is not None and float(vix) > 25:
        score -= 15
    score = max(0, min(100, score))
    aligned = score >= 55
    posture = (
        "aggressive"
        if tradeability == "STRONG_TRADE"
        else "defensive"
        if tradeability in ("NO_TRADE", "WAIT")
        else "neutral"
    )
    return {
        "current_regime": f"{trend} · {tradeability}",
        "best_historical_regime": "Risk-on / broad breadth (model)",
        "worst_historical_regime": "Risk-off / VIX spike (model)",
        "regime_fit_score": score,
        "aligned_with_regime": aligned,
        "suggested_posture": posture,
        "note": (
            "Aligned — maintain sizing"
            if aligned
            else "Misaligned — reduce risk or wait for breadth"
        ),
        "position_count": len(positions),
    }


def build_benchmark_intel(
    positions: List[Dict[str, Any]],
    summary: Optional[Dict[str, Any]],
    benchmark: str = "SPY",
    *,
    broker_synced: bool = False,
    observation_count: int = 0,
) -> Dict[str, Any]:
    """Benchmark-relative snapshot (portfolio book level)."""
    total_pnl_pct = float((summary or {}).get("total_pnl_pct") or 0)
    n = len(positions)
    stats_reliable = (
        n >= _BENCHMARK_MIN_POSITIONS
        and broker_synced
        and observation_count >= _BENCHMARK_MIN_OBSERVATIONS
    )
    verdict = (
        "OUTPERFORMING"
        if total_pnl_pct > 1
        else "LAGGING"
        if total_pnl_pct < -1
        else "INLINE"
    )
    disclaimer = None
    if not stats_reliable:
        if n < _BENCHMARK_MIN_POSITIONS or not broker_synced:
            disclaimer = _BENCHMARK_DISCLAIMER_COPY
        else:
            disclaimer = (
                "Performance statistics need more history — treat alpha, beta, and "
                "benchmark-relative path as illustrative until ≥20 observations."
            )
    return {
        "benchmark": benchmark,
        "portfolio_return_proxy_pct": total_pnl_pct,
        "verdict": verdict,
        "stats_reliable": stats_reliable,
        "stats_disclaimer": disclaimer,
        "display_mode": "full" if stats_reliable else "illustrative",
        "min_positions": _BENCHMARK_MIN_POSITIONS,
        "min_observations": _BENCHMARK_MIN_OBSERVATIONS,
        "position_count": n,
        "observation_count": observation_count,
        "rolling_alpha_note": "Full rolling alpha requires equity curve — use Perf Lab",
        "rolling_beta_note": "Estimate from position betas when live curve wired",
        "tracking_error_note": "—",
        "information_ratio_note": "—",
        "upside_capture_note": "Wire 60d equity vs SPY for capture ratios",
        "downside_capture_note": "Wire 60d equity vs SPY for capture ratios",
    }


def build_action_needed(
    alerts: List[Dict[str, Any]],
    allocation_rows: List[Dict[str, Any]],
    *,
    heat_pct: float = 0.0,
    top_concentration_pct: float = 0.0,
    heat: Optional[Dict[str, Any]] = None,
    ibkr_linkage: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Alerts / action-needed box — critical tier first, then secondary."""
    critical: List[Dict[str, Any]] = []
    secondary: List[Dict[str, Any]] = []
    heat = heat or {}

    for ticker in heat.get("stop_breached_tickers") or []:
        open_r = next(
            (
                b.get("open_r")
                for b in (heat.get("stop_breached_positions") or [])
                if b.get("ticker") == ticker
            ),
            None,
        )
        r_note = f" ({open_r:+.2f}R open)" if open_r is not None else ""
        critical.append(
            {
                "severity": "critical",
                "tier": "critical",
                "category": "stop_breach",
                "message": f"🛑 {ticker} stop breached{r_note} — exit risk unmanaged",
                "asset": ticker,
            }
        )

    linkage = ibkr_linkage or {}
    if linkage.get("sync_quality") == "local_only" or not linkage.get("broker_truth"):
        critical.append(
            {
                "severity": "critical",
                "tier": "critical",
                "category": "broker_sync",
                "message": linkage.get("broker_offline_banner") or _BROKER_OFFLINE_COPY,
                "asset": None,
            }
        )

    if top_concentration_pct >= 99 and len(allocation_rows) <= 1:
        ticker = allocation_rows[0]["asset"] if allocation_rows else None
        critical.append(
            {
                "severity": "critical",
                "tier": "critical",
                "category": "concentration",
                "message": f"Single-name book at {top_concentration_pct:.0f}% — {ticker or 'position'} dominates all risk",
                "asset": ticker,
            }
        )
    elif top_concentration_pct > _MAX_SINGLE_PCT * 100:
        secondary.append(
            {
                "severity": "warning",
                "tier": "secondary",
                "category": "concentration",
                "message": f"Largest position {top_concentration_pct:.1f}% — trim or hedge",
                "asset": None,
            }
        )

    for a in alerts[:6]:
        item = {
            "severity": a.get("severity", "warning"),
            "tier": "critical" if a.get("severity") == "critical" else "secondary",
            "category": a.get("type", "alert"),
            "message": a.get("msg", ""),
            "asset": a.get("ticker"),
        }
        (critical if item["tier"] == "critical" else secondary).append(item)

    for row in allocation_rows:
        if row.get("tier") == "critical" and row.get("action_required") != "HOLD":
            critical.append(
                {
                    "severity": "critical",
                    "tier": "critical",
                    "category": "policy_breach",
                    "message": (
                        f"{row['asset']}: {row['action_required']} — "
                        f"current {row['current_weight_pct']:.0f}% vs policy max "
                        f"{row.get('policy_max_pct', _MAX_SINGLE_PCT * 100):.0f}% "
                        f"(excess +{row.get('excess_pct', 0):.0f}%)"
                    ),
                    "asset": row["asset"],
                }
            )
        elif row.get("priority") in ("high", "medium") and row.get("action_required") != "HOLD":
            secondary.append(
                {
                    "severity": "warning",
                    "tier": "secondary",
                    "category": "rebalance_drift",
                    "message": f"{row['asset']}: {row['action_required']} — {row['reason']}",
                    "asset": row["asset"],
                }
            )

    if heat_pct > 6 and heat.get("heat_available"):
        secondary.append(
            {
                "severity": "critical",
                "tier": "secondary",
                "category": "portfolio_heat",
                "message": f"Total heat {heat_pct:.1f}% > 6% — reduce risk",
                "asset": None,
            }
        )

    if heat.get("without_stop") and not heat.get("stop_breached_count"):
        secondary.append(
            {
                "severity": "warning",
                "tier": "secondary",
                "category": "stop_coverage",
                "message": heat.get("heat_quality_label", "Stop missing on positions"),
                "asset": None,
            }
        )

    out = critical + secondary
    return out[:12]


def build_allocator_summary(
    *,
    positions: List[Dict[str, Any]],
    summary: Optional[Dict[str, Any]],
    regime: Dict[str, Any],
    allocation_rows: List[Dict[str, Any]],
    execution: Dict[str, Any],
    fund_allocator: Dict[str, Any],
    source: str,
) -> Dict[str, Any]:
    """Top-of-page Portfolio Decision Summary."""
    n = len(positions)
    total_pnl = float((summary or {}).get("total_pnl_pct") or 0)
    tradeability = regime.get("tradeability") or "WAIT"

    overweight = next(
        (r for r in allocation_rows if str(r.get("action_required") or "").startswith("TRIM")),
        None,
    )
    underweight = next(
        (r for r in allocation_rows if r.get("action_required") == "ADD"),
        None,
    )
    rebalance_suggested = any(
        str(r.get("action_required") or "").startswith(("TRIM", "ADD"))
        and r.get("priority") != "low"
        for r in allocation_rows
    )

    if tradeability == "NO_TRADE":
        stance = "REDUCE"
    elif rebalance_suggested:
        stance = "REBALANCE"
    elif total_pnl < -3:
        stance = "REDUCE"
    elif n == 0:
        stance = "PAUSE"
    elif tradeability in ("STRONG_TRADE", "TRADE"):
        stance = "HOLD"
    else:
        stance = "HOLD"

    deploy = fund_allocator.get("deploy_capital")
    deploy_posture = fund_allocator.get("deploy_posture")
    deploy_label = _format_deploy_label(deploy, deploy_posture)
    if overweight:
        recommended_action = (
            f"Trim {overweight['asset']} first — {overweight.get('reason', 'overweight')}"
        )
    elif underweight:
        recommended_action = (
            f"Add {underweight['asset']} first — {underweight.get('reason', 'underweight')}"
        )
    elif deploy_label:
        recommended_action = deploy_label
    else:
        recommended_action = "Monitor — no urgent rebalance"

    evidence = "live" if source == "ibkr" else "manual" if n else "empty"
    if execution.get("broker_connected"):
        evidence = "live_ibkr" if source == "ibkr" else "mixed"

    return {
        "stance": stance,
        "best_allocation_model": "Equal-risk sleeve (default policy)",
        "last_rebalance_date": "—",
        "current_risk_regime": regime.get("tradeability") or "—",
        "rebalance_suggested": rebalance_suggested,
        "most_overweight": overweight["asset"] if overweight else "—",
        "most_underweight": underweight["asset"] if underweight else "—",
        "largest_risk_contributor": overweight["asset"] if overweight else "—",
        "benchmark_relative_verdict": (
            "OUTPERFORMING"
            if total_pnl > 1
            else "LAGGING"
            if total_pnl < -1
            else "INLINE"
        ),
        "recommended_action": recommended_action,
        "confidence": "medium" if n >= 2 else "low",
        "evidence_quality": evidence,
        "capital_stance": fund_allocator.get("stance_one_liner")
        or fund_allocator.get("marginal_instruction"),
    }


def build_sleeve_monitor(fund_console: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Active fund / sleeve rows from fund manager console."""
    cards = fund_console.get("cards") or []
    out: List[Dict[str, Any]] = []
    for c in cards[:6]:
        mb = c.get("manager_box") or {}
        gs = (c.get("gate_status") or "NO_DATA").upper()
        evidence_raw = c.get("evidence_badge") or "model_backtest"
        evidence_type = (
            "LIVE"
            if "live" in str(evidence_raw).lower()
            else "PAPER"
            if "paper" in str(evidence_raw).lower()
            else "BACKTEST"
            if "backtest" in str(evidence_raw).lower() or "train" in str(evidence_raw).lower()
            else "HEURISTIC"
            if "mixed" in str(evidence_raw).lower()
            else "BACKTEST"
        )
        deployable = gs == "ACTIVE"
        out.append(
            {
                "id": c.get("id"),
                "name": c.get("display_name"),
                "status": gs.replace("_", " "),
                "stance": c.get("stance") or mb.get("manager_state") or "—",
                "action": "Deploy" if deployable else "Pause" if gs in ("PAUSED", "REDUCED") else "Monitor",
                "why_now": c.get("stance") or mb.get("manager_state") or "—",
                "why_not_full_size": (
                    c.get("status_reason")
                    if not deployable
                    else "Gate active — size within risk budget"
                ),
                "risk_budget_pct": mb.get("capital_deployed_pct"),
                "best_regime": c.get("regime_fit") or "—",
                "blocker": c.get("status_reason") if not deployable else None,
                "capital_deployed_pct": mb.get("capital_deployed_pct"),
                "allocation_weight_pct": mb.get("capital_deployed_pct"),
                "regime_fit": c.get("regime_fit"),
                "return_pct": c.get("total_return_pct"),
                "excess_pct": c.get("excess_return_pct"),
                "max_drawdown_pct": c.get("max_drawdown_pct"),
                "next_trigger": mb.get("next_trigger"),
                "reactivation_trigger": mb.get("next_trigger") or c.get("next_trigger"),
                "paused_reason": c.get("status_reason") if gs in ("PAUSED", "REDUCED") else None,
                "confidence": c.get("confidence") or ("high" if gs == "ACTIVE" else "low"),
                "deployable_now": deployable,
                "evidence_type": evidence_type,
                "live_trade_count": c.get("live_trade_count") or 0,
                "sample_window": c.get("period") or "1y backtest",
                "last_rebalance": mb.get("last_rebalance") or "—",
                "top_holdings": (c.get("top_holdings") or [])[:3],
                "evidence": evidence_raw,
            }
        )
    return out


def build_why_now(
    allocator_summary: Dict[str, Any],
    regime_fit: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "why_works_now": [
            allocator_summary.get("recommended_action", ""),
            regime_fit.get("note", ""),
        ],
        "why_may_stop": [
            "Regime shifts to NO_TRADE or breadth collapses",
            "Largest position breaches concentration cap",
        ],
        "rebalance_triggers": [
            "Drift > 5% vs equal-weight target",
            "Single name > 12% of portfolio",
            "Portfolio heat > 6%",
        ],
        "watch_next": [
            "VIX and breadth on Today tab",
            "Stop breaches in Action Needed",
            "Sleeve regime_fit on fund console",
        ],
    }


def _sanitize_brinson(brinson: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Suppress unstable Brinson decomposition when heuristic blows up."""
    if not isinstance(brinson, dict):
        return None
    alloc = abs(float(brinson.get("allocation_effect") or 0))
    select = abs(float(brinson.get("selection_effect") or 0))
    unstable = select > 100 or alloc > 100
    ir = brinson.get("information_ratio")
    try:
        ir_val = float(ir) if ir is not None else None
    except (TypeError, ValueError):
        ir_val = None
    if ir_val is not None and abs(ir_val) > 5:
        unstable = True
    out = {
        **brinson,
        "method_note": brinson.get(
            "method_note",
            "Pseudo-Brinson · sector heuristic · not audited",
        ),
        "evidence_quality": "HEURISTIC",
        "display_status": "suppressed" if unstable else "provisional",
        "display_label": (
            "UNSTABLE — selection/alloc heuristic unreliable; do not trade on this"
            if unstable
            else "ESTIMATED — pseudo-Brinson from sector map"
        ),
    }
    if unstable:
        out["allocation_effect"] = None
        out["selection_effect"] = None
        out["information_ratio"] = None
        out["active_return"] = brinson.get("active_return")
    return out


def build_rebalance_panel(allocation_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ranked trim/add list for PM rebalance panel."""
    trims = [
        r
        for r in allocation_rows
        if str(r.get("action_required") or "").startswith("TRIM")
    ]
    adds = [
        r
        for r in allocation_rows
        if r.get("action_required") == "ADD"
    ]
    urgency_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    trims.sort(
        key=lambda x: (
            urgency_rank.get(x.get("priority") or "low", 9),
            -abs(float(x.get("excess_pct") or x.get("drift_pct") or 0)),
        )
    )
    adds.sort(
        key=lambda x: (
            urgency_rank.get(x.get("priority") or "low", 9),
            -abs(float(x.get("drift_pct") or 0)),
        )
    )
    return {
        "top_trims": [
            {
                "ticker": r["asset"],
                "urgency": r.get("urgency"),
                "drift_pct": r.get("drift_pct"),
                "effect": f"Reduces single-name drift {abs(r.get('drift_pct') or 0):.1f}%",
                "action_size_pct": r.get("action_size_pct"),
                "reason": r.get("reason"),
            }
            for r in trims[:3]
        ],
        "top_adds": [
            {
                "ticker": r["asset"],
                "urgency": r.get("urgency"),
                "drift_pct": r.get("drift_pct"),
                "effect": f"Rebalances underweight by {abs(r.get('drift_pct') or 0):.1f}%",
                "action_size_pct": r.get("action_size_pct"),
                "reason": r.get("reason"),
            }
            for r in adds[:3]
        ],
        "evidence": "ESTIMATED — equal-weight drift vs current marks",
    }


def build_sleeve_strip(sleeves: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Top strip: strongest / safest / not investable sleeves."""
    active = [s for s in sleeves if s.get("deployable_now")]
    paused = [s for s in sleeves if not s.get("deployable_now")]
    strongest = max(
        sleeves,
        key=lambda s: float(s.get("excess_pct") or -999),
        default=None,
    )
    safest = min(
        active or sleeves,
        key=lambda s: abs(float(s.get("max_drawdown_pct") or 999)),
        default=None,
    )
    not_investable = paused[0] if paused else None
    return {
        "strongest": strongest,
        "safest": safest,
        "not_investable": not_investable,
    }


def build_critical_risk_event(
    *,
    positions: List[Dict[str, Any]],
    heat: Dict[str, Any],
    ibkr_linkage: Dict[str, Any],
    allocation_rows: List[Dict[str, Any]],
    top_concentration_pct: float = 0.0,
) -> Dict[str, Any]:
    """Dynamic CRITICAL RISK EVENT strip for portfolio tab."""
    n = len(positions)
    breached = heat.get("stop_breached_tickers") or []
    local_only = ibkr_linkage.get("sync_quality") == "local_only"
    broker_truth = bool(ibkr_linkage.get("broker_truth"))
    broker_offline = not bool(ibkr_linkage.get("broker_connected"))
    top_ticker = allocation_rows[0]["asset"] if allocation_rows else None
    if not top_ticker and positions:
        top_ticker = positions[0].get("ticker")

    issue_parts: List[str] = []
    if n == 1 and top_ticker and local_only:
        issue_parts.append(f"concentrated in a single local-only {top_ticker} position")
    elif top_concentration_pct >= 99 and n == 1 and top_ticker:
        issue_parts.append(f"concentrated in a single {top_ticker} position")
    elif top_concentration_pct > _MAX_SINGLE_PCT * 100 and top_ticker:
        issue_parts.append(
            f"{top_ticker} at {top_concentration_pct:.0f}% exceeds the {_MAX_SINGLE_PCT * 100:.0f}% cap"
        )
    if breached:
        if len(breached) == 1:
            issue_parts.append(f"the stop has already been breached on {breached[0]}")
        else:
            issue_parts.append(
                "stops have already been breached on " + ", ".join(breached)
            )
    if broker_offline:
        issue_parts.append("broker is offline — execution truth not confirmed")
    elif local_only or not broker_truth:
        issue_parts.append("broker truth is not synced")

    has_critical = bool(
        breached
        or local_only
        or broker_offline
        or (top_concentration_pct >= 99 and n == 1)
        or any(r.get("priority") == "critical" for r in allocation_rows)
    )
    if not has_critical:
        return {"active": False, "collapse_sleeves": False}

    if issue_parts:
        if len(issue_parts) == 1:
            detail = issue_parts[0]
        else:
            detail = ", ".join(issue_parts[:-1]) + ", and " + issue_parts[-1]
        body = (
            f"This book is currently {detail}. Treat the primary task as risk "
            "containment first — confirm broker state, reduce breached or concentrated "
            "exposure, then restore policy limits."
        )
    else:
        body = (
            "Portfolio protection takes priority over allocation research. "
            "Treat the primary task as risk containment first."
        )

    collapse_sleeves = (
        bool(breached)
        or top_concentration_pct >= 50
        or local_only
        or broker_offline
    )
    return {
        "active": True,
        "headline": (
            "CRITICAL RISK EVENT — portfolio protection takes priority over "
            "allocation research."
        ),
        "message": body,
        "issues": issue_parts,
        "collapse_sleeves": collapse_sleeves,
        "sleeve_collapse_note": _SLEEVE_COLLAPSE_COPY if collapse_sleeves else None,
    }


def build_risk_state(
    *,
    positions: List[Dict[str, Any]],
    heat: Dict[str, Any],
    ibkr_linkage: Dict[str, Any],
    risk_cockpit: Dict[str, Any],
    top_concentration_pct: float = 0.0,
) -> Dict[str, Any]:
    """Compact risk-state panel for portfolio tab."""
    top_ticker = risk_cockpit.get("top_ticker")
    sector_exposure = risk_cockpit.get("sector_exposure_pct") or {}
    top_sector = None
    top_sector_pct = 0.0
    if sector_exposure:
        top_sector = max(sector_exposure, key=sector_exposure.get)
        top_sector_pct = float(sector_exposure.get(top_sector) or 0)
    return {
        "stop_breached": bool(heat.get("stop_breached_count")),
        "stop_breached_tickers": heat.get("stop_breached_tickers") or [],
        "post_breach_open_r": heat.get("post_breach_open_r"),
        "single_name_pct": round(top_concentration_pct, 1),
        "single_name_ticker": top_ticker,
        "sector_pct": top_sector_pct,
        "sector_name": top_sector,
        "local_only": ibkr_linkage.get("sync_quality") == "local_only",
        "broker_truth": bool(ibkr_linkage.get("broker_truth")),
        "local_only_message": ibkr_linkage.get("local_only_banner") or _LOCAL_ONLY_COPY,
        "heat_warning": heat.get("heat_warning"),
        "heat_model": heat.get("heat_model"),
        "post_breach_note": heat.get("post_breach_note"),
        "position_count": len(positions),
    }


def build_do_now(
    action_needed: List[Dict[str, Any]],
    heat: Dict[str, Any],
    ibkr_linkage: Dict[str, Any],
    allocation_rows: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Ordered immediate actions — critical tier first."""
    items: List[Dict[str, str]] = []
    seen: set = set()

    def _add(action: str, detail: str, tier: str = "critical") -> None:
        key = action + detail
        if key in seen:
            return
        seen.add(key)
        items.append({"action": action, "detail": detail, "tier": tier})

    if not ibkr_linkage.get("broker_truth"):
        _add(
            "Confirm broker",
            "Reconcile local book against actual broker holdings before acting",
        )

    for bp in heat.get("stop_breached_positions") or []:
        ticker = bp.get("ticker") or "—"
        open_r = bp.get("open_r")
        r_note = f" ({open_r:+.2f}R)" if open_r is not None else ""
        _add(
            "Reduce breached position",
            f"Exit or resize {ticker}{r_note} — stop already breached",
        )

    for row in allocation_rows:
        if row.get("priority") == "critical" and str(row.get("action_required") or "").startswith("TRIM"):
            _add(
                "Restore concentration",
                f"{row['asset']}: trim toward {row.get('policy_max_pct', 12):.0f}% policy max "
                f"(excess +{row.get('excess_pct', 0):.0f}%)",
            )

    for a in action_needed:
        if a.get("tier") != "critical":
            continue
        cat = a.get("category") or ""
        if cat in ("stop_breach", "broker_sync", "concentration", "policy_breach"):
            continue
        _add(cat.replace("_", " ").title(), a.get("message") or "")

    for a in action_needed:
        if a.get("tier") == "secondary" and len(items) < 6:
            _add(
                (a.get("category") or "review").replace("_", " ").title(),
                a.get("message") or "",
                tier="secondary",
            )

    return items[:6]


def build_operating_discipline(
    *,
    positions: List[Dict[str, Any]],
    allocation_rows: List[Dict[str, Any]],
    heat: Dict[str, Any],
    risk_cockpit: Dict[str, Any],
    allocator_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Single discipline strip for portfolio tab."""
    without_stop = int(heat.get("without_stop") or 0)
    rebalance_due = bool(allocator_summary.get("rebalance_suggested"))
    sector_breaches = risk_cockpit.get("sector_breaches") or []
    return {
        "single_name_cap_pct": round(_MAX_SINGLE_PCT * 100, 0),
        "sector_cap_pct": round(_SECTOR_CAP_PCT * 100, 0),
        "heat_target_pct": _HEAT_TARGET_PCT,
        "missing_stop_count": without_stop,
        "stop_coverage_pct": heat.get("stop_coverage_pct", 0),
        "rebalance_due": rebalance_due,
        "rebalance_note": (
            "Drift or cap breach — review allocation monitor"
            if rebalance_due
            else "Within drift band"
        ),
        "sleeve_override": allocator_summary.get("capital_stance") or "—",
        "at_position_cap": bool(risk_cockpit.get("at_position_cap")),
        "sector_breach_count": len(sector_breaches),
        "heat_status": (
            "stop_breached"
            if heat.get("stop_breached_count")
            else "unavailable"
            if without_stop and not heat.get("heat_available")
            else "partial"
            if without_stop
            else "measured"
        ),
    }


def build_portfolio_action_now(
    *,
    decision_bar: Dict[str, Any],
    allocator_summary: Dict[str, Any],
    portfolio_verdict: Dict[str, Any],
    regime_fit: Dict[str, Any],
    heat: Dict[str, Any],
    ibkr_linkage: Dict[str, Any],
    action_needed: List[Dict[str, Any]],
    rebalance_panel: Dict[str, Any],
    risk_cockpit: Dict[str, Any],
    allocation_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Single consolidated action card payload."""
    top_blocker = None
    for a in action_needed:
        if a.get("severity") == "critical":
            top_blocker = a.get("message")
            break
    if not top_blocker and action_needed:
        top_blocker = action_needed[0].get("message")
    if not top_blocker and heat.get("without_stop"):
        top_blocker = heat.get("heat_quality_label")

    over_concentrated = bool(
        (risk_cockpit.get("concentration_offenders") or [])
        or (risk_cockpit.get("top_weight_pct") or 0) > 12
    )

    heat_label = "UNAVAILABLE"
    if heat.get("heat_model") == "disabled_stop_breach" or heat.get("stop_breached_count"):
        open_r = heat.get("post_breach_open_r")
        r_suffix = f" · {open_r:+.2f}R open" if open_r else ""
        heat_label = f"POST-BREACH{r_suffix}"
    elif heat.get("heat_available"):
        heat_label = f"{heat.get('heat_pct', 0):.2f}% · {heat.get('heat_r', 0):.2f}R"
    elif heat.get("heat_quality") == "partial":
        heat_label = "PARTIAL"
    elif heat.get("without_stop"):
        heat_label = "UNAVAILABLE"

    metrics_real = []
    metrics_incomplete = []
    if heat.get("heat_available"):
        metrics_real.append("portfolio heat")
    elif heat.get("stop_breached_count"):
        metrics_incomplete.append("portfolio heat (stop breached — planned risk N/A)")
    else:
        metrics_incomplete.append("portfolio heat (stop anchors missing)")
    if ibkr_linkage.get("broker_truth") or ibkr_linkage.get("source_pill", "").startswith("IBKR"):
        metrics_real.append("broker positions")
    else:
        metrics_incomplete.append("broker sync")

    trims = rebalance_panel.get("top_trims") or []
    adds = rebalance_panel.get("top_adds") or []
    hedges = risk_cockpit.get("risk_reduction_actions") or []
    hold_rows = [
        row
        for row in (allocation_rows or [])
        if row.get("action_required") == "HOLD"
    ]
    hold_rows.sort(key=lambda x: -float(x.get("current_weight_pct") or 0))
    holds = [
        {
            "ticker": r.get("asset"),
            "reason": r.get("reason") or "Within drift band",
        }
        for r in hold_rows[:4]
    ]
    blockers: List[str] = []
    if top_blocker:
        blockers.append(str(top_blocker))
    if heat.get("without_stop"):
        blockers.append(
            str(
                heat.get(
                    "heat_quality_label",
                    "Add stops to enable portfolio heat measurement",
                )
            )
        )
    for a in action_needed:
        msg = a.get("message")
        if msg and msg not in blockers:
            blockers.append(str(msg))

    critical_actions = [a for a in action_needed if a.get("tier") == "critical"]
    secondary_actions = [a for a in action_needed if a.get("tier") == "secondary"]

    action_priority = {
        "critical": critical_actions[:4],
        "secondary": secondary_actions[:4],
        "trim_first": trims[:1],
        "add_first": adds[:1],
        "hedge_reduce_first": hedges[:1],
        "no_action": holds[:4],
        "blockers": blockers[:3],
    }

    return {
        "decision": portfolio_verdict.get("verdict") or decision_bar.get("verdict"),
        "confidence": decision_bar.get("conviction"),
        "evidence_label": (
            (decision_bar.get("evidence_quality") or {}).get("label")
            or allocator_summary.get("evidence_quality")
        ),
        "why": portfolio_verdict.get("why") or [],
        "best_action": portfolio_verdict.get("best_action_now")
        or decision_bar.get("next_action"),
        "do_now": critical_actions[:3] or secondary_actions[:2],
        "top_trims": rebalance_panel.get("top_trims") or [],
        "top_adds": rebalance_panel.get("top_adds") or [],
        "biggest_risk_blocker": top_blocker,
        "regime_fit_score": regime_fit.get("regime_fit_score"),
        "regime_fit_note": regime_fit.get("note"),
        "over_concentrated": over_concentrated,
        "ibkr_sync": ibkr_linkage,
        "heat_label": heat_label,
        "heat_detail": heat.get("heat_quality_label"),
        "heat_warning": heat.get("heat_warning"),
        "post_breach_note": heat.get("post_breach_note"),
        "post_breach_open_r": heat.get("post_breach_open_r"),
        "stop_anchors": f"{heat.get('with_stop', 0)}/{heat.get('with_stop', 0) + heat.get('without_stop', 0)} valid",
        "metrics_real": metrics_real,
        "metrics_incomplete": metrics_incomplete,
        "urgency": portfolio_verdict.get("urgency"),
        "action_priority": action_priority,
        "critical_actions": critical_actions[:4],
        "secondary_actions": secondary_actions[:4],
    }


def build_curve_diagnostics_placeholder() -> Dict[str, Any]:
    """Placeholder until book-level equity series is wired."""
    return {
        "equity_curve": [],
        "underwater_curve": [],
        "rolling_sharpe_note": "Use Closed-Trade Ledger + Perf Lab for path quality",
        "rolling_alpha_note": "Wire portfolio equity vs SPY for rolling α",
        "evidence": "book_pnl_proxy",
    }


async def build_portfolio_decision(request) -> Dict[str, Any]:
    """Full portfolio decision payload for UI + API."""
    from src.services.execution_readiness import build_execution_readiness
    from src.services.portfolio_risk_cockpit import build_portfolio_risk_cockpit

    holdings: List[Dict[str, Any]] = []
    source = "manual"
    try:
        from src.api.routers.portfolio import _user_portfolio

        holdings = list(_user_portfolio.get("holdings") or [])
        source = _user_portfolio.get("source") or "manual"
    except Exception:
        logger.debug("portfolio holdings import failed", exc_info=True)

    # Enrich with monitor endpoint logic (prices) if we have market_data
    positions = holdings
    alerts: List[Dict[str, Any]] = []
    if holdings and hasattr(request.app.state, "market_data"):
        try:
            from src.api.routers.portfolio import portfolio_monitor

            mon = await portfolio_monitor(request)
            positions = mon.get("positions") or holdings
            alerts = mon.get("alerts") or []
        except Exception:
            logger.debug("portfolio_monitor delegate failed", exc_info=True)

    total = _total_value(positions)
    summary = {
        "total_positions": len(positions),
        "total_value": round(total, 2),
        "total_pnl_pct": round(
            sum(float(p.get("pnl_pct") or 0) * (float(p.get("market_value") or 0) / total)
                if total
                else 0
                for p in positions
            ),
            2,
        )
        if total
        else 0,
        "source": source,
    }

    today = getattr(request.app.state, "today_v7_cache", None) or {}
    regime = today.get("market_regime") or {}

    allocation_rows = build_allocation_monitor(positions)
    attribution = build_return_attribution(positions)
    regime_fit = build_regime_fit(regime, positions)
    execution = build_execution_readiness(portfolio_source=source)

    fund_console: Dict[str, Any] = {}
    fund_cache = getattr(request.app.state, "fund_cards_cache", None)
    if isinstance(fund_cache, dict) and fund_cache.get("cards"):
        try:
            from src.services.fund_manager_console import build_fund_console_payload

            fund_console = build_fund_console_payload(
                cards=fund_cache.get("cards") or [],
                regime=str(fund_cache.get("regime") or ""),
                benchmark="SPY",
                execution_readiness=execution,
                market_regime_label=str(regime.get("tradeability") or ""),
                tradeability=str(regime.get("tradeability") or ""),
            )
        except Exception:
            logger.debug("portfolio_decision fund_console failed", exc_info=True)

    fund_allocator = fund_console.get("allocator_decision") or {}
    allocator_summary = build_allocator_summary(
        positions=positions,
        summary=summary,
        regime=regime,
        allocation_rows=allocation_rows,
        execution=execution,
        fund_allocator=fund_allocator,
        source=source,
    )

    top_pct = 0.0
    if positions and total:
        top_pct = max(
            (float(p.get("market_value") or 0) / total) * 100 for p in positions
        )

    heat = compute_portfolio_heat(positions, equity=total or None)

    ibkr_linkage = build_ibkr_linkage(
        source=source,
        execution=execution,
        positions=positions,
        updated_at=summary.get("updated_at"),
    )

    action_needed = build_action_needed(
        alerts,
        allocation_rows,
        heat_pct=heat.get("heat_pct") or 0.0,
        top_concentration_pct=top_pct,
        heat=heat,
        ibkr_linkage=ibkr_linkage,
    )

    risk_cockpit = build_portfolio_risk_cockpit(
        positions,
        heat=heat,
    )

    curve_diagnostics = build_curve_diagnostics_placeholder()
    observation_count = 0
    try:
        from src.services.portfolio_equity import build_portfolio_equity_series

        eq = await build_portfolio_equity_series(request, positions, period="6mo")
        observation_count = len(eq.get("dates") or [])
        if eq.get("has_series"):
            curve_diagnostics = {
                "equity_curve": eq.get("equity_curve"),
                "benchmark_curve": eq.get("benchmark_curve"),
                "underwater_curve": eq.get("underwater_curve"),
                "dates": eq.get("dates"),
                "total_return_pct": eq.get("total_return_pct"),
                "benchmark_return_pct": eq.get("benchmark_return_pct"),
                "active_return_pct": eq.get("active_return_pct"),
                "rolling": eq.get("rolling"),
                "brinson": eq.get("brinson"),
                "rolling_sharpe_note": f"20d Sharpe {eq.get('rolling', {}).get('sharpe_20d', '—')}",
                "rolling_alpha_note": f"20d α {eq.get('rolling', {}).get('alpha_20d_ann_pct', '—')}% ann",
                "evidence": eq.get("evidence"),
                "observation_count": observation_count,
            }
    except Exception:
        logger.debug("portfolio equity series failed", exc_info=True)

    benchmark_intel = build_benchmark_intel(
        positions,
        summary,
        broker_synced=bool(ibkr_linkage.get("broker_truth")),
        observation_count=observation_count,
    )
    if not benchmark_intel.get("stats_reliable"):
        curve_diagnostics["stats_disclaimer"] = benchmark_intel.get("stats_disclaimer")
        curve_diagnostics["stats_reliable"] = False

    from src.services.decision_bar import bar_from_portfolio
    from src.services.monitors_store import evaluate_monitors
    from src.services.rebalance_sim import simulate_rebalance

    rebalance_urgency = allocator_summary.get("rebalance_suggested", False)
    decision_bar = bar_from_portfolio(
        allocator_summary,
        regime_fit,
        rebalance_urgency=rebalance_urgency,
    )
    rebalance_sim = simulate_rebalance(positions)
    monitor_alerts = evaluate_monitors(today=today, positions=positions)

    brinson = curve_diagnostics.get("brinson") if isinstance(curve_diagnostics, dict) else None
    if isinstance(brinson, dict):
        brinson = _sanitize_brinson(
            {
                **brinson,
                "period": curve_diagnostics.get("period") or "6mo",
            }
        )

    rebalance_panel = build_rebalance_panel(allocation_rows)
    sleeve_monitor = build_sleeve_monitor(fund_console)
    sleeve_strip = build_sleeve_strip(sleeve_monitor)
    portfolio_verdict = {
        "verdict": decision_bar.get("verdict") or allocator_summary.get("stance"),
        "best_action_now": allocator_summary.get("recommended_action"),
        "why": [
            x
            for x in [
                regime_fit.get("note"),
                heat.get("heat_quality_label"),
                f"Largest position {top_pct:.1f}%" if top_pct > _MAX_SINGLE_PCT * 100 else None,
            ]
            if x
        ],
        "urgency": (
            "now"
            if heat.get("stop_breached_count")
            or (heat.get("heat_pct") or 0) > 6
            or any(a.get("severity") == "critical" for a in action_needed)
            else "today"
            if allocator_summary.get("rebalance_suggested")
            else "monitor"
        ),
    }
    critical_risk_event = build_critical_risk_event(
        positions=positions,
        heat=heat,
        ibkr_linkage=ibkr_linkage,
        allocation_rows=allocation_rows,
        top_concentration_pct=top_pct,
    )
    do_now = build_do_now(action_needed, heat, ibkr_linkage, allocation_rows)
    risk_state = build_risk_state(
        positions=positions,
        heat=heat,
        ibkr_linkage=ibkr_linkage,
        risk_cockpit=risk_cockpit,
        top_concentration_pct=top_pct,
    )
    portfolio_action_now = build_portfolio_action_now(
        decision_bar=decision_bar,
        allocator_summary=allocator_summary,
        portfolio_verdict=portfolio_verdict,
        regime_fit=regime_fit,
        heat=heat,
        ibkr_linkage=ibkr_linkage,
        action_needed=action_needed,
        rebalance_panel=rebalance_panel,
        risk_cockpit=risk_cockpit,
        allocation_rows=allocation_rows,
    )
    operating_discipline = build_operating_discipline(
        positions=positions,
        allocation_rows=allocation_rows,
        heat=heat,
        risk_cockpit=risk_cockpit,
        allocator_summary=allocator_summary,
    )

    from src.services.core_satellite import build_core_satellite_summary

    core_satellite = build_core_satellite_summary(
        positions,
        equity=total or None,
        local_only=not bool(ibkr_linkage.get("broker_truth")),
        broker_synced=bool(ibkr_linkage.get("broker_truth")),
    )

    from src.services.crisis_regime import build_crisis_bundle

    crisis_survival = build_crisis_bundle(
        market_regime={
            **regime,
            "heat_pct": heat.get("heat_pct"),
        },
        execution_readiness=execution,
        positions=positions,
    ).get("crisis_survival") or {}
    crisis_survival = {
        **crisis_survival,
        "section_copy": crisis_survival.get("headline")
        or "Survival first — liquidity and heat before new risk",
    }

    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "critical_risk_event": critical_risk_event,
        "do_now": do_now,
        "risk_state": risk_state,
        "allocation_monitor_note": _ALLOC_MONITOR_COPY if any(
            float(r.get("excess_pct") or 0) > 0 for r in allocation_rows
        ) else None,
        "sleeve_research_collapsed": critical_risk_event.get("collapse_sleeves"),
        "sleeve_collapse_note": critical_risk_event.get("sleeve_collapse_note"),
        "portfolio_action_now": portfolio_action_now,
        "operating_discipline": operating_discipline,
        "core_satellite": core_satellite,
        "crisis_survival": crisis_survival,
        "decision_bar": decision_bar,
        "rebalance_sim": rebalance_sim,
        "rebalance_panel": rebalance_panel,
        "monitor_alerts": monitor_alerts,
        "risk_cockpit": risk_cockpit,
        "portfolio_heat": heat,
        "ibkr_linkage": ibkr_linkage,
        "allocator_summary": allocator_summary,
        "execution": execution,
        "allocation_monitor": allocation_rows,
        "return_attribution": attribution,
        "regime_fit": regime_fit,
        "benchmark_intel": benchmark_intel,
        "sleeve_monitor": sleeve_monitor,
        "sleeve_strip": sleeve_strip,
        "fund_allocator": fund_allocator,
        "action_needed": action_needed,
        "curve_diagnostics": curve_diagnostics,
        "brinson_attribution": brinson,
        "why_now": build_why_now(allocator_summary, regime_fit),
        "portfolio_verdict": portfolio_verdict,
        "evidence": {
            "basis": allocator_summary.get("evidence_quality"),
            "positions_source": source,
            "funds_basis": "model_backtest",
            "gross_net": "gross_book_pnl",
        },
        "summary": summary,
        "positions_count": len(positions),
    }
