#!/usr/bin/env python3
"""
CC Instant Server — starts in <1 second, loads full API in background.

Architecture:
  1. stdlib http.server binds port 8000 instantly → dashboard works
  2. Background thread imports FastAPI app + starts uvicorn on :8001 IN-PROCESS
  3. Once :8001 is ready, all API requests proxy there transparently
  4. Dashboard (/) and /health are always served locally for speed
  5. Backend runs in a spawned child process (set CC_INSTANT_NO_BACKEND=1 to skip for dev)
"""

import atexit
import fcntl
import http.server
import json
import os
import signal
import sys
import socketserver
import subprocess
import threading
import time
import gzip
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")

PORT = 8000
BACKEND_PORT = 8001
TEMPLATE = Path("src/api/templates/index.html").read_text()
TEMPLATE_BYTES = TEMPLATE.encode()
TEMPLATE_GZIP = gzip.compress(TEMPLATE_BYTES)
_backend_ready = False
_start = time.time()
_SNAPSHOT_PATH = Path("data/market_overview_last_good.json")
_BRIEF_GLOB = Path("data")
_RANKED_SNAPSHOT_PATH = Path("data/cache/playbook_ranked_snapshot.json")
_RANKED_SNAPSHOT_KEY = "30::"
_PORTFOLIO_LOCAL_PATH = Path("data/portfolio_local_holdings.json")

DEGRADED_BANNER = (
    "INSTANT DEGRADED — snapshot only · not suitable for sizing or IBKR handoff"
)


def _stamp_instant_degraded(payload: dict, *, reason: str | None = None) -> dict:
    """Stamp all instant-server degraded JSON with a prominent operator banner."""
    out = dict(payload)
    trust = dict(out.get("trust") or {})
    is_degraded = bool(
        out.get("degraded")
        or out.get("instant_degraded")
        or out.get("display_mode") == "LOADING"
        or out.get("hub_status") == "degraded"
        or trust.get("stale")
        or str(trust.get("source") or "").startswith("instant-degraded")
        or str(trust.get("source") or "") == "brief-fallback"
        or out.get("source") in ("brief-fallback", "disk-snapshot", "instant-local")
    )
    if not is_degraded:
        return out
    out["degraded"] = True
    out.setdefault("instant_degraded", True)
    out.setdefault("degraded_banner", DEGRADED_BANNER)
    trust.setdefault("stale", True)
    if reason:
        trust.setdefault("reason", reason)
    if not trust.get("source"):
        trust["source"] = "instant-degraded"
    out["trust"] = trust
    return out


def _encode_degraded(payload: dict, *, reason: str | None = None) -> bytes:
    return json.dumps(_stamp_instant_degraded(payload, reason=reason)).encode()


def _maybe_stamp_degraded_body(body: bytes) -> bytes:
    try:
        payload = json.loads(body.decode())
    except Exception:
        return body
    stamped = _stamp_instant_degraded(payload)
    if stamped.get("degraded_banner") == payload.get("degraded_banner") and not (
        stamped.get("instant_degraded") and not payload.get("instant_degraded")
    ):
        if not stamped.get("instant_degraded"):
            return body
    return json.dumps(stamped).encode()


def _proxy_timeout(path: str) -> int:
    """Keep dashboard-critical calls from hanging the instant server."""
    if path.startswith("/api/v7/opportunity-scanner") and "force_refresh=true" in path:
        return 35
    if path.startswith(
        (
            "/healthz",
            "/readyz",
            "/api/health",
            "/api/live/market",
            "/api/recommendations",
            "/api/v7/today",
            "/api/ops/cc-header",
            "/api/ops/error-log",
            "/api/ops/changelog",
            "/api/ops/engine/status",
            "/api/v7/playbook/ranked",
            "/api/v7/flow-decision",
            "/api/v7/playbook/scanners",
        )
    ):
        return 5
    if "strategy-factory" in path:
        return 120
    if path.startswith("/api/v7/macro-intel"):
        return 120
    if path.startswith(
        (
            "/api/v7/portfolio-brief",
            "/api/v7/performance-lab",
            "/api/v7/regime-screener",
            "/api/v7/compare-overlay",
            "/api/live/backtest",
            "/api/live/brief",
            "/api/live/dossier/",
            "/api/live/time-travel",
            "/api/v7/stock-intel/",
            "/api/v7/decision-hub",
            "/api/v7/portfolio-decision",
            "/api/dossier/",
            "/api/v7/playbook/no-trade",
            "/api/v7/backtest-lab",
            "/api/fund-lab/live",
            "/api/v7/today/ai-narrative",
            "/api/ops/status",
            "/api/v7/ops-console",
        )
    ):
        return 90
    return 20


def _dashboard_api_key(header_value: str | None) -> str | None:
    """Return the API key the local dashboard proxy should send upstream.

    The static dashboard historically falls back to ``dev-secret-local``. In
    prod-local runs the real key can be supplied from ``.env`` and differ from
    that fallback, which caused authenticated Ops panels to stay blank with
    401s. Keep the real key server-side and only rewrite the known dashboard
    fallback inside this local proxy.
    """
    actual = os.environ.get("API_SECRET_KEY") or None
    if actual and (not header_value or header_value == "dev-secret-local"):
        return actual
    return header_value


def _load_snapshot():
    """Return last-good market overview bytes (with stale flag), or None."""
    try:
        if not _SNAPSHOT_PATH.is_file():
            return None
        raw = _SNAPSHOT_PATH.read_bytes()
        try:
            data = json.loads(raw)
            trust = dict(data.get("trust") or {})
            trust.update(
                {
                    "source": "snapshot",
                    "stale": True,
                    "reason": "backend importing",
                }
            )
            data["trust"] = trust
            return _encode_degraded(data, reason="backend importing")
        except Exception:
            return raw
    except Exception:
        return None


def _load_latest_brief() -> dict | None:
    """Load newest data/brief-YYYY-MM-DD.json without importing the app stack."""
    try:
        candidates = sorted(_BRIEF_GLOB.glob("brief-*.json"), reverse=True)
        for path in candidates:
            if not path.is_file():
                continue
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                data["_brief_path"] = str(path)
                return data
    except Exception:
        return None
    return None


def _brief_row_to_top5(row: dict, rank: int) -> dict:
    ticker = row.get("ticker") or row.get("symbol") or "—"
    entry = row.get("entry") or row.get("entry_price") or row.get("price")
    stop = row.get("stop") or row.get("stop_price")
    target = row.get("target_3r") or row.get("target_2r") or row.get("target_price")
    return {
        "rank": rank,
        "ticker": ticker,
        "strategy": "brief_fallback",
        "score": float(row.get("rs_score") or row.get("score") or 0),
        "grade": "B",
        "timing": "Developing",
        "action": "WATCH",
        "raw_action": "WATCH",
        "action_reason": (
            "Morning brief fallback — live scanner unavailable; watch only"
        ),
        "why_now": [
            f"RS {row.get('rs_score', '—')} · ATR {row.get('atr_pct', '—')}% · Vol {row.get('vol_ratio', '—')}x"
        ],
        "entry_price": entry,
        "target_price": target,
        "stop_price": stop,
        "risk_reward": row.get("risk_reward"),
        "execution_ready": False,
        "confidence_fallback_only": True,
        "thesis_conf": 0,
        "timing_conf": 0,
        "exec_conf": 0,
        "data_conf": 0,
        "final_conf": None,
        "evidence_badge": "brief-fallback",
    }


