"""
TradingAI Bot — Strategy Optimizer v6
======================================
Self-improving strategy engine that:
  1. Backtests every strategy on real yfinance data (no external signals needed)
  2. Detects which market REGIME we are currently in
  3. Ranks strategies by Sharpe + Win-rate + Profit-factor in THAT regime
  4. Self-corrects signal scoring thresholds based on recent accuracy
  5. Cross-checks: runs all strategies on same data, surfaces conflicts
  6. Tests NEW strategy permutations (parameter sweeps) automatically
  7. Reports everything to Discord with plain-English explanations

Designed to run:
  - On-demand via /backtest, /best_strategy, /strategy_report
  - Automatically via auto_strategy_learn (background task, 6h)
"""

import logging
import math
import random
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── helpers ────────────────────────────────────────────────────────────────

def _sharpe(returns: List[float], rf: float = 0.0) -> float:
    """Annualised Sharpe from a list of per-trade return %."""
    if len(returns) < 3:
        return 0.0
    arr = np.array(returns)
    std = arr.std()
    if std == 0:
        return 0.0
    return float((arr.mean() - rf) / std * math.sqrt(len(arr)))


def _max_drawdown(equity: List[float]) -> float:
    """Peak-to-trough drawdown as a fraction."""
    if not equity:
        return 0.0
    peak = equity[0]
    dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = max(dd, (peak - v) / peak)
    return dd


def _profit_factor(returns: List[float]) -> float:
    wins = sum(r for r in returns if r > 0)
    loss = abs(sum(r for r in returns if r < 0))
    return wins / loss if loss else (float("inf") if wins > 0 else 0.0)


