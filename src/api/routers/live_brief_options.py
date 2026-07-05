"""Live brief and synthetic options research endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.api.live_state import fetch_regime_state, mds_quote_for_app

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live"])


def _get_engine(request: Request):
    eng = getattr(request.app.state, "engine", None)
    if eng is not None:
        return eng
    try:
        from src.api.main import _get_engine as _ge

        return _ge()
    except Exception:
        return None


@router.get("/brief")
async def live_brief(request: Request):
    """Analyst-grade daily portfolio brief."""
    regime = await fetch_regime_state(request)
    engine = _get_engine(request)

    vol_map = {
        "low_vol": "LOW",
        "normal_vol": "NORMAL",
        "elevated_vol": "HIGH",
        "high_vol": "HIGH",
        "crisis_vol": "CRISIS",
    }
    trend_map = {"uptrend": "UPTREND", "downtrend": "DOWNTREND", "sideways": "SIDEWAYS"}
    vol_label = vol_map.get(regime.volatility_regime, "NORMAL")
    trend_label = trend_map.get(regime.trend_regime, "SIDEWAYS")

    recs = []
    if engine:
        recs = list(getattr(engine, "_cached_recommendations", []))[:10]

    actionable = [r for r in recs if hasattr(r, "score") and (r.score or 0) >= 6]
    watch = [r for r in recs if not hasattr(r, "score") or (r.score or 0) < 6]

    sector_data = []
    try:
        all_sectors = [
            ("XLK", "Technology"),
            ("XLF", "Financials"),
            ("XLV", "Healthcare"),
            ("XLE", "Energy"),
            ("XLI", "Industrials"),
            ("XLY", "Consumer Disc"),
            ("XLP", "Staples"),
            ("XLU", "Utilities"),
        ]
        fetched = await asyncio.gather(
            *[mds_quote_for_app(request.app, s) for s, _ in all_sectors]
        )
        for (sym, name), q in zip(all_sectors, fetched):
            sector_data.append(
                {
                    "name": name,
                    "symbol": sym,
                    "change_pct": round(q.get("change_pct", 0), 2),
                }
            )
        sector_data.sort(key=lambda x: x["change_pct"], reverse=True)
    except Exception:
        pass

    regime_narrative = (
        f"Market is in {regime.regime.replace('_', ' ')} regime with "
        f"{trend_label.lower()} trend and {vol_label.lower()} volatility."
    )
    if regime.no_trade_reason:
        regime_narrative += f" ⚠ {regime.no_trade_reason}"

    what_changed = []
    if vol_label in ("HIGH", "CRISIS"):
        what_changed.append("Volatility elevated — consider reducing position sizes")
    if trend_label == "DOWNTREND":
        what_changed.append("Trend has shifted bearish — long setups face headwind")
    if trend_label == "UPTREND":
        what_changed.append("Uptrend confirmed — momentum strategies favored")
    if not regime.should_trade:
        what_changed.append(f"Trading paused: {regime.no_trade_reason}")
    if sector_data:
        top = sector_data[0]
        bottom = sector_data[-1]
        what_changed.append(
            f"Sector rotation: {top['name']} leading ({top['change_pct']:+.2f}%), "
            f"{bottom['name']} lagging ({bottom['change_pct']:+.2f}%)"
        )

    def _rec_to_dict(r):
        if isinstance(r, dict):
            return r
        d = {}
        for k in (
            "ticker",
            "symbol",
            "score",
            "confidence",
            "direction",
            "strategy",
            "entry_price",
            "target_price",
            "stop_price",
        ):
            if hasattr(r, k):
                d[k] = getattr(r, k)
        return d

    dry_run = not engine or bool(getattr(engine, "dry_run", True))
    trust_mode = "PAPER" if dry_run else "LIVE"

    return sanitize_for_json(
        {
            "date": date.today().isoformat(),
            "regime": {
                "label": regime.regime,
                "trend": trend_label,
                "vol": vol_label,
                "should_trade": regime.should_trade,
                "no_trade_reason": regime.no_trade_reason,
                "narrative": regime_narrative,
            },
            "what_changed": what_changed,
            "actionable": [_rec_to_dict(r) for r in actionable],
            "watch": [_rec_to_dict(r) for r in watch],
            "no_trade_reason": regime.no_trade_reason,
            "sectors": sector_data,
            "follow_up": [
                "Which signals have the highest R:R today?",
                "What is the sector rotation telling us?",
                "Are there any earnings catalysts this week?",
                "Should I reduce position sizes given current volatility?",
            ],
            "trust": {
                "mode": trust_mode,
                "source": "engine_cache + market_data_service",
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
        }
    )


@router.get("/options/{ticker}")
async def live_options(ticker: str, request: Request):
    """Synthetic options research for a ticker (labeled SYNTHETIC)."""
    ticker = validate_ticker(ticker)
    mds = request.app.state.market_data

    q_raw = await mds.get_quote(ticker)
    if q_raw is None:
        raise HTTPException(404, f"No data for {ticker}")

    price = q_raw["price"]
    regime = await fetch_regime_state(request)

    base_iv = 0.25
    if regime.volatility_regime in ("elevated_vol", "high_vol"):
        base_iv = 0.40
    elif regime.volatility_regime == "crisis_vol":
        base_iv = 0.60
    elif regime.volatility_regime == "low_vol":
        base_iv = 0.18

    strikes = [
        round(price * 0.95, 0),
        round(price * 0.975, 0),
        round(price, 0),
        round(price * 1.025, 0),
        round(price * 1.05, 0),
    ]
    dtes = [30, 30, 45, 45, 60]
    types = ["CALL", "CALL", "CALL", "PUT", "PUT"]
    base_deltas = [0.65, 0.55, 0.50, -0.45, -0.35]
    _iv_offsets = [0.01, -0.02, 0.0, 0.03, -0.01]
    _base_ois = [2000, 5000, 10000, 4000, 3000]

    contracts = []
    for i, strike in enumerate(strikes):
        iv = round(base_iv + _iv_offsets[i], 3)
        oi = _base_ois[i]
        spread = "TIGHT" if iv < 0.35 else "WIDE"
        moneyness = (
            (price - strike) / price if types[i] == "CALL" else (strike - price) / price
        )
        ev = round(moneyness * 100 + (1 - i) * 0.5, 1)
        contracts.append(
            {
                "strike": int(strike),
                "dte": dtes[i],
                "type": types[i],
                "delta": base_deltas[i],
                "iv": iv,
                "oi": oi,
                "spread_quality": spread,
                "ev": ev,
                "break_even": round(
                    strike
                    + (price * iv * (dtes[i] / 365) ** 0.5)
                    * (1 if types[i] == "CALL" else -1),
                    2,
                ),
            }
        )

    iv_rank = min(80, max(20, int(base_iv * 200)))

    return sanitize_for_json(
        {
            "symbol": ticker,
            "price": round(price, 2),
            "contracts": contracts,
            "iv_rank": iv_rank,
            "iv_percentile": min(95, iv_rank + 5),
            "term_structure": (
                "Normal contango — front month IV < back month"
                if iv_rank < 50
                else "Backwardation — front month IV elevated (event risk?)"
            ),
            "skew_note": (
                "Moderate put skew — standard risk-off hedge demand"
                if regime.regime != "RISK_OFF"
                else "Steep put skew — fear elevated, hedging demand high"
            ),
            "regime_context": (
                f"{regime.regime.replace('_', ' ')} regime — "
                f"{'sell premium strategies favored' if iv_rank > 50 else 'directional strategies may offer better edge'}"
            ),
            "trust": {
                "mode": "SYNTHETIC",
                "source": "heuristic_model",
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
                "note": "Contracts are synthetic. Verify with broker before execution.",
            },
        }
    )