def _today_bytes_from_brief(brief: dict, reason: str) -> bytes:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    top5: list[dict] = []
    rank = 1
    for section in ("actionable", "watch"):
        for row in brief.get(section) or []:
            if rank > 5:
                break
            top5.append(_brief_row_to_top5(row, rank))
            rank += 1
        if rank > 5:
            break
    universe = int(brief.get("universe_count") or 0)
    try:
        from src.services.decision_truth_model import (
            apply_authority_to_rows,
            assemble_confidence_breakdown,
            build_decision_authority,
        )

        for row in top5:
            conf = assemble_confidence_breakdown(row)
            row["confidence_breakdown"] = conf
            row["final_conf"] = conf.get("final")
        authority = build_decision_authority(
            tradeability="WAIT",
            should_trade=False,
            fallback_brief=True,
            scanner_degraded=True,
            data_stale=True,
            trust_source="brief-fallback",
        )
        top5 = apply_authority_to_rows(top5, authority)
        decision_authority = authority
    except Exception:
        decision_authority = {
            "source": "fallback_brief",
            "authority_level": "suspended",
            "gates": {"fallback_brief": True},
            "effective_action_max": "NONE",
        }
    payload = {
        "date": brief.get("date") or now.strftime("%Y-%m-%d"),
        "narrative": (
            f"Morning brief fallback ({brief.get('date', 'latest')}) — "
            "live scanner unavailable. Informational watch only."
        ),
        "market_regime": {
            "label": "NEUTRAL",
            "risk_state": "NEUTRAL",
            "should_trade": False,
            "confidence": 0.45,
            "tradeability": "WAIT",
            "summary": reason,
            "trend": "SIDEWAYS",
            "volatility": "NORMAL",
            "score": 50,
            "vix": None,
            "breadth": None,
            "entropy": None,
        },
        "market_pulse": {},
        "top_5": top5,
        "filter_funnel": {
            "universe": universe,
            "signals_triggered": len(top5),
            "score_above_6": len(top5),
            "actionable_above_7": len(
                [r for r in top5 if float(r.get("score") or 0) >= 70]
            ),
            "high_conviction_above_8": len(
                [r for r in top5 if float(r.get("score") or 0) >= 80]
            ),
        },
        "best_setup_family": None,
        "family_breakdown": {},
        "avoid": ["Live validation pending — brief fallback only"],
        "what_changed": [reason],
        "event_risks": [],
        "sector_summary": {},
        "action_summary": {},
        "ai_narrative": None,
        "decision_authority": decision_authority,
        "todays_decision": {
            "day_state": "PILOT_WATCH_DAY",
            "hero_label": "Top fallback candidate",
            "deploy_posture": "WATCH",
            "deploy_label": "Brief fallback — informational watch only",
            "can_deploy_today": False,
        },
        "trust": {
            "mode": "PAPER",
            "source": "brief-fallback",
            "freshness": "DEGRADED",
            "stale": True,
            "reason": reason,
            "ai_powered": False,
            "as_of": now.isoformat() + "Z",
        },
        "generated_at": now.isoformat() + "Z",
    }
    return _encode_degraded(payload, reason=reason)


def _stale_today_bytes(reason: str = "backend importing") -> bytes:
    """Minimal /api/v7/today payload so the dashboard renders during cold start."""
    brief = _load_latest_brief()
    if brief and (brief.get("actionable") or brief.get("watch")):
        return _today_bytes_from_brief(brief, reason)
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "date": now.strftime("%Y-%m-%d"),
        "narrative": "API is still loading — showing degraded snapshot.",
        "market_regime": {
            "label": "NEUTRAL",
            "risk_state": "NEUTRAL",
            "should_trade": False,
            "confidence": 0.0,
            "tradeability": "WAIT",
            "summary": reason,
            "trend": "SIDEWAYS",
            "volatility": "NORMAL",
            "score": 0,
            "vix": None,
            "breadth": None,
            "entropy": None,
        },
        "market_pulse": {},
        "top_5": [],
        "filter_funnel": {
            "universe": 0,
            "signals_triggered": 0,
            "score_above_6": 0,
            "actionable_above_7": 0,
            "high_conviction_above_8": 0,
        },
        "best_setup_family": None,
        "family_breakdown": {},
        "avoid": [reason],
        "what_changed": [reason],
        "event_risks": [],
        "sector_summary": {},
        "action_summary": {},
        "ai_narrative": None,
        "trust": {
            "mode": "PAPER",
            "source": "instant-degraded",
            "freshness": "DEGRADED",
            "stale": True,
            "reason": reason,
            "ai_powered": False,
            "as_of": now.isoformat() + "Z",
        },
        "generated_at": now.isoformat() + "Z",
    }
    return _encode_degraded(payload, reason=reason)


def _finalize_degraded_ranked(payload: dict, *, limit: int = 30) -> dict:
    """Apply near-miss supplement so all-AVOID snapshots still render watch rows."""
    try:
        from src.services.playbook_board_fallback import (
            annotate_board_mode,
            supplement_zero_deploy_board,
        )
        from src.services.decision_truth_model import finalize_ranked_payload_authority

        data = annotate_board_mode(dict(payload), from_live=False)
        data = supplement_zero_deploy_board(data, limit)
        return finalize_ranked_payload_authority(data)
    except Exception:
        return payload


