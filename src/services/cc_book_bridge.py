"""
Book context bridge — live holdings and realized strategy health for CC OS.

Research/ops support only; never grants deploy authority.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def normalize_portfolio_positions(holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map portfolio holdings to portfolio-intel position rows."""
    out: List[Dict[str, Any]] = []
    for h in holdings or []:
        if not isinstance(h, dict):
            continue
        sym = str(h.get("ticker") or h.get("symbol") or "").upper().strip()
        if not sym:
            continue
        out.append(
            {
                "ticker": sym,
                "symbol": sym,
                "sector": h.get("sector") or h.get("sector_name") or "unknown",
                "weight_pct": h.get("weight_pct") or h.get("allocation_pct"),
            }
        )
    return out


def load_live_strategy_health(
    *,
    window_days: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Best-effort realized trade health from closed_trades ledger.

    Returns None when ledger empty — caller should keep research-only curve stub.
    """
    try:
        from src.services.strategy_health_service import load_per_strategy

        payload = load_per_strategy(window_days=window_days)
        strategies = list(payload.get("strategies") or [])
        if not strategies:
            return None
        best = strategies[0]
        if best.get("status") == "NO_DATA" or int(best.get("n_trades") or 0) < 1:
            return None
        return {
            "source": "closed_trades_ledger",
            "window_days": window_days,
            "best_strategy_id": best.get("strategy_id"),
            "sharpe_trade": best.get("sharpe_trade"),
            "sharpe_ann": best.get("sharpe_ann"),
            "sortino_ann": best.get("sortino_ann"),
            "max_dd_pct": best.get("max_dd_pct"),
            "win_rate": best.get("hit_rate"),
            "n_trades": best.get("n_trades"),
            "expectancy_r": best.get("expectancy_r") or best.get("mean_r"),
            "status": best.get("status"),
            "live_not_backtest": True,
            "may_authorize_deploy": False,
        }
    except Exception:
        return None


def resolve_curve_inputs_for_os(
    *,
    live_health: Optional[Dict[str, Any]] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Map live ledger health into curve governance kwargs."""
    if not live_health or degraded:
        return {"degraded": True}
    n = int(live_health.get("n_trades") or 0)
    sharpe = live_health.get("sharpe_trade") or live_health.get("sharpe_ann") or 0.0
    max_dd = abs(float(live_health.get("max_dd_pct") or 0))
    win_rate = float(live_health.get("win_rate") or 0)
    exp = float(live_health.get("expectancy_r") or 0)
    return {
        "sharpe_wf": float(sharpe),
        "max_dd_pct": max_dd if max_dd > 0 else 12.0,
        "win_rate": win_rate,
        "n_trades": n,
        "expectancy_r": exp,
        "live_sharpe": float(sharpe),
        "degraded": n < 10,
    }
