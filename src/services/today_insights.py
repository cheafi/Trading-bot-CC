"""Today dashboard insights — near-miss, funnel diagnosis, monitor triggers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


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
        lines.append("Broad trend is supportive — uptrend is the backdrop, not a deploy signal.")
        lines.append(
            "No name passed full action rules (score ≥8, thesis+timing ≥65%, R:R ≥2.5, regime gate)."
        )
        if actionable > 0:
            lines.append(
                f"{actionable} setup(s) scored ≥7.0 but failed timing, execution, or R:R gates."
            )
        else:
            lines.append("Scanner found no names above actionable score threshold today.")
    elif not should_trade:
        lines.append("Regime gate is closed — capital preservation overrides individual setups.")
    elif trade_count > 0:
        lines.append(f"{trade_count} TRADE-ready name(s) — deploy selectively at 1R.")
    else:
        lines.append(f"Tradeability: {tradeability} — patience is the active decision.")
    if vix > 22:
        lines.append(f"VIX {vix:.0f} — elevated vol; size down or wait for compression.")
    if breadth < 40:
        lines.append(f"Breadth {breadth:.0f}% — narrow participation; leaders only.")
    return lines[:5]


def build_no_setup_diagnosis(
    council_results: List[Any],
    *,
    scanner_degraded: bool = False,
) -> Dict[str, Any]:
    """Why no deploy today — failure bucket counts."""
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
            rr = float(pr.signal.get("risk_reward") or pr.decision.risk_reward_ratio or 0)
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
    return {
        "breakdown": buckets,
        "total_evaluated": total,
        "headline": (
            "No deploy candidate passed action rules"
            if total
            else "Scanner still warming — diagnosis unavailable"
        ),
    }


def build_near_miss_candidates(
    council_results: List[Any],
    top5_tickers: Set[str],
    *,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Closest names to TRADE that did not make top deploy list."""
    rows: List[Dict[str, Any]] = []
    for cr in council_results or []:
        try:
            pr = cr.pipeline
            sig = pr.signal
            ticker = sig.get("ticker") or ""
            if not ticker or ticker in top5_tickers:
                continue
            action = (pr.decision.action or "WATCH").upper()
            if action in ("TRADE", "BUY", "NO_TRADE", "AVOID"):
                if action in ("NO_TRADE", "AVOID"):
                    continue
            score = float(pr.fit.final_score)
            if score < 6.0:
                continue
            timing = float(pr.confidence.timing)
            thesis = float(pr.confidence.thesis)
            rr = float(sig.get("risk_reward") or pr.decision.risk_reward_ratio or 0)
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
                    trigger = f"Hold above ${float(entry):.2f} with stop ${float(stop):.2f}"
                else:
                    trigger = "Await trigger confirmation"
            distance_parts: List[str] = []
            if timing < 0.5:
                distance_parts.append(
                    f"timing +{int(max(0, (0.5 - timing) * 100))}pts"
                )
            if thesis < 0.65:
                distance_parts.append(
                    f"thesis +{int(max(0, (0.65 - thesis) * 100))}pts"
                )
            if rr > 0 and rr < 2.5:
                distance_parts.append(f"R:R need {2.5 - rr:.1f}")
            distance_to_pass = " · ".join(distance_parts) if distance_parts else "At gate — review sizing"
            rows.append(
                {
                    "ticker": ticker,
                    "action": action,
                    "score": round(score, 1),
                    "final_conf": round(float(pr.confidence.final), 2),
                    "gaps": gaps,
                    "upgrade_trigger": trigger,
                    "distance_to_pass": distance_to_pass,
                    "invalidation_price": stop,
                    "entry_price": entry,
                    "stop_price": stop,
                    "target_price": target,
                    "risk_reward": round(rr, 1) if rr else None,
                    "why_not": (
                        getattr(expl, "why_not_stronger", None) or gaps if expl else gaps
                    ),
                }
            )
        except Exception:
            continue
    rows.sort(key=lambda x: (-x["score"], -x["final_conf"]))
    return rows[:limit]


def build_monitor_triggers(
    *,
    market_pulse: Dict[str, Any],
    near_miss: List[Dict[str, Any]],
    vix: float,
    breadth: float,
    tradeability: str,
) -> List[Dict[str, Any]]:
    """What to watch when there are zero deploy setups."""
    triggers: List[Dict[str, Any]] = []
    if near_miss:
        nm = near_miss[0]
        triggers.append(
            {
                "type": "near_miss",
                "label": f"Upgrade watch: {nm['ticker']}",
                "detail": nm.get("upgrade_trigger", ""),
                "horizon": "intraday",
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
    return triggers[:6]


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
            "badge": "fallback" if regime_synthetic else ("stale" if scanner_degraded else "live"),
            "label": (
                "Regime: synthetic fallback"
                if regime_synthetic
                else ("Regime: degraded scanner" if scanner_degraded else "Regime: live engine")
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


def build_sleeve_summary(cards: List[Dict[str, Any]], regime: str = "") -> Dict[str, Any]:
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
        cards, key=lambda c: (-(c.get("regime_fit") or 0), -(c.get("excess_return_pct") or 0))
    )
    strongest = sorted_cards[0] if sorted_cards else None
    controller = next((c for c in cards if c.get("controls_capital")), strongest)
    strongest_training = max(
        cards, key=lambda c: (c.get("excess_return_pct") or 0), default=None
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
        }

    return {
        "strongest_live": _card_strip(strongest),
        "strongest_training": _card_strip(strongest_training),
        "active_today": _card_strip(controller),
        "fund_manager": {
            "active_sleeve_id": (controller or {}).get("id"),
            "active_sleeve_name": (controller or {}).get("display_name"),
            "stance": (controller or {}).get("stance", "NEUTRAL"),
            "mode": (controller or {}).get("mode", "training"),
            "controls_capital": bool((controller or {}).get("controls_capital")),
            "regime_fit": (controller or {}).get("regime_fit"),
        },
        "active_count": len(active),
        "paused_count": len([c for c in cards if c.get("gate_status") == "PAUSED"]),
        "cards": [_card_strip(c) for c in sorted_cards[:3] if _card_strip(c)],
        "regime": regime,
        "stance": (
            f"Active: {(controller or {}).get('display_name')} · "
            f"{(controller or {}).get('stance', 'NEUTRAL')} · "
            f"{(controller or {}).get('gate_status', '—')}"
            if controller
            else "No sleeve data"
        ),
    }
