"""CC — Scanner Service (extracted from src/api/main.py P4).

ScannerService holds the watchlist-scan caches and the full async scan logic.
Wire once in app startup via _init_shared_services(), access everywhere via
request.app.state.scanner_service.scan(limit).
"""
import asyncio
import logging
import time as _time

import numpy as np

from src.core.risk_limits import RISK, SIGNAL_THRESHOLDS
from src.services.confidence import compute_4layer_confidence
from src.services.indicators import (
    compute_indicators as _compute_indicators,
    compute_rs_vs_benchmark as _compute_rs_vs_benchmark,
)

logger = logging.getLogger(__name__)

# ── Phase 9 engine imports (graceful fallback) ───────────────────────────────
try:
    from src.engines.breakout_monitor import BreakoutMonitor
    from src.engines.decision_persistence import get_journal
    from src.engines.earnings_calendar import get_earnings_info
    from src.engines.entry_quality import EntryQualityEngine
    from src.engines.fundamental_data import get_fundamentals
    from src.engines.portfolio_gate import PortfolioGate
    from src.engines.structure_detector import StructureDetector
    _P9_ENGINES = True
except ImportError:
    _P9_ENGINES = False

try:
    from src.engines.conformal_predictor import reliability_bucket, reliability_note
except ImportError:
    def reliability_bucket(n): return "low"  # noqa
    def reliability_note(n): return "Insufficient data"  # noqa

