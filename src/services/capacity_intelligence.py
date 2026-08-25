"""
Capacity intelligence — research-only scale & friction layer.

Existing services answer "is the edge real after cost?" (cost_adjusted_edge,
cost_adjusted_ranker, slippage_gate_service). Capacity answers the *next* two
operator questions that nothing else does:

    "Can this opportunity SCALE?"   and   "What is the edge net of SIZE?"

It layers a scale dimension on top of the existing cost primitive
(compute_net_edge), reusing — never duplicating — that cost math. The new
primitives here are:

  - %ADV usage (participation)               - market-impact pressure (bps, sqrt-law proxy)
  - participation-rate ceilings              - edge net of cost AND net of scale
  - capacity headroom (shares / sleeve / book) - capacity pressure score (0-100, componentized)
  - a four-way capacity classification        - per-card compact chip (downgrade-only)

Authority: research_only, downgrade-only (SIGNAL_CAPACITY). Capacity may only
shrink or demote an idea — it can never upgrade tradeability, authorize deploy,
or imply an IBKR handoff. Thresholds are aligned with slippage_gate_service so
the two layers agree on what "too big" means.

Honesty: every estimate is a heuristic, explicitly labeled. Missing ADV / price
data yields a degraded payload with classification 'unknown' — never a guess
dressed up as a number.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from src.services.cost_adjusted_edge import compute_net_edge
from src.services.signal_provenance import (
    SIGNAL_CAPACITY,
    build_provenance_envelope,
)
from src.services.slippage_gate_service import (
    HARD_PARTICIPATION,
    SOFT_PARTICIPATION,
)

# ---------------------------------------------------------------------------
# Thresholds — single source of truth, aligned with slippage_gate_service.
# ---------------------------------------------------------------------------
# Clean target participation (comfortable, low-impact). SOFT_PARTICIPATION (5%)
# is the warn line; HARD_PARTICIPATION (10%) is the refuse line. We treat the
# "clean" ceiling as 60% of the soft line so a clean fill leaves real headroom.
TARGET_PARTICIPATION = SOFT_PARTICIPATION * 0.6  # 3%
WARN_PARTICIPATION = SOFT_PARTICIPATION  # 5%
HARD_LIMIT_PARTICIPATION = HARD_PARTICIPATION  # 10%

# Square-root market-impact model: impact_fraction = coef * daily_vol * sqrt(part).
_IMPACT_COEF = 1.0
_DEFAULT_DAILY_VOL = 0.02  # 2% daily vol when not supplied
_MAX_SCALE_PENALTY = 1.5  # points off the 0-10 net-edge scale at the hard limit

# Spread (bps) that we consider "weak execution" friction.
_WEAK_SPREAD_BPS = 25.0
_HEAVY_SPREAD_BPS = 50.0

# ---------------------------------------------------------------------------
# Capacity classifications — the four operator-facing outcomes (+ the clean case).
# ---------------------------------------------------------------------------
CAP_SCALES_CLEAN = "scales_clean"
CAP_GOOD_CANNOT_SCALE = "good_but_cannot_scale"
CAP_PILOT_ONLY = "scale_pilot_only"
CAP_SCALE_WEAK_EXEC = "scale_weak_execution"
CAP_LOW_CAPACITY = "low_capacity_high_friction"
CAP_UNKNOWN = "unknown"

# Operator copy — single Python source. The JS mirror (cc-helpers.js) must use
# the SAME strings to preserve copy parity when the chips reach the UI.
CAPACITY_LABELS: Dict[str, str] = {
    CAP_SCALES_CLEAN: "Scales clean — capacity headroom OK",
    CAP_GOOD_CANNOT_SCALE: "Edge looks good but cannot scale — capacity constrained",
    CAP_PILOT_ONLY: "Scale as pilot only — limited capacity headroom",
    CAP_SCALE_WEAK_EXEC: "Scales but execution quality weak — high friction",
    CAP_LOW_CAPACITY: "Low capacity / high friction — monitor only",
    CAP_UNKNOWN: "Capacity unknown — liquidity data degraded",
}
# Research tones only — never a green/deploy tone. Capacity is downgrade-only.
CAPACITY_TONES: Dict[str, str] = {
    CAP_SCALES_CLEAN: "neutral",
    CAP_GOOD_CANNOT_SCALE: "caution",
    CAP_PILOT_ONLY: "caution",
    CAP_SCALE_WEAK_EXEC: "caution",
    CAP_LOW_CAPACITY: "muted",
    CAP_UNKNOWN: "muted",
}


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def participation_fraction(size_shares: float, adv: Optional[float]) -> Optional[float]:
    """Order size as a fraction of average daily volume. None if ADV unknown."""
    if not adv or adv <= 0 or size_shares is None or size_shares <= 0:
        return None
    return float(size_shares) / float(adv)


def participation_ceiling_shares(
    adv: Optional[float], participation: float
) -> Optional[int]:
    """Max shares at a given participation cap. None if ADV unknown."""
    if not adv or adv <= 0:
        return None
    return int(adv * participation)


def market_impact_bps(
    part_frac: Optional[float], daily_vol: float = _DEFAULT_DAILY_VOL
) -> Optional[float]:
    """Square-root-law market-impact proxy, in basis points.

    impact_fraction = coef * daily_vol * sqrt(participation); *10000 -> bps.
    Honest heuristic for *ranking humility*, not a venue-calibrated TCA number.
    """
    if part_frac is None or part_frac <= 0:
        return None
    vol = daily_vol if daily_vol and daily_vol > 0 else _DEFAULT_DAILY_VOL
    impact = _IMPACT_COEF * vol * math.sqrt(part_frac)
    return round(impact * 10000.0, 1)


def edge_net_of_scale(
    raw_score: float,
    *,
    part_frac: Optional[float],
    turnover_burden: float = 0.25,
    spread_burden: float = 0.20,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """Net edge after cost (reused) AND after a scale penalty.

    The scale penalty grows with participation toward the hard limit, so an idea
    that is fine in small size but degrades when sized up is shown honestly.
    """
    cost = compute_net_edge(
        raw_score,
        turnover_burden=turnover_burden,
        spread_burden=spread_burden,
        action=action,
    )
    net_after_cost = cost["net_deploy_score"]
    if part_frac is None:
        return {
            **cost,
            "scale_penalty": 0.0,
            "net_of_scale_score": net_after_cost,
            "scale_known": False,
        }
    # Intensity 0 at zero participation, 1 at the hard limit; squared so the
    # penalty bites harder as you approach the refuse line.
    intensity = min(1.0, part_frac / HARD_LIMIT_PARTICIPATION)
    scale_penalty = round((intensity**2) * _MAX_SCALE_PENALTY, 2)
    net_of_scale = round(max(0.0, net_after_cost - scale_penalty), 1)
    return {
        **cost,
        "scale_penalty": scale_penalty,
        "net_of_scale_score": net_of_scale,
        "scale_known": True,
    }


def capacity_pressure_score(
    *,
    part_frac: Optional[float],
    impact_bps: Optional[float],
    spread_bps: Optional[float],
    crowding: Optional[float] = None,
) -> Dict[str, Any]:
    """Composite 0-100 capacity pressure (higher = more constrained).

    Componentized so the operator sees exactly why capacity is tight.
    """
    components: Dict[str, float] = {}
    if part_frac is not None:
        components["participation"] = round(
            min(40.0, (part_frac / HARD_LIMIT_PARTICIPATION) * 40.0), 2
        )
    if impact_bps is not None:
        components["market_impact"] = round(min(30.0, impact_bps / 2.0), 2)
    if spread_bps is not None:
        components["spread"] = round(
            min(20.0, spread_bps / _HEAVY_SPREAD_BPS * 20.0), 2
        )
    if crowding is not None:
        components["crowding"] = round(min(10.0, float(crowding) / 10.0), 2)
    score = round(min(100.0, sum(components.values())), 2) if components else None
    return {"score": score, "components": components, "degraded": part_frac is None}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify_capacity(
    *,
    net_of_scale_score: float,
    net_after_cost: float,
    part_frac: Optional[float],
    impact_bps: Optional[float],
    spread_bps: Optional[float],
) -> str:
    """Map the metrics to one of the operator-facing capacity outcomes."""
    if part_frac is None:
        return CAP_UNKNOWN

    weak_exec = (spread_bps is not None and spread_bps >= _WEAK_SPREAD_BPS) or (
        impact_bps is not None and impact_bps >= 60.0
    )
    edge_good = net_after_cost >= 6.0
    over_hard = part_frac >= HARD_LIMIT_PARTICIPATION
    over_warn = part_frac >= WARN_PARTICIPATION
    over_target = part_frac > TARGET_PARTICIPATION

    # Edge survives cost but order already blows past the refuse line: good idea,
    # cannot be deployed at this size at all.
    if edge_good and over_hard:
        return CAP_GOOD_CANNOT_SCALE
    # Edge is gone once scale + cost are applied AND friction is high.
    if net_of_scale_score < 5.0 and (weak_exec or over_warn):
        return CAP_LOW_CAPACITY
    # Scales but execution friction erodes quality.
    if weak_exec and net_of_scale_score >= 5.0:
        return CAP_SCALE_WEAK_EXEC
    # Past the clean target but below warn — only pilot-size fits cleanly.
    if over_target and over_warn:
        return CAP_PILOT_ONLY
    if over_target:
        return CAP_PILOT_ONLY
    return CAP_SCALES_CLEAN


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------
def assess_capacity(
    *,
    ticker: str,
    size_shares: float,
    adv: Optional[float],
    price: Optional[float] = None,
    raw_score: float = 7.0,
    spread_bps: Optional[float] = None,
    daily_vol: float = _DEFAULT_DAILY_VOL,
    crowding: Optional[float] = None,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """Full per-ticker capacity assessment (research-only, downgrade-only)."""
    part_frac = participation_fraction(size_shares, adv)
    impact = market_impact_bps(part_frac, daily_vol)
    edge = edge_net_of_scale(raw_score, part_frac=part_frac, action=action)
    pressure = capacity_pressure_score(
        part_frac=part_frac, impact_bps=impact, spread_bps=spread_bps, crowding=crowding
    )
    classification = classify_capacity(
        net_of_scale_score=edge["net_of_scale_score"],
        net_after_cost=edge["net_deploy_score"],
        part_frac=part_frac,
        impact_bps=impact,
        spread_bps=spread_bps,
    )
    clean_ceiling = participation_ceiling_shares(adv, TARGET_PARTICIPATION)
    hard_ceiling = participation_ceiling_shares(adv, HARD_LIMIT_PARTICIPATION)
    headroom_clean = (
        max(0, clean_ceiling - int(size_shares)) if clean_ceiling is not None else None
    )
    degraded = part_frac is None
    return {
        "ticker": str(ticker).upper(),
        "classification": classification,
        "capacity_label": CAPACITY_LABELS[classification],
        "tone": CAPACITY_TONES[classification],
        "participation_pct": round(part_frac * 100, 2)
        if part_frac is not None
        else None,
        "target_participation_pct": round(TARGET_PARTICIPATION * 100, 2),
        "hard_limit_participation_pct": round(HARD_LIMIT_PARTICIPATION * 100, 2),
        "market_impact_bps": impact,
        "spread_bps": spread_bps,
        "clean_ceiling_shares": clean_ceiling,
        "hard_ceiling_shares": hard_ceiling,
        "headroom_to_clean_shares": headroom_clean,
        "edge": edge,
        "pressure": pressure,
        "degraded": degraded,
        "downgrade_only": True,
        "may_authorize_deploy": False,
        "model_note": "Heuristic %ADV / sqrt-impact estimate — scale humility, not live TCA.",
    }


def build_capacity_chip(
    *,
    ticker: str,
    size_shares: float,
    adv: Optional[float],
    raw_score: float = 7.0,
    spread_bps: Optional[float] = None,
    daily_vol: float = _DEFAULT_DAILY_VOL,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """Compact, scannable chip for Playbook / Dossier cards (supporting only).

    Returns the minimal fields a card needs: label, tone, classification, and a
    short detail. Never green/deploy-toned; explicitly downgrade-only.
    """
    a = assess_capacity(
        ticker=ticker,
        size_shares=size_shares,
        adv=adv,
        raw_score=raw_score,
        spread_bps=spread_bps,
        daily_vol=daily_vol,
        action=action,
    )
    part = a["participation_pct"]
    detail = (
        f"{part:.1f}% ADV · impact ~{a['market_impact_bps']}bps"
        if part is not None and a["market_impact_bps"] is not None
        else "liquidity data degraded"
    )
    return {
        "ticker": a["ticker"],
        "classification": a["classification"],
        "label": a["capacity_label"],
        "tone": a["tone"],
        "detail": detail,
        "degraded": a["degraded"],
        "downgrade_only": True,
    }


def build_sleeve_capacity(sleeves: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate capacity headroom by sleeve (Funds / Portfolio research).

    Each sleeve dict: {name, size_shares, adv, raw_score?, spread_bps?}. Sleeves
    are ranked by remaining clean headroom so the operator sees the best-funded
    and most-constrained sleeves at a glance.
    """
    rows: List[Dict[str, Any]] = []
    for s in sleeves:
        a = assess_capacity(
            ticker=s.get("name", "SLEEVE"),
            size_shares=s.get("size_shares", 0),
            adv=s.get("adv"),
            raw_score=s.get("raw_score", 7.0),
            spread_bps=s.get("spread_bps"),
        )
        rows.append(
            {
                "name": s.get("name", "sleeve"),
                "classification": a["classification"],
                "participation_pct": a["participation_pct"],
                "headroom_to_clean_shares": a["headroom_to_clean_shares"],
                "pressure_score": a["pressure"]["score"],
                "degraded": a["degraded"],
            }
        )
    scored = [r for r in rows if r["headroom_to_clean_shares"] is not None]
    best = max(scored, key=lambda r: r["headroom_to_clean_shares"]) if scored else None
    constrained = (
        min(scored, key=lambda r: r["headroom_to_clean_shares"]) if scored else None
    )
    return {
        "sleeves": rows,
        "best_funded_sleeve": best["name"] if best else None,
        "most_constrained_sleeve": constrained["name"] if constrained else None,
        "degraded": not scored,
    }


def build_capacity_context(
    *,
    ticker: str = "AAPL",
    size_shares: float = 1000,
    adv: Optional[float] = None,
    price: Optional[float] = None,
    raw_score: float = 7.0,
    spread_bps: Optional[float] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Research-only API payload wrapped in the provenance envelope.

    Authority: research_only, downgrade-only. Informs Playbook/Dossier/Funds
    context; never authorizes deploy (deploy_from_signal_alone=False, gate
    required) — guaranteed by build_provenance_envelope + SIGNAL_CAPACITY rules.
    """
    assessment = assess_capacity(
        ticker=ticker,
        size_shares=size_shares,
        adv=adv,
        price=price,
        raw_score=raw_score,
        spread_bps=spread_bps,
    )
    return build_provenance_envelope(
        signal_type=SIGNAL_CAPACITY,
        source="capacity_intelligence",
        degraded=degraded or assessment["degraded"],
        data_mode="research_only",
        extra={
            "capacity": assessment,
            "note": "Capacity is scale humility — it shrinks or demotes, never authorizes.",
        },
    )
