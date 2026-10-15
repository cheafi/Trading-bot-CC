"""Correlation surface — edge density timeline with hysteresis (descriptive, not a signal)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Enter "fused bloc" when edge density >= high; exit when <= low.
_HYST_HIGH = 0.72
_HYST_LOW = 0.48
_CORR_EDGE = 0.65
_MIN_OBS = 20


def _local_calendar_index(series: pd.Series) -> pd.DatetimeIndex:
    idx = pd.to_datetime(series.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(None)
    return pd.DatetimeIndex(idx.normalize())


def align_histories_local_date(
    frames: Dict[str, pd.DataFrame],
) -> Tuple[pd.DataFrame, List[str]]:
    """Align close prices by each series' local calendar date (naive dates)."""
    closes: Dict[str, pd.Series] = {}
    warnings: List[str] = []
    for sym, df in frames.items():
        if df is None or getattr(df, "empty", True):
            warnings.append(f"{sym}:no_bars")
            continue
        col = "Close" if "Close" in df.columns else "close"
        s = df[col].astype(float).copy()
        s.index = _local_calendar_index(s)
        s = s[~s.index.duplicated(keep="last")]
        closes[sym] = s
    if len(closes) < 2:
        return pd.DataFrame(), warnings
    panel = pd.DataFrame(closes).sort_index().ffill()
    panel = panel.dropna(how="any")
    if len(panel) < _MIN_OBS:
        warnings.append("insufficient_aligned_bars")
    return panel, warnings


def _pair_correlation_defined(a: pd.Series, b: pd.Series) -> Tuple[Optional[float], str]:
    if a.std(ddof=1) == 0 or b.std(ddof=1) == 0:
        return None, "undefined_constant_history"
    c = float(a.corr(b))
    if np.isnan(c):
        return None, "undefined_nan"
    return c, "ok"


def edge_density_from_panel(panel: pd.DataFrame) -> Dict[str, Any]:
    """Fraction of pairs with |corr| >= edge threshold; unknown pairs excluded."""
    tickers = list(panel.columns)
    pairs_total = 0
    pairs_measured = 0
    pairs_high = 0
    undefined: List[str] = []
    matrix: Dict[str, Dict[str, Optional[float]]] = {t: {} for t in tickers}
    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1 :]:
            pairs_total += 1
            c, reason = _pair_correlation_defined(panel[ta], panel[tb])
            matrix[ta][tb] = c
            matrix[tb][ta] = c
            if c is None:
                undefined.append(f"{ta}/{tb}:{reason}")
                continue
            pairs_measured += 1
            if abs(c) >= _CORR_EDGE:
                pairs_high += 1
    density: Optional[float] = None
    if pairs_measured > 0:
        density = round(pairs_high / pairs_measured, 4)
    return {
        "edge_density": density,
        "pairs_total": pairs_total,
        "pairs_measured": pairs_measured,
        "pairs_high_corr": pairs_high,
        "undefined_pairs": undefined[:30],
        "corr_threshold": _CORR_EDGE,
        "note": (
            "Undefined pair correlations keep edge density unknown — "
            "constant-price histories cannot claim measured zero density."
        ),
        "matrix_sample": {
            ta: {tb: matrix[ta].get(tb) for tb in tickers if tb != ta}
            for ta in tickers[:6]
        },
    }


def hysteresis_timeline(densities: List[Optional[float]]) -> List[str]:
    """Map density series to fused / normal / unknown regimes."""
    state = "normal"
    out: List[str] = []
    for d in densities:
        if d is None:
            out.append("unknown")
            continue
        if state == "normal" and d >= _HYST_HIGH:
            state = "fused_bloc"
        elif state == "fused_bloc" and d <= _HYST_LOW:
            state = "normal"
        out.append(state)
    return out


async def build_correlation_regime_timeline(
    mds,
    tickers: List[str],
    *,
    period: str = "6mo",
    window: int = 40,
    step: int = 5,
) -> Dict[str, Any]:
    """Rolling edge-density timeline for correlation surface (research context)."""
    symbols = [t.upper() for t in tickers if t][:12]
    frames: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            hist = await mds.get_history(sym, period=period, interval="1d")
            if hist is not None and not hist.empty:
                frames[sym] = hist
        except Exception as exc:
            logger.debug("corr timeline skip %s: %s", sym, exc)

    panel, align_warnings = align_histories_local_date(frames)
    if panel.empty or len(panel) < window:
        return {
            "ok": False,
            "error": "insufficient_data",
            "warnings": align_warnings,
            "authority": "research_only",
            "descriptive_only": True,
        }

    dates: List[str] = []
    densities: List[Optional[float]] = []
    for end in range(window, len(panel) + 1, step):
        slice_panel = panel.iloc[end - window : end]
        ed = edge_density_from_panel(slice_panel)
        dates.append(str(slice_panel.index[-1].date()))
        densities.append(ed.get("edge_density"))

    regimes = hysteresis_timeline(densities)
    full = edge_density_from_panel(panel)
    return {
        "ok": True,
        "authority": "research_only",
        "descriptive_only": True,
        "not_a_signal": True,
        "tickers": symbols,
        "aligned_bars": len(panel),
        "window": window,
        "step": step,
        "hysteresis": {"enter_fused_at": _HYST_HIGH, "exit_fused_at": _HYST_LOW},
        "current": {
            "edge_density": full.get("edge_density"),
            "regime": regimes[-1] if regimes else "unknown",
            "as_of": dates[-1] if dates else None,
        },
        "timeline": [
            {"date": d, "edge_density": dens, "regime": reg}
            for d, dens, reg in zip(dates, densities, regimes)
        ],
        "warnings": align_warnings,
    }
