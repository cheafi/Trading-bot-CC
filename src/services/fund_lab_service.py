"""
Fund Lab Service — Sprint 78
============================
Self-running portfolio lab that builds three strategy sleeves:
- FUND_ALPHA  : momentum growth leaders
- FUND_PENDA  : defensive / low-beta stability
- FUND_CAT    : cyclical + tactical rotation

Each sleeve is generated from latest market data, then tested against
an index benchmark with ROI / Sharpe / volatility / max drawdown / alpha.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class SleeveResult:
    name: str
    thesis: str
    picks: List[Dict[str, Any]]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "thesis": self.thesis,
            "picks": self.picks,
            "metrics": self.metrics,
        }


class FundLabService:
    """Build and evaluate AI-style sleeves on updated market data."""

    FUND_UNIVERSES: Dict[str, Dict[str, Any]] = {
        "FUND_ALPHA": {
            "thesis": "High-conviction growth + momentum leaders",
            "candidates": [
                "NVDA",
                "MSFT",
                "META",
                "AMZN",
                "AVGO",
                "TSLA",
                "AAPL",
                "AMD",
                "NFLX",
                "GOOGL",
            ],
            # Aggressive: concentrated, momentum-heavy, low vol tolerance
            "style": {
                "top_n": 5,
                "momentum_weight": 0.80,
                "vol_penalty": 0.05,
                "quality_weight": 0.10,
                "regime_gates": ["BULL", "bull_trending"],
                "vix_gate": 28,
                "max_cash_pct": 0.10,
                "stop_r": 1.0,
                "target_r": 3.0,
                "turnover_tolerance": "high",
            },
        },
        "FUND_PENDA": {
            "thesis": "Defensive alpha preservation (low-beta + quality)",
            "candidates": [
                "XLV",
                "XLP",
                "XLU",
                "JNJ",
                "PG",
                "KO",
                "PEP",
                "MRK",
                "ABBV",
                "SO",
            ],
            # Balanced-defensive: diversified, vol-penalised, all-regime
            "style": {
                "top_n": 7,
                "momentum_weight": 0.40,
                "vol_penalty": 0.30,
                "quality_weight": 0.35,
                "regime_gates": [
                    "BULL",
                    "BEAR",
                    "SIDEWAYS",
                    "CHOPPY",
                    "bull_trending",
                    "bear_trending",
                    "sideways",
                ],
                "vix_gate": 35,
                "max_cash_pct": 0.30,
                "stop_r": 0.75,
                "target_r": 2.0,
                "turnover_tolerance": "low",
            },
        },
        "FUND_CAT": {
            "thesis": "Cyclical / tactical allocation by relative strength",
            "candidates": [
                "XLE",
                "XLF",
                "XLI",
                "IWM",
                "SMH",
                "EEM",
                "INDA",
                "EWJ",
                "GLD",
                "TLT",
            ],
            # Tactical: sector rotation, goes to cash in BEAR/high-VIX
            "style": {
                "top_n": 6,
                "momentum_weight": 0.55,
                "vol_penalty": 0.20,
                "quality_weight": 0.15,
                "regime_gates": ["BULL", "SIDEWAYS", "bull_trending", "sideways"],
                "vix_gate": 28,
                "max_cash_pct": 0.50,
                "stop_r": 1.0,
                "target_r": 2.5,
                "turnover_tolerance": "medium",
            },
        },
    }

    async def _history(self, mds: Any, ticker: str, period: str) -> pd.Series:
        """Fetch close series for one ticker."""
        df = await mds.get_history(ticker, period=period, interval="1d")
        if df is None or df.empty:
            return pd.Series(dtype=float)
        close = df.get("Close") if isinstance(df, pd.DataFrame) else None
        if close is None:
            return pd.Series(dtype=float)
        if isinstance(close, pd.DataFrame):
            # sometimes yfinance returns multi-column close for multi-symbol calls
            close = close.iloc[:, 0]
        s = pd.to_numeric(close, errors="coerce").dropna()
        s.name = ticker
        return s

    async def _momentum_score(
        self,
        mds: Any,
        ticker: str,
        period: str,
        momentum_weight: float = 0.65,
        vol_penalty: float = 0.15,
        quality_weight: float = 0.0,
    ) -> Tuple[str, float, float, float]:
        s = await self._history(mds, ticker, period)
        if s.empty or len(s) < 40:
            return ticker, float("-inf"), 0.0, 0.0

        # 3m and 1m momentum blend
        ret_1m = float(s.iloc[-1] / s.iloc[-22] - 1.0) if len(s) > 22 else 0.0
        ret_3m = float(s.iloc[-1] / s.iloc[-63] - 1.0) if len(s) > 63 else ret_1m
        vol = float(s.pct_change().dropna().std() * np.sqrt(252)) if len(s) > 2 else 0.0

        # Quality proxy: inverse vol (stability) — used by FUND_PENDA style
        quality = (1.0 / max(vol, 0.01)) * 0.05 if quality_weight > 0 else 0.0

        one_m_wt = 1.0 - momentum_weight
        score = (
            ret_3m * momentum_weight
            + ret_1m * one_m_wt
            - vol * vol_penalty
            + quality * quality_weight
        )
        return ticker, score, ret_3m, vol

    async def _build_sleeve(
        self,
        mds: Any,
        name: str,
        period: str,
        top_n: int = 5,
        regime: str = "unknown",
    ) -> Dict[str, Any]:
        spec = self.FUND_UNIVERSES[name]
        style = spec.get("style", {})

        # Regime gate: funds with restricted regime_gates go to cash outside their window
        # "unknown" bypasses gating — we only restrict when regime is positively known
        regime_gates = style.get("regime_gates", [])
        if (
            regime_gates
            and regime not in ("unknown", "")
            and regime not in regime_gates
        ):
            return {
                "name": name,
                "thesis": spec["thesis"],
                "picks": [],
                "regime_gated": True,
                "regime": regime,
                "cash_pct": round(style.get("max_cash_pct", 1.0) * 100, 1),
            }

        # Style weights from config
        mom_w = style.get("momentum_weight", 0.65)
        vol_p = style.get("vol_penalty", 0.15)
        qual_w = style.get("quality_weight", 0.0)
        effective_top_n = style.get("top_n", top_n)

        tasks = [
            self._momentum_score(
                mds,
                t,
                period,
                momentum_weight=mom_w,
                vol_penalty=vol_p,
                quality_weight=qual_w,
            )
            for t in spec["candidates"]
        ]
        rows = await asyncio.gather(*tasks)
        rows = [r for r in rows if math.isfinite(r[1])]
        rows.sort(key=lambda x: x[1], reverse=True)
        picks = rows[: max(1, min(effective_top_n, len(rows)))]
        if not picks:
            return {"name": name, "thesis": spec["thesis"], "picks": []}

        # Score-proportional weighting (uses computed momentum edge)
        scores = np.array([sc for (_, sc, _, _) in picks], dtype=float)
        # Shift to positive range so all weights > 0, then normalise
        shifted = scores - scores.min() + 1e-6
        w_arr = shifted / shifted.sum()
        return {
            "name": name,
            "thesis": spec["thesis"],
            "style": {
                "stop_r": style.get("stop_r", 1.0),
                "target_r": style.get("target_r", 2.5),
                "turnover": style.get("turnover_tolerance", "medium"),
                "max_cash_pct": style.get("max_cash_pct", 0.2),
            },
            "picks": [
                {
                    "ticker": t,
                    "weight": round(float(w_arr[j]), 4),
                    "momentum_3m": round(r3 * 100, 2),
                    "volatility": round(v * 100, 2),
                    "score": round(sc, 4),
                }
                for j, (t, sc, r3, v) in enumerate(picks)
            ],
        }

    async def _portfolio_returns(
        self, mds: Any, picks: List[Dict[str, Any]], period: str
    ) -> pd.Series:
        if not picks:
            return pd.Series(dtype=float)

        # Parallel history fetches (5 picks × 1 call each, in parallel)
        raw = await asyncio.gather(
            *[self._history(mds, p["ticker"], period) for p in picks]
        )
        series = []
        weights = []
        for s, p in zip(raw, picks):
            if s.empty:
                continue
            series.append(s)
            weights.append(float(p.get("weight", 0.0)))

        if not series:
            return pd.Series(dtype=float)

        df = pd.concat(series, axis=1, join="inner").dropna()
        if df.empty:
            return pd.Series(dtype=float)

        w = np.array(weights[: df.shape[1]], dtype=float)
        if w.sum() <= 0:
            w = np.ones(df.shape[1], dtype=float)
        w = w / w.sum()

        rets = df.pct_change().dropna()
        if rets.empty:
            return pd.Series(dtype=float)

        p_rets = rets.mul(w, axis=1).sum(axis=1)
        p_rets.name = "portfolio"
        return p_rets

    @staticmethod
    def _metrics(port_rets: pd.Series, bm_rets: pd.Series) -> Dict[str, Any]:
        if port_rets.empty or bm_rets.empty:
            return {
                "total_return": 0.0,
                "annualized": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "alpha_annualized": 0.0,
                "roi_vs_benchmark": 0.0,
            }

        aligned = pd.concat(
            [port_rets.rename("p"), bm_rets.rename("b")], axis=1, join="inner"
        ).dropna()
        if aligned.empty:
            return {
                "total_return": 0.0,
                "annualized": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "alpha_annualized": 0.0,
                "roi_vs_benchmark": 0.0,
            }

        p = aligned["p"]
        b = aligned["b"]
        n = len(p)

        eq_p = (1 + p).cumprod()
        eq_b = (1 + b).cumprod()

        total_p = float(eq_p.iloc[-1] - 1.0)
        total_b = float(eq_b.iloc[-1] - 1.0)
        years = max(
            n / 252.0, 0.1
        )  # floor ~25 trading days to avoid astronomical annualization
        ann_p = float((1 + total_p) ** (1 / years) - 1)
        ann_b = float((1 + total_b) ** (1 / years) - 1)

        vol = float(p.std() * np.sqrt(252)) if p.std() > 0 else 0.0
        sharpe = float((p.mean() / p.std()) * np.sqrt(252)) if p.std() > 0 else 0.0

        running_max = eq_p.cummax()
        dd = (eq_p / running_max - 1.0).min()

        return {
            "total_return": round(total_p * 100, 2),
            "annualized": round(ann_p * 100, 2),
            "volatility": round(vol * 100, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(float(dd) * 100, 2),
            "excess_return": round(
                (ann_p - ann_b) * 100, 2
            ),  # not Jensen's alpha (no beta adj)
            "roi_vs_benchmark": round((total_p - total_b) * 100, 2),
        }

    async def run(
        self,
        mds: Any,
        period: str = "1y",
        benchmark: str = "SPY",
        top_n: int = 5,
        regime: str = "unknown",
    ) -> Dict[str, Any]:
        # Parallel sleeve builds (3× faster than sequential)
        sleeve_list = await asyncio.gather(
            *[
                self._build_sleeve(mds, name, period, top_n, regime=regime)
                for name in self.FUND_UNIVERSES
            ]
        )
        sleeves = {s["name"]: s for s in sleeve_list}

        bm_prices = await self._history(mds, benchmark.upper(), period)
        bm_rets = (
            bm_prices.pct_change().dropna()
            if not bm_prices.empty
            else pd.Series(dtype=float)
        )

        # Parallel portfolio returns (3 sleeves in parallel)
        sleeve_items = list(sleeves.items())
        port_rets_list = await asyncio.gather(
            *[
                self._portfolio_returns(mds, sleeve.get("picks", []), period)
                for _, sleeve in sleeve_items
            ]
        )

        results: List[Dict[str, Any]] = []
        for (fund_name, sleeve), p_rets in zip(sleeve_items, port_rets_list):
            metrics = self._metrics(p_rets, bm_rets)
            entry = SleeveResult(
                name=fund_name,
                thesis=sleeve.get("thesis", ""),
                picks=sleeve.get("picks", []),
                metrics=metrics,
            ).to_dict()
            # Propagate regime gate info so dashboard can show why cash
            if sleeve.get("regime_gated"):
                entry["regime_gated"] = True
                entry["regime"] = sleeve.get("regime", "unknown")
            results.append(entry)

        # sort by excess return desc
        results.sort(
            key=lambda x: x.get("metrics", {}).get("excess_return", 0.0),
            reverse=True,
        )

        # "Best Performer" instead of "Winner" — avoids misleading label when all alpha < 0
        best = results[0]["name"] if results else None
        return {
            "period": period,
            "benchmark": benchmark.upper(),
            "funds": results,
            "best_performer": best,
            "winner": best,  # backward compat
        }


_fund_lab_service: FundLabService | None = None


def get_fund_lab_service() -> FundLabService:
    global _fund_lab_service
    if _fund_lab_service is None:
        _fund_lab_service = FundLabService()
    return _fund_lab_service
