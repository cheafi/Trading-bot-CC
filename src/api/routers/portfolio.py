"""
CC — Portfolio & Operator Router
=================================
Extracted from main.py Sprint 56.
Handles portfolio import/holdings/futu/advise + operator console.
"""

import logging
from datetime import datetime, timezone
from typing import List

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Portfolio state ──────────────────────────────────────────────────
_user_portfolio: dict = {"holdings": [], "source": "manual", "updated_at": ""}


class HoldingInput(BaseModel):
    ticker: str
    shares: float = 0
    avg_cost: float = 0


class PortfolioImportRequest(BaseModel):
    holdings: List[HoldingInput]
    source: str = "manual"


# ── Operator state ───────────────────────────────────────────────────
_operator_state: dict = {
    "throttle": "NORMAL",
    "kill_switch": False,
    "reason": "initial",
    "set_at": datetime.now(timezone.utc).isoformat() + "Z",
}


# ══════════════════════════════════════════════════════════════════════
# Portfolio endpoints
# ══════════════════════════════════════════════════════════════════════


@router.post("/api/portfolio/import", tags=["portfolio"])
async def portfolio_import(req: PortfolioImportRequest, request: Request):
    """Batch-import portfolio holdings — multiple stocks at once."""
    global _user_portfolio
    now = datetime.now(timezone.utc).isoformat() + "Z"
    enriched = []
    mds = request.app.state.market_data
    for h in req.holdings:
        t = h.ticker.upper().strip()
        price = None
        try:
            hist = await mds.get_history(t, period="5d", interval="1d")
            if hist is not None and not hist.empty:
                c_col = "Close" if "Close" in hist.columns else "close"
                price = float(hist[c_col].iloc[-1])
        except Exception:
            pass
        enriched.append(
            {
                "ticker": t,
                "shares": h.shares,
                "avg_cost": h.avg_cost,
                "current_price": price,
                "market_value": round(price * h.shares, 2) if price else None,
                "unrealized_pnl": (
                    round((price - h.avg_cost) * h.shares, 2)
                    if price and h.avg_cost
                    else None
                ),
                "pnl_pct": (
                    round((price / h.avg_cost - 1) * 100, 2)
                    if price and h.avg_cost
                    else None
                ),
            }
        )
    _user_portfolio = {
        "holdings": enriched,
        "source": req.source,
        "updated_at": now,
        "count": len(enriched),
    }
    return _user_portfolio


@router.get("/api/portfolio/holdings", tags=["portfolio"])
async def portfolio_holdings():
    """Return the currently stored portfolio."""
    return _user_portfolio


@router.get("/api/portfolio/futu", tags=["portfolio"])
async def portfolio_from_futu():
    """Auto-fetch positions from Futu OpenD and store as portfolio."""
    global _user_portfolio
    try:
        from src.brokers.futu_broker import FutuBroker

        fb = FutuBroker()
        await fb.connect()
        positions = await fb.get_positions()
        account = await fb.get_account()
        await fb.disconnect()
        enriched = []
        for p in positions:
            enriched.append(
                {
                    "ticker": p.ticker,
                    "shares": p.quantity,
                    "avg_cost": p.avg_price,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pnl,
                    "pnl_pct": p.unrealized_pnl_pct,
                }
            )
        now = datetime.now(timezone.utc).isoformat() + "Z"
        _user_portfolio = {
            "holdings": enriched,
            "source": "futu",
            "updated_at": now,
            "count": len(enriched),
            "account": {
                "portfolio_value": account.portfolio_value,
                "cash": account.cash,
                "buying_power": account.buying_power,
            },
        }
        return _user_portfolio
    except Exception as exc:
        raise HTTPException(500, f"Futu fetch failed: {exc}") from exc


