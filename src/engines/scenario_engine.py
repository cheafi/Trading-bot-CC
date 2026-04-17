"""Scenario / stress engine — what-if analysis with hedge suggestions.

Runs portfolio through predefined stress scenarios (2008 GFC, COVID crash,
2022 rate shock, flash crash, sector rotation, etc.) and suggests hedges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "ScenarioEngine",
    "StressScenario",
    "ScenarioResult",
    "HedgeSuggestion",
]


# ═══════════════════════════════════════════════════════════════
# Predefined stress scenarios
# ═══════════════════════════════════════════════════════════════

_BUILTIN_SCENARIOS = {
    "gfc_2008": {
        "name": "2008 Global Financial Crisis",
        "description": "Broad equity drawdown ~55%, financials -80%, credit freeze",
        "shocks": {"equity": -0.55, "financials": -0.80, "tech": -0.50, "energy": -0.45, "vix_to": 80},
        "duration_days": 365,
        "historical_ref": "S&P 500 Oct 2007 – Mar 2009",
    },
    "covid_2020": {
        "name": "COVID-19 Crash",
        "description": "Sharp -34% drawdown in 23 trading days, V-shaped recovery",
        "shocks": {"equity": -0.34, "travel": -0.60, "energy": -0.50, "tech": -0.25, "vix_to": 82},
        "duration_days": 23,
        "historical_ref": "S&P 500 Feb–Mar 2020",
    },
    "rate_shock_2022": {
        "name": "2022 Rate Shock",
        "description": "Fed hiking cycle, growth-to-value rotation, -27% Nasdaq",
        "shocks": {"equity": -0.20, "tech": -0.33, "growth": -0.35, "value": -0.05, "bonds": -0.15, "vix_to": 35},
        "duration_days": 280,
        "historical_ref": "Nasdaq Jan–Oct 2022",
    },
    "flash_crash": {
        "name": "Flash Crash",
        "description": "Intraday -9% followed by partial recovery, liquidity evaporates",
        "shocks": {"equity": -0.09, "small_cap": -0.15, "vix_to": 45},
        "duration_days": 1,
        "historical_ref": "May 6, 2010",
    },
    "sector_rotation": {
        "name": "Sector Rotation",
        "description": "Sharp rotation from growth/momentum into value/defensive",
        "shocks": {"growth": -0.15, "momentum": -0.12, "value": 0.05, "defensive": 0.03, "vix_to": 22},
        "duration_days": 30,
        "historical_ref": "Various rotation episodes",
    },
    "china_contagion": {
        "name": "China/EM Contagion",
        "description": "EM crisis spills into US markets, commodity crash",
        "shocks": {"equity": -0.15, "em": -0.30, "commodities": -0.25, "energy": -0.20, "vix_to": 30},
        "duration_days": 60,
        "historical_ref": "Aug 2015 / 2018 EM stress",
    },
    "inflation_spike": {
        "name": "Inflation Spike",
        "description": "Unexpected CPI surge → rate fears → equity selloff",
        "shocks": {"equity": -0.12, "tech": -0.18, "bonds": -0.08, "commodities": 0.10, "vix_to": 28},
        "duration_days": 45,
        "historical_ref": "2021–2022 inflation surprise",
    },
    "liquidity_crisis": {
        "name": "Liquidity Crisis",
        "description": "Funding stress, credit spreads widen, small-caps illiquid",
        "shocks": {"equity": -0.20, "small_cap": -0.30, "financials": -0.25, "vix_to": 40},
        "duration_days": 30,
        "historical_ref": "Mar 2023 SVB / regional banks",
    },
}


@dataclass(frozen=True)
class StressScenario:
    """A single stress scenario definition."""

    key: str
    name: str
    description: str
    shocks: dict[str, float]  # sector/asset → shock magnitude
    duration_days: int
    historical_ref: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "shocks": self.shocks,
            "duration_days": self.duration_days,
            "historical_ref": self.historical_ref,
        }


@dataclass(frozen=True)
class HedgeSuggestion:
    """A suggested hedge for a scenario."""

    instrument: str  # e.g. "SPY puts", "VIX calls", "TLT"
    action: str  # "BUY", "SELL"
    rationale: str
    urgency: str  # "IMMEDIATE", "SOON", "MONITOR"
    estimated_cost_pct: float  # rough cost as % of portfolio

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "action": self.action,
            "rationale": self.rationale,
            "urgency": self.urgency,
            "estimated_cost_pct": round(self.estimated_cost_pct, 2),
        }


@dataclass(frozen=True)
class ScenarioResult:
    """Result of running a portfolio through a stress scenario."""

    scenario: dict
    estimated_pnl_pct: float  # estimated portfolio P&L
    worst_position: str  # ticker with biggest loss
    worst_position_loss_pct: float
    surviving_positions: int  # positions that survive stop-loss
    total_positions: int
    hedges: list[dict]
    risk_summary: str

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "estimated_pnl_pct": round(self.estimated_pnl_pct, 2),
            "worst_position": self.worst_position,
            "worst_position_loss_pct": round(self.worst_position_loss_pct, 2),
            "surviving_positions": self.surviving_positions,
            "total_positions": self.total_positions,
            "hedges": self.hedges,
            "risk_summary": self.risk_summary,
        }


# ═══════════════════════════════════════════════════════════════
# Sector mapping for stress shocks
# ═══════════════════════════════════════════════════════════════

_TICKER_SECTOR_MAP: dict[str, list[str]] = {
    # Maps tickers to applicable shock categories
    "AAPL": ["equity", "tech"],
    "MSFT": ["equity", "tech"],
    "GOOGL": ["equity", "tech"],
    "AMZN": ["equity", "tech", "growth"],
    "NVDA": ["equity", "tech", "growth", "momentum"],
    "META": ["equity", "tech", "growth"],
    "TSLA": ["equity", "tech", "growth", "momentum"],
    "JPM": ["equity", "financials"],
    "GS": ["equity", "financials"],
    "BAC": ["equity", "financials"],
    "XOM": ["equity", "energy", "commodities"],
    "CVX": ["equity", "energy", "commodities"],
    "PBR": ["equity", "energy", "em", "commodities"],
    "RKLB": ["equity", "growth", "small_cap"],
    "SPY": ["equity"],
    "QQQ": ["equity", "tech", "growth"],
    "IWM": ["equity", "small_cap"],
}


def _get_shock_for_ticker(ticker: str, shocks: dict[str, float]) -> float:
    """Estimate shock for a specific ticker based on sector mapping."""
    categories = _TICKER_SECTOR_MAP.get(ticker, ["equity"])
    # Use the worst (most negative) applicable shock
    applicable = [shocks.get(cat, 0) for cat in categories]
    return min(applicable) if applicable else shocks.get("equity", -0.10)


# ═══════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════


class ScenarioEngine:
    """Run portfolios through stress scenarios."""

    def __init__(self) -> None:
        self.scenarios: dict[str, StressScenario] = {}
        for key, cfg in _BUILTIN_SCENARIOS.items():
            self.scenarios[key] = StressScenario(
                key=key,
                name=cfg["name"],
                description=cfg["description"],
                shocks=cfg["shocks"],
                duration_days=cfg["duration_days"],
                historical_ref=cfg["historical_ref"],
            )

    def list_scenarios(self) -> list[dict]:
        return [s.to_dict() for s in self.scenarios.values()]

    def run_scenario(
        self,
        scenario_key: str,
        positions: list[dict],
    ) -> ScenarioResult:
        """Run a portfolio through a stress scenario.

        Args:
            scenario_key: key from builtin scenarios
            positions: list of {"ticker": str, "weight": float, "entry_price": float}
        """
        scenario = self.scenarios.get(scenario_key)
        if not scenario:
            return ScenarioResult(
                scenario={"key": scenario_key, "name": "Unknown"},
                estimated_pnl_pct=0,
                worst_position="N/A",
                worst_position_loss_pct=0,
                surviving_positions=0,
                total_positions=len(positions),
                hedges=[],
                risk_summary="Unknown scenario",
            )

        total_pnl = 0.0
        worst_ticker = "N/A"
        worst_loss = 0.0
        surviving = 0

        for pos in positions:
            ticker = pos.get("ticker", "???")
            weight = pos.get("weight", 0.0)
            shock = _get_shock_for_ticker(ticker, scenario.shocks)
            pos_pnl = weight * shock
            total_pnl += pos_pnl

            if shock < worst_loss:
                worst_loss = shock
                worst_ticker = ticker

            # Position "survives" if loss < 20% (rough stop-loss proxy)
            if abs(shock) < 0.20:
                surviving += 1

        # Generate hedge suggestions
        hedges = self._suggest_hedges(scenario, total_pnl, positions)

        severity = "SEVERE" if total_pnl < -0.20 else "MODERATE" if total_pnl < -0.10 else "MILD"
        summary = (
            f"{scenario.name}: estimated {total_pnl*100:.1f}% portfolio impact ({severity}). "
            f"Worst hit: {worst_ticker} at {worst_loss*100:.1f}%. "
            f"{surviving}/{len(positions)} positions survive."
        )

        return ScenarioResult(
            scenario=scenario.to_dict(),
            estimated_pnl_pct=total_pnl,
            worst_position=worst_ticker,
            worst_position_loss_pct=worst_loss,
            surviving_positions=surviving,
            total_positions=len(positions),
            hedges=[h.to_dict() for h in hedges],
            risk_summary=summary,
        )

    def run_all_scenarios(
        self,
        positions: list[dict],
    ) -> list[dict]:
        """Run portfolio through all builtin scenarios."""
        return [
            self.run_scenario(key, positions).to_dict()
            for key in self.scenarios
        ]

    def _suggest_hedges(
        self,
        scenario: StressScenario,
        estimated_pnl: float,
        positions: list[dict],
    ) -> list[HedgeSuggestion]:
        """Suggest hedges based on scenario severity."""
        hedges: list[HedgeSuggestion] = []

        if estimated_pnl < -0.15:
            hedges.append(HedgeSuggestion(
                "SPY puts (1-month ATM)", "BUY",
                "Broad equity protection for severe drawdown",
                "IMMEDIATE", 1.5,
            ))
        if estimated_pnl < -0.10:
            hedges.append(HedgeSuggestion(
                "VIX calls (short-dated)", "BUY",
                "Volatility hedge — profits from fear spikes",
                "SOON", 0.5,
            ))
        if scenario.shocks.get("tech", 0) < -0.20:
            hedges.append(HedgeSuggestion(
                "QQQ puts or reduce tech weight", "BUY/REDUCE",
                "Tech-heavy portfolio needs sector hedge",
                "IMMEDIATE", 1.0,
            ))
        if scenario.shocks.get("bonds", 0) < -0.10:
            hedges.append(HedgeSuggestion(
                "TLT puts or short duration", "BUY",
                "Rate-sensitive scenario — hedge duration",
                "SOON", 0.5,
            ))
        if not hedges:
            hedges.append(HedgeSuggestion(
                "Cash raise 5-10%", "SELL",
                "Mild scenario — small cash raise sufficient",
                "MONITOR", 0.0,
            ))

        return hedges
