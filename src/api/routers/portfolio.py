"""
CC — Portfolio & Operator Router
=================================
Extracted from main.py Sprint 56.
Handles portfolio import/holdings/futu/advise + operator console.
"""

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import List

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from src.services.ibkr_service import get_ibkr_service
from src.services.portfolio_positions import (
    build_position_record,
    portfolio_header_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Portfolio state ──────────────────────────────────────────────────
_user_portfolio: dict = {"holdings": [], "source": "manual", "updated_at": ""}


def positions_label(count: int) -> str:
    """Human count label: 0 → No positions, 1 → 1 position, else N positions."""
    n = int(count or 0)
    if n <= 0:
        return "No positions"
    if n == 1:
        return "1 position"
    return f"{n} positions"


def portfolio_header_snapshot_for_cc(*, ibkr_connected: bool = False) -> dict:
    """Book snapshot with live position count for cc-header."""
    holdings = _user_portfolio.get("holdings") or []
    source = str(_user_portfolio.get("source") or "manual")
    count = len(holdings)
    manual = source in ("manual", "demo-seed", "") or not ibkr_connected
    base = portfolio_header_snapshot(ibkr_connected=ibkr_connected and not manual)
    base["position_count"] = count
    base["positions_label"] = positions_label(count)
    base["book_label"] = "Manual book" if manual else source.upper()
    base["source"] = source
    return base


class HoldingInput(BaseModel):
    ticker: str
    shares: float = 0
    avg_cost: float = 0


class PositionAddRequest(BaseModel):
    """Add a single position (from BUY confirmation flow)."""

    ticker: str
    shares: float = 0
    entry_price: float = 0
    stop_price: float = 0
    target_1r: float = 0
    target_2r: float = 0
    notes: str = ""
    sleeve: str = ""
    sector: str = ""


class PositionUpdateRequest(BaseModel):
    """Update an existing position."""

    ticker: str
    shares: float | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_1r: float | None = None
    target_2r: float | None = None
    notes: str | None = None


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
                "stop_price": float(h.stop_price or 0),
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


@router.post("/api/portfolio/seed-demo", tags=["portfolio"])
async def portfolio_seed_demo(request: Request):
    """Seed a diversified demo portfolio for instant HISTSIM / portfolio console demo.

    Idempotent — overwrites any existing holdings. Pulls live prices via
    market_data so cost basis is realistic.
    """
    global _user_portfolio
    now = datetime.now(timezone.utc).isoformat() + "Z"
    mds = request.app.state.market_data
    from src.core.stock_universe import DEMO_PORTFOLIO_POSITIONS

    demo = DEMO_PORTFOLIO_POSITIONS
    enriched = []
    for d in demo:
        t = d["ticker"]
        price = None
        try:
            hist = await mds.get_history(t, period="5d", interval="1d")
            if hist is not None and not hist.empty:
                c_col = "Close" if "Close" in hist.columns else "close"
                price = float(hist[c_col].iloc[-1])
        except Exception:
            pass
        avg_cost = round((price or 100) * 0.95, 2)  # pretend bought 5% lower
        entry = avg_cost
        stop = round(entry * 0.95, 2) if entry else 0.0
        risk = entry - stop if entry and stop else entry * 0.05
        enriched.append(
            {
                "ticker": t,
                "shares": d["shares"],
                "entry_price": entry,
                "avg_cost": avg_cost,
                "stop_price": stop,
                "target_1r": round(entry + risk, 2) if entry and stop else 0.0,
                "target_2r": round(entry + 2 * risk, 2) if entry and stop else 0.0,
                "current_price": price,
                "market_value": (price * d["shares"]) if price else None,
                "unrealized_pnl": (
                    round((price - avg_cost) * d["shares"], 2)
                    if price and avg_cost
                    else None
                ),
                "pnl_pct": (
                    round((price / avg_cost - 1) * 100, 2)
                    if price and avg_cost
                    else None
                ),
            }
        )
    _user_portfolio = {
        "holdings": enriched,
        "source": "demo-seed",
        "updated_at": now,
        "count": len(enriched),
    }
    return {
        "ok": True,
        "seeded": len(enriched),
        "holdings": enriched,
        "next": "Open Portfolio tab; VaR pill should flip to HISTSIM in 5min refresh window.",
    }


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
        # FUTU OpenD not running / not installed — degrade honestly, do not 500.
        return {
            "holdings": _user_portfolio.get("holdings", []),
            "source": _user_portfolio.get("source", "manual"),
            "futu_connected": False,
            "degraded": True,
            "error": f"Futu unavailable: {exc}",
        }


_ALLOWED_CAPTURE_MIME = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/webp"}
)
_MAX_CAPTURE_BYTES = int(os.getenv("FUTU_CAPTURE_MAX_BYTES", str(10 * 1024 * 1024)))


