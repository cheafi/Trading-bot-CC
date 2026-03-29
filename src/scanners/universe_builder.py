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
    US_MID_CAPS,
    US_SP500_REST,
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
    "us": 500,
    "hk": 20,
    "jp": 15,
    "crypto": 15,
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
        "Financials": 1.1,
        "Consumer": 1.1,
        "Communication": 1.1,
        "Materials": 1.0,
        "Industrials": 1.0,
        "Energy": 1.0,
        "ETF": 0.8,
        "Healthcare": 0.9,
        "REITs": 0.8,
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
        "REITs": 1.0,
        "Financials": 0.9,
        "Materials": 0.9,
        "Consumer": 0.8,
        "Communication": 0.8,
        "Industrials": 0.8,
        "Energy": 0.7,
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

# Sprint 32: sector hints for mid-caps
_MID_SECTOR_MAP = {
    "Technology": [
        "MRVL", "ON", "NXPI", "KLAC", "LRCX", "MPWR",
        "SWKS", "QCOM", "NOW", "INTU", "ADBE", "CRM",
        "WDAY", "TEAM", "HUBS", "VEEV", "BILL", "PAYC",
        "PCTY", "GTLB", "MDB", "ESTC", "CFLT", "DKNG",
    ],
    "Financials": [
        "GS", "MS", "JPM", "BAC", "WFC", "C", "SCHW",
        "BX", "KKR", "AXP", "PYPL", "FIS", "FISV", "GPN",
    ],
    "Healthcare": [
        "ISRG", "REGN", "VRTX", "GILD", "AMGN", "BIIB",
        "MRNA", "BMY", "ZTS", "EW", "DXCM", "ALGN",
        "IDXX", "SYK", "MDT", "BSX",
    ],
    "Industrials": [
        "CAT", "DE", "GE", "LMT", "NOC", "GD", "BA",
        "MMM", "EMR", "ETN", "ITW", "PH", "ROK", "FTV",
    ],
    "Energy": [
        "XOM", "CVX", "SLB", "EOG", "PXD", "DVN", "OXY",
        "MPC", "PSX", "VLO", "HAL",
    ],
    "Consumer": [
        "NKE", "SBUX", "TGT", "WMT", "LULU", "DG",
        "DLTR", "ROST", "TJX", "CMG", "YUM", "DPZ",
        "WYNN", "MGM", "MAR", "HLT", "DIS", "NFLX",
        "CMCSA", "PARA", "WBD", "SPOT", "ROKU",
    ],
    "REITs": [
        "AMT", "CCI", "PLD", "EQIX", "O", "SPG",
    ],
    "Utilities": [
        "SO", "DUK", "AEP", "D", "SRE",
    ],
    "Staples": [
        "CL", "GIS", "K", "HSY",
    ],
}
for _sector, _tickers in _MID_SECTOR_MAP.items():
    for _t in _tickers:
        _US_SECTOR_HINTS[_t] = _sector