def _load_ranked_snapshot_bytes() -> bytes | None:
    """Serve last-good playbook board from disk cache."""
    try:
        if not _RANKED_SNAPSHOT_PATH.is_file():
            return None
        store = json.loads(_RANKED_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        entry = store.get(_RANKED_SNAPSHOT_KEY) or next(iter(store.values()), None)
        if not isinstance(entry, dict):
            return None
        payload = entry.get("data")
        if not isinstance(payload, dict):
            return None
        payload = {
            **payload,
            "cached": True,
            "stale": True,
            "source": "disk-snapshot",
            "refreshing": False,
            "board_mode": payload.get("board_mode") or "compressed_fallback",
        }
        payload = _finalize_degraded_ranked(payload)
        return _encode_degraded(payload, reason="disk snapshot — backend still loading")
    except Exception:
        return None


def _parse_query(path: str) -> dict[str, str]:
    if "?" not in path:
        return {}
    try:
        from urllib.parse import parse_qs

        return {k: v[0] for k, v in parse_qs(path.split("?", 1)[1]).items()}
    except Exception:
        return {}


def _brief_row_for_ticker(ticker: str) -> dict | None:
    """Find newest morning-brief row for a symbol (no app import)."""
    brief = _load_latest_brief() or {}
    want = str(ticker or "").strip().upper()
    if not want:
        return None
    for section in ("actionable", "watch", "avoid", "reject"):
        for row in brief.get(section) or []:
            sym = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
            if sym == want:
                return row
    return None


def _stale_stock_intel_bytes(path: str, reason: str) -> bytes | None:
    """Core/enrichment stock-intel while uvicorn is loading or upstream 503."""
    from datetime import datetime, timezone

    path_only = path.split("?", 1)[0]
    segments = [s for s in path_only.rstrip("/").split("/") if s]
    if len(segments) < 2 or segments[-2] != "stock-intel":
        return None
    ticker = segments[-1].strip().upper()
    if not ticker or len(ticker) > 12:
        return None

    q = _parse_query(path)
    enrich = str(q.get("enrichments", "")).lower() in ("true", "1", "yes")
    now = datetime.now(timezone.utc)
    as_of = now.isoformat().replace("+00:00", "Z")

    if enrich:
        return _encode_degraded(
            {
                "ticker": ticker,
                "as_of": as_of,
                "load_phase": "enrichments",
                "partial": True,
                "research_only": True,
                "sizing_blocked": True,
                "size_info": {
                    "shares": 0,
                    "sizing_blocked": True,
                    "size_explanation": "No sizing guidance in confirm-only mode",
                },
                "module_errors": {"enrichments": reason},
                "dossier": {"symbol": ticker},
                "unified_decision": {
                    "label": "CONFIRM ONLY",
                    "pill": "pw",
                    "color": "border",
                    "confidence": None,
                    "confidence_available": False,
                    "reason": "Enrichments unavailable until live API is ready.",
                },
                "narrative": {
                    "bull_case": [],
                    "bear_case": ["Enrichment modules pending backend warm-up."],
                },
                "decision_bar": {"verdict": "CONFIRM ONLY", "confidence": None},
                "decision_stack": {
                    "primary_state": "RESEARCH",
                    "verdict": "CONFIRM ONLY",
                },
                "trust": {
                    "mode": "RESEARCH",
                    "source": "instant-degraded",
                    "as_of": as_of,
                    "stale": True,
                    "reason": reason,
                },
            },
            reason=reason,
        )

    row = _brief_row_for_ticker(ticker)
    price = 0.0
    stop = target_1r = target_2r = None
    atr = vol_ratio = 0.0
    if row:
        try:
            price = float(row.get("price") or row.get("entry") or 0)
        except (TypeError, ValueError):
            price = 0.0
        stop = row.get("stop")
        target_1r = row.get("target_2r")
        target_2r = row.get("target_3r")
        try:
            atr = float(row.get("atr_value") or 0)
        except (TypeError, ValueError):
            atr = 0.0
        try:
            vol_ratio = float(row.get("vol_ratio") or 1)
        except (TypeError, ValueError):
            vol_ratio = 1.0

    entry = row.get("entry") if row else None
    trade_plan: dict = {}
    if entry is not None:
        trade_plan["entry_zone"] = [entry, entry]
    if stop is not None:
        trade_plan["stop"] = stop
    if target_1r is not None:
        trade_plan["target_1r"] = target_1r
    if target_2r is not None:
        trade_plan["target_2r"] = target_2r

    dossier = {
        "symbol": ticker,
        "price": round(price, 2) if row else None,
        "change_pct": 0.0,
        "technicals": {
            "rsi": 50.0,
            "atr": round(atr, 2) if atr else 0.0,
            "vol_ratio": round(vol_ratio, 2) if vol_ratio else 1.0,
            "above_sma20": False,
            "above_sma50": False,
            "above_sma200": False,
        },
        "trade_plan": trade_plan,
        "why_buy": (
            ["Brief-backed levels — confirm live research before sizing."]
            if row
            else ["Live quote pending — backend still loading."]
        ),
        "why_stop": ["Levels are indicative until full dossier loads."],
        "regime": {"should_trade": False, "label": "UNKNOWN"},
        "structure": {"cached": True, "note": "Structure from brief cache only"},
        "trust": {
            "mode": "RESEARCH",
            "source": "instant-degraded",
            "as_of": as_of,
            "stale": True,
            "reason": reason,
        },
        "_partial": True,
        "_partial_reason": "instant_core_fallback",
    }

    module_errors: dict[str, str] = {}
    partial_notice = (
        "Brief-backed core from instant snapshot — load enrichments or retry when live API is ready."
    )
    if not row:
        module_errors["dossier"] = (
            f"{ticker} not in latest brief cache — quote/technicals pending live API"
        )
        partial_notice = module_errors["dossier"]

    unified = {
        "label": "CONFIRM ONLY",
        "pill": "pw",
        "color": "border",
        "confidence": None,
        "confidence_available": False,
        "reason": (
            "Core dossier from brief cache — not decision-grade until live research loads."
            if row
            else "Awaiting live market data — brief has no row for this symbol."
        ),
        "entry_zone": trade_plan.get("entry_zone"),
        "stop": trade_plan.get("stop"),
        "target_1r": trade_plan.get("target_1r"),
        "target_2r": trade_plan.get("target_2r"),
        "rr_ratio": None,
        "rr_ratio_display": None,
    }

    size_info = {
        "shares": 0,
        "risk_per_share": None,
        "size_explanation": "No sizing guidance in confirm-only mode",
        "size_basis": None,
        "entry_midpoint": None,
        "sizing_blocked": True,
    }
    return _encode_degraded(
        {
            "ticker": ticker,
            "as_of": as_of,
            "load_phase": "core",
            "partial": True,
            "research_only": True,
            "sizing_blocked": True,
            "partial_notice": partial_notice,
            "module_errors": module_errors,
            "dossier": dossier,
            "unified_decision": unified,
            "size_info": size_info,
            "narrative": {
                "bull_case": dossier["why_buy"],
                "bear_case": dossier["why_stop"],
            },
            "decision_bar": {"verdict": "CONFIRM ONLY", "confidence": None},
            "decision_stack": {
                "primary_state": "RESEARCH",
                "verdict": "CONFIRM ONLY",
            },
            "p9": {"fundamentals": None, "earnings": None, "structure": None},
            "regime": {"label": "UNKNOWN", "should_trade": False},
            "trust": dossier["trust"],
        },
        reason=reason,
    )


def _stale_flow_bytes() -> bytes:
    """Full flow-decision shape — mock/research_only until live provider loads."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    brief = _load_latest_brief() or {}
    mock_flow: list[dict] = []
    for row in (brief.get("actionable") or [])[:6]:
        tk = row.get("ticker") or row.get("symbol")
        if not tk:
            continue
        mock_flow.append(
            {
                "underlying": tk,
                "contract_symbol": f"{tk}_MOCK",
                "radar_score": round(float(row.get("vol_ratio") or 0) * 10, 1),
                "pm_action": "WATCH_FOR_STOCK_CONFIRM",
                "actionable": False,
                "call_put": "C",
                "mock": True,
            }
        )
    payload = {
        "as_of": now.isoformat() + "Z",
        "regime": {
            "tradeability": "WAIT",
            "trend": "SIDEWAYS",
            "stance": "Backend loading — flow is research-only until live provider connects",
        },
        "freshness": {
            "provider": "instant-degraded",
            "mode": "mock",
            "synthetic": True,
            "stale": True,
            "tier": "STALE",
            "as_of": now.isoformat() + "Z",
            "warning": "Backend importing — mock/research flow only",
            "methodology": "Degraded instant snapshot — not live provider data",
        },
        "calibration": {
            "available": False,
            "label": "Calibration unavailable",
            "detail": "Backend still loading — insufficient evidence for calibrated flow grades",
        },
        "actionable_top3": [],
        "watch_for_confirm": mock_flow[:3],
        "best_bullish_flow": [],
        "best_bearish_flow": [],
        "crowded_trap_risk": [],
        "live_flow": [],
        "mock_flow": mock_flow,
        "count_live": 0,
        "count_mock": len(mock_flow),
        "degraded": True,
        "mock_only": True,
        "research_only": True,
        "provider_hint": "Instant server — full flow surface pending on :8001",
        "warning": "MOCK MODE — illustrative research preview until backend is ready",
        "trust": {"stale": True, "source": "instant-degraded", "synthetic": True},
    }
    return _encode_degraded(payload)


def _stale_fund_lab_bytes(reason: str) -> bytes:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    brief = _load_latest_brief() or {}
    regime_label = "SIDEWAYS · WAIT"
    _constituent_labels = (
        "Research constituent",
        "Sleeve sample member",
        "Candidate constituent",
    )
    cards: list[dict] = []
    for idx, row in enumerate((brief.get("actionable") or [])[:3]):
        tk = row.get("ticker")
        if not tk:
            continue
        role = _constituent_labels[idx % len(_constituent_labels)]
        cards.append(
            {
                "id": f"brief_{str(tk).lower()}",
                "display_name": f"{tk} · {role}",
                "constituent_role": role,
                "gate_status": "RESEARCH",
                "stance": "NEUTRAL",
                "mode": "model_backtest",
                "controls_capital": False,
                "regime_fit": "warming",
                "metrics_pending": True,
                "fund_return_pct": None,
                "excess_return_pct": None,
                "max_drawdown_pct": None,
                "benchmark_return_pct": None,
                "equity_curve_20": [],
                "evidence_badge": "model_backtest",
            }
        )
    console = {
        "regime": regime_label,
        "regime_display": regime_label,
        "regime_stale": True,
        "regime_stale_note": reason,
        "allocator_truth_strip": {
            "live_eligible_count": 0,
            "research_sleeve_count": len(cards),
            "execution_ready": False,
            "execution_ready_label": "Blocked — backend loading",
            "current_allocatable": "None",
            "max_capital_allowed": "0%",
            "why_not_more": [
                "Backend importing — full API still loading",
                "Live fund-lab pending",
            ],
        },
        "investable_now": {
            "regime": regime_label,
            "regime_source": "instant-degraded",
            "regime_stale": True,
            "regime_stale_note": reason,
            "deploy_label": "No — backend still loading",
            "truth_headline": "Model sleeves unavailable — research context only",
            "allocation_headline": "0% deployable — research context only",
            "allocation_lines": [
                "Core index posture only — model sleeves not allocatable",
                "HTTP 503 · API warming until full backend is ready",
            ],
            "max_capital_allowed": "0%",
            "execution_state_label": "Blocked — backend loading",
            "execution_ready": "No",
        },
        "execution_readiness": {
            "execution_state_label": "Blocked — backend loading",
            "readiness_label": "Not ready",
            "broker_connected": False,
            "trade_handoff_ready": False,
            "paper_or_live": "paper",
            "can_push_ibkr": False,
            "can_push_ibkr_label": "No — backend loading",
        },
        "cards": cards,
    }
    payload = {
        "regime": regime_label,
        "regime_display": regime_label,
        "benchmark": "SPY",
        "benchmark_return_pct": None,
        "metrics_pending": True,
        "period": "1y",
        "cards": cards,
        "console": console,
        "count": len(cards),
        "degraded": True,
        "research_only": True,
        "as_of": now.isoformat() + "Z",
        "trust": {"stale": True, "source": "instant-degraded", "reason": reason},
    }
    return _encode_degraded(payload, reason=reason)


def _stale_no_trade_bytes(reason: str) -> bytes:
    brief = _load_latest_brief() or {}
    signals: list[dict] = []
    for row in brief.get("avoid") or []:
        tk = row if isinstance(row, str) else row.get("ticker")
        if not tk:
            continue
        signals.append(
            {
                "ticker": tk,
                "action": "NO_TRADE",
                "reason": "Brief avoid list — live rejection audit pending",
                "blocker_category": "context",
                "sector": "—",
                "stage": "—",
            }
        )
        if len(signals) >= 8:
            break
    return _encode_degraded(
        {
            "count": len(signals),
            "no_trade_signals": signals,
            "rejection_summary": {
                "total_blocked": len(signals),
                "by_blocker": {},
                "note": reason,
            },
            "regime": {
                "trend": "SIDEWAYS",
                "tradeability": "WAIT",
                "should_trade": False,
            },
            "degraded": True,
            "research_only": True,
            "trust": {"stale": True, "source": "instant-degraded", "reason": reason},
        },
        reason=reason,
    )


def _stale_backtest_lab_bytes(path: str, reason: str) -> bytes:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    q = _parse_query(path)
    ticker = str(q.get("ticker") or "AAPL").upper()
    return _encode_degraded(
        {
            "as_of": now.isoformat() + "Z",
            "ticker": ticker,
            "strategy": q.get("strategy") or "all",
            "period": q.get("period") or "6mo",
            "core_backtest": {
                "ticker": ticker,
                "equity_chart": {"bh": [], "strategy": [], "signals": []},
                "strategies": [],
                "best_strategy": None,
            },
            "walk_forward": {
                "windows": [{"window": "recent", "label": "Recent window", "error": reason}],
                "stability_score": 0,
                "verdict": "insufficient_data",
                "note": "Backend importing — run lab again when API is ready",
            },
            "trade_level_review": {
                "trade_count": 0,
                "summary": reason,
                "strategy": None,
                "win_rate": None,
                "avg_win_pct": None,
                "avg_loss_pct": None,
            },
            "attribution": {"ranked": [], "benchmark_return_pct": None},
            "evidence": {
                "basis": "backtest",
                "label": "Degraded placeholder — not a valid backtest",
            },
            "degraded": True,
            "research_only": True,
            "trust": {"stale": True, "source": "instant-degraded", "reason": reason},
        },
        reason=reason,
    )


def _stale_ops_console_bytes(reason: str) -> bytes:
    from src.services.ops_operator_console import build_degraded_ops_operator_console

    brief_ok = bool(_load_latest_brief())
    return _encode_degraded(
        build_degraded_ops_operator_console(reason=reason, brief_ok=brief_ok),
        reason=reason,
    )


def _stale_ops_error_log_bytes(reason: str) -> bytes:
    """Session ring buffer lives in uvicorn — honest warming stub for Ops Error Log."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = {
        "id": "ops-warming",
        "timestamp": now,
        "severity": "warning",
        "component": "ops",
        "message": "Session error buffer not yet confirmed",
        "detail": (
            f"{reason}. The in-memory error log is owned by the full API process — "
            "this panel cannot confirm whether errors were logged this session until "
            "the backend is ready."
        ),
        "suggested_action": "Wait for /api/health mode=full, then click Refresh.",
    }
    return _encode_degraded(
        {
            "count": 1,
            "total_buffered": 1,
            "severity_filter": "all",
            "include_stack": False,
            "entries": [entry],
            "session_confirmed": False,
        },
        reason=reason,
    )


