"""Portfolio decision console — allocator-grade layer on top of holdings analytics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_SINGLE_PCT = 0.12
_DRIFT_REBALANCE_PCT = 0.05
_SECTOR_CAP_PCT = 0.35


def _total_value(positions: List[Dict[str, Any]]) -> float:
    return sum(float(p.get("market_value") or 0) for p in positions)


def build_allocation_monitor(
    positions: List[Dict[str, Any]],
    *,
    max_single_pct: float = _MAX_SINGLE_PCT,
) -> List[Dict[str, Any]]:
    """Current vs equal-weight target with drift and action."""
    n = len(positions)
    if n == 0:
        return []
    total = _total_value(positions) or 1.0
    target = 1.0 / n
    rows: List[Dict[str, Any]] = []
    for p in sorted(positions, key=lambda x: -(float(x.get("market_value") or 0))):
        mv = float(p.get("market_value") or 0)
        current = mv / total if total else 0.0
        drift = current - target
        drift_pct = round(drift * 100, 2)
        if current > max_single_pct:
            action = "TRIM"
            priority = "high"
            reason = f"Above {max_single_pct * 100:.0f}% single-name cap"
        elif drift > _DRIFT_REBALANCE_PCT:
            action = "TRIM"
            priority = "medium"
            reason = "Overweight vs equal-weight target"
        elif drift < -_DRIFT_REBALANCE_PCT:
            action = "ADD"
            priority = "medium"
            reason = "Underweight vs equal-weight target"
        else:
            action = "HOLD"
            priority = "low"
            reason = "Within drift band"
        rows.append(
            {
                "asset": p.get("ticker", "—"),
                "current_weight_pct": round(current * 100, 2),
                "target_weight_pct": round(target * 100, 2),
                "drift_pct": drift_pct,
                "action_required": action,
                "priority": priority,
                "reason": reason,
                "estimated_trade_hint": (
                    f"~{abs(drift_pct):.1f}% of portfolio"
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
) -> Dict[str, Any]:
    """Benchmark-relative snapshot (portfolio book level)."""
    total_pnl_pct = float((summary or {}).get("total_pnl_pct") or 0)
    # Without full equity curve, use book P&L as proxy
    verdict = (
        "OUTPERFORMING"
        if total_pnl_pct > 1
        else "LAGGING"
        if total_pnl_pct < -1
        else "INLINE"
    )
    return {
        "benchmark": benchmark,
        "portfolio_return_proxy_pct": total_pnl_pct,
        "verdict": verdict,
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
) -> List[Dict[str, Any]]:
    """Alerts / action-needed box for PM."""
    out: List[Dict[str, Any]] = []
    for a in alerts[:6]:
        out.append(
            {
                "severity": a.get("severity", "warning"),
                "category": a.get("type", "alert"),
                "message": a.get("msg", ""),
                "asset": a.get("ticker"),
            }
        )
    for row in allocation_rows:
        if row.get("priority") == "high" and row.get("action_required") != "HOLD":
            out.append(
                {
                    "severity": "warning",
                    "category": "rebalance_drift",
                    "message": f"{row['asset']}: {row['action_required']} — {row['reason']}",
                    "asset": row["asset"],
                }
            )
    if heat_pct > 6:
        out.append(
            {
                "severity": "critical",
                "category": "portfolio_heat",
                "message": f"Total heat {heat_pct:.1f}% > 6% — reduce risk",
                "asset": None,
            }
        )
    if top_concentration_pct > _MAX_SINGLE_PCT * 100:
        out.append(
            {
                "severity": "warning",
                "category": "concentration",
                "message": f"Largest position {top_concentration_pct:.1f}% — trim or hedge",
                "asset": None,
            }
        )
    return out[:10]


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
        (r for r in allocation_rows if r.get("action_required") == "TRIM"),
        None,
    )
    underweight = next(
        (r for r in allocation_rows if r.get("action_required") == "ADD"),
        None,
    )
    rebalance_suggested = any(
        r.get("action_required") in ("TRIM", "ADD") and r.get("priority") != "low"
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

    deploy = fund_allocator.get("deploy_capital") or fund_allocator.get("deploy_posture")
    rec_parts: List[str] = []
    if overweight:
        rec_parts.append(f"Trim {overweight['asset']}")
    if underweight:
        rec_parts.append(f"Add {underweight['asset']}")
    if deploy:
        rec_parts.append(f"Sleeve: {deploy}")
    if not rec_parts:
        rec_parts.append("Monitor — no urgent rebalance")

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
        "recommended_action": " · ".join(rec_parts),
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
        out.append(
            {
                "id": c.get("id"),
                "name": c.get("display_name"),
                "status": c.get("gate_status"),
                "stance": c.get("stance") or mb.get("manager_state"),
                "capital_deployed_pct": mb.get("capital_deployed_pct"),
                "regime_fit": c.get("regime_fit"),
                "return_pct": c.get("total_return_pct"),
                "excess_pct": c.get("excess_return_pct"),
                "max_drawdown_pct": c.get("max_drawdown_pct"),
                "next_trigger": mb.get("next_trigger"),
                "evidence": c.get("evidence_badge") or "model_backtest",
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
    benchmark_intel = build_benchmark_intel(positions, summary)
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

    action_needed = build_action_needed(
        alerts,
        allocation_rows,
        heat_pct=0.0,
        top_concentration_pct=top_pct,
    )

    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "allocator_summary": allocator_summary,
        "execution": execution,
        "allocation_monitor": allocation_rows,
        "return_attribution": attribution,
        "regime_fit": regime_fit,
        "benchmark_intel": benchmark_intel,
        "sleeve_monitor": build_sleeve_monitor(fund_console),
        "fund_allocator": fund_allocator,
        "action_needed": action_needed,
        "curve_diagnostics": build_curve_diagnostics_placeholder(),
        "why_now": build_why_now(allocator_summary, regime_fit),
        "evidence": {
            "basis": allocator_summary.get("evidence_quality"),
            "positions_source": source,
            "funds_basis": "model_backtest",
            "gross_net": "gross_book_pnl",
        },
        "summary": summary,
        "positions_count": len(positions),
    }
