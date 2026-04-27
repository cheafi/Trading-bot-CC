"""
FundBuilder — Sprint 62
========================
Build-your-own fund: select strategies, allocate weights, track
performance vs SPY benchmark.

Strategies available:
  - MOMENTUM     : Buy RS leaders, ride trends
  - VCP          : Volatility Contraction Pattern setups
  - MEAN_REVERT  : Oversold bounces in uptrending stocks
  - BREAKOUT     : Buy breakouts above resistance with volume
  - DEFENSIVE    : Low-beta, high-quality, dividend-paying
  - BALANCED     : Equal mix of all strategies

Usage:
    fund = FundBuilder("My Growth Fund")
    fund.add_strategy("MOMENTUM", weight=0.40)
    fund.add_strategy("VCP", weight=0.35)
    fund.add_strategy("BREAKOUT", weight=0.25)

    # Add holdings (ticker, entry_price, shares, strategy, entry_date)
    fund.add_position("NVDA", 125.0, 80, "MOMENTUM", "2026-01-15")
    fund.add_position("CRWD", 380.0, 26, "VCP", "2026-02-01")

    # Update current prices and get performance vs SPY
    prices = {"NVDA": 140.0, "CRWD": 410.0, "SPY": 530.0}
    report = fund.performance_report(prices, spy_entry=500.0)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ── Strategy Definitions ──

STRATEGY_PROFILES = {
    "MOMENTUM": {
        "description": "Buy relative strength leaders in confirmed uptrends",
        "criteria": ["RS rank > 80", "Above SMA50", "Volume expanding"],
        "typical_hold": "4-12 weeks",
        "risk_level": "MEDIUM-HIGH",
        "stop_method": "Trailing 20d low",
    },
    "VCP": {
        "description": "Volatility Contraction Patterns — tightening bases before breakout",
        "criteria": ["2+ contractions", "Volume dry-up at pivot", "RS > 60"],
        "typical_hold": "2-8 weeks",
        "risk_level": "MEDIUM",
        "stop_method": "Below pivot low",
    },
    "MEAN_REVERT": {
        "description": "Oversold bounces in stocks with strong long-term uptrends",
        "criteria": ["RSI < 30", "Above SMA200", "Volume spike on reversal"],
        "typical_hold": "1-3 weeks",
        "risk_level": "MEDIUM",
        "stop_method": "Below recent swing low",
    },
    "BREAKOUT": {
        "description": "Buy breakouts above resistance with volume confirmation",
        "criteria": ["Breaking multi-week resistance", "Volume > 1.5x avg", "Trend up"],
        "typical_hold": "2-6 weeks",
        "risk_level": "MEDIUM-HIGH",
        "stop_method": "Below breakout level",
    },
    "DEFENSIVE": {
        "description": "Low-beta, quality names for capital preservation",
        "criteria": ["Beta < 0.8", "Dividend yield > 1.5%", "Low drawdown"],
        "typical_hold": "3-12 months",
        "risk_level": "LOW",
        "stop_method": "Below SMA200",
    },
    "BALANCED": {
        "description": "Equal-weight mix across all strategies",
        "criteria": ["Diversified"],
        "typical_hold": "Varies",
        "risk_level": "MEDIUM",
        "stop_method": "Per-strategy",
    },
}


@dataclass
class FundPosition:
    """A single position in the fund."""

    ticker: str
    entry_price: float
    shares: int
    strategy: str
    entry_date: str
    stop_price: float = 0.0
    target_price: float = 0.0
    notes: str = ""

    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.shares

    def current_value(self, price: float) -> float:
        return price * self.shares

    def pnl(self, price: float) -> float:
        return (price - self.entry_price) * self.shares

    def pnl_pct(self, price: float) -> float:
        if self.entry_price == 0:
            return 0.0
        return (price - self.entry_price) / self.entry_price * 100

    def to_dict(self, current_price: float = 0.0) -> dict:
        d = {
            "ticker": self.ticker,
            "strategy": self.strategy,
            "entry_price": self.entry_price,
            "shares": self.shares,
            "entry_date": self.entry_date,
            "cost_basis": round(self.cost_basis, 2),
        }
        if current_price > 0:
            d["current_price"] = current_price
            d["current_value"] = round(self.current_value(current_price), 2)
            d["pnl"] = round(self.pnl(current_price), 2)
            d["pnl_pct"] = round(self.pnl_pct(current_price), 2)
        if self.stop_price:
            d["stop_price"] = self.stop_price
        if self.target_price:
            d["target_price"] = self.target_price
        return d


@dataclass
class ClosedPosition:
    """A position that has been closed."""

    ticker: str
    strategy: str
    entry_price: float
    exit_price: float
    shares: int
    entry_date: str
    exit_date: str
    exit_reason: str = ""  # "stop_hit", "target_reached", "manual", "signal_change"

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.exit_price - self.entry_price) / self.entry_price * 100


class FundBuilder:
    """
    Build and track a custom fund with selectable strategies.
    Measure performance against SPY benchmark.
    """

    def __init__(self, name: str = "My Fund", starting_capital: float = 100000.0):
        self.name = name
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.strategies: dict[str, float] = {}  # strategy → target weight
        self.positions: list[FundPosition] = []
        self.closed: list[ClosedPosition] = []
        self.spy_entry_price: float = 0.0  # SPY price at fund inception
        self.created_at: str = datetime.now().strftime("%Y-%m-%d")

    # ── Strategy management ──

    def add_strategy(self, name: str, weight: float = 0.0) -> None:
        """Add a strategy to the fund with target allocation weight."""
        if name not in STRATEGY_PROFILES and name != "CUSTOM":
            raise ValueError(
                f"Unknown strategy: {name}. Available: {list(STRATEGY_PROFILES.keys())}"
            )
        self.strategies[name] = weight

    def remove_strategy(self, name: str) -> None:
        self.strategies.pop(name, None)

    def get_strategies(self) -> list[dict]:
        """List configured strategies with their profiles."""
        result = []
        for name, weight in self.strategies.items():
            profile = STRATEGY_PROFILES.get(name, {"description": "Custom strategy"})
            result.append(
                {
                    "name": name,
                    "target_weight": round(weight * 100, 1),
                    **profile,
                }
            )
        return result

    # ── Position management ──

    def add_position(
        self,
        ticker: str,
        entry_price: float,
        shares: int,
        strategy: str,
        entry_date: str = "",
        stop_price: float = 0.0,
        target_price: float = 0.0,
    ) -> FundPosition:
        """Add a position to the fund."""
        cost = entry_price * shares
        if cost > self.cash:
            raise ValueError(
                f"Insufficient cash: need ${cost:.0f}, have ${self.cash:.0f}"
            )

        pos = FundPosition(
            ticker=ticker,
            entry_price=entry_price,
            shares=shares,
            strategy=strategy,
            entry_date=entry_date or datetime.now().strftime("%Y-%m-%d"),
            stop_price=stop_price,
            target_price=target_price,
        )
        self.positions.append(pos)
        self.cash -= cost
        return pos

    def close_position(
        self,
        ticker: str,
        exit_price: float,
        exit_date: str = "",
        exit_reason: str = "manual",
    ) -> ClosedPosition | None:
        """Close a position and record it."""
        for i, pos in enumerate(self.positions):
            if pos.ticker == ticker:
                closed = ClosedPosition(
                    ticker=pos.ticker,
                    strategy=pos.strategy,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    shares=pos.shares,
                    entry_date=pos.entry_date,
                    exit_date=exit_date or datetime.now().strftime("%Y-%m-%d"),
                    exit_reason=exit_reason,
                )
                self.closed.append(closed)
                self.cash += exit_price * pos.shares
                self.positions.pop(i)
                return closed
        return None

    # ── Performance ──

    def total_value(self, prices: dict[str, float]) -> float:
        """Current total fund value (cash + positions)."""
        invested = sum(
            pos.current_value(prices.get(pos.ticker, pos.entry_price))
            for pos in self.positions
        )
        return self.cash + invested

    def performance_report(
        self,
        current_prices: dict[str, float],
        spy_current: float = 0.0,
        spy_entry: float = 0.0,
    ) -> dict:
        """
        Full performance report vs SPY.

        Args:
            current_prices: {ticker: current_price} for all holdings
            spy_current: Current SPY price
            spy_entry: SPY price at fund inception (for benchmark return)
        """
        spy_e = spy_entry or self.spy_entry_price
        total = self.total_value(current_prices)
        fund_return = (total - self.starting_capital) / self.starting_capital * 100

        report = {
            "fund_name": self.name,
            "created": self.created_at,
            "starting_capital": self.starting_capital,
            "current_value": round(total, 2),
            "cash": round(self.cash, 2),
            "fund_return_pct": round(fund_return, 2),
            "positions_count": len(self.positions),
            "closed_count": len(self.closed),
        }

        # ── vs SPY benchmark ──
        if spy_e > 0 and spy_current > 0:
            spy_return = (spy_current - spy_e) / spy_e * 100
            alpha = fund_return - spy_return
            report["benchmark"] = {
                "spy_entry": spy_e,
                "spy_current": spy_current,
                "spy_return_pct": round(spy_return, 2),
                "alpha": round(alpha, 2),
                "beating_spy": alpha > 0,
                "verdict": (
                    f"Fund {'outperforming' if alpha > 0 else 'underperforming'} "
                    f"SPY by {abs(alpha):.1f}%"
                ),
            }

        # ── Per-position breakdown ──
        positions_detail = []
        for pos in self.positions:
            price = current_prices.get(pos.ticker, pos.entry_price)
            positions_detail.append(pos.to_dict(price))
        report["positions"] = positions_detail

        # ── Strategy attribution ──
        strat_pnl: dict[str, float] = {}
        strat_cost: dict[str, float] = {}
        for pos in self.positions:
            price = current_prices.get(pos.ticker, pos.entry_price)
            s = pos.strategy
            strat_pnl[s] = strat_pnl.get(s, 0) + pos.pnl(price)
            strat_cost[s] = strat_cost.get(s, 0) + pos.cost_basis

        for cp in self.closed:
            s = cp.strategy
            strat_pnl[s] = strat_pnl.get(s, 0) + cp.pnl
            strat_cost[s] = strat_cost.get(s, 0) + (cp.entry_price * cp.shares)

        strategy_perf = []
        for strat in sorted(set(list(strat_pnl.keys()) + list(self.strategies.keys()))):
            pnl = strat_pnl.get(strat, 0)
            cost = strat_cost.get(strat, 0)
            strategy_perf.append(
                {
                    "strategy": strat,
                    "target_weight": round(self.strategies.get(strat, 0) * 100, 1),
                    "pnl": round(pnl, 2),
                    "return_pct": round(pnl / cost * 100, 2) if cost > 0 else 0.0,
                }
            )
        report["strategy_attribution"] = strategy_perf

        # ── Closed trades stats ──
        if self.closed:
            wins = [c for c in self.closed if c.pnl > 0]
            losses = [c for c in self.closed if c.pnl <= 0]
            avg_win = sum(c.pnl_pct for c in wins) / len(wins) if wins else 0
            avg_loss = sum(c.pnl_pct for c in losses) / len(losses) if losses else 0
            report["trade_stats"] = {
                "total_trades": len(self.closed),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(self.closed) * 100, 1),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "profit_factor": round(
                    (
                        abs(sum(c.pnl for c in wins)) / abs(sum(c.pnl for c in losses))
                        if losses and sum(c.pnl for c in losses) != 0
                        else 0
                    ),
                    2,
                ),
            }

        # ── Allocation check ──
        actual_alloc: dict[str, float] = {}
        for pos in self.positions:
            price = current_prices.get(pos.ticker, pos.entry_price)
            val = pos.current_value(price)
            actual_alloc[pos.strategy] = actual_alloc.get(pos.strategy, 0) + val

        if total > 0:
            alloc_report = []
            for strat, target_w in self.strategies.items():
                actual_val = actual_alloc.get(strat, 0)
                actual_w = actual_val / total
                drift = actual_w - target_w
                alloc_report.append(
                    {
                        "strategy": strat,
                        "target_pct": round(target_w * 100, 1),
                        "actual_pct": round(actual_w * 100, 1),
                        "drift_pct": round(drift * 100, 1),
                        "needs_rebalance": abs(drift) > 0.05,
                    }
                )
            report["allocation"] = alloc_report

        return report

    def to_dict(self) -> dict:
        """Serialize fund for storage."""
        return {
            "name": self.name,
            "starting_capital": self.starting_capital,
            "cash": self.cash,
            "strategies": self.strategies,
            "spy_entry_price": self.spy_entry_price,
            "created_at": self.created_at,
            "positions": [
                {
                    "ticker": p.ticker,
                    "entry_price": p.entry_price,
                    "shares": p.shares,
                    "strategy": p.strategy,
                    "entry_date": p.entry_date,
                    "stop_price": p.stop_price,
                    "target_price": p.target_price,
                }
                for p in self.positions
            ],
            "closed": [
                {
                    "ticker": c.ticker,
                    "strategy": c.strategy,
                    "entry_price": c.entry_price,
                    "exit_price": c.exit_price,
                    "shares": c.shares,
                    "entry_date": c.entry_date,
                    "exit_date": c.exit_date,
                    "exit_reason": c.exit_reason,
                }
                for c in self.closed
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FundBuilder":
        """Deserialize fund from storage."""
        fund = cls(data["name"], data.get("starting_capital", 100000))
        fund.cash = data.get("cash", fund.starting_capital)
        fund.strategies = data.get("strategies", {})
        fund.spy_entry_price = data.get("spy_entry_price", 0)
        fund.created_at = data.get("created_at", "")
        for p in data.get("positions", []):
            pos = FundPosition(**p)
            fund.positions.append(pos)
        for c in data.get("closed", []):
            fund.closed.append(ClosedPosition(**c))
        return fund
