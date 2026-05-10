"""
Model Funds Service — Sprint 99
================================
Three first-class productized model funds for PM-facing dashboard.

Funds
-----
LEADER_MOMENTUM   — High-conviction RS leaders, BULL-only, high-beta
BALANCED_MULTI    — Multi-factor balanced: momentum + quality + mean-reversion
TACTICAL_DEF      — Tactical / Defensive: low-beta + quality, all-regime

Each fund card exposes
  • mandate / strategy identity
  • benchmark-relative return (excess return vs SPY)
  • current holdings with weight + conviction
  • adds / reduces / exits since last snapshot (diff from fund_holdings table)
  • attribution (top + bottom contributors)
  • regime fit score (0–100)
  • current regime gate status

Design
------
- Builds on top of FundLabService FUND_ALPHA / FUND_PENDA / FUND_CAT fabric
- Adds productized naming, attribution, diff tracking, and regime fit scoring
- No yfinance calls here; delegates to FundLabService.run() via caller
- Stateless: result is computed from live fund_lab payload + SQLite history

Usage
-----
    from src.services.model_funds import ModelFundService
    svc = ModelFundService()
    cards = await svc.build_cards(fund_lab_payload, regime="BULL", benchmark="SPY")
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Fund identity metadata ─────────────────────────────────────────────────

FUND_IDENTITY: Dict[str, Dict[str, Any]] = {
    "LEADER_MOMENTUM": {
        "display_name": "Leader Momentum",
        "source_fund": "FUND_ALPHA",
        "mandate": (
            "Concentrate in the top relative-strength leaders in confirmed "
            "uptrends. BULL-regime only. High conviction, higher beta, "
            "trailing 1R stop discipline."
        ),
        "benchmark": "SPY",
        "icon": "🚀",
        "color": "#58a6ff",
        "regime_affinity": ["BULL", "bull_trending"],
        "strategy_family": "momentum",
        "risk_level": "HIGH",
        "hold_style": "Swing (4–12 weeks)",
        "stop_method": "Trailing 20-day low",
        "target_r": 3.0,
        "min_r_r": 3.0,
    },
    "BALANCED_MULTI": {
        "display_name": "Balanced Multi-Factor",
        "source_fund": "FUND_CAT",
        "mandate": (
            "Equal-risk blend of momentum, quality, and mean-reversion "
            "factors. Regime-aware rotation between cyclicals and defensives. "
            "Lower turnover, tighter correlation budget."
        ),
        "benchmark": "SPY",
        "icon": "⚖️",
        "color": "#3fb950",
        "regime_affinity": ["BULL", "SIDEWAYS", "bull_trending", "sideways"],
        "strategy_family": "multi_factor",
        "risk_level": "MEDIUM",
        "hold_style": "Swing-to-position (4–16 weeks)",
        "stop_method": "Per-strategy (ATR-based)",
        "target_r": 2.5,
        "min_r_r": 2.0,
    },
    "TACTICAL_DEF": {
        "display_name": "Tactical / Defensive",
        "source_fund": "FUND_PENDA",
        "mandate": (
            "Capital preservation sleeve. Low-beta, high-quality names "
            "with dividend support. Active in all regimes — adds hedges "
            "in BEAR / elevated VIX. Drawdown guard: hard exit at −5%."
        ),
        "benchmark": "SPY",
        "icon": "🛡",
        "color": "#d29922",
        "regime_affinity": ["BULL", "BEAR", "SIDEWAYS", "CHOPPY", "bear_trending"],
        "strategy_family": "defensive",
        "risk_level": "LOW",
        "hold_style": "Position (3–12 months)",
        "stop_method": "Below SMA200",
        "target_r": 2.0,
        "min_r_r": 1.5,
    },
}

# Maps source fund name to model fund id
_SOURCE_TO_MODEL = {v["source_fund"]: k for k, v in FUND_IDENTITY.items()}


class ModelFundService:
    """Build PM-facing fund cards from a fund_lab payload + SQLite history."""

    # ── Regime fit scoring ────────────────────────────────────────────────────

    def _regime_fit(self, fund_id: str, regime: str) -> int:
        """Return 0–100 regime fit score for a model fund."""
        affinity = FUND_IDENTITY[fund_id]["regime_affinity"]
        regime_norm = (regime or "").strip().upper()
        # exact match on normalised regime
        for a in affinity:
            if a.upper() == regime_norm or a.upper() in regime_norm:
                return 95
        # partial keyword matches
        bull_kw = {"BULL", "TRENDING", "UPTREND"}
        bear_kw = {"BEAR", "DOWNTREND", "CRISIS"}
        side_kw = {"SIDE", "CHOP", "RANGE"}

        def _has(kws: set) -> bool:
            return any(k in regime_norm for k in kws)

        if fund_id == "LEADER_MOMENTUM":
            if _has(bull_kw):
                return 90
            if _has(side_kw):
                return 45
            return 15  # BEAR
        if fund_id == "BALANCED_MULTI":
            if _has(bull_kw):
                return 85
            if _has(side_kw):
                return 70
            return 40  # BEAR
        if fund_id == "TACTICAL_DEF":
            if _has(bear_kw):
                return 95
            if _has(side_kw):
                return 80
            return 65  # even in BULL still useful as hedge sleeve

        return 50

    # ── Holdings diff (adds / reduces / exits) ────────────────────────────────

    def _compute_diff(
        self,
        fund_id: str,
        source_fund: str,
        current_picks: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Compare current picks against yesterday's persisted holdings."""
        try:
            from src.services.fund_persistence import _get_db

            conn = _get_db()
            today = date.today().isoformat()
            # Most recent prior snapshot (not today)
            rows = conn.execute(
                """
                SELECT ticker, weight, date_key FROM fund_holdings
                WHERE fund_id = ? AND date_key < ?
                ORDER BY date_key DESC LIMIT 20
                """,
                (source_fund, today),
            ).fetchall()
            conn.close()
        except Exception as exc:
            logger.debug("model_funds diff fetch failed: %s", exc)
            rows = []

        prev_tickers = {r["ticker"]: r["weight"] for r in rows} if rows else {}
        curr_tickers = {
            p.get("ticker", p.get("name", "")): p.get("weight", 0.0)
            for p in current_picks
        }

        adds = [t for t in curr_tickers if t not in prev_tickers]
        exits = [t for t in prev_tickers if t not in curr_tickers]
        reduces = [
            t
            for t in curr_tickers
            if t in prev_tickers and curr_tickers[t] < prev_tickers[t] * 0.85
        ]
        return {"adds": adds, "exits": exits, "reduces": reduces}

    # ── Attribution ───────────────────────────────────────────────────────────

    @staticmethod
    def _attribution(
        picks: List[Dict[str, Any]], total_return: float
    ) -> Dict[str, Any]:
        """
        Simple weight-apportioned attribution.
        Uses momentum_score as a proxy for contribution when P&L not available.
        """
        if not picks:
            return {"top": [], "bottom": [], "note": "no holdings"}

        scored = sorted(
            picks,
            key=lambda p: float(p.get("momentum_score") or p.get("rs_rank") or 0),
            reverse=True,
        )
        top = [
            {
                "ticker": p.get("ticker", p.get("name", "—")),
                "weight": round(float(p.get("weight", 0)), 2),
                "score": round(
                    float(p.get("momentum_score") or p.get("rs_rank") or 0), 1
                ),
            }
            for p in scored[:3]
        ]
        bottom = [
            {
                "ticker": p.get("ticker", p.get("name", "—")),
                "weight": round(float(p.get("weight", 0)), 2),
                "score": round(
                    float(p.get("momentum_score") or p.get("rs_rank") or 0), 1
                ),
            }
            for p in scored[-2:]
        ]
        return {
            "top": top,
            "bottom": bottom,
            "note": "score-weighted proxy (live P&L when available)",
        }

    # ── Main builder ──────────────────────────────────────────────────────────

    async def build_cards(
        self,
        fund_lab_payload: Dict[str, Any],
        regime: str = "unknown",
        benchmark: str = "SPY",
    ) -> List[Dict[str, Any]]:
        """
        Build 3 productized fund cards from a fund_lab payload.

        Parameters
        ----------
        fund_lab_payload : dict
            Result of FundLabService.run() — contains 'funds' list
        regime : str
            Current regime string (BULL / BEAR / SIDEWAYS / etc.)
        benchmark : str
            Benchmark ticker (default SPY)

        Returns
        -------
        List of fund card dicts, one per model fund
        """
        raw_funds: List[Dict[str, Any]] = fund_lab_payload.get("funds", [])
        bm_return: float = float(fund_lab_payload.get("benchmark_return_pct", 0.0))
        cards: List[Dict[str, Any]] = []

        for model_id, meta in FUND_IDENTITY.items():
            source = meta["source_fund"]
            raw = next((f for f in raw_funds if f.get("name") == source), None)

            picks: List[Dict[str, Any]] = (raw or {}).get("picks", [])
            metrics: Dict[str, Any] = (raw or {}).get("metrics", {})

            fund_return = float(metrics.get("total_return_pct", 0.0))
            excess_return = round(fund_return - bm_return, 2)
            sharpe = round(float(metrics.get("sharpe", 0.0)), 2)
            max_dd = round(float(metrics.get("max_drawdown_pct", 0.0)), 2)
            calmar = round(float(metrics.get("calmar", 0.0)), 2)
            regime_fit = self._regime_fit(model_id, regime)
            diff = self._compute_diff(model_id, source, picks)
            attribution = self._attribution(picks, fund_return)

            # Gate status
            if not raw:
                gate_status = "NO_DATA"
            elif regime_fit >= 80:
                gate_status = "ACTIVE"
            elif regime_fit >= 50:
                gate_status = "REDUCED"
            else:
                gate_status = "PAUSED"

            card: Dict[str, Any] = {
                "id": model_id,
                "display_name": meta["display_name"],
                "icon": meta["icon"],
                "color": meta["color"],
                "mandate": meta["mandate"],
                "strategy_family": meta["strategy_family"],
                "risk_level": meta["risk_level"],
                "hold_style": meta["hold_style"],
                "stop_method": meta["stop_method"],
                "target_r": meta["target_r"],
                "min_r_r": meta["min_r_r"],
                # Performance
                "fund_return_pct": round(fund_return, 2),
                "benchmark_return_pct": round(bm_return, 2),
                "excess_return_pct": excess_return,
                "sharpe": sharpe,
                "max_drawdown_pct": max_dd,
                "calmar": calmar,
                # Holdings
                "holdings_count": len(picks),
                "holdings": [
                    {
                        "ticker": p.get("ticker", p.get("name", "—")),
                        "weight": round(float(p.get("weight", 0)), 3),
                        "score": round(
                            float(p.get("momentum_score") or p.get("rs_rank") or 0), 1
                        ),
                        "regime_gate": p.get("regime_gate"),
                    }
                    for p in picks
                ],
                # Changes
                "adds": diff["adds"],
                "exits": diff["exits"],
                "reduces": diff["reduces"],
                # Attribution
                "attribution": attribution,
                # Regime
                "regime_fit": regime_fit,
                "gate_status": gate_status,
                "regime_affinity": meta["regime_affinity"],
                "benchmark": benchmark,
            }
            cards.append(card)

        return cards


# ── Singleton ─────────────────────────────────────────────────────────────────

_svc: Optional[ModelFundService] = None


def get_model_fund_service() -> ModelFundService:
    global _svc
    if _svc is None:
        _svc = ModelFundService()
    return _svc
