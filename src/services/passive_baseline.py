"""
Passive baseline comparison — SPY / QQQ / equal-weight stub for Dashboard humility strip.

Lightweight proxy: active edge must beat doing less before deploy is justified.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Static fallback when live quotes unavailable (20d approx, not for trading)
_STUB_RETURNS_20D: Dict[str, float] = {
    "SPY": 0.025,
    "QQQ": 0.032,
    "RSP": 0.022,  # equal-weight S&P proxy
}


def _pct_display(ret: float) -> str:
    return f"{ret * 100:+.1f}%"


def build_passive_baseline_strip(
    *,
    spy_return_20d: Optional[float] = None,
    qqq_return_20d: Optional[float] = None,
    rsp_return_20d: Optional[float] = None,
    active_edge_net: Optional[float] = None,
    deployable_count: int = 0,
    position_count: int = 0,
    local_only: bool = False,
) -> Dict[str, Any]:
    """
    Build dashboard passive comparison strip.

    active_edge_net: best net_deploy_score on board (0–10), if any.
    """
    insufficient_book = position_count <= 1 or (local_only and position_count < 3)
    spy = spy_return_20d if spy_return_20d is not None else _STUB_RETURNS_20D["SPY"]
    qqq = qqq_return_20d if qqq_return_20d is not None else _STUB_RETURNS_20D["QQQ"]
    rsp = rsp_return_20d if rsp_return_20d is not None else _STUB_RETURNS_20D["RSP"]
    eq_avg = round((spy + qqq + rsp) / 3, 4)

    beats_passive = False
    complexity_justified: Optional[bool] = None
    advantage_note = "No deploy-grade active edge on board — passive baseline is the honest comparator."
    if insufficient_book:
        advantage_note = (
            "Book too thin or local-only — cannot honestly claim active edge vs passive. "
            "Index or cash is the fair baseline until broker sync and depth improve."
        )
        complexity_justified = False
    elif active_edge_net is not None and deployable_count >= 1:
        # Map 0–10 net score to rough annualized edge proxy (heuristic only)
        implied_edge = (float(active_edge_net) - 5.0) * 0.004
        beats_passive = implied_edge > spy
        if beats_passive:
            advantage_note = (
                "Expected advantage over passive baseline — best board net score plausibly "
                "exceeds simple drift; still verify after costs and book fit."
            )
            complexity_justified = True
        else:
            advantage_note = (
                "Active setup may not beat SPY/QQQ passive drift after costs — "
                "cash or index is valid."
            )
            complexity_justified = False

    return {
        "benchmarks": {
            "SPY": {"return_20d": spy, "display": _pct_display(spy)},
            "QQQ": {"return_20d": qqq, "display": _pct_display(qqq)},
            "RSP": {"return_20d": rsp, "display": _pct_display(rsp)},
            "equal_weight_avg": {"return_20d": eq_avg, "display": _pct_display(eq_avg)},
        },
        "active_edge_net": active_edge_net,
        "deployable_count": deployable_count,
        "beats_passive_proxy": beats_passive,
        "complexity_justified": complexity_justified,
        "insufficient_data": insufficient_book,
        "position_count": position_count,
        "local_only": local_only,
        "headline": (
            f"20d: SPY {_pct_display(spy)} · QQQ {_pct_display(qqq)} · EW {_pct_display(rsp)}"
        ),
        "advantage_note": advantage_note,
        "expected_advantage_label": (
            "Insufficient data"
            if insufficient_book
            else ("Yes — heuristic" if beats_passive else "No — passive valid")
        ),
        "model_note": (
            "Local/thin book — passive comparison is humility only, not attribution."
            if insufficient_book
            else "Stub/heuristic — not a live track record; use for humility only."
        ),
        "data_source": "live" if spy_return_20d is not None else "stub",
    }


async def fetch_live_baseline_returns(window: int = 20) -> Dict[str, Optional[float]]:
    """Try market_data for SPY/QQQ/RSP 20d returns; fall back to None."""
    try:
        from src.services.market_data import MarketDataService  # noqa: PLC0415

        svc = MarketDataService()

        async def _ret(sym: str) -> Optional[float]:
            try:
                if sym == "SPY":
                    return await svc.get_spy_return(window)
                df = await svc.get_history(sym, period="3mo", interval="1d")
                if df is None or len(df) < window:
                    return None
                close = df["Close"]
                return round(float(close.iloc[-1]) / float(close.iloc[-window]) - 1, 4)
            except Exception:
                return None

        spy, qqq, rsp = await __import__("asyncio").gather(
            _ret("SPY"), _ret("QQQ"), _ret("RSP")
        )
        return {"SPY": spy, "QQQ": qqq, "RSP": rsp}
    except Exception:
        return {"SPY": None, "QQQ": None, "RSP": None}


async def build_passive_baseline_for_today(
    *,
    opportunities: Optional[list] = None,
    deployable_count: int = 0,
    position_count: int = 0,
    local_only: bool = False,
) -> Dict[str, Any]:
    """Async dashboard helper with optional live benchmark fetch."""
    opps = opportunities or []
    best_net = None
    for row in opps:
        net = row.get("net_deploy_score")
        if net is not None:
            best_net = max(best_net or 0, float(net))
    live = await fetch_live_baseline_returns()
    return build_passive_baseline_strip(
        spy_return_20d=live.get("SPY"),
        qqq_return_20d=live.get("QQQ"),
        rsp_return_20d=live.get("RSP"),
        active_edge_net=best_net,
        deployable_count=deployable_count,
        position_count=position_count,
        local_only=local_only,
    )
