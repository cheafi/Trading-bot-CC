"""
Cross-Asset Monitor — Sprint 52
=================================
Detects cross-asset stress signals and divergences that may
indicate systemic risk or regime transitions.

Key signals:
 • VIX-equity divergence (stocks rising while VIX rising = warning)
 • Bond-equity divergence (both falling = flight from all risk)
 • Sector rotation signals (defensive > offensive = risk-off)
 • Breadth divergence (index up but breadth narrowing)
 • Currency stress (DXY surge = global liquidity tightening)

These are contextual intelligence signals — they don't generate
trades directly, but they affect regime classification, position
sizing, and "should we even be trading?" decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CrossAssetSignal:
    """A single cross-asset observation."""

    signal_type: str  # "divergence" / "stress" / "rotation"
    severity: str  # "low" / "medium" / "high" / "critical"
    description: str
    implication: str  # What this means for trading
    action: str  # What to do about it
    affects: str  # "sizing" / "regime" / "direction" / "context"


@dataclass
class CrossAssetReport:
    """Complete cross-asset analysis."""

    stress_level: str  # "calm" / "elevated" / "high" / "crisis"
    stress_score: float  # 0–100
    signals: list[dict] = field(default_factory=list)
    regime_implication: str = ""
    sizing_adjustment: float = 1.0
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        return {
            "stress_level": self.stress_level,
            "stress_score": self.stress_score,
            "signals": self.signals,
            "regime_implication": self.regime_implication,
            "sizing_adjustment": self.sizing_adjustment,
            "generated_at": self.generated_at,
        }


class CrossAssetMonitor:
    """
    Analyses cross-asset relationships to detect stress and divergences.
    Uses heuristic inputs (can be wired to real data feeds later).
    """

    def analyse(
        self,
        vix: float = 20.0,
        spy_change_pct: float = 0.0,
        qqq_change_pct: float = 0.0,
        iwm_change_pct: float = 0.0,
        tlt_change_pct: float = 0.0,
        gld_change_pct: float = 0.0,
        dxy_change_pct: float = 0.0,
        breadth_pct: float = 50.0,
    ) -> CrossAssetReport:
        """
        Generate cross-asset stress analysis.

        Parameters
        ----------
        vix : VIX level
        spy_change_pct : S&P 500 daily change %
        qqq_change_pct : Nasdaq 100 daily change %
        iwm_change_pct : Russell 2000 daily change %
        tlt_change_pct : Long-term Treasury bond daily change %
        gld_change_pct : Gold daily change %
        dxy_change_pct : US Dollar Index daily change %
        breadth_pct : % of stocks above 200-day SMA
        """
        signals: list[CrossAssetSignal] = []
        stress = 0.0

        # ── 1. VIX-Equity divergence ───────────────────────────────
        if vix > 25 and spy_change_pct > 0.5:
            signals.append(
                CrossAssetSignal(
                    signal_type="divergence",
                    severity="medium",
                    description=(
                        f"VIX at {vix:.0f} while SPY up "
                        f"{spy_change_pct:.1f}% — fear/greed mismatch"
                    ),
                    implication="Market may be ignoring risk. Reversal risk elevated.",
                    action="Tighten stops, reduce position sizes",
                    affects="sizing",
                )
            )
            stress += 15

        if vix > 30:
            signals.append(
                CrossAssetSignal(
                    signal_type="stress",
                    severity="high",
                    description=f"VIX at {vix:.0f} — elevated fear",
                    implication="High volatility regime. Wider stops needed.",
                    action="Reduce exposure, increase cash allocation",
                    affects="sizing",
                )
            )
            stress += 20
        elif vix > 40:
            stress += 30

        # ── 2. Bond-equity correlation ─────────────────────────────
        if spy_change_pct < -1 and tlt_change_pct < -0.5:
            signals.append(
                CrossAssetSignal(
                    signal_type="stress",
                    severity="high",
                    description=(
                        f"Stocks down {spy_change_pct:.1f}% AND "
                        f"bonds down {tlt_change_pct:.1f}% — "
                        f"correlated selling"
                    ),
                    implication="Flight from ALL risk assets. Possible liquidity crisis.",
                    action="Halt new entries. Review all positions.",
                    affects="regime",
                )
            )
            stress += 25

        # ── 3. Gold surge (safe-haven demand) ──────────────────────
        if gld_change_pct > 1.5:
            signals.append(
                CrossAssetSignal(
                    signal_type="rotation",
                    severity="medium",
                    description=(
                        f"Gold up {gld_change_pct:.1f}% — " f"safe-haven demand"
                    ),
                    implication="Risk aversion rising. Defensive rotation.",
                    action="Consider reducing equity long exposure",
                    affects="context",
                )
            )
            stress += 10

        # ── 4. Dollar surge (global liquidity tightening) ──────────
        if dxy_change_pct > 1.0:
            signals.append(
                CrossAssetSignal(
                    signal_type="stress",
                    severity="medium",
                    description=(
                        f"USD Index up {dxy_change_pct:.1f}% — " f"dollar strength"
                    ),
                    implication="Global liquidity tightening. EM and commodities pressured.",
                    action="Avoid EM-exposed and commodity stocks",
                    affects="context",
                )
            )
            stress += 10

        # ── 5. Breadth divergence ──────────────────────────────────
        if spy_change_pct > 0.5 and breadth_pct < 40:
            signals.append(
                CrossAssetSignal(
                    signal_type="divergence",
                    severity="high",
                    description=(
                        f"SPY up {spy_change_pct:.1f}% but only "
                        f"{breadth_pct:.0f}% above 200-day SMA — "
                        f"narrow leadership"
                    ),
                    implication="Rally driven by few stocks. Breadth weak. Fragile.",
                    action="Be selective. Avoid chasing. Tighten filters.",
                    affects="regime",
                )
            )
            stress += 15

        # ── 6. Small-cap divergence ────────────────────────────────
        if spy_change_pct > 0.5 and iwm_change_pct < -0.5:
            signals.append(
                CrossAssetSignal(
                    signal_type="divergence",
                    severity="medium",
                    description=(
                        f"SPY up {spy_change_pct:.1f}% but IWM "
                        f"down {iwm_change_pct:.1f}% — "
                        f"risk appetite selective"
                    ),
                    implication="Money flowing to safety. Small-cap risk elevated.",
                    action="Favor large-cap, avoid small-cap",
                    affects="direction",
                )
            )
            stress += 10

        # ── Composite ──────────────────────────────────────────────
        stress = min(100, stress)
        if stress >= 60:
            level = "crisis"
        elif stress >= 40:
            level = "high"
        elif stress >= 20:
            level = "elevated"
        else:
            level = "calm"

        # Sizing adjustment
        if stress >= 60:
            sizing_adj = 0.25
        elif stress >= 40:
            sizing_adj = 0.5
        elif stress >= 20:
            sizing_adj = 0.75
        else:
            sizing_adj = 1.0

        # Regime implication
        if stress >= 40:
            regime_imp = "RISK_OFF — defensive posture recommended"
        elif stress >= 20:
            regime_imp = "CAUTIOUS — tighter filters, reduced size"
        else:
            regime_imp = "NORMAL — standard trading permitted"

        return CrossAssetReport(
            stress_level=level,
            stress_score=round(stress, 1),
            signals=[
                {
                    "type": s.signal_type,
                    "severity": s.severity,
                    "description": s.description,
                    "implication": s.implication,
                    "action": s.action,
                    "affects": s.affects,
                }
                for s in signals
            ],
            regime_implication=regime_imp,
            sizing_adjustment=sizing_adj,
        )

    def summary(self) -> dict:
        return {
            "engine": "CrossAssetMonitor",
            "monitored_assets": [
                "SPY",
                "QQQ",
                "IWM",
                "TLT",
                "GLD",
                "DXY",
                "VIX",
            ],
            "signal_types": [
                "divergence",
                "stress",
                "rotation",
            ],
        }
