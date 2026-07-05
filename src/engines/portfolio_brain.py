"""
Portfolio Brain — Sprint 73
==============================
Self-running portfolio system with:
  - 3 archetype portfolios (Trend Leaders / Defensive Rotation / Tactical)
  - Policy objects (benchmark, sizing, stops, rebalance, caps)
  - Run simulation against benchmark
  - Weekly/monthly review with postmortem
  - Keep/discard recommendations

This is the "Neal-style" self-learning portfolio:
  build → run → compare → review → adjust → repeat
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PORTFOLIO_DIR = Path("data/portfolios")
PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)


# ── Portfolio Policy ─────────────────────────────────────────────────────────

@dataclass
class PortfolioPolicy:
    """Defines the rules for a portfolio archetype."""
    name: str = ""
    archetype: str = ""             # TREND_LEADERS / DEFENSIVE / TACTICAL
    benchmark: str = "SPY"
    max_positions: int = 10
    max_sector_pct: float = 0.30    # max 30% in one sector
    max_single_position_pct: float = 0.10   # max 10% per position
    correlation_cap: float = 0.70   # reject if corr > 0.7 with existing
    rebalance_frequency: str = "weekly"  # daily / weekly / monthly
    stop_policy: str = "1R_HARD"    # 1R_HARD / TRAILING_1R / ATR_2X
    sizing_policy: str = "EQUAL"    # EQUAL / CONVICTION / KELLY
    min_rs_composite: float = 105.0  # RS floor for entry
    min_confidence: int = 60        # minimum final_confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "benchmark": self.benchmark,
            "max_positions": self.max_positions,
            "max_sector_pct": self.max_sector_pct,
            "max_single_position_pct": self.max_single_position_pct,
            "correlation_cap": self.correlation_cap,
            "rebalance_frequency": self.rebalance_frequency,
            "stop_policy": self.stop_policy,
            "sizing_policy": self.sizing_policy,
            "min_rs_composite": self.min_rs_composite,
            "min_confidence": self.min_confidence,
        }


# ── Default Archetypes ───────────────────────────────────────────────────────

TREND_LEADERS_POLICY = PortfolioPolicy(
    name="Trend Leaders",
    archetype="TREND_LEADERS",
    benchmark="SPY",
    max_positions=10,
    max_sector_pct=0.35,
    max_single_position_pct=0.12,
    rebalance_frequency="weekly",
    stop_policy="TRAILING_1R",
    sizing_policy="CONVICTION",
    min_rs_composite=110.0,
    min_confidence=65,
)

DEFENSIVE_POLICY = PortfolioPolicy(
    name="Defensive Rotation",
    archetype="DEFENSIVE",
    benchmark="SPY",
    max_positions=8,
    max_sector_pct=0.40,
    max_single_position_pct=0.15,
    rebalance_frequency="monthly",
    stop_policy="ATR_2X",
    sizing_policy="EQUAL",
    min_rs_composite=95.0,
    min_confidence=50,
)

TACTICAL_POLICY = PortfolioPolicy(
    name="Tactical / Theme",
    archetype="TACTICAL",
    benchmark="QQQ",
    max_positions=5,
    max_sector_pct=0.50,
    max_single_position_pct=0.20,
    rebalance_frequency="weekly",
    stop_policy="1R_HARD",
    sizing_policy="CONVICTION",
    min_rs_composite=115.0,
    min_confidence=70,
)

ALL_POLICIES = {
    "TREND_LEADERS": TREND_LEADERS_POLICY,
    "DEFENSIVE": DEFENSIVE_POLICY,
    "TACTICAL": TACTICAL_POLICY,
}


# ── Portfolio Holding ────────────────────────────────────────────────────────

@dataclass
class Holding:
    """A single position in a portfolio."""
    ticker: str = ""
    entry_date: str = ""
    entry_price: float = 0.0
    current_price: float = 0.0
    shares: int = 0
    weight_pct: float = 0.0
    sector: str = "—"
    stop: Optional[float] = None
    target: Optional[float] = None
    entry_rs: float = 100.0
    entry_confidence: int = 50
    entry_thesis: str = ""
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    status: str = "OPEN"       # OPEN / STOPPED / TARGET_HIT / MANUAL_EXIT

    def update_pnl(self) -> None:
        if self.entry_price > 0:
            self.pnl_pct = round(
                (self.current_price - self.entry_price) / self.entry_price * 100, 2
            )
            if self.stop and self.entry_price != self.stop:
                risk = abs(self.entry_price - self.stop)
                self.r_multiple = round(
                    (self.current_price - self.entry_price) / risk, 2
                ) if risk > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker, "entry_date": self.entry_date,
            "entry_price": self.entry_price, "current_price": self.current_price,
            "shares": self.shares, "weight_pct": round(self.weight_pct, 2),
            "sector": self.sector, "stop": self.stop, "target": self.target,
            "entry_rs": self.entry_rs, "entry_confidence": self.entry_confidence,
            "entry_thesis": self.entry_thesis,
            "pnl_pct": self.pnl_pct, "r_multiple": self.r_multiple,
            "status": self.status,
        }


# ── Portfolio Run ────────────────────────────────────────────────────────────

@dataclass
class PortfolioRun:
    """A single portfolio instance with holdings and performance."""
    policy: PortfolioPolicy = field(default_factory=PortfolioPolicy)
    holdings: List[Holding] = field(default_factory=list)
    cash_pct: float = 100.0
    created_at: str = ""
    last_rebalance: str = ""
    total_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    alpha_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    journal: List[Dict[str, Any]] = field(default_factory=list)

    def open_positions(self) -> List[Holding]:
        return [h for h in self.holdings if h.status == "OPEN"]

    def closed_positions(self) -> List[Holding]:
        return [h for h in self.holdings if h.status != "OPEN"]

    def sector_exposure(self) -> Dict[str, float]:
        """Sector weights of open positions."""
        exp: Dict[str, float] = {}
        for h in self.open_positions():
            exp[h.sector] = exp.get(h.sector, 0) + h.weight_pct
        return exp

    def can_add(self, ticker: str, sector: str) -> tuple[bool, str]:
        """Check if a new position is allowed by policy."""
        open_pos = self.open_positions()

        if len(open_pos) >= self.policy.max_positions:
            return False, f"Max positions ({self.policy.max_positions}) reached"

        # Sector cap
        sec_exp = self.sector_exposure()
        current_sector_pct = sec_exp.get(sector, 0)
        if current_sector_pct + self.policy.max_single_position_pct > self.policy.max_sector_pct:
            return False, f"Sector {sector} at {current_sector_pct:.0%}, cap is {self.policy.max_sector_pct:.0%}"

        # Duplicate check
        if any(h.ticker == ticker for h in open_pos):
            return False, f"{ticker} already in portfolio"

        return True, "Allowed"

    def add_holding(self, holding: Holding) -> None:
        """Add a new position and update weights."""
        self.holdings.append(holding)
        self._reweight()
        self.journal.append({
            "action": "ADD",
            "ticker": holding.ticker,
            "date": holding.entry_date,
            "price": holding.entry_price,
            "thesis": holding.entry_thesis,
        })

    def close_holding(self, ticker: str, exit_price: float, reason: str) -> None:
        """Close a position."""
        for h in self.holdings:
            if h.ticker == ticker and h.status == "OPEN":
                h.current_price = exit_price
                h.status = reason  # STOPPED / TARGET_HIT / MANUAL_EXIT
                h.update_pnl()
                self.journal.append({
                    "action": "CLOSE",
                    "ticker": ticker,
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "exit_price": exit_price,
                    "pnl_pct": h.pnl_pct,
                    "r_multiple": h.r_multiple,
                    "reason": reason,
                })
                break
        self._reweight()

    def _reweight(self) -> None:
        """Recalculate position weights."""
        open_pos = self.open_positions()
        if not open_pos:
            self.cash_pct = 100.0
            return
        total_value = sum(h.shares * h.current_price for h in open_pos)
        if total_value > 0:
            for h in open_pos:
                h.weight_pct = (h.shares * h.current_price) / total_value * (100 - self.cash_pct)

    def summary(self) -> Dict[str, Any]:
        """Portfolio summary snapshot."""
        open_pos = self.open_positions()
        closed = self.closed_positions()
        winners = [h for h in closed if h.pnl_pct > 0]
        losers = [h for h in closed if h.pnl_pct <= 0]

        return {
            "archetype": self.policy.archetype,
            "name": self.policy.name,
            "benchmark": self.policy.benchmark,
            "open_positions": len(open_pos),
            "closed_positions": len(closed),
            "cash_pct": round(self.cash_pct, 1),
            "total_return_pct": self.total_return_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "alpha_pct": round(self.total_return_pct - self.benchmark_return_pct, 2),
            "win_rate": round(len(winners) / len(closed) * 100, 1) if closed else 0,
            "avg_winner": round(sum(h.pnl_pct for h in winners) / len(winners), 2) if winners else 0,
            "avg_loser": round(sum(h.pnl_pct for h in losers) / len(losers), 2) if losers else 0,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sector_exposure": self.sector_exposure(),
            "holdings": [h.to_dict() for h in open_pos],
            "policy": self.policy.to_dict(),
        }

    def save(self) -> None:
        """Persist portfolio state to JSON."""
        path = PORTFOLIO_DIR / f"{self.policy.archetype.lower()}.json"
        data = {
            "policy": self.policy.to_dict(),
            "holdings": [h.to_dict() for h in self.holdings],
            "cash_pct": self.cash_pct,
            "total_return_pct": self.total_return_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "journal": self.journal[-100:],  # keep last 100 entries
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("[PortfolioBrain] Saved %s", path)

    @classmethod
    def load(cls, archetype: str) -> Optional["PortfolioRun"]:
        """Load portfolio from disk."""
        path = PORTFOLIO_DIR / f"{archetype.lower()}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            policy = ALL_POLICIES.get(archetype.upper(), PortfolioPolicy())
            run = cls(policy=policy)
            run.cash_pct = data.get("cash_pct", 100.0)
            run.total_return_pct = data.get("total_return_pct", 0.0)
            run.benchmark_return_pct = data.get("benchmark_return_pct", 0.0)
            run.max_drawdown_pct = data.get("max_drawdown_pct", 0.0)
            run.journal = data.get("journal", [])
            for h_data in data.get("holdings", []):
                h = Holding()
                for k, v in h_data.items():
                    if hasattr(h, k):
                        setattr(h, k, v)
                run.holdings.append(h)
            return run
        except Exception as e:
            logger.warning("[PortfolioBrain] Load failed: %s", e)
            return None


# ── Portfolio Review ─────────────────────────────────────────────────────────

@dataclass
class PortfolioReview:
    """
    Periodic postmortem output.
    Answers: why did we win/lose, what should change.
    """
    archetype: str = ""
    period: str = ""  # "2026-W18" or "2026-04"
    total_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    # Attribution
    biggest_winner: str = ""
    biggest_winner_pnl: float = 0.0
    biggest_loser: str = ""
    biggest_loser_pnl: float = 0.0
    biggest_drag: str = ""           # sector or position dragging most
    biggest_contributor: str = ""    # sector or position contributing most
    # Self-critique
    stopped_too_early: List[str] = field(default_factory=list)
    stopped_too_late: List[str] = field(default_factory=list)
    took_profit_too_early: List[str] = field(default_factory=list)
    should_have_added: List[str] = field(default_factory=list)
    # What-if
    tighter_stop_result: float = 0.0  # return if stops were 20% tighter
    looser_stop_result: float = 0.0   # return if stops were 20% looser
    less_sector_concentration_result: float = 0.0
    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "archetype": self.archetype,
            "period": self.period,
            "total_return": self.total_return,
            "benchmark_return": self.benchmark_return,
            "alpha": round(self.alpha, 2),
            "biggest_winner": self.biggest_winner,
            "biggest_winner_pnl": self.biggest_winner_pnl,
            "biggest_loser": self.biggest_loser,
            "biggest_loser_pnl": self.biggest_loser_pnl,
            "biggest_drag": self.biggest_drag,
            "biggest_contributor": self.biggest_contributor,
            "self_critique": {
                "stopped_too_early": self.stopped_too_early,
                "stopped_too_late": self.stopped_too_late,
                "took_profit_too_early": self.took_profit_too_early,
                "should_have_added": self.should_have_added,
            },
            "what_if": {
                "tighter_stop": self.tighter_stop_result,
                "looser_stop": self.looser_stop_result,
                "less_sector_concentration": self.less_sector_concentration_result,
            },
            "recommendations": self.recommendations,
        }


def generate_review(run: PortfolioRun, period: str = "") -> PortfolioReview:
    """Generate a postmortem review for a portfolio run."""
    review = PortfolioReview(
        archetype=run.policy.archetype,
        period=period or datetime.now(timezone.utc).strftime("%Y-W%V"),
        total_return=run.total_return_pct,
        benchmark_return=run.benchmark_return_pct,
        alpha=run.total_return_pct - run.benchmark_return_pct,
    )

    closed = run.closed_positions()
    if not closed:
        review.recommendations.append("No closed positions yet — too early to review")
        return review

    # Find biggest winner/loser
    by_pnl = sorted(closed, key=lambda h: h.pnl_pct)
    review.biggest_loser = by_pnl[0].ticker
    review.biggest_loser_pnl = by_pnl[0].pnl_pct
    review.biggest_winner = by_pnl[-1].ticker
    review.biggest_winner_pnl = by_pnl[-1].pnl_pct

    # Self-critique heuristics
    for h in closed:
        if h.status == "STOPPED" and h.pnl_pct > -2:
            review.stopped_too_early.append(h.ticker)
        if h.status == "STOPPED" and h.pnl_pct < -8:
            review.stopped_too_late.append(h.ticker)
        if h.status == "TARGET_HIT" and h.r_multiple < 1.5:
            review.took_profit_too_early.append(h.ticker)

    # Recommendations
    if review.alpha < -2:
        review.recommendations.append("Underperforming benchmark — review entry criteria")
    if len(review.stopped_too_late) > 2:
        review.recommendations.append("Multiple late stops — consider tighter stop policy")
    if len(review.stopped_too_early) > 2:
        review.recommendations.append("Multiple early stops — consider wider initial stops")

    winners = [h for h in closed if h.pnl_pct > 0]
    losers = [h for h in closed if h.pnl_pct <= 0]
    if losers and winners:
        avg_win = sum(h.pnl_pct for h in winners) / len(winners)
        avg_loss = abs(sum(h.pnl_pct for h in losers) / len(losers))
        if avg_win < avg_loss:
            review.recommendations.append(
                f"Winners avg {avg_win:.1f}% vs losers avg -{avg_loss:.1f}% — let winners run longer"
            )

    # Sector concentration check
    sec_exp = run.sector_exposure()
    for sector, pct in sec_exp.items():
        if pct > run.policy.max_sector_pct * 100:
            review.recommendations.append(
                f"Sector {sector} at {pct:.0f}% — exceeds {run.policy.max_sector_pct:.0%} cap"
            )

    return review


# ── Portfolio Brain (orchestrator) ───────────────────────────────────────────

class PortfolioBrain:
    """
    Orchestrates the 3 portfolio archetypes.
    Central entry point for portfolio operations.
    """

    def __init__(self) -> None:
        self.portfolios: Dict[str, PortfolioRun] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load or create all archetype portfolios."""
        for archetype, policy in ALL_POLICIES.items():
            loaded = PortfolioRun.load(archetype)
            if loaded:
                self.portfolios[archetype] = loaded
            else:
                self.portfolios[archetype] = PortfolioRun(
                    policy=policy,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )

    def get_portfolio(self, archetype: str) -> Optional[PortfolioRun]:
        return self.portfolios.get(archetype.upper())

    def all_summaries(self) -> List[Dict[str, Any]]:
        return [run.summary() for run in self.portfolios.values()]

    def review_all(self) -> List[Dict[str, Any]]:
        return [
            generate_review(run).to_dict()
            for run in self.portfolios.values()
        ]

    def save_all(self) -> None:
        for run in self.portfolios.values():
            run.save()