def _stale_ops_changelog_bytes(reason: str) -> bytes:
    """Disk changelog while uvicorn is still importing."""
    from datetime import datetime, timezone

    path = Path("data/changelog.json")
    now = datetime.now(timezone.utc)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("changelog root must be object")
        entries = raw.get("entries")
        if not isinstance(entries, list):
            entries = []
        payload = {
            "version": raw.get("version") or "—",
            "updated": raw.get("updated") or now.strftime("%Y-%m-%d"),
            "product": raw.get("product") or "CC — Clarity Console",
            "source": "data/changelog.json",
            "entries": entries,
            "instant_degraded": True,
            "degraded_reason": reason,
        }
        return _encode_degraded(payload, reason=reason)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return _encode_degraded(
            {
                "version": "—",
                "updated": now.strftime("%Y-%m-%d"),
                "product": "CC — Clarity Console",
                "source": "instant-fallback",
                "entries": [
                    {
                        "date": now.strftime("%Y-%m-%d"),
                        "title": "CC platform",
                        "summary": (
                            f"{reason}. Changelog file unavailable — showing built-in fallback."
                        ),
                        "surfaces": ["Ops"],
                    }
                ],
            },
            reason=reason,
        )


def _stale_rs_decision_bytes(reason: str) -> bytes:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    brief = _load_latest_brief() or {}
    stale_rows: list[dict] = []
    for row in (brief.get("actionable") or [])[:8]:
        tk = row.get("ticker")
        if not tk:
            continue
        stale_rows.append(
            {
                "ticker": tk,
                "rs_score": float(row.get("rs_score") or 0),
                "trend": "WATCH",
                "buyability": "MONITOR",
                "sector": "—",
                "stale": True,
            }
        )
    return _encode_degraded(
        {
            "as_of": now.isoformat() + "Z",
            "compute_ms": 0,
            "freshness": {
                "live": False,
                "stale_reason": reason,
                "universe_size": len(stale_rows),
                "benchmark": "SPY",
                "interval": "1d",
                "methodology": "Brief fallback — not live RS compute",
            },
            "regime": {
                "tradeability": "WAIT",
                "trend": "SIDEWAYS",
                "stance": "Stand down — live RS unavailable",
            },
            "actionable_top3": [],
            "false_leaders_top3": [],
            "pullback_candidates": [],
            "crowded_chase_risk": [],
            "sector_rotation": [],
            "live_leaders": [],
            "stale_watchlist": stale_rows,
            "emerging": [],
            "failed": [],
            "count_live": 0,
            "count_stale": len(stale_rows),
            "degraded": True,
            "research_only": True,
            "warning": "Live RS unavailable — stale names are NOT actionable",
            "trust": {"stale": True, "source": "instant-degraded", "reason": reason},
        },
        reason=reason,
    )


_DECISION_INTENT_ORDER = (
    "LEADERS",
    "PULLBACKS",
    "BREAKOUTS",
    "FLOW",
    "NO_TRADE",
)


def _stale_scanners_bytes() -> bytes:
    """Degraded Discovery hub — mirrors live /scanners shape (intent cards never blank)."""
    brief = _load_latest_brief() or {}
    universe_size = int(brief.get("universe_count") or 0)
    regime_note = "Brief fallback · backend importing"
    top_hits: list[dict] = []
    for row in (brief.get("actionable") or []) + (brief.get("watch") or []):
        tk = row.get("ticker")
        if not tk:
            continue
        score = float(row.get("rs_score") or row.get("score") or 5)
        top_hits.append(
            {
                "ticker": tk,
                "scanner": "brief_fallback",
                "category": "PATTERN",
                "score": round(min(10.0, max(3.0, score / 10 if score > 10 else score)), 1),
                "strength": round(min(10.0, max(3.0, score / 10 if score > 10 else score)), 1),
                "headline": "Brief watchlist (degraded hub)",
                "why_surfaced": "Morning brief row until live scanner matrix loads",
                "signal_source": "brief_fallback",
                "freshness": "stale",
                "status": "monitor",
                "urgency": "NORMAL",
                "next_action": "Open dossier · confirm in Playbook",
                "confidence": 0.55,
            }
        )
        if len(top_hits) >= 12:
            break

    pattern_bucket = {
        "brief_fallback": {
            "count": len(top_hits),
            "top_hits": top_hits[:10],
            "display_count": min(len(top_hits), 10),
        }
    }
    category_summary = {
        "PATTERN": {
            "count": len(top_hits),
            "top_hits": top_hits[:5],
            "display_count": min(len(top_hits), 5),
            "urgent_count": 0,
            "warning_count": 0,
        },
        "FLOW": {"count": 0, "top_hits": [], "display_count": 0},
        "SECTOR": {"count": 0, "top_hits": [], "display_count": 0},
        "RISK": {"count": 0, "top_hits": [], "display_count": 0},
        "VALIDATION": {"count": 0, "top_hits": [], "display_count": 0},
    }
    decision_intent = {
        intent: {
            "intent": intent,
            "count": len(top_hits) if intent == "LEADERS" and top_hits else 0,
            "probe_status": "warming",
            "regime_note": regime_note,
            "empty_why": (
                "Brief-backed degraded hub — live matrix still loading. "
                "Zero hits on other intents is normal until backend is ready."
            ),
            "top_hits": top_hits[:3] if intent == "LEADERS" else [],
        }
        for intent in _DECISION_INTENT_ORDER
    }
    merged = [
        {
            "ticker": h["ticker"],
            "max_score": h.get("score"),
            "overlap": 1,
            "action": "WATCH",
        }
        for h in top_hits[:12]
    ]
    reason = (
        "Backend importing — showing brief-backed Discovery hub (research-only)."
        if not top_hits
        else "Backend importing — brief names shown as warming samples (research-only)."
    )
    payload = {
        "universe_size": universe_size or len(top_hits) or 40,
        "universe_label": "warming" if not top_hits else "watchlist",
        "total_hits": len(top_hits),
        "scanners": {"PATTERN": pattern_bucket} if top_hits else {},
        "category_summary": category_summary,
        "decision_intent": decision_intent,
        "merged_top_names": merged,
        "discovery_verdict": {
            "best_scanner_today": "brief_fallback" if top_hits else None,
            "best_scanner_hits": len(top_hits),
            "best_confirmed_name": merged[0] if len(merged) >= 2 else None,
            "best_speculative_name": merged[0] if len(merged) == 1 else None,
            "avoid_now_count": len(brief.get("avoid") or []),
            "discovery_breadth": (
                f"{1 if top_hits else 0}/5 categories active (brief fallback)"
            ),
            "active_categories": 1 if top_hits else 0,
            "total_unique_names": len(merged),
            "universe_size": universe_size or len(top_hits),
            "regime": "warming",
        },
        "scanner_overlap": {m["ticker"]: m["overlap"] for m in merged},
        "scanner_quality": {
            "label": "WARMING",
            "note": "Instant server — full scanner matrix pending",
        },
        "diagnostics": {
            "data_freshness": "stale",
            "source": "brief-fallback",
            "symbols_scanned": universe_size or len(top_hits),
            "reason_no_hits": reason,
            "universe_label": "warming",
            "failures": ["backend importing"],
        },
        "research_note": (
            "Decision-intent scanners are research/supporting unless Playbook confirms. "
            "Degraded hub — confirm in Playbook before sizing."
        ),
        "hub_status": "degraded",
        "trust": {"stale": True, "source": "instant-degraded"},
    }
    return _encode_degraded(payload)


