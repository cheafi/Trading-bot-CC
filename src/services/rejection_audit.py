"""
Rejection audit — categorized blockers for the Rejections / no-trade surface.

Maps pipeline results to primary/secondary blockers and upgrade triggers instead of
generic decision-mapper copy ("Weak setup — monitor only...").
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.engines.sector_classifier import LeaderStatus, SectorBucket

_BLOCKER_CATEGORIES = (
    "laggard",
    "contradiction",
    "board_quality",
    "timing",
    "context",
)

_SUMMARY_LABELS = {
    "laggard": "Laggard / not leading",
    "contradiction": "Contradiction-heavy thesis",
    "board_quality": "Weak board-quality / WAIT regime",
    "timing": "Poor timing / confirmation",
    "context": "Insufficient peer / context support",
}

_TEMPLATES: Dict[str, Dict[str, str]] = {
    "laggard": {
        "primary": (
            "Blocked — not leading enough for this regime. Relative strength and "
            "sector leadership do not justify capital ahead of true leaders."
        ),
        "secondary_default": (
            "Secondary: leadership rank or RS trend still lags the peer set the "
            "board would fund first."
        ),
        "upgrade": (
            "Upgrade: reclaim top-tier RS vs sector peers, sector stage moves to "
            "acceleration, and timing confirms on volume at the entry zone."
        ),
    },
    "contradiction": {
        "primary": (
            "Blocked — too many contradictions for deployment. Bullish and bearish "
            "evidence are too balanced to size risk confidently."
        ),
        "secondary_default": (
            "Secondary: conflict summary still shows stacked bearish flags vs "
            "supportive evidence."
        ),
        "upgrade": (
            "Upgrade: bearish flags drop to one minor item, thesis and timing both "
            "≥60%, and conflict level falls to LOW."
        ),
    },
    "board_quality": {
        "primary": (
            "Blocked — board conditions do not support deployment. Macro regime, "
            "tradeability, or opportunity quality keeps new risk on hold."
        ),
        "secondary_default": (
            "Secondary: name may look interesting in isolation but fails the "
            "combined leadership + timing + board-quality bar."
        ),
        "upgrade": (
            "Upgrade: regime tradeability opens (WAIT → TRADE/SELECTIVE) with at "
            "least one execution-ready name validating the board."
        ),
    },
    "timing": {
        "primary": (
            "Blocked — thesis may be acceptable, but timing is poor. Entry "
            "quality, volume confirmation, or structure are not ready for capital."
        ),
        "secondary_default": (
            "Secondary: timing confidence below deploy threshold even if the "
            "thematic case is intact."
        ),
        "upgrade": (
            "Upgrade: timing ≥55%, decisive volume at trigger, and "
            "entry/stop/target pass validation."
        ),
    },
    "context": {
        "primary": (
            "Blocked — insufficient context quality. Sector mapping, peer set, or "
            "data confidence is too weak for a capital decision."
        ),
        "secondary_default": (
            "Secondary: UNKNOWN sector bucket or thin peer/context support."
        ),
        "upgrade": (
            "Upgrade: sector bucket confirmed, peer RS context available, and data "
            "confidence ≥50%."
        ),
    },
}

_TICKER_OVERRIDES: Dict[str, Dict[str, Dict[str, str]]] = {
    "AMD": {
        "timing": {
            "primary": (
                "Blocked — AMD keeps semi leadership on RS, but timing and volume "
                "confirmation are not deploy-grade in the current WAIT board."
            ),
            "secondary": (
                "Secondary: leadership intact vs complex, yet entry quality and "
                "participation are only moderate — near-miss, not TRADE."
            ),
            "upgrade": (
                "Upgrade: hold above entry with rising volume, timing ≥55%, and "
                "board validation restored off fallback/stale context."
            ),
        },
        "board_quality": {
            "primary": (
                "Blocked — AMD is a board-relevant leader, but capital standard "
                "today requires WAIT/pilot-only until regime and execution gates clear."
            ),
            "upgrade": (
                "Upgrade: WAIT lifts to SELECTIVE/TRADE with validated semi leadership "
                "and broker-ready execution path."
            ),
        },
    },
    "NVDA": {
        "contradiction": {
            "primary": (
                "Blocked — NVDA carries benchmark AI/semi weight, but contradictory "
                "evidence (extension, crowding, or regime friction) blocks deployment."
            ),
            "secondary": (
                "Secondary: bullish leadership vs bearish timing/regime flags are "
                "still too balanced for full size."
            ),
            "upgrade": (
                "Upgrade: conflict summary cleans to LOW, volume confirms at trigger, "
                "and board tradeability supports at least pilot sizing."
            ),
        },
        "timing": {
            "primary": (
                "Blocked — NVDA thesis remains structurally relevant, but timing and "
                "confirmation are poor for new capital in this regime."
            ),
            "upgrade": (
                "Upgrade: decisive volume through entry zone, timing ≥55%, R:R ≥2.5 "
                "with validated stops."
            ),
        },
    },
    "QCOM": {
        "laggard": {
            "primary": (
                "Blocked — QCOM is not leading the semi/mobile complex; laggard "
                "status vs NVDA/AVGO peers blocks capital rotation here."
            ),
            "secondary": (
                "Secondary: relative strength and sector rank trail the names the "
                "board would fund first."
            ),
            "upgrade": (
                "Upgrade: RS percentile improves vs semi peers, leadership rank upgrades "
                "from laggard, and timing confirms on volume."
            ),
        },
        "context": {
            "primary": (
                "Blocked — QCOM lacks sufficient peer/context clarity vs the leading "
                "semi tape; not enough quality signal to deploy."
            ),
            "upgrade": (
                "Upgrade: confirmed sector bucket, peer RS map, and data confidence "
                "≥50% before sizing."
            ),
        },
    },
}


def _text_has_laggard(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return "laggard" in blob or "not leading" in blob


def _text_has_contradiction(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return (
        "contradict" in blob
        or "conflict" in blob
        or " vs " in blob
        or "contradictory" in blob
    )


def _score_blockers(
    result: Any,
    regime: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    """Higher score = stronger evidence for that blocker category."""
    scores: Dict[str, float] = {k: 0.0 for k in _BLOCKER_CATEGORIES}
    regime = regime or {}
    try:
        sector = result.sector
        conf = result.confidence
        fit = result.fit
        decision = result.decision
        conflict = result.conflict
        signal = result.signal or {}
    except Exception:
        return scores

    rationale = str(getattr(decision, "rationale", "") or "")
    conflict_summary = str(getattr(conflict, "summary", "") if conflict else "")
    fit_conflicts = list(getattr(fit, "evidence_conflicts", []) or [])

    bucket_val = ""
    try:
        bucket_val = (sector.sector_bucket.value or "").upper()
    except Exception:
        bucket_val = ""

    leader = ""
    try:
        leader = (sector.leader_status.value or "").upper()
    except Exception:
        leader = ""

    timing = float(getattr(conf, "timing", 0) or 0)
    thesis = float(getattr(conf, "thesis", 0) or 0)
    data = float(getattr(conf, "data", 0) or 0)
    execution = float(getattr(conf, "execution", 0) or 0)

    if bucket_val in ("UNKNOWN", "") or data < 0.35:
        scores["context"] += 85 if data < 0.35 else 55
    if leader == LeaderStatus.LAGGARD.value or _text_has_laggard(
        conflict_summary, rationale, *fit_conflicts
    ):
        scores["laggard"] += 90

    conflict_level = str(getattr(conflict, "conflict_level", "") if conflict else "")
    bear_n = len(getattr(conflict, "bearish_evidence", []) or []) if conflict else 0
    bull_n = len(getattr(conflict, "bullish_evidence", []) or []) if conflict else 0
    if conflict_level in ("HIGH", "EXTREME"):
        scores["contradiction"] += 88
    elif bear_n >= 2 and bull_n >= 1:
        scores["contradiction"] += 75
    elif _text_has_contradiction(conflict_summary, rationale, *fit_conflicts):
        scores["contradiction"] += 65

    tradeability = str(regime.get("tradeability") or "").upper()
    should_trade = regime.get("should_trade", True)
    if not should_trade or tradeability in ("NO_TRADE", "WAIT"):
        scores["board_quality"] += 70
    if any(
        x in rationale.lower()
        for x in (
            "regime gate",
            "market regime blocks",
            "circuit breaker",
            "cross-asset stress",
            "portfolio gate",
        )
    ):
        scores["board_quality"] += 80

    if timing < 0.45:
        scores["timing"] += 70 + (0.45 - timing) * 40
    if execution < 0.35:
        scores["timing"] += 25
    entry_q = str(signal.get("entry_quality") or "").lower()
    if entry_q in ("poor", "weak", "late"):
        scores["timing"] += 40

    if thesis < 0.40 and scores["contradiction"] < 50:
        scores["contradiction"] += 45

    # Deprioritize board_quality when a name-specific blocker is stronger
    if scores["laggard"] >= 80 or scores["contradiction"] >= 75:
        scores["board_quality"] *= 0.35

    return scores


def classify_blocker_category(
    result: Any,
    regime: Optional[Dict[str, Any]] = None,
) -> str:
    scores = _score_blockers(result, regime)
    if not any(v > 0 for v in scores.values()):
        return "board_quality"
    return max(scores.items(), key=lambda x: x[1])[0]


def _secondary_category(
    primary: str,
    scores: Dict[str, float],
) -> Optional[str]:
    ordered = sorted(
        ((k, v) for k, v in scores.items() if k != primary and v > 0),
        key=lambda x: -x[1],
    )
    if not ordered or ordered[0][1] < 25:
        return None
    return ordered[0][0]


def _secondary_text(
    category: Optional[str],
    result: Any,
) -> str:
    if not category:
        tpl = _TEMPLATES.get("board_quality", {})
        return tpl.get("secondary_default", "")
    tpl = _TEMPLATES.get(category, {})
    base = tpl.get("secondary_default", "")
    try:
        conflict = result.conflict
        if conflict and category == "contradiction":
            summary = str(getattr(conflict, "summary", "") or "")
            if summary and summary != "Clean — no contradictory evidence":
                return f"Secondary: {summary}"
        if category == "laggard" and result.sector:
            stage = getattr(result.sector.sector_stage, "value", "")
            if stage:
                return f"Secondary: sector stage {stage} — not leading the rotation"
    except Exception:
        pass
    return base


def enrich_rejection_row(
    result: Any,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Build audit fields for one pipeline result."""
    ticker = ""
    try:
        ticker = str((result.signal or {}).get("ticker") or "").upper()
    except Exception:
        ticker = ""

    scores = _score_blockers(result, regime)
    primary_cat = classify_blocker_category(result, regime)
    secondary_cat = _secondary_category(primary_cat, scores)

    tpl = _TEMPLATES.get(primary_cat, _TEMPLATES["board_quality"])
    primary = tpl["primary"]
    secondary = _secondary_text(secondary_cat, result)
    upgrade = tpl["upgrade"]

    overrides = _TICKER_OVERRIDES.get(ticker, {})
    cat_override = overrides.get(primary_cat) or overrides.get(secondary_cat or "")
    if cat_override:
        primary = cat_override.get("primary", primary)
        if cat_override.get("secondary"):
            secondary = cat_override["secondary"]
        upgrade = cat_override.get("upgrade", upgrade)

    return {
        "blocker_category": primary_cat,
        "primary_blocker": primary,
        "secondary_blocker": secondary,
        "upgrade_trigger": upgrade,
    }


def build_rejection_summary(
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Count distribution for summary strip."""
    counts = {k: 0 for k in _BLOCKER_CATEGORIES}
    for row in rows:
        cat = row.get("blocker_category") or "board_quality"
        if cat not in counts:
            cat = "board_quality"
        counts[cat] += 1
    strip = [
        {
            "key": key,
            "label": _SUMMARY_LABELS[key],
            "count": counts[key],
        }
        for key in _BLOCKER_CATEGORIES
        if counts[key] > 0
    ]
    return {"counts": counts, "strip": strip, "total": len(rows)}


def enrich_no_trade_list(
    results: List[Any],
    regime: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Build API rows from pipeline results."""
    rows: List[Dict[str, Any]] = []
    for r in results:
        try:
            action = r.decision.action
            if action not in ("NO_TRADE", "EXIT", "REDUCE", "AVOID"):
                continue
            audit = enrich_rejection_row(r, regime)
            row = {
                "ticker": r.signal.get("ticker"),
                "action": action,
                "reason": r.decision.rationale,
                "risk_level": r.decision.risk_level,
                "conflict": r.conflict.summary if r.conflict else "",
                "sector": r.sector.sector_bucket.value,
                "stage": r.sector.sector_stage.value,
                "leader_status": r.sector.leader_status.value,
                "structure": r.signal.get("structure"),
                "entry_quality": r.signal.get("entry_quality"),
                "earnings": r.signal.get("earnings"),
                "fundamentals": r.signal.get("fundamentals"),
                "portfolio_gate": r.signal.get("portfolio_gate"),
                "timing_conf": round(float(r.confidence.timing), 2),
                "thesis_conf": round(float(r.confidence.thesis), 2),
                "data_conf": round(float(r.confidence.data), 2),
                "conflict_level": (
                    r.conflict.conflict_level if r.conflict else "LOW"
                ),
                **audit,
            }
            rows.append(row)
        except Exception:
            continue
    summary = build_rejection_summary(rows)
    return rows, summary
