"""Multi-signal confluence score — weighted evidence stack."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_WEIGHTS = {
    "insider_cluster": 18,
    "options_conviction": 16,
    "institutional_accumulation": 14,
    "estimate_revision": 12,
    "technical_structure": 12,
    "peer_rs": 10,
    "regime_gate": 10,
    "fundamental_quality": 8,
    "public_disclosure": 4,
    "social_noise": 0,
}


def build_confluence(
    *,
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
    smart_money: Dict[str, Any],
    pm_answer: Dict[str, Any],
    regime: Optional[Dict[str, Any]] = None,
    portfolio_fit: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    signals: List[Dict[str, Any]] = []
    score = 0
    max_score = sum(v for v in _WEIGHTS.values() if v > 0)

    tech = dossier.get("technicals") or {}
    if tech.get("above_sma50") and tech.get("rsi"):
        w = _WEIGHTS["technical_structure"]
        score += w
        signals.append(
            {
                "signal": "technical_structure",
                "weight": w,
                "state": "positive",
                "detail": "Above SMA50 with RSI in play",
            }
        )

    if (unified.get("label") or "").upper() in ("TRADE", "BUY"):
        w = _WEIGHTS["technical_structure"] // 2
        score += w
        signals.append(
            {"signal": "unified_verdict", "weight": w, "state": "positive", "detail": unified.get("reason")}
        )

    ins = (smart_money.get("insider") or "").lower()
    if ins == "bullish":
        w = _WEIGHTS["insider_cluster"]
        score += w
        signals.append({"signal": "insider_cluster", "weight": w, "state": "positive", "detail": "Insider bullish"})

    opt = (smart_money.get("options_flow") or "")
    if opt in ("unusual_activity_watch",):
        w = _WEIGHTS["options_conviction"]
        score += w
        signals.append({"signal": "options_conviction", "weight": w, "state": "positive", "detail": opt})

    hf = (smart_money.get("hedge_fund_trend") or "")
    if "accumul" in hf:
        w = _WEIGHTS["institutional_accumulation"]
        score += w // 2
        signals.append(
            {"signal": "institutional_accumulation", "weight": w // 2, "state": "mixed", "detail": "13F lagged"}
        )

    if regime and regime.get("should_trade"):
        w = _WEIGHTS["regime_gate"]
        score += w
        signals.append({"signal": "regime_gate", "weight": w, "state": "positive", "detail": "Regime allows risk"})

    if portfolio_fit and portfolio_fit.get("score", 0) >= 60:
        w = 6
        score += w
        signals.append(
            {"signal": "portfolio_fit", "weight": w, "state": "positive", "detail": portfolio_fit.get("fit_label")}
        )

    action = (pm_answer.get("action_now") or "").upper()
    if action == "AVOID":
        score = max(0, score - 25)
        signals.append({"signal": "pm_avoid", "weight": -25, "state": "negative", "detail": "PM layer avoid"})

    normalized = round(min(100, score / max_score * 100)) if max_score else 0
    return {
        "score": normalized,
        "signal_count": len(signals),
        "signals": signals,
        "headline": (
            f"Confluence {normalized}/100 — {len([s for s in signals if s['state'] == 'positive'])} aligned"
        ),
        "evidence": {
            "basis": "rule_stack",
            "label": "Weighted hierarchy — not ML calibrated",
        },
    }
