"""Research-tier opportunity filters — liquidity, dedupe, scanner agreement."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from src.engines.correlation_risk import get_sector

# Research-tier gates only — does not change TRADE/deploy thresholds.
MIN_VOL_RATIO = 0.85
MIN_SCORE_FOR_WATCH_PROMOTION = 5.0
SCANNER_AGREEMENT_MIN = 2
MAX_NEAR_MISS_PER_SECTOR = 3
MAX_NEAR_MISS_PER_THEME = 2

_ETF_THEME_TICKERS = frozenset(
    {
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "XLK",
        "XLF",
        "XLV",
        "XLE",
        "SOXX",
        "SMH",
        "ARKK",
        "KWEB",
        "GLD",
    }
)


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val if val is not None else default)
    except (TypeError, ValueError):
        return default


def _sector_key(row: Dict[str, Any]) -> str:
    for key in ("sector_type", "sector", "sector_bucket"):
        val = row.get(key)
        if val:
            return str(val).upper()
    ticker = str(row.get("ticker") or "").upper()
    if ticker:
        return str(get_sector(ticker) or "UNKNOWN").upper()
    return "UNKNOWN"


def _theme_key(row: Dict[str, Any]) -> str:
    ticker = str(row.get("ticker") or "").upper()
    if ticker in _ETF_THEME_TICKERS:
        return f"ETF:{ticker}"
    theme = row.get("theme") or row.get("sector_type")
    if theme:
        return str(theme).upper()
    return _sector_key(row)


def passes_liquidity_filter(row: Dict[str, Any]) -> bool:
    """Drop illiquid / dead-volume names from watch promotion pool."""
    vol = _f(row.get("vol_ratio"), 1.0)
    if vol < MIN_VOL_RATIO:
        return False
    ac = str(row.get("asset_class") or "").lower()
    if ac in ("etf", "index"):
        return True
    price = _f(row.get("entry_price") or row.get("price") or row.get("close"))
    if 0 < price < 5.0:
        return False
    avg_vol = row.get("avg_volume") or row.get("average_volume")
    if avg_vol is not None:
        try:
            if float(avg_vol) < 150_000:
                return False
        except (TypeError, ValueError):
            pass
    return True


def scanner_agreement_flags(row: Dict[str, Any]) -> List[str]:
    """Lightweight 2-of-N scanner agreement — heuristic flags, research tier only."""
    flags: List[str] = []
    strategy = str(row.get("strategy") or row.get("setup") or "").lower()
    pattern = str(row.get("pattern") or "").lower()
    text = f"{strategy} {pattern}"
    if str(row.get("leader") or "").upper() == "LEADER" or _f(row.get("rs_rank")) >= 70:
        flags.append("rs_leader")
    if row.get("near_52w_high") or "breakout" in text or "squeeze" in text or "vcp" in text:
        flags.append("breakout")
    if "uptrend" in str(row.get("trend_structure") or "").lower() or row.get("above_50sma"):
        flags.append("trend")
    if _f(row.get("vol_ratio")) >= 1.15:
        flags.append("volume")
    ac = str(row.get("asset_class") or "").lower()
    if ac in ("etf", "index") or row.get("source") == "coverage_pad":
        flags.append("etf_theme")
    if "reversal" in text or "pullback" in text or "mean_reversion" in text:
        flags.append("reversal")
    rsi = row.get("rsi")
    if rsi is not None and (_f(rsi) <= 35 or _f(rsi) >= 68):
        flags.append("timing_extreme")
    return flags


def scanner_agreement_count(row: Dict[str, Any]) -> int:
    return len(scanner_agreement_flags(row))


def passes_scanner_agreement(row: Dict[str, Any], *, min_agreement: int = SCANNER_AGREEMENT_MIN) -> bool:
    """Require multi-factor agreement before research-tier WATCH promotion."""
    if row.get("execution_ready"):
        return True
    if str(row.get("source") or "") == "coverage_pad":
        return scanner_agreement_count(row) >= 1
    return scanner_agreement_count(row) >= min_agreement


def dedupe_correlated_rows(
    rows: List[Dict[str, Any]],
    *,
    max_per_sector: int = MAX_NEAR_MISS_PER_SECTOR,
    max_per_theme: int = MAX_NEAR_MISS_PER_THEME,
) -> Tuple[List[Dict[str, Any]], int]:
    """Cap correlated names in monitor pool — sector/theme buckets."""
    kept: List[Dict[str, Any]] = []
    sector_counts: Dict[str, int] = {}
    theme_counts: Dict[str, int] = {}
    dropped = 0
    for row in rows:
        sec = _sector_key(row)
        theme = _theme_key(row)
        if sector_counts.get(sec, 0) >= max_per_sector:
            dropped += 1
            continue
        if theme_counts.get(theme, 0) >= max_per_theme:
            dropped += 1
            continue
        kept.append(row)
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
    return kept, dropped


def filter_watch_promotion_candidates(
    rows: List[Dict[str, Any]],
    *,
    require_agreement: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Apply research-tier quality filters to near-miss / watch rows.

    Does not alter deploy-qualified rows or TRADE bar logic.
    Scanner agreement applies only when promoting from AVOID (near_avoid).
    """
    stats = {
        "input": len(rows),
        "liquidity_dropped": 0,
        "agreement_dropped": 0,
        "score_dropped": 0,
        "dedupe_dropped": 0,
        "output": 0,
    }
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if _f(row.get("score")) < MIN_SCORE_FOR_WATCH_PROMOTION:
            stats["score_dropped"] += 1
            continue
        if not passes_liquidity_filter(row):
            stats["liquidity_dropped"] += 1
            continue
        needs_agreement = require_agreement and row.get("promotion_source") == "near_avoid"
        if needs_agreement and not passes_scanner_agreement(row):
            stats["agreement_dropped"] += 1
            continue
        filtered.append(row)
    deduped, dedupe_n = dedupe_correlated_rows(filtered)
    stats["dedupe_dropped"] = dedupe_n
    stats["output"] = len(deduped)
    return deduped, stats