def _stale_ranked_bytes(reason: str) -> bytes:
    body = _load_ranked_snapshot_bytes()
    if body:
        return _maybe_stamp_degraded_body(body)
    brief = _load_latest_brief() or {}
    opps = []
    for row in (brief.get("actionable") or []) + (brief.get("watch") or []):
        rs = float(row.get("rs_score") or 0)
        tier = "High" if rs >= 7.5 else ("Medium" if rs >= 6 else "Low")
        opps.append(
            {
                "ticker": row.get("ticker"),
                "score": rs,
                "score_display_mode": "fallback_rank",
                "score_display": tier,
                "score_display_label": "Fallback rank · relevance only",
                "priority_tier": tier,
                "score_source": "brief-fallback",
                "action": "WATCH",
                "grade": "C",
                "why_now": "Brief fallback board",
                "evidence_badge": "brief-fallback",
                "confidence_fallback_only": True,
                "card_display_mode": "reference_only",
            }
        )
        if len(opps) >= 30:
            break
    payload = {
        "count": len(opps),
        "opportunities": opps,
        "cached": True,
        "stale": True,
        "source": "brief-fallback",
        "score_display_mode": "fallback_rank",
        "board_mode": "compressed_fallback",
        "board_message": reason,
        "refreshing": False,
    }
    payload = _finalize_degraded_ranked(payload)
    return _encode_degraded(payload, reason=reason)


def _load_local_portfolio() -> dict:
    try:
        if _PORTFOLIO_LOCAL_PATH.is_file():
            data = json.loads(_PORTFOLIO_LOCAL_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"holdings": [], "source": "manual", "updated_at": ""}


def _save_local_portfolio(data: dict) -> None:
    _PORTFOLIO_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PORTFOLIO_LOCAL_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _build_local_position(body: dict, *, now: str) -> dict:
    """Minimal position record when full API stack is still importing."""
    t = str(body.get("ticker") or "").upper().strip()
    entry = float(body.get("entry_price") or 0)
    shares = float(body.get("shares") or 0)
    stop = float(body.get("stop_price") or 0)
    stop_defined = stop > 0
    risk = abs(entry - stop) if stop_defined else 0.0
    t1r = float(body.get("target_1r") or 0)
    t2r = float(body.get("target_2r") or 0)
    if stop_defined and not t1r:
        t1r = round(entry + risk, 2)
    if stop_defined and not t2r:
        t2r = round(entry + 2 * risk, 2)
    return {
        "ticker": t,
        "shares": shares,
        "avg_cost": entry,
        "entry_price": entry,
        "current_price": entry,
        "stop_price": stop if stop_defined else 0,
        "target_1r": t1r if stop_defined else 0,
        "target_2r": t2r if stop_defined else 0,
        "market_value": round(entry * shares, 2),
        "cost_basis": round(entry * shares, 2),
        "unrealized_pnl": 0.0,
        "pnl_pct": 0.0,
        "r_multiple": None,
        "stop_defined": stop_defined,
        "quote_pending": True,
        "status": "OPEN",
        "added_at": now,
        "notes": str(body.get("notes") or ""),
    }


def _degraded_portfolio_position_post(body: bytes) -> tuple[int, bytes] | None:
    """Accept quick-add while uvicorn is still loading."""
    from datetime import datetime, timezone

    try:
        payload = json.loads(body.decode("utf-8") if body else "{}")
    except Exception:
        return 400, json.dumps({"detail": "Invalid JSON body"}).encode()

    t = str(payload.get("ticker") or "").upper().strip()
    shares = float(payload.get("shares") or 0)
    entry = float(payload.get("entry_price") or 0)
    if not t:
        return 400, json.dumps({"detail": "Ticker is required"}).encode()
    if shares <= 0:
        return 400, json.dumps({"detail": "Shares must be greater than 0"}).encode()
    if entry <= 0:
        return 400, json.dumps({"detail": "Entry price must be greater than 0"}).encode()

    now = datetime.now(timezone.utc).isoformat() + "Z"
    pos = _build_local_position(payload, now=now)
    store = _load_local_portfolio()
    holdings = [h for h in store.get("holdings", []) if h.get("ticker") != t]
    holdings.append(pos)
    store = {
        "holdings": holdings,
        "source": "manual",
        "updated_at": now,
        "count": len(holdings),
    }
    _save_local_portfolio(store)
    return 200, _encode_degraded(
        {
            "status": "added",
            "position": pos,
            "saved_locally": True,
            "broker_sync": "unavailable",
            "message": "Saved locally · Broker sync unavailable",
            "degraded": True,
        }
    )


def _degraded_live_backtest_post(body: bytes) -> tuple[int, bytes] | None:
    """Graceful POST /api/live/backtest while backend warms."""
    try:
        params = urllib.parse.parse_qs(body.decode("utf-8") if body else "")
    except Exception:
        params = {}
    ticker = (params.get("ticker") or ["AAPL"])[0]
    note = "backend importing — full backtest pending API warm-up"
    return 200, _encode_degraded(
        {
            "ticker": str(ticker).upper()[:12],
            "strategies": [],
            "equity_chart": {"bh": [], "strategy": [], "signals": []},
            "degraded": True,
            "trust": {"stale": True, "source": "instant-degraded", "reason": note},
        },
        reason=note,
    )


def _degraded_ai_narrative_post(body: bytes) -> tuple[int, bytes]:
    """Honest rule-based narrative while backend warms — narrative only, not authoritative."""
    note = "backend importing — full LLM narrative pending API warm-up"
    try:
        payload = json.loads(body.decode("utf-8") if body else "{}")
    except Exception:
        payload = {}
    regime = payload.get("regime_ctx") or {}
    top5 = payload.get("top_5") or []
    board_narrative = str(payload.get("narrative") or "").strip()

    trend = regime.get("trend") or regime.get("label") or "unknown"
    tradeability = regime.get("tradeability") or "WAIT"
    lines = [
        "Rule-based briefing (instant degraded — narrative only; does not affect "
        "ranking, sizing, or deploy gates).",
        f"Regime **{trend}**, tradeability **{tradeability}**.",
    ]
    if top5:
        preview = ", ".join(
            str(row.get("ticker") or "?") for row in top5[:5]
        )
        lines.append(f"Board preview: {preview}.")
    elif board_narrative:
        lines.append(board_narrative[:600])
    else:
        lines.append("No ranked setups on the board yet — observe until the funnel clears.")
    lines.append(
        f"{note} Retry Generate after /health shows mode=full for LLM-backed prose."
    )
    ai_narrative = "\n\n".join(lines)

    return 200, _encode_degraded(
        {
            "ai_narrative": ai_narrative,
            "provider": "stub",
            "model": "deterministic-instant",
            "configured": False,
            "message": note,
            "setup_hint": (
                "Set OPENAI_API_KEY or LOCAL_LLM_URL for richer prose after warm-up."
            ),
            "degraded": True,
            "research_only": True,
            "trust": {"stale": True, "source": "instant-degraded", "reason": note},
        },
        reason=note,
    )


