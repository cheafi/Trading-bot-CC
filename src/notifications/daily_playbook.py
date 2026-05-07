"""
Daily Playbook Builder (Sprint 38).

Generates a structured morning briefing card that tells
the trader: what to watch, what setups are ripe, what
regime we're in, and what the plan is for today.

Consumed by:
  - Discord ``/playbook`` command
  - Discord daily notification
  - Dashboard morning card

Format:
  ┌─────────────────────────────────┐
  │ 📋 Daily Playbook — 2026-03-29  │
  ├─────────────────────────────────┤
  │ Regime: risk_on ·  Gate: 🟢     │
  │ VIX: 18.5 · Futures: +0.3%     │
  ├─────────────────────────────────┤
  │ 🎯 Top Setups (3)              │
  │   1. NVDA — breakout, 78% conf │
  │   2. AAPL — swing, 72% conf    │
  │   3. MSFT — mean_rev, 65% conf │
  ├─────────────────────────────────┤
  │ ⚠️ Watch List                   │
  │   TSLA — earnings in 2 days    │
  │   AMZN — near resistance       │
  ├─────────────────────────────────┤
  │ 📊 Plan                        │
  │   Max new positions: 3         │
  │   Budget remaining: 85%        │
  │   Focus: momentum + breakout   │
  └─────────────────────────────────┘
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlaybookSetup:
    """A single setup in the playbook."""
    ticker: str
    strategy: str = ""
    confidence: float = 0.0
    direction: str = "LONG"
    entry_price: float = 0.0
    stop_price: float = 0.0
    why: str = ""
    horizon: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "why": self.why,
            "horizon": self.horizon,
        }


@dataclass
class PlaybookCard:
    """Complete daily playbook."""
    date: str = ""
    regime_label: str = ""
    should_trade: bool = True
    vix: float = 0.0
    futures_pct: float = 0.0

    # Setups
    top_setups: List[PlaybookSetup] = field(
        default_factory=list,
    )
    watch_list: List[Dict[str, str]] = field(
        default_factory=list,
    )

    # Plan
    max_new_positions: int = 3
    budget_remaining_pct: float = 100.0
    focus_strategies: List[str] = field(
        default_factory=list,
    )
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "regime_label": self.regime_label,
            "should_trade": self.should_trade,
            "vix": round(self.vix, 1),
            "futures_pct": round(self.futures_pct, 2),
            "top_setups": [
                s.to_dict() for s in self.top_setups
            ],
            "watch_list": self.watch_list,
            "max_new_positions": self.max_new_positions,
            "budget_remaining_pct": round(
                self.budget_remaining_pct, 1,
            ),
            "focus_strategies": self.focus_strategies,
            "notes": self.notes,
        }

    def format_text(self) -> str:
        """Render as plain text for Discord / notifications."""
        lines = [
            f"\U0001f4cb Daily Playbook \u2014 {self.date}",
            "\u2550" * 32,
        ]
        gate = "\U0001f7e2 OPEN" if self.should_trade else "\U0001f534 CLOSED"
        lines.append(
            f"Regime: {self.regime_label} \u2502 Gate: {gate}"
        )
        if self.vix:
            lines.append(
                f"VIX: {self.vix:.1f} \u2502 "
                f"Futures: {self.futures_pct:+.2f}%"
            )
        lines.append("")

        if self.top_setups:
            lines.append(
                f"\U0001f3af Top Setups ({len(self.top_setups)})"
            )
            for i, s in enumerate(self.top_setups[:5], 1):
                lines.append(
                    f"  {i}. {s.ticker} \u2014 "
                    f"{s.strategy}, {s.confidence:.0f}% conf"
                )
                if s.horizon:
                    lines[-1] += f" [{s.horizon}]"
            lines.append("")

        if self.watch_list:
            lines.append("\u26a0\ufe0f Watch List")
            for w in self.watch_list[:5]:
                lines.append(
                    f"  {w.get('ticker', '?')} \u2014 "
                    f"{w.get('reason', '')}"
                )
            lines.append("")

        lines.append("\U0001f4ca Plan")
        lines.append(
            f"  Max new positions: {self.max_new_positions}"
        )
        lines.append(
            f"  Budget remaining: "
            f"{self.budget_remaining_pct:.0f}%"
        )
        if self.focus_strategies:
            lines.append(
                f"  Focus: {', '.join(self.focus_strategies)}"
            )
        if self.notes:
            lines.append(f"  Note: {self.notes}")

        return "\n".join(lines)


class DailyPlaybookBuilder:
    """
    Builds the morning playbook from engine cached state.

    Usage::

        builder = DailyPlaybookBuilder()
        card = builder.build(
            regime_state={...},
            recommendations=[...],
            budget_info={...},
            market_data={...},
        )
        text = card.format_text()
    """

    def build(
        self,
        regime_state: Dict[str, Any],
        recommendations: Optional[List[Dict[str, Any]]] = None,
        budget_info: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> PlaybookCard:
        """Build the playbook card from available data."""
        now = datetime.now(timezone.utc)
        recs = recommendations or []
        budget = budget_info or {}
        mkt = market_data or {}

        card = PlaybookCard(
            date=now.strftime("%Y-%m-%d"),
            regime_label=regime_state.get("regime", "unknown"),
            should_trade=regime_state.get(
                "should_trade", True,
            ),
            vix=mkt.get("vix", 0),
            futures_pct=mkt.get("sp500_futures_pct", 0),
        )

        # Top setups from recommendations
        for rec in recs[:5]:
            if rec.get("trade_decision", False):
                card.top_setups.append(PlaybookSetup(
                    ticker=rec.get("ticker", "?"),
                    strategy=rec.get("strategy_id", ""),
                    confidence=rec.get(
                        "signal_confidence", 0,
                    ),
                    direction=rec.get("direction", "LONG"),
                    entry_price=rec.get("entry_price", 0),
                    stop_price=rec.get("stop_price", 0),
                    why=rec.get("why_now", ""),
                    horizon=rec.get("horizon", ""),
                ))

        # Watch list — recs that aren't trade_decision=True
        for rec in recs[:10]:
            if not rec.get("trade_decision", False):
                reason = rec.get(
                    "why_not_trade",
                    rec.get("suppression_reason", ""),
                )
                if reason:
                    card.watch_list.append({
                        "ticker": rec.get("ticker", "?"),
                        "reason": reason[:100],
                    })

        # Budget
        card.budget_remaining_pct = budget.get(
            "budget_remaining", 100,
        )
        card.max_new_positions = budget.get(
            "max_positions", 3,
        ) - budget.get("open_positions", 0)

        # Focus strategies from regime
        regime = regime_state.get("regime", "")
        if "uptrend" in regime or "risk_on" in regime:
            card.focus_strategies = [
                "momentum", "breakout", "trend_following",
            ]
        elif "range" in regime or "neutral" in regime:
            card.focus_strategies = [
                "mean_reversion", "swing",
            ]
        elif "risk_off" in regime or "crisis" in regime:
            card.focus_strategies = [
                "defensive", "cash",
            ]
            card.notes = "Reduce exposure. Protect capital."
        else:
            card.focus_strategies = ["diversified"]

        return card
