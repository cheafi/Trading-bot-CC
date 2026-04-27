"""
Morning Brief & Fund API Router — Sprint 62
=============================================
New endpoints:
  GET  /api/brief          — Morning brief (regime, top setups, heat, risk)
  GET  /api/stock-vs-spy   — Compare any stock vs SPY
  POST /api/fund/create    — Create a custom fund
  GET  /api/fund/{name}    — Get fund performance report
  POST /api/fund/{name}/position — Add position to fund
  GET  /api/fund/strategies — List available strategies
"""

from __future__ import annotations
from fastapi import APIRouter, Query
from typing import Optional
import json, os, time
from datetime import datetime

router = APIRouter(prefix="/api", tags=["brief", "fund"])

# ── Morning Brief ──

@router.get("/brief")
async def morning_brief():
    """
    Daily morning brief: current regime, top setups, portfolio heat, risks.
    The single most useful daily workflow endpoint.
    """
    from src.engines.macro_regime_engine import MacroRegimeEngine

    brief = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
    }

    # Try to load latest brief data
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
    )
    brief_files = sorted(
        [f for f in os.listdir(data_dir) if f.startswith("brief-")],
        reverse=True,
    ) if os.path.isdir(data_dir) else []

    if brief_files:
        try:
            with open(os.path.join(data_dir, brief_files[0])) as f:
                latest = json.load(f)
            brief["latest_brief"] = latest
            brief["brief_date"] = brief_files[0].replace("brief-", "").replace(".json", "")
        except Exception:
            pass

    # Regime (demo with synthetic data if no real data)
    engine = MacroRegimeEngine()
    # In production, these would come from a data service
    brief["regime"] = {
        "note": "Wire MacroRegimeEngine to live SPY/QQQ/VIX data for real regime",
        "engine": "MacroRegimeEngine available",
    }

    brief["top_actions"] = [
        "1. Check regime before any new positions",
        "2. Review top-ranked signals in /api/recommendations",
        "3. Check portfolio heat vs limits",
    ]

    return brief


# ── Stock vs SPY ──

@router.get("/stock-vs-spy")
async def stock_vs_spy(
    ticker: str = Query(..., description="Stock ticker"),
    stock_prices: str = Query(
        "", description="Comma-separated stock closes (recent last)"
    ),
    spy_prices: str = Query(
        "", description="Comma-separated SPY closes (recent last)"
    ),
):
    """
    Compare a stock's performance vs SPY.
    Pass daily closes as comma-separated values, or use with a data feed.
    """
    from src.engines.macro_regime_engine import StockVsSPY

    if not stock_prices or not spy_prices:
        return {
            "error": "Provide stock_prices and spy_prices as comma-separated closes",
            "example": "/api/stock-vs-spy?ticker=NVDA&stock_prices=100,102,105&spy_prices=500,502,504",
            "note": "In production, wire to market data service for automatic price lookup",
        }

    try:
        s_prices = [float(x.strip()) for x in stock_prices.split(",") if x.strip()]
        b_prices = [float(x.strip()) for x in spy_prices.split(",") if x.strip()]
    except ValueError:
        return {"error": "Invalid price data — use comma-separated numbers"}

    result = StockVsSPY.compare(s_prices, b_prices, ticker=ticker.upper())
    return result


# ── Fund Builder API ──

# In-memory fund store (in production, use SQLite/Postgres)
_funds: dict[str, dict] = {}


def _get_fund_store_path() -> str:
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
    )
    return os.path.join(data_dir, "funds.json")


def _load_funds():
    global _funds
    path = _get_fund_store_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                _funds = json.load(f)
        except Exception:
            _funds = {}


def _save_funds():
    path = _get_fund_store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(_funds, f, indent=2)


@router.get("/fund/strategies")
async def list_strategies():
    """List all available strategies with their profiles."""
    from src.engines.fund_builder import STRATEGY_PROFILES
    return {
        "strategies": [
            {"name": k, **v} for k, v in STRATEGY_PROFILES.items()
        ]
    }


