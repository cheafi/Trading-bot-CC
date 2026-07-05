"""
Nison candlestick context engine — detection != judgment.

Steve Nison principles (Japanese Candlestick Charting Techniques):
- Context over pattern name
- Macro first, micro second
- Location / position matters
- Risk-first: no stop = no trade; weak R:R = no trade
- Adapt when thesis invalidates (market chameleon)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.services.macro_trend import assess_macro_trend
from src.utils.numeric_parse import coerce_float, parse_ratio

# Operator-facing labels (Nison humility vocabulary)
NISON_LABELS: Dict[str, str] = {
    "pattern_present_context_weak": "pattern present, context weak",
    "reversal_clue_not_trade": "reversal clue, not yet a trade",
    "location_strengthens": "location strengthens the signal",
    "strong_candle_poor_geometry": "strong candle, poor geometry",
    "bullish_pattern_bearish_backdrop": "bullish pattern inside bearish backdrop",
    "thesis_invalidated_adapt": "thesis invalidated — adapt to market",
    "detection_not_judgment": "detection ≠ judgment — verify context",
    "no_stop_no_trade": "no stop = no trade",
    "weak_rr_no_trade": "weak R:R = no trade",
    "strong_pattern_strong_context": "strong pattern, strong context",
    "pattern_present_not_actionable": "pattern present, not actionable",
    "context_check_pending": "context check pending — monitor only",
}

TRADE_RR_MIN = 2.0
PATTERN_QUALITY_MIN = 55
CONTEXT_QUALITY_MIN = 55


def _infer_pattern_heuristic(tech: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristic pattern stub from existing technicals — not a full OHLC detector.
    """
    rsi = coerce_float(tech.get("rsi"), 50.0)
    macd = str(tech.get("macd_signal") or "").upper()
    vol_ratio = coerce_float(tech.get("volume_ratio"), 1.0)
    above50 = bool(tech.get("above_sma50"))
    above20 = bool(tech.get("above_sma20"))
    support_dist = coerce_float(tech.get("support_dist_pct"), 99.0)

    name = "none"
    direction = "neutral"
    quality_hint = 40
    notes: List[str] = []

    if rsi <= 35 and support_dist <= 4:
        name = "hammer_like_reversal"
        direction = "bullish"
        quality_hint = 62
        notes.append("Oversold near support — hammer / doji reversal clue")
    elif rsi >= 72 and not above50:
        name = "shooting_star_like"
        direction = "bearish"
        quality_hint = 58
        notes.append("Overbought below 50 MA — rejection clue")
    elif macd == "BULLISH" and vol_ratio >= 1.5 and above20:
        name = "momentum_engulfing_like"
        direction = "bullish"
        quality_hint = 65
        notes.append("MACD bullish with volume surge — momentum candle sequence")
    elif macd == "BEARISH" and not above20:
        name = "bearish_engulfing_like"
        direction = "bearish"
        quality_hint = 60
        notes.append("MACD bearish with price below 20 MA")
    elif 45 <= rsi <= 55 and vol_ratio < 0.8:
        name = "doji_like_indecision"
        direction = "neutral"
        quality_hint = 45
        notes.append("Mid RSI, quiet volume — indecision / doji zone")
    elif above50 and above20 and vol_ratio >= 1.2:
        name = "trend_continuation"
        direction = "bullish"
        quality_hint = 55
        notes.append("Trend-aligned continuation — not a standalone reversal")

    return {
        "pattern_name": name,
        "direction": direction,
        "quality_hint": quality_hint,
        "detection_notes": notes,
        "is_heuristic": True,
    }


def score_pattern_quality(tech: Dict[str, Any], pattern: Dict[str, Any]) -> int:
    """Pattern Quality Score 0–100 from heuristic + volume/MACD confirmation."""
    base = int(pattern.get("quality_hint") or 40)
    vol = coerce_float(tech.get("volume_ratio"), 1.0)
    if vol >= 1.5:
        base += 8
    elif vol >= 1.2:
        base += 4
    macd = str(tech.get("macd_signal") or "").upper()
    direction = pattern.get("direction")
    if direction == "bullish" and macd == "BULLISH":
        base += 6
    elif direction == "bearish" and macd == "BEARISH":
        base += 6
    return max(0, min(100, base))


