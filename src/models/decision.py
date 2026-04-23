"""
CC — Decision Product Schema
=============================
Canonical data model shared by Web API, Discord bot, and any future consumer.

Usage
-----
    from src.models.decision import DecisionProduct, Opportunity, MarketRegime

    product = DecisionProduct(**api_response)
    for opp in product.top_5:
        print(opp.ticker, opp.action, opp.entry_price)
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# ── Sub-models ────────────────────────────────────────────────────────


class MarketRegime(BaseModel):
    """Current market regime assessment."""

    label: str = Field(description="RISK_ON | NEUTRAL | RISK_OFF")
    risk_state: str = Field(description="RISK_ON | NEUTRAL | RISK_OFF")
    should_trade: bool = True
    confidence: float = Field(0.5, ge=0, le=1)
    tradeability: str = Field(
        description="STRONG_TRADE | TRADE | SELECTIVE | WAIT | NO_TRADE"
    )
    summary: str = ""
    trend: str = Field(description="UPTREND | DOWNTREND | SIDEWAYS")
    volatility: str = Field(description="LOW | NORMAL | ELEVATED | HIGH | CRISIS")
    score: int = Field(50, ge=0, le=100)
    vix: float = 18.0
    breadth: float = Field(50, description="Breadth %")
    entropy: float = 1.0


class IndexQuote(BaseModel):
    """Quick index/sector quote snapshot."""

    symbol: str
    name: str
    price: Optional[float] = None
    change_pct: float = 0.0


class MarketPulse(BaseModel):
    """Index + sector snapshot."""

    indices: List[IndexQuote] = []
    sector_leaders: List[IndexQuote] = []
    sector_laggards: List[IndexQuote] = []


class Opportunity(BaseModel):
    """A single decision-ready trade opportunity."""

    rank: int = 0
    ticker: str
    strategy: str = ""
    score: float = 0
    grade: str = ""
    timing: str = ""
    action: str = Field(description="BUY | BUY_ON_DIP | WATCH | WAIT | AVOID")
    action_reason: str = ""
    why_now: List[str] = []
    why_not: List[str] = []
    risk_reward: float = 0
    entry_price: float = 0
    target_price: float = 0
    stop_price: float = 0
    rsi: float = 0
    invalidation: str = ""
    position_hint: str = ""


class FilterFunnel(BaseModel):
    """Pipeline stages from universe to actionable."""

    universe: int = 0
    signals_triggered: int = 0
    score_above_6: int = 0
    actionable_above_7: int = 0
    high_conviction_above_8: int = 0


class FamilyStat(BaseModel):
    """Stats for a setup family."""

    count: int = 0
    avg_score: float = 0


class TrustInfo(BaseModel):
    """Data provenance & trust metadata."""

    mode: str = Field(description="LIVE | PAPER | BACKTEST | SYNTHETIC")
    source: str = "decision_engine"
    freshness: str = Field(description="REAL_TIME | DELAYED | STALE")
    as_of: str = ""


class DecisionProduct(BaseModel):
    """
    The canonical decision product — a single object that answers:
    "Should I trade today? What? How?"

    Produced by /api/v7/today and consumed by:
    - Web dashboard (Playbook tab)
    - Discord bot (/today, /top, /regime commands)
    - Any future client
    """

    date: str
    narrative: str = ""
    market_regime: MarketRegime
    market_pulse: MarketPulse = MarketPulse()
    top_5: List[Opportunity] = []
    filter_funnel: FilterFunnel = FilterFunnel()
    best_setup_family: Optional[str] = None
    family_breakdown: dict[str, FamilyStat] = {}
    avoid: List[str] = []
    what_changed: List[str] = []
    event_risks: List[str] = []
    trust: TrustInfo = TrustInfo(mode="LIVE", freshness="REAL_TIME")
    generated_at: str = ""

    # ── Discord-friendly formatters ──────────────────────────────────

    def regime_embed_text(self) -> str:
        """One-liner for Discord regime embed."""
        r = self.market_regime
        return (
            f"**{r.trend}** · {r.volatility} vol · "
            f"VIX {r.vix:.0f} · Breadth {r.breadth:.0f}% · "
            f"Confidence {r.score}%"
        )

    def top_tickers_text(self, n: int = 5) -> str:
        """Discord-friendly top picks list."""
        lines = []
        for opp in self.top_5[:n]:
            emoji = {"BUY": "🟢", "BUY_ON_DIP": "🟡", "WATCH": "⚪"}.get(
                opp.action, "⚫"
            )
            lines.append(
                f"{emoji} **{opp.ticker}** {opp.score:.1f} · "
                f"{opp.action} · R:R {opp.risk_reward:.1f} · "
                f"E${opp.entry_price:.2f} → T${opp.target_price:.2f}"
            )
        return "\n".join(lines) or "No actionable setups"

    def brief_narrative(self, max_len: int = 200) -> str:
        """Truncated narrative for Discord."""
        if len(self.narrative) <= max_len:
            return self.narrative
        return self.narrative[: max_len - 1] + "…"
