"""
ExecutionCostEngine — Sprint 99
================================
Models realistic execution costs and tracks fill quality per trade.

Components:
  - TWAP/VWAP slippage estimators (ATR-based + volume-impact)
  - Commission model ($0.005/share, min $1.00; $0.65/contract options)
  - FillRecord persistence (SQLite via fund_persistence schema)
  - FillQualityTracker — rolling slippage vs benchmark, best-ex stats

Usage::

    engine = ExecutionCostEngine()

    # Estimate before entry
    est = engine.estimate(ticker="AAPL", side="BUY", shares=100,
                          price=185.00, atr=2.50, adv=65_000_000)

    # Record actual fill
    engine.record_fill(ticker="AAPL", side="BUY", shares=100,
                       expected_price=185.00, fill_price=185.08,
                       commission=0.50, strategy="TWAP")

    # Get best-ex summary
    stats = engine.quality_stats(lookback_days=30)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.risk_limits import RISK

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_DB_PATH = Path("data") / "fund_portfolio.db"
_COMMISSION_PER_SHARE: float = 0.005  # Interactive Brokers tiered
_COMMISSION_MIN: float = 1.00
_COMMISSION_OPTIONS: float = 0.65  # per contract
_MARKET_IMPACT_COEFF: float = 0.10  # fraction of ATR * (order_size/ADV)^0.5


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class CostEstimate:
    """Pre-trade cost breakdown."""

    ticker: str
    side: str  # BUY | SELL
    shares: int
    price: float
    atr: float
    adv: float  # average daily volume (shares)

    # Computed
    commission: float = 0.0
    spread_cost: float = 0.0  # half-spread estimate (ATR/50)
    market_impact: float = 0.0  # price impact from order size
    twap_slippage: float = 0.0  # expected TWAP drift vs arrival price
    vwap_slippage: float = 0.0  # expected VWAP shortfall
    total_cost_bps: float = 0.0
    total_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FillRecord:
    """Actual fill outcome for post-trade analysis."""

    id: Optional[int] = None
    ticker: str = ""
    side: str = ""  # BUY | SELL
    shares: int = 0
    expected_price: float = 0.0
    fill_price: float = 0.0
    commission: float = 0.0
    strategy: str = "MARKET"  # TWAP | VWAP | MARKET | LIMIT
    slippage_bps: float = 0.0  # (fill - expected) / expected * 10000
    slippage_usd: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── DB helpers ────────────────────────────────────────────────────────────────


def _ensure_table() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_fills (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker         TEXT    NOT NULL,
                side           TEXT    NOT NULL,
                shares         INTEGER NOT NULL,
                expected_price REAL    NOT NULL,
                fill_price     REAL    NOT NULL,
                commission     REAL    NOT NULL DEFAULT 0,
                strategy       TEXT    NOT NULL DEFAULT 'MARKET',
                slippage_bps   REAL    NOT NULL DEFAULT 0,
                slippage_usd   REAL    NOT NULL DEFAULT 0,
                timestamp      TEXT    NOT NULL
            )
            """)
        conn.commit()


@contextmanager
def _db():
    _DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


_ensure_table()


# ── Core engine ───────────────────────────────────────────────────────────────


