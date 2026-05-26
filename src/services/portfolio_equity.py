"""Portfolio book equity curve and rolling alpha/beta vs benchmark."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from src.engines.benchmark_portfolio import BenchmarkPortfolioEngine, PositionSnapshot
from src.engines.correlation_risk import get_sector

logger = logging.getLogger(__name__)


def _col(hist, name: str):
    return name if name in hist.columns else name.lower()


async def build_portfolio_equity_series(
    request,
    positions: List[Dict[str, Any]],
    *,
    period: str = "6mo",
    benchmark: str = "SPY",
) -> Dict[str, Any]:
    """
    Daily portfolio equity from weighted holding prices (live marks).
    """
    if not positions:
        return {
            "has_series": False,
            "note": "No holdings — seed demo or add positions",
            "evidence": {"basis": "empty", "label": "—"},
        }

    mds = request.app.state.market_data
    total_mv = sum(float(p.get("market_value") or 0) for p in positions) or 1.0
    weights = {
        (p.get("ticker") or "").upper(): float(p.get("market_value") or 0) / total_mv
        for p in positions
        if p.get("ticker")
    }
    tickers = list(weights.keys())
    if not tickers:
        return {"has_series": False, "note": "Invalid holdings"}

    async def _hist(sym: str):
        try:
            return sym, await mds.get_history(sym, period=period, interval="1d")
        except Exception as exc:
            logger.debug("hist %s: %s", sym, exc)
            return sym, None

    bench_task = mds.get_history(benchmark, period=period, interval="1d")
    results = await asyncio.gather(bench_task, *[_hist(t) for t in tickers])
    bench_hist = results[0]
    ticker_hists = {sym: h for sym, h in results[1:] if h is not None and not h.empty}

    if bench_hist is None or bench_hist.empty:
        return {"has_series": False, "note": "Benchmark data unavailable"}

    b_col = _col(bench_hist, "Close")
    bench_close = bench_hist[b_col].dropna()
    index = bench_close.index

    port_rets: Dict[Any, float] = {d: 0.0 for d in index}
    used = 0
    for sym, w in weights.items():
        h = ticker_hists.get(sym)
        if h is None or h.empty:
            continue
        c_col = _col(h, "Close")
        s = h[c_col].reindex(index).ffill().bfill()
        if len(s) < 2:
            continue
        daily = s.pct_change().fillna(0.0)
        for d, r in daily.items():
            if d in port_rets:
                port_rets[d] += w * float(r)
        used += 1

    if used == 0:
        return {"has_series": False, "note": "Could not load holding histories"}

    dates = sorted(port_rets.keys())
    rets = [port_rets[d] for d in dates]
    bench_rets = bench_close.reindex(dates).pct_change().fillna(0.0).tolist()

    equity = [100.0]
    for r in rets[1:]:
        equity.append(equity[-1] * (1 + r))
    bench_equity = [100.0]
    for r in bench_rets[1:]:
        bench_equity.append(bench_equity[-1] * (1 + r))

    underwater = []
    peak = equity[0]
    for v in equity:
        peak = max(peak, v)
        underwater.append(round((v / peak - 1) * 100, 2))

    rolling = _rolling_alpha_beta(rets, bench_rets, window=20)

    engine = BenchmarkPortfolioEngine(benchmark=benchmark)
    snaps = []
    for p in positions:
        t = (p.get("ticker") or "").upper()
        w = weights.get(t, 0)
        snaps.append(
            PositionSnapshot(
                ticker=t,
                weight=w,
                return_pct=float(p.get("pnl_pct") or 0),
                sector=get_sector(t),
            )
        )
    period_bench_ret = (
        (bench_equity[-1] / bench_equity[0] - 1) * 100 if bench_equity else 0
    )
    brinson = engine.compute_attribution(
        snaps,
        benchmark_return=period_bench_ret,
        portfolio_returns_series=[x * 100 for x in rets],
        benchmark_returns_series=[x * 100 for x in bench_rets],
    )

    return {
        "has_series": True,
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "period": period,
        "benchmark": benchmark,
        "holdings_used": used,
        "dates": [str(d)[:10] for d in dates[-120:]],
        "equity_curve": [round(v, 2) for v in equity[-120:]],
        "benchmark_curve": [round(v, 2) for v in bench_equity[-120:]],
        "underwater_curve": underwater[-120:],
        "total_return_pct": round((equity[-1] / equity[0] - 1) * 100, 2),
        "benchmark_return_pct": round(period_bench_ret, 2),
        "active_return_pct": round(
            (equity[-1] / equity[0] - 1) * 100 - period_bench_ret, 2
        ),
        "rolling": rolling,
        "brinson": brinson.to_dict(),
        "evidence": {
            "basis": "live_daily_marks",
            "label": "Book equity from weighted daily returns — not audited NAV",
            "gross_net": "gross",
        },
    }


def _rolling_alpha_beta(
    port_rets: List[float],
    bench_rets: List[float],
    *,
    window: int = 20,
) -> Dict[str, Any]:
    if len(port_rets) < window + 5:
        return {
            "window": window,
            "alpha_20d": None,
            "beta_20d": None,
            "sharpe_20d": None,
            "note": "Need more days for rolling window",
        }
    p = np.array(port_rets[-window:])
    b = np.array(bench_rets[-window:])
    if np.std(b) == 0:
        beta = 1.0
    else:
        beta = float(np.cov(p, b)[0, 1] / np.var(b))
    alpha = float((np.mean(p) - beta * np.mean(b)) * 252 * 100)
    sharpe = 0.0
    if np.std(p) > 0:
        sharpe = float(np.mean(p) / np.std(p) * np.sqrt(252))
    return {
        "window": window,
        "alpha_20d_ann_pct": round(alpha, 2),
        "beta_20d": round(beta, 2),
        "sharpe_20d": round(sharpe, 2),
    }
