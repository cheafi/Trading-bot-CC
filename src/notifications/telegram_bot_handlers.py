"""Telegram inbound command handlers for CC Live Intelligence."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.notifications.telegram import (
    _chat_id,
    escape_html,
    format_brand_footer,
    format_brand_header,
    format_cc_dashboard_link,
)

CcGetFn = Callable[[str], Dict[str, Any]]
CcPostFn = Callable[[str], Dict[str, Any]]

RESTRICTED_COMMANDS = frozenset({"/status", "/test"})
KNOWN_COMMANDS = frozenset({"/start", "/status", "/test", "/help"})


def normalize_command(text: str) -> str:
    """Extract slash command without bot suffix."""
    raw = str(text or "").strip()
    if not raw.startswith("/"):
        return ""
    return raw.split()[0].split("@")[0].lower()


def is_restricted_command(command: str) -> bool:
    return command in RESTRICTED_COMMANDS


def is_chat_authorized(chat_id: int | str) -> bool:
    """When TELEGRAM_CHAT_ID is set, only that chat may use /status and /test."""
    allowed = _chat_id()
    if not allowed:
        return True
    return str(chat_id) == allowed


def format_unauthorized_reply() -> str:
    return (
        f"{format_brand_header()}\n\n"
        "<b>Unauthorized · 未授權</b>\n"
        "This command is restricted to the configured alert channel.\n"
        "Send /start to see setup instructions · 請使用 /start 查看設定說明\n\n"
        f"{format_brand_footer()}"
    )


def format_help_reply() -> str:
    return (
        f"{format_brand_header()}\n\n"
        "<b>Commands · 指令</b>\n"
        "/start — Welcome & setup · 歡迎與設定\n"
        "/status — CC deploy gate & channel status · 部署閘門與頻道狀態\n"
        "/test — Send test alert · 測試推播\n"
        "/help — This message · 說明\n\n"
        f"{format_brand_footer()}"
    )


def format_start_welcome(*, chat_id: int | str) -> str:
    """Welcome message for /start — open to any chat."""
    lines = [
        format_brand_header(),
        "",
        "<b>Welcome · 歡迎使用 CC Live Intelligence</b>",
        "",
        "You will receive live alerts when the playbook scan detects:",
        "",
        "🟢 <b>DEPLOY</b> — TRADE-bar qualified, execution-ready setups",
        "   (human approval required before any order · 下單前需人工確認)",
        "",
        "👀 <b>WATCH / MONITOR</b> — high-tier research signals",
        "   (monitor only — not deploy permission · 僅監控，非部署許可)",
        "",
        "Alerts include score, tier, R:R, blockers, and a CC deep link when configured.",
        "",
        "Commands: /status · /test · /help",
    ]
    cc_link = format_cc_dashboard_link()
    if cc_link:
        lines.extend(
            ["", f'🔗 <a href="{escape_html(cc_link)}">Open in CC · 開啟 CC</a>']
        )

    configured_chat = _chat_id()
    if not configured_chat:
        lines.extend(
            [
                "",
                "<b>Setup · 設定</b>",
                f"Your chat ID: <code>{escape_html(str(chat_id))}</code>",
                f"Add <code>TELEGRAM_CHAT_ID={escape_html(str(chat_id))}</code> to .env",
                "Restart the API, then send /test to verify alert delivery.",
                "重啟 API 後使用 /test 驗證推播。",
            ]
        )
    elif str(chat_id) != configured_chat:
        lines.extend(
            [
                "",
                "⚠️ This chat is not the configured alert channel · 非設定之推播頻道",
                f"Configured · 已設定: <code>{escape_html(configured_chat)}</code>",
                f"Your chat · 此聊天: <code>{escape_html(str(chat_id))}</code>",
            ]
        )

    lines.extend(["", format_brand_footer()])
    return "\n".join(lines)


def format_status_reply(
    notify_status: Dict[str, Any],
    decision_board: Optional[Dict[str, Any]] = None,
) -> str:
    """Status summary from notify/status + decision board deploy_open."""
    tg = notify_status.get("telegram") or {}
    board = decision_board or {}
    ss = board.get("system_state") or {}
    deploy_open = board.get("deploy_open")
    tradeability = board.get("tradeability") or ss.get("tradeability") or "—"
    regime = board.get("regime") or {}
    regime_label = regime.get("label") or regime.get("regime") or "—"
    gate_reasons = board.get("gate_reasons") or []
    blocker = ss.get("blocker_compact") or (gate_reasons[0] if gate_reasons else "—")

    lines = [
        format_brand_header(),
        "",
        "<b>CC Live Intelligence · Status · 狀態</b>",
        "",
    ]
    if deploy_open is not None:
        open_label = "OPEN · 開啟" if deploy_open else "CLOSED · 關閉"
        lines.append(f"Deploy gate · 部署閘門: <b>{open_label}</b>")
    lines.extend(
        [
            f"Tradeability · 可交易性: {escape_html(str(tradeability))}",
            f"Regime · 市場型態: {escape_html(str(regime_label))}",
            f"Blocker · 阻擋: {escape_html(str(blocker))}",
            "",
            f"Telegram configured · 已設定: {tg.get('telegram_configured')}",
            f"CC base URL · 連結: {tg.get('cc_base_url_set')}",
        ]
    )
    if notify_status.get("last_alert_ts"):
        lines.append(
            f"Last alert · 上次推播: {escape_html(str(notify_status.get('last_alert_type')))} "
            f"@ {escape_html(str(notify_status.get('last_alert_ts')))}"
        )
    cc_link = format_cc_dashboard_link()
    if cc_link:
        lines.extend(
            ["", f'🔗 <a href="{escape_html(cc_link)}">Open in CC · 開啟 CC</a>']
        )
    lines.extend(["", format_brand_footer()])
    return "\n".join(lines)


def format_test_reply(result: Dict[str, Any]) -> str:
    if result.get("pushed_to_telegram"):
        return (
            f"{format_brand_header()}\n\n"
            "<b>Test alert dispatched · 測試推播已送出</b>\n"
            "Check your configured alert channel for the welcome message.\n"
            "請在設定的推播頻道查看歡迎訊息。\n\n"
            f"{format_brand_footer()}"
        )
    err = result.get("error") or "unknown"
    return (
        f"{format_brand_header()}\n\n"
        f"<b>Test failed · 測試失敗</b>\n{escape_html(str(err))}\n\n"
        f"{format_brand_footer()}"
    )


def format_api_error(reason: str) -> str:
    return (
        f"{format_brand_header()}\n\n"
        f"<b>CC API unreachable · 無法連線 CC API</b>\n"
        f"{escape_html(str(reason))}\n\n"
        f"{format_brand_footer()}"
    )


def handle_telegram_command(
    command: str,
    chat_id: int,
    *,
    cc_get: CcGetFn,
    cc_post: CcPostFn,
) -> str:
    """Return HTML reply for a slash command."""
    cmd = normalize_command(command) if not command.startswith("/") else command.lower()

    if cmd == "/start":
        return format_start_welcome(chat_id=chat_id)

    if cmd == "/help":
        return format_help_reply()

    if is_restricted_command(cmd) and not is_chat_authorized(chat_id):
        return format_unauthorized_reply()

    if cmd == "/status":
        notify_status = cc_get("/api/v7/notify/status")
        decision_board: Optional[Dict[str, Any]] = None
        try:
            decision_board = cc_get("/api/v7/decision/board")
        except Exception:
            decision_board = None
        return format_status_reply(notify_status, decision_board)

    if cmd == "/test":
        result = cc_post("/api/v7/notify/telegram/test")
        return format_test_reply(result)

    return format_help_reply()
