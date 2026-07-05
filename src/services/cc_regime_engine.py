"""
Advanced regime / index engine — posture and monitor support only.

Never grants deploy permission or overrides board WAIT.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.crisis_regime import classify_crisis_state
from src.services.index_regime import (
    STRESS_HIGH,
    STRESS_LOW,
    TERM_BACKWARDATION,
    TERM_CONTANGO,
    TERM_FLAT,
    _vix_stress_level,
    _vix_term_structure,
)

AUTHORITY_REGIME = "research_only"
AUTHORITY_CONFIRMATION = "confirmation_only"


def _index_trend_state(
    symbol: str,
    *,
    market_trend: str,
    change_20d: Optional[float] = None,
) -> Dict[str, Any]:
    t = (market_trend or "SIDEWAYS").upper()
    c = float(change_20d) if change_20d is not None else 0.0
    if t == "UPTREND" and c > 1.5:
        state = "trend_up"
    elif t == "DOWNTREND" or c < -3:
        state = "trend_down"
    elif abs(c) < 0.5:
        state = "range"
    else:
        state = "mixed"
    return {
        "symbol": symbol,
        "state": state,
        "change_20d_pct": round(c, 2) if change_20d is not None else None,
        "monitor_only": True,
    }


def _breadth_thrust_decay(
    breadth: Optional[float],
    *,
    prior_breadth: Optional[float] = None,
) -> Dict[str, Any]:
    b = float(breadth) if breadth is not None else None
    if b is not None and b <= 1.0:
        b *= 100.0
    if b is None:
        return {
            "signal": "unknown",
            "label": "Breadth unavailable — MOCK/DEGRADED",
            "degraded": True,
        }
    prior = float(prior_breadth) if prior_breadth is not None else b
    if prior <= 1.0:
        prior *= 100.0
    delta = b - prior
    if delta >= 8:
        signal = "thrust"
        label = f"Breadth thrust +{delta:.0f}pts — participation expanding"
    elif delta <= -8:
        signal = "decay"
        label = f"Breadth decay {delta:.0f}pts — narrow participation risk"
    else:
        signal = "stable"
        label = f"Breadth stable ({b:.0f}%) — filter context only"
    return {"signal": signal, "label": label, "breadth_pct": round(b, 0), "degraded": False}


def _risk_on_off_composite(
    *,
    vix: Optional[float],
    breadth: Optional[float],
    trend: str,
    tradeability: str,
) -> Dict[str, Any]:
    stress = _vix_stress_level(vix)
    b = float(breadth) if breadth is not None else 50.0
    if b <= 1.0:
        b *= 100.0
    tb = (tradeability or "").upper()
    score = 50
    if stress == STRESS_LOW:
        score += 15
    elif stress == STRESS_HIGH:
        score -= 25
    if b >= 55:
        score += 15
    elif b < 42:
        score -= 15
    if (trend or "").upper() == "UPTREND":
        score += 10
    elif (trend or "").upper() == "DOWNTREND":
        score -= 20
    if tb in ("WAIT", "NO_TRADE"):
        score -= 10
    score = max(0, min(100, score))
    if score >= 65:
        band = "risk_on"
    elif score >= 45:
        band = "neutral"
    else:
        band = "risk_off"
    return {
        "score": score,
        "band": band,
        "label": f"Risk composite {score}/100 ({band}) — posture filter only",
        "may_authorize_deploy": False,
    }


def _vol_compression_expansion(vix: Optional[float]) -> Dict[str, Any]:
    if vix is None:
        return {"state": "unknown", "label": "Vol state unknown — degraded"}
    v = float(vix)
    if v < 14:
        state = "compression"
        label = "Vol compression — breakout risk elevated (confirm-only)"
    elif v > 26:
        state = "expansion"
        label = "Vol expansion — size humility (downgrade-only)"
    else:
        state = "normal"
        label = "Vol in normal band — standard filter"
    return {"state": state, "label": label, "vix": round(v, 1)}


def _sector_rotation_engine(
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    leaders = list(sector_leaders or [])
    if not leaders:
        return {
            "rotation": "unknown",
            "label": "Sector rotation unavailable — research context only",
            "degraded": True,
        }
    names = [str(l.get("sector") or l.get("name") or "") for l in leaders[:3]]
    return {
        "rotation": "active",
        "leaders": names,
        "label": f"Leadership: {', '.join(n for n in names if n) or '—'} — not a trade route",
        "degraded": False,
    }


def _macro_pressure_strip(
    cross_asset: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    assets = list((cross_asset or {}).get("assets") or [])
    pressures: List[str] = []
    for sym in ("TLT", "UUP", "USO", "GLD"):
        row = next((a for a in assets if a.get("symbol") == sym), None)
        if not row:
            continue
        c20 = row.get("change_20d_pct")
        if c20 is None:
            continue
        if sym == "TLT" and float(c20) > 2:
            pressures.append("rates bid")
        if sym == "UUP" and float(c20) > 1.5:
            pressures.append("dollar firm")
        if sym == "USO" and abs(float(c20)) > 3:
            pressures.append("oil volatile")
    if not pressures:
        return {
            "pressures": [],
            "label": "Macro pressure neutral or unavailable — confirm-only",
            "degraded": not assets,
        }
    return {
        "pressures": pressures,
        "label": f"Macro pressure: {', '.join(pressures)} — filter only",
        "degraded": False,
    }


def build_advanced_regime_stack(
    *,
    trend: str = "SIDEWAYS",
    vix: Optional[float] = None,
    breadth: Optional[float] = None,
    tradeability: str = "WAIT",
    should_trade: bool = True,
    cross_asset: Optional[Dict[str, Any]] = None,
    sector_leaders: Optional[List[Dict[str, Any]]] = None,
    prior_breadth: Optional[float] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Aggregate advanced regime trackers for Dashboard / macro strips."""
    term = _vix_term_structure(vix, trend)
    crisis = classify_crisis_state(
        tradeability=tradeability,
        vix=vix,
        breadth=breadth,
        should_trade=should_trade,
    )
    index_states = {
        sym: _index_trend_state(
            sym,
            market_trend=trend,
            change_20d=_asset_change(cross_asset, sym),
        )
        for sym in ("SPY", "QQQ", "IWM", "DIA")
    }
    stack = {
        "authority": AUTHORITY_REGIME,
        "monitoring_only": True,
        "may_authorize_deploy": False,
        "degraded": degraded or vix is None,
        "vix_term_structure": {
            "term": term,
            "label": (
                f"VIX term {term}"
                + (" — stress backwardation" if term == TERM_BACKWARDATION else "")
            ),
        },
        "vix_regime_band": {
            "stress": _vix_stress_level(vix),
            "vix": round(float(vix), 1) if vix is not None else None,
        },
        "breadth_thrust_decay": _breadth_thrust_decay(
            breadth, prior_breadth=prior_breadth
        ),
        "index_trend_states": index_states,
        "risk_on_off": _risk_on_off_composite(
            vix=vix, breadth=breadth, trend=trend, tradeability=tradeability
        ),
        "vol_compression_expansion": _vol_compression_expansion(vix),
        "sector_rotation": _sector_rotation_engine(sector_leaders),
        "macro_pressure": _macro_pressure_strip(cross_asset),
        "crisis_monitor": {
            "state": crisis,
            "label": f"Crisis monitor: {crisis} — preservation filter",
        },
        "participation_quality": {
            "label": (
                "Participation broad"
                if (breadth or 0) >= 55
                else "Participation narrow — downgrade filter"
            ),
        },
    }
    parts = [
        stack["risk_on_off"]["label"],
        stack["breadth_thrust_decay"]["label"],
        stack["vol_compression_expansion"]["label"],
    ]
    strip = " · ".join(p for p in parts if p)[:240]
    if stack["degraded"]:
        strip = f"MOCK/DEGRADED · {strip}"
    stack["strip_line"] = strip + " — not deploy authority"
    return stack


def _asset_change(cross_asset: Optional[Dict[str, Any]], symbol: str) -> Optional[float]:
    if not cross_asset:
        return None
    row = next(
        (a for a in (cross_asset.get("assets") or []) if a.get("symbol") == symbol),
        None,
    )
    if not row:
        return None
    val = row.get("change_20d_pct")
    return float(val) if val is not None else None
