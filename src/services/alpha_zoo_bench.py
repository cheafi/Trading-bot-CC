"""Alpha zoo bench — sample factor IC categorization (research subset)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from src.services.alpha_formulas import (
    canonical_formula_for_id,
    canonical_pack_stats,
    compute_canonical_factor,
)
from src.services.alpha_manifest import load_manifest, manifest_summary
from src.services.research_safety import sanitize_research_payload

# Subset catalog; full 478-alpha zoo is roadmap (Qlib/Kakushadze/GTJA packs).
ALPHA_CATALOG: Dict[str, str] = {
    "mom_20": "20-day momentum",
    "rev_5": "5-day reversal",
    "vol_z_20": "20-day volume z-score",
    "rsi_14": "RSI(14) level",
    "sma_spread_10_50": "SMA10 vs SMA50 spread",
    "high_low_range": "20-day range / close",
    "overnight_gap": "Open vs prior close gap",
    "dollar_vol_rank": "Dollar volume trend",
}


def _ic_series(factor: pd.Series, forward_ret: pd.Series) -> Optional[float]:
    aligned = pd.concat([factor, forward_ret], axis=1).dropna()
    if len(aligned) < 30:
        return None
    if aligned.iloc[:, 0].std(ddof=1) == 0:
        return None
    try:
        return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman"))
    except (ImportError, ValueError, TypeError):
        return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="pearson"))


def _categorize(ic: Optional[float]) -> str:
    if ic is None:
        return "unknown"
    if ic >= 0.03:
        return "alive"
    if ic <= -0.03:
        return "reversed"
    return "dead"


def _alpha_mom_20(close: pd.Series) -> pd.Series:
    return close.pct_change(20)


def _alpha_rev_5(close: pd.Series) -> pd.Series:
    return -close.pct_change(5)


def _alpha_vol_z_20(vol: pd.Series) -> pd.Series:
    m = vol.rolling(20).mean()
    s = vol.rolling(20).std(ddof=1)
    return (vol - m) / s


def _alpha_rsi_14(close: pd.Series) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _alpha_sma_spread(close: pd.Series) -> pd.Series:
    return close.rolling(10).mean() / close.rolling(50).mean() - 1


def _alpha_range(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    r = (high - low).rolling(20).mean()
    return r / close


def _alpha_gap(open_: pd.Series, close: pd.Series) -> pd.Series:
    return open_ / close.shift(1) - 1


def _alpha_dollar_vol(close: pd.Series, vol: pd.Series) -> pd.Series:
    dv = close * vol
    return dv.pct_change(10)


def load_alpha_pack_meta() -> Dict[str, Any]:
    path = Path("data/research/alpha_packs.json")
    if not path.exists():
        return {"total_alphas": len(ALPHA_CATALOG), "packs": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"total_alphas": 478, "packs": []}


def resolve_bench_alpha_ids(*, limit: int = 25) -> List[str]:
    """One-line IC bench across zoo sample (proxies for Qlib/Kakushadze/GTJA packs)."""
    limit = max(1, min(limit, 120))
    for w in range(3, 62, 2):
        aid = f"mom_{w}"
        if aid not in ALPHA_CATALOG:
            ALPHA_CATALOG[aid] = f"{w}-day momentum (zoo proxy)"
    for w in range(3, 22, 2):
        aid = f"rev_{w}"
        if aid not in ALPHA_CATALOG:
            ALPHA_CATALOG[aid] = f"{w}-day reversal (zoo proxy)"
    ordered = list(ALPHA_CATALOG.keys())
    return ordered[:limit]


def _compute_alpha(name: str, frame: pd.DataFrame) -> pd.Series:
    close = frame["close"]
    m = re.match(r"^mom_(\d+)$", name)
    if m:
        return _alpha_mom_20(close) if int(m.group(1)) == 20 else close.pct_change(int(m.group(1)))
    m = re.match(r"^rev_(\d+)$", name)
    if m:
        w = int(m.group(1))
        return -close.pct_change(w)
    open_ = frame.get("open", close)
    high = frame.get("high", close)
    low = frame.get("low", close)
    vol = frame.get("volume", pd.Series(1.0, index=close.index))
    fns: Dict[str, Callable[..., pd.Series]] = {
        "mom_20": lambda: _alpha_mom_20(close),
        "rev_5": lambda: _alpha_rev_5(close),
        "vol_z_20": lambda: _alpha_vol_z_20(vol),
        "rsi_14": lambda: _alpha_rsi_14(close),
        "sma_spread_10_50": lambda: _alpha_sma_spread(close),
        "high_low_range": lambda: _alpha_range(close, high, low),
        "overnight_gap": lambda: _alpha_gap(open_, close),
        "dollar_vol_rank": lambda: _alpha_dollar_vol(close, vol),
    }
    return fns[name]()


def bench_alphas_on_history(
    df: pd.DataFrame, *, alpha_ids: Optional[List[str]] = None, limit: int = 25
) -> Dict[str, Any]:
    frame = df.copy()
    rename = {"Close": "close", "Open": "open", "High": "high", "Low": "low", "Volume": "volume"}
    for a, b in rename.items():
        if a in frame.columns:
            frame[b] = frame[a]
    if "close" not in frame.columns:
        return {"ok": False, "error": "missing_close"}
    forward = frame["close"].pct_change().shift(-1)
    ids = alpha_ids or resolve_bench_alpha_ids(limit=limit)
    packs = load_alpha_pack_meta()
    results: List[Dict[str, Any]] = []
    for aid in ids:
        if aid not in ALPHA_CATALOG:
            continue
        try:
            factor = _compute_alpha(aid, frame)
            ic = _ic_series(factor, forward)
            cat = _categorize(ic)
        except Exception:
            ic = None
            cat = "unknown"
        results.append(
            {
                "alpha_id": aid,
                "label": ALPHA_CATALOG[aid],
                "ic_spearman": round(ic, 4) if ic is not None else None,
                "category": cat,
            }
        )
    alive = sum(1 for r in results if r["category"] == "alive")
    return sanitize_research_payload(
        {
            "ok": True,
            "catalog_size": packs.get("total_alphas") or len(ALPHA_CATALOG),
            "packs": packs.get("packs") or [],
            "computed_count": len(results),
            "catalog_note": (
                "Online bench uses proxy factor library; full 478 pack import is incremental."
            ),
            "pit_safe_fundamental": False,
            "results": results,
            "summary": {
                "alive": alive,
                "reversed": sum(1 for r in results if r["category"] == "reversed"),
                "dead": sum(1 for r in results if r["category"] == "dead"),
                "unknown": sum(1 for r in results if r["category"] == "unknown"),
            },
            "authority": "research_only",
        }
    )


def _factor_from_manifest(frame: pd.DataFrame, template: str, window: int) -> pd.Series:
    close = frame["close"]
    open_ = frame.get("open", close)
    high = frame.get("high", close)
    low = frame.get("low", close)
    vol = frame.get("volume", pd.Series(1.0, index=close.index))
    w = max(3, min(int(window or 10), 60))
    tmpl = str(template or "mom").lower()
    if tmpl == "mom":
        return close.pct_change(w)
    if tmpl == "rev":
        return -close.pct_change(w)
    if tmpl == "vol_z":
        return _alpha_vol_z_20(vol) if w == 20 else (vol - vol.rolling(w).mean()) / vol.rolling(w).std(ddof=1)
    if tmpl == "rsi":
        return _alpha_rsi_14(close)
    if tmpl == "sma_spread":
        return close.rolling(max(3, w // 2)).mean() / close.rolling(w).mean() - 1
    if tmpl == "range":
        return _alpha_range(close, high, low)
    if tmpl == "gap":
        return _alpha_gap(open_, close)
    return _alpha_dollar_vol(close, vol)


def bench_manifest_on_history(
    df: pd.DataFrame, *, compute_limit: int = 60, manifest_limit: int = 478
) -> Dict[str, Any]:
    manifest = load_manifest(limit=manifest_limit)
    rows = manifest.get("alphas") or []
    compute_limit = max(1, min(compute_limit, 478))
    rows = rows[:compute_limit]
    frame = df.copy()
    rename = {"Close": "close", "Open": "open", "High": "high", "Low": "low", "Volume": "volume"}
    for a, b in rename.items():
        if a in frame.columns:
            frame[b] = frame[a]
    if "close" not in frame.columns:
        return {"ok": False, "error": "missing_close"}
    forward = frame["close"].pct_change().shift(-1)
    results: List[Dict[str, Any]] = []
    canon = canonical_pack_stats()
    for row in rows:
        aid = str(row.get("id") or "")
        formula = row.get("formula") or canonical_formula_for_id(aid)
        window = int(row.get("window") or 10)
        canonical = bool(formula)
        try:
            if formula:
                factor = compute_canonical_factor(frame, str(formula), window)
            else:
                factor = _factor_from_manifest(
                    frame, str(row.get("template")), window
                )
            ic = _ic_series(factor, forward)
            cat = _categorize(ic)
        except Exception:
            ic = None
            cat = "unknown"
        results.append(
            {
                "alpha_id": row.get("id"),
                "pack": row.get("pack"),
                "label": row.get("label"),
                "formula": formula if formula else None,
                "canonical": canonical,
                "ic_spearman": round(ic, 4) if ic is not None else None,
                "category": cat,
                "pit_safe_fundamental": bool(row.get("pit_safe_fundamental")),
            }
        )
    summary = {
        "alive": sum(1 for r in results if r["category"] == "alive"),
        "reversed": sum(1 for r in results if r["category"] == "reversed"),
        "dead": sum(1 for r in results if r["category"] == "dead"),
        "unknown": sum(1 for r in results if r["category"] == "unknown"),
    }
    meta = manifest_summary()
    return sanitize_research_payload(
        {
            "ok": True,
            "zoo_total": meta.get("total_alphas") or 478,
            "computed_count": len(results),
            "compute_limit": compute_limit,
            "manifest_note": "478 manifest IDs; nightly cache runs full zoo IC when compute_limit=478.",
            "canonical_pack": canon,
            "summary": summary,
            "top_alive": [r for r in results if r["category"] == "alive"][:10],
            "results": results,
            "authority": "research_only",
        }
    )


async def bench_alphas_zoo(
    mds, ticker: str, *, period: str = "2y", compute_limit: int = 60
) -> Dict[str, Any]:
    hist = await mds.get_history(ticker, period=period, interval="1d")
    if hist is None or getattr(hist, "empty", True):
        return {"ok": False, "error": "no_history", "ticker": ticker}
    out = bench_manifest_on_history(hist, compute_limit=compute_limit)
    out["ticker"] = ticker
    return out


async def bench_alphas_for_ticker(
    mds, ticker: str, *, period: str = "2y", limit: int = 25
) -> Dict[str, Any]:
    hist = await mds.get_history(ticker, period=period, interval="1d")
    if hist is None or getattr(hist, "empty", True):
        return {"ok": False, "error": "no_history", "ticker": ticker}
    out = bench_alphas_on_history(hist, limit=limit)
    out["ticker"] = ticker
    return out
