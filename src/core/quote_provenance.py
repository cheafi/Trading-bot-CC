"""
Quote provenance — attach trustworthy market-data metadata to recommendations.

Research validity (daily bar, labeled source) is separate from execution-ready
freshness (short TTL), which TradeDecision enforces in trade_decision.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

from src.core.models import TradeRecommendation

# Canonical sources (do not invent timestamps or prices).
SOURCE_DAILY_BAR = "market_data:daily_bar"
SOURCE_LIVE_QUOTE = "market_data:live_quote"

PROVENANCE_FLAT_KEYS = (
    "price_timestamp",
    "quote_timestamp",
    "price_source",
    "quote_source",
    "quote_price",
    "research_as_of",
)


def normalize_quote_source(source: Optional[str]) -> Optional[str]:
    if source is None:
        return None
    cleaned = str(source).strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"unknown", "none", "n/a", "na", "null", "undefined"}:
        return None
    return cleaned


def index_to_utc_iso(index_value: Any) -> Optional[str]:
    try:
        if hasattr(index_value, "to_pydatetime"):
            dt = index_value.to_pydatetime()
        else:
            dt = datetime.fromisoformat(str(index_value))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class QuoteProvenance:
    quote_timestamp: Optional[str] = None
    quote_source: Optional[str] = None
    quote_price: Optional[float] = None
    research_as_of: Optional[str] = None

    def is_complete(self) -> bool:
        return bool(self.quote_timestamp and self.quote_source and self.quote_price)


def provenance_from_daily_bar_series(close_series: Any) -> Optional[QuoteProvenance]:
    """Last daily bar close + index timestamp (not signal generation time)."""
    if close_series is None:
        return None
    try:
        if len(close_series) == 0:
            return None
        price = float(close_series.iloc[-1])
        if not math.isfinite(price) or price <= 0:
            return None
        ts = index_to_utc_iso(close_series.index[-1])
        if not ts:
            return None
        return QuoteProvenance(
            quote_timestamp=ts,
            quote_source=SOURCE_DAILY_BAR,
            quote_price=round(price, 6),
            research_as_of=ts,
        )
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def provenance_from_mapping(row: Mapping[str, Any]) -> QuoteProvenance:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    trust = row.get("trust") if isinstance(row.get("trust"), dict) else {}
    ts = (
        row.get("price_timestamp")
        or row.get("quote_timestamp")
        or meta.get("price_timestamp")
        or meta.get("quote_timestamp")
    )
    source = (
        row.get("price_source")
        or row.get("quote_source")
        or meta.get("price_source")
        or meta.get("quote_source")
        or trust.get("source")
    )
    mode = str(trust.get("mode") or "").upper()
    source = normalize_quote_source(source)
    if not source and mode in ("LIVE", "DELAYED"):
        source = f"trust_mode:{mode.lower()}"
    price_raw = row.get("quote_price") or row.get("price") or meta.get("quote_price")
    quote_price: Optional[float] = None
    if price_raw is not None:
        try:
            q = float(price_raw)
            if math.isfinite(q) and q > 0:
                quote_price = q
        except (TypeError, ValueError):
            pass
    research = (
        row.get("research_as_of")
        or meta.get("research_as_of")
        or (ts if ts else None)
    )
    return QuoteProvenance(
        quote_timestamp=str(ts).strip() if ts else None,
        quote_source=source,
        quote_price=quote_price,
        research_as_of=str(research).strip() if research else None,
    )


def provenance_from_recommendation(rec: TradeRecommendation) -> QuoteProvenance:
    meta = getattr(rec, "metadata", {}) or {}
    orig = meta.get("_original_dict") if isinstance(meta, dict) else {}
    base = orig if isinstance(orig, dict) else {}
    merged: Dict[str, Any] = {**base, **meta}
    merged.setdefault("trust", rec.trust or {})
    if rec.entry_price and not merged.get("quote_price"):
        merged["quote_price"] = rec.entry_price
    return provenance_from_mapping(merged)


def apply_provenance_to_metadata(
    metadata: Dict[str, Any], prov: QuoteProvenance
) -> None:
    if prov.quote_timestamp:
        metadata["price_timestamp"] = prov.quote_timestamp
        metadata["quote_timestamp"] = prov.quote_timestamp
    if prov.quote_source:
        metadata["price_source"] = prov.quote_source
        metadata["quote_source"] = prov.quote_source
    if prov.quote_price is not None:
        metadata["quote_price"] = prov.quote_price
    if prov.research_as_of:
        metadata["research_as_of"] = prov.research_as_of


def flatten_provenance_to_api_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure cache/API rows expose provenance at top level."""
    meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
    prov = provenance_from_mapping({**d, "metadata": meta})
    if prov.quote_timestamp:
        d["price_timestamp"] = prov.quote_timestamp
        d["quote_timestamp"] = prov.quote_timestamp
    if prov.quote_source:
        d["price_source"] = prov.quote_source
        d["quote_source"] = prov.quote_source
    if prov.quote_price is not None:
        d["quote_price"] = prov.quote_price
    if prov.research_as_of:
        d["research_as_of"] = prov.research_as_of
    return d


def attach_bar_provenance_to_recommendation(
    rec: TradeRecommendation,
    close_series: Any,
    *,
    price_tolerance_pct: float = 2.0,
) -> bool:
    """
    Attach daily-bar provenance when entry aligns with last bar close.

    Returns True if provenance was attached.
    """
    prov = provenance_from_daily_bar_series(close_series)
    if not prov or not prov.is_complete():
        return False
    entry = float(rec.entry_price or 0)
    if entry > 0 and prov.quote_price:
        drift = abs(entry - prov.quote_price) / prov.quote_price * 100.0
        if drift > price_tolerance_pct:
            rec.metadata["quote_price_mismatch_pct"] = round(drift, 2)
            return False
    apply_provenance_to_metadata(rec.metadata, prov)
    if prov.quote_price and entry <= 0:
        rec.entry_price = prov.quote_price
    return True


def quote_age_seconds(
    quote_timestamp: Optional[str], *, now: Optional[datetime] = None
) -> Optional[float]:
    if not quote_timestamp:
        return None
    now = now or datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(quote_timestamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = (now - dt).total_seconds()
    if age < 0:
        return None
    return age


def price_matches_quote(
    entry: float, quote_price: Optional[float], tolerance_pct: float = 2.0
) -> bool:
    if not quote_price or entry <= 0:
        return False
    if not math.isfinite(entry) or not math.isfinite(quote_price):
        return False
    drift = abs(entry - quote_price) / quote_price * 100.0
    return drift <= tolerance_pct