async def _enrich_futu_holdings(holdings: list, mds) -> list:
    """Attach live prices to parsed Futu holdings."""
    enriched = []
    for h in holdings:
        t = h["ticker"]
        price = h.get("current_price")
        try:
            if price is None:
                hist = await mds.get_history(t, period="5d", interval="1d")
                if hist is not None and not hist.empty:
                    c_col = "Close" if "Close" in hist.columns else "close"
                    price = float(hist[c_col].iloc[-1])
        except Exception:
            pass
        shares = float(h.get("shares") or 0)
        avg_cost = float(h.get("avg_cost") or 0)
        mv = h.get("market_value")
        if mv is None and price and shares:
            mv = round(price * shares, 2)
        pnl = h.get("unrealized_pnl")
        if pnl is None and price and avg_cost and shares:
            pnl = round((price - avg_cost) * shares, 2)
        pnl_pct = h.get("pnl_pct")
        if pnl_pct is None and price and avg_cost:
            pnl_pct = round((price / avg_cost - 1) * 100, 2)
        enriched.append(
            {
                "ticker": t,
                "shares": shares,
                "avg_cost": avg_cost,
                "entry_price": avg_cost,
                "current_price": price,
                "market_value": mv,
                "unrealized_pnl": pnl,
                "pnl_pct": pnl_pct,
            }
        )
    return enriched


