"""Bench alpha IC across a ticker universe (Signal Board leaders)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.alpha_zoo_bench import bench_alphas_on_history, resolve_bench_alpha_ids
from src.services.research_safety import sanitize_research_payload


def _universe_tickers(limit: int = 12) -> List[str]:
    try:
        from src.services.signal_board import get_latest

        board = get_latest()
        out: List[str] = []
        for bucket in ("strong_buy", "buy", "watch"):
            for row in (board.get("buckets") or {}).get(bucket) or []:
                if isinstance(row, dict):
                    t = str(row.get("ticker") or "").upper()
                    if t and t not in out:
                        out.append(t)
        if out:
            return out[:limit]
    except Exception:
        pass
    return ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "BTC-USD"][:limit]


async def bench_alphas_universe(
    mds,
    *,
    tickers: Optional[List[str]] = None,
    period: str = "1y",
    limit: int = 15,
    per_ticker_alpha_limit: int = 12,
) -> Dict[str, Any]:
    symbols = [str(t).upper() for t in (tickers or _universe_tickers(limit))][:limit]
    alpha_ids = resolve_bench_alpha_ids(limit=per_ticker_alpha_limit)
    by_alpha: Dict[str, List[float]] = {aid: [] for aid in alpha_ids}
    ticker_rows: List[Dict[str, Any]] = []
    for sym in symbols:
        try:
            hist = await mds.get_history(sym, period=period, interval="1d")
        except Exception:
            continue
        if hist is None or getattr(hist, "empty", True):
            continue
        leg = bench_alphas_on_history(hist, alpha_ids=alpha_ids)
        ticker_rows.append(
            {
                "ticker": sym,
                "summary": leg.get("summary"),
                "top_alive": [
                    r["alpha_id"]
                    for r in leg.get("results") or []
                    if r.get("category") == "alive"
                ][:3],
            }
        )
        for r in leg.get("results") or []:
            ic = r.get("ic_spearman")
            if ic is not None:
                by_alpha.setdefault(r["alpha_id"], []).append(float(ic))
    aggregate: List[Dict[str, Any]] = []
    for aid, ics in by_alpha.items():
        if not ics:
            continue
        mean_ic = sum(ics) / len(ics)
        cat = "alive" if mean_ic >= 0.03 else "reversed" if mean_ic <= -0.03 else "dead"
        aggregate.append(
            {
                "alpha_id": aid,
                "mean_ic_spearman": round(mean_ic, 4),
                "category": cat,
                "universe_hits": len(ics),
            }
        )
    aggregate.sort(key=lambda x: abs(x["mean_ic_spearman"]), reverse=True)
    return sanitize_research_payload(
        {
            "ok": bool(ticker_rows),
            "universe": symbols,
            "ticker_results": ticker_rows,
            "aggregate_alphas": aggregate[:40],
            "authority": "research_only",
        }
    )