def _regime_from_data(hist: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect market regime from price history.
    Returns: regime label + quantitative features used.
    """
    if hist.empty or len(hist) < 20:
        return {"label": "UNKNOWN", "vix_proxy": 20, "trend": "NEUTRAL"}

    close = hist["Close"] if "Close" in hist.columns else hist["close"]
    close = close.dropna()

    if len(close) < 20:
        return {"label": "UNKNOWN", "vix_proxy": 20, "trend": "NEUTRAL"}

    # Trend: price vs SMA50
    sma50 = close.rolling(min(50, len(close))).mean().iloc[-1]
    price = close.iloc[-1]
    trend_pct = (price - sma50) / sma50 * 100 if sma50 else 0

    # Volatility: 20-day realised vol (annualised)
    rets = close.pct_change().dropna().iloc[-20:]
    vol_ann = rets.std() * math.sqrt(252) * 100  # in %

    # Momentum: 20d return
    mom20 = (close.iloc[-1] / close.iloc[-min(21, len(close))] - 1) * 100

    # Regime classification
    if vol_ann > 35:
        regime = "HIGH_VOL"
    elif vol_ann > 22:
        if mom20 > 3:
            regime = "RISK_ON_HIGH_VOL"
        else:
            regime = "RISK_OFF"
    elif vol_ann > 13:
        if trend_pct > 3 and mom20 > 2:
            regime = "RISK_ON_TRENDING"
        elif trend_pct < -3 and mom20 < -2:
            regime = "DOWNTREND"
        else:
            regime = "NEUTRAL"
    else:
        if trend_pct > 2:
            regime = "LOW_VOL_UPTREND"
        elif trend_pct < -2:
            regime = "LOW_VOL_DOWNTREND"
        else:
            regime = "LOW_VOL_RANGING"

    return {
        "label": regime,
        "price": float(price),
        "sma50": float(sma50),
        "trend_pct": float(trend_pct),
        "vol_ann": float(vol_ann),
        "mom20d": float(mom20),
    }


# ─── per-strategy backsimulation ────────────────────────────────────────────

def _backtest_swing(hist: pd.DataFrame, params: Dict) -> Dict[str, Any]:
    """
    Walk-forward swing backtest on price history.
    Entries: price crosses back above EMA20 after pullback.
    Exits: stop = params["stop_atr"]*ATR below entry; target = params["rr"]*risk.
    """
    close = hist["Close"].dropna() if "Close" in hist.columns else hist["close"].dropna()
    high = hist["High"].dropna() if "High" in hist.columns else hist["high"].dropna()
    low = hist["Low"].dropna() if "Low" in hist.columns else hist["low"].dropna()

    if len(close) < 60:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    ema20 = close.ewm(span=20, adjust=False).mean()
    sma50 = close.rolling(50).mean()

    stop_mult = params.get("stop_atr", 2.0)
    rr = params.get("rr", 2.5)
    min_pb_days = params.get("min_pullback_days", 2)

    # ATR (14-day)
    atr_series = []
    for i in range(1, len(close)):
        tr = max(
            high.iloc[i] - low.iloc[i],
            abs(high.iloc[i] - close.iloc[i - 1]),
            abs(low.iloc[i] - close.iloc[i - 1]),
        )
        atr_series.append(tr)
    atr_s = pd.Series(atr_series, index=close.index[1:]).rolling(14).mean()

    returns = []
    equity = [1.0]
    hold_days = []
    in_trade = False
    pb_count = 0

    for i in range(55, len(close)):
        price = close.iloc[i]
        prev = close.iloc[i - 1]
        ema = ema20.iloc[i]
        sma = sma50.iloc[i]
        atr = atr_s.iloc[i - 1] if i - 1 < len(atr_s) else price * 0.02

        if in_trade:
            if price <= stop_price:
                pnl = (stop_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            elif price >= target_price:
                pnl = (target_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            else:
                hold += 1
                if hold >= 15:  # time stop
                    pnl = (price - entry) / entry
                    returns.append(pnl)
                    equity.append(equity[-1] * (1 + pnl))
                    hold_days.append(hold)
                    in_trade = False
        else:
            # Count pullback days (below EMA20)
            if prev < ema:
                pb_count += 1
            else:
                pb_count = 0

            # Entry: cross back above EMA20 after min pullback days, trend intact
            if (pb_count >= min_pb_days and prev < ema <= price
                    and price > sma and not np.isnan(atr)):
                entry = price * 1.001  # 0.1% slippage
                stop_price = entry - stop_mult * atr
                risk = entry - stop_price
                target_price = entry + rr * risk
                in_trade = True
                hold = 0

    if not returns:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    wins = [r for r in returns if r > 0]
    return {
        "trades": len(returns),
        "win_rate": len(wins) / len(returns),
        "sharpe": _sharpe(returns),
        "pf": _profit_factor(returns),
        "max_dd": _max_drawdown(equity),
        "avg_hold": sum(hold_days) / len(hold_days) if hold_days else 0,
        "avg_return": float(np.mean(returns)),
        "returns": returns,
    }


def _backtest_breakout(hist: pd.DataFrame, params: Dict) -> Dict[str, Any]:
    """
    Breakout backtest: buy when price breaks 20-day high with above-avg vol.
    """
    close = hist["Close"].dropna() if "Close" in hist.columns else hist["close"].dropna()
    high = hist["High"].dropna() if "High" in hist.columns else hist["high"].dropna()
    low = hist["Low"].dropna() if "Low" in hist.columns else hist["low"].dropna()
    vol = hist["Volume"].dropna() if "Volume" in hist.columns else hist["volume"].dropna()

    if len(close) < 40:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    lookback = params.get("lookback", 20)
    vol_mult = params.get("vol_mult", 1.5)
    stop_mult = params.get("stop_atr", 1.5)
    rr = params.get("rr", 2.0)

    avg_vol = vol.rolling(20).mean()

    returns = []
    equity = [1.0]
    hold_days = []
    in_trade = False

    for i in range(lookback + 5, len(close)):
        price = close.iloc[i]
        prev = close.iloc[i - 1]
        resistance = high.iloc[i - lookback:i].max()
        base_low = low.iloc[i - lookback:i].min()
        cur_vol = vol.iloc[i]
        avg_v = avg_vol.iloc[i]
        atr = (high.iloc[i] - low.iloc[i]) * 0.5 + abs(price - prev) * 0.5

        if in_trade:
            if price <= stop_price:
                pnl = (stop_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            elif price >= target_price:
                pnl = (target_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            else:
                hold += 1
                if hold >= 20:
                    pnl = (price - entry) / entry
                    returns.append(pnl)
                    equity.append(equity[-1] * (1 + pnl))
                    hold_days.append(hold)
                    in_trade = False
        else:
            if (prev < resistance and price > resistance
                    and cur_vol > vol_mult * avg_v):
                entry = price * 1.001
                stop_price = max(base_low, entry - stop_mult * atr)
                risk = entry - stop_price
                target_price = entry + rr * risk
                in_trade = True
                hold = 0

    if not returns:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    wins = [r for r in returns if r > 0]
    return {
        "trades": len(returns),
        "win_rate": len(wins) / len(returns),
        "sharpe": _sharpe(returns),
        "pf": _profit_factor(returns),
        "max_dd": _max_drawdown(equity),
        "avg_hold": sum(hold_days) / len(hold_days) if hold_days else 0,
        "avg_return": float(np.mean(returns)),
        "returns": returns,
    }


def _backtest_mean_reversion(hist: pd.DataFrame, params: Dict) -> Dict[str, Any]:
    """
    Mean reversion backtest: buy RSI < threshold, sell at RSI > exit or +N%.
    """
    close = hist["Close"].dropna() if "Close" in hist.columns else hist["close"].dropna()
    if len(close) < 30:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    rsi_entry = params.get("rsi_entry", 30)
    rsi_exit = params.get("rsi_exit", 55)
    stop_pct = params.get("stop_pct", 0.04)
    target_pct = params.get("target_pct", 0.05)

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)

    returns = []
    equity = [1.0]
    hold_days = []
    in_trade = False

    for i in range(20, len(close)):
        price = close.iloc[i]
        rsi_val = rsi.iloc[i] if not np.isnan(rsi.iloc[i]) else 50

        if in_trade:
            if price <= stop_price:
                pnl = (stop_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            elif price >= target_price or rsi_val > rsi_exit:
                pnl = (price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            else:
                hold += 1
                if hold >= 10:
                    pnl = (price - entry) / entry
                    returns.append(pnl)
                    equity.append(equity[-1] * (1 + pnl))
                    hold_days.append(hold)
                    in_trade = False
        else:
            if rsi_val < rsi_entry:
                entry = price * 1.001
                stop_price = entry * (1 - stop_pct)
                target_price = entry * (1 + target_pct)
                in_trade = True
                hold = 0

    if not returns:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    wins = [r for r in returns if r > 0]
    return {
        "trades": len(returns),
        "win_rate": len(wins) / len(returns),
        "sharpe": _sharpe(returns),
        "pf": _profit_factor(returns),
        "max_dd": _max_drawdown(equity),
        "avg_hold": sum(hold_days) / len(hold_days) if hold_days else 0,
        "avg_return": float(np.mean(returns)),
        "returns": returns,
    }


def _backtest_momentum(hist: pd.DataFrame, params: Dict) -> Dict[str, Any]:
    """
    Momentum backtest: enter on big surge day, trail stop, hold momentum.
    """
    close = hist["Close"].dropna() if "Close" in hist.columns else hist["close"].dropna()
    vol = hist["Volume"].dropna() if "Volume" in hist.columns else hist["volume"].dropna()
    if len(close) < 25:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    min_move = params.get("min_move_pct", 3.0) / 100
    vol_mult = params.get("vol_mult", 1.5)
    stop_mult = params.get("stop_atr", 1.5)
    rr = params.get("rr", 2.0)
    avg_vol = vol.rolling(20).mean()

    returns = []
    equity = [1.0]
    hold_days = []
    in_trade = False

    for i in range(21, len(close)):
        price = close.iloc[i]
        prev = close.iloc[i - 1]
        day_ret = (price - prev) / prev if prev else 0
        atr = abs(price - prev) * 1.2

        cur_vol = vol.iloc[i]
        avg_v = avg_vol.iloc[i]

        if in_trade:
            # trail stop up
            trail = price - stop_mult * atr
            stop_price = max(stop_price, trail)
            if price <= stop_price:
                pnl = (stop_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            elif price >= target_price:
                pnl = (target_price - entry) / entry
                returns.append(pnl)
                equity.append(equity[-1] * (1 + pnl))
                hold_days.append(hold)
                in_trade = False
            else:
                hold += 1
                if hold >= 10:
                    pnl = (price - entry) / entry
                    returns.append(pnl)
                    equity.append(equity[-1] * (1 + pnl))
                    hold_days.append(hold)
                    in_trade = False
        else:
            if day_ret >= min_move and cur_vol > vol_mult * avg_v:
                entry = price * 1.001
                stop_price = entry - stop_mult * atr
                risk = entry - stop_price
                target_price = entry + rr * risk
                in_trade = True
                hold = 0

    if not returns:
        return {"trades": 0, "win_rate": 0, "sharpe": 0, "pf": 0, "max_dd": 0,
                "avg_hold": 0, "returns": []}

    wins = [r for r in returns if r > 0]
    return {
        "trades": len(returns),
        "win_rate": len(wins) / len(returns),
        "sharpe": _sharpe(returns),
        "pf": _profit_factor(returns),
        "max_dd": _max_drawdown(equity),
        "avg_hold": sum(hold_days) / len(hold_days) if hold_days else 0,
        "avg_return": float(np.mean(returns)),
        "returns": returns,
    }


# ─── Strategy registry ──────────────────────────────────────────────────────

STRATEGY_REGISTRY: Dict[str, Dict] = {
    "SWING": {
        "fn": _backtest_swing,
        "default_params": {"stop_atr": 2.0, "rr": 2.5, "min_pullback_days": 2},
        "param_grid": {
            "stop_atr": [1.5, 2.0, 2.5, 3.0],
            "rr": [2.0, 2.5, 3.0],
            "min_pullback_days": [1, 2, 3],
        },
        "regime_fit": ["RISK_ON_TRENDING", "LOW_VOL_UPTREND", "NEUTRAL"],
    },
    "BREAKOUT": {
        "fn": _backtest_breakout,
        "default_params": {"lookback": 20, "vol_mult": 1.5, "stop_atr": 1.5, "rr": 2.0},
        "param_grid": {
            "lookback": [15, 20, 30],
            "vol_mult": [1.3, 1.5, 2.0],
            "stop_atr": [1.0, 1.5, 2.0],
            "rr": [1.5, 2.0, 2.5],
        },
        "regime_fit": ["RISK_ON_TRENDING", "RISK_ON_HIGH_VOL", "LOW_VOL_UPTREND"],
    },
    "MEAN_REVERSION": {
        "fn": _backtest_mean_reversion,
        "default_params": {"rsi_entry": 30, "rsi_exit": 55, "stop_pct": 0.04, "target_pct": 0.05},
        "param_grid": {
            "rsi_entry": [25, 30, 35],
            "rsi_exit": [50, 55, 60],
            "stop_pct": [0.03, 0.04, 0.05],
            "target_pct": [0.04, 0.05, 0.07],
        },
        "regime_fit": ["NEUTRAL", "LOW_VOL_RANGING", "RISK_OFF"],
    },
    "MOMENTUM": {
        "fn": _backtest_momentum,
        "default_params": {"min_move_pct": 3.0, "vol_mult": 1.5, "stop_atr": 1.5, "rr": 2.0},
        "param_grid": {
            "min_move_pct": [2.0, 3.0, 4.0],
            "vol_mult": [1.3, 1.5, 2.0],
            "stop_atr": [1.0, 1.5, 2.0],
            "rr": [1.5, 2.0, 2.5],
        },
        "regime_fit": ["RISK_ON_TRENDING", "RISK_ON_HIGH_VOL", "HIGH_VOL"],
    },
}


# ─── Composite scoring ──────────────────────────────────────────────────────

def _score_result(r: Dict, regime: str, strategy_name: str) -> float:
    """
    Single composite quality score (0–100) for a backtest result.
    Weights: Sharpe 35%, win-rate 20%, profit-factor 20%, drawdown -15%, trade count 10%
    """
    if r["trades"] < 2:
        return 0.0

    sharpe_score = min(r["sharpe"] / 3.0, 1.0)  # clamp at Sharpe=3 → 1.0
    wr_score = r["win_rate"]
    pf = min(r["pf"], 5.0) / 5.0
    dd_penalty = max(0.0, 1.0 - r["max_dd"] / 0.3)  # 30% dd = 0 penalty score
    trade_score = min(r["trades"] / 30.0, 1.0)

    raw = (sharpe_score * 35 + wr_score * 20 + pf * 20 +
           dd_penalty * 15 + trade_score * 10)

    # Regime bonus: +10 if strategy naturally fits this regime
    if regime in STRATEGY_REGISTRY.get(strategy_name, {}).get("regime_fit", []):
        raw = min(raw + 8, 100)

    return round(raw, 1)


# ─── Main optimizer class ────────────────────────────────────────────────────

class StrategyOptimizer:
    """
    Runs backtest + parameter-sweep + cross-check + regime-match for any ticker.
    Fully self-contained: only needs yfinance data.
    """

    def __init__(self):
        # In-memory accuracy tracking: {strategy: {"hits": N, "misses": N}}
        self._accuracy: Dict[str, Dict[str, int]] = defaultdict(lambda: {"hits": 0, "misses": 0})
        # Score correction factors derived from live accuracy
        self._score_adjustments: Dict[str, float] = {}
        # Historical regime→best_strategy cache
        self._regime_cache: Dict[str, Dict] = {}

    # ── public API ────────────────────────────────────────────────────────

    def full_analysis(
        self,
        ticker: str,
        hist: pd.DataFrame,
        period_label: str = "1y",
    ) -> Dict[str, Any]:
        """
        Run ALL strategies on hist data, rank them, identify best for current regime.
        Returns a rich analysis dict ready for Discord rendering.
        """
        regime_info = _regime_from_data(hist)
        regime = regime_info["label"]

        results: Dict[str, Dict] = {}

        # 1. Run each strategy with default params
        for name, cfg in STRATEGY_REGISTRY.items():
            try:
                r = cfg["fn"](hist.copy(), cfg["default_params"])
                adj = self._score_adjustments.get(name, 1.0)
                r["score"] = round(_score_result(r, regime, name) * adj, 1)
                r["strategy"] = name
                r["params"] = cfg["default_params"]
                results[name] = r
            except Exception as exc:
                logger.warning(f"Strategy {name} failed: {exc}")
                results[name] = {"trades": 0, "score": 0, "strategy": name,
                                 "returns": [], "win_rate": 0, "sharpe": 0,
                                 "pf": 0, "max_dd": 0, "avg_hold": 0}

        # 2. Walk-forward validation on best strategies
        ranked = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        top2 = ranked[:2]
        wf_results = {}
        for r in top2:
            try:
                wf = self._walk_forward(hist.copy(), r["strategy"])
                wf_results[r["strategy"]] = wf
            except Exception:
                pass

        # 3. Parameter sweep (find best params for top strategy)
        best_strat = ranked[0]["strategy"] if ranked else "SWING"
        best_params, sweep_score = self._param_sweep(hist.copy(), best_strat)

        # 4. Cross-check: do strategies agree on direction?
        conflict = self._cross_check(results)

        # 5. Self-correction summary
        correction_notes = self._correction_notes()

        # 6. Best strategy for current regime
        regime_recommendation = self._regime_recommendation(regime, results)

        # 7. Monte Carlo on best strategy's returns
        mc = self._monte_carlo(results.get(best_strat, {}).get("returns", []))

        return {
            "ticker": ticker,
            "period": period_label,
            "regime": regime_info,
            "strategy_results": results,
            "ranked": ranked,
            "best_strategy": best_strat,
            "best_params": best_params,
            "sweep_improvement": round(sweep_score - results.get(best_strat, {}).get("score", 0), 1),
            "walk_forward": wf_results,
            "cross_check": conflict,
            "regime_recommendation": regime_recommendation,
            "correction_notes": correction_notes,
            "monte_carlo": mc,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def quick_regime_rank(self, hist: pd.DataFrame) -> List[Dict]:
        """
        Fast rank of strategies for current regime (no param sweep).
        Returns sorted list for signal-card ML bonus.
        """
        regime_info = _regime_from_data(hist)
        regime = regime_info["label"]
        scored = []
        for name, cfg in STRATEGY_REGISTRY.items():
            try:
                r = cfg["fn"](hist.copy(), cfg["default_params"])
                score = _score_result(r, regime, name)
                adj = self._score_adjustments.get(name, 1.0)
                scored.append({"strategy": name, "score": round(score * adj, 1),
                               "regime_fit": regime in cfg["regime_fit"]})
            except Exception:
                scored.append({"strategy": name, "score": 0, "regime_fit": False})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def record_signal_outcome(self, strategy: str, was_correct: bool):
        """
        Feed live outcomes back in to self-correct scoring weights.
        Called whenever a signal hits target (correct) or stop (incorrect).
        """
        if was_correct:
            self._accuracy[strategy]["hits"] += 1
        else:
            self._accuracy[strategy]["misses"] += 1

        # Recalculate adjustment factor
        acc = self._accuracy[strategy]
        total = acc["hits"] + acc["misses"]
        if total >= 10:
            live_wr = acc["hits"] / total
            # Neutral = 0.5 wr → factor 1.0; above → bonus; below → penalty
            factor = 0.6 + live_wr * 0.8  # range ≈ 0.6 to 1.4
            self._score_adjustments[strategy] = round(factor, 3)
            logger.info(f"Self-corrected {strategy}: live_wr={live_wr:.2f} → factor={factor:.3f}")

    def get_accuracy_summary(self) -> Dict[str, Dict]:
        """Return live accuracy per strategy for the /strategy_report command."""
        out = {}
        for strat, acc in self._accuracy.items():
            total = acc["hits"] + acc["misses"]
            out[strat] = {
                "hits": acc["hits"],
                "misses": acc["misses"],
                "total": total,
                "live_win_rate": round(acc["hits"] / total * 100, 1) if total else None,
                "score_factor": self._score_adjustments.get(strat, 1.0),
            }
        return out

    # ── internal helpers ──────────────────────────────────────────────────

    def _walk_forward(
        self, hist: pd.DataFrame, strategy_name: str,
        n_folds: int = 4
    ) -> Dict[str, Any]:
        """
        Split hist into n_folds, train (find best params) on first half,
        test on second half of each fold. Returns OOS (out-of-sample) metrics.
        """
        cfg = STRATEGY_REGISTRY.get(strategy_name)
        if not cfg or len(hist) < 120:
            return {}

        fold_size = len(hist) // n_folds
        oos_results = []

        for fold in range(n_folds - 1):
            train_end = (fold + 2) * fold_size
            test_start = train_end
            test_end = min(train_end + fold_size, len(hist))

            train_data = hist.iloc[:train_end].copy()
            test_data = hist.iloc[test_start:test_end].copy()

            if len(test_data) < 20:
                continue

            # Quick best params on train (use only a small grid subset)
            grid = cfg["param_grid"]
            best_p = cfg["default_params"]
            best_s = -999
            sample_keys = list(grid.keys())[:2]  # limit to 2 params for speed
            for v0 in grid[sample_keys[0]][:3]:
                for v1 in (grid[sample_keys[1]][:3] if len(sample_keys) > 1 else [None]):
                    p = dict(cfg["default_params"])
                    p[sample_keys[0]] = v0
                    if v1 is not None:
                        p[sample_keys[1]] = v1
                    try:
                        r = cfg["fn"](train_data, p)
                        s = _score_result(r, "NEUTRAL", strategy_name)
                        if s > best_s:
                            best_s = s
                            best_p = p
                    except Exception:
                        pass

            # Test on OOS
            try:
                oos_r = cfg["fn"](test_data, best_p)
                oos_results.append({
                    "fold": fold,
                    "trades": oos_r["trades"],
                    "win_rate": oos_r["win_rate"],
                    "sharpe": oos_r["sharpe"],
                    "max_dd": oos_r["max_dd"],
                    "score": _score_result(oos_r, "NEUTRAL", strategy_name),
                })
            except Exception:
                pass

        if not oos_results:
            return {}

        avg_oos_sharpe = float(np.mean([r["sharpe"] for r in oos_results]))
        avg_oos_wr = float(np.mean([r["win_rate"] for r in oos_results]))
        avg_oos_score = float(np.mean([r["score"] for r in oos_results]))

        return {
            "folds": len(oos_results),
            "avg_oos_sharpe": round(avg_oos_sharpe, 3),
            "avg_oos_win_rate": round(avg_oos_wr, 3),
            "avg_oos_score": round(avg_oos_score, 1),
            "fold_detail": oos_results,
            "stable": avg_oos_sharpe > 0 and avg_oos_wr > 0.4,
        }

    def _param_sweep(
        self, hist: pd.DataFrame, strategy_name: str
    ) -> Tuple[Dict, float]:
        """
        Grid search best params for strategy_name on hist data.
        Returns (best_params, best_score).
        """
        cfg = STRATEGY_REGISTRY.get(strategy_name)
        if not cfg:
            return {}, 0.0

        regime_info = _regime_from_data(hist)
        regime = regime_info["label"]
        grid = cfg["param_grid"]
        keys = list(grid.keys())

        best_params = dict(cfg["default_params"])
        best_score = 0.0

        # Enumerate combinations (cap at 81 to stay fast)
        combos: List[Dict] = [{}]
        for k in keys:
            new_combos = []
            for c in combos:
                for v in grid[k]:
                    nc = dict(c)
                    nc[k] = v
                    new_combos.append(nc)
            combos = new_combos
            if len(combos) > 81:
                combos = random.sample(combos, 81)

        for combo in combos:
            p = dict(cfg["default_params"])
            p.update(combo)
            try:
                r = cfg["fn"](hist, p)
                s = _score_result(r, regime, strategy_name)
                if s > best_score:
                    best_score = s
                    best_params = p
            except Exception:
                pass

        return best_params, best_score

    def _cross_check(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Check whether strategies agree or conflict.
        Returns verdict + reasoning.
        """
        scored = [(name, r["score"]) for name, r in results.items() if r["trades"] >= 3]
        if not scored:
            return {"verdict": "INSUFFICIENT_DATA", "explanation": "Too few trades to cross-check."}

        good = [n for n, s in scored if s >= 55]
        bad = [n for n, s in scored if s < 35]
        mid = [n for n, s in scored if 35 <= s < 55]

        if len(good) >= 2:
            verdict = "STRONG_AGREEMENT"
            explanation = (
                f"{', '.join(good)} all score ≥ 55 on this data. "
                f"Multiple strategies agree → higher conviction."
            )
        elif len(good) == 1 and len(bad) >= 2:
            verdict = "MIXED_SIGNAL"
            explanation = (
                f"Only {good[0]} is strong. {', '.join(bad)} are weak here. "
                f"Use {good[0]} only, smaller position."
            )
        elif len(bad) >= 3:
            verdict = "AVOID"
            explanation = (
                f"All strategies score poorly on this ticker/period. "
                f"Market structure unfavourable — sit out or wait."
            )
        else:
            verdict = "MODERATE"
            explanation = (
                f"Mixed results. {len(good)} strong, {len(mid)} neutral, {len(bad)} weak. "
                f"Proceed cautiously with best-scoring strategy."
            )

        return {
            "verdict": verdict,
            "explanation": explanation,
            "good_strategies": good,
            "weak_strategies": bad,
        }

    def _regime_recommendation(self, regime: str, results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Given current regime + backtest results, recommend the best strategy.
        """
        candidates = []
        for name, r in results.items():
            fit = regime in STRATEGY_REGISTRY.get(name, {}).get("regime_fit", [])
            candidates.append({
                "strategy": name,
                "score": r.get("score", 0),
                "regime_fit": fit,
                "trades": r.get("trades", 0),
            })

        # Sort: regime-fit first, then by score
        candidates.sort(key=lambda x: (x["regime_fit"], x["score"]), reverse=True)
        best = candidates[0] if candidates else {}

        regime_explanations = {
            "RISK_ON_TRENDING": "Market is trending up with good breadth — momentum & breakout excel",
            "LOW_VOL_UPTREND": "Quiet uptrend — swing trades work best here",
            "NEUTRAL": "Ranging market — mean reversion setups most reliable",
            "RISK_OFF": "Risk-off environment — reduce size, mean reversion only with tight stops",
            "HIGH_VOL": "High volatility — only momentum with strict stops; wider swings expected",
            "RISK_ON_HIGH_VOL": "Risk-on but volatile — breakouts work but expect whipsaws",
            "DOWNTREND": "Downtrend — avoid long strategies; wait for regime change",
            "LOW_VOL_RANGING": "Tight, low-vol range — mean reversion edges, small size",
            "LOW_VOL_DOWNTREND": "Quiet slide lower — reduce exposure, wait",
        }
        regime_expl = regime_explanations.get(regime, "Regime unclear — use smallest size")

        return {
            "regime": regime,
            "explanation": regime_expl,
            "best_strategy": best.get("strategy", "N/A"),
            "best_score": best.get("score", 0),
            "regime_fit": best.get("regime_fit", False),
            "all_candidates": candidates,
        }

    def _correction_notes(self) -> List[str]:
        """Generate notes about self-correction that has happened."""
        notes = []
        for strat, factor in self._score_adjustments.items():
            acc = self._accuracy.get(strat, {})
            total = acc.get("hits", 0) + acc.get("misses", 0)
            live_wr = acc.get("hits", 0) / total * 100 if total else 0
            if factor > 1.05:
                notes.append(
                    f"✅ {strat}: live win-rate {live_wr:.0f}% → boosted score ×{factor:.2f}"
                )
            elif factor < 0.95:
                notes.append(
                    f"⚠️ {strat}: live win-rate {live_wr:.0f}% → reduced score ×{factor:.2f}"
                )
        if not notes:
            notes.append("No self-corrections yet — feed more live signal outcomes.")
        return notes

    def _monte_carlo(self, returns: List[float], n: int = 500) -> Dict[str, Any]:
        """Fast Monte Carlo on trade returns."""
        if len(returns) < 10:
            return {}
        pnls = np.array(returns)
        finals = []
        for _ in range(n):
            shuffled = np.random.permutation(pnls)
            finals.append(float(np.prod(1 + shuffled)))
        finals_arr = np.array(finals)
        return {
            "n": n,
            "median_final": round(float(np.median(finals_arr)), 3),
            "p5_final": round(float(np.percentile(finals_arr, 5)), 3),
            "p95_final": round(float(np.percentile(finals_arr, 95)), 3),
            "pct_profitable": round(float((finals_arr > 1.0).mean() * 100), 1),
        }


# Module-level singleton (shared across Discord bot tasks)
_optimizer = StrategyOptimizer()


def get_optimizer() -> StrategyOptimizer:
    """Return the global StrategyOptimizer singleton."""
    return _optimizer
