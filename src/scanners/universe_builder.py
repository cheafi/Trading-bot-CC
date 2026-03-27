"""
Staged Universe Builder.

Three-stage pipeline that replaces the flat hardcoded ``[:50]`` slice:

  1. **Source** — gather raw tickers from all configured markets
  2. **Filter** — fix ticker format (crypto suffix), deduplicate,
     apply per-market caps
  3. **Prioritise** — regime-aware sector weighting, adaptive total cap

Usage::

    from src.scanners.universe_builder import UniverseBuilder

    builder = UniverseBuilder()
    tickers = builder.build(
        markets=["us", "hk", "crypto"],
        regime_state={"regime": "RISK_ON", ...},
    )
    # tickers is a List[str] ready for yfinance download
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.scanners.multi_market_scanner import (
    MarketRegion,
    UniverseAsset,
    US_MEGA_CAPS,
    US_GROWTH,
    US_SECTOR_ETFS,
    HK_MAJOR,
    JP_MAJOR,
    CRYPTO_MAJOR,
)

logger = logging.getLogger(__name__)


# ── Crypto suffix map (bare symbol → yfinance symbol) ────────────
_CRYPTO_SUFFIX = "-USD"

# ── Per-market defaults ──────────────────────────────────────────
_DEFAULT_MARKET_CAP = {
    "us": 50,
    "hk": 12,
    "jp": 8,
    "crypto": 10,
}

# ── Regime → sector preference mapping ───────────────────────────
#
# Each regime label maps to a dict of sector keywords → weight
# multiplier.  Tickers whose ``sector`` field (or ticker list)
# matches a favoured sector get boosted to the front of the queue.
#
# Weights > 1.0 = overweight (sort earlier)
# Weights < 1.0 = underweight (sort later)
# Missing sectors default to 1.0 (neutral)

REGIME_SECTOR_WEIGHTS: Dict[str, Dict[str, float]] = {
    "RISK_ON": {
        "Technology": 1.4,
        "Growth": 1.3,
        "Crypto": 1.2,
        "ETF": 0.8,
        "Utilities": 0.6,
        "Staples": 0.6,
        "Defensive": 0.6,
    },
    "RISK_OFF": {
        "Utilities": 1.4,
        "Healthcare": 1.3,
        "Staples": 1.3,
        "Defensive": 1.3,
        "ETF": 1.1,
        "Technology": 0.7,
        "Growth": 0.6,
        "Crypto": 0.4,
    },
    "NEUTRAL": {},  # all equal
}

# US ticker → sector rough mapping (for prioritisation only)
_US_SECTOR_HINTS: Dict[str, str] = {}
# Growth stocks get "Growth" sector
for _t in US_GROWTH:
    _US_SECTOR_HINTS[_t] = "Growth"
# Sector ETFs get "ETF"
for _t in US_SECTOR_ETFS:
    _US_SECTOR_HINTS[_t] = "ETF"
# Defensive ETFs
for _t in ("XLU", "XLP", "XLV"):
    _US_SECTOR_HINTS[_t] = "Defensive"
# Tech ETFs / leaders
for _t in ("XLK", "QQQ"):
    _US_SECTOR_HINTS[_t] = "Technology"
# The rest default to the asset's sector field from the universe


@dataclass
class UniverseSpec:
    """Output of the staged pipeline — one per build() call."""

    tickers: List[str] = field(default_factory=list)
    assets: List[UniverseAsset] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.tickers)


class UniverseBuilder:
    """
    Three-stage universe builder.

    Parameters
    ----------
    market_caps : dict
        Per-market ticker limits, e.g. ``{"us": 60, "hk": 15}``.
        Defaults to ``_DEFAULT_MARKET_CAP``.
    total_cap : int
        Hard upper bound on total tickers returned (across all
        markets).  Default 80.
    """

    def __init__(
        self,
        market_caps: Optional[Dict[str, int]] = None,
        total_cap: int = 80,
    ):
        self.market_caps = market_caps or dict(_DEFAULT_MARKET_CAP)
        self.total_cap = total_cap

    # ── Public API ────────────────────────────────────────────

    def build(
        self,
        markets: Optional[List[str]] = None,
        regime_state: Optional[Dict[str, Any]] = None,
        watchlist: Optional[List[str]] = None,
    ) -> UniverseSpec:
        """
        Build the universe in three stages.

        Parameters
        ----------
        markets : list of str
            Active market keys, e.g. ``["us", "hk", "crypto"]``.
            Defaults to all four markets.
        regime_state : dict
            Regime classification from ``RegimeRouter.classify()``.
            Used for sector weighting in stage 3.
        watchlist : list of str
            Extra tickers to always include (user favourites,
            alert tickers, etc.).

        Returns
        -------
        UniverseSpec
            ``.tickers`` is the flat list ready for yfinance.
        """
        if markets is None:
            markets = ["us", "hk", "jp", "crypto"]
        regime_state = regime_state or {}
        watchlist = watchlist or []

        # ── Stage 1: Source ───────────────────────────────────
        raw = self._source(markets)

        # ── Stage 2: Filter ───────────────────────────────────
        filtered = self._filter(raw, markets)

        # ── Stage 3: Prioritise ───────────────────────────────
        prioritised = self._prioritise(filtered, regime_state)

        # ── Always include watchlist at the front ─────────────
        final = self._prepend_watchlist(prioritised, watchlist)

        # ── Hard cap ──────────────────────────────────────────
        final = final[: self.total_cap]

        tickers = [a.ticker for a in final]
        stats = self._compute_stats(final, markets)

        logger.info(
            "Universe built: %d tickers (%s)",
            len(tickers),
            ", ".join(
                f"{m}={stats.get(m, 0)}" for m in markets
            ),
        )

        return UniverseSpec(
            tickers=tickers, assets=final, stats=stats,
        )

    # ── Stage 1: Source ───────────────────────────────────────

    def _source(
        self, markets: List[str],
    ) -> List[UniverseAsset]:
        """Gather raw assets from hardcoded lists."""
        assets: List[UniverseAsset] = []

        if "us" in markets:
            for t in US_MEGA_CAPS + US_SECTOR_ETFS + US_GROWTH:
                sector = _US_SECTOR_HINTS.get(t, "Equity")
                assets.append(UniverseAsset(
                    ticker=t, name=t,
                    market=MarketRegion.US, sector=sector,
                ))

        if "hk" in markets:
            for t in HK_MAJOR:
                assets.append(UniverseAsset(
                    ticker=t, name=t,
                    market=MarketRegion.HK, sector="HK Equity",
                ))

        if "jp" in markets:
            for t in JP_MAJOR:
                assets.append(UniverseAsset(
                    ticker=t, name=t,
                    market=MarketRegion.JP, sector="JP Equity",
                ))

        if "crypto" in markets:
            for t in CRYPTO_MAJOR:
                assets.append(UniverseAsset(
                    ticker=t, name=t,
                    market=MarketRegion.CRYPTO, sector="Crypto",
                ))

        return assets

    # ── Stage 2: Filter ───────────────────────────────────────

    def _filter(
        self,
        assets: List[UniverseAsset],
        markets: List[str],
    ) -> List[UniverseAsset]:
        """Deduplicate, fix crypto tickers, apply per-market caps."""
        # Deduplicate by ticker
        seen: Set[str] = set()
        unique: List[UniverseAsset] = []
        for a in assets:
            if a.ticker in seen:
                continue
            seen.add(a.ticker)

            # Fix crypto ticker format for yfinance
            if a.market == MarketRegion.CRYPTO:
                if not a.ticker.endswith(_CRYPTO_SUFFIX):
                    a.ticker = a.ticker + _CRYPTO_SUFFIX

            unique.append(a)

        # Apply per-market caps
        per_market: Dict[str, List[UniverseAsset]] = {}
        for a in unique:
            mkey = a.market.value  # "us", "hk", etc.
            per_market.setdefault(mkey, []).append(a)

        capped: List[UniverseAsset] = []
        for mkey in markets:
            market_assets = per_market.get(mkey, [])
            cap = self.market_caps.get(mkey, 20)
            capped.extend(market_assets[:cap])

        return capped

    # ── Stage 3: Prioritise ───────────────────────────────────

    def _prioritise(
        self,
        assets: List[UniverseAsset],
        regime_state: Dict[str, Any],
    ) -> List[UniverseAsset]:
        """Sort assets by regime-aware sector affinity.

        In RISK_ON regimes, Technology/Growth/Crypto get boosted
        to the front.  In RISK_OFF, Defensive/Healthcare/Utilities
        get boosted.  NEUTRAL leaves the order unchanged.
        """
        regime_label = regime_state.get("regime", "NEUTRAL")
        sector_weights = REGIME_SECTOR_WEIGHTS.get(
            regime_label,
            REGIME_SECTOR_WEIGHTS.get("NEUTRAL", {}),
        )

        if not sector_weights:
            return assets  # no re-ordering

        def _sort_key(a: UniverseAsset) -> float:
            """Higher weight → lower sort key (appears first)."""
            sector = a.sector or "Equity"
            # Try exact match, then substring
            w = sector_weights.get(sector, None)
            if w is None:
                for key, val in sector_weights.items():
                    if key.lower() in sector.lower():
                        w = val
                        break
            if w is None:
                w = 1.0
            return -w  # negative so higher weight sorts first

        return sorted(assets, key=_sort_key)

    # ── Watchlist injection ───────────────────────────────────

    @staticmethod
    def _prepend_watchlist(
        assets: List[UniverseAsset],
        watchlist: List[str],
    ) -> List[UniverseAsset]:
        """Ensure watchlist tickers are at the front."""
        if not watchlist:
            return assets

        existing = {a.ticker for a in assets}
        prepended: List[UniverseAsset] = []
        for t in watchlist:
            if t not in existing:
                prepended.append(UniverseAsset(
                    ticker=t, name=t,
                    market=MarketRegion.US,
                    sector="Watchlist",
                ))
        return prepended + assets

    # ── Stats ─────────────────────────────────────────────────

    @staticmethod
    def _compute_stats(
        assets: List[UniverseAsset],
        markets: List[str],
    ) -> Dict[str, Any]:
        stats: Dict[str, Any] = {"total": len(assets)}
        for mkey in markets:
            region = {
                "us": MarketRegion.US,
                "hk": MarketRegion.HK,
                "jp": MarketRegion.JP,
                "crypto": MarketRegion.CRYPTO,
            }.get(mkey)
            if region:
                stats[mkey] = sum(
                    1 for a in assets if a.market == region
                )
        return stats
