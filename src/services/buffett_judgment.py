"""
《巴菲特传》Buffett biography mode — business judgment and capital allocation.

Owner mindset: understand the business, stay inside competence, allocate capital
patiently. Heuristic layer only — not a DCF engine. Orthogonal to 巴芒 value_investing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

BUFFETT_LABELS: Dict[str, str] = {
    "business_clear": "business understandable in plain language",
    "business_opaque": "business model opaque — study before sizing",
    "quality_strong": "economic quality signals supportive",
    "quality_weak": "returns/margin story weak — verify moat",
    "moat_likely": "durability proxy OK — thesis + structure",
    "moat_unclear": "moat unclear — do not pay for hope",
    "mgmt_unknown": "management/capital allocation — insufficient public data",
    "mgmt_ok": "capital discipline signals acceptable (proxy)",
    "inside_circle": "inside circle of competence",
    "outside_circle": "outside circle — study or pass",
    "ownable": "ownable — fits concentrated owner book",
    "study": "study pile — not yet ownable",
    "watch": "watch — patience over action",
    "inferior": "inferior use of capital vs cash or index",
    "noise_day": "market noise high — action not required",
    "patience": "patience is the position — wait for clarity",
    "hold_owner": "hold as owner — thesis intact",
    "trim_extended": "trim watch — price extended vs thesis",
    "exit_watch": "exit watch — thesis or quality breaking",
}

_PARTS_FRAMEWORK: List[Dict[str, str]] = [
    {"part": "1", "title": "Business understanding", "focus": "Explain the business in a paragraph"},
    {"part": "2", "title": "Economic quality", "focus": "Returns, margins, reinvestment"},
    {"part": "3", "title": "Moat", "focus": "Durability of advantage"},
    {"part": "4", "title": "Management", "focus": "Honesty and capital allocation"},
    {"part": "5", "title": "Circle of competence", "focus": "Stay inside what you can judge"},
    {"part": "6", "title": "Valuation & margin", "focus": "Price vs owner value band (proxy)"},
    {"part": "7", "title": "Portfolio worthiness", "focus": "Ownable vs watch vs pass"},
    {"part": "8", "title": "Temperament", "focus": "Filter noise; act only when necessary"},
]

_KNOWN_SECTOR_KEYS = (
    "technology",
    "financial",
    "health",
    "consumer",
    "industrial",
    "energy",
    "utility",
    "material",
    "communication",
    "software",
    "semiconductor",
    "bank",
    "insurance",
    "retail",
)


def _f(row: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) if row.get(key) is not None else default)
    except (TypeError, ValueError):
        return default


def _fundamentals_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    fb = row.get("fundamentals_block") or row.get("fundamentals") or {}
    raw = fb.get("raw") if isinstance(fb, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    flags = list(fb.get("flags") or []) if isinstance(fb, dict) else []
    return {
        "flags": flags,
        "pe": row.get("pe") or row.get("valuation_pe") or raw.get("pe_ratio") or raw.get("trailingPE"),
        "margin": (fb.get("margin_trend") if isinstance(fb, dict) else None) or raw.get("profit_margin"),
        "growth": (fb.get("revenue_growth") if isinstance(fb, dict) else None) or raw.get("revenue_growth"),
        "quality_score": (fb.get("quality_score") if isinstance(fb, dict) else None) or raw.get("quality_score"),
        "story_broken": bool(fb.get("story_broken")) if isinstance(fb, dict) else "story_broken_risk" in flags,
        "rich_valuation": "rich_valuation" in flags,
    }


def evaluate_business(row: Dict[str, Any]) -> Dict[str, Any]:
    """Business understanding + quality + moat heuristics."""
    thesis = _f(row, "thesis_conf") or _f(row, "thesis_quality")
    fund = _fundamentals_from_row(row)
    sector = str(row.get("sector") or row.get("industry") or row.get("sector_bucket") or "—")
    name = str(row.get("name") or row.get("company") or row.get("ticker") or "")
    extended = bool((row.get("structure") or {}).get("is_extended"))

    labels: List[str] = []
    understandable = thesis >= 0.5 and sector != "—"
    if understandable:
        labels.append(BUFFETT_LABELS["business_clear"])
    else:
        labels.append(BUFFETT_LABELS["business_opaque"])

    quality = "medium"
    if fund["story_broken"]:
        quality = "low"
        labels.append(BUFFETT_LABELS["quality_weak"])
    elif thesis >= 0.65 and not fund["rich_valuation"]:
        quality = "high"
        labels.append(BUFFETT_LABELS["quality_strong"])
    elif thesis < 0.45:
        quality = "low"
        labels.append(BUFFETT_LABELS["quality_weak"])

    moat = "unclear"
    if thesis >= 0.65 and not extended and quality != "low":
        moat = "likely"
        labels.append(BUFFETT_LABELS["moat_likely"])
    else:
        labels.append(BUFFETT_LABELS["moat_unclear"])

    summary = (
        f"{name or row.get('ticker', '')}: {sector} — "
        f"quality {quality}, moat {moat}. "
        + (labels[0] if labels else "")
    )[:240]

    return {
        "business_summary": summary,
        "business_quality": quality,
        "moat": moat,
        "labels": labels[:4],
        "understandable": understandable,
    }


def evaluate_management(row: Dict[str, Any]) -> Dict[str, Any]:
    """Management / capital allocation — stub from available proxies."""
    fund = _fundamentals_from_row(row)
    thesis = _f(row, "thesis_conf")
    growth = fund.get("growth")
    labels: List[str] = []

    try:
        from src.utils.numeric_parse import coerce_float

        g = coerce_float(growth, default=None) if growth is not None else None
    except Exception:
        g = None

    if thesis >= 0.6 and not fund["story_broken"] and (g is None or g >= 0):
        grade = "acceptable_proxy"
        labels.append(BUFFETT_LABELS["mgmt_ok"])
        note = "Reinvestment/growth proxies OK — not a management audit"
    else:
        grade = "unknown"
        labels.append(BUFFETT_LABELS["mgmt_unknown"])
        note = "Treat mgmt/capital allocation as unknown until filings reviewed"

    return {
        "management_grade": grade,
        "management_note": note,
        "labels": labels,
    }


def evaluate_buffett_competence(row: Dict[str, Any]) -> Dict[str, Any]:
    """Circle of competence — Buffett-only; does not call Naval specific_knowledge."""
    sector = str(row.get("sector") or row.get("sector_bucket") or "").lower()
    thesis = _f(row, "thesis_conf") or _f(row, "thesis_quality")
    cal_n = int(
        (row.get("evidence_quality") or {}).get("sample_count")
        or row.get("calibration_n")
        or 0
    )
    sector_familiar = bool(sector) and any(k in sector for k in _KNOWN_SECTOR_KEYS)

    if thesis >= 0.65 and sector_familiar and cal_n >= 15:
        fit = "inside"
        label = BUFFETT_LABELS["inside_circle"]
    elif thesis >= 0.5 and sector_familiar:
        fit = "partial"
        label = "partial circle — deepen research before concentration"
    else:
        fit = "outside"
        label = BUFFETT_LABELS["outside_circle"]

    return {
        "competence_fit": fit,
        "competence_label": label,
        "sector_familiar": sector_familiar,
    }


def evaluate_allocation(row: Dict[str, Any], *, tradeability: str = "") -> Dict[str, Any]:
    """Ownable / study / watch / inferior capital decision."""
    biz = evaluate_business(row)
    comp = evaluate_buffett_competence(row)
    thesis = _f(row, "thesis_conf")
    score = _f(row, "score") or _f(row, "validated_score")
    tb = (tradeability or "").upper()
    extended = bool((row.get("structure") or {}).get("is_extended"))

    if biz["business_quality"] == "low" or comp["competence_fit"] == "outside":
        action = "inferior"
        tag = BUFFETT_LABELS["inferior"]
    elif thesis >= 0.65 and score >= 7.0 and not extended and comp["competence_fit"] == "inside":
        action = "ownable"
        tag = BUFFETT_LABELS["ownable"]
    elif thesis >= 0.5 and comp["competence_fit"] != "outside":
        action = "study"
        tag = BUFFETT_LABELS["study"]
    else:
        action = "watch"
        tag = BUFFETT_LABELS["watch"]

    if tb in ("WAIT", "NO_TRADE") and action == "ownable":
        action = "study"
        tag = BUFFETT_LABELS["patience"]

    return {
        "allocation_action": action,
        "allocation_label": tag,
        "portfolio_worthiness": action,
    }


def evaluate_temperament(
    *,
    tradeability: str = "",
    deployable_count: int = 0,
    opportunities: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Noise filter and whether action is necessary today."""
    tb = (tradeability or "WAIT").upper()
    opps = opportunities or []
    high_scores = sum(1 for o in opps[:12] if _f(o, "score") >= 7.5)

    noise_high = tb in ("WAIT", "NO_TRADE") and high_scores >= 2
    action_necessary = (
        deployable_count > 0 and tb in ("TRADE", "SELECTIVE", "STRONG_TRADE")
    )

    labels: List[str] = []
    if noise_high:
        labels.append(BUFFETT_LABELS["noise_day"])
    if tb in ("WAIT", "NO_TRADE"):
        labels.append(BUFFETT_LABELS["patience"])

    return {
        "noise_high": noise_high,
        "action_necessary": action_necessary,
        "selectivity": "high" if noise_high or deployable_count == 0 else "normal",
        "patience_note": (
            "No action required — let the market serve you ideas, not urgency"
            if not action_necessary
            else "Selective action only when business and price align"
        ),
        "labels": labels,
    }


