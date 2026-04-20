"""
Decision Journal Engine — Sprint 50
=====================================
Audit trail for every signal evaluation and trading decision.

Every time the system evaluates a candidate, the journal records:
 • Timestamp, ticker, regime
 • All factor scores and evidence
 • Expert committee votes
 • Gate check results
 • Position sizing output
 • Final decision (TRADE / PASS / DEFER)
 • Reasons

This is critical for:
 1. Post-trade attribution ("why did we take this?")
 2. Learning loop ("which factors predicted correctly?")
 3. Compliance / governance audit trail
 4. Debugging signal quality
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class JournalEntry:
    """A single decision record."""

    entry_id: str
    timestamp: str
    ticker: str
    decision: str  # TRADE / PASS / DEFER / BLOCKED
    price: float = 0.0
    regime: str = ""
    score: float = 0.0
    confidence: float = 0.0
    setup_grade: str = ""

    # Evidence
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)

    # Committee
    committee_direction: str = ""
    committee_agreement: float = 0.0
    dissenting_views: list[str] = field(default_factory=list)

    # Gate
    gate_allowed: bool = True
    gate_blocks: list[str] = field(default_factory=list)
    gate_warnings: list[str] = field(default_factory=list)
    gate_size_multiplier: float = 1.0

    # Sizing
    position_shares: int = 0
    position_dollar: float = 0.0
    risk_pct: float = 0.0

    # Outcome (filled later)
    outcome: Optional[str] = None  # WIN / LOSS / OPEN / EXPIRED
    pnl_pct: Optional[float] = None

    # Free-form
    notes: list[str] = field(default_factory=list)
    factors: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class DecisionJournal:
    """
    In-memory decision journal with bounded size.
    Stores last N decisions for review and learning.
    """

    MAX_ENTRIES = 1000

    def __init__(self):
        self._entries: deque[JournalEntry] = deque(maxlen=self.MAX_ENTRIES)
        self._counter = 0

    def record(
        self,
        ticker: str,
        decision: str,
        price: float = 0.0,
        regime: str = "",
        score: float = 0.0,
        confidence: float = 0.0,
        setup_grade: str = "",
        evidence_for: Optional[list[str]] = None,
        evidence_against: Optional[list[str]] = None,
        committee_direction: str = "",
        committee_agreement: float = 0.0,
        dissenting_views: Optional[list[str]] = None,
        gate_allowed: bool = True,
        gate_blocks: Optional[list[str]] = None,
        gate_warnings: Optional[list[str]] = None,
        gate_size_multiplier: float = 1.0,
        position_shares: int = 0,
        position_dollar: float = 0.0,
        risk_pct: float = 0.0,
        notes: Optional[list[str]] = None,
        factors: Optional[dict] = None,
    ) -> JournalEntry:
        """Record a new decision."""
        self._counter += 1
        entry = JournalEntry(
            entry_id=f"DJ-{self._counter:06d}",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            ticker=ticker,
            decision=decision,
            price=price,
            regime=regime,
            score=score,
            confidence=confidence,
            setup_grade=setup_grade,
            evidence_for=evidence_for or [],
            evidence_against=evidence_against or [],
            committee_direction=committee_direction,
            committee_agreement=committee_agreement,
            dissenting_views=dissenting_views or [],
            gate_allowed=gate_allowed,
            gate_blocks=gate_blocks or [],
            gate_warnings=gate_warnings or [],
            gate_size_multiplier=gate_size_multiplier,
            position_shares=position_shares,
            position_dollar=position_dollar,
            risk_pct=risk_pct,
            notes=notes or [],
            factors=factors or {},
        )
        self._entries.append(entry)
        return entry

    def record_outcome(
        self,
        entry_id: str,
        outcome: str,
        pnl_pct: float = 0.0,
    ) -> bool:
        """Update a journal entry with trade outcome."""
        for e in reversed(self._entries):
            if e.entry_id == entry_id:
                e.outcome = outcome
                e.pnl_pct = pnl_pct
                return True
        return False

    @property
    def entries(self) -> list[JournalEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    def recent(self, n: int = 20) -> list[dict]:
        """Return last N entries as dicts."""
        return [e.to_dict() for e in list(self._entries)[-n:]]

    def stats(self) -> dict:
        """Summary statistics of the journal."""
        total = len(self._entries)
        if total == 0:
            return {
                "total_decisions": 0,
                "trades": 0,
                "passes": 0,
                "blocks": 0,
                "defers": 0,
                "win_rate": None,
            }

        decisions = [e.decision for e in self._entries]
        trades = decisions.count("TRADE")
        passes = decisions.count("PASS")
        blocks = decisions.count("BLOCKED")
        defers = decisions.count("DEFER")

        # Win rate from completed outcomes
        completed = [e for e in self._entries if e.outcome in ("WIN", "LOSS")]
        wins = sum(1 for e in completed if e.outcome == "WIN")
        wr = round(wins / len(completed), 3) if completed else None

        # Selectivity
        selectivity = round(trades / total, 3) if total > 0 else 0

        return {
            "total_decisions": total,
            "trades": trades,
            "passes": passes,
            "blocks": blocks,
            "defers": defers,
            "selectivity": selectivity,
            "completed_trades": len(completed),
            "wins": wins,
            "win_rate": wr,
        }

    def by_ticker(self, ticker: str) -> list[dict]:
        """Get all journal entries for a ticker."""
        return [e.to_dict() for e in self._entries if e.ticker == ticker]

    def summary(self) -> dict:
        s = self.stats()
        s["recent"] = self.recent(5)
        return s
