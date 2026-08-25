"""Immediate Telegram alerts for deploy-qualified and high-tier monitor opportunities."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.notifications.telegram import (
    dedupe_blocked_for_alert,
    escape_html,
    format_cc_link,
    send_message,
    telegram_is_configured,
    validate_ticker,
)
from src.services.decision_truth_model import row_passes_trade_bar

logger = logging.getLogger("opportunity_telegram")

_STATE_PATH = os.path.join("data", "artifacts", "telegram_opportunity_state.json")
_STATE_LOCK = threading.Lock()

_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"})
_HIGH_TIERS = frozenset({"A", "HIGH", "High", "STRONG"})


def _state_enabled() -> bool:
    return os.getenv("TELEGRAM_OPPORTUNITY_STATE", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def _notify_deploy() -> bool:
    return os.getenv("TELEGRAM_NOTIFY_DEPLOY", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def _notify_monitor() -> bool:
    return os.getenv("TELEGRAM_NOTIFY_MONITOR", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def _load_state() -> Dict[str, Any]:
    if not _state_enabled():
        return {"tickers": {}}
    try:
        if os.path.isfile(_STATE_PATH):
            with open(_STATE_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
    except Exception as exc:
        logger.debug("telegram opportunity state read failed: %s", exc)
    return {"tickers": {}}


def _save_state(state: Dict[str, Any]) -> None:
    if not _state_enabled():
        return
    try:
        os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(_STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except Exception as exc:
        logger.warning("telegram opportunity state write failed: %s", exc)


def _row_score(row: Dict[str, Any]) -> float:
    for key in ("score", "final_conf", "validated_score"):
        val = row.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def _row_rr(row: Dict[str, Any]) -> Optional[float]:
    raw = row.get("risk_reward") or row.get("rr")
    if raw is None:
        return None
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def _row_tier(row: Dict[str, Any]) -> str:
    for key in ("priority_tier", "score_display", "grade"):
        val = str(row.get(key) or "").strip()
        if val:
            return val
    score = _row_score(row)
    if score >= 8.0:
        return "A"
    if score >= 7.0:
        return "High"
    if score >= 6.0:
        return "Medium"
    return "Low"


def _row_blocker(row: Dict[str, Any]) -> str:
    for key in ("whats_missing", "primary_blocker", "blocker"):
        val = row.get(key)
        if isinstance(val, list):
            val = "; ".join(str(x) for x in val if x)
        if val:
            return str(val)[:240]
    gaps = row.get("gaps") or []
    if gaps:
        return "; ".join(str(g) for g in gaps[:3])[:240]
    trade_bar = row.get("trade_bar") or {}
    missing: List[str] = []
    if trade_bar and not trade_bar.get("passes_trade_bar"):
        if not trade_bar.get("score_ok"):
            missing.append("score below TRADE bar")
        if not trade_bar.get("timing_ok"):
            missing.append("timing not confirmed")
        if not trade_bar.get("thesis_ok"):
            missing.append("thesis incomplete")
        if not trade_bar.get("rr_ok"):
            missing.append("R:R below gate")
        if not trade_bar.get("execution_ready"):
            missing.append("not execution-ready")
    return "; ".join(missing) if missing else "—"


def _alert_kind(row: Dict[str, Any]) -> Optional[str]:
    """Classify row for alerting without loosening deploy authority."""
    if bool(row.get("execution_ready")) and row_passes_trade_bar(row):
        return "deploy"
    act = str(row.get("action") or "").upper()
    if act in _WATCH_ACTIONS or row.get("near_miss_label") in ("watch", "near_miss"):
        score = _row_score(row)
        tier = _row_tier(row)
        if score >= 7.0 or tier in _HIGH_TIERS:
            return "monitor"
    return None


def _snapshot_row(row: Dict[str, Any], *, rank: int) -> Dict[str, Any]:
    ticker = validate_ticker(row.get("ticker") or "")
    kind = _alert_kind(row) or "other"
    return {
        "ticker": ticker or str(row.get("ticker") or "").upper(),
        "kind": kind,
        "score": _row_score(row),
        "tier": _row_tier(row),
        "rank": rank,
        "execution_ready": bool(row.get("execution_ready")),
    }


def _collect_rows(payload: Dict[str, Any]) -> List[Tuple[int, Dict[str, Any]]]:
    rows: List[Tuple[int, Dict[str, Any]]] = []
    for i, row in enumerate(payload.get("opportunities") or [], start=1):
        if isinstance(row, dict):
            rows.append((i, row))
    for i, row in enumerate(payload.get("near_miss") or [], start=1):
        if isinstance(row, dict):
            rows.append((100 + i, row))
    return rows


def current_top_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    opps = payload.get("opportunities") or []
    if not opps or not isinstance(opps[0], dict):
        return None
    return validate_ticker(opps[0].get("ticker") or "")


def _format_message(
    *,
    kind: str,
    ticker: str,
    tier: str,
    score: float,
    rr: Optional[float],
    blocker: str,
    headline: str,
    degraded: bool = False,
) -> str:
    sym = escape_html(ticker)
    if kind == "deploy":
        badge = "🟢 DEPLOY"
        authority = "DEPLOY · 可部署 · Playbook confirmed"
        footer = "Confirm bracket/IBKR in CC before sending orders · 下單前請在 CC 確認"
    else:
        badge = "👀 WATCH / MONITOR"
        authority = "RESEARCH · 監控 · NOT deploy permission · 非部署許可"
        footer = "Monitor only — rank ≠ permission · 僅供監控，排名≠許可"

    rr_text = f"{rr:.1f}" if rr is not None else "—"
    link = format_cc_link(ticker)
    lines = [
        f"<b>{badge} · {sym}</b>",
        escape_html(authority),
        "",
        f"Score: {score:.1f} | Tier: {escape_html(tier)} | R:R {escape_html(rr_text)}",
        f"Blocker: {escape_html(blocker)}",
    ]
    if headline:
        lines.append(f"Note: {escape_html(headline)}")
    if degraded:
        lines.append("⚠️ Degraded board · 降級看板")
    if link:
        lines.append(f'🔗 <a href="{escape_html(link)}">Open in CC · 開啟 CC</a>')
    lines.append("")
    lines.append(escape_html(footer))
    return "\n".join(lines)


def _detect_alerts(
    payload: Dict[str, Any],
    prev: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not prev.get("last_scan_ts"):
        return []

    alerts: List[Dict[str, Any]] = []
    prev_tickers = prev.get("tickers") or {}
    current_top = current_top_from_payload(payload)
    rows = _collect_rows(payload)
    degraded = bool(payload.get("compressed") or payload.get("stale"))

    for rank, row in rows:
        ticker = validate_ticker(row.get("ticker") or "")
        if not ticker:
            continue
        kind = _alert_kind(row)
        if not kind:
            continue
        if kind == "deploy" and not _notify_deploy():
            continue
        if kind == "monitor" and not _notify_monitor():
            continue
        snap = _snapshot_row(row, rank=rank)
        prev_row = prev_tickers.get(ticker) or {}
        prev_kind = prev_row.get("kind")
        prev_score = float(prev_row.get("score") or 0)

        headline = ""
        is_new = ticker not in prev_tickers
        upgraded = (
            prev_kind == "monitor"
            and kind == "deploy"
            or (kind == "monitor" and prev_score and _row_score(row) - prev_score >= 0.5)
        )
        if is_new:
            headline = "New opportunity detected · 新機會"
        elif upgraded:
            headline = "Near-miss upgrade · 監控升級"
        elif (
            current_top == ticker
            and prev.get("top_ticker")
            and prev.get("top_ticker") != current_top
        ):
            headline = "New top-ranked · 新榜首"
        else:
            continue

        if degraded and kind == "deploy":
            continue

        alerts.append(
            {
                "kind": kind,
                "ticker": ticker,
                "tier": snap["tier"],
                "score": snap["score"],
                "rr": _row_rr(row),
                "blocker": _row_blocker(row),
                "headline": headline,
                "degraded": degraded,
            }
        )

    prev_top = prev.get("top_ticker")
    if (
        current_top
        and prev_top
        and current_top != prev_top
        and not any(a.get("headline", "").startswith("New top-ranked") for a in alerts)
    ):
        top_row = next(
            (r for _, r in rows if validate_ticker(r.get("ticker") or "") == current_top),
            None,
        )
        if top_row:
            kind = _alert_kind(top_row)
            if kind and ((kind == "deploy" and _notify_deploy()) or (kind == "monitor" and _notify_monitor())):
                alerts.append(
                    {
                        "kind": kind,
                        "ticker": current_top,
                        "tier": _row_tier(top_row),
                        "score": _row_score(top_row),
                        "rr": _row_rr(top_row),
                        "blocker": _row_blocker(top_row),
                        "headline": "New top-ranked · 新榜首",
                        "degraded": degraded,
                    }
                )

    return alerts


def notify_live_playbook_scan(payload: Dict[str, Any], *, source: str = "playbook") -> Dict[str, Any]:
    """Evaluate ranked playbook payload and push immediate Telegram alerts."""
    result = {
        "configured": telegram_is_configured(),
        "sent": 0,
        "skipped": 0,
        "errors": 0,
        "source": source,
    }
    if not telegram_is_configured():
        return result
    if payload.get("board_mode") == "emergency":
        return result

    with _STATE_LOCK:
        prev = _load_state()
        alerts = _detect_alerts(payload, prev)
        next_state: Dict[str, Any] = {"tickers": {}, "top_ticker": None}
        for rank, row in _collect_rows(payload):
            ticker = validate_ticker(row.get("ticker") or "")
            if not ticker:
                continue
            next_state["tickers"][ticker] = _snapshot_row(row, rank=rank)
        next_state["top_ticker"] = current_top_from_payload(payload)
        next_state["last_scan_ts"] = datetime.now(timezone.utc).isoformat()
        _save_state(next_state)

    for alert in alerts:
        if dedupe_blocked_for_alert(alert["kind"], alert["ticker"], alert["tier"]):
            result["skipped"] += 1
            continue
        text = _format_message(
            kind=alert["kind"],
            ticker=alert["ticker"],
            tier=alert["tier"],
            score=float(alert["score"]),
            rr=alert.get("rr"),
            blocker=str(alert.get("blocker") or "—"),
            headline=str(alert.get("headline") or ""),
            degraded=bool(alert.get("degraded")),
        )
        ok = send_message(text)
        if ok:
            result["sent"] += 1
            logger.info(
                "Telegram opportunity alert sent: %s %s (%s)",
                alert["kind"],
                alert["ticker"],
                source,
            )
        else:
            result["errors"] += 1
    return result