def evaluate_hold_sell(row: Dict[str, Any]) -> Dict[str, Any]:
    """Hold / trim / exit watch for owner positions."""
    thesis = _f(row, "thesis_conf")
    extended = bool((row.get("structure") or {}).get("is_extended"))
    fund = _fundamentals_from_row(row)
    has_position = bool(row.get("has_position") or row.get("in_portfolio"))
    action = str(row.get("action") or row.get("verdict") or "").upper()

    if fund["story_broken"] or thesis < 0.4:
        stance = "exit_watch"
        label = BUFFETT_LABELS["exit_watch"]
    elif extended and thesis < 0.7:
        stance = "trim_extended"
        label = BUFFETT_LABELS["trim_extended"]
    elif has_position or action in ("HOLD", "MONITOR", "WATCH"):
        stance = "hold_owner"
        label = BUFFETT_LABELS["hold_owner"]
    else:
        stance = "watch"
        label = BUFFETT_LABELS["watch"]

    return {"hold_stance": stance, "hold_label": label}


def evaluate_buffett_judgment(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
) -> Dict[str, Any]:
    """Full judgment bundle for dossier or tests."""
    biz = evaluate_business(row)
    mgmt = evaluate_management(row)
    comp = evaluate_buffett_competence(row)
    alloc = evaluate_allocation(row, tradeability=tradeability)
    hold = evaluate_hold_sell(row)
    return {
        "mode": "buffett_biography",
        "parts_framework": _PARTS_FRAMEWORK,
        "business": biz,
        "management": mgmt,
        "competence": comp,
        "allocation": alloc,
        "hold_sell": hold,
        "authority": "research_only",
        "model_note": "Heuristic from thesis, fundamentals flags, structure — not audited 10-K",
    }


