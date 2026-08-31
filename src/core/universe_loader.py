"""
Load and validate CC X investable universe from ``data/universe.json``.

Fixed-path JSON only (no user-controlled paths). Tickers are normalized to
uppercase and validated as alphanumeric (+ dot/dash) with a max length guard.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
_MAX_TICKER_LEN = 12

# Repo-root relative — resolved from this module, never from request input.
_DEFAULT_UNIVERSE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "universe.json"
)


def validate_ticker(ticker: str) -> Optional[str]:
    """Return normalized ticker or None if invalid."""
    tk = str(ticker or "").strip().upper()
    if not tk or len(tk) > _MAX_TICKER_LEN:
        return None
    if not _TICKER_RE.match(tk):
        return None
    return tk


def _dedupe(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in items:
        tk = validate_ticker(raw)
        if tk and tk not in seen:
            seen.add(tk)
            out.append(tk)
    return out


@dataclass(frozen=True)
class UniverseRecord:
    """One symbol entry with classification metadata."""

    ticker: str
    asset_class: str  # equity | etf | index_proxy
    tier: str  # core | extended
    sector: str = ""
    theme: str = ""


@dataclass
class LoadedUniverse:
    """Parsed universe with tiered ticker lists."""

    meta: Dict[str, Any] = field(default_factory=dict)
    records: List[UniverseRecord] = field(default_factory=list)
    tier_caps: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def core_tickers(self) -> List[str]:
        return [r.ticker for r in self.records if r.tier == "core"]

    @property
    def extended_tickers(self) -> List[str]:
        return [r.ticker for r in self.records if r.tier == "extended"]

    @property
    def all_tickers(self) -> List[str]:
        return [r.ticker for r in self.records]

    def by_asset_class(self, asset_class: str) -> List[str]:
        ac = asset_class.strip().lower()
        return [r.ticker for r in self.records if r.asset_class == ac]

    def summary(self) -> Dict[str, Any]:
        eq = len(self.by_asset_class("equity"))
        etf = len(self.by_asset_class("etf"))
        idx = len(self.by_asset_class("index_proxy"))
        return {
            "source": self.meta.get("source", "unknown"),
            "provenance": self.meta.get("provenance", "unknown"),
            "version": self.meta.get("version", ""),
            "total_symbols": len(self.records),
            "core_count": len(self.core_tickers),
            "extended_count": len(self.extended_tickers),
            "equity_count": eq,
            "etf_count": etf,
            "index_proxy_count": idx,
            "tier_caps": dict(self.tier_caps),
            "validation_errors": len(self.errors),
        }


def load_universe_json(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load raw JSON from the fixed universe config path."""
    config_path = path or _DEFAULT_UNIVERSE_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"Universe config not found: {config_path}")
    with open(config_path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_universe(data: Dict[str, Any]) -> LoadedUniverse:
    """Parse universe JSON into validated records."""
    meta = dict(data.get("meta") or {})
    tier_caps = {
        str(k): int(v.get("scan_cap", 0))
        for k, v in (data.get("tiers") or {}).items()
        if isinstance(v, dict)
    }

    records: List[UniverseRecord] = []
    errors: List[str] = []
    seen: set[str] = set()

    for raw in data.get("symbols") or []:
        if not isinstance(raw, dict):
            errors.append("symbol entry is not an object")
            continue
        tk = validate_ticker(str(raw.get("ticker") or ""))
        if not tk:
            errors.append(f"invalid ticker: {raw.get('ticker')!r}")
            continue
        if tk in seen:
            continue
        seen.add(tk)

        asset_class = str(raw.get("asset_class") or "equity").strip().lower()
        if asset_class not in ("equity", "etf", "index_proxy"):
            errors.append(f"{tk}: invalid asset_class {asset_class!r}")
            continue

        tier = str(raw.get("tier") or "extended").strip().lower()
        if tier not in ("core", "extended"):
            errors.append(f"{tk}: invalid tier {tier!r}")
            continue

        records.append(
            UniverseRecord(
                ticker=tk,
                asset_class=asset_class,
                tier=tier,
                sector=str(raw.get("sector") or "").strip(),
                theme=str(raw.get("theme") or "").strip(),
            )
        )

    return LoadedUniverse(
        meta=meta,
        records=records,
        tier_caps=tier_caps,
        errors=errors,
    )


def load_universe(path: Optional[Path] = None) -> LoadedUniverse:
    """Load and parse the CC X universe config."""
    return parse_universe(load_universe_json(path))


# Module-level cache — JSON is static config, safe to memoize.
_CACHED: Optional[LoadedUniverse] = None


def get_universe() -> LoadedUniverse:
    global _CACHED
    if _CACHED is None:
        _CACHED = load_universe()
    return _CACHED


def reset_universe_cache() -> None:
    """Test helper — clear memoized load."""
    global _CACHED
    _CACHED = None
