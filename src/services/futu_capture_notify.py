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