def build_buffett_owner_view(
    *,
    ticker: str,
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
    fundamentals_block: Optional[Dict[str, Any]] = None,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Owner-view block for stock_intel dossier."""
    conf = unified.get("confidence") if isinstance(unified.get("confidence"), dict) else {}
    row: Dict[str, Any] = {
        "ticker": ticker,
        "name": dossier.get("name") or dossier.get("company"),
        "sector": dossier.get("sector") or dossier.get("sector_bucket"),
        "score": unified.get("score") or dossier.get("score"),
        "thesis_conf": conf.get("thesis") or dossier.get("thesis_conf"),
        "structure": dossier.get("structure") or {},
        "fundamentals_block": fundamentals_block or dossier.get("fundamentals_block"),
        "action": unified.get("action") or unified.get("verdict"),
        "has_position": dossier.get("has_position"),
    }
    tb = str((regime or {}).get("tradeability") or "")
    j = evaluate_buffett_judgment(row, tradeability=tb)
    biz = j["business"]
    comp = j["competence"]
    alloc = j["allocation"]
    mgmt = j["management"]
    hold = j["hold_sell"]

    headline = (
        f"{alloc['allocation_action'].upper()}: {biz['business_quality']} business, "
        f"moat {biz['moat']}, {comp['competence_fit']} competence."
    )

    return {
        "mode": "buffett_biography",
        "headline": headline,
        "business_summary": biz["business_summary"],
        "business_quality": biz["business_quality"],
        "moat": biz["moat"],
        "management_grade": mgmt["management_grade"],
        "management_note": mgmt["management_note"],
        "competence_fit": comp["competence_fit"],
        "competence_label": comp["competence_label"],
        "allocation_action": alloc["allocation_action"],
        "allocation_label": alloc["allocation_label"],
        "portfolio_worthiness": alloc["portfolio_worthiness"],
        "hold_stance": hold["hold_stance"],
        "hold_label": hold["hold_label"],
        "labels": (biz.get("labels") or [])[:3],
        "authority": j["authority"],
        "model_note": j["model_note"],
    }


def buffett_clarity_strip_for_today(
    market_regime: Dict[str, Any],
    decision_model: Dict[str, Any],
    *,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Dashboard buffett_clarity strip on /api/v7/today."""
    tb = str(
        decision_model.get("honest_tradeability")
        or market_regime.get("tradeability")
        or "WAIT"
    )
    temp = evaluate_temperament(
        tradeability=tb,
        deployable_count=deployable_count,
        opportunities=opportunities,
    )

    ownable: List[Dict[str, str]] = []
    for o in (opportunities or [])[:8]:
        row = dict(o)
        alloc = evaluate_allocation(row, tradeability=tb)
        if alloc["allocation_action"] == "ownable":
            ownable.append({"ticker": str(o.get("ticker") or "—"), "band": "ownable"})

    what_matters: List[Dict[str, str]] = ownable[:2]
    if not what_matters and (opportunities or []):
        best = max(
            (opportunities or [])[:6],
            key=lambda x: _f(x, "thesis_conf") or _f(x, "score"),
            default=None,
        )
        if best:
            what_matters = [
                {
                    "ticker": str(best.get("ticker") or "—"),
                    "band": evaluate_allocation(dict(best), tradeability=tb)["allocation_action"],
                }
            ]

    headline = temp["patience_note"]
    if what_matters:
        tickers = ", ".join(w["ticker"] for w in what_matters[:2])
        headline = f"What matters for owners: {tickers} — everything else can wait"

    return {
        "mode": "buffett_biography",
        "headline": headline,
        "banner": (
            "Patience and selectivity — understand the business before capital"
            if not temp["action_necessary"]
            else "Only deploy into businesses you would own for years"
        ),
        "patience": temp["selectivity"] == "high" or tb in ("WAIT", "NO_TRADE"),
        "selectivity": temp["selectivity"],
        "action_necessary": temp["action_necessary"],
        "what_matters": what_matters,
        "noise_high": temp["noise_high"],
    }


def tags_for_playbook_row(row: Dict[str, Any], *, tradeability: str = "") -> Dict[str, Any]:
    biz = evaluate_business(row)
    comp = evaluate_buffett_competence(row)
    alloc = evaluate_allocation(row, tradeability=tradeability)
    return {
        "business_quality": biz["business_quality"],
        "buffett_competence_fit": comp["competence_fit"],
        "portfolio_worthiness": alloc["portfolio_worthiness"],
        "buffett_allocation_action": alloc["allocation_action"],
        "buffett_labels": biz.get("labels", [])[:2],
    }