def score_pattern_context(
    tech: Dict[str, Any],
    macro: Dict[str, Any],
    pattern: Dict[str, Any],
) -> int:
    """Pattern Context Score — location and macro backdrop (more important than name)."""
    score = 50
    support_dist = coerce_float(tech.get("support_dist_pct"), 99.0)
    resistance_dist = coerce_float(tech.get("resistance_dist_pct"), 99.0)
    direction = pattern.get("direction")

    if direction == "bullish" and support_dist <= 3:
        score += 22
    elif direction == "bullish" and support_dist <= 6:
        score += 10
    elif direction == "bearish" and resistance_dist <= 3:
        score += 18

    bias = macro.get("trend_bias")
    if direction == "bullish" and bias == "bullish":
        score += 15
    elif direction == "bullish" and bias == "bearish":
        score -= 20
    elif direction == "bearish" and bias == "bearish":
        score += 12
    elif direction == "bearish" and bias == "bullish":
        score -= 15

    if not macro.get("regime_allows_trading", True):
        score -= 12

    rsi = coerce_float(tech.get("rsi"), 50.0)
    if direction == "bullish" and rsi > 75:
        score -= 10
    if direction == "bearish" and rsi < 25:
        score -= 8

    return max(0, min(100, score))


def score_risk_geometry(
    trade_plan: Dict[str, Any],
    unified: Dict[str, Any],
    tech: Dict[str, Any],
) -> int:
    """Risk Geometry Score — stop, R:R, support distance."""
    stop = coerce_float(trade_plan.get("stop") or unified.get("stop"), 0.0)
    rr = coerce_float(unified.get("rr_ratio") or trade_plan.get("rr_ratio"), 0.0)
    if rr <= 0:
        rr = parse_ratio(trade_plan.get("rr_ratio_label"), 0.0) or 0.0

    score = 30
    if stop > 0:
        score += 25
    else:
        return min(score, 25)

    support_dist = coerce_float(tech.get("support_dist_pct"), 99.0)
    if support_dist <= 3:
        score += 20
    elif support_dist <= 6:
        score += 10
    elif support_dist > 12:
        score -= 15

    if rr >= TRADE_RR_MIN:
        score += 25
    elif rr >= 1.5:
        score += 10
    elif rr > 0:
        score -= 10

    return max(0, min(100, score))


def score_trend_alignment(macro: Dict[str, Any], pattern: Dict[str, Any]) -> int:
    """Trend Alignment Score from macro engine."""
    strength = coerce_float(macro.get("bias_strength"), 0.5) * 100
    direction = pattern.get("direction")
    bias = macro.get("trend_bias")
    if direction == "neutral":
        return int(max(35, min(60, strength * 0.7)))
    if (direction == "bullish" and bias == "bullish") or (
        direction == "bearish" and bias == "bearish"
    ):
        return int(min(100, strength + 15))
    if (direction == "bullish" and bias == "bearish") or (
        direction == "bearish" and bias == "bullish"
    ):
        return int(max(0, 40 - strength * 0.3))
    return int(strength)


def score_invalidation_clarity(
    trade_plan: Dict[str, Any],
    unified: Dict[str, Any],
    tech: Dict[str, Any],
) -> int:
    """Invalidation Clarity Score — explicit level + narrative."""
    inv = str(trade_plan.get("invalidation") or unified.get("invalidation") or "")
    stop = coerce_float(trade_plan.get("stop") or unified.get("stop"), 0.0)
    support = coerce_float(tech.get("support"), 0.0)

    score = 20
    if inv and inv not in ("—", "-", "None"):
        score += 35
        if "$" in inv or "below" in inv.lower() or "above" in inv.lower():
            score += 15
    if stop > 0:
        score += 20
    if support > 0 and ("support" in inv.lower() or str(round(support, 2)) in inv):
        score += 10
    return max(0, min(100, score))