def _parse_ibkr_json_body(body: bytes) -> dict:
    try:
        raw = json.loads(body.decode("utf-8") if body else "{}")
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _ibkr_mode_host_port(req: dict) -> tuple[str, str, int]:
    mode = str(req.get("mode") or "paper").lower()
    host = str(req.get("host") or "127.0.0.1").strip() or "127.0.0.1"
    port = req.get("port")
    if port is None:
        port = 7497 if mode == "paper" else 4001
    return mode, host, int(port)


def _degraded_ibkr_diagnosis(mode: str, host: str, port: int) -> dict:
    """Transport-only diagnosis while full API is still importing."""
    from src.services.ibkr_diagnosis import build_ibkr_diagnosis

    docker = Path("/.dockerenv").exists()
    return build_ibkr_diagnosis(
        mode=mode,
        host=host,
        port=port,
        docker=docker,
        ibapi_available=True,
        socket_connected=False,
        session_usable=False,
    )


def _degraded_ibkr_status_bytes(full_path: str) -> bytes:
    """GET /api/ibkr/status during instant degraded — TCP probe + honest copy."""
    parsed = urllib.parse.urlparse(full_path or "/api/ibkr/status")
    qs = urllib.parse.parse_qs(parsed.query)
    mode = str((qs.get("mode") or ["paper"])[0]).lower()
    host = str((qs.get("host") or ["127.0.0.1"])[0]).strip() or "127.0.0.1"
    port = int((qs.get("port") or [str(7497 if mode == "paper" else 4001)])[0])
    diagnosis = _degraded_ibkr_diagnosis(mode, host, port)
    reason = (
        "backend importing — IBKR status is transport probe only until /health mode=full"
    )
    readiness = {
        "full_handoff_ready": False,
        "session_usable": False,
        "bracket_status": "unavailable",
        "bracket_reason": "API still loading — use Connect when /health mode=full",
        "health": {
            "summary_label": diagnosis.get("label"),
            "session_status": "inactive",
            "degraded_reasons": [reason],
        },
        "portfolio_sync_reason": (
            "Broker sync unavailable until API finishes loading — local portfolio only"
        ),
    }
    payload = {
        "connected": False,
        "session_usable": False,
        "gateway_reachable": bool(diagnosis.get("gateway_reachable")),
        "api_port_open": bool(diagnosis.get("api_port_open")),
        "mode": mode,
        "host": host,
        "port": int(diagnosis.get("expected_port") or port),
        "monitoring_only": True,
        "readiness": readiness,
        "diagnosis": diagnosis,
        "health": readiness["health"],
        "health_label": diagnosis.get("label"),
        "health_label_short": diagnosis.get("short"),
        "backend_warming": True,
        "connect_blocked": True,
        "connect_blocked_reason": (
            "Wait for /health mode=full before POST /api/ibkr/connect"
        ),
    }
    return _encode_degraded(payload, reason=reason)


def _degraded_ibkr_ping_post(body: bytes) -> tuple[int, bytes]:
    req = _parse_ibkr_json_body(body)
    mode, host, port = _ibkr_mode_host_port(req)
    diagnosis = _degraded_ibkr_diagnosis(mode, host, port)
    api_open = bool(diagnosis.get("api_port_open"))
    note = "backend importing — session probe only until /health mode=full"
    message = diagnosis.get("label") or (
        f"Port {'open' if api_open else 'closed'} at {host}:{port}"
    )
    return 200, _encode_degraded(
        {
            "reachable": bool(diagnosis.get("gateway_reachable")),
            "api_port_open": api_open,
            "host": host,
            "port": port,
            "mode": mode,
            "message": message,
            "hint": diagnosis.get("hint"),
            "diagnosis": diagnosis,
            "probe_type": "tcp_instant_degraded",
            "backend_warming": True,
            "trust": {"stale": True, "source": "instant-degraded", "reason": note},
        },
        reason=note,
    )


def _degraded_ibkr_connect_post(body: bytes) -> tuple[int, bytes]:
    req = _parse_ibkr_json_body(body)
    mode, host, port = _ibkr_mode_host_port(req)
    diagnosis = _degraded_ibkr_diagnosis(mode, host, port)
    detail = (
        "Clarity Console API is still loading — wait for /health mode=full, then Connect."
    )
    if diagnosis.get("api_port_open"):
        detail += (
            " IB Gateway port is open; the API session starts only after the full backend loads."
        )
    elif diagnosis.get("short") == "OFFLINE":
        detail += " Start IB Gateway or TWS and enable Socket API (paper default port 7497)."
    payload = {
        "ok": False,
        "detail": detail,
        "error": detail,
        "degraded": True,
        "backend_warming": True,
        "diagnosis": diagnosis,
        "trust": {
            "stale": True,
            "source": "instant-degraded",
            "reason": "backend importing — connect blocked",
        },
    }
    return 503, _encode_degraded(payload, reason="backend importing — connect blocked")


def _degraded_portfolio_monitor_bytes() -> bytes:
    store = _load_local_portfolio()
    holdings = store.get("holdings") or []
    enriched = []
    total_cost = 0.0
    total_value = 0.0
    for h in holdings:
        entry = float(h.get("entry_price") or h.get("avg_cost") or 0)
        shares = float(h.get("shares") or 0)
        price = float(h.get("current_price") or entry)
        mv = round(price * shares, 2)
        cost = round(entry * shares, 2)
        total_cost += cost
        total_value += mv
        enriched.append(
            {
                **h,
                "current_price": price,
                "market_value": mv,
                "cost_basis": cost,
                "unrealized_pnl": round((price - entry) * shares, 2),
                "pnl_pct": round((price / entry - 1) * 100, 2) if entry else 0,
                "stop_defined": bool(h.get("stop_defined") or (h.get("stop_price") or 0) > 0),
                "quote_pending": bool(h.get("quote_pending", True)),
            }
        )
    return _encode_degraded(
        {
            "positions": enriched,
            "alerts": [],
            "summary": {
                "total_positions": len(enriched),
                "total_value": round(total_value, 2),
                "total_cost": round(total_cost, 2),
                "total_pnl": round(total_value - total_cost, 2),
                "total_pnl_pct": (
                    round((total_value / total_cost - 1) * 100, 2) if total_cost else 0
                ),
            },
            "degraded": True,
            "source": "instant-local",
        }
    )


def _stale_quant_intelligence_bytes(path: str, reason: str) -> bytes | None:
    """Research-only quant / algo stubs while backend warms."""
    try:
        from urllib.parse import parse_qs, urlparse

        from src.services.cost_adjusted_ranker import build_cost_rank_context
        from src.services.drawdown_sizer import build_drawdown_sizer_context
        from src.services.execution_analytics import build_execution_analytics
        from src.services.factor_exposure import build_factor_exposure
        from src.services.strategy_allocator import build_allocator_context
        from src.services.strategy_curve_health import build_strategy_curve_context
        from src.services.strategy_validity import build_strategy_validity_context

        parsed = urlparse(path)
        qs = parse_qs(parsed.query)
        ticker = (qs.get("ticker") or ["AAPL"])[0].upper()
        route = parsed.path.rstrip("/").split("/")[-1]
        strategy_id = (qs.get("strategy_id") or ["momentum_breakout_v2"])[0]
        raw_score = float((qs.get("raw_score") or ["7.0"])[0])
        tradeability = (qs.get("tradeability") or ["WAIT"])[0]
        builders = {
            "strategy-health": lambda: build_strategy_curve_context(
                ticker, strategy_id=strategy_id, degraded=True
            ),
            "cost-ranked": lambda: build_cost_rank_context(
                ticker,
                raw_score=raw_score,
                tradeability=tradeability,
                degraded=True,
            ),
            "sleeve-allocation": lambda: build_allocator_context(degraded=True),
            "execution-analytics": lambda: build_execution_analytics(degraded=True),
            "factor-exposure": lambda: build_factor_exposure(ticker, degraded=True),
            "strategy-validity": lambda: build_strategy_validity_context(
                strategy_id, degraded=True
            ),
            "drawdown-sizing": lambda: build_drawdown_sizer_context(
                research_only=True, degraded=True
            ),
        }
        build = builders.get(route)
        if not build:
            return None
        payload = build()
        payload["instant_degraded"] = True
        payload["degraded_reason"] = reason
        payload["research_only"] = True
        return _encode_degraded(payload, reason=reason)
    except Exception:
        return None