# ── Watchlist + sector map ───────────────────────────────────────────────────
SCAN_WATCHLIST = [
    # ── Information Technology ──
    "AAPL",
    "MSFT",
    "NVDA",
    "AVGO",
    "ORCL",
    "CRM",
    "AMD",
    "CSCO",
    "ACN",
    "ADBE",
    "IBM",
    "INTC",
    "TXN",
    "QCOM",
    "INTU",
    "AMAT",
    "NOW",
    "MU",
    "LRCX",
    "ADI",
    "KLAC",
    "PANW",
    "SNPS",
    "CDNS",
    "CRWD",
    "MSI",
    "NXPI",
    "FTNT",
    "ROP",
    "APH",
    "MCHP",
    "TEL",
    "ADSK",
    "KEYS",
    "ON",
    "CDW",
    "FICO",
    "IT",
    "FSLR",
    "MPWR",
    "SMCI",
    "ARM",
    "PLTR",
    "NET",
    "DDOG",
    "SNOW",
    "ZS",
    "SHOP",
    "TTD",
    "HUBS",
    "TEAM",
    "MDB",
    "ESTC",
    "CFLT",
    "S",
    "CRDO",
    "ONTO",
    "ANET",
    "DELL",
    "HPQ",
    "HPE",
    "WDC",
    "STX",
    "ENPH",
    "GLOB",
    "EPAM",
    "PAYC",
    "PCTY",
    "MANH",
    "BILL",
    "DOCU",
    "OKTA",
    # ── Communication Services ──
    "META",
    "GOOGL",
    "GOOG",
    "NFLX",
    "T",
    "TMUS",
    "VZ",
    "DIS",
    "CMCSA",
    "CHTR",
    "EA",
    "TTWO",
    "MTCH",
    "WBD",
    "LYV",
    "RBLX",
    "PINS",
    "SNAP",
    "ROKU",
    "ZM",
    "SPOT",
    "RDDT",
    "DASH",
    "UBER",
    # ── Consumer Discretionary ──
    "AMZN",
    "TSLA",
    "HD",
    "MCD",
    "NKE",
    "SBUX",
    "TJX",
    "BKNG",
    "LOW",
    "CMG",
    "ORLY",
    "ABNB",
    "MAR",
    "GM",
    "F",
    "ROST",
    "YUM",
    "DHI",
    "LEN",
    "LULU",
    "AZO",
    "GPC",
    "POOL",
    "DECK",
    "ULTA",
    "DPZ",
    "WYNN",
    "MGM",
    "LVS",
    "RCL",
    "CCL",
    "NCLH",
    "ETSY",
    "W",
    "RIVN",
    "NIO",
    "XPEV",
    "LI",
    "LCID",
    # ── Financials ──
    "JPM",
    "V",
    "MA",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "SPGI",
    "BLK",
    "AXP",
    "SCHW",
    "C",
    "CB",
    "MMC",
    "PGR",
    "ICE",
    "AON",
    "CME",
    "MCO",
    "USB",
    "AJG",
    "MSCI",
    "PNC",
    "TFC",
    "AIG",
    "MET",
    "PRU",
    "TROW",
    "BK",
    "STT",
    "FITB",
    "RF",
    "CFG",
    "HBAN",
    "KEY",
    "ALLY",
    "SOFI",
    "COIN",
    "HOOD",
    "MKTX",
    "FIS",
    "FISV",
    "PYPL",
    "XYZ",
    "AFRM",  # SQ→XYZ (Block rebrand)
    # ── Healthcare ──
    "UNH",
    "JNJ",
    "LLY",
    "ABBV",
    "MRK",
    "TMO",
    "ABT",
    "DHR",
    "PFE",
    "BMY",
    "AMGN",
    "MDT",
    "ISRG",
    "SYK",
    "GILD",
    "VRTX",
    "REGN",
    "BSX",
    "ELV",
    "CI",
    "ZTS",
    "BDX",
    "HCA",
    "MRNA",
    "BNTX",
    "DXCM",
    "IDXX",
    "IQV",
    "MTD",
    "ALGN",
    "HOLX",
    "PODD",
    "INCY",
    "BIIB",
    "ILMN",
    "A",
    "WST",
    "RMD",
    "EW",
    "BAX",
    "CNC",
    "MOH",
    "NBIX",
    "IONS",
    # ── Industrials ──
    "GE",
    "CAT",
    "UNP",
    "HON",
    "RTX",
    "BA",
    "LMT",
    "DE",
    "UPS",
    "ADP",
    "ETN",
    "WM",
    "ITW",
    "EMR",
    "NSC",
    "CSX",
    "GD",
    "NOC",
    "TDG",
    "CTAS",
    "PCAR",
    "CARR",
    "FAST",
    "ODFL",
    "CPRT",
    "WCN",
    "RSG",
    "LHX",
    "VRSK",
    "PWR",
    "IR",
    "ROK",
    "SWK",
    "FTV",
    "AXON",
    "TDY",
    "HEI",
    "RKLB",
    "ASTS",
    "LUNR",
    # ── Consumer Staples ──
    "PG",
    "COST",
    "KO",
    "PEP",
    "WMT",
    "PM",
    "MO",
    "MDLZ",
    "CL",
    "EL",
    "KMB",
    "GIS",
    "SJM",
    "HSY",
    "K",
    "STZ",
    "ADM",
    "TSN",
    "TGT",
    "DG",
    # ── Energy ──
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "EOG",
    "MPC",
    "PSX",
    "VLO",
    "OXY",
    "DVN",
    "HAL",
    "BKR",
    "FANG",
    "KMI",
    "WMB",
    "OKE",
    "TRGP",
    "ET",
    "PBR",
    "BP",
    "SHEL",
    "TTE",
    "VALE",
    # ── Materials ──
    "LIN",
    "APD",
    "SHW",
    "ECL",
    "DD",
    "NEM",
    "FCX",
    "NUE",
    "VMC",
    "MLM",
    "PPG",
    "ALB",
    "EMN",
    "CF",
    "MOS",
    # ── Utilities ──
    "NEE",
    "SO",
    "DUK",
    "D",
    "AEP",
    "SRE",
    "EXC",
    "XEL",
    "WEC",
    "ED",
    # ── Real Estate ──
    "PLD",
    "AMT",
    "CCI",
    "EQIX",
    "PSA",
    "O",
    "WELL",
    "DLR",
    "SPG",
    "VICI",
    "ARE",
    "AVB",
    "EQR",
    "MAA",
    "INVH",
    # ── ETFs ──
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLI",
    "XLP",
    "XLY",
    "ARKK",
    "ARKG",
    "SMH",
    "SOXX",
    # ── Crypto-adjacent ──
    "MSTR",
    "MARA",
    "RIOT",
    "CLSK",
    "BTBT",
    "HUT",
    "BITF",
    "CIFR",
    # ── International ADRs ──
    "BABA",
    "TSM",
    "ASML",
    "NVO",
    "SAP",
    "TM",
    "SNY",
    "AZN",
    "DEO",
    "UL",
    "INFY",
    "WIT",
    "GRAB",
    "SE",
    "MELI",
    "NU",
    "BIDU",
    "JD",
    "PDD",
    "KWEB",
    # ── Additional Mid/Small-Cap & Popular ──
    # Fintech / Payments
    "UPST",
    "LMND",
    "OPEN",
    "LC",
    "TOST",
    "FOUR",
    "GPN",
    "WEX",
    "PAGS",
    "STNE",
    # Cybersecurity
    "TENB",
    "RPD",
    "VRNS",
    "QLYS",
    # AI / Data / Analytics
    "AI",
    "PATH",
    "BRZE",
    "DV",
    "CWAN",
    "GTLB",
    # Cannabis
    "TLRY",
    "CGC",
    "ACB",
    "SNDL",
    # Biotech Small-Cap
    "SMMT",
    "LEGN",
    "SRPT",
    "ALNY",
    "BMRN",
    "EXAS",
    "NTRA",
    "RXRX",
    "DNA",
    # Solar / Clean Energy
    "RUN",
    "ARRY",
    "SHLS",
    # Retail / E-commerce
    "CHWY",
    "COUR",
    "DUOL",
    "ASAN",
    "FVRR",
    "UPWK",
    # Gaming / Entertainment
    "DKNG",
    "PENN",
    "RSI",
    "GENI",
    "U",
    # Telecom / Infrastructure
    "LUMN",
    "TNET",
    "CALIX",
    # Travel / Hospitality
    "EXPE",
    "TRIP",
    "HTHT",
    # Industrials Small-Cap
    "GNRC",
    "TTC",
    "SITE",
    "BLDR",
    "TREX",
    # Food / Beverage
    "CELH",
    "MNST",
    "SAM",
    "FIZZ",
    # Insurance
    "ROOT",
    "ACGL",
    "RNR",
    "ERIE",
    # Mining / Metals
    "GOLD",
    "AEM",
    "WPM",
    "RGLD",
    "PAAS",
    "AG",
    # REITs Small
    "REXR",
    "SUI",
    "ELS",
    "CUBE",
    # Misc Popular
    "CAVA",
    "BROS",
    "DJT",
    "IONQ",
    "RGTI",
    "QUBT",
    "SOUN",
    "JOBY",
    "ACHR",
    "VST",
    "TXRH",
    "WING",
    "COKE",
    "TMDX",
    "PRCT",
    "AXSM",
    "KRYS",
    "CVNA",
]
# Deduplicate while preserving order
SCAN_WATCHLIST = list(dict.fromkeys(SCAN_WATCHLIST))