@router.post("/fund/create")
async def create_fund(
    name: str = Query(..., description="Fund name"),
    capital: float = Query(100000, description="Starting capital"),
    strategies: str = Query(
        "", description="Comma-sep strategy:weight pairs, e.g. MOMENTUM:0.4,VCP:0.3,BREAKOUT:0.3"
    ),
    spy_price: float = Query(0, description="SPY price at fund inception"),
):
    """Create a new custom fund with selected strategies."""
    from src.engines.fund_builder import FundBuilder

    _load_funds()

    fund = FundBuilder(name=name, starting_capital=capital)
    fund.spy_entry_price = spy_price

    if strategies:
        for part in strategies.split(","):
            part = part.strip()
            if ":" in part:
                strat, weight = part.split(":", 1)
                fund.add_strategy(strat.strip().upper(), float(weight.strip()))
            else:
                fund.add_strategy(part.strip().upper(), 0.0)

    _funds[name] = fund.to_dict()
    _save_funds()

    return {
        "status": "created",
        "fund": fund.to_dict(),
        "strategies": fund.get_strategies(),
    }


@router.get("/fund/{name}")
async def get_fund(
    name: str,
    spy_current: float = Query(0, description="Current SPY price for benchmark"),
    prices: str = Query("", description="ticker:price pairs, e.g. NVDA:140,CRWD:410"),
):
    """Get fund performance report vs SPY."""
    from src.engines.fund_builder import FundBuilder

    _load_funds()
    if name not in _funds:
        return {"error": f"Fund '{name}' not found", "available": list(_funds.keys())}

    fund = FundBuilder.from_dict(_funds[name])

    current_prices = {}
    if prices:
        for part in prices.split(","):
            if ":" in part:
                t, p = part.split(":", 1)
                current_prices[t.strip().upper()] = float(p.strip())

    report = fund.performance_report(
        current_prices,
        spy_current=spy_current,
        spy_entry=fund.spy_entry_price,
    )
    return report


@router.post("/fund/{name}/position")
async def add_fund_position(
    name: str,
    ticker: str = Query(...),
    entry_price: float = Query(...),
    shares: int = Query(...),
    strategy: str = Query(...),
    stop_price: float = Query(0),
    target_price: float = Query(0),
):
    """Add a position to an existing fund."""
    from src.engines.fund_builder import FundBuilder

    _load_funds()
    if name not in _funds:
        return {"error": f"Fund '{name}' not found"}

    fund = FundBuilder.from_dict(_funds[name])
    try:
        pos = fund.add_position(
            ticker=ticker.upper(),
            entry_price=entry_price,
            shares=shares,
            strategy=strategy.upper(),
            stop_price=stop_price,
            target_price=target_price,
        )
    except ValueError as e:
        return {"error": str(e)}

    _funds[name] = fund.to_dict()
    _save_funds()

    return {
        "status": "position_added",
        "position": pos.to_dict(entry_price),
        "cash_remaining": round(fund.cash, 2),
    }


@router.post("/fund/{name}/close")
async def close_fund_position(
    name: str,
    ticker: str = Query(...),
    exit_price: float = Query(...),
    reason: str = Query("manual"),
):
    """Close a position in the fund."""
    from src.engines.fund_builder import FundBuilder

    _load_funds()
    if name not in _funds:
        return {"error": f"Fund '{name}' not found"}

    fund = FundBuilder.from_dict(_funds[name])
    closed = fund.close_position(ticker.upper(), exit_price, exit_reason=reason)

    if not closed:
        return {"error": f"No open position for {ticker.upper()}"}

    _funds[name] = fund.to_dict()
    _save_funds()

    return {
        "status": "position_closed",
        "pnl": round(closed.pnl, 2),
        "pnl_pct": round(closed.pnl_pct, 2),
        "cash_remaining": round(fund.cash, 2),
    }