def _stale_opportunity_intelligence_bytes(path: str, reason: str) -> bytes | None:
    """Research-only opportunity intel while backend warms."""
    try:
        from urllib.parse import parse_qs, urlparse

        from src.services.event_noise_filter import build_event_risk_context
        from src.services.insider_tracker import build_insider_context
        from src.services.institutional_13f import build_institutional_context
        from src.services.strategy_curve_health import build_strategy_curve_context

        parsed = urlparse(path)
        qs = parse_qs(parsed.query)
        ticker = (qs.get("ticker") or ["AAPL"])[0].upper()
        route = parsed.path.rstrip("/").split("/")[-1]
        builders = {
            "insider": lambda: build_insider_context(ticker, degraded=True),
            "institutional": lambda: build_institutional_context(ticker, degraded=True),
            "events": lambda: build_event_risk_context(ticker, degraded=True),
            "strategy-health": lambda: build_strategy_curve_context(
                ticker, degraded=True
            ),
        }
        build = builders.get(route)
        if not build:
            return None
        payload = build()
        payload["instant_degraded"] = True
        payload["degraded_reason"] = reason
        return _encode_degraded(payload, reason=reason)
    except Exception:
        return None


def _degraded_response(path_only: str, reason: str, full_path: str = "") -> bytes | None:
    """Disk/brief fallbacks for dashboard-critical endpoints."""
    path = full_path or path_only
    if path_only.startswith("/api/v7/intelligence/"):
        body = _stale_opportunity_intelligence_bytes(path, reason)
        if body is not None:
            return body
    if path_only.startswith("/api/v7/quant/"):
        body = _stale_quant_intelligence_bytes(path, reason)
        if body is not None:
            return body
    if path_only == "/api/v7/today":
        return _stale_today_bytes(reason)
    if path_only == "/api/ops/cc-header":
        return _stale_cc_header_bytes()
    if path_only == "/api/ops/error-log":
        return _stale_ops_error_log_bytes(reason)
    if path_only == "/api/ops/changelog":
        return _stale_ops_changelog_bytes(reason)
    if path_only in (
        "/api/v7/playbook/ranked/snapshot",
        "/api/v7/playbook/ranked",
    ):
        return _stale_ranked_bytes(reason)
    if path_only == "/api/v7/flow-decision":
        return _stale_flow_bytes()
    if path_only == "/api/v7/playbook/scanners":
        return _stale_scanners_bytes()
    if path_only == "/api/v7/playbook/no-trade":
        return _stale_no_trade_bytes(reason)
    if path_only == "/api/v7/backtest-lab":
        return _stale_backtest_lab_bytes(path, reason)
    if path_only.startswith("/api/fund-lab/"):
        return _stale_fund_lab_bytes(reason)
    if path_only == "/api/v7/ops-console":
        return _stale_ops_console_bytes(reason)
    if path_only == "/api/v7/rs-decision":
        return _stale_rs_decision_bytes(reason)
    if path_only.startswith("/api/live/market"):
        return _load_snapshot()
    if path_only.startswith("/api/v7/stock-intel/"):
        body = _stale_stock_intel_bytes(path, reason)
        if body is not None:
            return body
    if path_only.startswith("/api/live/dossier/"):
        # Legacy chart/peers may call live dossier; reuse core intel envelope.
        sym = path_only.rsplit("/", 1)[-1].strip().upper()
        if sym:
            return _stale_stock_intel_bytes(
                f"/api/v7/stock-intel/{sym}?lite=true", reason
            )
    if path_only == "/api/portfolio/monitor":
        return _degraded_portfolio_monitor_bytes()
    if path_only == "/api/ibkr/status":
        return _degraded_ibkr_status_bytes(path)
    return None


def _stale_playbook_ranked_bytes(path: str) -> bytes:
    """Playbook board during cold start — disk snapshot or brief (no src import)."""
    del path
    return _stale_ranked_bytes("backend importing — full API still loading")


