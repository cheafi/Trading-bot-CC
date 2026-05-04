"""
Morning Brief Router — Sprint 64
===================================
/api/brief — Top 3 setups, regime, portfolio heat, risk.
/api/brief/diff — What changed since yesterday.
/api/brief/regime — Current regime with history.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/brief", tags=["brief"])


@router.get("")
async def morning_brief():
    """
    Morning brief: regime, top setups, portfolio heat, risk.
    Loads the latest data/brief-*.json for real actionable signals.
    """
    import glob
    import json
    import os

    from src.services.regime_service import RegimeService

    regime = RegimeService.get()

    # Load latest brief file for real setups
    from src.services.brief_data_service import load_brief

    brief_data = load_brief()

    actionable = brief_data.get("actionable", [])
    watch = brief_data.get("watch", [])
    top_setups = actionable[:5] if actionable else watch[:3]

    return {
        "regime": regime,
        "date": brief_data.get("date"),
        "headline": brief_data.get("headline", "No brief available"),
        "top_setups": top_setups,
        "portfolio_heat": {"positions": len(brief_data.get("holdings_with_signals", [])), "max": 10},
        "risk_watch": regime.get("signals", [])[:3],
        "synthetic": regime.get("synthetic", False),
    }


@router.get("/diff")
async def decision_diff():
    """What changed since yesterday."""
    try:
        from src.engines.decision_tracker import DecisionTracker
        tracker = DecisionTracker()
        diffs = tracker.get_diffs()
        tracker.close()
        from collections import Counter

        counts = Counter(d["change"] for d in diffs)
        return {
            "diffs": diffs,
            "count": len(diffs),
            "upgrades": counts.get("UPGRADE", 0),
            "downgrades": counts.get("DOWNGRADE", 0),
            "new": counts.get("NEW", 0),
        }
    except Exception as e:
        return {"error": str(e), "diffs": []}


@router.get("/regime")
async def regime_status():
    """Current regime with history."""
    try:
        from src.engines.decision_tracker import DecisionTracker
        tracker = DecisionTracker()
        history = tracker.get_regime_history(limit=10)
        tracker.close()
        return {
            "current": history[0] if history else None,
            "history": history,
        }
    except Exception as e:
        return {"error": str(e), "current": None, "history": []}


@router.get("/strategies")
async def available_strategies():
    """List available fund strategies."""
    from src.engines.fund_builder import STRATEGY_PROFILES
    return {"strategies": STRATEGY_PROFILES}


@router.get("/changelog")
async def changelog():
    """Recent changes since last deployment."""
    import json
    import os
    import subprocess

    entries = []

    # Try git first (works locally, not in Docker)
    for cwd in [
        "/app",
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(__file__))
            )
        ),
    ]:
        try:
            out = subprocess.check_output(
                ["git", "log", "--oneline", "-20"],
                cwd=cwd,
                text=True,
                timeout=5,
                stderr=subprocess.DEVNULL,
            ).strip()
            for line in out.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    entries.append({
                        "hash": parts[0],
                        "message": parts[1],
                    })
            if entries:
                break
        except Exception:
            pass

    # Fallback: baked changelog.json (Docker)
    if not entries:
        for p in ["/app/changelog.json", "changelog.json"]:
            if os.path.isfile(p):
                try:
                    with open(p) as f:
                        entries = json.load(f)
                    break
                except Exception:
                    pass
    return {"entries": entries, "count": len(entries)}


@router.get("/circuit-breaker")
async def circuit_breaker_status():
    """Check drawdown circuit breaker status using real portfolio heat engine."""
    from src.engines.drawdown_breaker import DrawdownCircuitBreaker
    from src.engines.portfolio_heat import get_portfolio_heat_engine

    breaker = DrawdownCircuitBreaker()
    engine = get_portfolio_heat_engine()
    snap = engine.snapshot()

    # Derive equity proxy from portfolio heat snapshot
    # _peak_equity and _current_equity are initialised at 100 (index base)
    current = float(getattr(engine, "_current_equity", 100.0))
    peak = float(getattr(engine, "_peak_equity", current))
    # period_start: approximate as peak minus recorded drawdown
    period_start = peak  # conservative: week started at peak

    result = breaker.check(
        current_value=current,
        peak_value=peak,
        period_start_value=period_start,
    )
    open_positions = len(getattr(engine, "_positions", {}))
    return {
        **result.to_dict(),
        "portfolio": {
            "current_equity": round(current, 2),
            "peak_equity": round(peak, 2),
            "open_positions": open_positions,
            "gross_exposure_pct": round(snap.gross_exposure_pct, 1),
        },
    }


@router.get("/performance-tracker")
async def performance_tracker(request: Request):
    """
    Week opportunities tracker: all tickers seen in brief files,
    showing % change from first-seen date to today vs SPY (index)
    and their sector ETF (industry benchmark).
    """
    import glob
    import json
    import os
    from datetime import datetime

    svc = getattr(getattr(request, "app", None) and request.app.state, "market_data", None)
    if svc is None:
        return {"rows": [], "error": "market_data service not initialised"}

    brief_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    files = sorted(glob.glob(os.path.join(brief_dir, "brief-*.json")))
    if not files:
        return {"rows": [], "error": "No brief files found"}

    # Collect first-seen date and action for each ticker
    seen: dict = {}
    for fp in files:
        try:
            with open(fp) as f:
                d = json.load(f)
        except Exception:
            continue
        date_str = d.get("date", "")
        for section in ("actionable", "watch", "review"):
            for item in d.get(section, []):
                t = item.get("ticker", "").upper()
                if t and t not in seen:
                    seen[t] = {
                        "ticker": t,
                        "first_seen": date_str,
                        "action": item.get("action", section.upper()),
                        "note": item.get("note", ""),
                        "entry_rsi": (item.get("indicators") or {}).get("rsi"),
                    }

    if not seen:
        return {"rows": [], "error": "No tickers in brief files"}

    # Sector ETF map for industry benchmark
    sector_etf = {
        "NVDA": "SMH",
        "AMD": "SMH",
        "INTC": "SMH",
        "TSM": "SMH",
        "AAPL": "XLK",
        "MSFT": "XLK",
        "GOOGL": "XLK",
        "META": "XLK",
        "AMZN": "XLY",
        "TSLA": "XLY",
        "JPM": "XLF",
        "BAC": "XLF",
        "GS": "XLF",
        "JNJ": "XLV",
        "PFE": "XLV",
        "UNH": "XLV",
        "XOM": "XLE",
        "CVX": "XLE",
        "NFLX": "XLC",
        "DIS": "XLC",
    }
    default_sector = "SPY"

    tickers_list = list(seen.keys())
    # Find earliest first-seen date for download window
    dates = [v["first_seen"] for v in seen.values() if v["first_seen"]]
    if not dates:
        return {"rows": [], "error": "No dates in brief files"}

    start = min(dates)
    # Download price data for all tickers + SPY
    needed = list(set(tickers_list + list(set(sector_etf.values())) + ["SPY"]))
    import asyncio as _asyncio
    # Fetch all symbols concurrently through the cached MarketDataService
    _tasks = {sym: svc.get_history(sym, period="2y", interval="1d") for sym in needed}
    _results = await _asyncio.gather(*_tasks.values(), return_exceptions=True)
    _frames: dict = {}
    for sym, res in zip(_tasks.keys(), _results):
        if isinstance(res, Exception) or res is None or res.empty:
            continue
        _frames[sym] = res["Close"].dropna().rename(sym)
    if not _frames:
        return {"rows": [], "error": "Could not fetch price data"}
    import pandas as _pd
    closes = _pd.concat(_frames.values(), axis=1)

    today_str = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for t, meta in seen.items():
        fs = meta["first_seen"]
        if not fs:
            continue
        etf = sector_etf.get(t, default_sector)
        try:
            # Get entry price (first available close on or after first_seen)
            col_t   = t   if t   in closes.columns else None
            col_spy = "SPY" if "SPY" in closes.columns else None
            col_etf = etf  if etf  in closes.columns else None
            if col_t is None:
                continue

            subset = closes[closes.index >= fs]
            if subset.empty:
                continue

            entry_price = float(subset[col_t].dropna().iloc[0])
            current_price = float(closes[col_t].dropna().iloc[-1])
            pct_chg = round((current_price - entry_price) / entry_price * 100, 2)

            spy_entry = float(subset[col_spy].dropna().iloc[0]) if col_spy else None
            spy_curr = float(closes[col_spy].dropna().iloc[-1]) if col_spy else None
            spy_chg = (
                round((spy_curr - spy_entry) / spy_entry * 100, 2)
                if spy_entry
                else None
            )

            etf_entry = float(subset[col_etf].dropna().iloc[0]) if col_etf else None
            etf_curr = float(closes[col_etf].dropna().iloc[-1]) if col_etf else None
            etf_chg = (
                round((etf_curr - etf_entry) / etf_entry * 100, 2)
                if etf_entry
                else None
            )

            alpha_vs_spy = round(pct_chg - spy_chg, 2) if spy_chg is not None else None
            alpha_vs_sector = (
                round(pct_chg - etf_chg, 2) if etf_chg is not None else None
            )

            rows.append(
                {
                    "ticker": t,
                    "first_seen": fs,
                    "action": meta["action"],
                    "entry_price": round(entry_price, 2),
                    "current_price": round(current_price, 2),
                    "pct_chg": pct_chg,
                    "spy_chg": spy_chg,
                    "sector_etf": etf,
                    "sector_chg": etf_chg,
                    "alpha_vs_spy": alpha_vs_spy,
                    "alpha_vs_sector": alpha_vs_sector,
                    "note": meta["note"],
                    "entry_rsi": meta["entry_rsi"],
                }
            )
        except Exception:
            continue

    rows.sort(key=lambda r: r["pct_chg"], reverse=True)
    return {
        "rows": rows,
        "count": len(rows),
        "as_of": today_str,
        "synthetic": False,  # performance-tracker uses MarketDataService (real data)
    }
