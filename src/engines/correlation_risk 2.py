"""
Correlation & Concentration Risk Engine — Sprint 50
=====================================================
Portfolio-level risk analysis: sector exposure, pairwise correlation,
crowding risk, and concentration scoring.

Purpose: Ensure the portfolio doesn't have hidden correlated risk,
over-concentration in one name/sector, or crowding into the same
factor exposure.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

# ── Sector mapping (top tickers) ────────────────────────────────────
_SECTOR_MAP: dict[str, str] = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "META": "Technology",
    "NVDA": "Technology",
    "AMD": "Technology",
    "NFLX": "Communication Services",
    "CRM": "Technology",
    "JPM": "Financials",
    "BAC": "Financials",
    "GS": "Financials",
    "V": "Financials",
    "MA": "Financials",
    "UNH": "Healthcare",
    "JNJ": "Healthcare",
    "LLY": "Healthcare",
    "PFE": "Healthcare",
    "ABBV": "Healthcare",
    "XOM": "Energy",
    "CVX": "Energy",
    "COP": "Energy",
    "COST": "Consumer Staples",
    "WMT": "Consumer Staples",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "MU": "Technology",
    "PLTR": "Technology",
    "AVGO": "Technology",
    "INTC": "Technology",
    "QCOM": "Technology",
    "DIS": "Communication Services",
    "CMCSA": "Communication Services",
    "BA": "Industrials",
    "CAT": "Industrials",
    "HON": "Industrials",
    "NEE": "Utilities",
    "DUK": "Utilities",
    "SPY": "Index",
    "QQQ": "Index",
    "IWM": "Index",
    "DIA": "Index",
}


def get_sector(ticker: str) -> str:
    return _SECTOR_MAP.get(ticker.upper(), "Unknown")


@dataclass
class ConcentrationReport:
    """Output of concentration risk analysis."""

    sector_weights: dict[str, float]
    top_concentration_pct: float
    top_ticker: str
    hhi_score: float  # Herfindahl–Hirschman Index
    crowding_flags: list[str]
    warnings: list[str]
    grade: str  # A/B/C/D/F


@dataclass
class CorrelationFlag:
    ticker_a: str
    ticker_b: str
    estimated_correlation: float
    reason: str


class CorrelationRiskEngine:
    """
    Analyse portfolio-level concentration and correlation risk.
    Uses sector mapping and simple heuristics (no live data required).
    """

    MAX_SINGLE_WEIGHT = 0.25  # 25% max per ticker
    MAX_SECTOR_WEIGHT = 0.40  # 40% max per sector
    HHI_WARNING_THRESHOLD = 2000  # HHI > 2000 = concentrated

    def analyse(
        self,
        holdings: list[dict],
    ) -> ConcentrationReport:
        """
        holdings: list of {"ticker": str, "market_value": float}
        """
        total = sum(h.get("market_value", 0) for h in holdings)
        if total <= 0:
            return ConcentrationReport(
                sector_weights={},
                top_concentration_pct=0,
                top_ticker="N/A",
                hhi_score=0,
                crowding_flags=[],
                warnings=["Empty portfolio"],
                grade="F",
            )

        warnings: list[str] = []
        crowding: list[str] = []

        # ── Per-ticker weights ──────────────────────────────────────
        ticker_weights: dict[str, float] = {}
        for h in holdings:
            t = h.get("ticker", "?")
            w = h.get("market_value", 0) / total
            ticker_weights[t] = ticker_weights.get(t, 0) + w

        # ── Sector weights ──────────────────────────────────────────
        sector_weights: dict[str, float] = {}
        for t, w in ticker_weights.items():
            s = get_sector(t)
            sector_weights[s] = sector_weights.get(s, 0) + w

        # ── HHI ─────────────────────────────────────────────────────
        hhi = sum((w * 100) ** 2 for w in ticker_weights.values())

        # ── Concentration warnings ──────────────────────────────────
        top_ticker = max(ticker_weights, key=ticker_weights.get)
        top_pct = ticker_weights[top_ticker]

        if top_pct > self.MAX_SINGLE_WEIGHT:
            warnings.append(
                f"{top_ticker} is {top_pct:.0%} of portfolio "
                f"(max recommended {self.MAX_SINGLE_WEIGHT:.0%})"
            )

        for s, w in sector_weights.items():
            if w > self.MAX_SECTOR_WEIGHT:
                warnings.append(
                    f"Sector '{s}' is {w:.0%} of portfolio "
                    f"(max recommended {self.MAX_SECTOR_WEIGHT:.0%})"
                )

        if hhi > self.HHI_WARNING_THRESHOLD:
            warnings.append(
                f"HHI = {hhi:.0f} — portfolio is concentrated "
                f"(threshold {self.HHI_WARNING_THRESHOLD})"
            )

        # ── Same-sector crowding ────────────────────────────────────
        sector_counts = Counter(get_sector(h.get("ticker", "")) for h in holdings)
        for s, cnt in sector_counts.items():
            if cnt >= 3 and sector_weights.get(s, 0) > 0.30:
                crowding.append(
                    f"{cnt} holdings in '{s}' sector "
                    f"({sector_weights[s]:.0%} weight) — crowding risk"
                )

        # ── Grade ───────────────────────────────────────────────────
        n_issues = len(warnings) + len(crowding)
        if n_issues == 0:
            grade = "A"
        elif n_issues <= 1:
            grade = "B"
        elif n_issues <= 3:
            grade = "C"
        else:
            grade = "D"

        return ConcentrationReport(
            sector_weights={k: round(v, 4) for k, v in sector_weights.items()},
            top_concentration_pct=round(top_pct, 4),
            top_ticker=top_ticker,
            hhi_score=round(hhi, 1),
            crowding_flags=crowding,
            warnings=warnings,
            grade=grade,
        )

    def estimate_correlation_flags(
        self,
        tickers: list[str],
    ) -> list[CorrelationFlag]:
        """
        Heuristic correlation flags — same-sector pairs are likely
        correlated ≥ 0.6.  No live data needed.
        """
        flags: list[CorrelationFlag] = []
        for i, a in enumerate(tickers):
            for b in tickers[i + 1 :]:
                sa = get_sector(a)
                sb = get_sector(b)
                if sa == sb and sa != "Unknown":
                    flags.append(
                        CorrelationFlag(
                            ticker_a=a,
                            ticker_b=b,
                            estimated_correlation=0.65,
                            reason=f"Both in '{sa}' sector",
                        )
                    )
        return flags

    def summary(self, holdings: list[dict]) -> dict:
        report = self.analyse(holdings)
        corr = self.estimate_correlation_flags([h.get("ticker", "") for h in holdings])
        return {
            "grade": report.grade,
            "hhi": report.hhi_score,
            "top_ticker": report.top_ticker,
            "top_weight_pct": round(report.top_concentration_pct * 100, 1),
            "sector_weights": report.sector_weights,
            "warnings": report.warnings,
            "crowding_flags": report.crowding_flags,
            "correlation_pairs": len(corr),
            "correlated_pairs": [
                {
                    "a": c.ticker_a,
                    "b": c.ticker_b,
                    "est_corr": c.estimated_correlation,
                    "reason": c.reason,
                }
                for c in corr[:10]
            ],
        }
