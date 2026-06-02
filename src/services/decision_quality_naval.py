"""
《纳瓦尔宝典》decision quality — clarity of reasoning, known unknowns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.calm_reactive_mode import evaluate_calm_reactive
from src.services.compounding_priority import evaluate_compounding_priority
from src.services.leverage_engine import label_leverage
from src.services.opportunity_quality_naval import evaluate_opportunity_quality
from src.services.signal_to_noise import classify_signal_to_noise, what_matters_today
from src.services.specific_knowledge import evaluate_competence_fit


def evaluate_decision_quality(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Clarity score from explainability + confidence spread."""
    thesis = float(row.get("thesis_conf") or 0)
    timing = float(row.get("timing_conf") or 0)
    data = float(row.get("data_conf") or 0)
    why_not = str(row.get("why_not") or row.get("why_not_stronger") or "")
    invalidation = str(row.get("invalidation") or "")

    known_unknowns: List[str] = []
    if timing < 0.5 and thesis >= 0.6:
        known_unknowns.append("timing uncertain despite solid thesis")
    if data < 0.5:
        known_unknowns.append("data freshness or completeness gap")
    if not invalidation:
        known_unknowns.append("invalidation not explicit — add before sizing")
    if why_not:
        known_unknowns.append(f"open objection: {why_not[:80]}")

    spread = max(thesis, timing, data) - min(thesis, timing, data)
    clarity = "high" if spread < 0.25 and thesis >= 0.55 else "medium" if thesis >= 0.45 else "low"

    return {
        "clarity": clarity,
        "clarity_label": (
            "reasoning clear — objections named"
            if clarity == "high"
            else "reasoning partial — list unknowns before acting"
            if clarity == "medium"
            else "reasoning thin — research only"
        ),
        "known_unknowns": known_unknowns[:4],
    }


def build_naval_thinking(
    *,
    ticker: str,
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """30-second Naval block for stock_intel dossier."""
    row = {
        "ticker": ticker,
        "score": unified.get("score") or dossier.get("score"),
        "thesis_conf": (unified.get("confidence") or {}).get("thesis")
        or dossier.get("thesis_conf"),
        "timing_conf": (unified.get("confidence") or {}).get("timing"),
        "data_conf": (unified.get("confidence") or {}).get("data"),
        "action": unified.get("action") or unified.get("verdict"),
        "risk_reward": dossier.get("risk_reward") or unified.get("risk_reward"),
        "why_now": unified.get("why_now") or dossier.get("why_now"),
        "why_not": unified.get("why_not") or dossier.get("why_not"),
        "invalidation": dossier.get("invalidation"),
        "structure": dossier.get("structure") or {},
        "execution_ready": unified.get("execution_ready"),
    }
    tb = str((regime or {}).get("tradeability") or "")
    sn = classify_signal_to_noise(row, tradeability=tb)
    comp = evaluate_competence_fit(row)
    qual = evaluate_opportunity_quality(row)
    dq = evaluate_decision_quality(row, tradeability=tb)
    lev = label_leverage(row, surface="dossier")
    compound = evaluate_compounding_priority(row)

    summary = (
        f"{sn['label']}. "
        f"{comp['competence_label']}. "
        f"{'Worth bandwidth' if qual['mental_bandwidth_worthy'] else 'Defer bandwidth'}."
    )

    return {
        "mode": "naval_almanac",
        "summary_30s": summary,
        "signal_to_noise": sn["level"],
        "signal_label": sn["label"],
        "competence_fit": comp["competence_fit"],
        "competence_label": comp["competence_label"],
        "borrowed_conviction_risk": comp["borrowed_conviction_risk"],
        "mental_bandwidth_worthy": qual["mental_bandwidth_worthy"],
        "durability": qual["durability_label"],
        "asymmetry": qual["asymmetry_label"],
        "decision_clarity": dq["clarity"],
        "known_unknowns": dq["known_unknowns"],
        "leverage_type": lev["primary"],
        "leverage_label": lev["label"],
        "compounding_vs_noise": compound["headline"],
        "preserve_focus": sn["preserve_focus"],
        "authority": "research_only" if sn["level"] in ("ignore", "noise") else "supportive",
    }


def naval_clarity_strip_for_today(
    market_regime: Dict[str, Any],
    decision_model: Dict[str, Any],
    *,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Dashboard naval_clarity strip on /api/v7/today."""
    tb = str(
        decision_model.get("honest_tradeability")
        or market_regime.get("tradeability")
        or "WAIT"
    )
    calm = evaluate_calm_reactive(
        tradeability=tb,
        deployable_count=deployable_count,
        opportunities=opportunities,
    )
    matters = what_matters_today(
        opportunities,
        tradeability=tb,
        deployable_count=deployable_count,
    )
    compound = evaluate_compounding_priority(
        {"action": "WAIT" if deployable_count == 0 else "TRADE"},
        context={"deployable_count": deployable_count, "tradeability": tb},
    )

    action_necessity = "none"
    if deployable_count > 0 and tb in ("TRADE", "SELECTIVE", "STRONG_TRADE"):
        action_necessity = "selective"
    elif calm.get("false_urgency"):
        action_necessity = "none — false urgency suppressed"

    headline = calm.get("headline") or "Preserve focus — most scanner output is noise today"
    if matters:
        tickers = ", ".join(m["ticker"] for m in matters[:2])
        headline = f"What matters: {tickers} — everything else can wait"

    return {
        "mode": "naval_almanac",
        "headline": headline,
        "banner": calm.get("banner") or "No action required unless gates and clarity align",
        "what_matters": matters,
        "action_necessity": action_necessity,
        "preserve_focus": calm.get("preserve_focus", True),
        "false_urgency": calm.get("false_urgency", False),
        "peace_cost": calm.get("peace_cost", "low"),
        "compounding_note": compound.get("headline"),
        "signal_light": calm.get("signal_light", "monitor_lightly"),
    }