# Sprint 32-b: sector hints for S&P 500 remainder
_SP500_SECTOR_MAP = {
    "Technology": [
        "ORCL", "IBM", "FTNT", "ANSS", "CDNS", "SNPS", "KEYS",
        "TER", "ZBRA", "JNPR", "HPE", "HPQ", "NTAP", "WDC",
        "STX", "AKAM", "FFIV", "LDOS", "IT", "TRMB", "VRSN",
        "GEN", "CTSH", "ENPH", "FSLR", "TYL", "BR", "CDW",
        "FICO", "CPAY", "GDDY", "EPAM", "PTC", "MANH", "NTNX",
        "JKHY", "MSCI",
    ],
    "Financials": [
        "BLK", "CB", "PGR", "AFL", "MET", "PRU", "TRV", "AIG",
        "ALL", "CINF", "AJG", "MMC", "AON", "TROW", "BEN",
        "IVZ", "NDAQ", "ICE", "CME", "MCO", "SPGI", "ACGL",
        "RJF", "STT", "NTRS", "CFG", "HBAN", "KEY", "RF",
        "FITB", "ZION", "CMA", "MTB", "PNC", "USB", "TFC",
        "DFS", "SYF", "COF", "GL", "L", "ERIE", "RE",
    ],
    "Healthcare": [
        "CI", "ELV", "HCA", "HUM", "CNC", "MOH", "A", "IQV",
        "WAT", "BIO", "DGX", "LH", "HOLX", "MTD", "BAX", "BDX",
        "COO", "RMD", "PODD", "INCY", "ALNY", "GEHC", "VTRS",
        "PKI", "RVTY", "TFX", "OGN",
    ],
    "Consumer": [
        "F", "GM", "APTV", "BWA", "RL", "PVH", "TPR", "GRMN",
        "POOL", "TSCO", "BBY", "KMX", "AZO", "ORLY", "EBAY",
        "ETSY", "LVS", "CZR", "RCL", "CCL", "NCLH", "LEN",
        "DHI", "PHM", "NVR", "DECK", "BURL", "ULTA", "GPC",
        "EXPE", "CPRT", "PENN",
    ],
    "Staples": [
        "MDLZ", "KHC", "SJM", "MKC", "CAG", "CPB", "HRL",
        "TSN", "SYY", "KR", "ADM", "STZ", "TAP", "MNST",
        "KDP", "CHD", "EL", "WBA", "CVS", "MO",
    ],
    "Industrials": [
        "WM", "RSG", "VRSK", "PAYX", "ADP", "CTAS", "FAST",
        "GWW", "SNA", "SWK", "TT", "CARR", "OTIS", "AME",
        "HUBB", "ROP", "IEX", "XYL", "DOV", "AOS", "GNRC",
        "PWR", "PCAR", "WAB", "NSC", "CSX", "CHRW", "JBHT",
        "UAL", "DAL", "LUV", "FDX", "UPS", "IR", "TDG",
        "HWM", "AXON", "EXPD", "STE", "ALLE", "HII",
    ],
    "Energy": [
        "WMB", "KMI", "OKE", "TRGP", "FANG", "CTRA", "MRO",
        "APA", "EQT", "BKR", "HES",
    ],
    "Materials": [
        "LIN", "APD", "SHW", "ECL", "DD", "DOW", "LYB", "EMN",
        "PPG", "ALB", "FMC", "CF", "MOS", "NUE", "STLD", "FCX",
        "NEM", "IP", "PKG", "AVY", "BLL", "VMC", "MLM", "CE",
        "CLF", "WRK", "SEE",
    ],
    "Utilities": [
        "EXC", "XEL", "ES", "WEC", "ED", "DTE", "CMS", "CNP",
        "ATO", "NI", "EVRG", "PPL", "FE", "AWK", "PNW", "AES",
        "LNT",
    ],
    "REITs": [
        "DLR", "PSA", "WELL", "AVB", "EQR", "ESS", "MAA",
        "UDR", "INVH", "KIM", "REG", "VTR", "IRM", "SBA",
        "ARE",
    ],
    "Communication": [
        "T", "VZ", "TMUS", "CHTR", "EA", "TTWO", "MTCH",
        "PINS", "SNAP", "LYV", "FOXA", "OMC", "IPG",
    ],
}
for _sector, _tickers in _SP500_SECTOR_MAP.items():
    for _t in _tickers:
        _US_SECTOR_HINTS[_t] = _sector


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
        total_cap: int = 550,
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
        filtered = self._filter(raw)

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
            for t in (
                US_MEGA_CAPS + US_MID_CAPS
                + US_SP500_REST + US_SECTOR_ETFS
                + US_GROWTH
            ):
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
    ) -> List[UniverseAsset]:
        """Deduplicate and fix crypto tickers.

        Per-market caps are applied *after* regime-aware sorting
        in ``_prioritise()`` so that favoured sectors survive the
        cut regardless of their position in the source lists.
        """
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

        return unique

    # ── Stage 3: Prioritise ───────────────────────────────────

    def _prioritise(
        self,
        assets: List[UniverseAsset],
        regime_state: Dict[str, Any],
    ) -> List[UniverseAsset]:
        """Sort assets by regime-aware sector affinity, then cap.

        In RISK_ON regimes, Technology/Growth/Crypto get boosted
        to the front.  In RISK_OFF, Defensive/Healthcare/Utilities
        get boosted.  NEUTRAL leaves the order unchanged.

        Per-market caps are applied *after* sorting so that regime-
        favoured tickers survive regardless of source-list order.
        """
        regime_label = regime_state.get("regime", "NEUTRAL")
        sector_weights = REGIME_SECTOR_WEIGHTS.get(
            regime_label,
            REGIME_SECTOR_WEIGHTS.get("NEUTRAL", {}),
        )

        if sector_weights:
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

            assets = sorted(assets, key=_sort_key)

        # Apply per-market caps on the sorted list
        per_market: Dict[str, int] = {}
        capped: List[UniverseAsset] = []
        for a in assets:
            mkey = a.market.value  # "us", "hk", etc.
            count = per_market.get(mkey, 0)
            cap = self.market_caps.get(mkey, 20)
            if count < cap:
                capped.append(a)
                per_market[mkey] = count + 1

        return capped

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

    # ── Sprint 38: Dynamic Sleeve Allocation ──────────────────

    SLEEVE_ALLOCATIONS = {
        "RISK_ON": {
            "momentum": 0.50,
            "growth": 0.25,
            "value": 0.10,
            "defensive": 0.10,
            "bearish": 0.05,
        },
        "NEUTRAL": {
            "momentum": 0.30,
            "growth": 0.20,
            "value": 0.25,
            "defensive": 0.20,
            "bearish": 0.05,
        },
        "RISK_OFF": {
            "momentum": 0.10,
            "growth": 0.10,
            "value": 0.15,
            "defensive": 0.40,
            "bearish": 0.25,
        },
    }

    SLEEVE_SECTORS = {
        "momentum": {
            "Technology", "Consumer Discretionary",
            "Crypto",
        },
        "growth": {
            "Communication Services", "Biotechnology",
            "Semiconductors",
        },
        "value": {
            "Financials", "Industrials", "Energy",
            "Materials",
        },
        "defensive": {
            "Healthcare", "Utilities",
            "Consumer Staples", "Real Estate",
        },
        "bearish": set(),  # populated dynamically
    }

    def get_sleeve_allocation(
        self,
        regime_label: str = "NEUTRAL",
    ) -> Dict[str, float]:
        """Return current sleeve weights for given regime."""
        return dict(
            self.SLEEVE_ALLOCATIONS.get(
                regime_label,
                self.SLEEVE_ALLOCATIONS["NEUTRAL"],
            )
        )

    def allocate_by_sleeve(
        self,
        assets: List[UniverseAsset],
        regime_label: str = "NEUTRAL",
    ) -> Dict[str, List[str]]:
        """Partition assets into sleeves with regime-aware counts.

        Returns a dict mapping sleeve name to list of tickers.
        """
        allocation = self.get_sleeve_allocation(regime_label)
        total = len(assets)

        # Classify each asset into a sleeve
        sleeve_assets: Dict[str, List[UniverseAsset]] = {
            s: [] for s in allocation
        }
        for a in assets:
            placed = False
            sector = a.sector or "Equity"
            for sleeve, sectors in self.SLEEVE_SECTORS.items():
                if sleeve == "bearish":
                    continue
                for s in sectors:
                    if s.lower() in sector.lower():
                        sleeve_assets[sleeve].append(a)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                # Default to value sleeve
                sleeve_assets["value"].append(a)

        # Apply allocation ratios
        result: Dict[str, List[str]] = {}
        for sleeve, pct in allocation.items():
            cap = max(1, int(total * pct))
            pool = sleeve_assets.get(sleeve, [])
            result[sleeve] = [
                a.ticker for a in pool[:cap]
            ]

        return result

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
