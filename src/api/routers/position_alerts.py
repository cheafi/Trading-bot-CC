"""
Position Risk Alerts
====================
Scans current portfolio holdings for actionable risk signals.

Alerts produced:
  STOP_PROXIMITY    current price within 2% of stop (only if stop_price>0)
  STOP_BREACH       current price beyond stop (LONG: px<=stop)
  UNREAL_DRAWDOWN   unrealized pnl_pct <= -5%
  CONCENTRATION     single position > 25% of gross book
  STALE_QUOTE       data freshness watchdog flagged STALE/CRITICAL

Pure read-only — no order side effects.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from src.api.deps import optional_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

PROX_PCT = 2.0  # within 2% of stop → STOP_PROXIMITY
DRAWDOWN_PCT = -5.0  # unrealized <= -5%
CONC_PCT = 25.0  # single pos > 25% gross book

ALERTS_LOG = os.path.join("data", "alerts.jsonl")
# In-memory de-dupe to avoid spamming Discord on every 60s poll
_DISPATCHED: Dict[str, str] = {}  # key = ticker+kind → iso timestamp
DEDUPE_MIN = 60  # don't re-push the same alert within 60 minutes
# Auto-rotation: when alerts.jsonl exceeds AUTO_ROTATE_AT lines, keep last AUTO_ROTATE_KEEP
AUTO_ROTATE_AT = 10000
AUTO_ROTATE_KEEP = 5000
_LAST_ROTATE_CHECK = 0.0  # epoch sec; only check every 5 min


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _severity_rank(sev: str) -> int:
    return {"CRITICAL": 3, "HIGH": 2, "WARN": 1, "INFO": 0}.get(sev, 0)


@router.get("/api/portfolio/risk-alerts", tags=["portfolio"])
async def portfolio_risk_alerts(request: Request, _=optional_api_key):
    """Scan current holdings and return actionable risk alerts."""
    alerts: List[Dict[str, Any]] = []

    # 1. Pull holdings from portfolio router's in-memory state
    holdings: List[Dict[str, Any]] = []
    try:
        from src.api.routers import portfolio as _pf

        holdings = list(_pf._user_portfolio.get("holdings") or [])
    except Exception as exc:
        logger.warning("alerts: portfolio import failed: %s", exc)

    gross = 0.0
    for h in holdings:
        try:
            gross += abs(float(h.get("market_value") or 0.0))
        except Exception:
            pass

    # 2. Per-position scan
    for h in holdings:
        try:
            tkr = str(h.get("ticker") or "").upper()
            if not tkr:
                continue
            px = float(h.get("current_price") or 0.0)
            stop = float(h.get("stop_price") or 0.0)
            pnl_pct = float(h.get("pnl_pct") or 0.0)
            mv = abs(float(h.get("market_value") or 0.0))
            direction = str(h.get("direction") or "LONG").upper()

            # stop breach / proximity
            if stop > 0 and px > 0:
                if direction == "LONG":
                    dist_pct = (px - stop) / stop * 100.0
                else:
                    dist_pct = (stop - px) / stop * 100.0
                if dist_pct <= 0:
                    alerts.append(
                        {
                            "ticker": tkr,
                            "kind": "STOP_BREACH",
                            "severity": "CRITICAL",
                            "msg": f"{tkr} {direction} {px:.2f} crossed stop {stop:.2f}",
                            "value": round(dist_pct, 2),
                        }
                    )
                elif dist_pct <= PROX_PCT:
                    alerts.append(
                        {
                            "ticker": tkr,
                            "kind": "STOP_PROXIMITY",
                            "severity": "HIGH",
                            "msg": f"{tkr} within {dist_pct:.1f}% of stop {stop:.2f}",
                            "value": round(dist_pct, 2),
                        }
                    )

            # unrealised drawdown
            if pnl_pct <= DRAWDOWN_PCT:
                alerts.append(
                    {
                        "ticker": tkr,
                        "kind": "UNREAL_DRAWDOWN",
                        "severity": "HIGH" if pnl_pct <= -10 else "WARN",
                        "msg": f"{tkr} unrealised {pnl_pct:.1f}%",
                        "value": round(pnl_pct, 2),
                    }
                )

            # concentration
            if gross > 0 and mv / gross * 100.0 > CONC_PCT:
                pct = mv / gross * 100.0
                alerts.append(
                    {
                        "ticker": tkr,
                        "kind": "CONCENTRATION",
                        "severity": "WARN",
                        "msg": f"{tkr} is {pct:.1f}% of gross book (>{CONC_PCT:.0f}%)",
                        "value": round(pct, 2),
                    }
                )
        except Exception as exc:
            logger.debug("alerts: per-position scan failed for %s: %s", h, exc)

    # 3. Data freshness — single STALE_QUOTE alert if watchdog flags anything
    try:
        from src.services.data_freshness_service import freshness_report

        market_data = getattr(request.app.state, "market_data", None)
        if market_data is not None:
            tickers = sorted(
                {
                    str(h.get("ticker") or "").upper()
                    for h in holdings
                    if h.get("ticker")
                }
            )
            report = await freshness_report(market_data, tickers or None)
            bad = [
                s
                for s in report.get("streams", [])
                if s.get("tier") in ("STALE", "CRITICAL")
            ]
            if bad:
                worst = max(bad, key=lambda s: s.get("age_min") or 0)
                sev = "HIGH" if worst.get("tier") == "CRITICAL" else "WARN"
                alerts.append(
                    {
                        "ticker": worst.get("ticker", "—"),
                        "kind": "STALE_QUOTE",
                        "severity": sev,
                        "msg": (
                            f"{len(bad)} stream(s) {worst.get('tier')}; "
                            f"worst {worst.get('ticker')} age {worst.get('age_min')}min"
                        ),
                        "value": worst.get("age_min"),
                    }
                )
    except Exception as exc:
        logger.debug("alerts: freshness probe failed: %s", exc)

    alerts.sort(key=lambda a: _severity_rank(a.get("severity", "INFO")), reverse=True)
    counts = {"CRITICAL": 0, "HIGH": 0, "WARN": 0, "INFO": 0}
    for a in alerts:
        counts[a.get("severity", "INFO")] = counts.get(a.get("severity", "INFO"), 0) + 1

    # Persist + fan-out new alerts (de-duped per ticker+kind within DEDUPE_MIN)
    now_iso = _utc_now_iso()
    new_dispatches = 0
    try:
        os.makedirs(os.path.dirname(ALERTS_LOG), exist_ok=True)
        with open(ALERTS_LOG, "a", encoding="utf-8") as fh:
            for a in alerts:
                key = f"{a.get('ticker')}|{a.get('kind')}"
                last_iso = _DISPATCHED.get(key)
                if last_iso:
                    try:
                        last_dt = datetime.fromisoformat(
                            last_iso.replace("Z", "+00:00")
                        )
                        age_min = (
                            datetime.now(timezone.utc) - last_dt
                        ).total_seconds() / 60
                        if age_min < DEDUPE_MIN:
                            continue
                    except Exception:
                        pass
                # Persist
                row = {**a, "ts": now_iso}
                fh.write(json.dumps(row) + "\n")
                _DISPATCHED[key] = now_iso
                new_dispatches += 1
                # Fan out HIGH+CRITICAL to Discord (best-effort, non-blocking)
                if a.get("severity") in ("HIGH", "CRITICAL"):
                    try:
                        from src.services.alert_service import _push_discord

                        sev_lower = a.get("severity", "info").lower()
                        _push_discord(
                            title=f"{a.get('kind')} · {a.get('ticker')}",
                            message=a.get("msg", ""),
                            severity=sev_lower,
                        )
                    except Exception as exc:
                        logger.debug("discord push failed: %s", exc)
    except Exception as exc:
        logger.warning("alerts persistence failed: %s", exc)

    # Auto-rotation (cheap line-count check at most every 5 min)
    global _LAST_ROTATE_CHECK
    import time as _time

    if _time.time() - _LAST_ROTATE_CHECK > 300:
        _LAST_ROTATE_CHECK = _time.time()
        try:
            if os.path.exists(ALERTS_LOG):
                with open(ALERTS_LOG, "r", encoding="utf-8") as fh:
                    n_lines = sum(1 for _ in fh)
                if n_lines > AUTO_ROTATE_AT:
                    logger.info(
                        "auto-rotating alerts.jsonl: %d lines → keep %d",
                        n_lines,
                        AUTO_ROTATE_KEEP,
                    )
                    await alerts_rotate(keep=AUTO_ROTATE_KEEP)
        except Exception as exc:
            logger.debug("auto-rotate check failed: %s", exc)

    return {
        "ok": True,
        "generated_at": now_iso,
        "positions_scanned": len(holdings),
        "alerts": alerts,
        "count": len(alerts),
        "by_severity": counts,
        "new_dispatches": new_dispatches,
        "thresholds": {
            "proximity_pct": PROX_PCT,
            "drawdown_pct": DRAWDOWN_PCT,
            "concentration_pct": CONC_PCT,
        },
    }


@router.get("/api/portfolio/alerts-history", tags=["portfolio"])
async def alerts_history(limit: int = 50, _=optional_api_key):
    """Tail the persistent alerts log (data/alerts.jsonl)."""
    rows: List[Dict[str, Any]] = []
    try:
        if os.path.exists(ALERTS_LOG):
            with open(ALERTS_LOG, "r", encoding="utf-8") as fh:
                lines = fh.readlines()[-max(1, min(limit, 500)) :]
                for ln in lines:
                    try:
                        rows.append(json.loads(ln))
                    except Exception:
                        continue
    except Exception as exc:
        logger.warning("alerts-history read failed: %s", exc)
    rows.reverse()  # most recent first
    return {
        "ok": True,
        "count": len(rows),
        "limit": limit,
        "rows": rows,
        "path": ALERTS_LOG,
    }


@router.post("/api/portfolio/alerts-clear-dedupe", tags=["portfolio"])
async def alerts_clear_dedupe(_=optional_api_key):
    """Wipe in-memory de-dupe map — next scan re-pushes all active alerts."""
    n = len(_DISPATCHED)
    _DISPATCHED.clear()
    return {"ok": True, "cleared": n}


@router.post("/api/portfolio/alerts-rotate", tags=["portfolio"])
async def alerts_rotate(keep: int = 5000, _=optional_api_key):
    """Trim alerts.jsonl to the last `keep` rows (default 5000).

    Archives discarded rows to alerts.jsonl.<UTC-date>.bak only if >0 trimmed.
    """
    keep = max(100, min(keep, 100000))
    if not os.path.exists(ALERTS_LOG):
        return {"ok": True, "trimmed": 0, "remaining": 0, "path": ALERTS_LOG}
    try:
        with open(ALERTS_LOG, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        total = len(lines)
        if total <= keep:
            return {
                "ok": True,
                "trimmed": 0,
                "remaining": total,
                "path": ALERTS_LOG,
            }
        keep_lines = lines[-keep:]
        trimmed_lines = lines[:-keep]
        # Archive the trimmed rows
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bak_path = f"{ALERTS_LOG}.{stamp}.bak"
        with open(bak_path, "w", encoding="utf-8") as bfh:
            bfh.writelines(trimmed_lines)
        # Atomic-ish rewrite
        tmp_path = ALERTS_LOG + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as tfh:
            tfh.writelines(keep_lines)
        os.replace(tmp_path, ALERTS_LOG)
        return {
            "ok": True,
            "trimmed": len(trimmed_lines),
            "remaining": len(keep_lines),
            "archive": bak_path,
            "path": ALERTS_LOG,
        }
    except Exception as exc:
        logger.exception("alerts-rotate failed: %s", exc)
        return {"ok": False, "error": str(exc), "path": ALERTS_LOG}