def score_candlestick_execution_readiness(
    pattern_q: int,
    context_q: int,
    risk_q: int,
    trend_q: int,
    inv_q: int,
    *,
    has_stop: bool,
    rr: float,
) -> int:
    """
    Candlestick-specific execution readiness — distinct from execution_readiness.py.
    Requires geometry + context; pattern alone is insufficient.
    """
    if not has_stop:
        return min(25, pattern_q // 4)
    if rr > 0 and rr < 1.5:
        return min(35, int((pattern_q + context_q) / 4))

    weighted = (
        context_q * 0.30
        + risk_q * 0.25
        + trend_q * 0.20
        + inv_q * 0.15
        + pattern_q * 0.10
    )
    if context_q < CONTEXT_QUALITY_MIN:
        weighted *= 0.75
    if risk_q < 50:
        weighted *= 0.7
    return int(max(0, min(100, round(weighted))))


def resolve_composite_label(
    pattern_q: int,
    context_q: int,
    exec_q: int,
    macro: Dict[str, Any],
    pattern: Dict[str, Any],
) -> Tuple[str, str, List[str]]:
    """Return (primary_label_key, display_label, humility_chips)."""
    chips: List[str] = []
    direction = pattern.get("direction")
    bias = macro.get("trend_bias")

    if direction == "bullish" and bias == "bearish":
        chips.append(NISON_LABELS["bullish_pattern_bearish_backdrop"])

    if pattern_q >= PATTERN_QUALITY_MIN and context_q >= CONTEXT_QUALITY_MIN and exec_q >= 60:
        key = "strong_pattern_strong_context"
        chips.append(NISON_LABELS[key])
    elif pattern_q >= PATTERN_QUALITY_MIN and context_q < CONTEXT_QUALITY_MIN:
        key = "pattern_present_context_weak"
        chips.append(NISON_LABELS[key])
        chips.append(NISON_LABELS["detection_not_judgment"])
    elif pattern_q >= PATTERN_QUALITY_MIN and exec_q < 45:
        key = "strong_candle_poor_geometry"
        chips.append(NISON_LABELS[key])
    elif pattern_q >= 50 and context_q < 45:
        key = "pattern_present_not_actionable"
        chips.append(NISON_LABELS[key])
    elif pattern.get("pattern_name", "").endswith("reversal") or "reversal" in pattern.get("pattern_name", ""):
        key = "reversal_clue_not_trade"
        chips.append(NISON_LABELS[key])
    elif exec_q >= 55:
        key = "location_strengthens"
        chips.append(NISON_LABELS["location_strengthens"])
    else:
        key = "pattern_present_not_actionable"
        chips.append(NISON_LABELS["context_check_pending"])

    return key, NISON_LABELS.get(key, key.replace("_", " ")), chips[:4]


def build_chameleon_rule(
    macro: Dict[str, Any],
    pattern: Dict[str, Any],
    inv_text: str,
) -> str:
    """Thesis invalidation / market chameleon guidance."""
    bias = macro.get("trend_bias")
    direction = pattern.get("direction")
    if inv_text:
        return (
            f"If {inv_text}, abandon the prior read and reassess — "
            "Nison: let the market prove you wrong, then adapt."
        )
    if direction == "bullish" and bias == "bearish":
        return (
            "Bullish candle clue against bearish macro — size zero until "
            "macro trend aligns or invalidation level holds on a retest."
        )
    return (
        "When price action contradicts the pattern context, switch stance — "
        "do not marry the first label."
    )


def build_upgrade_break_triggers(
    scores: Dict[str, int],
    macro: Dict[str, Any],
    tech: Dict[str, Any],
) -> Dict[str, List[str]]:
    """What upgrades or breaks the candlestick thesis."""
    upgrades: List[str] = []
    breaks: List[str] = []

    if scores["pattern_context"] < CONTEXT_QUALITY_MIN:
        upgrades.append("Context score ≥55 with price holding support on volume")
    if scores["risk_geometry"] < 60:
        upgrades.append(f"R:R ≥{TRADE_RR_MIN}:1 with stop below logical swing low")
    if scores["trend_alignment"] < 55:
        upgrades.append("Reclaim 50-day MA with macro regime open")

    if not tech.get("above_sma50"):
        breaks.append("Close below 50-day MA — intermediate trend broken")
    support = coerce_float(tech.get("support"), 0.0)
    if support > 0:
        breaks.append(f"Daily close below support ${support:.2f}")
    if not macro.get("regime_allows_trading"):
        breaks.append("Board regime gate OFF — macro thesis invalid for new risk")
    if scores["invalidation_clarity"] < 40:
        breaks.append("Undefined invalidation — demote to watch until level is set")

    return {"upgrades": upgrades[:4], "breaks": breaks[:4]}


def build_candlestick_analysis(
    dossier: Dict[str, Any],
    unified: Optional[Dict[str, Any]] = None,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Full candlestick_analysis block for dossier / playbook enrichment.
    """
    tech = dict(dossier.get("technicals") or {})
    if dossier.get("price"):
        tech.setdefault("price", dossier.get("price"))
    reg = regime or dossier.get("regime") or {}
    unified = unified or {}
    trade_plan = dossier.get("trade_plan") or {}

    pattern = _infer_pattern_heuristic(tech)
    macro = assess_macro_trend(tech, reg)

    pq = score_pattern_quality(tech, pattern)
    cq = score_pattern_context(tech, macro, pattern)
    rq = score_risk_geometry(trade_plan, unified, tech)
    tq = score_trend_alignment(macro, pattern)
    iq = score_invalidation_clarity(trade_plan, unified, tech)

    stop = coerce_float(trade_plan.get("stop") or unified.get("stop"), 0.0)
    rr = coerce_float(unified.get("rr_ratio") or trade_plan.get("rr_ratio"), 0.0)
    if rr <= 0:
        rr = parse_ratio(trade_plan.get("rr_ratio_label"), 0.0) or 0.0

    exec_q = score_candlestick_execution_readiness(
        pq, cq, rq, tq, iq, has_stop=stop > 0, rr=rr
    )
    label_key, label_display, chips = resolve_composite_label(pq, cq, exec_q, macro, pattern)
    inv_text = str(trade_plan.get("invalidation") or unified.get("invalidation") or "")

    scores = {
        "pattern_quality": pq,
        "pattern_context": cq,
        "risk_geometry": rq,
        "trend_alignment": tq,
        "invalidation_clarity": iq,
        "execution_readiness": exec_q,
    }
    triggers = build_upgrade_break_triggers(scores, macro, tech)

    execution_status = "NOT_ACTIONABLE"
    if exec_q >= 65 and stop > 0 and rr >= TRADE_RR_MIN:
        execution_status = "ACTIONABLE"
    elif exec_q >= 45 and stop > 0:
        execution_status = "WATCH_FOR_TRIGGER"
    elif pq >= PATTERN_QUALITY_MIN:
        execution_status = "PATTERN_ONLY"

    if not stop:
        chips = list(dict.fromkeys(chips + [NISON_LABELS["no_stop_no_trade"]]))
    if rr > 0 and rr < TRADE_RR_MIN:
        chips = list(dict.fromkeys(chips + [NISON_LABELS["weak_rr_no_trade"]]))

    location_note = _location_note(tech, pattern, cq)

    return {
        "methodology": "Nison — context over pattern; macro first; risk-first gates",
        "detection_vs_judgment": {
            "detected": pattern.get("pattern_name"),
            "judgment": label_display,
            "note": NISON_LABELS["detection_not_judgment"],
        },
        "scores": scores,
        "composite_label": label_display,
        "composite_label_key": label_key,
        "humility_labels": chips,
        "pattern": {
            "name": pattern.get("pattern_name"),
            "direction": pattern.get("direction"),
            "quality_score": pq,
            "notes": pattern.get("detection_notes") or [],
            "is_heuristic": True,
        },
        "location": location_note,
        "macro_backdrop": macro,
        "stop_invalidation": {
            "stop": stop if stop > 0 else None,
            "invalidation": inv_text or None,
            "clarity_score": iq,
            "no_stop_no_trade": stop <= 0,
        },
        "risk_reward": {
            "ratio": round(rr, 2) if rr > 0 else None,
            "geometry_score": rq,
            "meets_trade_gate": rr >= TRADE_RR_MIN and stop > 0,
            "min_trade_rr": TRADE_RR_MIN,
        },
        "upgrade_breaks": triggers,
        "chameleon_rule": build_chameleon_rule(macro, pattern, inv_text),
        "execution_status": execution_status,
    }


def tags_for_playbook_row(
    analysis: Optional[Dict[str, Any]] = None,
    *,
    signal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compact tags for playbook / today rows."""
    if analysis:
        pat = analysis.get("pattern") or {}
        macro = analysis.get("macro_backdrop") or {}
        rr = analysis.get("risk_reward") or {}
        return {
            "pattern_tag": pat.get("name", "none"),
            "context_tag": analysis.get("composite_label_key"),
            "context_label": analysis.get("composite_label"),
            "rr_tag": "rr_ok" if rr.get("meets_trade_gate") else "rr_weak",
            "trend_tag": macro.get("trend_bias", "neutral"),
            "nison_execution_status": analysis.get("execution_status"),
            "nison_humility": analysis.get("humility_labels") or [],
            "context_checked": True,
        }
    sig = signal or {}
    tech = {
        "rsi": sig.get("rsi"),
        "above_sma50": sig.get("above_sma50"),
        "volume_ratio": sig.get("volume_ratio"),
    }
    stub = build_candlestick_analysis(
        {"technicals": tech, "trade_plan": {}, "price": sig.get("entry_price")},
        unified={
            "stop": sig.get("stop_price"),
            "rr_ratio": sig.get("risk_reward"),
            "invalidation": sig.get("invalidation"),
        },
    )
    return tags_for_playbook_row(stub)


def demote_scanner_hit_metadata(
    hit_metadata: Dict[str, Any],
    signal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Annotate scanner hit — pattern detections stay visible but demoted until context checked.
    """
    meta = dict(hit_metadata or {})
    sig = signal or meta
    tags = tags_for_playbook_row(signal=sig)
    meta["nison_context_label"] = tags.get("context_label") or NISON_LABELS["context_check_pending"]
    meta["nison_context_checked"] = tags.get("context_checked", False)
    exec_status = tags.get("nison_execution_status", "NOT_ACTIONABLE")
    if exec_status != "ACTIONABLE":
        meta["nison_demoted"] = True
        meta["nison_demote_reason"] = tags.get("context_label")
    return meta


def _location_note(tech: Dict[str, Any], pattern: Dict[str, Any], context_q: int) -> Dict[str, Any]:
    support = coerce_float(tech.get("support"), 0.0)
    resistance = coerce_float(tech.get("resistance"), 0.0)
    s_dist = coerce_float(tech.get("support_dist_pct"), 0.0)
    r_dist = coerce_float(tech.get("resistance_dist_pct"), 0.0)
    verdict = "neutral"
    if context_q >= 65 and s_dist <= 4:
        verdict = "support_zone_favorable"
    elif r_dist <= 3 and pattern.get("direction") == "bearish":
        verdict = "resistance_zone_favorable"
    elif s_dist > 10:
        verdict = "mid_range_poor_geometry"
    return {
        "support": support if support > 0 else None,
        "resistance": resistance if resistance > 0 else None,
        "support_dist_pct": s_dist,
        "resistance_dist_pct": r_dist,
        "verdict": verdict,
        "summary": (
            NISON_LABELS["location_strengthens"]
            if verdict == "support_zone_favorable"
            else "mid-range — location does not strengthen the signal"
            if verdict == "mid_range_poor_geometry"
            else "location neutral — confirm with macro trend"
        ),
    }
