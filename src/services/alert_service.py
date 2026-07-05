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

import asyncio
import json
import logging
import os
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


def _push_discord(title: str, message: str, severity: str = "info") -> bool:
    """Fire-and-forget Discord push.  Returns True if dispatched."""
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "") or os.getenv(
        "DISCORD_ALERT_WEBHOOK", ""
    )
    if not webhook:
        return False
    try:
        from src.notifications.discord_bot import DiscordInteractiveBot

        bot = DiscordInteractiveBot()
        if not bot.is_configured():
            return False
        color = _SEVERITY_COLOR.get(severity, 0x5865F2)
        emoji = _SEVERITY_EMOJI.get(severity, "ℹ️")

        async def _send():
            await bot.push_alert(
                title=f"{emoji} {title}",
                message=message,
                color=color,
            )
            await bot.close()

        # Run in a new event loop if there's no running loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_send())
            else:
                loop.run_until_complete(_send())
        except RuntimeError:
            asyncio.run(_send())
        return True
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
        f"• {a.get('strategy','?')} / {a.get('regime','?')} — "
        f"win_rate={a.get('win_rate',0):.1%}"
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
    message = f"Market regime shifted.  VIX: {vix:.1f}"
    severity = "warning" if new_regime in ("BEAR", "CHOPPY") else "info"
    event = _make_event(
        "regime_change",
        title,
        message,
        severity=severity,
        meta={"old": old_regime, "new": new_regime, "vix": vix},
    )
    _append_log(event)
    logger.info("[ALERT] %s", title)
    return _push_discord(title, message, severity)


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
    title = "⚡ Circuit Breaker Triggered"
    message = reason
    event = _make_event(
        "circuit_breaker", title, message, severity="critical", meta={"reason": reason}
    )
    _append_log(event)
    logger.error("[ALERT] %s | %s", title, message)
    return _push_discord(title, message, "critical")


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
        best = engine.recommend_best_arm()
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
