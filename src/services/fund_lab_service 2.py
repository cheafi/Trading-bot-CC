"""
Fund Lab Service — Sprint 96 (upgraded from Sprint 78)
=======================================================
Self-running portfolio lab that builds four strategy sleeves:
- FUND_ALPHA  : momentum growth leaders  (BULL-only, high-beta)
- FUND_PENDA  : defensive / low-beta stability (all-regime)
- FUND_CAT    : cyclical + tactical rotation  (BULL/SIDEWAYS)
- FUND_MACRO  : macro hedges + safe-haven rotation (any regime)

Sprint 96 scoring upgrades:
  • 12-1 momentum factor — skips last 21 trading days (reversal correction)
  • RS vs SPY — relative strength score added to composite
  • RSI overbought guard — FUND_ALPHA skips names with RSI > 75
  • Calmar ratio added to metrics
  • Per-fund weight auto-tuning hook (consumed by SelfLearningEngine)
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
            "style": {
                "top_n": 5,
                "momentum_weight": 0.60,
                "rs_weight": 0.15,  # RS vs SPY
                "vol_penalty": 0.05,
                "quality_weight": 0.10,
                "rsi_overbought": 75,  # skip names with RSI > 75
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
            "style": {
                "top_n": 7,
                "momentum_weight": 0.35,
                "rs_weight": 0.05,
                "vol_penalty": 0.30,
                "quality_weight": 0.35,
                "rsi_overbought": 80,
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
            "style": {
                "top_n": 6,
                "momentum_weight": 0.50,
                "rs_weight": 0.10,
                "vol_penalty": 0.20,
                "quality_weight": 0.15,
                "rsi_overbought": 78,
                "regime_gates": ["BULL", "SIDEWAYS", "bull_trending", "sideways"],
                "vix_gate": 28,
                "max_cash_pct": 0.50,
                "stop_r": 1.0,
                "target_r": 2.5,
                "turnover_tolerance": "medium",
            },
        },
        "FUND_MACRO": {
            "thesis": "Macro hedges + safe-haven rotation (all-regime diversifier)",
            "candidates": [
                "TLT",
                "GLD",
                "IEF",
                "HYG",
                "VNQ",
                "USO",
                "EMB",
                "BIL",
                "TIPS",
                "UUP",
            ],
            "style": {
                "top_n": 5,
                "momentum_weight": 0.30,
                "rs_weight": 0.20,  # RS relative to regime matters more here
                "vol_penalty": 0.25,
                "quality_weight": 0.20,
                "rsi_overbought": 80,
                "regime_gates": [  # open to all regimes
                    "BULL",
                    "BEAR",
                    "SIDEWAYS",
                    "CHOPPY",
                    "bull_trending",
                    "bear_trending",
                    "sideways",
                ],
                "vix_gate": 50,  # only gate at crisis level
                "max_cash_pct": 0.40,
                "stop_r": 0.75,
                "target_r": 1.5,
                "turnover_tolerance": "low",
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
            close = close.iloc[:, 0]
        s = pd.to_numeric(close, errors="coerce").dropna()
        s.name = ticker
        return s

    @staticmethod
    def _rsi(s: pd.Series, period: int = 14) -> float:
        """Compute last RSI value from a close series."""
        if len(s) < period + 1:
            return 50.0
        delta = s.diff().dropna()
        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)
        avg_gain = gains.rolling(period).mean().iloc[-1]
        avg_loss = losses.rolling(period).mean().iloc[-1]
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - 100 / (1 + rs))

    async def _momentum_score(
        self,
        mds: Any,
        ticker: str,
        period: str,
        spy_series: Optional[pd.Series] = None,
        momentum_weight: float = 0.60,
        rs_weight: float = 0.10,
        vol_penalty: float = 0.15,
        quality_weight: float = 0.0,
        rsi_overbought: int = 80,
    ) -> Tuple[str, float, float, float, float]:
        """
        Returns (ticker, composite_score, ret_12_1, vol, rsi).

        Scoring factors:
          - 12-1 momentum  : 12-month return skipping last 21 trading days
                             (Jegadeesh-Titman reversal correction)
          - 1m momentum    : short-term trend confirmation
          - RS vs SPY      : relative-strength outperformance
          - Volatility penalty
          - Quality proxy  : inverse-vol stability (FUND_PENDA)
          - RSI guard      : if RSI > rsi_overbought → score = -inf (skip)
        """
        s = await self._history(mds, ticker, period)
        if s.empty or len(s) < 40:
            return ticker, float("-inf"), 0.0, 0.0, 50.0

        # RSI overbought guard
        rsi_val = self._rsi(s)
        if rsi_val > rsi_overbought:
            return ticker, float("-inf"), 0.0, 0.0, rsi_val

        # 12-1 momentum: 12m return, skip last 21 days (one-month reversal)
        if len(s) > 252 + 21:
            ret_12_1 = float(s.iloc[-22] / s.iloc[-253] - 1.0)
        elif len(s) > 63:
            ret_12_1 = float(s.iloc[-22] / s.iloc[0] - 1.0) if len(s) > 22 else 0.0
        else:
            ret_12_1 = 0.0

        ret_1m = float(s.iloc[-1] / s.iloc[-22] - 1.0) if len(s) > 22 else 0.0
        vol = float(s.pct_change().dropna().std() * np.sqrt(252)) if len(s) > 2 else 0.0

        # RS vs SPY: excess return over benchmark in same window
        rs_score = 0.0
        if spy_series is not None and not spy_series.empty and len(spy_series) > 22:
            spy_ret_1m = float(spy_series.iloc[-1] / spy_series.iloc[-22] - 1.0)
            rs_score = ret_1m - spy_ret_1m

        # Quality: inverse-vol stability (used by FUND_PENDA / FUND_MACRO)
        quality = (1.0 / max(vol, 0.01)) * 0.05 if quality_weight > 0 else 0.0

        score = (
            ret_12_1 * momentum_weight
            + ret_1m * (1.0 - momentum_weight - rs_weight - quality_weight)
            + rs_score * rs_weight
            - vol * vol_penalty
            + quality * quality_weight
        )
        return ticker, score, ret_12_1, vol, rsi_val

    async def _build_sleeve(
        self,
        mds: Any,
        name: str,
        period: str,
        top_n: int = 5,
        regime: str = "unknown",
        spy_series: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        spec = self.FUND_UNIVERSES[name]
        style = spec.get("style", {})

        # Regime gate — "unknown" bypasses gating
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

        # ── FUND_MACRO regime tilt (Sprint 105) ──
        # Override candidate list based on macro regime to concentrate on
        # the assets most likely to outperform in the current environment.
        candidates = list(spec["candidates"])
        if name == "FUND_MACRO" and regime not in ("unknown", ""):
            regime_upper = regime.upper()
            if "BEAR" in regime_upper:
                # Flight-to-safety: bonds + gold dominate
                candidates = ["TLT", "GLD", "IEF", "BIL", "TIPS"]
            elif "BULL" in regime_upper:
                # Risk-on macro: commodities + EM debt
                candidates = ["USO", "GLD", "EMB", "HYG", "UUP"]
            elif "CHOPPY" in regime_upper:
                # Reduce volatility: bills + short-duration
                candidates = ["BIL", "TIPS", "IEF", "TLT", "UUP"]
            # SIDEWAYS: use full default universe (no tilt)

            # Sprint 106: push Discord alert when tilt candidates change
            _tilt_state_path = "models/fund_tilt_state.json"
            try:
                import json as _json
                from pathlib import Path as _Path

                _state_file = _Path(_tilt_state_path)
                _prev_state: dict = (
                    _json.loads(_state_file.read_text()) if _state_file.exists() else {}
                )
                _prev_candidates = _prev_state.get(name, list(spec["candidates"]))
                if set(_prev_candidates) != set(candidates):
                    from src.services.alert_service import (
                        on_fund_rebalance,
                    )  # noqa: PLC0415

                    on_fund_rebalance(name, regime, _prev_candidates, candidates)
                _prev_state[name] = candidates
                _state_file.parent.mkdir(parents=True, exist_ok=True)
                _state_file.write_text(_json.dumps(_prev_state, indent=2))
            except Exception as _tilt_exc:
                import logging as _logging

                _logging.getLogger("fund_lab_service").warning(
                    "fund_tilt_state update failed (non-fatal): %s", _tilt_exc
                )
        mom_w = style.get("momentum_weight", 0.60)
        rs_w = style.get("rs_weight", 0.10)
        vol_p = style.get("vol_penalty", 0.15)
        qual_w = style.get("quality_weight", 0.0)
        rsi_ob = style.get("rsi_overbought", 80)
        effective_top_n = style.get("top_n", top_n)

        tasks = [
            self._momentum_score(
                mds,
                t,
                period,
                spy_series=spy_series,
                momentum_weight=mom_w,
                rs_weight=rs_w,
                vol_penalty=vol_p,
                quality_weight=qual_w,
                rsi_overbought=rsi_ob,
            )
            for t in candidates  # regime-tilted candidates (FUND_MACRO) or default
        ]
        rows = await asyncio.gather(*tasks)
        rows = [r for r in rows if math.isfinite(r[1])]
        rows.sort(key=lambda x: x[1], reverse=True)
        picks = rows[: max(1, min(effective_top_n, len(rows)))]
        if not picks:
            return {"name": name, "thesis": spec["thesis"], "picks": []}

        scores = np.array([sc for (_, sc, _, _, _) in picks], dtype=float)
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
                    "momentum_12_1": round(r12 * 100, 2),
                    "volatility": round(v * 100, 2),
                    "rsi": round(rsi, 1),
                    "score": round(sc, 4),
                }
                for j, (t, sc, r12, v, rsi) in enumerate(picks)
            ],
        }

    async def _portfolio_returns(
        self, mds: Any, picks: List[Dict[str, Any]], period: str
    ) -> tuple[pd.Series, Dict[str, pd.Series]]:
        """Return (aggregate_portfolio_returns, {ticker: individual_returns}).

        The per-pick dict is consumed by _attribution() for contribution analysis.
        Sprint 107: changed return type from pd.Series to tuple.
        """
        _empty: tuple[pd.Series, Dict[str, pd.Series]] = (pd.Series(dtype=float), {})
        if not picks:
            return _empty

        # Parallel history fetches
        raw = await asyncio.gather(
            *[self._history(mds, p["ticker"], period) for p in picks]
        )
        series: List[pd.Series] = []
        weights: List[float] = []
        tickers: List[str] = []
        for s, p in zip(raw, picks):
            if s.empty:
                continue
            series.append(s)
            weights.append(float(p.get("weight", 0.0)))
            tickers.append(p["ticker"])

        if not series:
            return _empty

        df = pd.concat(series, axis=1, join="inner").dropna()
        if df.empty:
            return _empty

        w = np.array(weights[: df.shape[1]], dtype=float)
        if w.sum() <= 0:
            w = np.ones(df.shape[1], dtype=float)
        w = w / w.sum()

        rets = df.pct_change().dropna()
        if rets.empty:
            return _empty

        # Per-pick return series keyed by ticker
        per_pick: Dict[str, pd.Series] = {
            tickers[i]: rets.iloc[:, i] for i in range(min(len(tickers), rets.shape[1]))
        }

        p_rets = rets.mul(w, axis=1).sum(axis=1)
        p_rets.name = "portfolio"
        return p_rets, per_pick

    @staticmethod
    def _metrics(port_rets: pd.Series, bm_rets: pd.Series) -> Dict[str, Any]:
        if port_rets.empty or bm_rets.empty:
            return {
                "total_return": 0.0,
                "annualized": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "calmar": 0.0,
                "max_drawdown": 0.0,
                "excess_return": 0.0,
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
                "calmar": 0.0,
                "max_drawdown": 0.0,
                "excess_return": 0.0,
                "roi_vs_benchmark": 0.0,
            }

        p = aligned["p"]
        b = aligned["b"]
        n = len(p)

        eq_p = (1 + p).cumprod()
        eq_b = (1 + b).cumprod()

        total_p = float(eq_p.iloc[-1] - 1.0)
        total_b = float(eq_b.iloc[-1] - 1.0)
        years = max(n / 252.0, 0.1)
        ann_p = float((1 + total_p) ** (1 / years) - 1)
        ann_b = float((1 + total_b) ** (1 / years) - 1)

        vol = float(p.std() * np.sqrt(252)) if p.std() > 0 else 0.0
        sharpe = float((p.mean() / p.std()) * np.sqrt(252)) if p.std() > 0 else 0.0

        running_max = eq_p.cummax()
        dd_series = eq_p / running_max - 1.0
        dd = float(dd_series.min())
        calmar = round(ann_p / abs(dd), 2) if dd != 0 else 0.0

        # Sprint 105: watermark drawdown, recovery days, underwater days, equity curve
        watermark_dd = round(float(dd_series.iloc[-1]) * 100, 2)
        underwater_days = int((dd_series < 0).sum())

        # Recovery days: trading days from the trough to the first new-high afterward
        trough_idx = int(dd_series.argmin())
        peak_after = eq_p.iloc[trough_idx:][
            eq_p.iloc[trough_idx:] >= running_max.iloc[trough_idx]
        ]
        recovery_days: int | None = (
            int(peak_after.index.get_loc(peak_after.index[0]))
            if not peak_after.empty
            else None
        )

        # Equity curve normalised to base=100, last 20 bars
        eq_norm = (eq_p / eq_p.iloc[0] * 100.0).round(2)
        equity_curve_20 = eq_norm.iloc[-20:].tolist()

        return {
            "total_return": round(total_p * 100, 2),
            "annualized": round(ann_p * 100, 2),
            "volatility": round(vol * 100, 2),
            "sharpe": round(sharpe, 2),
            "calmar": calmar,
            "max_drawdown": round(dd * 100, 2),
            "excess_return": round((ann_p - ann_b) * 100, 2),
            "roi_vs_benchmark": round((total_p - total_b) * 100, 2),
            # Sprint 105 fields
            "watermark_drawdown": watermark_dd,
            "recovery_days": recovery_days,
            "underwater_days": underwater_days,
            "equity_curve_20": equity_curve_20,
        }

    @staticmethod
    def _attribution(
        picks: List[Dict[str, Any]],
        per_pick_rets: Dict[str, pd.Series],
        bm_rets: pd.Series,
    ) -> Dict[str, Any]:
        """Single-period Brinson-style attribution for one fund sleeve.

        Returns top contributors, top detractors, sector breakdown, cash drag,
        drawdown source, and a recent-win/loss split — all derived from data
        already fetched during scoring.  No extra I/O.

        Sprint 107.
        """
        if not picks or not per_pick_rets:
            return {"attribution_available": False}

        # ── sector map (static dict, no I/O) ─────────────────────────────────
        try:
            from src.engines.sector_classifier import _SECTOR_MAP  # noqa: PLC0415
        except Exception:
            _SECTOR_MAP = {}

        # Supplement with common ETF sectors not in equity map
        _ETF_SECTORS: Dict[str, str] = {
            "TLT": "Bonds/Long",
            "IEF": "Bonds/Intermediate",
            "BIL": "T-Bills",
            "TIPS": "Inflation-Linked",
            "GLD": "Gold",
            "USO": "Energy/Commodities",
            "EMB": "EM Debt",
            "HYG": "High Yield",
            "UUP": "USD",
            "VNQ": "REITs",
            "SPY": "Broad Market",
            "QQQ": "Tech/Nasdaq",
            "XLV": "Health Care",
            "XLP": "Staples",
            "XLU": "Utilities",
            "XLE": "Energy",
            "XLF": "Financials",
            "XLI": "Industrials",
            "SMH": "Semiconductors",
            "IWM": "Small Cap",
            "EEM": "Emerging Markets",
            "INDA": "India",
            "EWJ": "Japan",
        }

        def _sector(ticker: str) -> str:
            t = ticker.upper()
            if t in _ETF_SECTORS:
                return _ETF_SECTORS[t]
            entry = _SECTOR_MAP.get(t)
            if entry:
                return entry[1]  # subsector string e.g. "AI/Semiconductors"
            return "Other"

        bm_total = float((1 + bm_rets).prod() - 1) if not bm_rets.empty else 0.0

        contributions: List[Dict[str, Any]] = []
        total_weight = 0.0
        for pick in picks:
            t = pick["ticker"]
            w = float(pick.get("weight", 0.0))
            total_weight += w
            s = per_pick_rets.get(t)
            if s is None or s.empty:
                pick_total = 0.0
                dd_val = 0.0
            else:
                pick_total = float((1 + s).prod() - 1)
                eq = (1 + s).cumprod()
                dd_val = float((eq / eq.cummax() - 1).min())

            contribution = w * (pick_total - bm_total)
            contributions.append(
                {
                    "ticker": t,
                    "weight_pct": round(w * 100, 1),
                    "pick_return_pct": round(pick_total * 100, 2),
                    "contribution_pct": round(contribution * 100, 2),
                    "max_drawdown_pct": round(dd_val * 100, 2),
                    "sector": _sector(t),
                }
            )

        contributions.sort(key=lambda x: x["contribution_pct"], reverse=True)
        contributors = [c for c in contributions if c["contribution_pct"] >= 0][:3]
        detractors = sorted(
            [c for c in contributions if c["contribution_pct"] < 0],
            key=lambda x: x["contribution_pct"],
        )[:3]

        # Sector aggregation
        sector_map: Dict[str, float] = {}
        for c in contributions:
            sec = c["sector"]
            sector_map[sec] = round(sector_map.get(sec, 0.0) + c["contribution_pct"], 2)

        # Cash drag: uninvested weight earns 0, opportunity cost vs benchmark
        cash_weight = max(0.0, 1.0 - total_weight)
        cash_drag = round(-cash_weight * bm_total * 100, 2)

        # Drawdown source: pick with worst single-period max drawdown
        dd_source = min(contributions, key=lambda x: x["max_drawdown_pct"])

        # Recent performance: last 20 bars
        recent_wins: List[str] = []
        recent_losses: List[str] = []
        for pick in picks:
            t = pick["ticker"]
            s = per_pick_rets.get(t)
            if s is None or len(s) < 5:
                continue
            recent_ret = float((1 + s.iloc[-20:]).prod() - 1)
            if recent_ret >= 0:
                recent_wins.append(t)
            else:
                recent_losses.append(t)

        # Top factor: which score component has highest rank correlation with contribution
        contribs_by_ticker = {c["ticker"]: c["contribution_pct"] for c in contributions}
        factor_scores = {
            "momentum_12_1": [p.get("momentum_12_1", 0) for p in picks],
            "score": [p.get("score", 0) for p in picks],
        }
        contrib_vals = [contribs_by_ticker.get(p["ticker"], 0) for p in picks]
        best_factor = "score"
        best_corr = -999.0
        if len(contrib_vals) >= 3:
            try:
                from src.engines.feature_ic import _pearson  # noqa: PLC0415

                for fname, fvals in factor_scores.items():
                    corr = _pearson(fvals, contrib_vals)
                    if corr is not None and corr > best_corr:
                        best_corr = corr
                        best_factor = fname
            except Exception:
                pass

        return {
            "attribution_available": True,
            "note": "Single-period attribution — assumes static weights",
            "contributors": contributors,
            "detractors": detractors,
            "sector_contribution": sector_map,
            "cash_drag_pct": cash_drag,
            "cash_weight_pct": round(cash_weight * 100, 1),
            "drawdown_source": dd_source["ticker"],
            "drawdown_source_dd_pct": dd_source["max_drawdown_pct"],
            "recent_wins": recent_wins,
            "recent_losses": recent_losses,
            "top_factor": best_factor,
            "all_contributions": contributions,
        }

    async def run(
        self,
        mds: Any,
        period: str = "1y",
        benchmark: str = "SPY",
        top_n: int = 5,
        regime: str = "unknown",
    ) -> Dict[str, Any]:
        # Pre-fetch SPY once — reused for RS scoring in every sleeve
        bm_prices = await self._history(mds, benchmark.upper(), period)
        spy_series = None if bm_prices.empty else bm_prices
        bm_rets = (
            pd.Series(dtype=float)
            if bm_prices.empty
            else bm_prices.pct_change().dropna()
        )

        # Parallel sleeve builds — now all 4 sleeves in one gather
        sleeve_list = await asyncio.gather(
            *[
                self._build_sleeve(
                    mds, name, period, top_n, regime=regime, spy_series=spy_series
                )
                for name in self.FUND_UNIVERSES
            ]
        )
        sleeves = {s["name"]: s for s in sleeve_list}

        # Parallel portfolio returns — each returns (agg_series, per_pick_dict)
        sleeve_items = list(sleeves.items())
        port_rets_list = await asyncio.gather(
            *[
                self._portfolio_returns(mds, sleeve.get("picks", []), period)
                for _, sleeve in sleeve_items
            ]
        )

        results: List[Dict[str, Any]] = []
        for (fund_name, sleeve), port_tuple in zip(sleeve_items, port_rets_list):
            p_rets, per_pick_rets = port_tuple
            metrics = self._metrics(p_rets, bm_rets)
            entry = SleeveResult(
                name=fund_name,
                thesis=sleeve.get("thesis", ""),
                picks=sleeve.get("picks", []),
                metrics=metrics,
            ).to_dict()
            # Sprint 107: attach attribution to every sleeve
            entry["attribution"] = self._attribution(
                sleeve.get("picks", []), per_pick_rets, bm_rets
            )
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
