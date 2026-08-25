"""
Macro trend engine — Nison principle: macro first, micro second.

Uses existing dossier technicals and regime; stubs advanced chart biases
(three-line break, renko, trendline) for future OHLC pipelines.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.utils.numeric_parse import coerce_float


def _ma_stack(tech: Dict[str, Any]) -> str:
    """Ordered MA alignment label."""
    a20 = tech.get("above_sma20")
    a50 = tech.get("above_sma50")
    a200 = tech.get("above_sma200")
    if a20 and a50 and a200:
        return "bull_stack"
    if a20 and a50:
        return "bull_intermediate"
    if a20 and not a50:
        return "mixed_short_up"
    if not a20 and not a50 and a200 is False:
        return "bear_stack"
    if not a20 and not a50:
        return "bear_intermediate"
    return "mixed"


def assess_macro_trend(
    technicals: Optional[Dict[str, Any]] = None,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Macro backdrop for a single name or market proxy.

    Returns bias, MA alignment, distance context, and chart-method stubs.
    """
    tech = technicals or {}
    reg = regime or {}
    price = coerce_float(tech.get("price"), 0.0)
    rsi = coerce_float(tech.get("rsi"), 50.0)
    ma_stack = _ma_stack(tech)

    if ma_stack in ("bull_stack", "bull_intermediate"):
        trend_bias = "bullish"
        bias_strength = 0.75 if ma_stack == "bull_stack" else 0.6
    elif ma_stack in ("bear_stack", "bear_intermediate"):
        trend_bias = "bearish"
        bias_strength = 0.75 if ma_stack == "bear_stack" else 0.6
    else:
        trend_bias = "neutral"
        bias_strength = 0.45

    regime_label = str(reg.get("label") or reg.get("trend") or reg.get("regime_label") or "")
    should_trade = reg.get("should_trade", True)
    if not should_trade or "hostile" in regime_label.lower():
        trend_bias = "bearish" if trend_bias != "bullish" else "neutral"
        bias_strength = min(bias_strength, 0.5)

    macd = str(tech.get("macd_signal") or "").upper()
    if macd == "BULLISH" and trend_bias == "bullish":
        bias_strength = min(1.0, bias_strength + 0.1)
    elif macd == "BEARISH" and trend_bias == "bearish":
        bias_strength = min(1.0, bias_strength + 0.1)

    support_dist = coerce_float(tech.get("support_dist_pct"), 0.0)
    resistance_dist = coerce_float(tech.get("resistance_dist_pct"), 0.0)

    return {
        "trend_bias": trend_bias,
        "bias_strength": round(bias_strength, 2),
        "ma_alignment": ma_stack,
        "ma_labels": {
            "above_sma20": bool(tech.get("above_sma20")),
            "above_sma50": bool(tech.get("above_sma50")),
            "above_sma200": bool(tech.get("above_sma200")),
        },
        "rsi_context": round(rsi, 1),
        "support_dist_pct": support_dist,
        "resistance_dist_pct": resistance_dist,
        "regime_label": regime_label or None,
        "regime_allows_trading": bool(should_trade),
        "chart_methods": {
            "trendline": {"status": "stub", "note": "Swing high/low trendline bias pending OHLC feed"},
            "three_line_break": {"status": "stub", "note": "Three-line break direction pending daily bars"},
            "renko": {"status": "stub", "note": "Renko brick bias pending brick-size config"},
        },
        "summary": _macro_summary(trend_bias, ma_stack, regime_label, rsi),
        "price": round(price, 2) if price > 0 else None,
    }


def assess_market_macro(regime: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dashboard-level macro strip from cached regime (no per-ticker technicals)."""
    reg = regime or {}
    label = str(reg.get("trend") or reg.get("label") or "Unknown")
    tradeability = str(reg.get("tradeability") or ("OPEN" if reg.get("should_trade") else "WAIT"))
    vix = reg.get("vix")
    breadth = reg.get("breadth")
    should = bool(reg.get("should_trade", True))

    if "bull" in label.lower() or should:
        bias = "bullish" if should else "neutral"
    elif "bear" in label.lower() or "hostile" in label.lower():
        bias = "bearish"
    else:
        bias = "neutral"

    return {
        "trend_bias": bias,
        "regime_label": label,
        "tradeability": tradeability,
        "should_trade": should,
        "vix": vix,
        "breadth": breadth,
        "summary": f"Macro {label} · tradeability {tradeability}",
        "chart_methods": {
            "trendline": {"status": "regime_proxy"},
            "three_line_break": {"status": "stub"},
            "renko": {"status": "stub"},
        },
    }


def _macro_summary(bias: str, ma_stack: str, regime: str, rsi: float) -> str:
    parts = [f"Macro bias {bias}"]
    parts.append(f"MA stack {ma_stack.replace('_', ' ')}")
    if regime:
        parts.append(f"regime {regime}")
    if rsi >= 70:
        parts.append("RSI extended — favor patience on new longs")
    elif rsi <= 30:
        parts.append("RSI depressed — reversal clues need confirmation")
    return " · ".join(parts)