@router.post("/api/v7/portfolio/futu-capture", tags=["portfolio", "v7"])
async def futu_portfolio_capture(
    request: Request,
    file: UploadFile = File(...),
    notify_discord: bool = Form(True),
    ocr_text: str = Form(""),
):
    """Upload Futu portfolio screenshot → parse holdings → AI advisory → optional Discord.

    ADVISORY ONLY — never auto-trades or deploys.
    """
    global _user_portfolio

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_CAPTURE_MIME:
        raise HTTPException(
            400,
            f"Unsupported file type: {content_type or 'unknown'}. Use PNG/JPEG/WebP.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")
    if len(raw) > _MAX_CAPTURE_BYTES:
        raise HTTPException(
            400, f"File too large (max {_MAX_CAPTURE_BYTES // (1024 * 1024)}MB)"
        )

    tmp_path = None
    parse_method = "unknown"
    holdings_raw: list = []

    try:
        from src.services.futu_portfolio_advisor import build_futu_advisory
        from src.services.futu_portfolio_parser import (
            parse_futu_image_vision,
            parse_futu_text,
        )

        if ocr_text.strip():
            parsed, parse_method = parse_futu_text(ocr_text)
            holdings_raw = [h.to_dict() for h in parsed]

        if not holdings_raw:
            suffix = ".png" if "png" in content_type else ".jpg"
            fd, tmp_path = tempfile.mkstemp(prefix="futu_cap_", suffix=suffix)
            os.close(fd)
            with open(tmp_path, "wb") as fh:
                fh.write(raw)
            parsed, parse_method, _ = await parse_futu_image_vision(raw, content_type)
            holdings_raw = [h.to_dict() for h in parsed]

        if not holdings_raw:
            raise HTTPException(
                422,
                "Could not extract holdings. Try a clearer screenshot or pass ocr_text.",
            )

        mds = request.app.state.market_data
        enriched = await _enrich_futu_holdings(holdings_raw, mds)
        now = datetime.now(timezone.utc).isoformat() + "Z"
        _user_portfolio = {
            "holdings": enriched,
            "source": "futu-capture",
            "updated_at": now,
            "count": len(enriched),
        }

        regime = {}
        try:
            regime = getattr(request.app.state, "regime", None) or {}
        except Exception:
            pass

        advisory = await build_futu_advisory(
            enriched, market_data=mds, regime=regime if isinstance(regime, dict) else {}
        )

        pushed = False
        if notify_discord:
            from src.services.futu_capture_notify import notify_futu_capture_discord

            pushed = await notify_futu_capture_discord(
                holdings=enriched,
                advisory=advisory,
                parse_method=parse_method,
            )

        return {
            "ok": True,
            "advisory_only": True,
            "parse_method": parse_method,
            "holdings": enriched,
            "count": len(enriched),
            "advisory": advisory,
            "pushed_to_discord": pushed,
            "source": "futu-capture",
            "updated_at": now,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Position management (add/update/remove/monitor) ──────────────────


@router.post("/api/portfolio/position", tags=["portfolio"])
async def add_position(req: PositionAddRequest, request: Request):
    """Add a single position (e.g., from BUY confirmation flow)."""
    global _user_portfolio
    t = req.ticker.upper().strip()
    if not t:
        raise HTTPException(400, "Ticker is required")
    if req.shares <= 0:
        raise HTTPException(400, "Shares must be greater than 0")
    if req.entry_price <= 0:
        raise HTTPException(400, "Entry price must be greater than 0")

    now = datetime.now(timezone.utc).isoformat() + "Z"

    price = None
    try:
        mds = request.app.state.market_data
        hist = await mds.get_history(t, period="5d", interval="1d")
        if hist is not None and not hist.empty:
            c_col = "Close" if "Close" in hist.columns else "close"
            price = float(hist[c_col].iloc[-1])
    except Exception:
        pass

    pos = build_position_record(req, price=price, now=now)

    holdings = _user_portfolio.get("holdings", [])
    holdings = [h for h in holdings if h.get("ticker") != t]
    holdings.append(pos)
    _user_portfolio = {
        "holdings": holdings,
        "source": _user_portfolio.get("source", "manual"),
        "updated_at": now,
        "count": len(holdings),
    }

    broker_sync = "skipped"
    broker_message = ""
    try:
        ibkr = get_ibkr_service()
        ibkr_st = ibkr.status() if ibkr else {}
        ibkr_ok = bool(ibkr_st.get("session_usable") or ibkr_st.get("connected"))
        if ibkr_ok:
            broker_sync = "unavailable"
            broker_message = (
                "Saved locally · broker push not configured for manual adds"
            )
        else:
            broker_sync = "unavailable"
            broker_message = "Saved locally · Broker sync unavailable"
    except Exception:
        broker_sync = "unavailable"
        broker_message = "Saved locally · Broker sync unavailable"

    return {
        "status": "added",
        "position": pos,
        "saved_locally": True,
        "broker_sync": broker_sync,
        "message": broker_message or "Saved locally",
    }


@router.put("/api/portfolio/position", tags=["portfolio"])
async def update_position(req: PositionUpdateRequest):
    """Update stop/target/shares for an existing position."""
    global _user_portfolio
    t = req.ticker.upper().strip()
    holdings = _user_portfolio.get("holdings", [])
    found = None
    for h in holdings:
        if h.get("ticker") == t:
            found = h
            break
    if not found:
        raise HTTPException(404, f"Position {t} not found in portfolio")

    if req.shares is not None:
        found["shares"] = req.shares
    if req.entry_price is not None:
        found["entry_price"] = req.entry_price
        found["avg_cost"] = req.entry_price
    if req.stop_price is not None:
        found["stop_price"] = req.stop_price
    if req.target_1r is not None:
        found["target_1r"] = req.target_1r
    if req.target_2r is not None:
        found["target_2r"] = req.target_2r
    if req.notes is not None:
        found["notes"] = req.notes
    _user_portfolio["updated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return {"status": "updated", "position": found}


@router.delete("/api/portfolio/position/{ticker}", tags=["portfolio"])
async def remove_position(ticker: str):
    """Remove a position from portfolio."""
    global _user_portfolio
    t = ticker.upper().strip()
    holdings = _user_portfolio.get("holdings", [])
    before = len(holdings)
    holdings = [h for h in holdings if h.get("ticker") != t]
    if len(holdings) == before:
        raise HTTPException(404, f"Position {t} not found")
    _user_portfolio["holdings"] = holdings
    _user_portfolio["count"] = len(holdings)
    _user_portfolio["updated_at"] = datetime.now(timezone.utc).isoformat() + "Z"
    return {"status": "removed", "ticker": t}


@router.get("/api/portfolio/monitor", tags=["portfolio"])
async def portfolio_monitor(request: Request):
    """Monitor all positions: live price, PnL, R-multiple, stop/target alerts."""
    holdings = _user_portfolio.get("holdings", [])
    if not holdings:
        return {"positions": [], "alerts": []}

    mds = request.app.state.market_data
    alerts = []
    enriched = []

    for h in holdings:
        t = h.get("ticker", "")
        entry = h.get("entry_price") or h.get("avg_cost") or 0
        stop = (
            h.get("stop_price") or h.get("initial_stop") or h.get("current_stop") or 0
        )
        t1r = h.get("target_1r", 0)
        t2r = h.get("target_2r", 0)
        shares = h.get("shares", 0)

        # Fetch current price
        price = h.get("current_price")
        change_pct = 0
        try:
            hist = await mds.get_history(t, period="5d", interval="1d")
            if hist is not None and not hist.empty:
                c_col = "Close" if "Close" in hist.columns else "close"
                price = float(hist[c_col].iloc[-1])
                prev = float(hist[c_col].iloc[-2]) if len(hist) >= 2 else price
                change_pct = round((price / prev - 1) * 100, 2) if prev else 0
        except Exception:
            pass

        stop_defined = bool(stop and stop > 0)
        risk = abs(entry - stop) if stop_defined and entry else 0.0
        if stop_defined and entry and not t1r:
            t1r = round(entry + risk, 2)
        if stop_defined and entry and not t2r:
            t2r = round(entry + 2 * risk, 2)
        r_multiple = (
            round((price - entry) / risk, 2)
            if price and stop_defined and risk
            else None
        )
        pnl = round((price - entry) * shares, 2) if price and entry else 0
        pnl_pct = round((price / entry - 1) * 100, 2) if price and entry else 0

        dist_to_stop_pct = (
            round((price - stop) / price * 100, 2) if price and stop_defined else None
        )
        dist_to_stop_usd = (
            round((price - stop) * shares, 2)
            if price and stop_defined and shares
            else None
        )
        unrealized_r = r_multiple if stop_defined else None
        if not stop_defined:
            risk_status = "RISK ANCHOR MISSING"
            next_action = "SET STOP"
        elif price and stop and price <= stop:
            risk_status = "STOP BREACHED"
            next_action = "EXIT NOW"
        elif r_multiple is not None and r_multiple >= 2:
            risk_status = "TARGET ZONE"
            next_action = "TRIM / TRAIL"
        elif r_multiple is not None and r_multiple >= 1:
            risk_status = "PROFIT ZONE"
            next_action = "TRAIL STOP"
        else:
            risk_status = "IN TRADE"
            next_action = "MONITOR"

        pos = {
            **h,
            "current_price": price,
            "change_pct": change_pct,
            "unrealized_pnl": pnl,
            "pnl_pct": pnl_pct,
            "r_multiple": r_multiple,
            "market_value": round(price * shares, 2) if price else None,
            "initial_stop": stop if stop_defined else None,
            "current_stop": stop if stop_defined else None,
            "trailing_stop": h.get("trailing_stop"),
            "target_1r": t1r or None,
            "target_2r": t2r or None,
            "stop_defined": stop_defined,
            "distance_to_stop_pct": dist_to_stop_pct,
            "distance_to_stop_usd": dist_to_stop_usd,
            "unrealized_r": unrealized_r,
            "risk_status": risk_status,
            "next_action": next_action,
            "heat_included": stop_defined,
            "quote_pending": h.get("quote_pending", False) and not price,
            "cost_basis": round(entry * shares, 2) if entry and shares else None,
        }
        enriched.append(pos)

        # Generate alerts
        if price and stop and price <= stop:
            alerts.append(
                {
                    "ticker": t,
                    "type": "STOP_HIT",
                    "severity": "critical",
                    "msg": f"🛑 {t} hit stop ${stop:.2f} (now ${price:.2f})",
                }
            )
        if (
            price
            and t1r
            and price >= t1r
            and r_multiple is not None
            and r_multiple < 2.5
        ):
            alerts.append(
                {
                    "ticker": t,
                    "type": "TARGET_1R",
                    "severity": "success",
                    "msg": f"🎯 {t} reached 1R target ${t1r:.2f} (+{pnl_pct:.1f}%)",
                }
            )
        if price and t2r and price >= t2r:
            alerts.append(
                {
                    "ticker": t,
                    "type": "TARGET_2R",
                    "severity": "success",
                    "msg": f"🚀 {t} reached 2R target ${t2r:.2f} (+{pnl_pct:.1f}%)",
                }
            )
        if abs(change_pct) >= 5:
            alerts.append(
                {
                    "ticker": t,
                    "type": "BIG_MOVE",
                    "severity": "warning",
                    "msg": f"⚡ {t} moved {change_pct:+.1f}% today",
                }
            )

    # Summary
    total_value = sum(p.get("market_value") or 0 for p in enriched)
    total_pnl = sum(p.get("unrealized_pnl") or 0 for p in enriched)
    total_cost = sum(
        (p.get("entry_price") or p.get("avg_cost") or 0) * p.get("shares", 0)
        for p in enriched
    )

    return {
        "positions": enriched,
        "alerts": alerts,
        "summary": {
            "total_positions": len(enriched),
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": (
                round((total_value / total_cost - 1) * 100, 2) if total_cost else 0
            ),
        },
        "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


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
    from src.engines.conformal_predictor import ConformalPredictor
    from src.engines.expert_committee import ExpertCommittee
    from src.services.indicators import (
        compute_indicators as _compute_indicators,
    )  # noqa: PLC0415

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
    from src.core.models import MarketRegime, RiskRegime, TrendRegime, VolatilityRegime

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
