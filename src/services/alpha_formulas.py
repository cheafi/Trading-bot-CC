"""Canonical OHLCV alpha formulas (research bench — qlib/k101/gtja subset)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

# First 30 qlib manifest IDs map to these named formulas (v1 pack).
QLIB_CANONICAL: Dict[str, str] = {
    f"qlib_{i:03d}": key
    for i, key in enumerate(
        [
            "roc",
            "ma_dev",
            "volatility",
            "volume_surge",
            "rsi",
            "macd_hist",
            "bb_position",
            "atr_pct",
            "overnight",
            "intraday",
            "close_to_high",
            "close_to_low",
            "vwap_dev",
            "obv_slope",
            "williams_r",
            "stoch_k",
            "cci",
            "mfi",
            "ema_spread",
            "max_dd",
            "ret_skew",
            "ret_kurt",
            "autocorr_1",
            "high_low_range",
            "gap_follow",
            "dollar_vol_trend",
            "range_expansion",
            "vol_price_corr",
            "trend_strength",
            "mean_reversion_z",
        ],
        start=1,
    )
}


def _id_map(prefix: str, keys: list[str]) -> Dict[str, str]:
    return {f"{prefix}_{i:03d}": key for i, key in enumerate(keys, start=1)}


K101_CANONICAL: Dict[str, str] = _id_map(
    "k101",
    [
        "log_momentum",
        "price_position",
        "linear_trend",
        "realized_vol",
        "parkinson_vol",
        "amihud",
        "up_ratio",
        "lower_shadow",
        "upper_shadow",
        "body_ratio",
        "vol_of_vol",
        "sharpe_proxy",
        "high_break",
        "low_break",
        "advances_declines",
        "open_momentum",
        "close_momentum",
        "typical_price_dev",
        "weighted_close_dev",
        "median_dev",
        "range_vol_ratio",
        "gap_size",
        "overnight_vol",
        "intraday_vol",
        "volume_trend",
        "price_volume_trend",
        "neg_vol_ratio",
        "pos_vol_ratio",
        "hl_momentum",
        "oc_spread",
    ],
)

GTJA_CANONICAL: Dict[str, str] = _id_map(
    "gtja",
    [
        "rank_roc",
        "rank_volatility",
        "rank_volume",
        "decay_momentum",
        "delay_roc",
        "industry_neutral_roc",
        "scale_roc",
        "signed_power_roc",
        "ts_argmax",
        "ts_argmin",
        "ts_rank_close",
        "delta_rank",
        "correlation_hl",
        "correlation_cv",
        "sum_returns",
        "prod_returns",
        "min_return",
        "max_return",
        "std_high",
        "std_low",
        "mean_gap",
        "skew_volume",
        "kurt_volume",
        "beta_market_proxy",
        "alpha_market_proxy",
        "residual_vol",
        "trend_consistency",
        "drawdown_slope",
        "recovery_speed",
        "vol_regime",
    ],
)

# Manifest academic pack (acad_001–020) — template names → bench formulas
_ACAD_TEMPLATE_FORMULAS = (
    "roc",
    "mean_reversion_z",
    "volatility",
    "rsi",
    "ema_spread",
    "high_low_range",
    "gap_follow",
    "dollar_vol_trend",
)
ACAD_CANONICAL: Dict[str, str] = {
    f"acad_{i:03d}": _ACAD_TEMPLATE_FORMULAS[(i - 1) % len(_ACAD_TEMPLATE_FORMULAS)]
    for i in range(1, 21)
}

# PIT fundamental pack (pit_001–008) — OHLCV-only, no lookahead fundamentals
PIT_CANONICAL: Dict[str, str] = _id_map(
    "pit",
    [
        "roc",
        "ma_dev",
        "volatility",
        "volume_surge",
        "rsi",
        "atr_pct",
        "dollar_vol_trend",
        "obv_slope",
    ],
)

CANONICAL_BY_ID: Dict[str, str] = {
    **QLIB_CANONICAL,
    **K101_CANONICAL,
    **GTJA_CANONICAL,
    **ACAD_CANONICAL,
    **PIT_CANONICAL,
}

# Full manifest zoo (478 IDs) — cycle named formulas for IDs beyond v1 pack heads.
for _prefix, _count, _seed in (
    ("qlib", 158, QLIB_CANONICAL),
    ("k101", 101, K101_CANONICAL),
    ("gtja", 191, GTJA_CANONICAL),
):
    _pool = list(dict.fromkeys(_seed.values()))
    for _i in range(1, _count + 1):
        _aid = f"{_prefix}_{_i:03d}"
        if _aid not in CANONICAL_BY_ID:
            CANONICAL_BY_ID[_aid] = _pool[(_i - 1) % len(_pool)]


def canonical_formula_for_id(alpha_id: str) -> Optional[str]:
    return CANONICAL_BY_ID.get(str(alpha_id or "").strip())


def compute_canonical_factor(
    frame: pd.DataFrame, formula: str, window: int
) -> pd.Series:
    close = frame["close"]
    open_ = frame.get("open", close)
    high = frame.get("high", close)
    low = frame.get("low", close)
    vol = frame.get("volume", pd.Series(1.0, index=close.index))
    w = max(3, min(int(window or 10), 120))
    ret = close.pct_change()
    f = str(formula or "roc").lower()

    if f == "roc":
        return close.pct_change(w)
    if f == "ma_dev":
        ma = close.rolling(w).mean()
        return close / ma - 1
    if f == "volatility":
        return ret.rolling(w).std(ddof=1)
    if f == "volume_surge":
        return vol / vol.rolling(w).mean() - 1
    if f == "rsi":
        delta = close.diff()
        up = delta.clip(lower=0).rolling(14).mean()
        down = (-delta.clip(upper=0)).rolling(14).mean()
        rs = up / down.replace(0, np.nan)
        return 100 - (100 / (1 + rs))
    if f == "macd_hist":
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd - signal
    if f == "bb_position":
        ma = close.rolling(w).mean()
        sd = close.rolling(w).std(ddof=1)
        upper = ma + 2 * sd
        lower = ma - 2 * sd
        return (close - lower) / (upper - lower).replace(0, np.nan)
    if f == "atr_pct":
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(w).mean()
        return atr / close
    if f == "overnight":
        return open_ / close.shift(1) - 1
    if f == "intraday":
        return close / open_ - 1
    if f == "close_to_high":
        return close / high - 1
    if f == "close_to_low":
        return close / low - 1
    if f == "vwap_dev":
        pv = (close * vol).rolling(w).sum()
        vv = vol.rolling(w).sum().replace(0, np.nan)
        vwap = pv / vv
        return close / vwap - 1
    if f == "obv_slope":
        obv = (np.sign(ret.fillna(0)) * vol).cumsum()
        return obv.diff(w) / w
    if f == "williams_r":
        hh = high.rolling(w).max()
        ll = low.rolling(w).min()
        return -100 * (hh - close) / (hh - ll).replace(0, np.nan)
    if f == "stoch_k":
        hh = high.rolling(w).max()
        ll = low.rolling(w).min()
        return 100 * (close - ll) / (hh - ll).replace(0, np.nan)
    if f == "cci":
        tp = (high + low + close) / 3
        ma = tp.rolling(w).mean()
        md = (tp - ma).abs().rolling(w).mean()
        return (tp - ma) / (0.015 * md.replace(0, np.nan))
    if f == "mfi":
        tp = (high + low + close) / 3
        mf = tp * vol
        pos = mf.where(tp > tp.shift(1), 0).rolling(w).sum()
        neg = mf.where(tp < tp.shift(1), 0).rolling(w).sum()
        mfr = pos / neg.replace(0, np.nan)
        return 100 - (100 / (1 + mfr))
    if f == "ema_spread":
        return (
            close.ewm(span=max(3, w // 3), adjust=False).mean()
            / close.ewm(span=w, adjust=False).mean()
            - 1
        )
    if f == "max_dd":
        roll_max = close.rolling(w).max()
        return close / roll_max - 1
    if f == "ret_skew":
        return ret.rolling(w).skew()
    if f == "ret_kurt":
        return ret.rolling(w).kurt()
    if f == "autocorr_1":
        return ret.rolling(w).apply(lambda s: s.autocorr(lag=1), raw=False)
    if f == "high_low_range":
        return (high - low).rolling(w).mean() / close
    if f == "gap_follow":
        gap = open_ / close.shift(1) - 1
        return gap * ret.shift(1)
    if f == "dollar_vol_trend":
        return (close * vol).pct_change(w)
    if f == "range_expansion":
        rng = (high - low) / close
        return rng / rng.rolling(w).mean() - 1
    if f == "vol_price_corr":
        return close.rolling(w).corr(vol)
    if f == "trend_strength":
        return ret.rolling(w).sum() / ret.rolling(w).std(ddof=1).replace(0, np.nan)
    if f == "mean_reversion_z":
        ma = close.rolling(w).mean()
        sd = close.rolling(w).std(ddof=1)
        return -(close - ma) / sd.replace(0, np.nan)
    if f == "log_momentum":
        return np.log(close / close.shift(w))
    if f == "price_position":
        lo = low.rolling(w).min()
        hi = high.rolling(w).max()
        return (close - lo) / (hi - lo).replace(0, np.nan)
    if f == "linear_trend":
        return close.rolling(w).apply(
            lambda s: np.polyfit(np.arange(len(s)), s, 1)[0] if len(s) > 2 else np.nan,
            raw=False,
        )
    if f == "realized_vol":
        return (ret**2).rolling(w).sum().pow(0.5)
    if f == "parkinson_vol":
        hl = np.log(high / low.replace(0, np.nan))
        return (hl**2).rolling(w).mean().pow(0.5)
    if f == "amihud":
        dv = (close * vol).replace(0, np.nan)
        return (ret.abs() / dv).rolling(w).mean()
    if f == "up_ratio":
        up = (ret > 0).astype(float)
        return up.rolling(w).mean()
    if f == "lower_shadow":
        body = (close - open_).abs()
        shadow = (open_.combine(close, min) - low).abs()
        return shadow / body.replace(0, np.nan)
    if f == "upper_shadow":
        body = (close - open_).abs()
        shadow = (high - open_.combine(close, max)).abs()
        return shadow / body.replace(0, np.nan)
    if f == "body_ratio":
        return (close - open_).abs() / (high - low).replace(0, np.nan)
    if f == "vol_of_vol":
        v = ret.rolling(w // 2 or 3).std(ddof=1)
        return v.rolling(w).std(ddof=1)
    if f == "sharpe_proxy":
        return ret.rolling(w).mean() / ret.rolling(w).std(ddof=1).replace(0, np.nan)
    if f == "high_break":
        return close / high.rolling(w).max() - 1
    if f == "low_break":
        return close / low.rolling(w).min() - 1
    if f == "advances_declines":
        return (ret > 0).rolling(w).sum() - (ret < 0).rolling(w).sum()
    if f == "open_momentum":
        return open_.pct_change(w)
    if f == "close_momentum":
        return close.pct_change(w)
    if f == "typical_price_dev":
        tp = (high + low + close) / 3
        return tp / tp.rolling(w).mean() - 1
    if f == "weighted_close_dev":
        wc = (high + low + 2 * close) / 4
        return wc / wc.rolling(w).mean() - 1
    if f == "median_dev":
        return close / close.rolling(w).median() - 1
    if f == "range_vol_ratio":
        rng = (high - low) / close
        return rng / ret.rolling(w).std(ddof=1).replace(0, np.nan)
    if f == "gap_size":
        return (open_ / close.shift(1) - 1).abs()
    if f == "overnight_vol":
        oret = open_ / close.shift(1) - 1
        return oret.rolling(w).std(ddof=1)
    if f == "intraday_vol":
        iret = close / open_ - 1
        return iret.rolling(w).std(ddof=1)
    if f == "volume_trend":
        return vol.pct_change(w)
    if f == "price_volume_trend":
        return (ret * vol).rolling(w).sum()
    if f == "neg_vol_ratio":
        return vol.where(ret < 0, 0).rolling(w).sum() / vol.rolling(w).sum().replace(0, np.nan)
    if f == "pos_vol_ratio":
        return vol.where(ret > 0, 0).rolling(w).sum() / vol.rolling(w).sum().replace(0, np.nan)
    if f == "hl_momentum":
        return high.pct_change(w) - low.pct_change(w)
    if f == "oc_spread":
        return (close - open_).rolling(w).mean() / close
    if f == "rank_roc":
        s = close.pct_change(w)
        return s.rolling(w).rank(pct=True)
    if f == "rank_volatility":
        s = ret.rolling(w // 2 or 3).std(ddof=1)
        return s.rolling(w).rank(pct=True)
    if f == "rank_volume":
        return vol.rolling(w).rank(pct=True)
    if f == "decay_momentum":
        weights = np.arange(1, w + 1, dtype=float)
        weights /= weights.sum()

        def _wmean(s: pd.Series) -> float:
            if len(s) < w:
                return np.nan
            return float(np.dot(s.iloc[-w:], weights))

        return ret.rolling(w).apply(_wmean, raw=False)
    if f == "delay_roc":
        return close.pct_change(w).shift(w // 3 or 1)
    if f in ("industry_neutral_roc", "scale_roc", "signed_power_roc"):
        s = close.pct_change(w)
        if f == "scale_roc":
            return s / s.rolling(w).std(ddof=1).replace(0, np.nan)
        if f == "signed_power_roc":
            return np.sign(s) * (s.abs() ** 0.5)
        return s - s.rolling(w).mean()
    if f == "ts_argmax":
        return close.rolling(w).apply(lambda s: float(np.argmax(s.values)), raw=False)
    if f == "ts_argmin":
        return close.rolling(w).apply(lambda s: float(np.argmin(s.values)), raw=False)
    if f == "ts_rank_close":
        return close.rolling(w).rank(pct=True)
    if f == "delta_rank":
        r = close.rolling(w).rank(pct=True)
        return r - r.shift(w // 2 or 1)
    if f == "correlation_hl":
        return high.rolling(w).corr(low)
    if f == "correlation_cv":
        return close.rolling(w).corr(vol)
    if f == "sum_returns":
        return ret.rolling(w).sum()
    if f == "prod_returns":
        return (1 + ret).rolling(w).apply(lambda s: float(np.prod(s.values)), raw=False) - 1
    if f == "min_return":
        return ret.rolling(w).min()
    if f == "max_return":
        return ret.rolling(w).max()
    if f == "std_high":
        return high.pct_change().rolling(w).std(ddof=1)
    if f == "std_low":
        return low.pct_change().rolling(w).std(ddof=1)
    if f == "mean_gap":
        gap = open_ / close.shift(1) - 1
        return gap.rolling(w).mean()
    if f == "skew_volume":
        return vol.rolling(w).skew()
    if f == "kurt_volume":
        return vol.rolling(w).kurt()
    if f == "beta_market_proxy":
        m = ret.rolling(w).mean()
        return ret.rolling(w).cov(m) / m.rolling(w).var().replace(0, np.nan)
    if f == "alpha_market_proxy":
        m = ret.rolling(w).mean()
        beta = ret.rolling(w).cov(m) / m.rolling(w).var().replace(0, np.nan)
        return ret - beta * m
    if f == "residual_vol":
        m = ret.rolling(w).mean()
        return (ret - m).rolling(w).std(ddof=1)
    if f == "trend_consistency":
        return (ret > 0).rolling(w).mean() - 0.5
    if f == "drawdown_slope":
        dd = close / close.rolling(w).max() - 1
        return dd.diff(w // 3 or 1)
    if f == "recovery_speed":
        dd = close / close.rolling(w).max() - 1
        return -dd.diff(w // 3 or 1)
    if f == "vol_regime":
        short = ret.rolling(max(3, w // 4)).std(ddof=1)
        long = ret.rolling(w).std(ddof=1)
        return short / long.replace(0, np.nan)
    return close.pct_change(w)


def canonical_pack_stats() -> Dict[str, Any]:
    return {
        "canonical_count": len(CANONICAL_BY_ID),
        "manifest_total": 478,
        "packs": {
            "qlib": 158,
            "k101": 101,
            "gtja": 191,
            "academic": len(ACAD_CANONICAL),
            "pit_fundamental": len(PIT_CANONICAL),
        },
        "pack": "qlib_k101_gtja_v1",
        "note": "qlib/k101/gtja 001–030 each use named formulas; remainder use template proxies.",
    }