TICKER_SECTOR: dict[str, str] = {}
SECTOR_CLUSTERS = {
    "Semiconductor": [
        "NVDA",
        "AMD",
        "AVGO",
        "MU",
        "INTC",
        "SMCI",
        "ARM",
        "QCOM",
        "TXN",
        "AMAT",
        "LRCX",
        "ADI",
        "KLAC",
        "NXPI",
        "MCHP",
        "ON",
        "MPWR",
        "FSLR",
        "CRDO",
        "ONTO",
        "TSM",
        "ASML",
        "SOXX",
        "SMH",
    ],
    "Big Tech": ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META"],
    "Software/Cloud": [
        "CRM",
        "ORCL",
        "ADBE",
        "NOW",
        "INTU",
        "PANW",
        "SNPS",
        "CDNS",
        "CRWD",
        "FTNT",
        "ADSK",
        "ANSS",
        "FICO",
        "PLTR",
        "NET",
        "DDOG",
        "SNOW",
        "ZS",
        "SHOP",
        "TTD",
        "HUBS",
        "TEAM",
        "MDB",
        "ESTC",
        "CFLT",
        "OKTA",
        "DOCU",
        "BILL",
        "PAYC",
        "PCTY",
        "MANH",
        "SAP",
    ],
    "Financials": [
        "JPM",
        "V",
        "MA",
        "BAC",
        "WFC",
        "GS",
        "MS",
        "SPGI",
        "BLK",
        "AXP",
        "SCHW",
        "C",
        "CB",
        "PGR",
        "ICE",
        "AON",
        "CME",
        "MCO",
        "USB",
        "AJG",
        "MSCI",
        "PNC",
        "TFC",
        "AIG",
        "MET",
        "PRU",
        "TROW",
        "BK",
        "STT",
        "FITB",
        "RF",
        "CFG",
        "HBAN",
        "KEY",
        "ALLY",
        "SOFI",
        "COIN",
        "HOOD",
        "MKTX",
        "FIS",
        "FISV",
        "PYPL",
        "SQ",
        "AFRM",
        "XLF",
    ],
    "Healthcare": [
        "UNH",
        "JNJ",
        "LLY",
        "ABBV",
        "MRK",
        "TMO",
        "ABT",
        "DHR",
        "PFE",
        "BMY",
        "AMGN",
        "MDT",
        "ISRG",
        "SYK",
        "GILD",
        "VRTX",
        "REGN",
        "BSX",
        "ELV",
        "CI",
        "ZTS",
        "BDX",
        "HCA",
        "MRNA",
        "BNTX",
        "DXCM",
        "IDXX",
        "IQV",
        "MTD",
        "ALGN",
        "HOLX",
        "PODD",
        "INCY",
        "BIIB",
        "ILMN",
        "A",
        "WST",
        "RMD",
        "EW",
        "BAX",
        "CNC",
        "MOH",
        "HZNP",
        "NBIX",
        "IONS",
        "XLV",
    ],
    "Consumer Disc": [
        "HD",
        "MCD",
        "NKE",
        "SBUX",
        "TJX",
        "BKNG",
        "LOW",
        "CMG",
        "ORLY",
        "ABNB",
        "MAR",
        "ROST",
        "YUM",
        "DHI",
        "LEN",
        "LULU",
        "AZO",
        "GPC",
        "POOL",
        "DECK",
        "ULTA",
        "DPZ",
        "WYNN",
        "MGM",
        "LVS",
        "RCL",
        "CCL",
        "NCLH",
        "ETSY",
        "W",
        "XLY",
    ],
    "Consumer Staples": [
        "PG",
        "COST",
        "KO",
        "PEP",
        "WMT",
        "PM",
        "MO",
        "MDLZ",
        "CL",
        "EL",
        "KMB",
        "GIS",
        "SJM",
        "HSY",
        "STZ",
        "ADM",
        "TSN",
        "TGT",
        "DG",
        "XLP",
    ],
    "EV/Auto": ["TSLA", "RIVN", "NIO", "XPEV", "LI", "LCID", "QS", "GM", "F"],
    "ETF": [
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "XLK",
        "XLE",
        "XLI",
        "ARKK",
        "ARKG",
        "KWEB",
    ],
    "Aerospace/Defense": [
        "RTX",
        "BA",
        "LMT",
        "GE",
        "GD",
        "NOC",
        "TDG",
        "LHX",
        "TDY",
        "HEI",
        "RKLB",
        "ASTS",
        "LUNR",
        "AXON",
        "XLI",
    ],
    "Energy": [
        "XOM",
        "CVX",
        "COP",
        "SLB",
        "EOG",
        "MPC",
        "PSX",
        "VLO",
        "PXD",
        "OXY",
        "HES",
        "DVN",
        "HAL",
        "BKR",
        "FANG",
        "KMI",
        "WMB",
        "OKE",
        "TRGP",
        "ET",
        "PBR",
        "BP",
        "SHEL",
        "TTE",
        "VALE",
        "XLE",
    ],
    "Materials": [
        "LIN",
        "APD",
        "SHW",
        "ECL",
        "DD",
        "NEM",
        "FCX",
        "NUE",
        "VMC",
        "MLM",
        "PPG",
        "ALB",
        "EMN",
        "CF",
        "MOS",
    ],
    "Industrials": [
        "CAT",
        "UNP",
        "HON",
        "DE",
        "UPS",
        "ADP",
        "ETN",
        "WM",
        "ITW",
        "EMR",
        "NSC",
        "CSX",
        "CTAS",
        "PCAR",
        "CARR",
        "FAST",
        "ODFL",
        "CPRT",
        "WCN",
        "RSG",
        "VRSK",
        "PWR",
        "IR",
        "ROK",
        "SWK",
        "FTV",
    ],
    "Utilities": ["NEE", "SO", "DUK", "D", "AEP", "SRE", "EXC", "XEL", "WEC", "ED"],
    "Real Estate": [
        "PLD",
        "AMT",
        "CCI",
        "EQIX",
        "PSA",
        "O",
        "WELL",
        "DLR",
        "SPG",
        "VICI",
        "ARE",
        "AVB",
        "EQR",
        "MAA",
        "INVH",
    ],
    "Crypto-adjacent": ["MSTR", "MARA", "RIOT", "CLSK", "BTBT", "HUT", "BITF", "CIFR"],
    "Intl ADR": [
        "BABA",
        "TSM",
        "ASML",
        "NVO",
        "SAP",
        "TM",
        "SNY",
        "AZN",
        "DEO",
        "UL",
        "INFY",
        "WIT",
        "GRAB",
        "SE",
        "MELI",
        "NU",
        "BIDU",
        "JD",
        "PDD",
    ],
    "Communication": [
        "NFLX",
        "T",
        "TMUS",
        "VZ",
        "DIS",
        "CMCSA",
        "CHTR",
        "EA",
        "TTWO",
        "MTCH",
        "WBD",
        "PARA",
        "LYV",
        "RBLX",
        "PINS",
        "SNAP",
        "ROKU",
        "ZM",
        "SPOT",
        "RDDT",
        "DASH",
        "UBER",
    ],
}
for _sector, _tickers in SECTOR_CLUSTERS.items():
    for _t in _tickers:
        TICKER_SECTOR[_t] = _sector
MAX_SIGNALS_PER_SECTOR = RISK.max_correlated_names  # default 3