@router.post("/api/portfolio/advise", tags=["portfolio"])
async def portfolio_advise(request: Request):
    """Analyse imported portfolio — expert committee + conformal prediction."""
    holdings = _user_portfolio.get("holdings", [])
    if not holdings:
        raise HTTPException(
            400, "No portfolio imported. POST /api/portfolio/import first."
        )
    mds = request.app.state.market_data

    # Lazy imports to avoid circular deps
    from src.api.main import _compute_indicators
    from src.engines.conformal_predictor import ConformalPredictor
    from src.engines.expert_committee import ExpertCommittee

    advice_items = []
    total_value = 0
    total_pnl = 0
    for h in holdings:
        ticker = h["ticker"]
        mv = h.get("market_value") or 0
        total_value += mv
        total_pnl += h.get("unrealized_pnl") or 0
        verdict_str = "N/A"
        confidence = 0
        interval = None
        try:
            hist = await mds.get_history(ticker, period="6mo", interval="1d")
            if hist is not None and not hist.empty:
                c_col = "Close" if "Close" in hist.columns else "close"
                close = hist[c_col].values.astype(float)
                v_col = "Volume" if "Volume" in hist.columns else "volume"
                volume = (
                    hist[v_col].values.astype(float) if v_col in hist.columns else None
                )
                ec = ExpertCommittee()
                _ind = _compute_indicators(
                    close,
                    volume if volume is not None else np.ones(len(close)),
                )
                i = len(close) - 1
                trending = bool(
                    close[i] > _ind["sma50"][i] and _ind["sma50"][i] > _ind["sma200"][i]
                )
                rsi_val = float(_ind["rsi"][i])
                vol_r = float(_ind["vol_ratio"][i])
                atr_p = float(_ind["atr_pct"][i])
                votes = ec.collect_votes(
                    regime="UPTREND" if trending else "SIDEWAYS",
                    rsi=rsi_val,
                    vol_ratio=vol_r,
                    trending=trending,
                    rr_ratio=2.0,
                    atr_pct=atr_p,
                )
                v = ec.deliberate(votes, regime="UPTREND" if trending else "SIDEWAYS")
                verdict_str = v.direction
                confidence = v.agreement_ratio
                cp = ConformalPredictor(confidence_level=0.90)
                cp.calibrate_from_returns(close, horizon_days=20)
                interval = cp.predict(float(close[-1]) * 1.05)
        except Exception:
            pass

        pnl_pct = h.get("pnl_pct") or 0
        if verdict_str == "STRONG_BUY":
            action, reason = "ADD", "Expert committee strongly bullish"
        elif verdict_str == "BUY":
            action, reason = "HOLD / ADD on dip", "Committee bullish"
        elif verdict_str in ("SELL", "STRONG_SELL"):
            action, reason = "TRIM / EXIT", "Committee bearish"
        elif pnl_pct < -15:
            action, reason = "REVIEW", f"Down {pnl_pct:.1f}%"
        elif pnl_pct > 50:
            action, reason = "CONSIDER TRIM", f"Up {pnl_pct:.1f}%"
        else:
            action, reason = "HOLD", "Neutral signal"
        advice_items.append(
            {
                "ticker": ticker,
                "shares": h.get("shares"),
                "market_value": mv,
                "pnl_pct": pnl_pct,
                "committee_verdict": verdict_str,
                "committee_confidence": confidence,
                "action": action,
                "reason": reason,
                "prediction_interval": interval.to_dict() if interval else None,
            }
        )

    concentration_warnings = []
    if total_value > 0:
        for item in advice_items:
            w = (item["market_value"] / total_value) * 100
            item["portfolio_weight_pct"] = round(w, 1)
            if w > 25:
                concentration_warnings.append(
                    f"{item['ticker']} is {w:.0f}% — over-concentrated"
                )

    return {
        "portfolio_summary": {
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "holdings_count": len(holdings),
            "source": _user_portfolio.get("source"),
        },
        "advice": advice_items,
        "concentration_warnings": concentration_warnings,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ══════════════════════════════════════════════════════════════════════
# Operator Console endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/operator/status", tags=["operator"])
async def operator_status():
    """Get current operator console state."""
    return {
        "state": _operator_state,
        "throttle_options": [
            "NORMAL",
            "STARTER_ONLY",
            "HALF_SIZE",
            "HEDGE_ONLY",
            "NO_TRADE",
        ],
        "description": {
            "NORMAL": "All strategies active, full sizing",
            "STARTER_ONLY": "Only starter positions allowed (1/3 size)",
            "HALF_SIZE": "All strategies active but half position size",
            "HEDGE_ONLY": "Only hedging/defensive trades allowed",
            "NO_TRADE": "Kill switch — no new positions",
        },
    }


@router.post("/api/operator/throttle", tags=["operator"])
async def operator_set_throttle(
    throttle: str = Query(..., description="Throttle state"),
    reason: str = Query("manual", description="Reason for change"),
):
    """Set operator throttle state (kill switch / sizing control)."""
    valid = {"NORMAL", "STARTER_ONLY", "HALF_SIZE", "HEDGE_ONLY", "NO_TRADE"}
    if throttle not in valid:
        raise HTTPException(400, f"Invalid throttle: {throttle}. Valid: {valid}")
    _operator_state["throttle"] = throttle
    _operator_state["kill_switch"] = throttle == "NO_TRADE"
    _operator_state["reason"] = reason
    _operator_state["set_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    logger.info(f"[Operator] throttle → {throttle} (reason: {reason})")
    return {"status": "ok", "state": _operator_state}


@router.post("/api/operator/kill-switch", tags=["operator"])
async def operator_kill_switch(
    enabled: bool = Query(...),
    reason: str = Query("emergency", description="Reason"),
):
    """Emergency kill switch — stops all new trading."""
    _operator_state["kill_switch"] = enabled
    _operator_state["throttle"] = "NO_TRADE" if enabled else "NORMAL"
    _operator_state["reason"] = reason
    _operator_state["set_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    logger.warning(
        f"[Operator] KILL SWITCH {'ENGAGED' if enabled else 'RELEASED'}: {reason}"
    )
    return {"status": "ok", "kill_switch": enabled, "state": _operator_state}


# ══════════════════════════════════════════════════════════════════════
# Admin endpoints
# ══════════════════════════════════════════════════════════════════════


@router.post("/admin/trigger-job/{job_name}")
async def trigger_job(job_name: str):
    """Manually trigger a scheduled job."""
    return {
        "status": "triggered",
        "job": job_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/admin/jobs")
async def list_jobs():
    """List all scheduled jobs."""
    return {
        "jobs": [
            {"id": "overnight_news", "schedule": "6:00 AM ET"},
            {"id": "premarket_social", "schedule": "6:15 AM ET"},
            {"id": "daily_report", "schedule": "6:30 AM ET"},
            {"id": "premarket_signals", "schedule": "9:25 AM ET"},
            {"id": "intraday_data", "schedule": "Every 5 min during market hours"},
            {"id": "intraday_news", "schedule": "Every 15 min during market hours"},
            {"id": "eod_processing", "schedule": "4:30 PM ET"},
            {"id": "historical_backfill", "schedule": "8:00 PM ET"},
        ]
    }


# ══════════════════════════════════════════════════════════════════════
# Delta Scoreboard endpoint (wires existing engine)
# ══════════════════════════════════════════════════════════════════════

from src.engines.delta_scoreboard import DeltaTracker, ScoreboardBuilder

_delta_tracker = DeltaTracker()
_scoreboard_builder = ScoreboardBuilder()


@router.get("/api/v6/delta-scoreboard", tags=["intelligence"])
async def delta_scoreboard(request: Request):
    """Get market deltas + regime scoreboard.

    Computes what changed since yesterday and builds a regime-aware
    strategy playbook with scenario planning.
    """
    mds = request.app.state.market_data

    async def _fetch_index(ticker: str):
        try:
            hist = await mds.get_history(ticker, period="5d", interval="1d")
            if hist is not None and not hist.empty:
                c = "Close" if "Close" in hist.columns else "close"
                closes = hist[c].values.astype(float)
                return {
                    "close": float(closes[-1]),
                    "change_pct": (
                        float((closes[-1] / closes[-2] - 1) * 100)
                        if len(closes) >= 2
                        else 0.0
                    ),
                    "prev_close": float(closes[-2]) if len(closes) >= 2 else None,
                }
        except Exception:
            pass
        return {"close": 0.0, "change_pct": 0.0, "prev_close": None}

    # Fetch market data
    spx = await _fetch_index("SPY")
    ndx = await _fetch_index("QQQ")
    iwm = await _fetch_index("IWM")
    vix_data = await _fetch_index("^VIX")

    today_data = {
        "spx_close": spx["close"],
        "spx_change_pct": spx["change_pct"],
        "ndx_close": ndx["close"],
        "ndx_change_pct": ndx["change_pct"],
        "iwm_close": iwm["close"],
        "iwm_change_pct": iwm["change_pct"],
        "vix": vix_data["close"],
        "vix_change": vix_data["change_pct"],
    }

    yesterday_data = None
    if spx["prev_close"]:
        yesterday_data = {
            "spx_close": spx["prev_close"],
            "ndx_close": ndx.get("prev_close", 0),
            "iwm_close": iwm.get("prev_close", 0),
            "vix": vix_data.get("prev_close", 0),
        }

    # Compute deltas
    delta = _delta_tracker.compute(today_data, yesterday_data)
    material, noise = _delta_tracker.classify_changes(delta)

    # Derive MarketRegime from fetched data
    from src.core.models import (
        MarketRegime, VolatilityRegime, TrendRegime, RiskRegime,
    )
    vix_val = vix_data["close"]
    if vix_val > 30:
        vol_r = VolatilityRegime.CRISIS
    elif vix_val > 22:
        vol_r = VolatilityRegime.HIGH_VOL
    elif vix_val < 14:
        vol_r = VolatilityRegime.LOW_VOL
    else:
        vol_r = VolatilityRegime.NORMAL

    spx_chg = spx["change_pct"]
    if spx_chg > 1.0:
        trend_r = TrendRegime.STRONG_UPTREND
    elif spx_chg > 0.3:
        trend_r = TrendRegime.UPTREND
    elif spx_chg < -1.0:
        trend_r = TrendRegime.STRONG_DOWNTREND
    elif spx_chg < -0.3:
        trend_r = TrendRegime.DOWNTREND
    else:
        trend_r = TrendRegime.NEUTRAL

    if vix_val < 18 and spx_chg > 0:
        risk_r = RiskRegime.RISK_ON
    elif vix_val > 25 or spx_chg < -1:
        risk_r = RiskRegime.RISK_OFF
    else:
        risk_r = RiskRegime.NEUTRAL

    regime_obj = MarketRegime(
        timestamp=datetime.now(timezone.utc),
        volatility=vol_r,
        trend=trend_r,
        risk=risk_r,
        active_strategies=["swing", "momentum", "breakout"],
    )

    # Build scoreboard
    scoreboard = _scoreboard_builder.build(regime_obj, today_data, delta)
    scoreboard_text = _scoreboard_builder.format_scoreboard_text(scoreboard)

    return {
        "delta": delta.model_dump(mode="json"),
        "material_changes": [c.model_dump() for c in material],
        "noise": [c.model_dump() for c in noise],
        "scoreboard": scoreboard.model_dump(mode="json"),
        "scoreboard_text": scoreboard_text,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }
