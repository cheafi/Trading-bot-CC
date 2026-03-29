"""
TradingAI Pro v6 — Report Generator
=====================================
Format-agnostic report builder that produces structured report data
consumable by Discord embeds, HTML templates, and Markdown export.

Report types:
  • Morning Decision Memo  (pre-market, ~09:25 ET)
  • EOD Scorecard          (post-close, ~16:10 ET)
  • Signal Card            (per signal, on demand)
  • Regime Snapshot        (on demand, /market_now)

All builders return plain dicts so renderers (Discord, API)
can consume them without importing heavyweight UI libraries.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.core.models import (
    ChangeItem,
    DeltaSnapshot,
    FlowsPositioning,
    MarketRegime,
    RegimeScoreboard,
    ScenarioPlan,
    Signal,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _grade_emoji(grade: Optional[str]) -> str:
    return {"A": "🅰️", "B": "🅱️", "C": "🆑", "D": "🆔"}.get(grade or "", "❓")


def _approval_emoji(status: str) -> str:
    return {"approved": "✅", "conditional": "🟡", "rejected": "❌"}.get(status, "❓")


def _regime_color(label: str) -> int:
    """Discord-compatible colour int."""
    label_lc = label.lower()
    if "risk_on" in label_lc or "risk on" in label_lc:
        return 0x00C853   # green
    if "risk_off" in label_lc or "risk off" in label_lc:
        return 0xFF1744   # red
    return 0xFFAB00       # amber


def _pct_bar(pct: float, width: int = 10) -> str:
    filled = max(0, min(width, int(abs(pct) / 10 * width)))
    sym = "🟢" if pct >= 0 else "🔴"
    return f"{sym} {'█' * filled}{'░' * (width - filled)} {pct:+.2f}%"


def _format_vol(v: float) -> str:
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return str(int(v))


# ─────────────────────────────────────────────────────────────────────
# 1. Signal Card (v6)
# ─────────────────────────────────────────────────────────────────────

def build_signal_card(signal: Signal) -> Dict[str, Any]:
    """
    Build a v6 signal card dict with all pro-desk fields.

    Returns dict with keys:
        title, description, color, fields[], footer
    Each field = {name, value, inline}
    """
    direction = getattr(signal.direction, "value", str(signal.direction))
    is_buy = direction.upper() in ("LONG", "BUY")
    arrow = "🟢 LONG" if is_buy else "🔴 SHORT"
    conf = signal.confidence or 0
    color = 0xFFD600 if conf >= 80 else (0x00C853 if is_buy else 0xFF1744)

    fields: List[Dict[str, Any]] = []

    # ── Confidence + Approval ──
    approval = _approval_emoji(signal.approval_status)
    grade = _grade_emoji(signal.setup_grade)
    fields.append({
        "name": "Confidence",
        "value": (
            f"{'█' * (conf // 10)}{'░' * (10 - conf // 10)} {conf}% "
            f"{approval} {grade} {signal.setup_grade or '?'}"
        ),
        "inline": False,
    })

    # ── Horizon + Edge Type ──
    horizon_val = getattr(signal.horizon, "value", str(signal.horizon))
    fields.append({"name": "Horizon", "value": horizon_val, "inline": True})
    if signal.edge_type:
        fields.append({"name": "Edge", "value": f"`{signal.edge_type}`", "inline": True})

    # ── Targets ──
    if signal.targets:
        t_str = "\n".join(
            f"`T{i + 1}` ${t.price:.2f} ({t.pct_position}%)"
            for i, t in enumerate(signal.targets)
        )
        fields.append({"name": "🎯 Targets", "value": t_str, "inline": False})

    # ── Stop ──
    if signal.invalidation:
        inv = signal.invalidation
        fields.append({
            "name": "🛑 Stop",
            "value": f"${inv.stop_price:.2f} ({getattr(inv.stop_type, 'value', inv.stop_type)})",
            "inline": True,
        })

    # ── R:R ──
    if signal.risk_reward_ratio:
        fields.append({"name": "R:R", "value": f"**{signal.risk_reward_ratio:.1f}:1**", "inline": True})

    # ── EV ──
    if signal.expected_value is not None:
        fields.append({"name": "EV", "value": f"**{signal.expected_value:+.1f}%**", "inline": True})

    # ── Strategy ──
    if signal.strategy_id:
        fields.append({"name": "Strategy", "value": f"`{signal.strategy_id}`", "inline": True})

    # ── Why Now (v6) ──
    if signal.why_now:
        fields.append({"name": "⏱️ Why Now", "value": signal.why_now, "inline": False})

    # ── Time Stop ──
    if signal.time_stop_days:
        fields.append({"name": "⏳ Time Stop", "value": f"{signal.time_stop_days} days", "inline": True})

    # ── Event Risk ──
    if signal.event_risk:
        fields.append({"name": "📅 Event Risk", "value": signal.event_risk, "inline": True})

    # ── Edge Model (from feature_snapshot) ──
    fs = signal.feature_snapshot or {}
    edge = fs.get("edge_model", {})
    if edge:
        p_t1 = edge.get("p_t1", 0)
        p_stop = edge.get("p_stop", 0)
        ev = edge.get("expected_return_pct", 0)
        sample = edge.get("sample_size", 0)
        cal = f"(n={sample})" if sample >= 30 else "(base-rate)"
        fields.append({
            "name": "📊 Edge Model",
            "value": (
                f"P(T1): **{p_t1 * 100:.0f}%** | P(stop): {p_stop * 100:.0f}%\n"
                f"EV: **{ev:+.1f}%** | Hold: {edge.get('expected_holding_days', '?')}d\n"
                f"MAE: {edge.get('expected_mae_pct', 0):.1f}% {cal}"
            ),
            "inline": False,
        })

    # ── Scenario Plan (v6) ──
    sp = signal.scenario_plan
    if sp:
        base = sp.get("base_case", {})
        bull = sp.get("bull_case", {})
        bear = sp.get("bear_case", {})
        scenario_lines = []
        if base:
            scenario_lines.append(f"**Base** ({base.get('probability', '?')}): {base.get('description', '—')}")
        if bull:
            scenario_lines.append(f"**Bull** ({bull.get('probability', '?')}): {bull.get('description', '—')}")
        if bear:
            scenario_lines.append(f"**Bear** ({bear.get('probability', '?')}): {bear.get('description', '—')}")
        if scenario_lines:
            fields.append({
                "name": "🗺️ Scenario Map",
                "value": "\n".join(scenario_lines),
                "inline": False,
            })

    # ── Evidence (v6) ──
    if signal.evidence:
        fields.append({
            "name": "📋 Evidence",
            "value": "\n".join(f"• {e}" for e in signal.evidence[:5]),
            "inline": False,
        })

    # ── Risks ──
    if signal.key_risks:
        fields.append({
            "name": "⚠️ Risks",
            "value": "\n".join(f"• {r}" for r in signal.key_risks[:3]),
            "inline": False,
        })

    # ── Portfolio Fit ──
    if signal.portfolio_fit:
        fit_icon = {"good": "✅", "overlap": "⚠️", "concentrated": "🔴"}.get(
            signal.portfolio_fit, "❓"
        )
        fields.append({
            "name": "📦 Portfolio Fit",
            "value": f"{fit_icon} {signal.portfolio_fit}",
            "inline": True,
        })

    # ── Approval Flags (v6) ──
    if signal.approval_flags:
        flag_lines = []
        for flag_name, passed in signal.approval_flags.items():
            icon = "✅" if passed else "❌"
            flag_lines.append(f"{icon} {flag_name}")
        fields.append({
            "name": "🔍 Validation Checklist",
            "value": "\n".join(flag_lines),
            "inline": False,
        })

    return {
        "title": f"{arrow}  {signal.ticker}  —  ${signal.entry_price:.2f}",
        "description": signal.entry_logic or "",
        "color": color,
        "fields": fields,
        "footer": f"TradingAI Pro v6 • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    }


# ─────────────────────────────────────────────────────────────────────
# 2. Regime Snapshot (for /market_now)
# ─────────────────────────────────────────────────────────────────────

def build_regime_snapshot(
    scoreboard: RegimeScoreboard,
    delta: Optional[DeltaSnapshot] = None,
    bullish_changes: Optional[List[ChangeItem]] = None,
    bearish_changes: Optional[List[ChangeItem]] = None,
    flows: Optional[FlowsPositioning] = None,
) -> Dict[str, Any]:
    """
    Build a regime-snapshot dict for /market_now.

    Returns dict with keys:
        title, description, color, sections[]
    Each section = {name, value, inline}
    """
    sb = scoreboard
    color = _regime_color(sb.regime_label)
    now_ts = datetime.now(timezone.utc)

    sections: List[Dict[str, Any]] = []

    # ── Section 1: Regime + Risk Score ──
    sections.append({
        "name": "📊 Regime",
        "value": (
            f"**{sb.regime_label}** • Risk-On Score: **{sb.risk_on_score:.0f}/100**\n"
            f"Trend: **{sb.trend_state}** | Vol: **{sb.vol_state}**"
        ),
        "inline": False,
    })

    # ── Section 2: Risk Budget ──
    sections.append({
        "name": "💰 Risk Budget",
        "value": (
            f"Max Gross: **{sb.max_gross_pct:.0f}%** | "
            f"Net Long: **{sb.net_long_target_low:.0f}-{sb.net_long_target_high:.0f}%**\n"
            f"Max Single Name: **{sb.max_single_name_pct:.0f}%** | "
            f"Max Sector: **{sb.max_sector_pct:.0f}%**"
        ),
        "inline": False,
    })

    # ── Section 3: Strategy Playbook ──
    on_str = " · ".join(f"`{s}`" for s in sb.strategies_on) if sb.strategies_on else "—"
    cond_strs = []
    for c in sb.strategies_conditional:
        name = c.get("strategy", "?")
        cond = c.get("condition", "?")
        cond_strs.append(f"`{name}` if {cond}")
    cond_str = "\n".join(cond_strs) if cond_strs else "—"
    off_str = " · ".join(f"~~{s}~~" for s in sb.strategies_off) if sb.strategies_off else "—"
    sections.append({
        "name": "📋 Strategy Playbook",
        "value": f"🟢 ON: {on_str}\n🟡 CONDITIONAL:\n{cond_str}\n🔴 OFF: {off_str}",
        "inline": False,
    })

    # ── Section 4: What Changed (delta) ──
    if bullish_changes or bearish_changes:
        change_lines = []
        for ch in (bullish_changes or [])[:3]:
            change_lines.append(f"📈 {ch.description}")
        for ch in (bearish_changes or [])[:3]:
            change_lines.append(f"📉 {ch.description}")
        if change_lines:
            sections.append({
                "name": "🔄 What Changed",
                "value": "\n".join(change_lines),
                "inline": False,
            })

    # ── Section 5: Delta numbers ──
    if delta:
        delta_lines = []
        if delta.spx_1d_pct is not None:
            delta_lines.append(f"SPX: **{delta.spx_1d_pct:+.2f}%** (5d: {delta.spx_5d_pct or 0:+.2f}%)")
        if delta.ndx_1d_pct is not None:
            delta_lines.append(f"NDX: **{delta.ndx_1d_pct:+.2f}%** (5d: {delta.ndx_5d_pct or 0:+.2f}%)")
        if delta.vix_close is not None:
            delta_lines.append(
                f"VIX: **{delta.vix_close:.1f}** "
                f"({'🔴' if (delta.vix_close or 0) > 25 else '🟡' if (delta.vix_close or 0) > 18 else '🟢'}) "
                f"Δ1d: {delta.vix_1d_change or 0:+.1f}"
            )
        if delta.yield_10y is not None:
            delta_lines.append(f"10Y: **{delta.yield_10y:.2f}%** (Δ1d: {delta.yield_10y_1d_bp or 0:+.0f}bp)")
        if delta.pct_above_50dma is not None:
            delta_lines.append(f"Breadth (>50d): **{delta.pct_above_50dma:.0f}%** Δ{delta.pct_above_50dma_1d_change or 0:+.1f}%")
        if delta_lines:
            sections.append({
                "name": "📐 Delta Deck",
                "value": "\n".join(delta_lines),
                "inline": False,
            })

    # ── Section 6: Flows & Positioning ──
    if flows:
        flow_lines = []
        if flows.put_call_ratio is not None:
            flow_lines.append(f"P/C Ratio: **{flows.put_call_ratio:.2f}** ({flows.put_call_trend or '—'})")
        if flows.iv_rank_spy is not None:
            flow_lines.append(f"IV Rank (SPY): **{flows.iv_rank_spy:.0f}** | IV vs RV: {flows.iv_vs_rv or '—'}")
        if flows.gamma_zone:
            flow_lines.append(f"Gamma: **{flows.gamma_zone}**")
        if flows.crowding_flags:
            flow_lines.append(f"⚠️ Crowding: {', '.join(flows.crowding_flags[:3])}")
        if flow_lines:
            sections.append({
                "name": "🌊 Flows & Positioning",
                "value": "\n".join(flow_lines),
                "inline": False,
            })

    # ── Section 7: Scenarios ──
    if sb.scenarios:
        sp = sb.scenarios
        scenario_lines = []
        if sp.base_case:
            scenario_lines.append(
                f"**Base** ({sp.base_case.get('probability', '?')}): "
                f"{sp.base_case.get('description', '—')}"
            )
        if sp.bull_case:
            scenario_lines.append(
                f"**Bull** ({sp.bull_case.get('probability', '?')}): "
                f"{sp.bull_case.get('description', '—')}"
            )
        if sp.bear_case:
            scenario_lines.append(
                f"**Bear** ({sp.bear_case.get('probability', '?')}): "
                f"{sp.bear_case.get('description', '—')}"
            )
        if scenario_lines:
            sections.append({
                "name": "🗺️ Scenario Map",
                "value": "\n".join(scenario_lines),
                "inline": False,
            })

    # ── Section 8: Top Drivers ──
    if sb.top_drivers:
        sections.append({
            "name": "🔑 Top Drivers",
            "value": "\n".join(f"• {d}" for d in sb.top_drivers[:5]),
            "inline": False,
        })

    # ── Section 9: No-Trade Triggers ──
    if sb.no_trade_triggers:
        sections.append({
            "name": "🚫 No-Trade Triggers",
            "value": "\n".join(f"🔴 {t}" for t in sb.no_trade_triggers),
            "inline": False,
        })

    return {
        "title": f"🎛️ Market Now — {now_ts.strftime('%H:%M UTC')}",
        "description": (
            f"**{sb.regime_label}** • Risk-On: {sb.risk_on_score:.0f}/100 • "
            f"Trend: {sb.trend_state} • Vol: {sb.vol_state}"
        ),
        "color": color,
        "sections": sections,
        "footer": f"TradingAI Pro v6 • {now_ts.strftime('%Y-%m-%d %H:%M UTC')}",
    }


# ─────────────────────────────────────────────────────────────────────
# 3. Morning Decision Memo (v6)
# ─────────────────────────────────────────────────────────────────────

def build_morning_memo(
    scoreboard: RegimeScoreboard,
    delta: Optional[DeltaSnapshot] = None,
    bullish_changes: Optional[List[ChangeItem]] = None,
    bearish_changes: Optional[List[ChangeItem]] = None,
    flows: Optional[FlowsPositioning] = None,
    top_signals: Optional[List[Signal]] = None,
    market_prices: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """
    Build the v6 Morning Decision Memo as a list of embed dicts.

    Returns list of embed dicts (typically 2-3 embeds):
      [0] Main memo  (regime, delta, playbook, risk)
      [1] Top 5 trade ideas  (optional)
      [2] Scenario map  (optional)
    """
    sb = scoreboard
    prices = market_prices or {}
    now_ts = datetime.now(timezone.utc)
    color = _regime_color(sb.regime_label)
    embeds: List[Dict[str, Any]] = []

    # ═══ EMBED 1: Main Memo ═══
    fields: List[Dict[str, Any]] = []

    # ── Regime ──
    fields.append({
        "name": "📊 Regime Scoreboard",
        "value": (
            f"**{sb.regime_label}** • Risk-On: **{sb.risk_on_score:.0f}/100**\n"
            f"Trend: **{sb.trend_state}** | Vol: **{sb.vol_state}**\n"
            f"Max Gross: {sb.max_gross_pct:.0f}% | "
            f"Net Long: {sb.net_long_target_low:.0f}-{sb.net_long_target_high:.0f}%"
        ),
        "inline": False,
    })

    # ── What Changed ──
    change_lines = []
    for ch in (bullish_changes or [])[:4]:
        sev_icon = {"critical": "🔴", "warning": "⚠️"}.get(ch.severity, "📈")
        change_lines.append(f"{sev_icon} {ch.description}")
    for ch in (bearish_changes or [])[:4]:
        sev_icon = {"critical": "🔴", "warning": "⚠️"}.get(ch.severity, "📉")
        change_lines.append(f"{sev_icon} {ch.description}")
    if not change_lines:
        change_lines.append("No major overnight changes — quiet open expected")
    fields.append({
        "name": "🔄 What Changed",
        "value": "\n".join(change_lines[:8]),
        "inline": False,
    })

    # ── Delta Deck (compact) ──
    if delta:
        delta_parts = []
        if delta.spx_1d_pct is not None:
            delta_parts.append(f"SPX {delta.spx_1d_pct:+.2f}%")
        if delta.ndx_1d_pct is not None:
            delta_parts.append(f"NDX {delta.ndx_1d_pct:+.2f}%")
        if delta.iwm_1d_pct is not None:
            delta_parts.append(f"IWM {delta.iwm_1d_pct:+.2f}%")
        if delta.vix_close is not None:
            delta_parts.append(f"VIX {delta.vix_close:.1f}")
        if delta.yield_10y is not None:
            delta_parts.append(f"10Y {delta.yield_10y:.2f}%")
        if delta_parts:
            fields.append({
                "name": "📐 Delta Snapshot",
                "value": " | ".join(delta_parts),
                "inline": False,
            })

    # ── Breadth ──
    if delta and delta.pct_above_50dma is not None:
        breadth_icon = "🟢" if (delta.pct_above_50dma or 0) > 60 else "🔴" if (delta.pct_above_50dma or 0) < 40 else "🟡"
        breadth_text = (
            f"{breadth_icon} >50d: **{delta.pct_above_50dma:.0f}%** "
            f"(Δ{delta.pct_above_50dma_1d_change or 0:+.1f}%)"
        )
        if delta.new_highs is not None and delta.new_lows is not None:
            breadth_text += f" | H/L: {delta.new_highs}/{delta.new_lows}"
        fields.append({"name": "📐 Breadth", "value": breadth_text, "inline": True})

    # ── Sector Leadership ──
    if delta and (delta.top_3_sectors or delta.bottom_3_sectors):
        top_s = ", ".join(delta.top_3_sectors[:3]) if delta.top_3_sectors else "—"
        bot_s = ", ".join(delta.bottom_3_sectors[:3]) if delta.bottom_3_sectors else "—"
        fields.append({
            "name": "🏭 Sector Leadership",
            "value": f"📈 {top_s}\n📉 {bot_s}",
            "inline": True,
        })

    # ── Flows ──
    if flows:
        flow_parts = []
        if flows.put_call_ratio is not None:
            flow_parts.append(f"P/C: {flows.put_call_ratio:.2f}")
        if flows.iv_rank_spy is not None:
            flow_parts.append(f"IV Rank: {flows.iv_rank_spy:.0f}")
        if flows.gamma_zone:
            flow_parts.append(f"γ: {flows.gamma_zone}")
        if flow_parts:
            fields.append({
                "name": "🌊 Flows",
                "value": " | ".join(flow_parts),
                "inline": True,
            })

    # ── Strategy Playbook ──
    on_str = " · ".join(f"`{s}`" for s in sb.strategies_on) if sb.strategies_on else "—"
    off_str = " · ".join(f"~~{s}~~" for s in sb.strategies_off) if sb.strategies_off else "—"
    playbook_text = f"🟢 **ON:** {on_str}\n🔴 **OFF:** {off_str}"
    for c in sb.strategies_conditional[:3]:
        playbook_text += f"\n🟡 `{c.get('strategy', '?')}` if {c.get('condition', '?')}"
    fields.append({
        "name": "📋 Today's Playbook",
        "value": playbook_text,
        "inline": False,
    })

    # ── Key Levels (from market_prices) ──
    level_lines = []
    for sym, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq"), ("IWM", "Russell")]:
        p = prices.get(sym, {})
        if p:
            price = p.get("price", 0)
            hi = p.get("high", price)
            lo = p.get("low", price)
            pct = p.get("change_pct", 0)
            level_lines.append(f"**{label}**: ${price:.2f} ({pct:+.2f}%) — R: ${hi:.2f} | S: ${lo:.2f}")
    if level_lines:
        fields.append({
            "name": "📐 Key Levels",
            "value": "\n".join(level_lines),
            "inline": False,
        })

    # ── Risk Bulletin ──
    risk_lines = list(sb.no_trade_triggers) if sb.no_trade_triggers else []
    if not risk_lines:
        risk_lines.append("✅ No critical risk flags")
    else:
        risk_lines = [f"🔴 {r}" for r in risk_lines[:5]]
    fields.append({
        "name": "🛡️ Risk Bulletin",
        "value": "\n".join(risk_lines),
        "inline": False,
    })

    # ── Sizing Guidance ──
    regime_lc = sb.regime_label.lower()
    if "risk_off" in regime_lc:
        sizing = "⚠️ **25-50%** of normal • Wider stops • Capital preservation"
    elif "neutral" in regime_lc:
        sizing = "🟡 **75%** of normal • Standard stops • Be selective"
    else:
        sizing = "🟢 **100%** full size • Tight stops • Full offence"
    fields.append({"name": "📏 Sizing Guidance", "value": sizing, "inline": False})

    embeds.append({
        "title": f"☀️ Morning Decision Memo — {now_ts.strftime('%A, %B %d')}",
        "description": (
            f"**{sb.regime_label}** • Risk-On: {sb.risk_on_score:.0f}/100 • "
            f"Trend: {sb.trend_state} • Vol: {sb.vol_state}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "color": color,
        "fields": fields,
        "footer": "☀️ v6 Decision Memo • /market_now for real-time • Good luck!",
    })

    # ═══ EMBED 2: Top 5 Trade Ideas ═══
    if top_signals:
        trade_fields: List[Dict[str, Any]] = []
        for i, sig in enumerate(top_signals[:5], 1):
            direction = getattr(sig.direction, "value", str(sig.direction))
            arrow = "🟢" if direction.upper() in ("LONG", "BUY") else "🔴"
            grade = sig.setup_grade or "?"
            approval = _approval_emoji(sig.approval_status)
            rr = sig.risk_reward_ratio or 0
            ev_str = f"EV: {sig.expected_value:+.1f}%" if sig.expected_value else ""
            time_stop = f"⏳{sig.time_stop_days}d" if sig.time_stop_days else ""
            why = sig.why_now or ""

            value_parts = [
                f"Grade: **{grade}** {approval} | Conf: **{sig.confidence}** | R:R: **{rr:.1f}:1**",
            ]
            if ev_str or time_stop:
                value_parts.append(f"{ev_str} {time_stop}".strip())
            if why:
                value_parts.append(f"💡 {why[:80]}")

            trade_fields.append({
                "name": f"{arrow} #{i} {sig.ticker} — ${sig.entry_price:.2f}",
                "value": "\n".join(value_parts),
                "inline": False,
            })

        embeds.append({
            "title": "🎯 Top 5 Trade Ideas",
            "description": "Pre-market scan • sorted by conviction • v6 edge scoring",
            "color": 0x2979FF,
            "fields": trade_fields,
            "footer": "/signals for full list • Use buttons for deep-dive",
        })

    # ═══ EMBED 3: Scenario Map (if available) ═══
    if sb.scenarios:
        sp = sb.scenarios
        scenario_fields: List[Dict[str, Any]] = []
        for label, case, emoji in [
            ("Base Case", sp.base_case, "📊"),
            ("Bull Case", sp.bull_case, "🐂"),
            ("Bear Case", sp.bear_case, "🐻"),
        ]:
            if case:
                prob = case.get("probability", "?")
                desc = case.get("description", "—")
                trigger = case.get("trigger", "")
                value = f"**{prob}** — {desc}"
                if trigger:
                    value += f"\n→ Trigger: _{trigger}_"
                scenario_fields.append({"name": f"{emoji} {label}", "value": value, "inline": False})

        if sp.triggers:
            scenario_fields.append({
                "name": "⚡ Key Triggers to Watch",
                "value": "\n".join(f"• {t}" for t in sp.triggers[:5]),
                "inline": False,
            })

        if scenario_fields:
            embeds.append({
                "title": "🗺️ Scenario Map",
                "description": "If/then framework for today's session",
                "color": 0x7C4DFF,
                "fields": scenario_fields,
                "footer": "Scenarios update intraday as data changes",
            })

    return embeds


# ─────────────────────────────────────────────────────────────────────
# 4. EOD Scorecard (v6)
# ─────────────────────────────────────────────────────────────────────

def build_eod_scorecard(
    scoreboard: RegimeScoreboard,
    delta: Optional[DeltaSnapshot] = None,
    signals_today: Optional[List[Signal]] = None,
    market_prices: Optional[Dict[str, Dict[str, float]]] = None,
    sector_data: Optional[List[Tuple[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """
    Build v6 EOD Scorecard.

    Returns list of embed dicts (1-2 embeds).
    """
    sb = scoreboard
    prices = market_prices or {}
    now_ts = datetime.now(timezone.utc)
    embeds: List[Dict[str, Any]] = []

    fields: List[Dict[str, Any]] = []

    # ── Regime close ──
    fields.append({
        "name": "📊 Regime at Close",
        "value": (
            f"**{sb.regime_label}** • Risk-On: {sb.risk_on_score:.0f}/100\n"
            f"Trend: {sb.trend_state} | Vol: {sb.vol_state}"
        ),
        "inline": False,
    })

    # ── Index performance ──
    index_lines = []
    for sym, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq"), ("IWM", "Russell"), ("DIA", "Dow")]:
        p = prices.get(sym, {})
        if p:
            pct = p.get("change_pct", 0)
            index_lines.append(f"{_pct_bar(pct, 6)} **{label}** ${p.get('price', 0):.2f}")
    if index_lines:
        fields.append({
            "name": "📈 Index Performance",
            "value": "\n".join(index_lines),
            "inline": False,
        })

    # ── Sector heat map ──
    if sector_data:
        sector_data_sorted = sorted(sector_data, key=lambda x: x[1], reverse=True)
        heat_lines = []
        for name, pct in sector_data_sorted[:8]:
            icon = "🟢" if pct > 0.5 else "🔴" if pct < -0.5 else "⚪"
            heat_lines.append(f"{icon} {name}: {pct:+.2f}%")
        fields.append({
            "name": "🏭 Sector Heat Map",
            "value": "\n".join(heat_lines),
            "inline": False,
        })

    # ── Delta summary ──
    if delta:
        delta_parts = []
        if delta.vix_close is not None:
            delta_parts.append(f"VIX: {delta.vix_close:.1f} (Δ{delta.vix_1d_change or 0:+.1f})")
        if delta.pct_above_50dma is not None:
            delta_parts.append(f">50d: {delta.pct_above_50dma:.0f}%")
        if delta.new_highs is not None and delta.new_lows is not None:
            delta_parts.append(f"H/L: {delta.new_highs}/{delta.new_lows}")
        if delta_parts:
            fields.append({
                "name": "📐 Breadth & Vol",
                "value": " | ".join(delta_parts),
                "inline": False,
            })

    # ── Signal performance ──
    if signals_today:
        approved = [s for s in signals_today if s.approval_status == "approved"]
        conditional = [s for s in signals_today if s.approval_status == "conditional"]
        rejected = [s for s in signals_today if s.approval_status == "rejected"]
        fields.append({
            "name": "🎯 Signal Summary",
            "value": (
                f"Total: **{len(signals_today)}** | "
                f"✅ Approved: **{len(approved)}** | "
                f"🟡 Conditional: **{len(conditional)}** | "
                f"❌ Rejected: **{len(rejected)}**"
            ),
            "inline": False,
        })

        # Top signals by grade
        top = sorted(
            [s for s in signals_today if s.approval_status != "rejected"],
            key=lambda s: s.confidence or 0,
            reverse=True,
        )[:3]
        if top:
            top_lines = []
            for s in top:
                direction = getattr(s.direction, "value", str(s.direction))
                arrow = "🟢" if direction.upper() in ("LONG", "BUY") else "🔴"
                top_lines.append(
                    f"{arrow} **{s.ticker}** {s.setup_grade or '?'} "
                    f"Conf:{s.confidence} R:R:{s.risk_reward_ratio or 0:.1f}"
                )
            fields.append({
                "name": "🏆 Top Signals",
                "value": "\n".join(top_lines),
                "inline": False,
            })

    # ── Tomorrow outlook ──
    regime_lc = sb.regime_label.lower()
    if "risk_on" in regime_lc:
        outlook = "🟢 Constructive — continue with full book tomorrow"
    elif "risk_off" in regime_lc:
        outlook = "🔴 Defensive — reduce exposure, wider stops"
    else:
        outlook = "🟡 Mixed — be selective, manage position sizes"
    fields.append({"name": "🔮 Tomorrow Outlook", "value": outlook, "inline": False})

    embeds.append({
        "title": f"🌙 End-of-Day Scorecard — {now_ts.strftime('%A, %B %d')}",
        "description": "Markets closed. Here's your daily performance review.",
        "color": 0x7C4DFF,
        "fields": fields,
        "footer": f"TradingAI Pro v6 • {now_ts.strftime('%Y-%m-%d %H:%M UTC')}",
    })

    return embeds


# ─────────────────────────────────────────────────────────────────────
# 5. Markdown export (for docs / notifications / email)
# ─────────────────────────────────────────────────────────────────────

def embeds_to_markdown(embeds: List[Dict[str, Any]]) -> str:
    """Convert a list of embed dicts to a Markdown string."""
    parts: List[str] = []
    for embed in embeds:
        parts.append(f"# {embed.get('title', '')}\n")
        desc = embed.get("description", "")
        if desc:
            parts.append(f"{desc}\n")
        for field in embed.get("fields", embed.get("sections", [])):
            parts.append(f"### {field['name']}\n{field['value']}\n")
        footer = embed.get("footer", "")
        if footer:
            parts.append(f"---\n_{footer}_\n")
    return "\n".join(parts)