_SPY_CACHE: dict = {"close": None, "ts": 0.0}


class ScannerService:
    """Holds scan caches and exposes .scan(limit) coroutine."""

    CACHE_TTL = 300      # 5 minutes
    NEG_TTL   = 3600     # 1 hour
    BATCH     = 25

    def __init__(self, mds):
        self._mds = mds
        self._cache: dict = {"recs": [], "scores": {}, "ts": 0.0}
        self._neg: dict[str, float] = {}

    async def _spy_close(self) -> "np.ndarray | None":
        now = _time.time()
        if _SPY_CACHE["close"] is not None and now - _SPY_CACHE["ts"] < 3600:
            return _SPY_CACHE["close"]
        try:
            hist = await self._mds.get_history("SPY", period="1y", interval="1d")
            if hist is not None and not hist.empty:
                c = "Close" if "Close" in hist.columns else "close"
                spy = hist[c].values.astype(float)
                _SPY_CACHE["close"] = spy
                _SPY_CACHE["ts"] = now
                return spy
        except Exception:
            pass
        return None

def honest_confidence_label(composite: float) -> dict:
    """Return honest labeling for confidence scores.

    CRITICAL: The composite score measures indicator alignment, NOT
    probability of profit. This function adds honest framing.
    """
    if composite >= 85:
        alignment = "Strong indicator alignment"
        honest_note = ("Indicators are well-aligned. This does NOT guarantee profit. "
                       "No backtest validates this specific threshold.")
    elif composite >= 70:
        alignment = "Good indicator alignment"
        honest_note = ("Most indicators agree. This is a technical alignment score, "
                       "not a win probability. Historical hit rate unknown.")
    elif composite >= 55:
        alignment = "Moderate indicator alignment"
        honest_note = ("Mixed signals. Some indicators support, others neutral. "
                       "This is NOT a 55% win probability.")
    else:
        alignment = "Weak indicator alignment"
        honest_note = ("Indicators are poorly aligned. Low-quality setup. "
                       "Consider waiting for better conditions.")

    return {
        "composite": composite,
        "label": alignment,
        "is_probability": False,
        "honest_note": honest_note,
        "what_this_measures": "Degree of technical indicator agreement (0-100)",
        "what_this_does_NOT_measure": "Probability of profit, expected return, or edge",
        "calibration_status": "uncalibrated — no realized hit-rate data yet",
    }


