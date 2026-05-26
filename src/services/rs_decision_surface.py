"""Institutional RS decision surface — live leaders, buyability, freshness."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.stock_universe import RS_SECTOR_SHORT, RS_UNIVERSE, rs_sector_for

logger = logging.getLogger(__name__)

_INDEX_TICKERS = frozenset({"SPY", "QQQ", "IWM"})
_METHODOLOGY = (
    "Composite RS = 10%×1W + 25%×1M + 35%×3M + 30%×6M vs SPY "
    "(ratio of cumulative returns × 100; 100 = match SPY). "
    "Percentile = rank within live universe. "
    "Buyability uses RS state, acceleration, extension, and regime gate."
)

_SECTOR_FILTER_ALIASES = {
    "TECH": "Technology",
    "CONSUMER": "Consumer Discretionary",
    "ENERGY": "Energy",
    "HEALTH": "Healthcare",
    "FINANCE": "Financials",
}


def _period_return_pct(closes, days: int) -> Optional[float]:
    if closes is None or len(closes) < days + 1:
        return None
    try:
        a = float(closes.iloc[-1])
        b = float(closes.iloc[-days - 1])
        if b <= 0:
            return None
        return round((a / b - 1) * 100, 2)
    except Exception:
        return None


async def build_rs_universe_daily() -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Daily-aligned universe + SPY benchmark returns."""
    from src.services.rs_data_service import fetch_closes_batch

    tickers = [t for t in RS_UNIVERSE if t not in _INDEX_TICKERS]
    loop = asyncio.get_event_loop()
    closes_map = await loop.run_in_executor(
        None, lambda: fetch_closes_batch(tickers + ["SPY"], period="6mo", interval="1d")
    )
    spy = closes_map.get("SPY")
    bench: Dict[str, float] = {}
    if spy is not None and len(spy) >= 22:
        bench = {
            "return_1w": _period_return_pct(spy, 5) or 0.0,
            "return_1m": _period_return_pct(spy, 21) or 0.0,
            "return_3m": _period_return_pct(spy, 63) or 0.0,
            "return_6m": _period_return_pct(spy, 126) or _period_return_pct(spy, len(spy) - 1) or 0.0,
        }
        if len(spy) >= 11:
            bench["prev_rs_1w"] = 100.0  # placeholder for change calc via stock fields

    universe: List[Dict[str, Any]] = []
    for t in tickers:
        s = closes_map.get(t)
        if s is None or len(s) < 22:
            continue
        r1w = _period_return_pct(s, 5)
        r1m = _period_return_pct(s, 21)
        r3m = _period_return_pct(s, 63)
        r6m = _period_return_pct(s, 126) or _period_return_pct(s, len(s) - 1)
        if r1m is None:
            continue
        sector = rs_sector_for(t)
        prev_1w = _period_return_pct(s, 10) if len(s) >= 11 else r1w
        prev_1m = _period_return_pct(s, 42) if len(s) >= 43 else r1m
        universe.append(
            {
                "ticker": t,
                "sector": sector,
                "sector_short": RS_SECTOR_SHORT.get(sector, sector[:12]),
                "market_cap": "LARGE",
                "price": round(float(s.iloc[-1]), 2),
                "change_pct": round(
                    (float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2
                )
                if len(s) >= 2
                else 0.0,
                "return_1w": r1w or 0.0,
                "return_1m": r1m,
                "return_3m": r3m or r1m,
                "return_6m": r6m or r3m or r1m,
                "prev_return_1w": prev_1w or r1w or 0.0,
                "prev_return_1m": prev_1m or r1m,
            }
        )

    meta = {
        "universe_size": len(universe),
        "benchmark": "SPY",
        "interval": "1d",
        "period": "6mo",
        "data_source": "yfinance_batch",
    }
    return universe, {**bench, **meta}


def _bench_rs(stock_ret: float, bench_ret: float) -> float:
    if bench_ret == 0:
        return max(0, min(300, (1 + stock_ret / 100) * 100))
    bf = 1 + bench_ret / 100
    if bf <= 0:
        return 100.0
    return max(0, min(300, (1 + stock_ret / 100) / bf * 100))


def _buyability(row: Dict[str, Any], regime_tradeability: str) -> Dict[str, Any]:
    """Breakout / Pullback / Extended / Failing + actionable gate."""
    comp = float(row.get("rs_composite") or 100)
    chg_w = float(row.get("rs_change_1w") or 0)
    chg_m = float(row.get("rs_change_1m") or 0)
    pct = int(row.get("rs_percentile") or 0)
    trend = str(row.get("trend") or "STEADY")

    if trend in ("BREAKING_DOWN",) or chg_m < -6:
        state = "FAILING"
    elif comp > 128 and chg_m > 6:
        state = "EXTENDED"
    elif trend == "BREAKING_OUT" or (chg_w > 4 and pct >= 70):
        state = "BREAKOUT"
    elif comp >= 108 and chg_w < -1 and float(row.get("rs_3m") or 0) >= 105:
        state = "PULLBACK"
    elif comp >= 112 and chg_w >= 0:
        state = "BREAKOUT"
    else:
        state = "WATCH"

    price = float(row.get("price") or 0)
    stop_pct = 0.05 if state != "EXTENDED" else 0.03
    stop = round(price * (1 - stop_pct), 2) if price else None
    entry_lo = round(price * 0.985, 2) if state == "PULLBACK" and price else price
    entry_hi = round(price * 1.01, 2) if price else None
    target = round(price * 1.08, 2) if price else None
    risk = (price - stop) if price and stop and price > stop else None
    reward = (target - price) if target and price else None
    rr = round(reward / risk, 1) if risk and reward and risk > 0 else None

    regime_ok = regime_tradeability in ("TRADE", "STRONG_TRADE", "SELECTIVE")
    actionable = (
        state in ("BREAKOUT", "PULLBACK")
        and pct >= 75
        and comp >= 108
        and regime_ok
        and not row.get("stale")
    )
    if state == "EXTENDED":
        actionable = False
        action_label = "AVOID_CHASE"
    elif state == "FAILING":
        actionable = False
        action_label = "NOT_ACTIONABLE"
    elif actionable:
        action_label = "BUYABLE_NOW"
    elif state == "PULLBACK":
        action_label = "WATCH_PULLBACK"
    else:
        action_label = "WATCH"

    return {
        "buyability": state,
        "action_label": action_label,
        "actionable": actionable,
        "entry_zone": (
            {"low": entry_lo, "high": entry_hi} if entry_lo and entry_hi else None
        ),
        "stop": stop,
        "target": target,
        "risk_reward": rr,
        "invalidation": f"Close below {stop}" if stop else "RS breaks below 100 vs SPY",
    }


def _enrich_row(raw: Dict[str, Any], regime_tradeability: str) -> Dict[str, Any]:
    row = dict(raw)
    row["stale"] = False
    row["actionable"] = False
    row["data_freshness"] = "LIVE"
    buy = _buyability(row, regime_tradeability)
    row.update(buy)
    row["rs_acceleration"] = round(
        float(row.get("rs_change_1w") or 0) - float(row.get("rs_change_1m") or 0) / 4,
        2,
    )
    row["alignment"] = {
        "1w_1m_3m": (
            "aligned"
            if float(row.get("rs_1m", 0)) >= 105
            and float(row.get("rs_3m", 0)) >= 100
            and float(row.get("rs_1w", 0)) >= 100
            else "mixed"
        ),
        "vs_spy": "outperform" if float(row.get("rs_composite", 0)) >= 105 else "inline",
    }
    row["why_leader"] = _why_leader(row)
    return row


def _why_leader(row: Dict[str, Any]) -> str:
    parts = []
    if float(row.get("rs_composite", 0)) >= 115:
        parts.append(f"composite {row['rs_composite']:.0f} vs SPY")
    if float(row.get("rs_change_1w", 0)) > 3:
        parts.append(f"RS accelerating +{row['rs_change_1w']:.0f}pt 1W")
    if int(row.get("rs_percentile", 0)) >= 85:
        parts.append(f"top {100 - row['rs_percentile']}% of universe")
    if row.get("trend") == "BREAKING_OUT":
        parts.append("new RS breakout")
    return " · ".join(parts) if parts else "Ranked by composite RS vs SPY"


async def build_rs_decision_surface(
    request,
    *,
    limit: int = 30,
    sector: Optional[str] = None,
    wait_live_sec: float = 55.0,
) -> Dict[str, Any]:
    """Full PM RS payload with live compute and separated stale bucket."""
    t0 = time.time()
    regime = {}
    tradeability = "WAIT"
    try:
        today = getattr(request.app.state, "today_v7_cache", None) or {}
        regime = today.get("market_regime") or {}
        tradeability = str(regime.get("tradeability") or "WAIT")
    except Exception:
        pass

    sector_norm = _SECTOR_FILTER_ALIASES.get((sector or "").upper(), sector)

    live_rows: List[Dict[str, Any]] = []
    sector_rs: List[Dict[str, Any]] = []
    error_note = ""
    try:
        from src.engines.rs_ranking import RSRankingEngine

        universe, bench = await asyncio.wait_for(
            build_rs_universe_daily(), timeout=wait_live_sec * 0.85
        )
        if not universe:
            raise ValueError("empty universe")

        engine = RSRankingEngine()
        for u in universe:
            u["prev_rs_1w"] = _bench_rs(
                u.get("prev_return_1w", 0), bench.get("return_1w", 0)
            )
            u["prev_rs_1m"] = _bench_rs(
                u.get("prev_return_1m", 0), bench.get("return_1m", 0)
            )

        entries = engine.rank(universe, bench)
        if sector_norm:
            entries = [
                e
                for e in entries
                if (e.sector or "").upper() == sector_norm.upper()
                or RS_SECTOR_SHORT.get(e.sector, "").upper() == (sector or "").upper()
            ]

        sector_rs = []
        for s in engine.get_sector_rankings(entries):
            sd = s.to_dict()
            sd["sector_short"] = RS_SECTOR_SHORT.get(s.sector, s.sector[:12])
            sector_rs.append(sd)
        for e in entries[:limit]:
            d = e.to_dict()
            d["sector_short"] = RS_SECTOR_SHORT.get(e.sector, e.sector[:12])
            live_rows.append(_enrich_row(d, tradeability))
    except Exception as exc:
        error_note = str(exc)[:120]
        logger.warning("RS decision live compute failed: %s", exc)

    stale_rows: List[Dict[str, Any]] = []
    if not live_rows:
        from src.api.routers.playbook import _brief_rs_ranking_fallback

        fb = _brief_rs_ranking_fallback(limit, sector_norm, None)
        for r in fb.get("rankings") or []:
            sr = dict(r)
            sr["stale"] = True
            sr["actionable"] = False
            sr["data_freshness"] = "STALE"
            sr["action_label"] = "NOT_ACTIONABLE"
            sr["buyability"] = "STALE"
            sr["why_leader"] = "Cached brief watchlist — not live RS"
            stale_rows.append(sr)

    actionable = [r for r in live_rows if r.get("actionable")][:3]
    false_leaders = [
        r
        for r in live_rows
        if r.get("status") in ("LEADER", "STRONG")
        and not r.get("actionable")
        and r.get("buyability") in ("EXTENDED", "FAILING", "WATCH")
    ][:3]
    pullback_candidates = [
        r for r in live_rows if r.get("buyability") == "PULLBACK"
    ][:3]
    crowded = sorted(
        [r for r in live_rows if r.get("buyability") == "EXTENDED"],
        key=lambda x: float(x.get("rs_composite") or 0),
        reverse=True,
    )[:3]

    elapsed_ms = int((time.time() - t0) * 1000)
    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "compute_ms": elapsed_ms,
        "freshness": {
            "live": bool(live_rows),
            "stale_reason": error_note or (None if live_rows else "live_compute_failed"),
            "universe_size": len(live_rows) or len(stale_rows),
            "benchmark": "SPY",
            "interval": "1d",
            "methodology": _METHODOLOGY,
        },
        "regime": {
            "tradeability": tradeability,
            "trend": regime.get("trend"),
            "vix": regime.get("vix"),
            "breadth": regime.get("breadth"),
            "stance": (
                "Deploy selective"
                if tradeability in ("TRADE", "STRONG_TRADE", "SELECTIVE")
                else "Stand down — regime WAIT/NO_TRADE"
            ),
        },
        "actionable_top3": actionable,
        "false_leaders_top3": false_leaders,
        "pullback_candidates": pullback_candidates,
        "crowded_chase_risk": crowded,
        "sector_rotation": sector_rs[:8],
        "live_leaders": live_rows,
        "stale_watchlist": stale_rows,
        "emerging": [
            r for r in live_rows if r.get("trend") == "BREAKING_OUT"
        ][:8],
        "failed": [r for r in live_rows if r.get("buyability") == "FAILING"][:8],
        "count_live": len(live_rows),
        "count_stale": len(stale_rows),
        "warning": (
            None
            if live_rows
            else "Live RS unavailable — stale names are NOT actionable"
        ),
    }
