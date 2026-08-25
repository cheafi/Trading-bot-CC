"""Parse Futu (富途) portfolio screenshots and OCR text into structured holdings."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_TICKER_LEN = 12
_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")

_HEADER_MARKERS = (
    "持仓",
    "持倉",
    "代码",
    "代碼",
    "数量",
    "數量",
    "成本",
    "现价",
    "現價",
    "盈亏",
    "盈虧",
    "positions",
    "symbol",
    "qty",
    "quantity",
    "cost",
    "price",
)

VISION_SYSTEM = (
    "You extract portfolio holdings from Futu (富途) mobile app screenshots. "
    "Return JSON only with key 'holdings' as array of objects: "
    "ticker (uppercase, HK codes zero-padded to 5 digits), shares, avg_cost, "
    "current_price (optional), market_value (optional), unrealized_pnl (optional), "
    "pnl_pct (optional number without %), name (optional), currency (optional). "
    "Ignore cash rows and summary totals. Only actual stock/ETF positions."
)


@dataclass
class FutuHolding:
    ticker: str
    shares: float
    avg_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    name: str = ""
    currency: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def sanitize_ticker(raw: str) -> Optional[str]:
    """Normalize and validate a ticker symbol extracted from Futu data."""
    if not raw:
        return None
    t = raw.strip().upper()
    t = re.sub(r"[^A-Z0-9.\-]", "", t)
    if not t or len(t) > _MAX_TICKER_LEN:
        return None
    if t.isdigit():
        if len(t) <= 5:
            t = t.zfill(5)
        else:
            return None
    if not _TICKER_RE.match(t):
        return None
    return t


def _parse_number(value: str) -> Optional[float]:
    if not value:
        return None
    s = str(value).strip().replace(",", "").replace("，", "")
    s = re.sub(r"[+%$HKUS¥€£]", "", s, flags=re.I)
    s = s.replace("万", "0000").replace("萬", "0000")
    try:
        return float(s)
    except ValueError:
        return None


def parse_futu_text(text: str) -> Tuple[List[FutuHolding], str]:
    """Parse OCR/plain text from typical Futu portfolio screenshots."""
    if not text or not text.strip():
        return [], "empty"

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    holdings: List[FutuHolding] = []

    row_re = re.compile(
        r"(?P<ticker>[A-Z]{1,5}|\d{5})\s+"
        r"(?:(?P<name>[^\d]+?)\s+)?"
        r"(?P<qty>[\d,]+\.?\d*)\s+"
        r"(?P<cost>[\d,]+\.?\d*)\s+"
        r"(?:(?P<price>[\d,]+\.?\d*)\s+)?"
        r"(?:(?P<pnl>[+-]?[\d,]+\.?\d*)\s*)?"
        r"(?:(?P<pct>[+-]?[\d.]+%))?",
        re.I,
    )

    for line in lines:
        if any(h in line for h in _HEADER_MARKERS) and not re.search(r"\d{3,}", line):
            continue
        m = row_re.search(line.replace("\t", " "))
        if not m:
            continue
        ticker = sanitize_ticker(m.group("ticker"))
        if not ticker:
            continue
        qty = _parse_number(m.group("qty"))
        cost = _parse_number(m.group("cost"))
        if qty is None or cost is None or qty <= 0:
            continue
        price = _parse_number(m.group("price") or "")
        pnl = _parse_number(m.group("pnl") or "")
        pct_str = m.group("pct") or ""
        pnl_pct = _parse_number(pct_str.replace("%", "")) if pct_str else None
        holdings.append(
            FutuHolding(
                ticker=ticker,
                shares=qty,
                avg_cost=cost,
                current_price=price,
                unrealized_pnl=pnl,
                pnl_pct=pnl_pct,
                name=(m.group("name") or "").strip(),
            )
        )

    if holdings:
        return _dedupe(holdings), "text_regex"

    for line in lines:
        tokens = re.split(r"\s+", line.replace(",", " "))
        for i, tok in enumerate(tokens):
            ticker = sanitize_ticker(tok)
            if not ticker:
                continue
            nums: List[float] = []
            for t in tokens[i + 1 : i + 6]:
                n = _parse_number(t)
                if n is not None:
                    nums.append(n)
            if len(nums) >= 2 and nums[0] > 0:
                holdings.append(
                    FutuHolding(
                        ticker=ticker,
                        shares=nums[0],
                        avg_cost=nums[1],
                        current_price=nums[2] if len(nums) > 2 else None,
                        unrealized_pnl=nums[3] if len(nums) > 3 else None,
                    )
                )
                break

    if holdings:
        return _dedupe(holdings), "text_token_scan"
    return [], "no_match"


def _dedupe(holdings: List[FutuHolding]) -> List[FutuHolding]:
    seen: Dict[str, FutuHolding] = {}
    for h in holdings:
        seen[h.ticker] = h
    return list(seen.values())


def holdings_from_rows(rows: List[Dict[str, Any]]) -> List[FutuHolding]:
    """Normalize vision/JSON rows into validated holdings."""
    holdings: List[FutuHolding] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = sanitize_ticker(str(row.get("ticker") or row.get("symbol") or ""))
        if not ticker:
            continue
        shares = _parse_number(
            str(row.get("shares") or row.get("qty") or row.get("quantity") or "")
        )
        avg_cost = _parse_number(
            str(
                row.get("avg_cost")
                or row.get("cost")
                or row.get("average_cost")
                or ""
            )
        )
        if shares is None or avg_cost is None or shares <= 0:
            continue
        holdings.append(
            FutuHolding(
                ticker=ticker,
                shares=shares,
                avg_cost=avg_cost,
                current_price=_parse_number(
                    str(row.get("current_price") or row.get("price") or "")
                ),
                market_value=_parse_number(str(row.get("market_value") or "")),
                unrealized_pnl=_parse_number(
                    str(row.get("unrealized_pnl") or row.get("pnl") or "")
                ),
                pnl_pct=_parse_number(str(row.get("pnl_pct") or "")),
                name=str(row.get("name") or ""),
                currency=str(row.get("currency") or ""),
            )
        )
    return _dedupe(holdings)


async def parse_futu_image_vision(
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> Tuple[List[FutuHolding], str, Optional[str]]:
    """Use vision LLM to extract holdings from a Futu screenshot."""
    from src.services.ai_service import get_ai_service

    ai = get_ai_service()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"

    parsed = await ai.analyze_image_json(
        system=VISION_SYSTEM,
        user_prompt=(
            "Extract all holdings from this Futu portfolio screenshot. "
            "Support US tickers (AAPL) and HK codes (00700). "
            "Return valid JSON with 'holdings' array."
        ),
        image_url=data_url,
        max_tokens=2000,
    )
    if not parsed:
        return [], "vision_failed", None

    holdings = holdings_from_rows(parsed.get("holdings") or [])
    if holdings:
        return holdings, "vision", json.dumps({"count": len(holdings)})[:500]
    return [], "vision_empty", None
