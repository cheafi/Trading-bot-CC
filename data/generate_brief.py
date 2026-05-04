#!/usr/bin/env python3
"""
generate_brief.py — Nightly brief JSON generator
=================================================
Produces  data/brief-YYYY-MM-DD.json  consumed by BriefDataService.

Usage:
    python data/generate_brief.py              # full run
    python data/generate_brief.py --dry-run    # print JSON only

Scheduled by src/scheduler/main.py at 06:00 ET.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# ── resolve project root ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("generate_brief")

# ── universe ──────────────────────────────────────────────────────────────────
UNIVERSE: List[str] = [
    # Mega-cap / index leaders
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "AMZN",
    "TSLA",
    "AMD",
    "AVGO",
    "ORCL",
    "CRM",
    "ADBE",
    "NOW",
    "INTU",
    "PANW",
    # Financials
    "GS",
    "JPM",
    "MS",
    "BLK",
    "V",
    "MA",
    # Healthcare / biotech
    "LLY",
    "ABBV",
    "UNH",
    "ISRG",
    # Energy / Materials
    "XOM",
    "CVX",
    "FCX",
    "NEM",
    # Consumer / Retail
    "COST",
    "HD",
    "NKE",
    "LULU",
    # Semis / Chips
    "QCOM",
    "TXN",
    "AMAT",
    "LRCX",
    "KLAC",
    "MRVL",
    # Cloud / SaaS
    "DDOG",
    "NET",
    "SNOW",
    "MDB",
    "TTD",
    "ZS",
    # Small-cap momentum picks
    "SMCI",
    "AXON",
    "DECK",
    "CELH",
    "IBKR",
]

SPY = "SPY"
PERIODS = {"signal": "6mo", "trend": "1y"}


def _rs_score(closes: List[float], spy_closes: List[float]) -> float:
    """Simple RS score: 63-day price change ratio vs SPY."""
    if len(closes) < 63 or len(spy_closes) < 63:
        return 0.0
    stock_r = closes[-1] / closes[-63] - 1
    spy_r = spy_closes[-1] / spy_closes[-63] - 1
    if abs(spy_r) < 1e-9:
        return 0.0
    return round((stock_r - spy_r) * 100, 2)


def _atr_pct(
    highs: List[float], lows: List[float], closes: List[float], window: int = 14
) -> float:
    """Average True Range as % of price."""
    if len(closes) < window + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    atr = sum(trs[-window:]) / window
    return round(atr / closes[-1] * 100, 2)


def _vol_ratio(volumes: List[float], window: int = 20) -> float:
    """Recent volume vs 20-day average."""
    if len(volumes) < window + 1:
        return 1.0
    avg = sum(volumes[-window - 1 : -1]) / window
    return round(volumes[-1] / avg, 2) if avg else 1.0


def _near_52w_high(closes: List[float]) -> bool:
    if len(closes) < 2:
        return False
    high_52 = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    return closes[-1] >= 0.95 * high_52


def _classify_ticker(
    ticker: str,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
    spy_closes: List[float],
) -> Dict[str, Any]:
    """Return a signal dict for one ticker."""
    rs = _rs_score(closes, spy_closes)
    atr = _atr_pct(highs, lows, closes)
    vol_r = _vol_ratio(volumes)
    near_high = _near_52w_high(closes)
    price = round(closes[-1], 2) if closes else None

    # Simple tiering
    if rs >= 15 and near_high and vol_r >= 1.2:
        conviction = "TRADE"
        section = "actionable"
    elif rs >= 6 and near_high:
        conviction = "LEADER"
        section = "watch"
    elif rs >= 0:
        conviction = "WATCH"
        section = "review"
    else:
        conviction = "AVOID"
        section = "review"

    return {
        "ticker": ticker,
        "price": price,
        "rs_score": rs,
        "atr_pct": atr,
        "vol_ratio": vol_r,
        "near_52w_high": near_high,
        "conviction": conviction,
        "section": section,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


def build_brief(dry_run: bool = False) -> Dict[str, Any]:
    """Download data, compute signals, return brief dict."""
    from src.services.rs_data_service import (
        fetch_closes_batch,
        fetch_single,
    )  # noqa: PLC0415

    today = date.today().isoformat()
    logger.info("Fetching SPY benchmark …")
    spy_df = fetch_single(SPY, period=PERIODS["trend"])
    if spy_df is None or spy_df.empty:
        logger.error("Cannot fetch SPY — aborting")
        return {}
    spy_closes = spy_df["Close"].dropna().values.flatten().tolist()
    spy_closes = [float(x) for x in spy_closes]

    logger.info("Fetching universe (%d tickers) …", len(UNIVERSE))
    batch = fetch_closes_batch(UNIVERSE, period=PERIODS["trend"])

    brief: Dict[str, Any] = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "universe_count": len(UNIVERSE),
        "actionable": [],
        "watch": [],
        "review": [],
        "metadata": {
            "generator": "generate_brief.py",
            "spy_close": spy_closes[-1] if spy_closes else None,
        },
    }

    for ticker in UNIVERSE:
        df = batch.get(ticker)
        if df is None or df.empty:
            logger.warning("No data for %s — skipping", ticker)
            continue

        try:
            closes = [float(x) for x in df["Close"].dropna().values.flatten()]
            highs = [float(x) for x in df["High"].dropna().values.flatten()]
            lows = [float(x) for x in df["Low"].dropna().values.flatten()]
            volumes = [float(x) for x in df["Volume"].dropna().values.flatten()]
        except Exception as exc:
            logger.warning("Data parse error for %s: %s", ticker, exc)
            continue

        sig = _classify_ticker(ticker, closes, highs, lows, volumes, spy_closes)
        section = sig.pop("section")
        brief[section].append(sig)

    # Sort each section by rs_score desc
    for sec in ("actionable", "watch", "review"):
        brief[sec].sort(key=lambda x: x.get("rs_score", 0), reverse=True)

    logger.info(
        "Brief built: %d actionable, %d watch, %d review",
        len(brief["actionable"]),
        len(brief["watch"]),
        len(brief["review"]),
    )
    return brief


def save_brief(brief: Dict[str, Any]) -> Path:
    out_dir = ROOT / "data"
    out_dir.mkdir(exist_ok=True)
    today = brief.get("date", date.today().isoformat())
    out_path = out_dir / f"brief-{today}.json"
    with open(out_path, "w") as f:
        json.dump(brief, f, indent=2)
    logger.info("Saved → %s", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily brief JSON")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print JSON only, do not write"
    )
    args = parser.parse_args()

    brief = build_brief(dry_run=args.dry_run)
    if not brief:
        sys.exit(1)

    if args.dry_run:
        print(json.dumps(brief, indent=2))
    else:
        save_brief(brief)


if __name__ == "__main__":
    main()
