"""
CC — Symbol Dossier v2

Full single-ticker research page engine:
- Buy / Hold / Avoid verdict with confidence bucket
- Evidence table + contradiction table
- Event calendar (earnings, FOMC, CPI, NFP)
- Insider / fund flow panel
- Invalidation map
- Scenario tree (bull / base / bear with probabilities)

Usage:
    from src.engines.symbol_dossier import SymbolDossier
    dossier = SymbolDossier()
    result = dossier.build("AAPL", price_data, regime, ...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════
# VERDICT
# ═══════════════════════════════════════════════════════════════════


class Verdict:
    BUY = "BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"
    REDUCE = "REDUCE"


# ═══════════════════════════════════════════════════════════════════
# SCENARIO TREE
# ═══════════════════════════════════════════════════════════════════


@dataclass
class Scenario:
    """One branch of a scenario tree."""

    label: str = "base"  # bull / base / bear
    probability: float = 0.5
    target_pct: float = 0.0
    target_price: float = 0.0
    driver: str = ""
    key_risks: List[str] = field(default_factory=list)
    invalidation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "probability": round(self.probability, 2),
            "target_pct": round(self.target_pct, 3),
            "target_price": round(self.target_price, 2),
            "driver": self.driver,
            "key_risks": self.key_risks,
            "invalidation": self.invalidation,
        }


# ═══════════════════════════════════════════════════════════════════
# EVENT CALENDAR
# ═══════════════════════════════════════════════════════════════════

# Known macro events (static, updated periodically)
MACRO_EVENTS = [
    {"name": "FOMC Decision", "frequency": "6-weekly"},
    {"name": "CPI Release", "frequency": "monthly"},
    {"name": "NFP / Jobs Report", "frequency": "monthly"},
    {"name": "PCE Inflation", "frequency": "monthly"},
    {"name": "GDP Report", "frequency": "quarterly"},
    {"name": "ISM Manufacturing", "frequency": "monthly"},
    {"name": "Retail Sales", "frequency": "monthly"},
    {"name": "Consumer Confidence", "frequency": "monthly"},
]


@dataclass
class EventCalendarEntry:
    """An upcoming event relevant to this ticker."""

    event_type: str = ""  # earnings / fomc / cpi / nfp / ex_div
    event_name: str = ""
    event_date: Optional[str] = None
    days_away: int = 999
    impact: str = "medium"  # low / medium / high / critical
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "name": self.event_name,
            "date": self.event_date,
            "days_away": self.days_away,
            "impact": self.impact,
            "notes": self.notes,
        }


# ═══════════════════════════════════════════════════════════════════
# EVIDENCE / CONTRADICTION TABLES
# ═══════════════════════════════════════════════════════════════════


@dataclass
class EvidenceItem:
    """One piece of evidence for or against a thesis."""

    category: str = ""  # technical / fundamental / flow / macro
    description: str = ""
    strength: str = "moderate"  # weak / moderate / strong
    direction: str = "bullish"  # bullish / bearish / neutral

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "strength": self.strength,
            "direction": self.direction,
        }


# ═══════════════════════════════════════════════════════════════════
# SYMBOL DOSSIER ENGINE
# ═══════════════════════════════════════════════════════════════════


class SymbolDossier:
    """
    Builds a complete dossier for a single ticker.
    Consumes price data, regime, signals, events, insider data.
    """

    def build(
        self,
        ticker: str,
        close_prices: Optional[list] = None,
        sma20: Optional[list] = None,
        sma50: Optional[list] = None,
        sma200: Optional[list] = None,
        rsi: Optional[list] = None,
        volume_ratio: Optional[list] = None,
        atr_pct: Optional[list] = None,
        regime_label: str = "unknown",
        regime_fit: float = 0.5,
        days_to_earnings: int = 999,
        insider_net: int = 0,
        sector: str = "unknown",
        signal_score: float = 50.0,
        current_price: float = 0.0,
    ) -> Dict[str, Any]:
        """Build the full dossier."""

        # Default arrays
        close = close_prices or []
        s20 = sma20 or []
        s50 = sma50 or []
        s200 = sma200 or []
        r = rsi or []
        vr = volume_ratio or []
        atr = atr_pct or []

        price = current_price or (close[-1] if close else 0)

        # Evidence tables
        bull_evidence = self._collect_evidence(
            close,
            s20,
            s50,
            s200,
            r,
            vr,
            atr,
            regime_label,
            "bullish",
        )
        bear_evidence = self._collect_evidence(
            close,
            s20,
            s50,
            s200,
            r,
            vr,
            atr,
            regime_label,
            "bearish",
        )

        # Scenario tree
        scenarios = self._build_scenarios(
            price,
            close,
            s50,
            s200,
            atr,
            regime_label,
            regime_fit,
        )

        # Invalidation map
        invalidation = self._build_invalidation(
            price,
            s20,
            s50,
            s200,
            days_to_earnings,
        )

        # Event calendar
        events = self._build_event_calendar(
            days_to_earnings,
        )

        # Verdict
        verdict, confidence_bucket = self._compute_verdict(
            signal_score,
            regime_fit,
            bull_evidence,
            bear_evidence,
            days_to_earnings,
        )

        # What must happen next
        next_steps = self._what_must_happen_next(
            verdict,
            price,
            s20,
            s50,
            r,
        )

        # ── Symbol comparison (vs SPY index) ──
        comparison = None
        try:
            from src.engines.symbol_comparison import SymbolComparisonEngine
            import numpy as np
            if len(close) >= 21:
                ticker_returns = np.diff(close) / close[:-1] * 100
                # Use a simple SPY proxy from close prices if available
                # In production, this would fetch real SPY data
                comparison_engine = SymbolComparisonEngine()
                # For now, compute self-relative metrics
                if len(ticker_returns) >= 63:
                    comparison = {
                        "vs_index": "SPY",
                        "note": "Comparison requires benchmark data — wire via API",
                        "self_volatility": round(float(np.std(ticker_returns) * np.sqrt(252)), 2),
                        "self_max_dd": round(float(self._max_drawdown_pct(close)), 2),
                    }
        except Exception as e:
            logger.debug("Symbol comparison skipped: %s", e)

        result = {
            "ticker": ticker,
            "current_price": round(price, 2),
            "sector": sector,
            "regime": regime_label,
            "regime_fit": round(regime_fit, 2),
            "verdict": {
                "action": verdict,
                "confidence_bucket": confidence_bucket,
                "signal_score": round(signal_score, 1),
            },
            "evidence": {
                "bullish": [e.to_dict() for e in bull_evidence],
                "bearish": [e.to_dict() for e in bear_evidence],
                "bull_count": len(bull_evidence),
                "bear_count": len(bear_evidence),
            },
            "scenarios": [s.to_dict() for s in scenarios],
            "invalidation": invalidation,
            "event_calendar": [e.to_dict() for e in events],
            "insider_sentiment": {
                "net_transactions": insider_net,
                "signal": (
                    "bullish"
                    if insider_net > 2
                    else "bearish" if insider_net < -2 else "neutral"
                ),
            },
            "what_must_happen_next": next_steps,
            "comparison": comparison,
            "generated_at": _utcnow().isoformat(),
        }
        return result

    # ── Evidence ──────────────────────────────────────────────

    def _collect_evidence(
        self,
        close,
        s20,
        s50,
        s200,
        rsi,
        vr,
        atr,
        regime,
        direction,
    ) -> List[EvidenceItem]:
        items = []
        if not close:
            return items

        i = len(close) - 1
        price = close[i]

        if direction == "bullish":
            if s20 and price > s20[min(i, len(s20) - 1)]:
                items.append(
                    EvidenceItem(
                        "technical",
                        "Price above SMA20",
                        "moderate",
                        "bullish",
                    )
                )
            if (
                s50
                and s200
                and (s50[min(i, len(s50) - 1)] > s200[min(i, len(s200) - 1)])
            ):
                items.append(
                    EvidenceItem(
                        "technical",
                        "Golden cross (SMA50 > SMA200)",
                        "strong",
                        "bullish",
                    )
                )
            if rsi and 40 < rsi[min(i, len(rsi) - 1)] < 65:
                items.append(
                    EvidenceItem(
                        "technical",
                        "RSI in healthy range",
                        "moderate",
                        "bullish",
                    )
                )
            if vr and vr[min(i, len(vr) - 1)] > 1.3:
                items.append(
                    EvidenceItem(
                        "flow",
                        "Above-average volume",
                        "moderate",
                        "bullish",
                    )
                )
            if "bull" in regime.lower():
                items.append(
                    EvidenceItem(
                        "macro",
                        "Bullish regime environment",
                        "strong",
                        "bullish",
                    )
                )
        else:  # bearish
            if s50 and price < s50[min(i, len(s50) - 1)]:
                items.append(
                    EvidenceItem(
                        "technical",
                        "Price below SMA50",
                        "moderate",
                        "bearish",
                    )
                )
            if rsi and rsi[min(i, len(rsi) - 1)] > 70:
                items.append(
                    EvidenceItem(
                        "technical",
                        "RSI overbought",
                        "moderate",
                        "bearish",
                    )
                )
            if vr and vr[min(i, len(vr) - 1)] < 0.7:
                items.append(
                    EvidenceItem(
                        "flow",
                        "Declining volume",
                        "weak",
                        "bearish",
                    )
                )
            if atr and atr[min(i, len(atr) - 1)] > 0.04:
                items.append(
                    EvidenceItem(
                        "technical",
                        "High volatility (ATR > 4%)",
                        "moderate",
                        "bearish",
                    )
                )
            if "bear" in regime.lower():
                items.append(
                    EvidenceItem(
                        "macro",
                        "Bearish regime environment",
                        "strong",
                        "bearish",
                    )
                )

        return items

    # ── Scenarios ─────────────────────────────────────────────

    def _build_scenarios(
        self,
        price,
        close,
        s50,
        s200,
        atr,
        regime,
        regime_fit,
    ) -> List[Scenario]:
        if not close or price <= 0:
            return [
                Scenario("bull", 0.33, 0.10, price * 1.1, "Momentum continuation"),
                Scenario("base", 0.34, 0.0, price, "Range-bound consolidation"),
                Scenario(
                    "bear", 0.33, -0.08, price * 0.92, "Mean reversion / breakdown"
                ),
            ]

        # ATR-based targets
        atr_val = atr[-1] if atr else 0.02
        bull_target = price * (1 + atr_val * 3)
        bear_target = price * (1 - atr_val * 2)

        # Regime-adjusted probabilities
        if "bull" in regime.lower():
            bull_p, base_p, bear_p = 0.45, 0.35, 0.20
        elif "bear" in regime.lower():
            bull_p, base_p, bear_p = 0.20, 0.35, 0.45
        else:
            bull_p, base_p, bear_p = 0.30, 0.40, 0.30

        return [
            Scenario(
                "bull",
                bull_p,
                (bull_target - price) / price,
                round(bull_target, 2),
                "Momentum continuation with volume",
                ["Failed breakout", "Sector rotation"],
                f"Close below {price * 0.97:.2f}",
            ),
            Scenario(
                "base",
                base_p,
                0.0,
                round(price, 2),
                "Consolidation / range-bound",
                ["Stuck in range", "Opportunity cost"],
            ),
            Scenario(
                "bear",
                bear_p,
                (bear_target - price) / price,
                round(bear_target, 2),
                "Mean reversion or breakdown",
                ["Gap down", "Sector contagion"],
                f"Close above {price * 1.03:.2f}",
            ),
        ]

    # ── Invalidation ──────────────────────────────────────────

    def _build_invalidation(
        self,
        price,
        s20,
        s50,
        s200,
        days_to_earnings,
    ) -> List[Dict[str, str]]:
        items = []
        if s50:
            items.append(
                {
                    "condition": f"Close below SMA50 ({s50[-1]:.2f})",
                    "severity": "high",
                    "action": "Exit or reduce position",
                }
            )
        if s200:
            items.append(
                {
                    "condition": f"Close below SMA200 ({s200[-1]:.2f})",
                    "severity": "critical",
                    "action": "Exit position immediately",
                }
            )
        if days_to_earnings <= 5:
            items.append(
                {
                    "condition": f"Earnings in {days_to_earnings} days",
                    "severity": "high",
                    "action": "Reduce size or hedge before event",
                }
            )
        items.append(
            {
                "condition": "Broad market crash (VIX > 35)",
                "severity": "critical",
                "action": "Exit all risk positions",
            }
        )
        return items

    # ── Event calendar ────────────────────────────────────────

    def _build_event_calendar(
        self,
        days_to_earnings,
    ) -> List[EventCalendarEntry]:
        events = []
        if days_to_earnings < 60:
            events.append(
                EventCalendarEntry(
                    event_type="earnings",
                    event_name="Earnings Report",
                    days_away=days_to_earnings,
                    impact="critical" if days_to_earnings <= 5 else "high",
                    notes=(
                        "Consider reducing position or hedging"
                        if days_to_earnings <= 5
                        else "Monitor for pre-earnings positioning"
                    ),
                )
            )
        # Add generic macro events
        for evt in MACRO_EVENTS[:4]:
            events.append(
                EventCalendarEntry(
                    event_type="macro",
                    event_name=evt["name"],
                    impact="medium",
                    notes=f"Frequency: {evt['frequency']}",
                )
            )
        return events

    # ── Verdict ───────────────────────────────────────────────

    def _compute_verdict(
        self,
        score,
        regime_fit,
        bull_ev,
        bear_ev,
        days_to_earnings,
    ) -> tuple:
        bull_strength = sum(
            1 if e.strength == "weak" else 2 if e.strength == "moderate" else 3
            for e in bull_ev
        )
        bear_strength = sum(
            1 if e.strength == "weak" else 2 if e.strength == "moderate" else 3
            for e in bear_ev
        )

        net = bull_strength - bear_strength

        if days_to_earnings <= 2:
            return Verdict.AVOID, "earnings_imminent"

        if score >= 70 and net > 2 and regime_fit >= 0.5:
            return Verdict.BUY, "high"
        if score >= 55 and net > 0:
            return Verdict.HOLD, "moderate"
        if score < 40 or net < -2:
            return Verdict.AVOID, "low"
        return Verdict.HOLD, "moderate"

    # ── What must happen next ─────────────────────────────────

    def _what_must_happen_next(
        self,
        verdict,
        price,
        s20,
        s50,
        rsi,
    ) -> List[str]:
        items = []
        if verdict == Verdict.BUY:
            items.append("Maintain position above SMA20")
            if rsi and rsi[-1] > 65:
                items.append("Watch for RSI divergence")
            items.append("Volume must confirm (> 1.2x average)")
        elif verdict == Verdict.HOLD:
            items.append("Need catalyst for upgrade to BUY")
            if s50:
                items.append(f"Must hold above SMA50 ({s50[-1]:.2f})")
        elif verdict == Verdict.AVOID:
            items.append("Wait for setup to improve")
            items.append("Watch for support test and reversal")
        return items
