"""Telegram fan-out for AlertService system events (deploy gate, BDR, trade gate, regime)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.notifications.telegram import (
    dedupe_blocked_for_alert,
    escape_html,
    format_alert_timestamp,
    format_brand_footer,
    format_brand_header,
    format_cc_dashboard_link,
    send_message,
    telegram_is_configured,
)

logger = logging.getLogger("system_telegram")

_SEVERITY_BADGE = {
    "critical": "🔴 CRITICAL",
    "warning": "🟡 WARNING",
    "info": "🔵 INFO",
    "ok": "🟢 OK",
}


def _system_notify_enabled() -> bool:
    return os.getenv("TELEGRAM_NOTIFY_SYSTEM", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def _format_system_message(
    *,
    event_type: str,
    title: str,
    message: str,
    severity: str = "info",
    zh_summary: Optional[str] = None,
    footer_extra: str = "",
) -> str:
    badge = _SEVERITY_BADGE.get(severity, "🔵 INFO")
    lines = [
        format_brand_header(),
        "━━━━━━━━━━━━━━━━━━━━",
        f"<b>{escape_html(badge)} · {escape_html(title)}</b>",
        "",
    ]
    for para in str(message or "").split("\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("•"):
            lines.append(f"• {escape_html(para[1:].strip())}")
        else:
            lines.append(escape_html(para))
    if zh_summary:
        lines.extend(["", f"繁中 · {escape_html(zh_summary)}"])
    lines.append(format_alert_timestamp())
    dash = format_cc_dashboard_link()
    if dash:
        lines.append(f'🔗 <a href="{escape_html(dash)}">Open CC · 開啟 CC</a>')
    if not footer_extra:
        footer_extra = "System signal only — confirm in CC Ops before acting · 請於 CC 確認後再操作"
    lines.extend(["", format_brand_footer(extra=footer_extra)])
    return "\n".join(lines)


def push_system_alert(
    *,
    event_type: str,
    title: str,
    message: str,
    severity: str = "info",
    zh_summary: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    dedupe_key: str = "",
    footer_extra: str = "",
) -> bool:
    """Push a bilingual system alert to Telegram (non-fatal)."""
    if not telegram_is_configured() or not _system_notify_enabled():
        return False
    key = dedupe_key or event_type
    if dedupe_blocked_for_alert(event_type, key, severity):
        return False
    text = _format_system_message(
        event_type=event_type,
        title=title,
        message=message,
        severity=severity,
        zh_summary=zh_summary,
        footer_extra=footer_extra,
    )
    ok = send_message(text)
    if ok:
        logger.info("Telegram system alert sent: %s — %s", event_type, title)
    return ok


def push_deploy_gate_change(
    *,
    unlocked: bool,
    summary: str = "",
    tradeability: str = "",
    remaining: Optional[List[str]] = None,
) -> bool:
    rem = remaining or []
    if unlocked:
        title = "Deploy Gate UNLOCKED · 部署閘門解鎖"
        message = summary or "All four unlock_deploy conditions met."
        zh = "部署閘門已解鎖 — 四項條件齊備。送出前仍須確認 size 同 bracket。"
        severity = "ok"
        footer = "Human approval required before orders · 下單前需人工確認"
    else:
        title = "Deploy Gate LOCKED · 部署閘門鎖定"
        message = summary or "Deploy gate not cleared."
        if rem:
            message += "\n" + "\n".join(f"• {r}" for r in rem[:4])
        zh = "部署閘門已鎖 — 請完成 unlock checklist 後再 handoff。"
        severity = "warning"
        footer = "Complete unlock checklist in CC · 請於 CC 完成解鎖清單"
    if tradeability:
        message = f"Tradeability: {tradeability}\n{message}"
    return push_system_alert(
        event_type="deploy_gate_change",
        title=title,
        message=message,
        severity=severity,
        zh_summary=zh,
        dedupe_key=f"{'unlocked' if unlocked else 'locked'}",
        footer_extra=footer,
    )


def push_bdr_decision_change(
    old_code: str,
    new_code: str,
    decision_line: str = "",
) -> bool:
    title = f"BDR Decision: {old_code} → {new_code}"
    message = decision_line or f"Board decision review shifted to {new_code}."
    zh = f"BDR 決策由 {old_code} 轉為 {new_code} — 請查 Today 面板。"
    severity = "ok" if new_code == "DEPLOY" else "info"
    if new_code == "NO_TRADE":
        severity = "warning"
    return push_system_alert(
        event_type="bdr_decision_change",
        title=title,
        message=message,
        severity=severity,
        zh_summary=zh,
        dedupe_key=f"{old_code}_{new_code}",
        footer_extra="BDR advisory — not an order · BDR 僅供參考，非下單指令",
    )


def push_trade_gate_blocked(hard_blocks: List[str]) -> bool:
    if not hard_blocks:
        return False
    title = "Trade Gate BLOCKED · 引擎阻擋"
    message = "Portfolio trade gate blocked new executions:\n" + "\n".join(
        f"• {b}" for b in hard_blocks[:5]
    )
    zh = "引擎 TradeGate 阻擋新 execution — 持倉監控仍運行。"
    return push_system_alert(
        event_type="trade_gate_blocked",
        title=title,
        message=message,
        severity="warning",
        zh_summary=zh,
        dedupe_key=hard_blocks[0][:40],
        footer_extra="Executions paused — monitor positions in CC · 新單暫停，持倉監控繼續",
    )


def push_trade_gate_cleared(soft_warnings: Optional[List[str]] = None) -> bool:
    title = "Trade Gate CLEARED · 引擎放行"
    message = "Portfolio trade gate allows new executions again."
    warns = soft_warnings or []
    if warns:
        message += "\n" + "\n".join(f"• {w}" for w in warns[:3])
    zh = "引擎 TradeGate 已清 — 仍受 deploy authority 同 Playbook 閘門約束。"
    return push_system_alert(
        event_type="trade_gate_cleared",
        title=title,
        message=message,
        severity="ok",
        zh_summary=zh,
        dedupe_key="cleared",
        footer_extra="Subject to deploy authority & playbook gates · 仍受部署閘門約束",
    )


def push_regime_change(old_regime: str, new_regime: str, vix: float = 0.0) -> bool:
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
    return push_system_alert(
        event_type="regime_change",
        title=title,
        message=message,
        severity=severity,
        zh_summary=zh,
        dedupe_key=f"{old_regime}_{new_regime}",
        footer_extra="Refresh playbook — rank ≠ permission · 刷新看板，排名≠許可",
    )


def push_circuit_breaker(reason: str) -> bool:
    title = "Circuit Breaker Triggered · 熔斷觸發"
    message = f"{reason}\n\nNew executions blocked — confirm in Ops before resuming."
    zh = f"熔斷已觸發：{reason}。新 execution 已阻 — 請於 Ops 確認後再繼續。"
    return push_system_alert(
        event_type="circuit_breaker",
        title=title,
        message=message,
        severity="critical",
        zh_summary=zh,
        dedupe_key=reason[:48],
        footer_extra="All new executions blocked · 新 execution 全部暫停",
    )
