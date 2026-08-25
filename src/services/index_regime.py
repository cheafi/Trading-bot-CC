"""
Index regime intelligence — VIX/vol, breadth, factor/style, cross-asset blocks.

Monitor-only / regime_filter labels — never grant deploy authority or override WAIT.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_INDEX_REGIME,
    build_provenance_envelope,
)

AUTHORITY_MONITOR_ONLY = "monitor_only"
AUTHORITY_REGIME_FILTER = "regime_filter"

POSTURE_RISK_ON = "risk_on"
POSTURE_NORMAL = "normal"
POSTURE_SELECTIVE = "selective"
POSTURE_STRESSED = "stressed"
POSTURE_NO_TRADE_PRESSURE = "no_trade_pressure"

POSTURE_LABELS: Dict[str, str] = {
    POSTURE_RISK_ON: "Risk-on — broad participation supports selective adds (filter only)",
    POSTURE_NORMAL: "Normal — standard regime filter; board gate still required",
    POSTURE_SELECTIVE: "Selective — narrow leadership; size down in research templates",
    POSTURE_STRESSED: "Stressed — vol elevated; downgrade urgency, not a veto alone",
    POSTURE_NO_TRADE_PRESSURE: "No-trade pressure — preserve capital; monitors only",
}

TERM_CONTANGO = "contango"
TERM_FLAT = "flat"
TERM_BACKWARDATION = "backwardation"
TERM_UNKNOWN = "unknown"

STRESS_LOW = "low"
STRESS_ELEVATED = "elevated"
STRESS_HIGH = "high"


def _vix_term_structure(vix: Optional[float], trend: str) -> str:
    """Cboe-style term-structure tag from spot VIX proxy (no futures feed)."""
    if vix is None:
        return TERM_UNKNOWN
    v = float(vix)
    t = (trend or "SIDEWAYS").upper()
    if v >= 28:
        return TERM_BACKWARDATION
    if v <= 16 and t == "UPTREND":
        return TERM_CONTANGO
    if 16 < v < 24:
        return TERM_FLAT
    if v >= 24:
        return TERM_BACKWARDATION
    return TERM_FLAT


def _vix_stress_level(vix: Optional[float]) -> str:
    if vix is None:
        return STRESS_ELEVATED
    v = float(vix)
    if v < 18:
        return STRESS_LOW
    if v < 26:
        return STRESS_ELEVATED
    return STRESS_HIGH


def build_vol_regime_block(
    *,
    vix: Optional[float],
    trend: str = "SIDEWAYS",
    volatility_label: str = "NORMAL",
    degraded: bool = False,
) -> Dict[str, Any]:
    term = _vix_term_structure(vix, trend)
    stress = _vix_stress_level(vix)
    spot = round(float(vix), 1) if vix is not None else None
    return {
        "block": "vix_vol",
        "authority": AUTHORITY_REGIME_FILTER,
        "monitor_only": True,
        "degraded": degraded or vix is None,
        "vix_spot": spot,
        "term_structure": term,
        "stress_level": stress,
        "volatility_label": volatility_label,
        "summary": (
            f"VIX {spot:.0f} · {term} · {stress} stress"
            if spot is not None
            else "VIX unavailable — MOCK/DEGRADED term proxy"
        ),
    }


def build_breadth_regime_block(
    *,
    breadth: Optional[float],
    scanner_participation: Optional[int] = None,
    universe_scanned: Optional[int] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    b = float(breadth) if breadth is not None else None
    if b is not None and b <= 1.0:
        b = b * 100.0
    participation = "broad"
    if b is not None:
        if b < 40:
            participation = "narrow"
        elif b < 55:
            participation = "mixed"
    elif scanner_participation is not None and universe_scanned:
        ratio = scanner_participation / max(universe_scanned, 1)
        participation = (
            "broad" if ratio > 0.12 else "mixed" if ratio > 0.05 else "narrow"
        )
    return {
        "block": "breadth",
        "authority": AUTHORITY_REGIME_FILTER,
        "monitor_only": True,
        "degraded": degraded or b is None,
        "breadth_pct": round(b, 0) if b is not None else None,
        "participation": participation,
        "scanner_hits": scanner_participation,
        "summary": (
            f"Breadth {b:.0f}% — {participation} participation"
            if b is not None
            else "Breadth proxy unavailable — scanner participation estimate only"
        ),
    }


def build_factor_regime_block(
    *,
    trend: str = "SIDEWAYS",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    cross_asset: Optional[Dict[str, Any]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """MSCI/AQR-style factor leadership tags — filter hints only."""
    t = (trend or "SIDEWAYS").upper()
    v = float(vix) if vix is not None else 20.0
    b = float(breadth) if breadth is not None else 50.0
    if b <= 1.0:
        b *= 100.0

    tags: List[str] = []
    if t == "UPTREND" and v < 22 and b >= 50:
        tags.append("momentum")
    if v >= 24 or b < 42:
        tags.append("min_vol")
    if 42 <= b <= 58 and v < 22:
        tags.append("quality")
    if cross_asset:
        for asset in cross_asset.get("assets") or []:
            if asset.get("symbol") == "TLT" and (asset.get("change_20d_pct") or 0) > 2:
                tags.append("value")
                break
    if not tags:
        tags.append("mixed")

    leadership = tags[0] if len(tags) == 1 else " · ".join(tags[:3])
    return {
        "block": "factor_style",
        "authority": AUTHORITY_REGIME_FILTER,
        "monitor_only": True,
        "degraded": degraded,
        "leadership_tags": tags,
        "leadership_label": leadership,
        "summary": f"Factor leadership: {leadership} (regime filter — not deploy)",
    }


def resolve_index_posture(
    *,
    should_trade: bool,
    tradeability: str,
    vix: Optional[float],
    breadth: Optional[float],
    trend: str,
    cross_asset_alignment: Optional[str] = None,
) -> str:
    tb = (tradeability or "").upper()
    stress = _vix_stress_level(vix)
    b = float(breadth) if breadth is not None else 50.0
    if b <= 1.0:
        b *= 100.0

    if not should_trade or tb in ("NO_TRADE", "WAIT") or stress == STRESS_HIGH:
        return POSTURE_NO_TRADE_PRESSURE
    if stress == STRESS_ELEVATED or b < 42 or cross_asset_alignment == "conflicted":
        return POSTURE_STRESSED
    if tb == "SELECTIVE" or b < 55 or cross_asset_alignment == "mixed":
        return POSTURE_SELECTIVE
    if (trend or "").upper() == "UPTREND" and b >= 55 and stress == STRESS_LOW:
        return POSTURE_RISK_ON
    return POSTURE_NORMAL


def build_index_regime_summary(
    *,
    trend: str = "SIDEWAYS",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    volatility_label: str = "NORMAL",
    should_trade: bool = True,
    tradeability: str = "WAIT",
    scanner_participation: Optional[int] = None,
    universe_scanned: Optional[int] = None,
    cross_asset: Optional[Dict[str, Any]] = None,
    source: str = "index-regime-proxy",
    degraded: bool = False,
) -> Dict[str, Any]:
    """Aggregate index regime blocks for Today / Playbook context."""
    vol_block = build_vol_regime_block(
        vix=vix, trend=trend, volatility_label=volatility_label, degraded=degraded
    )
    breadth_block = build_breadth_regime_block(
        breadth=breadth,
        scanner_participation=scanner_participation,
        universe_scanned=universe_scanned,
        degraded=degraded or vol_block.get("degraded"),
    )
    factor_block = build_factor_regime_block(
        trend=trend,
        vix=vix,
        breadth=breadth,
        cross_asset=cross_asset,
        degraded=degraded or vol_block.get("degraded"),
    )
    alignment = (cross_asset or {}).get("alignment")
    posture = resolve_index_posture(
        should_trade=should_trade,
        tradeability=tradeability,
        vix=vix,
        breadth=breadth,
        trend=trend,
        cross_asset_alignment=alignment,
    )
    any_degraded = bool(
        degraded
        or vol_block.get("degraded")
        or breadth_block.get("degraded")
        or factor_block.get("degraded")
        or not cross_asset
    )
    strip_parts = [
        POSTURE_LABELS.get(posture, posture),
        vol_block.get("summary", ""),
        breadth_block.get("summary", ""),
    ]
    strip_line = " · ".join(p for p in strip_parts if p)[:220]
    if any_degraded:
        strip_line = f"MOCK/DEGRADED · {strip_line}"

    body: Dict[str, Any] = {
        "posture": posture,
        "posture_label": POSTURE_LABELS.get(posture, posture),
        "authority": AUTHORITY_MONITOR_ONLY,
        "data_mode": AUTHORITY_REGIME_FILTER,
        "may_authorize_deploy": False,
        "may_override_wait": False,
        "may_influence": [
            "filter_ranking",
            "sizing_hints",
            "monitor_triggers",
            "playbook_sort",
        ],
        "may_never_influence": [
            "deploy_gate",
            "tradeability_upgrade",
            "wait_override",
            "standalone_trade_trigger",
        ],
        "vol_regime": vol_block,
        "breadth_regime": breadth_block,
        "factor_regime": factor_block,
        "cross_asset": cross_asset
        or {
            "degraded": True,
            "summary": "Cross-asset block pending — MOCK/DEGRADED",
            "monitor_only": True,
        },
        "strip_line": strip_line,
        "summary": strip_line,
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_INDEX_REGIME,
        source=source,
        as_of=datetime.now(timezone.utc).isoformat() + "Z",
        degraded=any_degraded,
        data_mode=AUTHORITY_REGIME_FILTER,
        extra=body,
    )


async def build_index_regime_for_today(
    request,
    *,
    market_regime: Dict[str, Any],
    cross_asset: Optional[Dict[str, Any]] = None,
    funnel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Async wrapper — may extend with live fetches later."""
    regime = market_regime or {}
    funnel = funnel or {}
    return build_index_regime_summary(
        trend=str(regime.get("trend") or "SIDEWAYS"),
        vix=regime.get("vix"),
        breadth=regime.get("breadth"),
        volatility_label=str(regime.get("volatility") or "NORMAL"),
        should_trade=bool(regime.get("should_trade")),
        tradeability=str(regime.get("tradeability") or "WAIT"),
        scanner_participation=funnel.get("signals_triggered")
        or funnel.get("actionable_above_7"),
        universe_scanned=funnel.get("universe"),
        cross_asset=cross_asset,
        source="today-index-regime",
        degraded=bool(regime.get("vix") is None or not cross_asset),
    )