class ExecutionCostEngine:
    """
    Estimates and tracks execution costs with TWAP/VWAP models.

    Cost components:
      1. Commission  — $0.005/share, min $1.00
      2. Half-spread — ATR / 50  (proxy for bid-ask)
      3. Market impact — _MARKET_IMPACT_COEFF × ATR × √(shares/ADV)
      4. TWAP slippage — 0.5 × ATR × √(T/390) where T = execution minutes
      5. VWAP shortfall — slightly lower than TWAP (assumes better fill in
         high-volume periods)
    """

    def estimate(
        self,
        ticker: str,
        side: str,
        shares: int,
        price: float,
        atr: float,
        adv: float,
        twap_minutes: int = 30,
    ) -> CostEstimate:
        """
        Pre-trade cost estimate.

        Args:
            ticker: Ticker symbol
            side: "BUY" or "SELL"
            shares: Number of shares
            price: Current market price
            atr: Average True Range (daily)
            adv: Average daily volume in shares
            twap_minutes: Intended execution window for TWAP
        """
        est = CostEstimate(
            ticker=ticker,
            side=side,
            shares=shares,
            price=price,
            atr=atr,
            adv=max(adv, 1),
        )

        # 1. Commission
        est.commission = max(_COMMISSION_PER_SHARE * shares, _COMMISSION_MIN)

        # 2. Half-spread (ATR / 50 per share, ~2bps of ATR)
        est.spread_cost = (atr / 50.0) * shares

        # 3. Market impact
        participation = shares / (adv * (twap_minutes / 390.0))  # fraction of volume
        est.market_impact = _MARKET_IMPACT_COEFF * atr * (participation**0.5) * shares

        # 4. TWAP slippage (drift over execution window)
        est.twap_slippage = 0.5 * atr * ((twap_minutes / 390.0) ** 0.5) * shares

        # 5. VWAP shortfall (empirically ~80% of TWAP drift)
        est.vwap_slippage = est.twap_slippage * 0.80

        # Total
        est.total_cost_usd = (
            est.commission + est.spread_cost + est.market_impact + est.twap_slippage
        )
        notional = price * shares
        est.total_cost_bps = (
            (est.total_cost_usd / notional * 10000.0) if notional > 0 else 0.0
        )

        logger.debug(
            "Cost estimate %s %d %s @ %.2f: total=%.2f (%.1fbps)",
            side,
            shares,
            ticker,
            price,
            est.total_cost_usd,
            est.total_cost_bps,
        )
        return est

    def estimate_options(
        self,
        contracts: int,
        premium: float,
        underlying_atr: float,
    ) -> CostEstimate:
        """Simplified cost estimate for options contracts."""
        commission = contracts * _COMMISSION_OPTIONS
        # Options spread is wider — proxy as 2% of premium per contract
        spread_cost = 0.02 * premium * contracts * 100
        total_cost_usd = commission + spread_cost
        notional = premium * contracts * 100
        est = CostEstimate(
            ticker="OPTIONS",
            side="BUY",
            shares=contracts * 100,
            price=premium,
            atr=underlying_atr,
            adv=0,
            commission=commission,
            spread_cost=spread_cost,
            total_cost_usd=total_cost_usd,
            total_cost_bps=(
                (total_cost_usd / notional * 10000.0) if notional > 0 else 0.0
            ),
        )
        return est

    def record_fill(
        self,
        ticker: str,
        side: str,
        shares: int,
        expected_price: float,
        fill_price: float,
        commission: float = 0.0,
        strategy: str = "MARKET",
    ) -> FillRecord:
        """
        Record an actual fill and compute realised slippage.

        Slippage sign convention:
          - BUY: positive slippage = filled higher than expected (bad)
          - SELL: positive slippage = filled lower than expected (bad)
        """
        if side.upper() == "BUY":
            slip_per_share = fill_price - expected_price
        else:
            slip_per_share = expected_price - fill_price

        slippage_usd = slip_per_share * shares
        notional = expected_price * shares
        slippage_bps = (
            (slip_per_share / expected_price * 10000.0) if expected_price > 0 else 0.0
        )

        if commission == 0.0:
            commission = max(_COMMISSION_PER_SHARE * shares, _COMMISSION_MIN)

        rec = FillRecord(
            ticker=ticker,
            side=side.upper(),
            shares=shares,
            expected_price=expected_price,
            fill_price=fill_price,
            commission=commission,
            strategy=strategy.upper(),
            slippage_bps=round(slippage_bps, 2),
            slippage_usd=round(slippage_usd, 4),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        with _db() as conn:
            cur = conn.execute(
                """
                INSERT INTO execution_fills
                    (ticker, side, shares, expected_price, fill_price,
                     commission, strategy, slippage_bps, slippage_usd, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.ticker,
                    rec.side,
                    rec.shares,
                    rec.expected_price,
                    rec.fill_price,
                    rec.commission,
                    rec.strategy,
                    rec.slippage_bps,
                    rec.slippage_usd,
                    rec.timestamp,
                ),
            )
            conn.commit()
            rec.id = cur.lastrowid

        logger.info(
            "Fill recorded: %s %d %s exp=%.4f fill=%.4f slip=%.2fbps",
            side,
            shares,
            ticker,
            expected_price,
            fill_price,
            slippage_bps,
        )
        return rec

    def get_fills(
        self,
        ticker: Optional[str] = None,
        lookback_days: int = 30,
        strategy: Optional[str] = None,
        limit: int = 200,
    ) -> List[FillRecord]:
        """Retrieve fill records with optional filters."""
        conditions: List[str] = [
            f"timestamp >= datetime('now', '-{lookback_days} days')"
        ]
        params: List[Any] = []
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker.upper())
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy.upper())

        where = " AND ".join(conditions)
        with _db() as conn:
            rows = conn.execute(
                f"SELECT * FROM execution_fills WHERE {where} ORDER BY timestamp DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [FillRecord(**dict(r)) for r in rows]

    def quality_stats(
        self,
        ticker: Optional[str] = None,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Best-ex summary statistics:
          - avg/median/p95 slippage in bps
          - breakdown by strategy (TWAP vs VWAP vs MARKET)
          - total commission paid
          - % fills with negative slippage (favourable fills)
        """
        fills = self.get_fills(ticker=ticker, lookback_days=lookback_days)
        if not fills:
            return {
                "fills": 0,
                "avg_slippage_bps": None,
                "median_slippage_bps": None,
                "p95_slippage_bps": None,
                "pct_favourable": None,
                "total_commission_usd": 0.0,
                "by_strategy": {},
            }

        slippages = [f.slippage_bps for f in fills]
        slippages_sorted = sorted(slippages)
        n = len(slippages_sorted)
        avg = sum(slippages) / n
        median = slippages_sorted[n // 2]
        p95 = slippages_sorted[min(int(n * 0.95), n - 1)]
        favourable = sum(1 for s in slippages if s <= 0) / n * 100.0
        total_comm = sum(f.commission for f in fills)

        by_strategy: Dict[str, Dict[str, Any]] = {}
        for f in fills:
            s = f.strategy
            if s not in by_strategy:
                by_strategy[s] = {"count": 0, "total_slippage_bps": 0.0}
            by_strategy[s]["count"] += 1
            by_strategy[s]["total_slippage_bps"] += f.slippage_bps
        for s in by_strategy:
            cnt = by_strategy[s]["count"]
            by_strategy[s]["avg_slippage_bps"] = round(
                by_strategy[s]["total_slippage_bps"] / cnt, 2
            )

        return {
            "fills": n,
            "lookback_days": lookback_days,
            "avg_slippage_bps": round(avg, 2),
            "median_slippage_bps": round(median, 2),
            "p95_slippage_bps": round(p95, 2),
            "pct_favourable": round(favourable, 1),
            "total_commission_usd": round(total_comm, 2),
            "by_strategy": by_strategy,
        }


# Module-level singleton
_engine_instance: Optional[ExecutionCostEngine] = None


def get_execution_engine() -> ExecutionCostEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ExecutionCostEngine()
    return _engine_instance
