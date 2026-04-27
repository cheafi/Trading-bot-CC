"""
MacroRegimeEngine — Sprint 62
==============================
Computes market regime from real benchmark data (SPY/QQQ/VIX/IWM/HYG)
instead of accepting caller-provided regime dicts.

Regime states:
  RISK_ON     — Broad uptrend, low vol, healthy breadth
  UPTREND     — Positive trend but caution signals emerging
  SIDEWAYS    — Range-bound, mixed signals
  TRANSITIONAL— Trend changing, conflicting signals
  RISK_OFF    — Defensive posture, elevated vol
  DOWNTREND   — Confirmed bearish trend
  CRISIS      — Extreme conditions, capital preservation

Usage:
    engine = MacroRegimeEngine()
    regime = engine.compute(spy_closes, qqq_closes, vix_closes,
                            iwm_closes=iwm, hyg_closes=hyg)
    # regime = {"trend": "RISK_ON", "vix_level": 14.2, "breadth": "healthy", ...}
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class RegimeResult:
    """Complete regime assessment."""

    trend: str  # RISK_ON / UPTREND / SIDEWAYS / etc.
    vix_level: float = 0.0
    vix_regime: str = "NORMAL"  # LOW / NORMAL / ELEVATED / EXTREME
    spy_trend: str = "FLAT"  # UP / FLAT / DOWN
    qqq_trend: str = "FLAT"
    breadth: str = "neutral"  # healthy / neutral / weak / divergent
    risk_score: float = 50.0  # 0 (max risk-on) to 100 (max crisis)
    signals: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "trend": self.trend,
            "vix_level": round(self.vix_level, 2),
            "vix_regime": self.vix_regime,
            "spy_trend": self.spy_trend,
            "qqq_trend": self.qqq_trend,
            "breadth": self.breadth,
            "risk_score": round(self.risk_score, 1),
            "signals": self.signals,
            "confidence": round(self.confidence, 3),
        }


def _sma(prices: list[float], period: int) -> float:
    """Simple moving average of last `period` values."""
    if len(prices) < period:
        return sum(prices) / max(len(prices), 1)
    return sum(prices[-period:]) / period


def _returns(prices: list[float], period: int) -> float:
    """Percentage return over last `period` bars."""
    if len(prices) < period + 1:
        return 0.0
    p0 = prices[-(period + 1)]
    if p0 == 0:
        return 0.0
    return (prices[-1] - p0) / p0 * 100


def _trend_direction(prices: list[float]) -> str:
    """Classify trend from SMA20 vs SMA50 and price position."""
    if len(prices) < 50:
        return "FLAT"
    sma20 = _sma(prices, 20)
    sma50 = _sma(prices, 50)
    price = prices[-1]
    if price > sma20 > sma50:
        return "UP"
    elif price < sma20 < sma50:
        return "DOWN"
    else:
        return "FLAT"


def _max_drawdown(prices: list[float], period: int = 50) -> float:
    """Max drawdown over last `period` bars as positive percentage."""
    window = prices[-period:] if len(prices) >= period else prices
    if not window:
        return 0.0
    peak = window[0]
    max_dd = 0.0
    for p in window:
        if p > peak:
            peak = p
        dd = (peak - p) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd


class MacroRegimeEngine:
    """
    Computes market regime from benchmark price arrays.

    All price arrays should be daily closes, most recent last.
    Minimum 50 bars for full accuracy; works with 20+ bars at reduced confidence.
    """

    # VIX thresholds
    VIX_LOW = 14.0
    VIX_ELEVATED = 22.0
    VIX_HIGH = 30.0
    VIX_EXTREME = 40.0

    def compute(
        self,
        spy_closes: list[float],
        qqq_closes: list[float] | None = None,
        vix_closes: list[float] | None = None,
        iwm_closes: list[float] | None = None,
        hyg_closes: list[float] | None = None,
    ) -> RegimeResult:
        """
        Compute current market regime from benchmark data.

        Args:
            spy_closes: SPY daily closes (required, 50+ bars ideal)
            qqq_closes: QQQ daily closes (optional, improves breadth)
            vix_closes: VIX daily closes (optional, improves vol regime)
            iwm_closes: IWM daily closes (optional, improves breadth)
            hyg_closes: HYG daily closes (optional, credit stress signal)

        Returns:
            RegimeResult with trend, vix_level, breadth, risk_score, etc.
        """
        result = RegimeResult(trend="SIDEWAYS")
        signals = []
        risk_points = 50.0  # Start neutral

        # ── SPY trend (required) ──
        result.spy_trend = _trend_direction(spy_closes)
        spy_ret_20d = _returns(spy_closes, 20)
        spy_ret_50d = _returns(spy_closes, 50)
        spy_dd = _max_drawdown(spy_closes, 50)

        if result.spy_trend == "UP":
            risk_points -= 15
            signals.append("SPY uptrend (above SMA20 > SMA50)")
        elif result.spy_trend == "DOWN":
            risk_points += 15
            signals.append("SPY downtrend (below SMA20 < SMA50)")

        if spy_ret_20d < -5:
            risk_points += 10
            signals.append(f"SPY 20d return {spy_ret_20d:.1f}% (weak)")
        elif spy_ret_20d > 3:
            risk_points -= 5
            signals.append(f"SPY 20d return +{spy_ret_20d:.1f}%")

        if spy_dd > 10:
            risk_points += 15
            signals.append(f"SPY drawdown {spy_dd:.1f}% (significant)")
        elif spy_dd > 5:
            risk_points += 5
            signals.append(f"SPY drawdown {spy_dd:.1f}%")

        # ── VIX regime ──
        if vix_closes and len(vix_closes) >= 1:
            vix = vix_closes[-1]
            result.vix_level = vix
            if vix < self.VIX_LOW:
                result.vix_regime = "LOW"
                risk_points -= 10
                signals.append(f"VIX {vix:.1f} (low volatility)")
            elif vix < self.VIX_ELEVATED:
                result.vix_regime = "NORMAL"
                signals.append(f"VIX {vix:.1f} (normal)")
            elif vix < self.VIX_HIGH:
                result.vix_regime = "ELEVATED"
                risk_points += 10
                signals.append(f"VIX {vix:.1f} (elevated)")
            elif vix < self.VIX_EXTREME:
                result.vix_regime = "HIGH"
                risk_points += 20
                signals.append(f"VIX {vix:.1f} (high)")
            else:
                result.vix_regime = "EXTREME"
                risk_points += 30
                signals.append(f"VIX {vix:.1f} (EXTREME)")

            # VIX spike detection (20d)
            if len(vix_closes) >= 20:
                vix_20d_avg = _sma(vix_closes, 20)
                if vix > vix_20d_avg * 1.3:
                    risk_points += 10
                    signals.append(
                        f"VIX spiking ({vix:.0f} vs 20d avg {vix_20d_avg:.0f})"
                    )

        # ── QQQ trend (growth leadership) ──
        if qqq_closes and len(qqq_closes) >= 20:
            result.qqq_trend = _trend_direction(qqq_closes)
            qqq_ret = _returns(qqq_closes, 20)

            if result.qqq_trend == "UP" and result.spy_trend == "UP":
                risk_points -= 5
                signals.append("QQQ+SPY aligned uptrend")
            elif result.qqq_trend == "DOWN" and result.spy_trend == "UP":
                signals.append("QQQ lagging (growth rotation out)")
                risk_points += 5
            elif result.qqq_trend == "DOWN" and result.spy_trend == "DOWN":
                risk_points += 5
                signals.append("QQQ+SPY aligned downtrend")

        # ── IWM breadth (small caps confirm/diverge) ──
        if iwm_closes and len(iwm_closes) >= 20:
            iwm_trend = _trend_direction(iwm_closes)
            if iwm_trend == "UP" and result.spy_trend == "UP":
                result.breadth = "healthy"
                risk_points -= 5
                signals.append("Breadth healthy (IWM confirms)")
            elif iwm_trend == "DOWN" and result.spy_trend == "UP":
                result.breadth = "divergent"
                risk_points += 8
                signals.append("Breadth divergent (IWM lagging SPY)")
            elif iwm_trend == "DOWN":
                result.breadth = "weak"
                risk_points += 5
                signals.append("Breadth weak (IWM downtrend)")

        # ── HYG credit stress ──
        if hyg_closes and len(hyg_closes) >= 20:
            hyg_ret = _returns(hyg_closes, 20)
            if hyg_ret < -2:
                risk_points += 10
                signals.append(f"Credit stress (HYG {hyg_ret:.1f}%)")
            elif hyg_ret < -1:
                risk_points += 5
                signals.append(f"Credit caution (HYG {hyg_ret:.1f}%)")

        # ── Clamp risk score ──
        result.risk_score = max(0, min(100, risk_points))
        result.signals = signals

        # ── Map risk score → regime label ──
        if result.risk_score <= 20:
            result.trend = "RISK_ON"
            result.confidence = 0.85
        elif result.risk_score <= 35:
            result.trend = "UPTREND"
            result.confidence = 0.75
        elif result.risk_score <= 50:
            result.trend = "SIDEWAYS"
            result.confidence = 0.60
        elif result.risk_score <= 60:
            result.trend = "TRANSITIONAL"
            result.confidence = 0.55
        elif result.risk_score <= 75:
            result.trend = "RISK_OFF"
            result.confidence = 0.65
        elif result.risk_score <= 85:
            result.trend = "DOWNTREND"
            result.confidence = 0.70
        else:
            result.trend = "CRISIS"
            result.confidence = 0.80

        # Reduce confidence if few data sources
        data_sources = 1  # SPY always present
        for arr in [qqq_closes, vix_closes, iwm_closes, hyg_closes]:
            if arr and len(arr) >= 20:
                data_sources += 1
        if data_sources <= 2:
            result.confidence *= 0.8

        return result


class StockVsSPY:
    """
    Compare a stock's performance against SPY across multiple dimensions.

    Usage:
        comparison = StockVsSPY.compare(stock_closes, spy_closes, ticker="NVDA")
    """

    @staticmethod
    def compare(
        stock_closes: list[float],
        spy_closes: list[float],
        ticker: str = "STOCK",
    ) -> dict:
        """
        Full stock-vs-SPY comparison.

        Returns dict with:
            performance: {stock_ret, spy_ret, alpha, periods}
            relative_strength: {rs_ratio, rs_percentile, rs_trend}
            risk: {stock_vol, spy_vol, beta_approx, max_dd_stock, max_dd_spy}
            correlation: {corr_20d}
            verdict: str summary
        """
        n = min(len(stock_closes), len(spy_closes))
        if n < 5:
            return {"error": "Need at least 5 data points", "ticker": ticker}

        stock = stock_closes[-n:]
        spy = spy_closes[-n:]

        result = {"ticker": ticker}

        # ── Performance across timeframes ──
        perf = {}
        for label, period in [
            ("5d", 5),
            ("20d", 20),
            ("60d", 60),
            ("120d", 120),
            ("250d", 250),
        ]:
            if n >= period + 1:
                s_ret = (stock[-1] - stock[-(period + 1)]) / stock[-(period + 1)] * 100
                b_ret = (spy[-1] - spy[-(period + 1)]) / spy[-(period + 1)] * 100
                perf[label] = {
                    "stock_return": round(s_ret, 2),
                    "spy_return": round(b_ret, 2),
                    "alpha": round(s_ret - b_ret, 2),
                }
        result["performance"] = perf

        # ── Relative Strength ──
        if n >= 21:
            stock_ret_20 = (stock[-1] / stock[-21] - 1) * 100
            spy_ret_20 = (spy[-1] / spy[-21] - 1) * 100
            rs_ratio = (
                (1 + stock_ret_20 / 100) / (1 + spy_ret_20 / 100)
                if spy_ret_20 != -100
                else 1.0
            )
            result["relative_strength"] = {
                "rs_ratio": round(rs_ratio, 4),
                "stock_20d_ret": round(stock_ret_20, 2),
                "spy_20d_ret": round(spy_ret_20, 2),
                "rs_trend": (
                    "OUTPERFORMING"
                    if rs_ratio > 1.02
                    else "UNDERPERFORMING" if rs_ratio < 0.98 else "INLINE"
                ),
            }

        # ── Risk metrics ──
        if n >= 21:
            s_rets = [
                (stock[i] - stock[i - 1]) / stock[i - 1]
                for i in range(1, n)
                if stock[i - 1] != 0
            ]
            b_rets = [
                (spy[i] - spy[i - 1]) / spy[i - 1]
                for i in range(1, n)
                if spy[i - 1] != 0
            ]
            s_vol = (
                _std(s_rets[-20:]) * math.sqrt(252) * 100 if len(s_rets) >= 20 else 0
            )
            b_vol = (
                _std(b_rets[-20:]) * math.sqrt(252) * 100 if len(b_rets) >= 20 else 0
            )

            # Approximate beta
            if len(s_rets) >= 20 and len(b_rets) >= 20:
                cov = _cov(s_rets[-20:], b_rets[-20:])
                var_b = _var(b_rets[-20:])
                beta = cov / var_b if var_b > 0 else 1.0
            else:
                beta = 1.0

            result["risk"] = {
                "stock_annual_vol": round(s_vol, 1),
                "spy_annual_vol": round(b_vol, 1),
                "beta": round(beta, 2),
                "max_dd_stock": round(_max_drawdown(stock, min(n, 250)), 2),
                "max_dd_spy": round(_max_drawdown(spy, min(n, 250)), 2),
            }

            # Correlation
            if len(s_rets) >= 20 and len(b_rets) >= 20:
                corr = _corr(s_rets[-20:], b_rets[-20:])
                result["correlation"] = {"corr_20d": round(corr, 3)}

        # ── Verdict ──
        verdicts = []
        if perf.get("20d", {}).get("alpha", 0) > 3:
            verdicts.append(f"{ticker} strongly outperforming SPY over 20d")
        elif perf.get("20d", {}).get("alpha", 0) < -3:
            verdicts.append(f"{ticker} underperforming SPY over 20d")

        rs = result.get("relative_strength", {})
        if rs.get("rs_trend") == "OUTPERFORMING":
            verdicts.append("Relative strength positive — leader")
        elif rs.get("rs_trend") == "UNDERPERFORMING":
            verdicts.append("Relative strength negative — laggard")

        risk = result.get("risk", {})
        if risk.get("beta", 1) > 1.5:
            verdicts.append(f"High beta ({risk['beta']:.1f}) — amplified SPY moves")
        elif risk.get("beta", 1) < 0.5:
            verdicts.append(f"Low beta ({risk['beta']:.1f}) — defensive")

        if risk.get("max_dd_stock", 0) > risk.get("max_dd_spy", 0) * 2:
            verdicts.append("Drawdown risk significantly worse than SPY")

        result["verdict"] = (
            " | ".join(verdicts) if verdicts else f"{ticker} tracking close to SPY"
        )

        return result


# ── Math helpers ──


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _var(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / (len(values) - 1)


def _cov(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma = sum(a[-n:]) / n
    mb = sum(b[-n:]) / n
    return sum((a[-n + i] - ma) * (b[-n + i] - mb) for i in range(n)) / (n - 1)


def _corr(a: list[float], b: list[float]) -> float:
    sa = _std(a)
    sb = _std(b)
    if sa == 0 or sb == 0:
        return 0.0
    return _cov(a, b) / (sa * sb)
