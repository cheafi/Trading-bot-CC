"""Marginal return on capital — research_only capital ladder hints."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_CASH_HURDLE_BPS = 450


def _load_portfolio_holdings() -> List[Dict[str, Any]]:
    try:
        from src.api.routers import portfolio as portfolio_router

        book = portfolio_router._user_portfolio
        if not isinstance(book, dict):
            book = portfolio_router._load_portfolio_from_disk()
        holdings = book.get("holdings") or []
        return [h for h in holdings if isinstance(h, dict)]
    except Exception as exc:
        logger.debug("marginal roc portfolio load skipped: %s", exc)
        return []


def _row_score(row: Dict[str, Any]) -> float:
    raw = row.get("marginal_return_on_capital")
    if raw is not None:
        try:
            return float(raw) * 10000.0 if abs(float(raw)) < 1 else float(raw)
        except (TypeError, ValueError):
            pass
    for key in ("score", "raw_score", "validated_score"):
        val = row.get(key)
        if val is None:
            continue
        try:
            score = float(val)
        except (TypeError, ValueError):
            continue
        return max(0.0, (score - 5.0) * 80.0)
    return 0.0


def build_marginal_roc_ladder(*, deploy_open: bool = False) -> Dict[str, Any]:
    """Live ladder from portfolio holdings + playbook top row — display only, not deploy gate."""
    from src.services.playbook_board_fallback import load_playbook_snapshot

    snap = load_playbook_snapshot() or {}
    rows = snap.get("top_ranked") or snap.get("rows") or []
    holdings = _load_portfolio_holdings()
    held_tickers = {
        str(h.get("ticker") or "").upper()
        for h in holdings
        if str(h.get("ticker") or "").strip()
    }

    ladder: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for idx, row in enumerate(rows[:5]):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        marginal_bps = round(_row_score(row), 0)
        ladder.append(
            {
                "rank": len(ladder) + 1,
                "ticker": ticker,
                "source": "playbook",
                "held": ticker in held_tickers,
                "marginal_return_on_capital_bps": marginal_bps,
                "vs_cash": "beats_cash" if marginal_bps >= _CASH_HURDLE_BPS else "below_cash",
                "authority": "research_only",
            }
        )

    for h in holdings[:5]:
        ticker = str(h.get("ticker") or "").upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        marginal_bps = round(_row_score(h), 0)
        ladder.append(
            {
                "rank": len(ladder) + 1,
                "ticker": ticker,
                "source": "portfolio",
                "held": True,
                "marginal_return_on_capital_bps": marginal_bps,
                "vs_cash": "beats_cash" if marginal_bps >= _CASH_HURDLE_BPS else "below_cash",
                "authority": "research_only",
            }
        )

    ladder.sort(key=lambda r: float(r.get("marginal_return_on_capital_bps") or 0), reverse=True)
    for i, entry in enumerate(ladder):
        entry["rank"] = i + 1

    best = ladder[0] if ladder else None
    best_beats_cash = bool(best and best.get("vs_cash") == "beats_cash")
    cash_winning = (not deploy_open) or not best_beats_cash

    if best and best_beats_cash:
        cash_headline = (
            f"Best: {best['ticker']} {best['marginal_return_on_capital_bps']}bps vs "
            f"cash { _CASH_HURDLE_BPS}bps · 邊際候選勝過現金"
        )
        next_hint = best["ticker"]
    else:
        cash_headline = f"Cash hurdle {_CASH_HURDLE_BPS}bps winning · 持現勝出"
        next_hint = "CASH"

    return {
        "status": "live" if ladder else "empty",
        "authority": "research_only",
        "headline": "Marginal ROC · 邊際資本回報 — portfolio + playbook ladder",
        "cash_hurdle_bps": _CASH_HURDLE_BPS,
        "cash_winning": cash_winning,
        "cash_headline": cash_headline,
        "holdings_count": len(holdings),
        "playbook_rows": len(rows),
        "ladder": ladder[:8],
        "best_candidate": best,
        "next_10k_hint": next_hint,
    }
