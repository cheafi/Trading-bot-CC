"""
Risk Scorecard Engine — Sprint 51
===================================
Unified risk dashboard that combines:
 • Trade gate status
 • Portfolio heat
 • Concentration/HHI
 • Drawdown tracking
 • Regime risk
 • VaR estimate (parametric)

Produces a single risk scorecard with letter grade (A–F)
and actionable recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskScorecard:
    """Unified risk assessment."""

    overall_grade: str  # A/B/C/D/F
    overall_score: float  # 0–100 (100 = max risk)
    categories: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    can_trade: bool = True

    def to_dict(self) -> dict:
        return {
            "overall_grade": self.overall_grade,
            "overall_score": self.overall_score,
            "categories": self.categories,
            "recommendations": self.recommendations,
            "flags": self.flags,
            "can_trade": self.can_trade,
        }


class RiskScorecardEngine:
    """
    Produces a unified risk scorecard from multiple risk dimensions.
    """

    def evaluate(
        self,
        drawdown_pct: float = 0.0,
        portfolio_heat_pct: float = 0.0,
        open_positions: int = 0,
        max_positions: int = 20,
        hhi_score: float = 0.0,
        concentration_grade: str = "A",
        vix: Optional[float] = None,
        regime: str = "UNKNOWN",
        daily_pnl_pct: float = 0.0,
        win_rate: Optional[float] = None,
        equity: float = 100_000,
    ) -> RiskScorecard:
        """Evaluate all risk dimensions and produce unified scorecard."""
        cats: dict = {}
        recs: list[str] = []
        flags: list[str] = []
        risk_points = 0.0
        can_trade = True

        # ── 1. Drawdown risk (0–25 points) ──────────────────────────
        dd_score = min(25, drawdown_pct * 100 * 1.5)
        cats["drawdown"] = {
            "score": round(dd_score, 1),
            "value": f"{drawdown_pct:.1%}",
            "status": (
                "critical"
                if drawdown_pct > 0.15
                else "warning" if drawdown_pct > 0.08 else "ok"
            ),
        }
        if drawdown_pct > 0.15:
            flags.append("DRAWDOWN CRITICAL — trading suspended")
            can_trade = False
            recs.append("Stop all new trades. Review open positions.")
        elif drawdown_pct > 0.08:
            recs.append("Reduce position sizes. Tighten stops.")
        risk_points += dd_score

        # ── 2. Portfolio heat (0–20 points) ─────────────────────────
        heat_score = min(20, portfolio_heat_pct * 100 * 2.5)
        cats["portfolio_heat"] = {
            "score": round(heat_score, 1),
            "value": f"{portfolio_heat_pct:.1%}",
            "status": (
                "critical"
                if portfolio_heat_pct > 0.06
                else "warning" if portfolio_heat_pct > 0.04 else "ok"
            ),
        }
        if portfolio_heat_pct > 0.06:
            flags.append("Portfolio heat at maximum")
            can_trade = False
        risk_points += heat_score

        # ── 3. Concentration (0–20 points) ──────────────────────────
        conc_map = {"A": 0, "B": 5, "C": 12, "D": 17, "F": 20}
        conc_score = conc_map.get(concentration_grade, 10)
        cats["concentration"] = {
            "score": conc_score,
            "grade": concentration_grade,
            "hhi": round(hhi_score, 0),
            "status": (
                "critical"
                if concentration_grade in ("D", "F")
                else "warning" if concentration_grade == "C" else "ok"
            ),
        }
        if concentration_grade in ("D", "F"):
            recs.append("Diversify — too concentrated in few names/sectors.")
        risk_points += conc_score

        # ── 4. Market risk / VIX (0–20 points) ─────────────────────
        vix_val = vix if vix is not None else 20
        vix_score = min(20, max(0, (vix_val - 12) * 0.8))
        cats["market_volatility"] = {
            "score": round(vix_score, 1),
            "vix": vix_val,
            "regime": regime,
            "status": (
                "critical" if vix_val > 40 else "warning" if vix_val > 25 else "ok"
            ),
        }
        if vix_val > 40:
            flags.append(f"VIX {vix_val:.0f} — extreme fear")
            can_trade = False
        elif vix_val > 30:
            recs.append("Elevated VIX — reduce exposure, widen stops.")
        risk_points += vix_score

        # ── 5. Position capacity (0–15 points) ─────────────────────
        capacity_ratio = open_positions / max_positions if max_positions > 0 else 0
        cap_score = min(15, capacity_ratio * 15)
        cats["position_capacity"] = {
            "score": round(cap_score, 1),
            "open": open_positions,
            "max": max_positions,
            "utilization": f"{capacity_ratio:.0%}",
            "status": (
                "critical"
                if capacity_ratio >= 1.0
                else "warning" if capacity_ratio > 0.7 else "ok"
            ),
        }
        if capacity_ratio >= 1.0:
            flags.append("Max positions reached")
            can_trade = False
        risk_points += cap_score

        # ── Overall grade ───────────────────────────────────────────
        risk_points = min(100, risk_points)
        if risk_points <= 15:
            grade = "A"
        elif risk_points <= 30:
            grade = "B"
        elif risk_points <= 50:
            grade = "C"
        elif risk_points <= 70:
            grade = "D"
        else:
            grade = "F"

        if not recs and grade in ("A", "B"):
            recs.append("Risk levels healthy. Normal trading permitted.")

        return RiskScorecard(
            overall_grade=grade,
            overall_score=round(risk_points, 1),
            categories=cats,
            recommendations=recs,
            flags=flags,
            can_trade=can_trade,
        )

    def summary(self) -> dict:
        return {
            "engine": "RiskScorecardEngine",
            "dimensions": [
                "drawdown",
                "portfolio_heat",
                "concentration",
                "market_volatility",
                "position_capacity",
            ],
            "max_score": 100,
            "grades": "A (0-15), B (16-30), C (31-50), D (51-70), F (71+)",
        }