async def days_to_earnings(ticker: str, mds) -> int | None:
    """Estimate days to next earnings for a ticker.

    Uses yfinance calendar if available, otherwise returns None.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is not None and not cal.empty:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            # Calendar may be a DataFrame with 'Earnings Date' column
            if hasattr(cal, 'iloc'):
                for col in cal.columns:
                    val = cal[col].iloc[0]
                    if hasattr(val, 'date'):
                        delta = (val - now).days
                        if delta >= 0:
                            return delta
        # Try .earnings_dates attribute
        ed = getattr(t, 'earnings_dates', None)
        if ed is not None and not ed.empty:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            for dt in ed.index:
                if hasattr(dt, 'tz_localize'):
                    dt = dt.tz_localize('UTC')
                delta = (dt - now).days
                if delta >= 0:
                    return int(delta)
    except Exception:
        pass
    return None


def enrich_calibration(conf: dict, strategy: str) -> dict:
    """Build 6-layer calibrated confidence from 4-layer confidence output.

    Layers: forecast_probability, historical_reliability, uncertainty_band,
    data_confidence, execution_confidence, portfolio_fit_confidence.
    """
    composite = conf.get("composite", 50)
    cal = conf.get("calibration", {})
    bucket = cal.get("confidence_bucket", "medium")
    predicted_prob = cal.get("predicted_prob", composite / 100)

    # Uncertainty band: ±12% for high-confidence, ±18% for medium, ±25% for low
    band_half = {"high": 12, "medium": 18, "low": 25}.get(bucket, 18)
    low_bound = max(0, round(composite - band_half, 1))
    high_bound = min(100, round(composite + band_half, 1))

    return {
        "forecast_probability": round(predicted_prob, 3),
        "historical_reliability_bucket": bucket,
        "uncertainty_band": {"low": low_bound, "high": high_bound},
        "uncertainty_display": f"{low_bound:.0f}–{high_bound:.0f}%",
        "data_confidence": conf.get("data", {}).get("score", 50),
        "execution_confidence": conf.get("execution", {}).get("score", 50),
        "portfolio_fit_confidence": None,  # populated when portfolio context available
        "sample_size": None,  # populated from shadow tracker when available
        "calibration_note": "Brier-tracked; uncertainty bands are conformal estimates, not guarantees.",
        "display_recommendation": (
            f"{bucket.title()} confidence | {low_bound:.0f}–{high_bound:.0f}% range"
        ),
    }


def compute_action_state(conf: dict, rr: float, trending: bool) -> dict:
    """Compute 5-tier action state: STRONG_BUY, BUY, WATCH, REDUCE, NO_TRADE, HEDGE."""
    tier = conf.get("decision_tier", "WATCH")
    sizing = conf.get("sizing", "")
    should_trade = conf.get("should_trade", False)
    abstain = conf.get("abstain_reason")

    return {
        "action": tier,
        "sizing_guidance": sizing,
        "should_trade": should_trade,
        "abstain_reason": abstain,
        "risk_reward": rr,
        "regime_aligned": trending,
        "display": f"{'✅' if should_trade else '⏸️'} {tier.replace('_', ' ').title()}",
    }


def build_reasons_for(
    close, sma20, sma50, sma200, rsi, vol_ratio, i, strategy, trending
):
    """Build bullish evidence list."""
    reasons = []
    if close[i] > sma50[i] > sma200[i]:
        reasons.append("Strong uptrend: price > SMA50 > SMA200")
    elif close[i] > sma50[i]:
        reasons.append("Above SMA50 — uptrend intact")
    if 40 < rsi[i] < 70:
        reasons.append(f"RSI {rsi[i]:.0f} in healthy zone")
    if vol_ratio[i] > 1.5:
        reasons.append(
            f"Volume {vol_ratio[i]:.1f}x above average — institutional interest"
        )
    elif vol_ratio[i] > 1.0:
        reasons.append("Volume confirms move")
    if trending:
        reasons.append("Regime-aligned: trending market")
    if strategy == "swing" and rsi[i] < 40:
        reasons.append("RSI oversold — bounce potential")
    if strategy == "breakout" and vol_ratio[i] > 2.0:
        reasons.append("Breakout with surge volume — high conviction")
    return reasons[:5]


def build_reasons_against(
    close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, i, strategy
):
    """Build bearish / caution evidence list."""
    reasons = []
    if rsi[i] > 70:
        reasons.append(f"RSI {rsi[i]:.0f} overbought — risk of pullback")
    if rsi[i] > 80:
        reasons.append("Extremely overbought — high reversal risk")
    if close[i] < sma200[i]:
        reasons.append("Below SMA200 — long-term downtrend")
    if vol_ratio[i] < 0.8:
        reasons.append("Below-average volume — weak conviction")
    if float(atr_pct[i]) > 0.04:
        reasons.append(
            f"High volatility ({float(atr_pct[i])*100:.1f}% ATR) — wider stops needed"
        )
    dist_sma20 = abs(close[i] - sma20[i]) / sma20[i] if sma20[i] > 0 else 0
    if dist_sma20 > 0.05:
        reasons.append(f"Extended {dist_sma20*100:.1f}% from SMA20 — may need pullback")
    if strategy == "mean_reversion" and close[i] < sma200[i]:
        reasons.append("Counter-trend trade in downtrend — higher failure rate")
    if not reasons:
        reasons.append("No significant bearish factors identified")
    return reasons[:5]


def build_pre_mortem(strategy: str, trending: bool) -> str:
    """Most likely failure scenario for this trade."""
    pre_mortems = {
        "momentum": (
            "Momentum stalls at resistance and reverses on profit-taking"
            if trending
            else "False breakout in range-bound market — trapped longs"
        ),
        "breakout": (
            "Breakout fails on declining volume — price returns inside range"
            if not trending
            else "Breakout extends into exhaustion gap — sharp reversal"
        ),
        "swing": ("Bounce fails to hold — lower low confirms downtrend continuation"),
        "mean_reversion": (
            "Mean reversion premature — stock continues falling as trend accelerates"
        ),
    }
    return pre_mortems.get(strategy, "Unexpected macro event or sector-wide sell-off")


def build_why_wait(conf: dict, rr: float) -> str | None:
    """Suggest conditions that would improve entry quality."""
    composite = conf.get("composite", 50)
    reasons = []
    if composite < 60:
        reasons.append("confidence below 60 — wait for stronger setup confirmation")
    if rr < 2.0:
        reasons.append(
            f"risk/reward {rr:.1f}:1 — wait for tighter stop or higher target"
        )
    timing = conf.get("timing", {}).get("score", 50)
    if timing < 45:
        reasons.append("timing score weak — wait for pullback to support")
    if not reasons:
        return None
    return "Consider waiting: " + "; ".join(reasons)




    async def scan(self, limit: int = 10) -> tuple[list, dict]:
        """Scan watchlist for live signals using current market data.

        Returns (recommendations, strategy_scores) — same format as engine cache.
        Uses 6mo history + indicators to check all 4 strategies for each ticker.
        Results are cached for 5 minutes.
        """
        import time as _t

        import numpy as np

        now = _t.time()
        if self._cache["recs"] and (now - self._cache["ts"]) < self.CACHE_TTL:
            return self._cache["recs"][:limit], self._cache["scores"]

            mds = self._mds
        recs = []
        strat_wins = {"momentum": 0, "breakout": 0, "swing": 0, "mean_reversion": 0}
        strat_total = {"momentum": 0, "breakout": 0, "swing": 0, "mean_reversion": 0}

        # Filter out negative-cached tickers
        active_tickers = [
            t
            for t in SCAN_WATCHLIST
            if t not in self._neg or (now - self._neg[t]) > self.NEG_TTL
        ]
        logger.info(
            f"[Scanner] {len(active_tickers)}/{len(SCAN_WATCHLIST)} tickers "
            f"({len(SCAN_WATCHLIST) - len(active_tickers)} neg-cached)"
        )

        # Parallel batch fetch
        async def _fetch_one(ticker: str):
            try:
                hist = await mds.get_history(ticker, period="1y", interval="1d")
                if hist is None or hist.empty or len(hist) < 60:
                    self._neg[ticker] = now  # skip next time
                    return None
                return (ticker, hist)
            except Exception:
                self._neg[ticker] = now
                return None

        all_results = []
        for batch_start in range(0, len(active_tickers), self.BATCH):
            batch = active_tickers[batch_start : batch_start + self.BATCH]
            batch_results = await asyncio.gather(
                *[_fetch_one(t) for t in batch], return_exceptions=True
            )
            all_results.extend(
                r for r in batch_results if r is not None and not isinstance(r, Exception)
            )

        # Fetch SPY benchmark for RS computation
        spy_close = await self._spy_close()

        for ticker, hist in all_results:
            try:
                if hist is None or hist.empty or len(hist) < 60:
                    continue

                c_col = "Close" if "Close" in hist.columns else "close"
                v_col = "Volume" if "Volume" in hist.columns else "volume"
                close = hist[c_col].values.astype(float)
                volume = hist[v_col].values.astype(float)
                n = len(close)
                i = n - 1  # latest bar

                if n < 60:
                    continue

                # ── Compute indicators (causal, no look-ahead) ──
                _ind = _compute_indicators(close, volume)
                sma20 = _ind["sma20"]
                sma50 = _ind["sma50"]
                sma200 = _ind["sma200"]
                rsi = _ind["rsi"]
                vol_ratio = _ind["vol_ratio"]
                atr_pct = _ind["atr_pct"]
                cur_atr = max(float(atr_pct[i]), 0.005)

                trending = bool(close[i] > sma50[i] and sma50[i] > sma200[i])

                # ── RS vs SPY ──
                rs_info = (
                    _compute_rs_vs_benchmark(close, spy_close)
                    if spy_close is not None
                    else {
                        "rs_composite": 100.0,
                        "rs_1m": 100.0,
                        "rs_3m": 100.0,
                        "rs_6m": 100.0,
                        "rs_slope": 0.0,
                        "rs_status": "NEUTRAL",
                    }
                )

                # ── Check each strategy ──
                _ST = SIGNAL_THRESHOLDS
                strategies = {
                    "momentum": bool(
                        close[i] > sma20[i] > sma50[i]
                        and rsi[i] > _ST.rsi_momentum_low
                        and rsi[i] < _ST.rsi_momentum_high
                        and vol_ratio[i] > _ST.volume_confirmation
                    ),
                    "breakout": (
                        bool(
                            close[i] > float(np.max(close[max(0, i - 20) : i]))
                            and vol_ratio[i] > _ST.volume_surge_threshold
                            and close[i] > sma20[i]
                        )
                        if i > 20
                        else False
                    ),
                    "swing": (
                        bool(
                            rsi[i] < _ST.rsi_swing_entry
                            and close[i] > sma50[i] * (1 - _ST.swing_sma_distance)
                            and (close[i] > sma20[i] or close[i - 1] < sma20[i - 1])
                            and close[i] > close[i - 1]
                        )
                        if i > 1
                        else False
                    ),
                    "mean_reversion": bool(
                        rsi[i] < _ST.rsi_oversold
                        and close[i] < sma20[i] * (1 - _ST.mean_rev_sma_distance)
                        and vol_ratio[i] > _ST.volume_confirmation
                    ),
                }

                # Strategy params
                strat_params = {
                    "momentum": {
                        "stop": cur_atr * _ST.stop_atr_multiplier_momentum,
                        "target": _ST.target_trending if trending else _ST.target_normal,
                    },
                    "breakout": {
                        "stop": cur_atr * _ST.stop_atr_multiplier_breakout,
                        "target": (
                            _ST.target_breakout_trending
                            if trending
                            else _ST.target_breakout_normal
                        ),
                    },
                    "swing": {
                        "stop": cur_atr * _ST.stop_atr_multiplier_swing,
                        "target": (
                            _ST.target_swing_trending
                            if trending
                            else _ST.target_swing_normal
                        ),
                    },
                    "mean_reversion": {
                        "stop": cur_atr * _ST.stop_atr_multiplier_mean_rev,
                        "target": cur_atr * 3,
                    },
                }

                for strat_name, triggered in strategies.items():
                    strat_total[strat_name] += 1
                    if not triggered:
                        continue
                    strat_wins[strat_name] += 1

                    params = strat_params[strat_name]
                    entry_price = round(float(close[i]), 2)
                    stop_price = round(entry_price * (1 - params["stop"]), 2)
                    target_price = round(entry_price * (1 + params["target"]), 2)
                    risk = entry_price - stop_price
                    reward = target_price - entry_price
                    rr = round(reward / risk, 1) if risk > 0 else 0

                    # ── Phase 9: Pre-compute engines before confidence ──
                    _structure = {}
                    _entry_qual = {}
                    _earnings = {}
                    _fundamentals_brief = {}
                    _portfolio_check = {}
                    _gate_passed = True
                    if _P9_ENGINES:
                        try:
                            _pg = PortfolioGate()
                            _gr = _pg.check(
                                ticker=ticker,
                                sector=TICKER_SECTOR.get(ticker, "unknown"),
                                atr_risk_pct=float(atr_pct[i]) * 100,
                                current_positions=[
                                    {
                                        "ticker": r["ticker"],
                                        "sector": r.get("sector", "unknown"),
                                        "size_pct": 5.0,
                                        "risk_pct": 1.0,
                                    }
                                    for r in recs
                                ],
                            )
                            _portfolio_check = _gr.to_dict()
                            if not _gr.allowed:
                                _gate_passed = False
                        except Exception as _e9:
                            logger.debug("[Phase9] PortfolioGate: %s", _e9)
                    if _P9_ENGINES:
                        try:
                            h_col = "High" if "High" in hist.columns else "high"
                            l_col = "Low" if "Low" in hist.columns else "low"
                            _hi = hist[h_col].values.astype(float)
                            _lo = hist[l_col].values.astype(float)
                            _sd = StructureDetector()
                            _sr = _sd.analyze(close, _hi, _lo, volume)
                            _structure = _sr.to_dict()
                            # Use S/R for better stops/targets
                            _sup = _sr.nearest_support
                            _res = _sr.nearest_resistance
                            if _sup and _sup < entry_price:
                                stop_price = round(
                                    max(stop_price, _sup * 0.995),
                                    2,
                                )
                            if _res and _res > entry_price:
                                target_price = round(
                                    min(target_price, _res * 0.99),
                                    2,
                                )
                            risk = entry_price - stop_price
                            reward = target_price - entry_price
                            rr = round(reward / risk, 1) if risk > 0 else 0
                            _eq = EntryQualityEngine()
                            _eqr = _eq.assess(
                                close,
                                _hi,
                                _lo,
                                volume,
                                float(atr_pct[i]),
                                entry_price,
                                stop_price,
                                target_price,
                                _res,
                                _sup,
                                TICKER_SECTOR.get(ticker, "unknown"),
                            )
                            _entry_qual = _eqr.to_dict()
                        except Exception as _e9:
                            logger.debug("[Phase9] StructureDetector/EntryQuality: %s", _e9)
                        try:
                            _earnings = get_earnings_info(ticker)
                        except Exception as _e9:
                            logger.debug("[Phase9] EarningsCalendar: %s", _e9)
                        try:
                            _fd = get_fundamentals(ticker)
                            _fundamentals_brief = {
                                "quality": _fd.get("quality_score", None),
                                "pe": _fd.get("valuation", {}).get("pe_trailing"),
                                "roe": _fd.get("profitability", {}).get("roe"),
                                "rev_growth": _fd.get("growth", {}).get("revenue_growth"),
                                "moat": _fd.get("moat_indicators", {}).get(
                                    "has_moat", False
                                ),
                            }
                        except Exception as _e9:
                            logger.debug("[Phase9] FundamentalData: %s", _e9)

                    # Confidence from 4-layer (now includes Phase 9 penalties)
                    conf = compute_4layer_confidence(
                        close, sma20, sma50, sma200, rsi, atr_pct,
                        vol_ratio, i, volume, trending,
                        structure_result=_structure,
                        entry_quality_result=_entry_qual,
                        earnings_info=_earnings,
                        fundamentals_info=_fundamentals_brief,
                        regime_label="UPTREND" if trending else "SIDEWAYS",
                        ticker_sector=TICKER_SECTOR.get(ticker, "unknown"),
                    )
                    score = round(conf["composite"] / 10, 1)  # 0-10 scale
                    if not _gate_passed:
                        score = max(0, score - 2.0)

                    recs.append(
                        {
                            "ticker": ticker,
                            "symbol": ticker,
                            "score": score,
                            "confidence": conf["composite"],
                            "grade": conf["grade"] if _gate_passed else "F",
                            "direction": "LONG",
                            "strategy": strat_name,
                            "entry_price": entry_price,
                            "target_price": target_price,
                            "stop_price": stop_price,
                            "risk_reward": rr,
                            "regime": "UPTREND" if trending else "SIDEWAYS",
                            "rsi": round(float(rsi[i]), 1),
                            "vol_ratio": round(float(vol_ratio[i]), 2),
                            "atr_pct": round(float(atr_pct[i]) * 100, 2),
                            # ── Calibrated confidence (6-layer) ──
                            "calibrated_confidence": enrich_calibration(conf, strat_name),
                            # ── Action state ──
                            "action_state": compute_action_state(conf, rr, trending),
                            # ── Trust strip ──
                            "trust_strip": {
                                "mode": "SCAN",
                                "source": "yfinance",
                                "freshness": "delayed_15m",
                                "sample_size": None,
                                "assumptions": "gross returns, no commissions/slippage",
                                "feature_stage": "BETA",
                            },
                            # ── Contradiction / reasons against ──
                            "reasons_for": build_reasons_for(
                                close,
                                sma20,
                                sma50,
                                sma200,
                                rsi,
                                vol_ratio,
                                i,
                                strat_name,
                                trending,
                            ),
                            "reasons_against": build_reasons_against(
                                close,
                                sma20,
                                sma50,
                                sma200,
                                rsi,
                                vol_ratio,
                                atr_pct,
                                i,
                                strat_name,
                            ),
                            "invalidation": f"Close below ${stop_price}",
                            "pre_mortem": build_pre_mortem(strat_name, trending),
                            "why_wait": build_why_wait(conf, rr),
                            # ── Sprint 44: uncertainty + reliability ──
                            "honest_confidence": honest_confidence_label(
                                conf["composite"]
                            ),
                            "reliability": {
                                "bucket": reliability_bucket(len(close) - 60),
                                "sample_size": len(close) - 60,
                                "note": reliability_note(len(close) - 60),
                            },
                            # ── Phase 9: new engines ──
                            "structure": _structure,
                            "entry_quality": _entry_qual,
                            "earnings": _earnings,
                            "fundamentals": _fundamentals_brief,
                            "portfolio_gate": _portfolio_check,
                            "rs": rs_info,
                            "sector": TICKER_SECTOR.get(ticker, "unknown"),
                        }
                    )
                    # ── Wire Phase 9 feedback engines ──
                    if _P9_ENGINES:
                        try:
                            _bm = BreakoutMonitor()
                            _bm.load()
                            _bm.register_breakout(
                                ticker=ticker,
                                breakout_price=entry_price,
                                pivot_price=stop_price,
                            )
                            _bm.save()
                        except Exception as _e9:
                            logger.debug("[Phase9] BreakoutMonitor: %s", _e9)
                        try:
                            get_journal().record(
                                ticker=ticker,
                                decision_tier=conf.get("grade", "C"),
                                composite_score=conf["composite"] * 100,
                                should_trade=score >= 7.0,
                                regime="UPTREND" if trending else "SIDEWAYS",
                                sector=TICKER_SECTOR.get(ticker, "unknown"),
                                entry_price=entry_price,
                                stop_price=stop_price,
                                target_price=target_price,
                                extra={"strategy": strat_name, "rr": rr, "score": score},
                            )
                        except Exception as _e9:
                            logger.debug("[Phase9] DecisionJournal: %s", _e9)
            except Exception as exc:
                logger.debug(f"[Scanner] {ticker} skip: {exc}")
                continue

        # ── Fallback: if no strategy triggered, rank all tickers by strength ──
        if not recs:
            _fallback: list[tuple[str, dict]] = []
            for ticker in SCAN_WATCHLIST:
                try:
                    hist = await mds.get_history(ticker, period="1y", interval="1d")
                    if hist is None or hist.empty or len(hist) < 60:
                        continue
                    c_col = "Close" if "Close" in hist.columns else "close"
                    v_col = "Volume" if "Volume" in hist.columns else "volume"
                    close = hist[c_col].values.astype(float)
                    volume = hist[v_col].values.astype(float)
                    n = len(close)
                    ii = n - 1
                    _ind = _compute_indicators(close, volume)
                    sma20 = _ind["sma20"]
                    sma50 = _ind["sma50"]
                    sma200 = _ind["sma200"]
                    rsi_v = _ind["rsi"]
                    vol_ratio_v = _ind["vol_ratio"]
                    atr_pct_v = _ind["atr_pct"]
                    cur_atr = max(float(atr_pct_v[ii]), 0.005)
                    trending = bool(close[ii] > sma50[ii] and sma50[ii] > sma200[ii])

                    # ── Phase 9: Pre-compute for fallback path ──
                    _fb_structure = {}
                    _fb_entry_qual = {}
                    _fb_earnings = {}
                    _fb_fundamentals = {}
                    if _P9_ENGINES:
                        try:
                            h_col = "High" if "High" in hist.columns else "high"
                            l_col = "Low" if "Low" in hist.columns else "low"
                            _hi = hist[h_col].values.astype(float)
                            _lo = hist[l_col].values.astype(float)
                            _sd = StructureDetector()
                            _sr = _sd.analyze(close, _hi, _lo, volume)
                            _fb_structure = _sr.to_dict()
                        except Exception as _e9:
                            logger.debug("[Phase9-fb] structure: %s", _e9)
                        try:
                            _fb_earnings = get_earnings_info(ticker)
                        except Exception as _e9:
                            logger.debug("[Phase9-fb] earnings: %s", _e9)
                        try:
                            _fd = get_fundamentals(ticker)
                            _fb_fundamentals = {
                                "quality": _fd.get("quality_score"),
                                "pe": _fd.get("valuation", {}).get("pe_trailing"),
                                "roe": _fd.get("profitability", {}).get("roe"),
                                "rev_growth": _fd.get("growth", {}).get("revenue_growth"),
                                "moat": _fd.get("moat_indicators", {}).get(
                                    "has_moat", False
                                ),
                            }
                        except Exception as _e9:
                            logger.debug("[Phase9-fb] fundamentals: %s", _e9)

                    conf = compute_4layer_confidence(
                        close,
                        sma20,
                        sma50,
                        sma200,
                        rsi_v,
                        atr_pct_v,
                        vol_ratio_v,
                        ii,
                        volume,
                        trending,
                        structure_result=_fb_structure,
                        entry_quality_result=_fb_entry_qual,
                        earnings_info=_fb_earnings,
                        fundamentals_info=_fb_fundamentals,
                        regime_label="UPTREND" if trending else "SIDEWAYS",
                        ticker_sector=TICKER_SECTOR.get(ticker, "unknown"),
                    )
                    score = round(conf["composite"] / 10, 1)
                    entry_price = round(float(close[ii]), 2)
                    stop_price = round(entry_price * (1 - cur_atr * 2), 2)
                    target_price = round(entry_price * 1.05, 2)
                    risk = entry_price - stop_price
                    reward = target_price - entry_price
                    rr = round(reward / risk, 1) if risk > 0 else 0

                    _fallback.append(
                        (
                            ticker,
                            {
                                "ticker": ticker,
                                "symbol": ticker,
                                "score": score,
                                "confidence": conf["composite"],
                                "grade": conf["grade"],
                                "direction": "LONG",
                                "strategy": "watch",
                                "entry_price": entry_price,
                                "target_price": target_price,
                                "stop_price": stop_price,
                                "risk_reward": rr,
                                "regime": "UPTREND" if trending else "SIDEWAYS",
                                "rsi": round(float(rsi_v[ii]), 1),
                                "vol_ratio": round(float(vol_ratio_v[ii]), 2),
                                "atr_pct": round(float(atr_pct_v[ii]) * 100, 2),
                                "calibrated_confidence": enrich_calibration(
                                    conf, "momentum"
                                ),
                                "action_state": compute_action_state(conf, rr, trending),
                                "trust_strip": {
                                    "mode": "WATCH",
                                    "source": "yfinance",
                                    "freshness": "delayed_15m",
                                    "sample_size": None,
                                    "assumptions": "no entry criteria met — ranked by technical strength",
                                    "feature_stage": "BETA",
                                },
                                "reasons_for": build_reasons_for(
                                    close,
                                    sma20,
                                    sma50,
                                    sma200,
                                    rsi_v,
                                    vol_ratio_v,
                                    ii,
                                    "momentum",
                                    trending,
                                ),
                                "reasons_against": build_reasons_against(
                                    close,
                                    sma20,
                                    sma50,
                                    sma200,
                                    rsi_v,
                                    vol_ratio_v,
                                    atr_pct_v,
                                    ii,
                                    "momentum",
                                ),
                                "invalidation": f"Close below ${stop_price}",
                                "pre_mortem": "No strategy triggered — watch only",
                                "why_wait": "Wait for a defined entry setup before committing capital",
                                # Phase 9 fields (from pre-computed results)
                                "structure": _fb_structure,
                                "entry_quality": _fb_entry_qual,
                                "earnings": _fb_earnings,
                                "fundamentals": _fb_fundamentals,
                                "portfolio_gate": {},
                                "rs": (
                                    _compute_rs_vs_benchmark(close, spy_close)
                                    if spy_close is not None
                                    else {"rs_composite": 100.0, "rs_status": "NEUTRAL"}
                                ),
                                "sector": TICKER_SECTOR.get(ticker, "unknown"),
                            },
                        )
                    )
                except Exception as _e_fb:
                    logger.debug("[Scanner-fb] %s skip: %s", ticker, _e_fb)
                    continue
            _fallback.sort(key=lambda x: x[1]["score"], reverse=True)
            recs = [r for _, r in _fallback[:limit]]
            logger.info(f"[Scanner] no strategy triggered — returning top {len(recs)} by strength")

        # Sort by score desc
        recs.sort(key=lambda r: r["score"], reverse=True)

        # ── Sector correlation guard (P3) ──
        # Cap signals per sector cluster to prevent hidden concentration.
        # Walk the sorted list top-down; skip if sector already at capacity.
        sector_counts: dict[str, int] = {}
        filtered_recs: list = []
        demoted: list = []
        for rec in recs:
            sector = TICKER_SECTOR.get(rec["ticker"], "Other")
            rec["sector"] = sector
            cur = sector_counts.get(sector, 0)
            if cur < MAX_SIGNALS_PER_SECTOR:
                sector_counts[sector] = cur + 1
                filtered_recs.append(rec)
            else:
                rec["demoted_reason"] = f"Sector cap ({sector}: {MAX_SIGNALS_PER_SECTOR} max)"
                demoted.append(rec)
        recs = filtered_recs  # demoted signals dropped from active list

        # Strategy scores (0-10 scale)
        scores = {}
        for s in strat_wins:
            total = strat_total[s]
            wins = strat_wins[s]
            scores[s] = round((wins / total * 10) if total > 0 else 5.0, 1)

        self._cache["recs"] = recs
        self._cache["scores"] = scores
        self._cache["ts"] = now
        self._cache["demoted"] = demoted
        logger.info(
            f"[Scanner] scanned {len(SCAN_WATCHLIST)} tickers → "
            f"{len(recs)} signals ({len(demoted)} demoted by sector cap)"
        )
        return recs[:limit], scores



