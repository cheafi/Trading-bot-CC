"""Discord notifications for Futu portfolio capture results."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.notifications.discord_dispatch import push_notice_async

logger = logging.getLogger(__name__)


def _holdings_table(holdings: List[Dict[str, Any]], limit: int = 12) -> str:
    lines: List[str] = []
    for h in holdings[:limit]:
        ticker = h.get("ticker", "?")
        shares = h.get("shares", 0)
        cost = h.get("avg_cost", 0)
        price = h.get("current_price")
        pnl = h.get("pnl_pct")
        price_s = f"${price:,.2f}" if price else "—"
        pnl_s = f"{pnl:+.1f}%" if pnl is not None else "—"
        lines.append(
            f"**{ticker}** · {shares:g} sh · cost ${cost:,.2f} · {price_s} · {pnl_s}"
        )
    extra = len(holdings) - limit
    if extra > 0:
        lines.append(f"_+{extra} more positions_")
    return "\n".join(lines) or "No holdings parsed"


async def notify_futu_capture_telegram(
    *,
    holdings: List[Dict[str, Any]],
    advisory: Dict[str, Any],
    parse_method: str,
    pushed_by: str = "cc-api",
) -> bool:
    """Post parsed holdings + AI advisory to Telegram (monitor-only)."""
    from src.notifications.telegram import (
        escape_html,
        format_alert_timestamp,
        format_brand_footer,
        format_brand_header,
        format_cc_dashboard_link,
        send_message_async,
        telegram_is_configured,
    )

    if not telegram_is_configured():
        return False

    summary = advisory.get("portfolio_summary") or {}
    lines = [
        format_brand_header(),
        "━━━━━━━━━━━━━━━━━━━━",
        "<b>📸 Futu Capture · 富途持倉解析</b>",
        "",
        f"Holdings ({escape_html(parse_method)}) · "
        f"{summary.get('holdings_count', 0)} names",
        "",
    ]
    for h in holdings[:8]:
        ticker = escape_html(h.get("ticker", "?"))
        shares = h.get("shares", 0)
        pnl = h.get("pnl_pct")
        pnl_s = f"{pnl:+.1f}%" if pnl is not None else "—"
        lines.append(f"• <b>{ticker}</b> · {shares:g} sh · {escape_html(pnl_s)}")
    extra = len(holdings) - 8
    if extra > 0:
        lines.append(f"• +{extra} more positions")
    en = str(advisory.get("summary_en") or "")[:600]
    if en:
        lines.extend(["", f"<i>{escape_html(en)}</i>"])
    zh = str(advisory.get("summary_zh") or "")[:400]
    if zh:
        lines.extend(["", f"繁中 · {escape_html(zh)}"])
    lines.append(format_alert_timestamp())
    dash = format_cc_dashboard_link()
    if dash:
        lines.append(f'🔗 <a href="{escape_html(dash)}">Open CC · 開啟 CC</a>')
    lines.extend(
        [
            "",
            format_brand_footer(
                extra="Advisory only · 僅供參考 · Not financial advice · 非投資建議"
            ),
        ]
    )
    try:
        return await send_message_async("\n".join(lines))
    except Exception as exc:
        logger.warning("Futu Telegram notify failed: %s", exc)
        return False


async def notify_futu_capture_discord(
    *,
    holdings: List[Dict[str, Any]],
    advisory: Dict[str, Any],
    parse_method: str,
    pushed_by: str = "cc-api",
) -> bool:
    """Post parsed holdings + AI advisory to Discord (monitor-only footer)."""
    summary = advisory.get("portfolio_summary") or {}
    message = (
        f"**Holdings ({parse_method})** · {summary.get('holdings_count', 0)} names\n"
        f"{_holdings_table(holdings)}\n\n"
        f"**AI · EN**\n{(advisory.get('summary_en') or '')[:900]}\n\n"
        f"_{advisory.get('disclaimer_en', 'ADVISORY ONLY')}_"
    )
    zh = advisory.get("summary_zh") or advisory.get("disclaimer_zh") or ""
    meta = {
        "source": pushed_by,
        "parse_method": parse_method,
        "total_value": summary.get("total_value"),
        "warnings": len(advisory.get("concentration_warnings") or []),
    }
    try:
        return await push_notice_async(
            title="📸 Futu Capture · 富途持倉解析",
            message=message[:4000],
            severity="info",
            event_type="operator",
            meta=meta,
            zh_summary=zh[:500] if zh else None,
        )
    except Exception as exc:
        logger.warning("Futu Discord notify failed: %s", exc)
        return False