def _stale_cc_header_bytes() -> bytes:
    """Minimal cc-header for trust strip while uvicorn is still importing."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    brief = _load_latest_brief()
    brief_ok = bool(brief and (brief.get("actionable") or brief.get("watch")))
    payload = {
        "as_of": now.isoformat() + "Z",
        "healthy": False,
        "display_mode": "LOADING",
        "trust_mode": "PAPER",
        "engine": {
            "dry_run": True,
            "running": False,
            "circuit_breaker": False,
            "circuit_breaker_reason": "",
        },
        "freshness": {"worst_tier": "STALE", "stale": True},
        "brief_status": {
            "ok": brief_ok,
            "latest": brief.get("date") if brief_ok else None,
        },
        "risk_alerts": {"count": 0, "by_severity": {}},
        "ibkr": {
            "connected": False,
            "session_usable": False,
            "mode": "paper",
            "gateway_reachable": False,
            "monitoring_only": True,
            "health_label": "Backend loading",
        },
        "pills": {"data": "STALE", "brief": "STALE", "alerts": 0},
        "components": {
            "market_data": brief_ok,
            "regime_router": False,
            "broker": False,
        },
        "providers": {
            "yfinance": brief_ok,
            "regime_router": False,
            "alpaca": {"configured": False, "connected": False, "paper": True},
        },
        "degraded": True,
        "instant_degraded": True,
        "degraded_banner": DEGRADED_BANNER,
        "trust": {"stale": True, "source": "instant-degraded", "reason": "backend importing"},
    }
    return _encode_degraded(payload, reason="backend importing")


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves dashboard instantly; proxies API calls to backend once ready."""

    def do_GET(self):
        self._safe_handle()

    def do_POST(self):
        self._safe_handle()

    def do_PUT(self):
        self._safe_handle()

    def do_DELETE(self):
        self._safe_handle()

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self._cors_headers()
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _safe_handle(self):
        try:
            self._handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")

    def _handle(self):
        global _backend_ready

        # Dashboard — always local
        if self.path in ("/", ""):
            use_gzip = "gzip" in self.headers.get("Accept-Encoding", "").lower()
            body = TEMPLATE_GZIP if use_gzip else TEMPLATE_BYTES
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=30")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        # Health — local fast path (mode=full only when our API responds on :8001)
        if self.path in ("/health", "/api/health"):
            listening = _backend_healthy()
            health_payload = {
                "status": "ok",
                "version": "9.0.0",
                "uptime_seconds": round(time.time() - _start, 1),
                "mode": "full" if listening else "loading",
                "phase9_engines": {
                    "loaded": listening,
                    "components": (
                        [
                            "StructureDetector",
                            "EntryQuality",
                            "BreakoutMonitor",
                            "PortfolioGate",
                            "EarningsCalendar",
                            "FundamentalData",
                            "DecisionJournal",
                        ]
                        if listening
                        else []
                    ),
                },
            }
            if not listening:
                health_payload = _stamp_instant_degraded(
                    {**health_payload, "degraded": True, "display_mode": "LOADING"},
                    reason="backend importing — full API still loading",
                )
            self._send_json(json.dumps(health_payload).encode())
            return

        # Static files — serve locally
        if self.path.startswith("/static/"):
            fpath = Path("src/api") / self.path.lstrip("/")
            if fpath.is_file():
                self.send_response(200)
                ct = {
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                    ".svg": "image/svg+xml",
                    ".json": "application/json",
                    ".ico": "image/x-icon",
                }.get(fpath.suffix, "application/octet-stream")
                self.send_header("Content-Type", ct)
                self.end_headers()
                self.wfile.write(fpath.read_bytes())
            else:
                self._json_error(404, "Static file not found")
            return

        path_only = self.path.split("?", 1)[0]
        degrade_reason = "backend importing — full API still loading"

        if _mark_backend_ready():
            if self._proxy():
                return
            degrade_reason = "backend proxy failed — serving cached data"

        if self.command == "POST":
            cl = self.headers.get("Content-Length")
            raw = self.rfile.read(int(cl)) if cl else b""
            if path_only == "/api/portfolio/position":
                post_result = _degraded_portfolio_position_post(raw)
                if post_result is not None:
                    status, post_body = post_result
                    self._send_json(post_body, status=status)
                    return
            if path_only == "/api/live/backtest":
                bt_result = _degraded_live_backtest_post(raw)
                if bt_result is not None:
                    status, bt_body = bt_result
                    self._send_json(bt_body, status=status)
                    return
            if path_only == "/api/v7/today/ai-narrative":
                status, post_body = _degraded_ai_narrative_post(raw)
                self._send_json(post_body, status=status)
                return
            if path_only == "/api/ibkr/connect":
                status, ibkr_body = _degraded_ibkr_connect_post(raw)
                self._send_json(ibkr_body, status=status)
                return
            if path_only == "/api/ibkr/ping":
                status, ibkr_body = _degraded_ibkr_ping_post(raw)
                self._send_json(ibkr_body, status=status)
                return

        body = _degraded_response(path_only, degrade_reason, self.path)
        if body is None and path_only in (
            "/api/v7/playbook/ranked",
            "/api/v7/playbook/ranked/snapshot",
        ):
            body = _stale_playbook_ranked_bytes(self.path)
        if body is not None:
            self._send_json(body)
            return
        if self.path in ("/healthz", "/readyz"):
            self._send_json(
                json.dumps(
                    {
                        "status": "ok",
                        "alive": True,
                        "ready": _backend_healthy(),
                        "mode": "loading" if not _backend_healthy() else "full",
                        "uptime_seconds": round(time.time() - _start, 1),
                    }
                ).encode()
            )
            return
        self._json_error(503, "API warming up — retry in 3s")

    def _send_json(self, body: bytes, status: int = 200):
        body = _maybe_stamp_degraded_body(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self) -> bool:
        """Forward request to uvicorn backend on BACKEND_PORT. True if response sent."""
        url = f"http://127.0.0.1:{BACKEND_PORT}{self.path}"
        try:
            body = None
            cl = self.headers.get("Content-Length")
            if cl:
                body = self.rfile.read(int(cl))

            req = urllib.request.Request(url, data=body, method=self.command)
            req.add_header(
                "Content-Type", self.headers.get("Content-Type", "application/json")
            )
            api_key = _dashboard_api_key(self.headers.get("X-API-Key"))
            if api_key:
                req.add_header("X-API-Key", api_key)

            _timeout = _proxy_timeout(self.path)
            with urllib.request.urlopen(req, timeout=_timeout) as resp:
                status = resp.status
                data = resp.read()
                ct = resp.headers.get("Content-Type", "application/json")

            if status >= 500 and not self.path.split("?", 1)[0].startswith(
                "/api/ibkr/"
            ):
                return False
            self.send_response(status)
            self.send_header("Content-Type", ct)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
            return True
        except urllib.error.HTTPError as e:
            if e.code >= 500 and not self.path.split("?", 1)[0].startswith(
                "/api/ibkr/"
            ):
                return False
            body = b""
            try:
                body = e.read()
            except Exception:
                body = json.dumps({"error": str(e)}).encode()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return True
        except Exception:
            return False

    def _json_error(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())

    def log_message(self, fmt, *args):
        pass  # quiet


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _kill_port(port):
    """Terminate other processes on *port*; never signal this PID."""
    my_pid = os.getpid()
    try:
        r = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return
    for token in (r.stdout or "").strip().split():
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid == my_pid:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def _pid_alive(pid: int) -> bool:
    """True if pid exists (signal 0 only — no kill)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire_single_instance() -> bool:
    """Prevent overlapping starts from kill -9'ing an importing peer."""
    lock_path = Path("/tmp/cc_instant.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        stale_pid = 0
        try:
            stale_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            stale_pid = 0
        if stale_pid and not _pid_alive(stale_pid):
            print(
                f"[instant] Reclaiming stale lock (pid {stale_pid} dead)",
                flush=True,
            )
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            return _acquire_single_instance()
        print(
            "[instant] Another CC server is already running — exit without killing it",
            flush=True,
        )
        return False
    fd.write(str(os.getpid()))
    fd.flush()
    # Keep fd open for process lifetime (lock released on exit)
    globals()["_INSTANCE_LOCK_FD"] = fd
    return True


def _backend_healthy() -> bool:
    """True only when our FastAPI app answers /api/health (not a stray listener)."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{BACKEND_PORT}/api/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status")
        if status not in ("ok", "healthy"):
            return False
        return bool(data.get("version")) or bool(data.get("components"))
    except Exception:
        return False


def _mark_backend_ready() -> bool:
    """Set ready flag once our API health check passes."""
    global _backend_ready
    if _backend_ready:
        return True
    if _backend_healthy():
        _backend_ready = True
    return _backend_ready


def _run_backend():
    """Import FastAPI app and start uvicorn IN-PROCESS (no subprocess).

    This avoids the macOS Gatekeeper double-scan that causes 5-10 min hangs
    when a subprocess re-imports pydantic/numpy .so files.
    """
    if os.environ.get("CC_INSTANT_NO_BACKEND") == "1":
        print("[backend] skipped (CC_INSTANT_NO_BACKEND)", flush=True)
        return
    global _backend_ready
    try:
        print("[backend] importing src.api.main (child process)...", flush=True)
        t0 = time.time()

        # Heavy import happens HERE in this thread — same process,
        # so Gatekeeper only scans .so files once.
        import uvicorn
        from src.api.main import app as _app  # noqa: F811

        elapsed = time.time() - t0
        print(
            f"[backend] import done in {elapsed:.0f}s — starting uvicorn...", flush=True
        )

        def _mark_ready_on_startup():
            global _backend_ready
            _backend_ready = True
            print("[backend] uvicorn listening — proxy enabled", flush=True)

        @_app.on_event("startup")
        async def _cc_backend_startup():
            _mark_ready_on_startup()

        # Run uvicorn in this child process (blocking)
        _uvicorn_kw: dict = {
            "host": "127.0.0.1",
            "port": BACKEND_PORT,
            "timeout_keep_alive": 5,
            "log_level": "warning",
        }
        # Dev: no concurrency cap — macro-intel + verify burst otherwise get 503
        if os.getenv("CC_ENV") != "development":
            _uvicorn_kw["limit_concurrency"] = 20
        uvicorn.run(_app, **_uvicorn_kw)
    except Exception as e:
        print(f"[backend] FATAL: {e}", flush=True)
        import traceback

        traceback.print_exc()
    sys.exit(1)


def _spawn_backend() -> subprocess.Popen:
    """Start backend in a separate interpreter (avoids multiprocessing spawn taking down :8000)."""
    env = os.environ.copy()
    env["CC_INSTANT_BACKEND_CHILD"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", str(Path(__file__).resolve())],
        env=env,
        cwd=str(Path(__file__).resolve().parent),
    )
    print(f"[backend] child started pid={proc.pid}", flush=True)
    return proc


def _supervise_backend(proc: subprocess.Popen) -> None:
    """Log backend child exit; restart without stopping the instant server."""
    while True:
        try:
            code = proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            continue
        print(
            f"[backend] child exited (code={code!r}) — instant server stays up; restarting backend in 3s",
            flush=True,
        )
        global _backend_ready
        _backend_ready = False
        time.sleep(3)
        proc = _spawn_backend()


def _log_main_exit() -> None:
    print(f"[instant] main process exiting pid={os.getpid()}", flush=True)


def main() -> None:
    if not _acquire_single_instance():
        sys.exit(0)

    # Clear stale listeners from a crashed prior instance (we hold the singleton lock)
    _kill_port(PORT)
    _kill_port(BACKEND_PORT)
    time.sleep(0.5)

    atexit.register(_log_main_exit)

    # Backend import + uvicorn in a child interpreter so heavy native imports cannot
    # take down the instant HTTP server (multiprocessing.spawn also killed :8000 ~30–60s).
    if os.environ.get("CC_INSTANT_NO_BACKEND") == "1":
        print("[backend] skipped (CC_INSTANT_NO_BACKEND)", flush=True)
        backend_proc = None
    else:
        backend_proc = _spawn_backend()
        threading.Thread(
            target=_supervise_backend,
            args=(backend_proc,),
            name="cc-backend-supervisor",
            daemon=True,
        ).start()

    server = ReusableTCPServer(("0.0.0.0", PORT), Handler)
    print(f"CC Dashboard ready at http://localhost:{PORT}", flush=True)
    print("   API importing in background...", flush=True)
    try:
        while True:
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[instant] serve_forever error: {e!r} — retrying in 1s", flush=True)
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
        if backend_proc is not None and backend_proc.is_alive():
            backend_proc.terminate()
            backend_proc.join(timeout=5)


if __name__ == "__main__":
    if os.environ.get("CC_INSTANT_BACKEND_CHILD") == "1":
        _run_backend()
    else:
        main()
