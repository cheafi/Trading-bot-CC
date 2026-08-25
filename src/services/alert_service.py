"""
AlertService v2 — Sprint 106
=============================
Typed event dispatchers that bridge the intelligence engines to Discord
push notifications.  All methods are non-fatal: if Discord is not configured
or the network is unavailable the call logs a warning and returns False.

Event types
-----------
  on_ic_decay_alert(alerts)        — FeatureICDecayDetector decay warnings
  on_thompson_arm_degrade(arms)    — Thompson arms with win_rate < WIN_RATE_FLOOR
  on_fund_rebalance(fund, regime, old_candidates, new_candidates)
  on_regime_change(old, new, vix)  — RegimeRouter transition
  on_drawdown_breach(fund, dd_pct, limit_pct)
  on_circuit_breaker(reason)       — Hard circuit-breaker triggered

The last MAX_LOG events are persisted to ``models/alert_log.json`` so the
REST layer can surface them without a live Discord session.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alert_service")

# ── Configuration ─────────────────────────────────────────────────────────────
_LOG_PATH = Path("models/alert_log.json")
MAX_LOG = 50
WIN_RATE_FLOOR = 0.40  # Thompson arms below this trigger degrade alert
DD_BREACH_DEFAULT_LIMIT = 10.0  # % drawdown that triggers a breach alert by default


# ── Severity → Discord embed colour ──────────────────────────────────────────
_SEVERITY_COLOR = {
    "critical": 0xFF4444,  # red
    "warning": 0xFF8C00,  # orange
    "info": 0x5865F2,  # discord blurple
    "ok": 0x00FF88,  # green
}

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
    "ok": "🟢",
}


# ── Log helpers ───────────────────────────────────────────────────────────────


def _load_log() -> List[Dict[str, Any]]:
    try:
        if _LOG_PATH.exists():
            return json.loads(_LOG_PATH.read_text())
    except Exception:
        pass
    return []


def _append_log(event: Dict[str, Any]) -> None:
    log = _load_log()
    log.append(event)
    log = log[-MAX_LOG:]  # keep tail
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOG_PATH.write_text(json.dumps(log, indent=2))
    except Exception as exc:
        logger.warning("alert_log write failed: %s", exc)


def _make_event(
    event_type: str,
    title: str,
    message: str,
    severity: str = "info",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "title": title,
        "message": message,
        "severity": severity,
        "meta": meta or {},
    }


# ── Discord push helper ───────────────────────────────────────────────────────


def _push_discord(
    title: str,
    message: str,
    severity: str = "info",
    *,
    event_type: str = "alert_service",
    meta: Optional[Dict[str, Any]] = None,
    zh_summary: Optional[str] = None,
    log: bool = False,
) -> bool:
    """Fire-and-forget Discord push. Returns True if dispatched."""
    try:
        from src.notifications.discord_dispatch import push_notice

        return push_notice(
            title=title,
            message=message,
            severity=severity,
            event_type=event_type,
            meta=meta,
            log=log,
            zh_summary=zh_summary,
        )
    except Exception as exc:
        logger.warning("Discord push failed: %s", exc)
        return False


# ── Public API ────────────────────────────────────────────────────────────────


def on_ic_decay_alert(alerts: List[str]) -> bool:
    """Push a Feature IC decay alert.

    Parameters
    ----------
    alerts : list of feature names that triggered a decay warning.
    """
    if not alerts:
        return False
    title = f"Feature IC Decay — {len(alerts)} feature(s)"
    message = "Predictive power dropping below historical peak:\n" + "\n".join(
        f"• {a}" for a in alerts
    )
    event = _make_event(
        "ic_decay", title, message, severity="warning", meta={"features": alerts}
    )
    _append_log(event)
    logger.warning("[ALERT] %s | %s", title, message)
    return _push_discord(title, message, "warning")


def on_thompson_arm_degrade(arms: List[Dict[str, Any]]) -> bool:
    """Push a Thompson arm degradation alert.

    Parameters
    ----------
    arms : list of arm dicts with keys ``strategy``, ``regime``, ``win_rate``.
           Only arms with ``win_rate < WIN_RATE_FLOOR`` are considered.
    """
    degraded = [a for a in arms if (a.get("win_rate") or 0) < WIN_RATE_FLOOR]
    if not degraded:
        return False
    title = f"Thompson Arm Degrade — {len(degraded)} arm(s) below {WIN_RATE_FLOOR:.0%}"
    lines = [
        f"• {a.get('strategy', '?')} / {a.get('regime', '?')} — "
        f"win_rate={a.get('win_rate', 0):.1%}"
        for a in degraded
    ]
    message = "\n".join(lines)
    event = _make_event(
        "thompson_degrade", title, message, severity="warning", meta={"arms": degraded}
    )
    _append_log(event)
    logger.warning("[ALERT] %s | %s", title, message)
    return _push_discord(title, message, "warning")


def on_fund_rebalance(
    fund: str,
    regime: str,
    old_candidates: List[str],
    new_candidates: List[str],
) -> bool:
    """Push a fund sleeve rebalance notification when regime tilt changes."""
    if set(old_candidates) == set(new_candidates):
        return False
    added = sorted(set(new_candidates) - set(old_candidates))
    removed = sorted(set(old_candidates) - set(new_candidates))
    title = f"Fund Rebalance — {fund} | Regime: {regime}"
    parts = []
    if added:
        parts.append("Added: " + ", ".join(added))
    if removed:
        parts.append("Removed: " + ", ".join(removed))
    message = "\n".join(parts)
    event = _make_event(
        "fund_rebalance",
        title,
        message,
        severity="info",
        meta={"fund": fund, "regime": regime, "added": added, "removed": removed},
    )
    _append_log(event)
    logger.info("[ALERT] %s | %s", title, message)
    return _push_discord(title, message, "info")


def on_regime_change(old_regime: str, new_regime: str, vix: float = 0.0) -> bool:
    """Push a regime transition alert."""
    if old_regime == new_regime:
        return False
    title = f"Regime Change: {old_regime} → {new_regime}"
    message = (
        f"Market regime shifted.\n"
        f"VIX: {vix:.1f}\n"
        f"Next: refresh Dashboard + Playbook — ranking ≠ deploy permission."
    )
    zh = (
        f"市場體制由 {old_regime} 轉為 {new_regime}。"
        f"VIX {vix:.1f}。"
        f"請刷新 Dashboard／Playbook — 排序不等於 deploy 許可。"
    )
    severity = "warning" if new_regime in ("BEAR", "CHOPPY") else "info"
    event = _make_event(
        "regime_change",
        title,
        message,
        severity=severity,
        meta={"old": old_regime, "new": new_regime, "vix": vix, "zh_summary": zh},
    )
    _append_log(event)
    logger.info("[ALERT] %s", title)
    return _push_discord(title, message, severity, zh_summary=zh)


def on_drawdown_breach(
    fund: str,
    dd_pct: float,
    limit_pct: float = DD_BREACH_DEFAULT_LIMIT,
) -> bool:
    """Push a drawdown limit breach alert."""
    if abs(dd_pct) < limit_pct:
        return False
    title = f"Drawdown Breach — {fund}"
    message = f"Current drawdown {dd_pct:.1f}% exceeds limit {limit_pct:.1f}%."
    event = _make_event(
        "drawdown_breach",
        title,
        message,
        severity="critical",
        meta={"fund": fund, "dd_pct": dd_pct, "limit_pct": limit_pct},
    )
    _append_log(event)
    logger.error("[ALERT] %s | %s", title, message)
    return _push_discord(title, message, "critical")


def on_circuit_breaker(reason: str) -> bool:
    """Push a hard circuit-breaker triggered alert."""
    title = "Circuit Breaker Triggered"
    message = f"{reason}\n\nNew executions blocked — confirm in Ops before resuming."
    zh = f"熔斷已觸發：{reason}。新 execution 已阻 — 請於 Ops 確認後再繼續。"
    event = _make_event(
        "circuit_breaker",
        title,
        message,
        severity="critical",
        meta={"reason": reason, "zh_summary": zh},
    )
    _append_log(event)
    logger.error("[ALERT] %s | %s", title, message)
    return _push_discord(title, message, "critical", zh_summary=zh)


def on_deploy_gate_change(
    *,
    unlocked: bool,
    summary: str = "",
    tradeability: str = "",
    remaining: Optional[List[str]] = None,
) -> bool:
    """Notify when unlock_deploy flips locked ↔ unlocked."""
    rem = remaining or []
    if unlocked:
        title = "Deploy Gate UNLOCKED"
        message = summary or "All four unlock_deploy conditions met."
        zh = "部署閘門已解鎖 — 四項條件齊備。送出前仍須確認 size 同 bracket。"
        severity = "ok"
    else:
        title = "Deploy Gate LOCKED"
        message = summary or "Deploy gate not cleared."
        if rem:
            message += "\nRemaining:\n" + "\n".join(f"• {r}" for r in rem[:4])
        zh = "部署閘門已鎖 — 請完成 unlock checklist 後再 handoff。"
        severity = "warning"
    event = _make_event(
        "deploy_gate_change",
        title,
        message,
        severity=severity,
        meta={
            "unlocked": unlocked,
            "tradeability": tradeability,
            "remaining": rem if not unlocked else [],
            "zh_summary": zh,
        },
    )
    _append_log(event)
    logger.info("[ALERT] %s", title)
    return _push_discord(
        title,
        message,
        severity,
        event_type="deploy_gate_change",
        zh_summary=zh,
        log=True,
    )


def on_bdr_decision_change(
    old_code: str,
    new_code: str,
    decision_line: str = "",
) -> bool:
    """Notify when BDR decision_code transitions."""
    if not old_code or not new_code or old_code == new_code:
        return False
    title = f"BDR Decision: {old_code} → {new_code}"
    message = decision_line or f"Board decision review shifted to {new_code}."
    zh = f"BDR 決策由 {old_code} 轉為 {new_code} — 請查 Today 面板。"
    severity = "ok" if new_code == "DEPLOY" else "info"
    if new_code == "NO_TRADE":
        severity = "warning"
    event = _make_event(
        "bdr_decision_change",
        title,
        message,
        severity=severity,
        meta={"old": old_code, "new": new_code, "zh_summary": zh},
    )
    _append_log(event)
    logger.info("[ALERT] %s", title)
    return _push_discord(
        title,
        message,
        severity,
        event_type="bdr_decision_change",
        zh_summary=zh,
        log=True,
    )


def on_trade_gate_blocked(hard_blocks: List[str]) -> bool:
    """Engine TradeGate hard-block — new autonomous executions paused."""
    if not hard_blocks:
        return False
    title = "Trade Gate BLOCKED (engine)"
    message = "Portfolio trade gate blocked new executions:\n" + "\n".join(
        f"• {b}" for b in hard_blocks[:5]
    )
    zh = "引擎 TradeGate 阻擋新 execution — 持倉監控仍運行。"
    event = _make_event(
        "trade_gate_blocked",
        title,
        message,
        severity="warning",
        meta={"hard_blocks": hard_blocks, "zh_summary": zh},
    )
    _append_log(event)
    return _push_discord(
        title,
        message,
        "warning",
        event_type="trade_gate_blocked",
        zh_summary=zh,
        log=True,
    )


def on_trade_gate_cleared(soft_warnings: Optional[List[str]] = None) -> bool:
    """Engine TradeGate cleared — executions may resume (subject to other gates)."""
    title = "Trade Gate CLEARED (engine)"
    message = "Portfolio trade gate allows new executions again."
    if soft_warnings:
        message += "\nSoft warnings:\n" + "\n".join(f"• {w}" for w in soft_warnings[:3])
    zh = "引擎 TradeGate 已清 — 仍受 deploy authority 同 Playbook 閘門約束。"
    event = _make_event(
        "trade_gate_cleared",
        title,
        message,
        severity="ok",
        meta={"soft_warnings": soft_warnings or [], "zh_summary": zh},
    )
    _append_log(event)
    return _push_discord(
        title,
        message,
        "ok",
        event_type="trade_gate_cleared",
        zh_summary=zh,
        log=True,
    )


def check_and_push_ic_decay() -> bool:
    """Read FeatureICDecayDetector status and push any active decay alerts."""
    try:
        from src.engines.feature_ic import get_feature_ic_status

        status = get_feature_ic_status()
        alerts = status.get("alerts", [])
        return on_ic_decay_alert(alerts)
    except Exception as exc:
        logger.warning("check_and_push_ic_decay error: %s", exc)
        return False


def check_and_push_thompson_degrade() -> bool:
    """Read ThompsonSizingEngine and push degrade alerts for weak arms."""
    try:
        from src.engines.thompson_sizing import get_thompson_engine

        engine = get_thompson_engine()
        engine.recommend_best_arm()
        arms = []
        for key, arm in engine._arms.items():
            strategy, regime = key.split("::", 1) if "::" in key else (key, "")
            arms.append(
                {
                    "strategy": strategy,
                    "regime": regime,
                    "win_rate": arm.win_rate,
                    "n_wins": arm.n_wins,
                    "n_losses": arm.n_losses,
                }
            )
        return on_thompson_arm_degrade(arms)
    except Exception as exc:
        logger.warning("check_and_push_thompson_degrade error: %s", exc)
        return False


def get_alert_log(limit: int = MAX_LOG) -> List[Dict[str, Any]]:
    """Return the last ``limit`` alert events from persistent log."""
    log = _load_log()
    return log[-limit:]


def push_overnight_brief_discord(
    *,
    system_state: Optional[Dict[str, Any]] = None,
    today_payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """Generate overnight brief and push to Discord (monitor-only)."""
    try:
        from src.notifications.discord_dispatch import push_notice
        from src.services.vibe_agent import generate_overnight_brief

        brief = generate_overnight_brief(
            system_state=system_state,
            today_payload=today_payload,
        )
        title = str(brief.get("title") or "昨晚重點 · Overnight")
        message = str(brief.get("summary") or "\n".join(brief.get("lines") or []))
        return push_notice(
            title=title,
            message=message,
            severity="info",
            event_type="overnight_brief",
            meta={
                "regime": brief.get("regime"),
                "alert_count": brief.get("alert_count"),
            },
            log=True,
        )
    except Exception as exc:
        logger.warning("push_overnight_brief_discord error: %s", exc)
        return False
