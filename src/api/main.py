"""
TradingAI Bot - FastAPI Application
REST API for accessing signals, reports, and system status.

Features:
- RESTful API for signals and market data
- Rate limiting to prevent abuse
- API key authentication
- Comprehensive error handling
- Health checks with component status
"""

import asyncio
import logging
import math
import os
from contextlib import asynccontextmanager
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import get_settings
from src.core.models import (
    ChangeItem,
    DataQualityReport,
    DeltaSnapshot,
    RegimeScoreboard,
    ScenarioPlan,
    Signal,
)
from src.core.risk_limits import BACKTEST_DEFAULTS, RISK, SIGNAL_THRESHOLDS
from src.core.telemetry import telemetry
from src.core.version import APP_VERSION, PRODUCT_NAME
from src.api.live_analytics import compute_4layer_confidence as _compute_4layer_confidence

# ── Extracted services (back-compat shims) ──
from src.services.indicators import (
    compute_indicators as _compute_indicators,
    compute_rs_vs_benchmark as _compute_rs_vs_benchmark,
    rolling_mean as _rolling_mean,
)
from src.services.calendar_service import (
    is_us_market_holiday as _is_us_market_holiday,
    us_market_holidays as _compute_us_market_holidays,
    is_us_market_open,
    next_trading_day,
)

# ── Phase 9 engine imports ──
try:
    from src.engines.breakout_monitor import BreakoutMonitor
    from src.engines.decision_persistence import get_expert_store, get_journal
    from src.engines.earnings_calendar import (
        get_days_to_earnings,
        get_earnings_info,
        is_in_blackout,
    )
    from src.engines.entry_quality import EntryQualityEngine
    from src.engines.fundamental_data import get_fundamentals
    from src.engines.portfolio_gate import PortfolioGate
    from src.engines.structure_detector import StructureDetector

    _P9_ENGINES = True
except ImportError:
    _P9_ENGINES = False

# v6 optional imports (graceful fallback)
try:
    from src.notifications.report_generator import (
        build_eod_scorecard,
        build_morning_memo,
        build_regime_snapshot,
        build_signal_card,
        embeds_to_markdown,
    )

    _HAS_REPORT_GEN = True
except ImportError:
    _HAS_REPORT_GEN = False

settings = get_settings()

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ===== Rate Limiting =====


class RateLimiter:
    """Simple in-memory rate limiter with automatic cleanup."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Cleanup every 5 minutes

    async def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed."""
        async with self._lock:
            now = time.time()
            minute_ago = now - 60

            # Clean old requests for this client
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > minute_ago
            ]

            # Periodic global cleanup to prevent memory leaks
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale_clients(now)

            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False

            self.requests[client_id].append(now)
            return True

    def _cleanup_stale_clients(self, now: float):
        """Remove clients with no recent requests to prevent memory leak."""
        minute_ago = now - 60
        stale_clients = [
            client_id
            for client_id, timestamps in self.requests.items()
            if not timestamps or max(timestamps) < minute_ago
        ]
        for client_id in stale_clients:
            del self.requests[client_id]

        self._last_cleanup = now
        if stale_clients:
            logger.debug(f"Cleaned up {len(stale_clients)} stale rate limit entries")

    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        now = time.time()
        minute_ago = now - 60
        recent = [t for t in self.requests.get(client_id, []) if t > minute_ago]
        return max(0, self.requests_per_minute - len(recent))


_dev_rpm = 300 if os.getenv("CC_ENV") == "development" else 120
rate_limiter = RateLimiter(requests_per_minute=_dev_rpm)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    async def dispatch(self, request: Request, call_next):
        # Get client identifier (API key or IP)
        _client_host = request.client.host if request.client else "127.0.0.1"
        client_id = request.headers.get("x-api-key") or _client_host

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        if not await rate_limiter.is_allowed(client_id):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": 60,
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        remaining = rate_limiter.get_remaining(client_id)
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


# Create FastAPI app
app = FastAPI(
    title="TradingAI Bot API",
    description="""
# TradingAI Bot API — v6 Pro Desk

Institutional-grade market intelligence system providing:
- **Regime Scoreboard** — live risk/trend/vol regime with strategy playbook
- **Delta Deck** — what changed today (index, volatility, breadth)
- **Signal Cards** — v6 signals with approval, evidence, scenario plans
- **Data Quality** — pipeline health, staleness, gap detection
- Real-time trading signals · Market analysis · Portfolio management

## v6 Pro Desk Endpoints
- `GET /api/v6/scoreboard` — Regime scoreboard + risk budgets
- `GET /api/v6/delta` — Daily delta snapshot
- `GET /api/v6/regime-snapshot` — Formatted regime report
- `GET /api/v6/data-quality` — Data pipeline health
- `GET /api/v6/signal-card/{ticker}` — v6 signal card

## Authentication
Use the `X-API-Key` header for authenticated endpoints.

## Rate Limits
- 120 requests per minute per API key
- Rate limit headers included in responses
    """,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "Health check endpoints"},
        {"name": "signals", "description": "Trading signal operations"},
        {"name": "reports", "description": "Market reports and analysis"},
        {"name": "portfolio", "description": "Portfolio management"},
    ],
)

# Add middleware
app.add_middleware(RateLimitMiddleware)
# CORS: explicit origins only — never wildcard with credentials
_CORS_ORIGINS_ENV = os.environ.get("CORS_ORIGINS", "")
_CORS_ORIGINS = (
    [o.strip() for o in _CORS_ORIGINS_ENV.split(",") if o.strip()]
    if _CORS_ORIGINS_ENV
    else (
        ["https://cheafi.github.io"]
        if settings.environment == "production"
        else ["http://localhost:8000", "http://127.0.0.1:8000"]
    )
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

# Mount static files for PWA
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "icons").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ═══════════════════════════════════════════════════════════════════
# SINGLETON WIRING — one engine, one regime, one market-data service
# ═══════════════════════════════════════════════════════════════════


def _init_shared_services():
    """Create shared singletons once at import time.

    Stored on ``app.state`` so every endpoint, bot, and background
    task reads the same cached objects — no ad-hoc instantiation.
    """
    from src.engines.regime_router import RegimeRouter
    from src.services.market_data import get_market_data_service

    app.state.market_data = get_market_data_service()
    app.state.regime_router = RegimeRouter()
    app.state.regime_cache = None  # populated on first fetch
    app.state.regime_cache_ts = 0.0  # monotonic timestamp

    # Engine singleton (dry_run) — lazy to avoid heavy import at startup
    app.state.engine = None
    app.state.engine_init_done = False

    # ── P2: Stateful engine singletons — lazy, state persists across requests ──
    app.state.expert_council = None
    app.state.expert_council_init = False
    app.state.learning_loop = None
    app.state.learning_loop_init = False
    app.state.meta_ensemble = None
    app.state.meta_ensemble_init = False

    # ── P3/P4: Scanner service wired after SCAN_WATCHLIST is defined ──
    app.state.scanner_service = None  # set below after ScannerService is importable
    app.state.scan_signals = None  # set to _scan_live_signals shim below
    app.state.scan_watchlist = []  # set below after _SCAN_WATCHLIST is defined
    from src.api.live_state import LIVE_INDICES, LIVE_SECTORS

    app.state.live_indices = LIVE_INDICES
    app.state.live_sectors = LIVE_SECTORS
    logger.info("[Singleton] shared services registered on app.state")


def _get_expert_council():
    """Lazy-init ExpertCouncil singleton — state persists across requests."""
    if not app.state.expert_council_init:
        try:
            from src.engines.expert_council import ExpertCouncil

            app.state.expert_council = ExpertCouncil()
            logger.info("[Singleton] ExpertCouncil created")
        except Exception as exc:
            logger.warning("[Singleton] ExpertCouncil init failed: %s", exc)
            app.state.expert_council = None
        app.state.expert_council_init = True
    return app.state.expert_council


def _get_learning_loop():
    """Lazy-init LearningLoopPipeline singleton."""
    if not app.state.learning_loop_init:
        try:
            from src.engines.learning_loop import LearningLoopPipeline

            app.state.learning_loop = LearningLoopPipeline()
            logger.info("[Singleton] LearningLoopPipeline created")
        except Exception as exc:
            logger.warning("[Singleton] LearningLoopPipeline init failed: %s", exc)
            app.state.learning_loop = None
        app.state.learning_loop_init = True
    return app.state.learning_loop


def _get_meta_ensemble():
    """Lazy-init MetaEnsemble singleton."""
    if not app.state.meta_ensemble_init:
        try:
            from src.engines.meta_ensemble import MetaEnsemble

            app.state.meta_ensemble = MetaEnsemble()
            logger.info("[Singleton] MetaEnsemble created")
        except Exception as exc:
            logger.warning("[Singleton] MetaEnsemble init failed: %s", exc)
            app.state.meta_ensemble = None
        app.state.meta_ensemble_init = True
    return app.state.meta_ensemble


def _get_engine():
    """Lazy-init the shared AutoTradingEngine singleton."""
    if not app.state.engine_init_done:
        try:
            from src.engines.auto_trading_engine import AutoTradingEngine

            engine = AutoTradingEngine(dry_run=True)
            # Wire market data service into engine + context assembler
            engine.market_data = app.state.market_data
            if hasattr(engine, "context_assembler"):
                engine.context_assembler.market_data = app.state.market_data
            app.state.engine = engine
            logger.info("[Singleton] AutoTradingEngine created")
        except Exception as exc:
            logger.warning(f"[Singleton] engine init failed: {exc}")
            app.state.engine = None
        app.state.engine_init_done = True
    return app.state.engine


def _sanitize_for_json(obj):
    """Recursively replace NaN / Inf floats with None for JSON compliance."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


async def _get_regime():
    """Return cached RegimeState, refreshing every 60 s.

    Single source of truth — all surfaces read from here.
    """
    import time as _time

    now = _time.monotonic()
    if app.state.regime_cache and (now - app.state.regime_cache_ts) < 60:
        return app.state.regime_cache

    try:
        mkt = await app.state.market_data.get_market_state()
        state = app.state.regime_router.classify(mkt)
        app.state.regime_cache = state
        app.state.regime_cache_ts = now
        return state
    except Exception as exc:
        logger.warning(f"[Regime] classify error: {exc}")
        if app.state.regime_cache:
            return app.state.regime_cache
        from src.engines.regime_router import RegimeState

        return RegimeState()


_init_shared_services()


# ===== Dashboard Routes =====


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    """Serve the main dashboard."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/signals/explorer", response_class=HTMLResponse, include_in_schema=False)
async def signal_explorer(request: Request):
    """Serve the Signal Explorer page."""
    return templates.TemplateResponse(request, "signal_explorer.html")


@app.get("/api/dashboard", tags=["dashboard"])
async def get_dashboard_data():
    """Get real-time dashboard data for the web UI.

    Sprint 26: reads live data from AutoTradingEngine's cached
    state instead of returning hardcoded placeholders.
    """
    from datetime import datetime

    # Try to load engine state from the singleton
    state: Dict[str, Any] = {}
    try:
        engine = _get_engine()
        if engine and hasattr(engine, "get_cached_state"):
            state = engine.get_cached_state()
    except Exception:
        pass

    # Extract real values with safe defaults
    mkt = state.get("market_state", {})
    cb = state.get("circuit_breaker", {})
    recs = state.get("recommendations", [])
    equity = state.get("equity", 0)

    # Build top signals from live recommendations
    top_signals = []
    buy_count = 0
    sell_count = 0
    for r in recs[:10]:
        direction = r.get("direction", "LONG")
        if direction == "LONG":
            buy_count += 1
        else:
            sell_count += 1
        top_signals.append(
            {
                "ticker": r.get("ticker", "???"),
                "direction": direction,
                "score": round(r.get("composite_score", 0) * 10, 1),
                "strategy": r.get("strategy_id", "unknown"),
                "confidence": r.get("signal_confidence", 0),
            }
        )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "totalPnL": cb.get("daily_pnl", 0),
            "todayPnL": cb.get("daily_pnl", 0),
            "winRate": round(state.get("win_rate", 0), 1),
            "activeSignals": len(recs),
            "buySignals": buy_count,
            "sellSignals": sell_count,
            "portfolioValue": equity,
            "openPositions": state.get("open_positions", 0),
            "totalTrades": state.get("total_trades", 0),
            "cycleCount": state.get("cycle_count", 0),
            "dryRun": state.get("dry_run", True),
        },
        "regime": state.get("regime", {}),
        "markets": {
            "VIX": {"value": mkt.get("vix", 0)},
            "SPY_20d": {"value": mkt.get("spy_return_20d", 0)},
            "Breadth": {"value": mkt.get("breadth_pct", 0)},
            "RealVol": {"value": mkt.get("realized_vol_20d", 0)},
            "dataSource": mkt.get("data_source", "unknown"),
        },
        "circuitBreaker": {
            "triggered": cb.get("triggered", False),
            "reason": cb.get("reason", ""),
            "consecutiveLosses": cb.get("consecutive_losses", 0),
        },
        "topSignals": top_signals,
        "signalsToday": state.get("signals_today", 0),
        "tradesToday": state.get("trades_today", 0),
        "leaderboard": state.get("leaderboard", {}),
    }


# ===== Exception Handlers =====


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with clear messages."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "detail": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": (
                "An unexpected error occurred"
                if settings.environment == "production"
                else str(exc)
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ===== Authentication =====

# Canonical definitions live in src/api/deps.py; re-export here for backward compat.
from src.api.deps import (  # noqa: E402, F401
    optional_api_key,
    validate_ticker,
    verify_api_key,
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(
        ..., description="Service status: healthy, degraded, or unhealthy"
    )
    timestamp: str = Field(..., description="ISO timestamp of health check")
    version: str = Field(..., description="API version")
    database: Optional[str] = Field(None, description="Database connection status")
    redis: Optional[str] = Field(None, description="Redis connection status")
    uptime_seconds: Optional[float] = Field(
        None, description="Service uptime in seconds"
    )
    phase9_engines: Optional[dict] = Field(None, description="Phase 9 engine status")


class SignalListResponse(BaseModel):
    """Signal list response model."""

    signals: List[Signal] = Field(..., description="List of trading signals")
    total: int = Field(..., description="Total number of signals matching criteria")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Number of signals per page")
    generated_at: str = Field(..., description="Response generation timestamp")


class MarketReportResponse(BaseModel):
    """Market report response model."""

    report_date: str
    overview: dict
    sectors: dict
    signals: List[Signal]
    news_summary: str
    generated_at: str


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    timestamp: str = Field(..., description="Error timestamp")


# Track startup time for uptime calculation
startup_time = datetime.now(timezone.utc)


# ── Breakout Monitor background loop ──
_breakout_monitor_task = None


async def _breakout_monitor_loop():
    """Background task: update breakout monitor every 30 minutes during market hours."""
    import numpy as np

    await asyncio.sleep(60)  # wait for app to fully start
    bm = BreakoutMonitor() if _P9_ENGINES else None
    if bm is None:
        return
    bm.load()
    logger.info(
        "[BreakoutMonitor] Background loop started — %d active", len(bm.get_active())
    )

    while True:
        try:
            await asyncio.sleep(1800)  # 30 minutes
            if not bm.get_active():
                continue
            mds = app.state.market_data
            for rec in list(bm.get_active()):
                try:
                    hist = await mds.get_history(rec.ticker, period="5d", interval="1d")
                    if hist is None or hist.empty:
                        continue
                    c_col = "Close" if "Close" in hist.columns else "close"
                    v_col = "Volume" if "Volume" in hist.columns else "volume"
                    cur_close = float(hist[c_col].iloc[-1])
                    cur_vol = float(hist[v_col].iloc[-1])
                    avg_vol = (
                        float(np.mean(hist[v_col].values[-5:]))
                        if len(hist) >= 5
                        else cur_vol
                    )
                    result = bm.update(rec.ticker, cur_close, cur_vol, avg_vol)
                    if result and result.status.value in ("failed", "rejected"):
                        logger.info(
                            "[BreakoutMonitor] %s → %s: %s",
                            rec.ticker,
                            result.status.value,
                            result.failure_reasons,
                        )
                except Exception as e:
                    logger.debug("[BreakoutMonitor] %s update error: %s", rec.ticker, e)
            bm.save()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("[BreakoutMonitor] loop error: %s", e)
            await asyncio.sleep(300)


async def _startup_prewarm():
    """Pre-warm market data cache at startup so first user request is instant.

    Fetches all symbols used by /api/live/market in parallel, then warms
    the regime cache. Runs concurrently — server is ready before this finishes,
    but the cache will be hot within ~3s of boot.
    """
    await asyncio.sleep(0.5)  # let uvicorn finish binding the port first

    # Collect all symbols used by /api/live/market (defined later in file)
    _prewarm_symbols = [
        "SPY",
        "QQQ",
        "IWM",
        "DIA",  # indices
        "^VIX",
        "GLD",
        "TLT",
        "BTC-USD",  # macro
        "ETH-USD",
        "USO",
        "XLK",
        "XLF",
        "XLV",
        "XLE",
        "XLI",  # sectors
        "XLY",
        "XLP",
        "XLU",
        "XLRE",
        "XLC",
        "XLB",
        "^N225",
        "^HSI",
        "^KS11",  # asia (skip slow ones)
    ]

    mds = app.state.market_data
    t0 = __import__("time").time()
    logger.info("[Prewarm] Fetching %d symbols in parallel…", len(_prewarm_symbols))

    # Parallel fetch — all symbols at once
    await asyncio.gather(
        *[mds.get_quote(sym) for sym in _prewarm_symbols],
        return_exceptions=True,
    )
    elapsed = __import__("time").time() - t0
    logger.info("[Prewarm] Market data cache ready in %.1fs", elapsed)

    # Also warm regime cache so first tab load skips the yfinance round-trip
    try:
        mkt = await mds.get_market_state()
        state = app.state.regime_router.classify(mkt)
        app.state.regime_cache = state
        app.state.regime_cache_ts = __import__("time").monotonic()
        logger.info("[Prewarm] Regime cache warm: %s", getattr(state, "regime", "?"))
    except Exception as exc:
        logger.warning("[Prewarm] Regime warm failed (non-fatal): %s", exc)

    # Finally: call live_market() to populate the full overview cache so the
    # first user request returns data immediately instead of hitting the 503 path.
    try:
        from src.api.live_state import set_prewarm_done
        from src.api.routers.live_market import warm_market_overview

        set_prewarm_done(True)
        await warm_market_overview(app)
        logger.info("[Prewarm] Overview cache populated — dashboard ready")
    except Exception as exc:
        logger.warning("[Prewarm] Overview cache fill failed (non-fatal): %s", exc)


@asynccontextmanager
async def _lifespan(app):  # noqa: ARG001
    global _breakout_monitor_task
    # Seed self-learning default files (no-op if already exist)
    try:
        from src.engines.self_learning import (
            _DEFAULT_FUND_WEIGHTS,
            _DEFAULT_REGIME_PARAMS,
            _FUND_WEIGHTS_FILE,
            _REGIME_PARAMS_FILE,
            AUDIT_DIR,
        )
        import json as _json

        AUDIT_DIR.mkdir(exist_ok=True)
        if not _REGIME_PARAMS_FILE.exists():
            _REGIME_PARAMS_FILE.write_text(
                _json.dumps(_DEFAULT_REGIME_PARAMS, indent=2)
            )
            logger.info("[startup] seeded regime_params.json with defaults")
        if not _FUND_WEIGHTS_FILE.exists():
            _FUND_WEIGHTS_FILE.write_text(_json.dumps(_DEFAULT_FUND_WEIGHTS, indent=2))
            logger.info("[startup] seeded fund_weights.json with defaults")
    except Exception as _e:
        logger.warning("[startup] self-learning seed failed: %s", _e)

    # Probe Docker Model Runner (non-blocking — resolves within 5s)
    try:
        from src.services.ai_service import get_ai_service as _get_ai

        await _get_ai().probe_local_llm()
    except Exception:
        pass
    # Start both background tasks immediately on boot
    _prewarm_task = asyncio.create_task(_startup_prewarm())
    _breakout_monitor_task = asyncio.create_task(_breakout_monitor_loop())
    if os.getenv("CC_AUTO_START_ENGINE", "").lower() in ("1", "true", "yes"):
        try:
            eng = _get_engine()
            if eng and not eng.running:
                asyncio.create_task(eng.run())
                logger.info(
                    "[startup] AutoTradingEngine loop started (CC_AUTO_START_ENGINE)"
                )
        except Exception as exc:
            logger.warning("[startup] engine auto-start skipped: %s", exc)
    yield
    _prewarm_task.cancel()
    if _breakout_monitor_task:
        _breakout_monitor_task.cancel()
        try:
            await _breakout_monitor_task
        except asyncio.CancelledError:
            pass


# Wire lifespan (defined after dependencies to avoid NameError at import)
app.router.lifespan_context = _lifespan


# ═══════════════════════════════════════════════════════════════════
# Stale data detection (P3)
# ═══════════════════════════════════════════════════════════════════

_DATA_STALENESS_THRESHOLD_SEC = 900  # 15 minutes during market hours
_DATA_STALENESS_AFTER_HOURS_SEC = 86400  # 24 hours after market close


def _check_data_freshness(
    data_timestamp: float | None,
    label: str = "market_data",
) -> dict:
    """Return a freshness report for a data source.

    Args:
        data_timestamp: epoch time of last data refresh (or None if unknown)
        label: human-readable name for the data source

    Returns:
        dict with {fresh: bool, age_seconds: int, warning: str|None}
    """
    if data_timestamp is None:
        return {
            "fresh": False,
            "age_seconds": -1,
            "warning": f"⚠ {label}: timestamp unknown — data may be stale or synthetic",
        }
    age = time.time() - data_timestamp
    # Use tighter threshold during market hours
    threshold = _DATA_STALENESS_THRESHOLD_SEC
    try:
        if not _is_market_open():
            threshold = _DATA_STALENESS_AFTER_HOURS_SEC
    except Exception:
        pass
    if age > threshold:
        return {
            "fresh": False,
            "age_seconds": int(age),
            "warning": f"⚠ {label}: data is {int(age)}s old (threshold {threshold}s)",
        }
    return {"fresh": True, "age_seconds": int(age), "warning": None}


# ═══════════════════════════════════════════════════════════════════
# Indicator helpers — shared module (routers + inline routes)
# ═══════════════════════════════════════════════════════════════════

from src.api.technical_indicators import (
    compute_indicators as _compute_indicators,
    rolling_mean as _rolling_mean,
)


# ── Inline RS vs SPY computation ──
_SPY_CACHE: dict = {"close": None, "ts": 0}


async def _get_spy_close() -> np.ndarray | None:
    """Fetch SPY close array with 1h cache."""
    import time

    now = time.time()
    if _SPY_CACHE["close"] is not None and now - _SPY_CACHE["ts"] < 3600:
        return _SPY_CACHE["close"]
    try:
        mds = app.state.market_data
        hist = await mds.get_history("SPY", period="1y", interval="1d")
        if hist is not None and not hist.empty:
            c_col = "Close" if "Close" in hist.columns else "close"
            spy = hist[c_col].values.astype(float)
            _SPY_CACHE["close"] = spy
            _SPY_CACHE["ts"] = now
            return spy
    except Exception:
        pass
    return None


def _compute_rs_vs_benchmark(
    stock_close: np.ndarray,
    bench_close: np.ndarray,
) -> dict:
    """Compute Mansfield-style RS metrics: composite, percentile-ready, trend.

    RS = (stock % change / benchmark % change) for 1M/3M/6M windows.
    Returns rs_composite (100=in-line), rs_1m, rs_3m, rs_6m, rs_slope.
    """
    n = min(len(stock_close), len(bench_close))
    if n < 22:
        return {
            "rs_composite": 100.0,
            "rs_1m": 100.0,
            "rs_3m": 100.0,
            "rs_6m": 100.0,
            "rs_slope": 0.0,
            "rs_status": "NEUTRAL",
        }

    def _pct(arr, lookback):
        if n < lookback + 1:
            return 0.0
        return (arr[-1] / arr[-1 - lookback] - 1) * 100

    def _rs(s_ret, b_ret):
        if b_ret == 0:
            return 100.0 + s_ret * 10
        return max(0, min(300, (1 + s_ret / 100) / (1 + b_ret / 100) * 100))

    s, b = stock_close[-n:], bench_close[-n:]
    rs_1m = _rs(_pct(s, 21), _pct(b, 21))
    rs_3m = _rs(_pct(s, 63), _pct(b, 63)) if n >= 64 else rs_1m
    rs_6m = _rs(_pct(s, 126), _pct(b, 126)) if n >= 127 else rs_3m

    composite = 0.25 * rs_1m + 0.40 * rs_3m + 0.35 * rs_6m

    # RS slope: compare current 1M RS vs 1M RS from 21 days ago
    rs_slope = 0.0
    if n >= 43:
        old_s_ret = (s[-22] / s[-22 - 21] - 1) * 100 if n >= 44 else 0
        old_b_ret = (b[-22] / b[-22 - 21] - 1) * 100 if n >= 44 else 0
        old_rs = _rs(old_s_ret, old_b_ret)
        rs_slope = round(rs_1m - old_rs, 1)

    if composite >= 120:
        status = "LEADER"
    elif composite >= 105:
        status = "STRONG"
    elif composite >= 95:
        status = "NEUTRAL"
    elif composite >= 80:
        status = "WEAK"
    else:
        status = "LAGGARD"

    return {
        "rs_composite": round(composite, 1),
        "rs_1m": round(rs_1m, 1),
        "rs_3m": round(rs_3m, 1),
        "rs_6m": round(rs_6m, 1),
        "rs_slope": rs_slope,
        "rs_status": status,
    }


# US market holidays — dynamically computed for any year.
# Uses the standard rules for NYSE/NASDAQ holidays:
#   - New Year's Day (Jan 1, observed)
#   - MLK Jr Day (3rd Monday in Jan)
#   - Presidents Day (3rd Monday in Feb)
#   - Good Friday (2 days before Easter)
#   - Memorial Day (last Monday in May)
#   - Juneteenth (Jun 19, observed)
#   - Independence Day (Jul 4, observed)
#   - Labor Day (1st Monday in Sep)
#   - Thanksgiving (4th Thursday in Nov)
#   - Christmas (Dec 25, observed)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> int:
    """Return day of month for the nth occurrence of weekday in month.
    weekday: 0=Mon, 6=Sun. n: 1-based."""
    from datetime import date as _date

    first = _date(year, month, 1)
    # Days until first occurrence of weekday
    days_ahead = weekday - first.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_occurrence = 1 + days_ahead
    return first_occurrence + (n - 1) * 7


def _last_weekday(year: int, month: int, weekday: int) -> int:
    """Return day of month for the last occurrence of weekday in month."""
    from datetime import date as _date
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    last = _date(year, month, last_day)
    days_behind = last.weekday() - weekday
    if days_behind < 0:
        days_behind += 7
    return last_day - days_behind


def _easter_sunday(year: int) -> tuple:
    """Compute Easter Sunday using the anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return (year, month, day)


def _observed(d: tuple) -> tuple:
    """If holiday falls on Saturday, use Friday; Sunday → Monday."""
    from datetime import date as _date, timedelta

    dt = _date(d[0], d[1], d[2])
    if dt.weekday() == 5:  # Saturday
        dt -= timedelta(days=1)
    elif dt.weekday() == 6:  # Sunday
        dt += timedelta(days=1)
    return (dt.year, dt.month, dt.day)


def _compute_us_market_holidays(year: int) -> set:
    """Compute US market holidays for a given year."""
    from datetime import date as _date, timedelta

    holidays = set()

    # New Year's Day
    holidays.add(_observed((year, 1, 1)))

    # MLK Jr Day — 3rd Monday in January
    holidays.add((year, 1, _nth_weekday(year, 1, 0, 3)))

    # Presidents Day — 3rd Monday in February
    holidays.add((year, 2, _nth_weekday(year, 2, 0, 3)))

    # Good Friday — 2 days before Easter Sunday
    ey, em, ed = _easter_sunday(year)
    good_friday = _date(ey, em, ed) - timedelta(days=2)
    holidays.add((good_friday.year, good_friday.month, good_friday.day))

    # Memorial Day — last Monday in May
    holidays.add((year, 5, _last_weekday(year, 5, 0)))

    # Juneteenth
    holidays.add(_observed((year, 6, 19)))

    # Independence Day
    holidays.add(_observed((year, 7, 4)))

    # Labor Day — 1st Monday in September
    holidays.add((year, 9, _nth_weekday(year, 9, 0, 1)))

    # Thanksgiving — 4th Thursday in November
    holidays.add((year, 11, _nth_weekday(year, 11, 3, 4)))

    # Christmas
    holidays.add(_observed((year, 12, 25)))

    return holidays


def _get_us_market_holidays() -> set:
    """Get US market holidays for current year ±1 for safety."""
    from datetime import date as _date

    current_year = _date.today().year
    all_holidays = set()
    for y in range(current_year - 1, current_year + 2):
        all_holidays.update(_compute_us_market_holidays(y))
    return all_holidays


# Lazily computed on first access
_US_MARKET_HOLIDAYS: Optional[set] = None


def _is_us_market_holiday(dt=None) -> bool:
    """Check if a date is a US market holiday."""
    global _US_MARKET_HOLIDAYS
    if _US_MARKET_HOLIDAYS is None:
        _US_MARKET_HOLIDAYS = _get_us_market_holidays()
    if dt is None:
        from datetime import date as _date

        dt = _date.today()
    return (dt.year, dt.month, dt.day) in _US_MARKET_HOLIDAYS


# ===== Health Endpoints =====
# Extracted → src/api/routers/health.py (Sprint 82 ARCH)
# Routes: /health /health/detailed /health/live /health/ready
#         /status/data /status/jobs /status/signals /metrics


# ===== Calibration & Confidence Endpoints =====


@app.get(
    "/api/v6/calibration",
    tags=["health"],
    summary="Calibration diagnostics",
)
async def calibration_report(_: bool = Depends(verify_api_key)):
    """
    Calibration diagnostics: reliability diagrams, sample sizes,
    forecast-vs-realized hit rates per bucket × regime.
    """
    from src.engines.calibration_engine import get_calibration_engine

    engine = get_calibration_engine()
    return engine.calibration_report()


@app.get(
    "/api/v6/portfolio-heat",
    tags=["portfolio"],
    summary="Portfolio exposure and heat",
)
async def portfolio_heat(_: bool = Depends(verify_api_key)):
    """
    Portfolio heat: exposure, concentration, factor overlap,
    event proximity, throttle state, and risk budget consumed.
    """
    from src.engines.portfolio_heat import get_portfolio_heat_engine

    engine = get_portfolio_heat_engine()
    snap = engine.snapshot()
    return snap.to_dict()


@app.get(
    "/api/v6/event-context/{ticker}",
    tags=["signals"],
    summary="Event context for a ticker",
)
async def event_context(ticker: str, _: bool = Depends(verify_api_key)):
    """
    Event context: SEC filings, insider transactions,
    macro data, positioning — for timing/conviction/risk.
    """
    ticker = ticker.upper().strip()
    from src.services.event_data import get_event_data_service

    svc = get_event_data_service()
    return await svc.get_ticker_events(ticker)


@app.get(
    "/api/v6/macro-context",
    tags=["reports"],
    summary="Macro context for regime decisions",
)
async def macro_context(_: bool = Depends(verify_api_key)):
    """
    Macro context: FRED/ALFRED series for regime classification,
    risk budget, and positioning context.
    """
    from src.services.event_data import get_event_data_service

    svc = get_event_data_service()
    return await svc.get_macro_context()


@app.get(
    "/api/v6/version",
    tags=["health"],
    summary="System version and identity",
)
async def version_info():
    """Single source of truth for version and product identity."""
    from src.core.version import (
        APP_VERSION,
        DECISION_SURFACES,
        DISCORD_COMMAND_COUNT,
        DOCKER_SERVICE_COUNT,
        STRATEGY_COUNT,
        UNIVERSE_SUMMARY,
    )

    return {
        "product": PRODUCT_NAME,
        "version": APP_VERSION,
        "strategies": STRATEGY_COUNT,
        "discord_commands": DISCORD_COMMAND_COUNT,
        "docker_services": DOCKER_SERVICE_COUNT,
        "decision_surfaces": list(DECISION_SURFACES),
        "universe": UNIVERSE_SUMMARY,
    }


# ===== Shadow / Dossier / Operator Console Endpoints =====

# ── Sprint 46 swing endpoints extracted → src/api/routers/swing.py (Sprint 84)
# Routes: /api/v6/rs-strength, /api/v6/vcp-scan, /api/v6/swing-analysis,
#         /api/v6/swing-batch, /api/v6/distribution-days, /api/v6/shadow-resolve


@app.get(
    "/api/v6/shadow-report",
    tags=["analytics"],
    summary="Shadow-mode prediction tracker report",
)
async def shadow_report():
    """Return shadow-mode evaluation: hit-rate by bucket, drift flags."""
    from src.engines.shadow_tracker import shadow_tracker

    return shadow_tracker.shadow_report()


@app.get(
    "/api/v6/dossier/{ticker}",
    tags=["analytics"],
    summary="Symbol Dossier v2 – full single-ticker research page",
)
async def symbol_dossier(ticker: str):
    """Build verdict, evidence, scenarios, event calendar for a ticker."""
    from src.engines.symbol_dossier import SymbolDossier

    dossier = SymbolDossier()
    return dossier.build(ticker.upper())


@app.get(
    "/api/v6/circuit-breaker",
    tags=["operator"],
    summary="Circuit breaker state and broker reconciliation status",
)
async def circuit_breaker_state():
    """Return current circuit-breaker state and last reconciliation ts."""
    from src.engines.portfolio_heat import PortfolioHeatEngine

    engine = PortfolioHeatEngine()
    snap = engine.snapshot()
    return {
        "throttle_state": snap.throttle_state,
        "daily_loss_pct": snap.daily_pnl_pct,
        "open_positions": 0,
        "broker_reconciled_at": None,
    }


@app.get(
    "/api/v6/pnl-by-regime",
    tags=["analytics"],
    summary="PnL heatmap broken down by market regime",
)
async def pnl_by_regime():
    """Return PnL statistics grouped by regime label."""
    from src.engines.shadow_tracker import shadow_tracker

    report = shadow_tracker.shadow_report()
    return {
        "regime_pnl": report.get("by_regime", {}),
        "total_predictions": report.get("total_predictions", 0),
    }


@app.get(
    "/api/v6/exposure-dashboard",
    tags=["analytics"],
    summary="Portfolio exposure dashboard: sector, beta, theme",
)
async def exposure_dashboard():
    """Full portfolio exposure snapshot for PM views."""
    from src.engines.portfolio_heat import PortfolioHeatEngine

    engine = PortfolioHeatEngine()
    snap = engine.snapshot()
    return snap.to_dict()


@app.get(
    "/api/v6/meta-label/{ticker}",
    tags=["analytics"],
    summary="Meta-labeler: should I trade this now?",
)
async def meta_label_ticker(ticker: str):
    """Evaluate go/no-go + size for a candidate signal."""
    from src.engines.meta_labeler import MetaLabeler, SignalContext

    ml = MetaLabeler()
    ctx = SignalContext(ticker=ticker.upper())
    label = ml.evaluate(ctx)
    return label.to_dict()


@app.get(
    "/api/v6/post-trade-report",
    tags=["analytics"],
    summary="Post-trade attribution report",
)
async def post_trade_report():
    """Stated reasons vs realized outcomes."""
    from src.engines.post_trade_attribution import post_trade_attribution

    return post_trade_attribution.full_report()


@app.get(
    "/api/v6/regime-heatmap",
    tags=["analytics"],
    summary="PnL heatmap: regime × strategy",
)
async def regime_heatmap():
    """PnL by regime × strategy matrix."""
    from src.engines.post_trade_attribution import post_trade_attribution

    return {
        "heatmap": post_trade_attribution.regime_heatmap(),
    }


@app.get(
    "/api/v6/broker-reconciliation",
    tags=["operator"],
    summary="Broker reconciliation status",
)
async def broker_reconciliation_status():
    """Order tracking and reconciliation gate."""
    from src.engines.broker_reconciliation import broker_reconciliation

    return broker_reconciliation.status()


# ===== Signal Endpoints =====


@app.get("/signals", response_model=SignalListResponse)
async def get_signals(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    direction: Optional[str] = Query(None, description="LONG or SHORT"),
    min_confidence: Optional[float] = Query(
        0.5, description="Minimum confidence threshold"
    ),
    limit: int = Query(50, le=200),
    _: bool = Depends(verify_api_key),
):
    """
    Get trading signals.

    Returns latest signals filtered by date, ticker, direction, and confidence.
    """
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    try:
        # Build query
        conditions = ["confidence >= :min_confidence"]
        params = {"min_confidence": min_confidence}

        if date:
            conditions.append("DATE(generated_at) = :date")
            params["date"] = date
        else:
            # Default to today's signals
            conditions.append("DATE(generated_at) = CURRENT_DATE")

        if ticker:
            conditions.append("ticker = :ticker")
            params["ticker"] = ticker.upper()

        if direction:
            conditions.append("direction = :direction")
            params["direction"] = direction.upper()

        # Build query using SQLAlchemy select() — avoids f-string interpolation
        # of user-supplied values into SQL (SQL injection prevention).
        # All filter values go through bound parameters only.
        from sqlalchemy import Column, Float, Integer, MetaData, String, Table, select

        meta = MetaData()
        signals_table = Table(
            "signals",
            meta,
            Column("id", String),
            Column("ticker", String),
            Column("direction", String),
            Column("strategy", String),
            Column("entry_price", Float),
            Column("take_profit", Float),
            Column("stop_loss", Float),
            Column("confidence", Float),
            Column("generated_at", String),
        )
        stmt = select(signals_table).where(
            signals_table.c.confidence >= params["min_confidence"]
        )
        if date:
            from sqlalchemy import func

            stmt = stmt.where(func.date(signals_table.c.generated_at) == params["date"])
        else:
            from sqlalchemy import func, cast
            from sqlalchemy.sql.expression import literal

            stmt = stmt.where(
                func.date(signals_table.c.generated_at) == func.current_date()
            )
        if ticker:
            stmt = stmt.where(signals_table.c.ticker == params["ticker"])
        if direction:
            stmt = stmt.where(signals_table.c.direction == params["direction"])
        stmt = stmt.order_by(signals_table.c.confidence.desc()).limit(limit)

        async with AsyncSessionLocal() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()

        signals = []
        for row in rows:
            signals.append(
                Signal(
                    id=row.id,
                    ticker=row.ticker,
                    direction=row.direction,
                    strategy=row.strategy,
                    entry_price=row.entry_price,
                    take_profit=row.take_profit,
                    stop_loss=row.stop_loss,
                    confidence=row.confidence,
                    generated_at=row.generated_at,
                )
            )

        return SignalListResponse(
            signals=signals,
            total=len(signals),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/signals/{signal_id}")
async def get_signal_by_id(signal_id: str, _: bool = Depends(verify_api_key)):
    """Get a specific signal by ID."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT * FROM signals WHERE id = :id"), {"id": signal_id}
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    return {
        "id": row.id,
        "ticker": row.ticker,
        "direction": row.direction,
        "strategy": row.strategy,
        "entry_price": float(row.entry_price),
        "take_profit": float(row.take_profit),
        "stop_loss": float(row.stop_loss),
        "confidence": float(row.confidence),
        "regime": row.regime,
        "features": row.features,
        "generated_at": row.generated_at.isoformat(),
    }


@app.get("/signals/ticker/{ticker}")
async def get_signals_for_ticker(
    ticker: str, days: int = Query(7, le=30), _: bool = Depends(verify_api_key)
):
    """Get historical signals for a specific ticker."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT * FROM signals 
                WHERE ticker = :ticker
                AND generated_at > NOW() - INTERVAL ':days days'
                ORDER BY generated_at DESC
            """),
            {"ticker": ticker.upper(), "days": days},
        )
        rows = result.fetchall()

    signals = []
    for row in rows:
        signals.append(
            {
                "id": row.id,
                "direction": row.direction,
                "strategy": row.strategy,
                "entry_price": float(row.entry_price),
                "confidence": float(row.confidence),
                "generated_at": row.generated_at.isoformat(),
            }
        )

    return {"ticker": ticker.upper(), "signals": signals, "count": len(signals)}


# ===== Market Report Endpoints =====


@app.get("/reports/daily")
async def get_daily_report(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    _: bool = Depends(verify_api_key),
):
    """Get daily market report."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    report_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        async with AsyncSessionLocal() as session:
            # Get report from database
            result = await session.execute(
                text("SELECT * FROM daily_reports WHERE report_date = :date"),
                {"date": report_date},
            )
            row = result.fetchone()

        if row:
            return {
                "report_date": report_date,
                "overview": row.overview,
                "sectors": row.sectors,
                "notable_movers": row.notable_movers,
                "news_summary": row.news_summary,
                "signals_summary": row.signals_summary,
                "generated_at": row.generated_at.isoformat(),
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"No report found for {report_date}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily report: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/reports/market-overview")
async def get_market_overview(_: bool = Depends(verify_api_key)):
    """Get current market overview."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            # Get latest index data
            indices_sql = """
                SELECT ticker, close, 
                       (close - LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp)) / 
                       LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp) * 100 as change_pct
                FROM ohlcv
                WHERE ticker IN ('SPY', 'QQQ', 'IWM', 'DIA')
                AND interval = 'day'
                ORDER BY timestamp DESC
                LIMIT 4
            """
            result = await session.execute(text(indices_sql))
            indices = {
                row.ticker: {
                    "price": float(row.close),
                    "change_pct": float(row.change_pct or 0),
                }
                for row in result.fetchall()
            }

            # Get sector performance
            sectors_sql = """
                SELECT ticker, 
                       (close - LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp)) / 
                       LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp) * 100 as change_pct
                FROM ohlcv
                WHERE ticker IN ('XLF', 'XLE', 'XLK', 'XLV', 'XLY', 'XLP', 'XLI', 'XLU', 'XLB', 'XLRE', 'XLC')
                AND interval = 'day'
                ORDER BY timestamp DESC
                LIMIT 11
            """
            result = await session.execute(text(sectors_sql))
            sectors = {
                row.ticker: float(row.change_pct or 0) for row in result.fetchall()
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "indices": indices,
            "sectors": sectors,
            "market_status": "open" if _is_market_open() else "closed",
        }

    except Exception as e:
        logger.error(f"Error fetching market overview: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ===== Data Endpoints =====


@app.get("/data/ohlcv/{ticker}")
async def get_ohlcv_data(
    ticker: str,
    interval: str = Query("day", description="day, hour, 5min, 1min"),
    days: int = Query(30, le=365),
    _: bool = Depends(verify_api_key),
):
    """Get OHLCV data for a ticker."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT timestamp, open, high, low, close, volume
                FROM ohlcv
                WHERE ticker = :ticker
                AND interval = :interval
                AND timestamp > NOW() - INTERVAL ':days days'
                ORDER BY timestamp ASC
            """),
            {"ticker": ticker.upper(), "interval": interval, "days": days},
        )
        rows = result.fetchall()

    data = []
    for row in rows:
        data.append(
            {
                "timestamp": row.timestamp.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume),
            }
        )

    return {
        "ticker": ticker.upper(),
        "interval": interval,
        "data": data,
        "count": len(data),
    }


@app.get("/data/features/{ticker}")
async def get_features(
    ticker: str, date: Optional[str] = Query(None), _: bool = Depends(verify_api_key)
):
    """Get calculated features for a ticker."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    conditions = ["ticker = :ticker"]
    params = {"ticker": ticker.upper()}

    if date:
        conditions.append("DATE(calculated_at) = :date")
        params["date"] = date

    where = " AND ".join(conditions)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT * FROM features
                WHERE {where}
                ORDER BY calculated_at DESC
                LIMIT 1
            """),
            params,
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Features not found")

    return {
        "ticker": ticker.upper(),
        "features": row.features,
        "calculated_at": row.calculated_at.isoformat(),
    }


# ===== News & Sentiment Endpoints =====


@app.get("/news")
async def get_news(
    ticker: Optional[str] = Query(None),
    hours: int = Query(24, le=168),
    limit: int = Query(50, le=200),
    _: bool = Depends(verify_api_key),
):
    """Get recent news articles."""
    from sqlalchemy import text

    from src.core.database import AsyncSessionLocal

    conditions = ["published_at > NOW() - INTERVAL ':hours hours'"]
    params = {"hours": hours, "limit": limit}

    if ticker:
        conditions.append("tickers LIKE :ticker_pattern")
        params["ticker_pattern"] = f"%{ticker.upper()}%"

    where = " AND ".join(conditions)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT id, title, source, published_at, sentiment_label, tickers
                FROM news_articles
                WHERE {where}
                ORDER BY published_at DESC
                LIMIT :limit
            """),
            params,
        )
        rows = result.fetchall()

    articles = []
    for row in rows:
        articles.append(
            {
                "id": row.id,
                "title": row.title,
                "source": row.source,
                "published_at": row.published_at.isoformat(),
                "sentiment": row.sentiment_label,
                "tickers": row.tickers.split(",") if row.tickers else [],
            }
        )

    return {"articles": articles, "count": len(articles)}


@app.get("/sentiment/{ticker}")
async def get_ticker_sentiment(
    ticker: str, hours: int = Query(24, le=168), _: bool = Depends(verify_api_key)
):
    """Get aggregated sentiment for a ticker."""
    from src.ingestors.social import SentimentAggregator

    aggregator = SentimentAggregator()
    sentiment = await aggregator.aggregate_sentiment(ticker.upper(), hours)

    return sentiment


# ===== Helper Functions =====


def _is_market_open() -> bool:
    """Check if US market is currently open (incl. major holidays)."""
    import pytz

    et = pytz.timezone("US/Eastern")
    now = datetime.now(et)

    # Check weekday
    if now.weekday() >= 5:
        return False

    # Check US market holidays (dynamic computation)
    if _is_us_market_holiday(now.date()):
        return False

    # Check time
    from datetime import time

    market_open = time(9, 30)
    market_close = time(16, 0)

    return market_open <= now.time() <= market_close


# ===== Exception Handlers =====

# ===== Scanner Endpoints =====


@app.get("/scan/patterns")
async def scan_patterns(
    tickers: str = Query(
        ..., description="Comma-separated tickers, e.g., AAPL,GOOGL,MSFT"
    ),
    min_confidence: float = Query(70.0, description="Minimum pattern confidence"),
    _: bool = Depends(verify_api_key),
):
    """
    Scan stocks for chart patterns.

    Returns detected patterns with confidence scores, targets, and historical success rates.
    """
    from src.ingestors.market_data import MarketDataIngestor
    from src.scanners import PatternScanner

    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        ingestor = MarketDataIngestor()
        scanner = PatternScanner()

        all_patterns = []

        for ticker in ticker_list[:10]:  # Limit to 10 tickers
            try:
                df = await ingestor.fetch_historical_data(ticker, days=100)
                if df is not None and len(df) > 0:
                    patterns = scanner.scan_patterns(df, ticker)
                    patterns = [p for p in patterns if p.confidence >= min_confidence]
                    for p in patterns:
                        all_patterns.append(
                            {
                                "ticker": p.ticker,
                                "pattern": p.pattern_type.value,
                                "direction": p.direction,
                                "confidence": p.confidence,
                                "historical_success_rate": p.historical_success_rate,
                                "entry_price": p.entry_price,
                                "target_price": p.target_price,
                                "stop_loss": p.stop_loss,
                                "risk_reward_ratio": p.risk_reward_ratio,
                                "description": p.pattern_description,
                                "trading_notes": p.trading_notes,
                            }
                        )
            except Exception as e:
                logger.warning(f"Error scanning {ticker}: {e}")
                continue

        return {
            "patterns": sorted(
                all_patterns, key=lambda x: x["confidence"], reverse=True
            ),
            "total": len(all_patterns),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Pattern scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan/sectors")
async def scan_sectors(_: bool = Depends(verify_api_key)):
    """
    Scan all sectors for opportunities.

    Returns sector performance, rotation analysis, and top opportunities.
    """
    from src.scanners import SectorScanner

    try:
        scanner = SectorScanner()
        results = await scanner.scan_all_sectors()

        sector_data = []
        for sector, metrics in results.items():
            sector_data.append(
                {
                    "sector": sector.value if hasattr(sector, "value") else str(sector),
                    "performance_1d": metrics.performance_1d,
                    "performance_1w": metrics.performance_1w,
                    "performance_1m": metrics.performance_1m,
                    "relative_strength": metrics.relative_strength,
                    "volume_ratio": metrics.volume_ratio,
                    "momentum_score": metrics.momentum_score,
                    "top_stocks": metrics.top_stocks[:5],
                    "bottom_stocks": metrics.bottom_stocks[:5],
                }
            )

        # Sort by momentum score
        sector_data.sort(key=lambda x: x["momentum_score"], reverse=True)

        # Rotation analysis
        rotation = scanner.analyze_rotation(results)

        return {
            "sectors": sector_data,
            "rotation": {
                "current_phase": rotation.current_phase,
                "leading_sectors": rotation.leading_sectors[:3],
                "lagging_sectors": rotation.lagging_sectors[:3],
                "rotation_direction": rotation.rotation_direction,
                "sector_recommendation": rotation.recommendation,
            },
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Sector scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scan/momentum")
async def scan_momentum(
    universe: str = Query(
        "spy_components",
        description="Universe to scan: spy_components, nasdaq100, custom",
    ),
    custom_tickers: Optional[str] = Query(
        None, description="Custom tickers if universe=custom"
    ),
    min_confidence: float = Query(60.0, description="Minimum signal confidence"),
    _: bool = Depends(verify_api_key),
):
    """
    Scan for momentum opportunities.

    Returns breakouts, gaps, volume surges, and trend signals.
    """
    from src.scanners import MomentumScanner

    try:
        scanner = MomentumScanner()

        if universe == "custom" and custom_tickers:
            tickers = [t.strip().upper() for t in custom_tickers.split(",")]
        else:
            tickers = None  # Use default universe

        alerts = await scanner.scan_universe(tickers, min_confidence=min_confidence)

        results = []
        for alert in alerts:
            results.append(
                {
                    "ticker": alert.ticker,
                    "signal_type": alert.signal_type.value,
                    "confidence": alert.confidence,
                    "volume_confirmation": alert.volume_confirmation,
                    "entry_zone": {
                        "low": alert.entry_zone[0] if alert.entry_zone else None,
                        "high": alert.entry_zone[1] if alert.entry_zone else None,
                    },
                    "targets": alert.targets[:3] if alert.targets else [],
                    "stop_loss": alert.stop_loss,
                    "description": alert.description,
                    "detected_at": (
                        alert.detected_at.isoformat() if alert.detected_at else None
                    ),
                }
            )

        return {
            "alerts": results,
            "total": len(results),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Momentum scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/market/snapshot")
async def get_market_snapshot(_: bool = Depends(verify_api_key)):
    """
    Get comprehensive market snapshot.

    Combines all scanners for a complete market view.
    """
    from src.scanners import MarketMonitor

    try:
        monitor = MarketMonitor()
        snapshot = await monitor.scan_market()

        return {
            "breadth": {
                "advancing": snapshot.breadth.advancing,
                "declining": snapshot.breadth.declining,
                "new_highs": snapshot.breadth.new_highs,
                "new_lows": snapshot.breadth.new_lows,
                "advance_decline_ratio": snapshot.breadth.advance_decline_ratio,
                "mcclellan_oscillator": snapshot.breadth.mcclellan_oscillator,
            },
            "top_patterns": [
                {
                    "ticker": p.ticker,
                    "pattern": p.pattern_type.value,
                    "confidence": p.confidence,
                    "direction": p.direction,
                }
                for p in snapshot.pattern_alerts[:5]
            ],
            "momentum_alerts": [
                {
                    "ticker": a.ticker,
                    "type": a.signal_type.value,
                    "confidence": a.confidence,
                }
                for a in snapshot.momentum_alerts[:5]
            ],
            "key_observations": snapshot.key_observations,
            "generated_at": (
                snapshot.generated_at.isoformat()
                if snapshot.generated_at
                else datetime.now(timezone.utc).isoformat()
            ),
        }

    except Exception as e:
        logger.error(f"Market snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ===== Research Endpoints =====


@app.get("/research/news")
async def get_news_brief(
    period: str = Query(
        "morning", description="Period: morning, midday, closing, overnight"
    ),
    tickers: Optional[str] = Query(None, description="Filter by tickers"),
    _: bool = Depends(verify_api_key),
):
    """
    Get AI-condensed news brief.

    Returns summarized news with sentiment and trading implications.
    """
    from src.ingestors.news import NewsIngestor
    from src.research import NewsAnalyzer

    try:
        ingestor = NewsIngestor()
        analyzer = NewsAnalyzer()

        # Fetch news
        ticker_list = (
            [t.strip().upper() for t in tickers.split(",")] if tickers else None
        )
        raw_news = await ingestor.fetch_news(tickers=ticker_list, limit=50)

        # Analyze
        analyzed = await analyzer.analyze_news_batch(raw_news)

        # Generate brief
        brief = await analyzer.generate_brief(analyzed, period=period)

        return {
            "period": brief.period,
            "market_mood": brief.market_mood,
            "headline": brief.headline,
            "executive_summary": brief.executive_summary,
            "trading_focus": brief.trading_focus,
            "top_stories": [
                {
                    "title": s.title,
                    "tickers": s.tickers,
                    "sentiment": s.sentiment.value,
                    "category": s.category.value,
                }
                for s in brief.top_stories[:5]
            ],
            "bullish_catalysts": brief.bullish_catalysts[:3],
            "bearish_catalysts": brief.bearish_catalysts[:3],
            "stocks_to_watch": brief.stocks_to_watch[:10],
            "generated_at": brief.generated_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"News brief error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/research/earnings/{ticker}")
async def get_earnings_analysis(ticker: str, _: bool = Depends(verify_api_key)):
    """
    Get AI-analyzed earnings report for a ticker.

    Returns beat/miss analysis, guidance, and trading implications.
    """
    from src.research import EarningsAnalyzer

    try:
        EarningsAnalyzer()  # validate import

        # Use yfinance for basic earnings data when available
        import yfinance as yf

        def _fetch_earnings():
            t = yf.Ticker(ticker.upper())
            return t.calendar or {}, t.info or {}

        cal, info = await asyncio.to_thread(_fetch_earnings)
        eps_trail = info.get("trailingEps")
        eps_fwd = info.get("forwardEps")
        rev = info.get("totalRevenue")
        margin = info.get("profitMargins")
        return {
            "ticker": ticker.upper(),
            "trailing_eps": eps_trail,
            "forward_eps": eps_fwd,
            "total_revenue": rev,
            "profit_margin": round(margin, 4) if margin else None,
            "calendar": {k: str(v) for k, v in cal.items()} if cal else {},
            "recommendation": info.get("recommendationKey", "none"),
            "source": "yfinance",
            "note": "Live data from Yahoo Finance. Cross-check with broker.",
        }

    except Exception as e:
        logger.error(f"Earnings analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ===== Performance Endpoints =====


@app.get("/performance/stats")
async def get_performance_stats(
    period: str = Query(
        "all_time", description="Period: daily, weekly, monthly, all_time"
    ),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    _: bool = Depends(verify_api_key),
):
    """
    Get signal performance statistics.

    Returns win rates, P&L, and strategy breakdown.
    """
    from src.performance import PerformanceTracker

    try:
        tracker = PerformanceTracker()

        # Load historical data
        await tracker.load_from_db()

        stats = tracker.get_performance_stats(period=period, strategy=strategy)

        return {
            "period": stats.period,
            "total_signals": stats.total_signals,
            "winners": stats.winners,
            "losers": stats.losers,
            "active": stats.active,
            "win_rate": round(stats.win_rate, 1),
            "total_pnl_pct": round(stats.total_pnl_pct, 2),
            "avg_winner_pct": round(stats.avg_winner_pct, 2),
            "avg_loser_pct": round(stats.avg_loser_pct, 2),
            "profit_factor": round(stats.profit_factor, 2),
            "expectancy": round(stats.expectancy, 2),
            "current_streak": stats.current_streak,
            "max_win_streak": stats.max_win_streak,
            "strategy_breakdown": stats.strategy_breakdown,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Performance stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/performance/analytics/{strategy}")
async def get_strategy_analytics(strategy: str, _: bool = Depends(verify_api_key)):
    """
    Get detailed analytics for a strategy.

    Returns risk-adjusted metrics, drawdown analysis, and recommendations.
    """
    from src.performance import PerformanceAnalytics, PerformanceTracker

    try:
        tracker = PerformanceTracker()
        analytics = PerformanceAnalytics()

        await tracker.load_from_db()

        # Get returns for strategy
        strategy_signals = [
            s for s in tracker.completed_signals if s.strategy == strategy
        ]
        returns = [s.pnl_pct for s in strategy_signals]

        if not returns:
            return {
                "strategy": strategy,
                "message": "No completed signals for this strategy",
                "trades": 0,
            }

        metrics = analytics.calculate_strategy_metrics(returns, strategy)

        return {
            "strategy": strategy,
            "total_return": round(metrics.total_return, 2),
            "annualized_return": round(metrics.annualized_return, 2),
            "volatility": round(metrics.volatility, 2),
            "max_drawdown": round(metrics.max_drawdown, 2),
            "sharpe_ratio": round(metrics.sharpe_ratio, 2),
            "sortino_ratio": round(metrics.sortino_ratio, 2),
            "calmar_ratio": round(metrics.calmar_ratio, 2),
            "win_rate": round(metrics.win_rate, 1),
            "profit_factor": round(metrics.profit_factor, 2),
            "total_trades": metrics.total_trades,
            "max_consecutive_losses": metrics.max_consecutive_losses,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Strategy analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# (duplicate exception handlers removed — detailed versions at app startup take precedence)


# ===== Broker Endpoints =====


# /broker/* routes extracted → src/api/routers/broker.py (Sprint 82 ARCH)


# ===== Main Entry Point =====


def start():
    """Start the API server."""
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)


# ===== AI Advisor & ML Status Endpoints =====


@app.get("/api/ai-advisor", tags=["ai"])
async def get_ai_advisor():
    """AI advisor market brief — LLM-powered when available."""
    regime = await _get_regime()
    engine = _get_engine()

    regime_label = regime.regime.replace("_", " ").title()
    vol_label = regime.volatility_regime.replace("_", " ").title()
    should_trade = getattr(regime, "should_trade", True)

    chain = [
        f"Regime: {regime_label} (vol: {vol_label})",
        f"Should trade: {'YES' if should_trade else 'NO'}",
    ]

    signals_today = 0
    trades_today = 0
    if engine:
        signals_today = getattr(engine, "signals_generated_today", 0)
        trades_today = getattr(engine, "trades_executed_today", 0)
        chain.append(f"Signals today: {signals_today}")
        chain.append(f"Trades today: {trades_today}")

    # Rule-based recommendation
    if not should_trade:
        rec = "PAUSE"
        reasoning = f"Regime filter says NO TRADE. {regime_label} regime with {vol_label} volatility."
    elif signals_today >= 5:
        rec = "REDUCE"
        reasoning = "High signal count — tighten selection to top 2-3."
    else:
        rec = "NORMAL"
        reasoning = f"{regime_label} regime is tradable. Standard sizing."

    chain.append(f"Decision: {rec}")

    # ── AI-enhanced brief ──
    ai_brief = None
    ai_provider = None
    try:
        from src.services.ai_service import get_ai_service

        _ai = get_ai_service()
        if _ai.is_configured:
            from src.api.main import _scan_live_signals

            scanned, _ = await _scan_live_signals(limit=5)
            top5 = [
                {
                    "ticker": s.get("ticker", "?"),
                    "score": s.get("score", 0),
                    "strategy": s.get("strategy", "?"),
                    "risk_reward": s.get("risk_reward", 0),
                    "entry_price": s.get("entry_price", 0),
                }
                for s in scanned[:5]
            ]
            _r = {
                "trend": regime_label,
                "volatility": vol_label,
                "vix": getattr(regime, "vix", 18),
                "breadth": getattr(regime, "breadth_pct", 0.5) * 100,
                "tradeability": rec,
                "should_trade": should_trade,
            }
            ai_brief = await _ai.generate_narrative(
                _r, top5, {}, {"universe": 484, "actionable_above_7": len(scanned)}
            )
            ai_provider = _ai._provider_used
    except Exception as exc:
        logger.debug("AI advisor brief unavailable: %s", exc)

    return {
        "status": "live",
        "market_brief": f"{regime_label} regime ({vol_label} volatility). {signals_today} signals, {trades_today} trades today.",
        "recommendation": rec,
        "reasoning": reasoning,
        "ai_brief": ai_brief,
        "ai_provider": ai_provider,
        "chain_of_thought": chain,
        "trust": {
            "mode": "LIVE",
            "source": "regime_router + engine",
            "ai_powered": ai_brief is not None,
            "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/ml-status", tags=["ai"])
async def get_ml_status():
    """Get ML model training status — honest report from engine state."""
    engine = _get_engine()

    if engine is None:
        return {
            "model_ready": False,
            "status": "Engine not loaded. ML models unavailable.",
            "trust": {
                "mode": "HONEST",
                "note": "No engine instance — cannot report model metrics.",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Pull real metrics from engine if available
    model_ready = hasattr(engine, "ml_model") and engine.ml_model is not None
    cached_recs = len(getattr(engine, "_recommendation_cache", {}))
    signals_today = getattr(engine, "signals_generated_today", 0)
    trades_today = getattr(engine, "trades_executed_today", 0)
    cycle_count = getattr(engine, "cycle_count", 0)

    return _sanitize_for_json(
        {
            "model_ready": model_ready,
            "status": "loaded" if model_ready else "not_loaded",
            "engine_metrics": {
                "cycle_count": cycle_count,
                "signals_today": signals_today,
                "trades_today": trades_today,
                "cached_recommendations": cached_recs,
            },
            "trust": {
                "mode": "LIVE" if model_ready else "HONEST",
                "note": (
                    "Real engine metrics. ML accuracy not tracked until learning loop is wired."
                    if not model_ready
                    else "Model loaded and reporting live metrics."
                ),
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


# ═══════════════════════════════════════════════════════════════════
# AI Service Status
# ═══════════════════════════════════════════════════════════════════


@app.get("/api/ai/status", tags=["ai"])
async def get_ai_status():
    """AI service health and usage stats (includes Docker Model Runner)."""
    try:
        from src.services.ai_service import get_ai_service

        ai = get_ai_service()
        return {
            "status": "ready" if ai.is_configured else "not_configured",
            **ai.stats,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.post("/api/ai/probe-local", tags=["ai"])
async def probe_local_llm():
    """Re-probe Docker Model Runner (call after models finish downloading)."""
    try:
        from src.services.ai_service import get_ai_service

        ai = get_ai_service()
        ok = await ai.probe_local_llm()
        return {
            "local_llm_available": ok,
            "url": ai.stats["providers"]["local_llm_url"],
            "fast_model": ai.stats["providers"]["local_model_fast"],
            "heavy_model": ai.stats["providers"]["local_model_heavy"],
        }
    except Exception as exc:
        return {"local_llm_available": False, "error": str(exc)}



# v6 pro desk → src/api/routers/v6_pro_desk.py



# ===== Sprint 6: Decision-Layer API Endpoints =====


@app.get("/api/regime", tags=["decision-layer"])
async def get_regime_state():
    """Get current market regime classification.

    Reads from the singleton cached regime — same source of truth
    as every other surface (dashboard, bot, screener).
    """
    try:
        state = await _get_regime()

        # Normalize to dict
        if hasattr(state, "to_dict"):
            regime_dict = state.to_dict()
        elif isinstance(state, dict):
            regime_dict = state
        else:
            regime_dict = {"regime": str(state)}

        return {
            "status": "ok",
            "regime": regime_dict,
            "source": "singleton_regime_cache",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Regime endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ═══════════════════════════════════════════════════════════════════
# Ticker Dictionary — autocomplete + company names (EN + 中文)
# ═══════════════════════════════════════════════════════════════════
_TICKER_DB: list[dict] = [
    # ── Mega-cap Tech ──
    {"s": "AAPL", "n": "Apple Inc.", "z": "蘋果"},
    {"s": "MSFT", "n": "Microsoft Corp.", "z": "微軟"},
    {"s": "GOOGL", "n": "Alphabet (Google)", "z": "谷歌"},
    {"s": "GOOG", "n": "Alphabet Class C", "z": "谷歌C"},
    {"s": "AMZN", "n": "Amazon.com Inc.", "z": "亞馬遜"},
    {"s": "NVDA", "n": "NVIDIA Corp.", "z": "英偉達"},
    {"s": "META", "n": "Meta Platforms", "z": "臉書/Meta"},
    {"s": "TSLA", "n": "Tesla Inc.", "z": "特斯拉"},
    {"s": "TSM", "n": "Taiwan Semiconductor", "z": "台積電"},
    {"s": "AVGO", "n": "Broadcom Inc.", "z": "博通"},
    {"s": "ORCL", "n": "Oracle Corp.", "z": "甲骨文"},
    {"s": "CRM", "n": "Salesforce Inc.", "z": "賽富時"},
    {"s": "ADBE", "n": "Adobe Inc.", "z": "奧多比"},
    {"s": "AMD", "n": "Advanced Micro Devices", "z": "超微半導體"},
    {"s": "INTC", "n": "Intel Corp.", "z": "英特爾"},
    {"s": "CSCO", "n": "Cisco Systems", "z": "思科"},
    {"s": "NFLX", "n": "Netflix Inc.", "z": "網飛"},
    {"s": "QCOM", "n": "Qualcomm Inc.", "z": "高通"},
    {"s": "INTU", "n": "Intuit Inc.", "z": "財捷"},
    {"s": "AMAT", "n": "Applied Materials", "z": "應用材料"},
    {"s": "MU", "n": "Micron Technology", "z": "美光"},
    {"s": "NOW", "n": "ServiceNow Inc.", "z": "ServiceNow"},
    {"s": "SNOW", "n": "Snowflake Inc.", "z": "雪花"},
    {"s": "SHOP", "n": "Shopify Inc.", "z": "Shopify"},
    {"s": "SQ", "n": "Block Inc.", "z": "Block"},
    {"s": "PLTR", "n": "Palantir Technologies", "z": "Palantir"},
    {"s": "UBER", "n": "Uber Technologies", "z": "優步"},
    {"s": "ABNB", "n": "Airbnb Inc.", "z": "愛彼迎"},
    {"s": "COIN", "n": "Coinbase Global", "z": "Coinbase"},
    {"s": "MRVL", "n": "Marvell Technology", "z": "邁威爾"},
    {"s": "PANW", "n": "Palo Alto Networks", "z": "派拓網絡"},
    {"s": "CRWD", "n": "CrowdStrike Holdings", "z": "CrowdStrike"},
    # ── Finance ──
    {"s": "JPM", "n": "JPMorgan Chase", "z": "摩根大通"},
    {"s": "V", "n": "Visa Inc.", "z": "維薩"},
    {"s": "MA", "n": "Mastercard Inc.", "z": "萬事達"},
    {"s": "BAC", "n": "Bank of America", "z": "美國銀行"},
    {"s": "WFC", "n": "Wells Fargo", "z": "富國銀行"},
    {"s": "GS", "n": "Goldman Sachs", "z": "高盛"},
    {"s": "MS", "n": "Morgan Stanley", "z": "摩根士丹利"},
    {"s": "BRK.B", "n": "Berkshire Hathaway B", "z": "巴郡B"},
    {"s": "AXP", "n": "American Express", "z": "美國運通"},
    {"s": "SCHW", "n": "Charles Schwab", "z": "嘉信理財"},
    {"s": "C", "n": "Citigroup Inc.", "z": "花旗"},
    {"s": "PYPL", "n": "PayPal Holdings", "z": "貝寶"},
    # ── Healthcare ──
    {"s": "UNH", "n": "UnitedHealth Group", "z": "聯合健康"},
    {"s": "JNJ", "n": "Johnson & Johnson", "z": "強生"},
    {"s": "LLY", "n": "Eli Lilly & Co.", "z": "禮來"},
    {"s": "PFE", "n": "Pfizer Inc.", "z": "輝瑞"},
    {"s": "ABBV", "n": "AbbVie Inc.", "z": "艾伯維"},
    {"s": "MRK", "n": "Merck & Co.", "z": "默克"},
    {"s": "TMO", "n": "Thermo Fisher Scientific", "z": "賽默飛"},
    {"s": "NVO", "n": "Novo Nordisk", "z": "諾和諾德"},
    # ── Consumer ──
    {"s": "COST", "n": "Costco Wholesale", "z": "好市多"},
    {"s": "WMT", "n": "Walmart Inc.", "z": "沃爾瑪"},
    {"s": "HD", "n": "Home Depot", "z": "家得寶"},
    {"s": "PG", "n": "Procter & Gamble", "z": "寶潔"},
    {"s": "KO", "n": "Coca-Cola Co.", "z": "可口可樂"},
    {"s": "PEP", "n": "PepsiCo Inc.", "z": "百事"},
    {"s": "MCD", "n": "McDonald's Corp.", "z": "麥當勞"},
    {"s": "NKE", "n": "Nike Inc.", "z": "耐克"},
    {"s": "SBUX", "n": "Starbucks Corp.", "z": "星巴克"},
    {"s": "DIS", "n": "Walt Disney Co.", "z": "迪士尼"},
    {"s": "TGT", "n": "Target Corp.", "z": "塔吉特"},
    {"s": "LOW", "n": "Lowe's Companies", "z": "勞氏"},
    # ── Industrial / Energy ──
    {"s": "XOM", "n": "Exxon Mobil", "z": "埃克森美孚"},
    {"s": "CVX", "n": "Chevron Corp.", "z": "雪佛龍"},
    {"s": "BA", "n": "Boeing Co.", "z": "波音"},
    {"s": "CAT", "n": "Caterpillar Inc.", "z": "卡特彼勒"},
    {"s": "UPS", "n": "United Parcel Service", "z": "聯合包裹"},
    {"s": "GE", "n": "GE Aerospace", "z": "通用電氣"},
    {"s": "RTX", "n": "RTX Corp.", "z": "雷神"},
    {"s": "HON", "n": "Honeywell International", "z": "霍尼韋爾"},
    {"s": "DE", "n": "Deere & Co.", "z": "迪爾"},
    {"s": "LMT", "n": "Lockheed Martin", "z": "洛歇馬丁"},
    # ── Telecom / Media ──
    {"s": "T", "n": "AT&T Inc.", "z": "AT&T"},
    {"s": "VZ", "n": "Verizon Communications", "z": "威瑞森"},
    {"s": "CMCSA", "n": "Comcast Corp.", "z": "康卡斯特"},
    {"s": "TMUS", "n": "T-Mobile US", "z": "T-Mobile"},
    # ── ETFs ──
    {"s": "SPY", "n": "S&P 500 ETF", "z": "標普500"},
    {"s": "QQQ", "n": "Nasdaq-100 ETF", "z": "納指100"},
    {"s": "IWM", "n": "Russell 2000 ETF", "z": "羅素2000"},
    {"s": "DIA", "n": "Dow Jones ETF", "z": "道指"},
    {"s": "VOO", "n": "Vanguard S&P 500", "z": "先鋒標普500"},
    {"s": "VTI", "n": "Vanguard Total Market", "z": "先鋒全市場"},
    {"s": "ARKK", "n": "ARK Innovation ETF", "z": "方舟創新"},
    {"s": "XLF", "n": "Financial Select SPDR", "z": "金融板塊"},
    {"s": "XLK", "n": "Technology Select SPDR", "z": "科技板塊"},
    {"s": "XLE", "n": "Energy Select SPDR", "z": "能源板塊"},
    {"s": "XLV", "n": "Health Care Select SPDR", "z": "醫療板塊"},
    {"s": "GLD", "n": "SPDR Gold Shares", "z": "黃金"},
    {"s": "SLV", "n": "iShares Silver Trust", "z": "白銀"},
    {"s": "TLT", "n": "20+ Year Treasury Bond", "z": "長期國債"},
    {"s": "HYG", "n": "High Yield Corporate Bond", "z": "高收益債"},
    {"s": "EEM", "n": "Emerging Markets ETF", "z": "新興市場"},
    {"s": "FXI", "n": "China Large-Cap ETF", "z": "中國大盤"},
    {"s": "KWEB", "n": "China Internet ETF", "z": "中概互聯網"},
    {"s": "EWJ", "n": "Japan ETF", "z": "日本"},
    {"s": "EWZ", "n": "Brazil ETF", "z": "巴西"},
    {"s": "VNQ", "n": "Real Estate ETF", "z": "房地產"},
    {"s": "SOXX", "n": "Semiconductor ETF", "z": "半導體"},
    # ── Crypto-adjacent ──
    {"s": "MSTR", "n": "MicroStrategy", "z": "微策略"},
    {"s": "MARA", "n": "Marathon Digital", "z": "Marathon"},
    {"s": "RIOT", "n": "Riot Platforms", "z": "Riot"},
    # ── China ADR ──
    {"s": "BABA", "n": "Alibaba Group", "z": "阿里巴巴"},
    {"s": "JD", "n": "JD.com Inc.", "z": "京東"},
    {"s": "PDD", "n": "PDD Holdings (Pinduoduo)", "z": "拼多多"},
    {"s": "BIDU", "n": "Baidu Inc.", "z": "百度"},
    {"s": "NIO", "n": "NIO Inc.", "z": "蔚來"},
    {"s": "XPEV", "n": "XPeng Inc.", "z": "小鵬"},
    {"s": "LI", "n": "Li Auto Inc.", "z": "理想汽車"},
    {"s": "BILI", "n": "Bilibili Inc.", "z": "嗶哩嗶哩"},
    {"s": "TME", "n": "Tencent Music", "z": "騰訊音樂"},
    {"s": "ZH", "n": "Zhihu Inc.", "z": "知乎"},
    # ── Airlines / Travel ──
    {"s": "AAL", "n": "American Airlines", "z": "美國航空"},
    {"s": "DAL", "n": "Delta Air Lines", "z": "達美航空"},
    {"s": "UAL", "n": "United Airlines", "z": "聯合航空"},
    {"s": "LUV", "n": "Southwest Airlines", "z": "西南航空"},
    {"s": "MAR", "n": "Marriott International", "z": "萬豪"},
    {"s": "BKNG", "n": "Booking Holdings", "z": "Booking"},
    # ── Other popular ──
    {"s": "F", "n": "Ford Motor Co.", "z": "福特"},
    {"s": "GM", "n": "General Motors", "z": "通用汽車"},
    {"s": "RIVN", "n": "Rivian Automotive", "z": "Rivian"},
    {"s": "LCID", "n": "Lucid Group", "z": "Lucid"},
    {"s": "SOFI", "n": "SoFi Technologies", "z": "SoFi"},
    {"s": "HOOD", "n": "Robinhood Markets", "z": "Robinhood"},
    {"s": "SNAP", "n": "Snap Inc.", "z": "Snapchat"},
    {"s": "PINS", "n": "Pinterest Inc.", "z": "Pinterest"},
    {"s": "ROKU", "n": "Roku Inc.", "z": "Roku"},
    {"s": "ZM", "n": "Zoom Video", "z": "Zoom"},
    {"s": "DKNG", "n": "DraftKings Inc.", "z": "DraftKings"},
    {"s": "PATH", "n": "UiPath Inc.", "z": "UiPath"},
    {"s": "AI", "n": "C3.ai Inc.", "z": "C3.ai"},
    {"s": "SMCI", "n": "Super Micro Computer", "z": "超微電腦"},
    {"s": "ARM", "n": "Arm Holdings", "z": "安謀"},
    {"s": "DELL", "n": "Dell Technologies", "z": "戴爾"},
    {"s": "HPQ", "n": "HP Inc.", "z": "惠普"},
    {"s": "IBM", "n": "IBM Corp.", "z": "IBM"},
]
# Build lookup index
_TICKER_INDEX = {t["s"].upper(): t for t in _TICKER_DB}


@app.get("/api/tickers", tags=["reference"])
async def search_tickers(q: str = Query("", description="Search query")):
    """Autocomplete — search tickers by symbol or company name (EN/中文)."""
    q = q.strip().upper()
    if not q:
        return {"results": [], "count": 0}
    matches = []
    for t in _TICKER_DB:
        if t["s"].upper().startswith(q) or q in t["n"].upper() or q in t.get("z", ""):
            matches.append(t)
        if len(matches) >= 12:
            break
    return {"results": matches, "count": len(matches)}


# ── Live Signal Scanner (on-demand when engine cache is empty) ──
_SCAN_WATCHLIST = [
    # ── Information Technology ──
    "AAPL",
    "MSFT",
    "NVDA",
    "AVGO",
    "ORCL",
    "CRM",
    "AMD",
    "CSCO",
    "ACN",
    "ADBE",
    "IBM",
    "INTC",
    "TXN",
    "QCOM",
    "INTU",
    "AMAT",
    "NOW",
    "MU",
    "LRCX",
    "ADI",
    "KLAC",
    "PANW",
    "SNPS",
    "CDNS",
    "CRWD",
    "MSI",
    "NXPI",
    "FTNT",
    "ROP",
    "APH",
    "MCHP",
    "TEL",
    "ADSK",
    "KEYS",
    "ON",
    "CDW",
    "FICO",
    "IT",
    "FSLR",
    "MPWR",
    "SMCI",
    "ARM",
    "PLTR",
    "NET",
    "DDOG",
    "SNOW",
    "ZS",
    "SHOP",
    "TTD",
    "HUBS",
    "TEAM",
    "MDB",
    "ESTC",
    "CFLT",
    "S",
    "CRDO",
    "ONTO",
    "ANET",
    "DELL",
    "HPQ",
    "HPE",
    "WDC",
    "STX",
    "ENPH",
    "GLOB",
    "EPAM",
    "PAYC",
    "PCTY",
    "MANH",
    "BILL",
    "DOCU",
    "OKTA",
    # ── Communication Services ──
    "META",
    "GOOGL",
    "GOOG",
    "NFLX",
    "T",
    "TMUS",
    "VZ",
    "DIS",
    "CMCSA",
    "CHTR",
    "EA",
    "TTWO",
    "MTCH",
    "WBD",
    "LYV",
    "RBLX",
    "PINS",
    "SNAP",
    "ROKU",
    "ZM",
    "SPOT",
    "RDDT",
    "DASH",
    "UBER",
    # ── Consumer Discretionary ──
    "AMZN",
    "TSLA",
    "HD",
    "MCD",
    "NKE",
    "SBUX",
    "TJX",
    "BKNG",
    "LOW",
    "CMG",
    "ORLY",
    "ABNB",
    "MAR",
    "GM",
    "F",
    "ROST",
    "YUM",
    "DHI",
    "LEN",
    "LULU",
    "AZO",
    "GPC",
    "POOL",
    "DECK",
    "ULTA",
    "DPZ",
    "WYNN",
    "MGM",
    "LVS",
    "RCL",
    "CCL",
    "NCLH",
    "ETSY",
    "W",
    "RIVN",
    "NIO",
    "XPEV",
    "LI",
    "LCID",
    # ── Financials ──
    "JPM",
    "V",
    "MA",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "SPGI",
    "BLK",
    "AXP",
    "SCHW",
    "C",
    "CB",
    "MMC",
    "PGR",
    "ICE",
    "AON",
    "CME",
    "MCO",
    "USB",
    "AJG",
    "MSCI",
    "PNC",
    "TFC",
    "AIG",
    "MET",
    "PRU",
    "TROW",
    "BK",
    "STT",
    "FITB",
    "RF",
    "CFG",
    "HBAN",
    "KEY",
    "ALLY",
    "SOFI",
    "COIN",
    "HOOD",
    "MKTX",
    "FIS",
    "FISV",
    "PYPL",
    "XYZ",
    "AFRM",  # SQ→XYZ (Block rebrand)
    # ── Healthcare ──
    "UNH",
    "JNJ",
    "LLY",
    "ABBV",
    "MRK",
    "TMO",
    "ABT",
    "DHR",
    "PFE",
    "BMY",
    "AMGN",
    "MDT",
    "ISRG",
    "SYK",
    "GILD",
    "VRTX",
    "REGN",
    "BSX",
    "ELV",
    "CI",
    "ZTS",
    "BDX",
    "HCA",
    "MRNA",
    "BNTX",
    "DXCM",
    "IDXX",
    "IQV",
    "MTD",
    "ALGN",
    "HOLX",
    "PODD",
    "INCY",
    "BIIB",
    "ILMN",
    "A",
    "WST",
    "RMD",
    "EW",
    "BAX",
    "CNC",
    "MOH",
    "NBIX",
    "IONS",
    # ── Industrials ──
    "GE",
    "CAT",
    "UNP",
    "HON",
    "RTX",
    "BA",
    "LMT",
    "DE",
    "UPS",
    "ADP",
    "ETN",
    "WM",
    "ITW",
    "EMR",
    "NSC",
    "CSX",
    "GD",
    "NOC",
    "TDG",
    "CTAS",
    "PCAR",
    "CARR",
    "FAST",
    "ODFL",
    "CPRT",
    "WCN",
    "RSG",
    "LHX",
    "VRSK",
    "PWR",
    "IR",
    "ROK",
    "SWK",
    "FTV",
    "AXON",
    "TDY",
    "HEI",
    "RKLB",
    "ASTS",
    "LUNR",
    # ── Consumer Staples ──
    "PG",
    "COST",
    "KO",
    "PEP",
    "WMT",
    "PM",
    "MO",
    "MDLZ",
    "CL",
    "EL",
    "KMB",
    "GIS",
    "SJM",
    "HSY",
    "K",
    "STZ",
    "ADM",
    "TSN",
    "TGT",
    "DG",
    # ── Energy ──
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "EOG",
    "MPC",
    "PSX",
    "VLO",
    "OXY",
    "DVN",
    "HAL",
    "BKR",
    "FANG",
    "KMI",
    "WMB",
    "OKE",
    "TRGP",
    "ET",
    "PBR",
    "BP",
    "SHEL",
    "TTE",
    "VALE",
    # ── Materials ──
    "LIN",
    "APD",
    "SHW",
    "ECL",
    "DD",
    "NEM",
    "FCX",
    "NUE",
    "VMC",
    "MLM",
    "PPG",
    "ALB",
    "EMN",
    "CF",
    "MOS",
    # ── Utilities ──
    "NEE",
    "SO",
    "DUK",
    "D",
    "AEP",
    "SRE",
    "EXC",
    "XEL",
    "WEC",
    "ED",
    # ── Real Estate ──
    "PLD",
    "AMT",
    "CCI",
    "EQIX",
    "PSA",
    "O",
    "WELL",
    "DLR",
    "SPG",
    "VICI",
    "ARE",
    "AVB",
    "EQR",
    "MAA",
    "INVH",
    # ── ETFs ──
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLI",
    "XLP",
    "XLY",
    "ARKK",
    "ARKG",
    "SMH",
    "SOXX",
    # ── Crypto-adjacent ──
    "MSTR",
    "MARA",
    "RIOT",
    "CLSK",
    "BTBT",
    "HUT",
    "BITF",
    "CIFR",
    # ── International ADRs ──
    "BABA",
    "TSM",
    "ASML",
    "NVO",
    "SAP",
    "TM",
    "SNY",
    "AZN",
    "DEO",
    "UL",
    "INFY",
    "WIT",
    "GRAB",
    "SE",
    "MELI",
    "NU",
    "BIDU",
    "JD",
    "PDD",
    "KWEB",
    # ── Additional Mid/Small-Cap & Popular ──
    # Fintech / Payments
    "UPST",
    "LMND",
    "OPEN",
    "LC",
    "TOST",
    "FOUR",
    "GPN",
    "WEX",
    "PAGS",
    "STNE",
    # Cybersecurity
    "TENB",
    "RPD",
    "VRNS",
    "QLYS",
    # AI / Data / Analytics
    "AI",
    "PATH",
    "BRZE",
    "DV",
    "CWAN",
    "GTLB",
    # Cannabis
    "TLRY",
    "CGC",
    "ACB",
    "SNDL",
    # Biotech Small-Cap
    "SMMT",
    "LEGN",
    "SRPT",
    "ALNY",
    "BMRN",
    "EXAS",
    "NTRA",
    "RXRX",
    "DNA",
    # Solar / Clean Energy
    "RUN",
    "ARRY",
    "SHLS",
    # Retail / E-commerce
    "CHWY",
    "COUR",
    "DUOL",
    "ASAN",
    "FVRR",
    "UPWK",
    # Gaming / Entertainment
    "DKNG",
    "PENN",
    "RSI",
    "GENI",
    "U",
    # Telecom / Infrastructure
    "LUMN",
    "TNET",
    "CALIX",
    # Travel / Hospitality
    "EXPE",
    "TRIP",
    "HTHT",
    # Industrials Small-Cap
    "GNRC",
    "TTC",
    "SITE",
    "BLDR",
    "TREX",
    # Food / Beverage
    "CELH",
    "MNST",
    "SAM",
    "FIZZ",
    # Insurance
    "ROOT",
    "ACGL",
    "RNR",
    "ERIE",
    # Mining / Metals
    "GOLD",
    "AEM",
    "WPM",
    "RGLD",
    "PAAS",
    "AG",
    # REITs Small
    "REXR",
    "SUI",
    "ELS",
    "CUBE",
    # Misc Popular
    "CAVA",
    "BROS",
    "DJT",
    "IONQ",
    "RGTI",
    "QUBT",
    "SOUN",
    "JOBY",
    "ACHR",
    "VST",
    "TXRH",
    "WING",
    "COKE",
    "TMDX",
    "PRCT",
    "AXSM",
    "KRYS",
    "CVNA",
]
# Deduplicate while preserving order
_SCAN_WATCHLIST = list(dict.fromkeys(_SCAN_WATCHLIST))
app.state.scan_watchlist = _SCAN_WATCHLIST  # P3: expose for routers without import

# ── Sector clustering for correlation guard (P3) ──
# Prevents hidden concentration: max N signals from the same sector cluster.
_TICKER_SECTOR: dict[str, str] = {}
_SECTOR_CLUSTERS = {
    "Semiconductor": [
        "NVDA",
        "AMD",
        "AVGO",
        "MU",
        "INTC",
        "SMCI",
        "ARM",
        "QCOM",
        "TXN",
        "AMAT",
        "LRCX",
        "ADI",
        "KLAC",
        "NXPI",
        "MCHP",
        "ON",
        "MPWR",
        "FSLR",
        "CRDO",
        "ONTO",
        "TSM",
        "ASML",
        "SOXX",
        "SMH",
    ],
    "Big Tech": ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META"],
    "Software/Cloud": [
        "CRM",
        "ORCL",
        "ADBE",
        "NOW",
        "INTU",
        "PANW",
        "SNPS",
        "CDNS",
        "CRWD",
        "FTNT",
        "ADSK",
        "ANSS",
        "FICO",
        "PLTR",
        "NET",
        "DDOG",
        "SNOW",
        "ZS",
        "SHOP",
        "TTD",
        "HUBS",
        "TEAM",
        "MDB",
        "ESTC",
        "CFLT",
        "OKTA",
        "DOCU",
        "BILL",
        "PAYC",
        "PCTY",
        "MANH",
        "SAP",
    ],
    "Financials": [
        "JPM",
        "V",
        "MA",
        "BAC",
        "WFC",
        "GS",
        "MS",
        "SPGI",
        "BLK",
        "AXP",
        "SCHW",
        "C",
        "CB",
        "PGR",
        "ICE",
        "AON",
        "CME",
        "MCO",
        "USB",
        "AJG",
        "MSCI",
        "PNC",
        "TFC",
        "AIG",
        "MET",
        "PRU",
        "TROW",
        "BK",
        "STT",
        "FITB",
        "RF",
        "CFG",
        "HBAN",
        "KEY",
        "ALLY",
        "SOFI",
        "COIN",
        "HOOD",
        "MKTX",
        "FIS",
        "FISV",
        "PYPL",
        "SQ",
        "AFRM",
        "XLF",
    ],
    "Healthcare": [
        "UNH",
        "JNJ",
        "LLY",
        "ABBV",
        "MRK",
        "TMO",
        "ABT",
        "DHR",
        "PFE",
        "BMY",
        "AMGN",
        "MDT",
        "ISRG",
        "SYK",
        "GILD",
        "VRTX",
        "REGN",
        "BSX",
        "ELV",
        "CI",
        "ZTS",
        "BDX",
        "HCA",
        "MRNA",
        "BNTX",
        "DXCM",
        "IDXX",
        "IQV",
        "MTD",
        "ALGN",
        "HOLX",
        "PODD",
        "INCY",
        "BIIB",
        "ILMN",
        "A",
        "WST",
        "RMD",
        "EW",
        "BAX",
        "CNC",
        "MOH",
        "HZNP",
        "NBIX",
        "IONS",
        "XLV",
    ],
    "Consumer Disc": [
        "HD",
        "MCD",
        "NKE",
        "SBUX",
        "TJX",
        "BKNG",
        "LOW",
        "CMG",
        "ORLY",
        "ABNB",
        "MAR",
        "ROST",
        "YUM",
        "DHI",
        "LEN",
        "LULU",
        "AZO",
        "GPC",
        "POOL",
        "DECK",
        "ULTA",
        "DPZ",
        "WYNN",
        "MGM",
        "LVS",
        "RCL",
        "CCL",
        "NCLH",
        "ETSY",
        "W",
        "XLY",
    ],
    "Consumer Staples": [
        "PG",
        "COST",
        "KO",
        "PEP",
        "WMT",
        "PM",
        "MO",
        "MDLZ",
        "CL",
        "EL",
        "KMB",
        "GIS",
        "SJM",
        "HSY",
        "STZ",
        "ADM",
        "TSN",
        "TGT",
        "DG",
        "XLP",
    ],
    "EV/Auto": ["TSLA", "RIVN", "NIO", "XPEV", "LI", "LCID", "QS", "GM", "F"],
    "ETF": [
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "XLK",
        "XLE",
        "XLI",
        "ARKK",
        "ARKG",
        "KWEB",
    ],
    "Aerospace/Defense": [
        "RTX",
        "BA",
        "LMT",
        "GE",
        "GD",
        "NOC",
        "TDG",
        "LHX",
        "TDY",
        "HEI",
        "RKLB",
        "ASTS",
        "LUNR",
        "AXON",
        "XLI",
    ],
    "Energy": [
        "XOM",
        "CVX",
        "COP",
        "SLB",
        "EOG",
        "MPC",
        "PSX",
        "VLO",
        "PXD",
        "OXY",
        "HES",
        "DVN",
        "HAL",
        "BKR",
        "FANG",
        "KMI",
        "WMB",
        "OKE",
        "TRGP",
        "ET",
        "PBR",
        "BP",
        "SHEL",
        "TTE",
        "VALE",
        "XLE",
    ],
    "Materials": [
        "LIN",
        "APD",
        "SHW",
        "ECL",
        "DD",
        "NEM",
        "FCX",
        "NUE",
        "VMC",
        "MLM",
        "PPG",
        "ALB",
        "EMN",
        "CF",
        "MOS",
    ],
    "Industrials": [
        "CAT",
        "UNP",
        "HON",
        "DE",
        "UPS",
        "ADP",
        "ETN",
        "WM",
        "ITW",
        "EMR",
        "NSC",
        "CSX",
        "CTAS",
        "PCAR",
        "CARR",
        "FAST",
        "ODFL",
        "CPRT",
        "WCN",
        "RSG",
        "VRSK",
        "PWR",
        "IR",
        "ROK",
        "SWK",
        "FTV",
    ],
    "Utilities": ["NEE", "SO", "DUK", "D", "AEP", "SRE", "EXC", "XEL", "WEC", "ED"],
    "Real Estate": [
        "PLD",
        "AMT",
        "CCI",
        "EQIX",
        "PSA",
        "O",
        "WELL",
        "DLR",
        "SPG",
        "VICI",
        "ARE",
        "AVB",
        "EQR",
        "MAA",
        "INVH",
    ],
    "Crypto-adjacent": ["MSTR", "MARA", "RIOT", "CLSK", "BTBT", "HUT", "BITF", "CIFR"],
    "Intl ADR": [
        "BABA",
        "TSM",
        "ASML",
        "NVO",
        "SAP",
        "TM",
        "SNY",
        "AZN",
        "DEO",
        "UL",
        "INFY",
        "WIT",
        "GRAB",
        "SE",
        "MELI",
        "NU",
        "BIDU",
        "JD",
        "PDD",
    ],
    "Communication": [
        "NFLX",
        "T",
        "TMUS",
        "VZ",
        "DIS",
        "CMCSA",
        "CHTR",
        "EA",
        "TTWO",
        "MTCH",
        "WBD",
        "PARA",
        "LYV",
        "RBLX",
        "PINS",
        "SNAP",
        "ROKU",
        "ZM",
        "SPOT",
        "RDDT",
        "DASH",
        "UBER",
    ],
}
for _sector, _tickers in _SECTOR_CLUSTERS.items():
    for _t in _tickers:
        _TICKER_SECTOR[_t] = _sector
_MAX_SIGNALS_PER_SECTOR = RISK.max_correlated_names  # default 3

_scan_cache: dict = {"recs": [], "scores": {}, "ts": 0.0}
_SCAN_CACHE_TTL = 300  # 5 minutes

# Negative cache: tickers that fail consistently are skipped for 1 hour
_neg_cache: dict[str, float] = {}  # ticker → timestamp of last failure
_NEG_CACHE_TTL = 3600  # 1 hour
_SCAN_BATCH_SIZE = 25  # parallel batch size for scanning


# ═══════════════════════════════════════════════════════════════════
# ENRICHMENT HELPERS — calibration, action state, trust, contradiction
# ═══════════════════════════════════════════════════════════════════


# ── Swing_Project helpers extracted → src/services/swing_analysis.py (Sprint 84) ────


def _honest_confidence_label(composite: float) -> dict:
    """Return honest labeling for confidence scores.

    CRITICAL: The composite score measures indicator alignment, NOT
    probability of profit. This function adds honest framing.
    """
    if composite >= 85:
        alignment = "Strong indicator alignment"
        honest_note = (
            "Indicators are well-aligned. This does NOT guarantee profit. "
            "No backtest validates this specific threshold."
        )
    elif composite >= 70:
        alignment = "Good indicator alignment"
        honest_note = (
            "Most indicators agree. This is a technical alignment score, "
            "not a win probability. Historical hit rate unknown."
        )
    elif composite >= 55:
        alignment = "Moderate indicator alignment"
        honest_note = (
            "Mixed signals. Some indicators support, others neutral. "
            "This is NOT a 55% win probability."
        )
    else:
        alignment = "Weak indicator alignment"
        honest_note = (
            "Indicators are poorly aligned. Low-quality setup. "
            "Consider waiting for better conditions."
        )

    return {
        "composite": composite,
        "label": alignment,
        "is_probability": False,
        "honest_note": honest_note,
        "what_this_measures": "Degree of technical indicator agreement (0-100)",
        "what_this_does_NOT_measure": "Probability of profit, expected return, or edge",
        "calibration_status": "uncalibrated — no realized hit-rate data yet",
    }


async def _days_to_earnings(ticker: str, mds) -> int | None:
    """Estimate days to next earnings for a ticker.

    Uses yfinance calendar if available, otherwise returns None.
    """
    try:
        import yfinance as yf

        def _fetch_cal():
            t = yf.Ticker(ticker)
            return t.calendar, getattr(t, "earnings_dates", None)

        cal, ed = await asyncio.to_thread(_fetch_cal)
        if cal is not None and not cal.empty:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            if hasattr(cal, "iloc"):
                for col in cal.columns:
                    val = cal[col].iloc[0]
                    if hasattr(val, "date"):
                        delta = (val - now).days
                        if delta >= 0:
                            return delta
        if ed is not None and not ed.empty:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            for dt in ed.index:
                if hasattr(dt, "tz_localize"):
                    dt = dt.tz_localize("UTC")
                delta = (dt - now).days
                if delta >= 0:
                    return int(delta)
    except Exception:
        pass
    return None


def _enrich_calibration(conf: dict, strategy: str) -> dict:
    """Build 6-layer calibrated confidence from 4-layer confidence output.

    Layers: forecast_probability, historical_reliability, uncertainty_band,
    data_confidence, execution_confidence, portfolio_fit_confidence.
    """
    composite = conf.get("composite", 50)
    cal = conf.get("calibration", {})
    bucket = cal.get("confidence_bucket", "medium")
    predicted_prob = cal.get("predicted_prob", composite / 100)

    # Uncertainty band: ±12% for high-confidence, ±18% for medium, ±25% for low
    band_half = {"high": 12, "medium": 18, "low": 25}.get(bucket, 18)
    low_bound = max(0, round(composite - band_half, 1))
    high_bound = min(100, round(composite + band_half, 1))

    return {
        "forecast_probability": round(predicted_prob, 3),
        "historical_reliability_bucket": bucket,
        "uncertainty_band": {"low": low_bound, "high": high_bound},
        "uncertainty_display": f"{low_bound:.0f}–{high_bound:.0f}%",
        "data_confidence": conf.get("data", {}).get("score", 50),
        "execution_confidence": conf.get("execution", {}).get("score", 50),
        "portfolio_fit_confidence": None,  # populated when portfolio context available
        "sample_size": None,  # populated from shadow tracker when available
        "calibration_note": "Brier-tracked; uncertainty bands are conformal estimates, not guarantees.",
        "display_recommendation": (
            f"{bucket.title()} confidence | {low_bound:.0f}–{high_bound:.0f}% range"
        ),
    }


def _compute_action_state(conf: dict, rr: float, trending: bool) -> dict:
    """Compute 5-tier action state: STRONG_BUY, BUY, WATCH, REDUCE, NO_TRADE, HEDGE."""
    tier = conf.get("decision_tier", "WATCH")
    sizing = conf.get("sizing", "")
    should_trade = conf.get("should_trade", False)
    abstain = conf.get("abstain_reason")

    return {
        "action": tier,
        "sizing_guidance": sizing,
        "should_trade": should_trade,
        "abstain_reason": abstain,
        "risk_reward": rr,
        "regime_aligned": trending,
        "display": f"{'✅' if should_trade else '⏸️'} {tier.replace('_', ' ').title()}",
    }


def _build_reasons_for(
    close, sma20, sma50, sma200, rsi, vol_ratio, i, strategy, trending
):
    """Build bullish evidence list."""
    reasons = []
    if close[i] > sma50[i] > sma200[i]:
        reasons.append("Strong uptrend: price > SMA50 > SMA200")
    elif close[i] > sma50[i]:
        reasons.append("Above SMA50 — uptrend intact")
    if 40 < rsi[i] < 70:
        reasons.append(f"RSI {rsi[i]:.0f} in healthy zone")
    if vol_ratio[i] > 1.5:
        reasons.append(
            f"Volume {vol_ratio[i]:.1f}x above average — institutional interest"
        )
    elif vol_ratio[i] > 1.0:
        reasons.append("Volume confirms move")
    if trending:
        reasons.append("Regime-aligned: trending market")
    if strategy == "swing" and rsi[i] < 40:
        reasons.append("RSI oversold — bounce potential")
    if strategy == "breakout" and vol_ratio[i] > 2.0:
        reasons.append("Breakout with surge volume — high conviction")
    return reasons[:5]


def _build_reasons_against(
    close, sma20, sma50, sma200, rsi, vol_ratio, atr_pct, i, strategy
):
    """Build bearish / caution evidence list."""
    reasons = []
    if rsi[i] > 70:
        reasons.append(f"RSI {rsi[i]:.0f} overbought — risk of pullback")
    if rsi[i] > 80:
        reasons.append("Extremely overbought — high reversal risk")
    if close[i] < sma200[i]:
        reasons.append("Below SMA200 — long-term downtrend")
    if vol_ratio[i] < 0.8:
        reasons.append("Below-average volume — weak conviction")
    if float(atr_pct[i]) > 0.04:
        reasons.append(
            f"High volatility ({float(atr_pct[i])*100:.1f}% ATR) — wider stops needed"
        )
    dist_sma20 = abs(close[i] - sma20[i]) / sma20[i] if sma20[i] > 0 else 0
    if dist_sma20 > 0.05:
        reasons.append(f"Extended {dist_sma20*100:.1f}% from SMA20 — may need pullback")
    if strategy == "mean_reversion" and close[i] < sma200[i]:
        reasons.append("Counter-trend trade in downtrend — higher failure rate")
    if not reasons:
        reasons.append("No significant bearish factors identified")
    return reasons[:5]


def _build_pre_mortem(strategy: str, trending: bool) -> str:
    """Most likely failure scenario for this trade."""
    pre_mortems = {
        "momentum": (
            "Momentum stalls at resistance and reverses on profit-taking"
            if trending
            else "False breakout in range-bound market — trapped longs"
        ),
        "breakout": (
            "Breakout fails on declining volume — price returns inside range"
            if not trending
            else "Breakout extends into exhaustion gap — sharp reversal"
        ),
        "swing": ("Bounce fails to hold — lower low confirms downtrend continuation"),
        "mean_reversion": (
            "Mean reversion premature — stock continues falling as trend accelerates"
        ),
    }
    return pre_mortems.get(strategy, "Unexpected macro event or sector-wide sell-off")


def _build_why_wait(conf: dict, rr: float) -> str | None:
    """Suggest conditions that would improve entry quality."""
    composite = conf.get("composite", 50)
    reasons = []
    if composite < 60:
        reasons.append("confidence below 60 — wait for stronger setup confirmation")
    if rr < 2.0:
        reasons.append(
            f"risk/reward {rr:.1f}:1 — wait for tighter stop or higher target"
        )
    timing = conf.get("timing", {}).get("score", 50)
    if timing < 45:
        reasons.append("timing score weak — wait for pullback to support")
    if not reasons:
        return None
    return "Consider waiting: " + "; ".join(reasons)


async def _scan_live_signals(limit: int = 10) -> tuple[list, dict]:
    """Scan watchlist for live signals using current market data.

    Returns (recommendations, strategy_scores) — same format as engine cache.
    Uses 6mo history + indicators to check all 4 strategies for each ticker.
    Results are cached for 5 minutes.
    """
    import time as _t

    import numpy as np

    now = _t.time()
    if _scan_cache["recs"] and (now - _scan_cache["ts"]) < _SCAN_CACHE_TTL:
        return _scan_cache["recs"][:limit], _scan_cache["scores"]

    mds = app.state.market_data
    recs = []
    strat_wins = {"momentum": 0, "breakout": 0, "swing": 0, "mean_reversion": 0}
    strat_total = {"momentum": 0, "breakout": 0, "swing": 0, "mean_reversion": 0}

    # Filter out negative-cached tickers
    active_tickers = [
        t
        for t in _SCAN_WATCHLIST
        if t not in _neg_cache or (now - _neg_cache[t]) > _NEG_CACHE_TTL
    ]
    logger.info(
        f"[Scanner] {len(active_tickers)}/{len(_SCAN_WATCHLIST)} tickers "
        f"({len(_SCAN_WATCHLIST) - len(active_tickers)} neg-cached)"
    )

    # Parallel batch fetch
    async def _fetch_one(ticker: str):
        try:
            hist = await mds.get_history(ticker, period="1y", interval="1d")
            if hist is None or hist.empty or len(hist) < 60:
                _neg_cache[ticker] = now  # skip next time
                return None
            return (ticker, hist)
        except Exception:
            _neg_cache[ticker] = now
            return None

    all_results = []
    for batch_start in range(0, len(active_tickers), _SCAN_BATCH_SIZE):
        batch = active_tickers[batch_start : batch_start + _SCAN_BATCH_SIZE]
        batch_results = await asyncio.gather(
            *[_fetch_one(t) for t in batch], return_exceptions=True
        )
        all_results.extend(
            r for r in batch_results if r is not None and not isinstance(r, Exception)
        )

    # Fetch SPY benchmark for RS computation
    spy_close = await _get_spy_close()

    for ticker, hist in all_results:
        try:
            if hist is None or hist.empty or len(hist) < 60:
                continue

            c_col = "Close" if "Close" in hist.columns else "close"
            v_col = "Volume" if "Volume" in hist.columns else "volume"
            close = hist[c_col].values.astype(float)
            volume = hist[v_col].values.astype(float)
            n = len(close)
            i = n - 1  # latest bar

            if n < 60:
                continue

            # ── Compute indicators (causal, no look-ahead) ──
            _ind = _compute_indicators(close, volume)
            sma20 = _ind["sma20"]
            sma50 = _ind["sma50"]
            sma200 = _ind["sma200"]
            rsi = _ind["rsi"]
            vol_ratio = _ind["vol_ratio"]
            atr_pct = _ind["atr_pct"]
            cur_atr = max(float(atr_pct[i]), 0.005)

            trending = bool(close[i] > sma50[i] and sma50[i] > sma200[i])

            # ── RS vs SPY ──
            rs_info = (
                _compute_rs_vs_benchmark(close, spy_close)
                if spy_close is not None
                else {
                    "rs_composite": 100.0,
                    "rs_1m": 100.0,
                    "rs_3m": 100.0,
                    "rs_6m": 100.0,
                    "rs_slope": 0.0,
                    "rs_status": "NEUTRAL",
                }
            )

            # ── Check each strategy ──
            _ST = SIGNAL_THRESHOLDS
            strategies = {
                "momentum": bool(
                    close[i] > sma20[i] > sma50[i]
                    and rsi[i] > _ST.rsi_momentum_low
                    and rsi[i] < _ST.rsi_momentum_high
                    and vol_ratio[i] > _ST.volume_confirmation
                ),
                "breakout": (
                    bool(
                        close[i] > float(np.max(close[max(0, i - 20) : i]))
                        and vol_ratio[i] > _ST.volume_surge_threshold
                        and close[i] > sma20[i]
                    )
                    if i > 20
                    else False
                ),
                "swing": (
                    bool(
                        rsi[i] < _ST.rsi_swing_entry
                        and close[i] > sma50[i] * (1 - _ST.swing_sma_distance)
                        and (close[i] > sma20[i] or close[i - 1] < sma20[i - 1])
                        and close[i] > close[i - 1]
                    )
                    if i > 1
                    else False
                ),
                "mean_reversion": bool(
                    rsi[i] < _ST.rsi_oversold
                    and close[i] < sma20[i] * (1 - _ST.mean_rev_sma_distance)
                    and vol_ratio[i] > _ST.volume_confirmation
                ),
            }

            # Strategy params
            strat_params = {
                "momentum": {
                    "stop": cur_atr * _ST.stop_atr_multiplier_momentum,
                    "target": _ST.target_trending if trending else _ST.target_normal,
                },
                "breakout": {
                    "stop": cur_atr * _ST.stop_atr_multiplier_breakout,
                    "target": (
                        _ST.target_breakout_trending
                        if trending
                        else _ST.target_breakout_normal
                    ),
                },
                "swing": {
                    "stop": cur_atr * _ST.stop_atr_multiplier_swing,
                    "target": (
                        _ST.target_swing_trending
                        if trending
                        else _ST.target_swing_normal
                    ),
                },
                "mean_reversion": {
                    "stop": cur_atr * _ST.stop_atr_multiplier_mean_rev,
                    "target": cur_atr * 3,
                },
            }

            for strat_name, triggered in strategies.items():
                strat_total[strat_name] += 1
                if not triggered:
                    continue
                strat_wins[strat_name] += 1

                params = strat_params[strat_name]
                # Enter at next bar's close to avoid look-ahead bias
                entry_idx = min(i + 1, len(close) - 1)
                entry_price = round(float(close[entry_idx]), 2)
                stop_price = round(entry_price * (1 - params["stop"]), 2)
                target_price = round(entry_price * (1 + params["target"]), 2)
                risk = entry_price - stop_price
                reward = target_price - entry_price
                rr = round(reward / risk, 1) if risk > 0 else 0

                # ── Phase 9: Pre-compute engines before confidence ──
                _structure = {}
                _entry_qual = {}
                _earnings = {}
                _fundamentals_brief = {}
                _portfolio_check = {}
                _gate_passed = True
                if _P9_ENGINES:
                    try:
                        _pg = PortfolioGate()
                        _gr = _pg.check(
                            ticker=ticker,
                            sector=_TICKER_SECTOR.get(ticker, "unknown"),
                            atr_risk_pct=float(atr_pct[i]) * 100,
                            current_positions=[
                                {
                                    "ticker": r["ticker"],
                                    "sector": r.get("sector", "unknown"),
                                    "size_pct": 5.0,
                                    "risk_pct": 1.0,
                                }
                                for r in recs
                            ],
                        )
                        _portfolio_check = _gr.to_dict()
                        if not _gr.allowed:
                            _gate_passed = False
                    except Exception as _e9:
                        logger.debug("[Phase9] PortfolioGate: %s", _e9)
                if _P9_ENGINES:
                    try:
                        h_col = "High" if "High" in hist.columns else "high"
                        l_col = "Low" if "Low" in hist.columns else "low"
                        _hi = hist[h_col].values.astype(float)
                        _lo = hist[l_col].values.astype(float)
                        _sd = StructureDetector()
                        _sr = _sd.analyze(close, _hi, _lo, volume)
                        _structure = _sr.to_dict()
                        # Use S/R for better stops/targets
                        _sup = _sr.nearest_support
                        _res = _sr.nearest_resistance
                        if _sup and _sup < entry_price:
                            stop_price = round(
                                max(stop_price, _sup * 0.995),
                                2,
                            )
                        if _res and _res > entry_price:
                            target_price = round(
                                min(target_price, _res * 0.99),
                                2,
                            )
                        risk = entry_price - stop_price
                        reward = target_price - entry_price
                        rr = round(reward / risk, 1) if risk > 0 else 0
                        _eq = EntryQualityEngine()
                        _eqr = _eq.assess(
                            close,
                            _hi,
                            _lo,
                            volume,
                            float(atr_pct[i]),
                            entry_price,
                            stop_price,
                            target_price,
                            _res,
                            _sup,
                            _TICKER_SECTOR.get(ticker, "unknown"),
                        )
                        _entry_qual = _eqr.to_dict()
                    except Exception as _e9:
                        logger.debug("[Phase9] StructureDetector/EntryQuality: %s", _e9)
                    try:
                        _earnings = get_earnings_info(ticker)
                    except Exception as _e9:
                        logger.debug("[Phase9] EarningsCalendar: %s", _e9)
                    try:
                        _fd = get_fundamentals(ticker)
                        _fundamentals_brief = {
                            "quality": _fd.get("quality_score", None),
                            "pe": _fd.get("valuation", {}).get("pe_trailing"),
                            "roe": _fd.get("profitability", {}).get("roe"),
                            "rev_growth": _fd.get("growth", {}).get("revenue_growth"),
                            "moat": _fd.get("moat_indicators", {}).get(
                                "has_moat", False
                            ),
                        }
                    except Exception as _e9:
                        logger.debug("[Phase9] FundamentalData: %s", _e9)

                # Confidence from 4-layer (now includes Phase 9 penalties)
                conf = _compute_4layer_confidence(
                    close,
                    sma20,
                    sma50,
                    sma200,
                    rsi,
                    atr_pct,
                    vol_ratio,
                    i,
                    volume,
                    trending,
                    structure_result=_structure,
                    entry_quality_result=_entry_qual,
                    earnings_info=_earnings,
                    fundamentals_info=_fundamentals_brief,
                    regime_label="UPTREND" if trending else "SIDEWAYS",
                    ticker_sector=_TICKER_SECTOR.get(ticker, "unknown"),
                )
                score = round(conf["composite"] / 10, 1)  # 0-10 scale
                if not _gate_passed:
                    score = max(0, score - 2.0)

                recs.append(
                    {
                        "ticker": ticker,
                        "symbol": ticker,
                        "score": score,
                        "confidence": conf["composite"],
                        "grade": conf["grade"] if _gate_passed else "F",
                        "direction": "LONG",
                        "strategy": strat_name,
                        "entry_price": entry_price,
                        "target_price": target_price,
                        "stop_price": stop_price,
                        "risk_reward": rr,
                        "regime": "UPTREND" if trending else "SIDEWAYS",
                        "rsi": round(float(rsi[i]), 1),
                        "vol_ratio": round(float(vol_ratio[i]), 2),
                        "atr_pct": round(float(atr_pct[i]) * 100, 2),
                        # ── Calibrated confidence (6-layer) ──
                        "calibrated_confidence": _enrich_calibration(conf, strat_name),
                        # ── Action state ──
                        "action_state": _compute_action_state(conf, rr, trending),
                        # ── Trust strip ──
                        "trust_strip": {
                            "mode": "SCAN",
                            "source": "yfinance",
                            "freshness": "delayed_15m",
                            "sample_size": None,
                            "assumptions": "gross returns, no commissions/slippage",
                            "feature_stage": "BETA",
                        },
                        # ── Contradiction / reasons against ──
                        "reasons_for": _build_reasons_for(
                            close,
                            sma20,
                            sma50,
                            sma200,
                            rsi,
                            vol_ratio,
                            i,
                            strat_name,
                            trending,
                        ),
                        "reasons_against": _build_reasons_against(
                            close,
                            sma20,
                            sma50,
                            sma200,
                            rsi,
                            vol_ratio,
                            atr_pct,
                            i,
                            strat_name,
                        ),
                        "invalidation": f"Close below ${stop_price}",
                        "pre_mortem": _build_pre_mortem(strat_name, trending),
                        "why_wait": _build_why_wait(conf, rr),
                        # ── Sprint 44: uncertainty + reliability ──
                        "honest_confidence": _honest_confidence_label(
                            conf["composite"]
                        ),
                        "reliability": {
                            "bucket": reliability_bucket(len(close) - 60),
                            "sample_size": len(close) - 60,
                            "note": reliability_note(len(close) - 60),
                        },
                        # ── Phase 9: new engines ──
                        "structure": _structure,
                        "entry_quality": _entry_qual,
                        "earnings": _earnings,
                        "fundamentals": _fundamentals_brief,
                        "portfolio_gate": _portfolio_check,
                        "rs": rs_info,
                        "sector": _TICKER_SECTOR.get(ticker, "unknown"),
                    }
                )
                # ── Wire Phase 9 feedback engines ──
                if _P9_ENGINES:
                    try:
                        _bm = BreakoutMonitor()
                        _bm.load()
                        _bm.register_breakout(
                            ticker=ticker,
                            breakout_price=entry_price,
                            pivot_price=stop_price,
                        )
                        _bm.save()
                    except Exception as _e9:
                        logger.debug("[Phase9] BreakoutMonitor: %s", _e9)
                    try:
                        get_journal().record(
                            ticker=ticker,
                            decision_tier=conf.get("grade", "C"),
                            composite_score=conf["composite"] * 100,
                            should_trade=score >= 7.0,
                            regime="UPTREND" if trending else "SIDEWAYS",
                            sector=_TICKER_SECTOR.get(ticker, "unknown"),
                            entry_price=entry_price,
                            stop_price=stop_price,
                            target_price=target_price,
                            extra={"strategy": strat_name, "rr": rr, "score": score},
                        )
                    except Exception as _e9:
                        logger.debug("[Phase9] DecisionJournal: %s", _e9)
        except Exception as exc:
            logger.debug(f"[Scanner] {ticker} skip: {exc}")
            continue

    # ── Fallback: if no strategy triggered, rank all tickers by strength ──
    if not recs:
        _fallback: list[tuple[str, dict]] = []
        for ticker in _SCAN_WATCHLIST:
            try:
                hist = await mds.get_history(ticker, period="1y", interval="1d")
                if hist is None or hist.empty or len(hist) < 60:
                    continue
                c_col = "Close" if "Close" in hist.columns else "close"
                v_col = "Volume" if "Volume" in hist.columns else "volume"
                close = hist[c_col].values.astype(float)
                volume = hist[v_col].values.astype(float)
                n = len(close)
                ii = n - 1
                _ind = _compute_indicators(close, volume)
                sma20 = _ind["sma20"]
                sma50 = _ind["sma50"]
                sma200 = _ind["sma200"]
                rsi_v = _ind["rsi"]
                vol_ratio_v = _ind["vol_ratio"]
                atr_pct_v = _ind["atr_pct"]
                cur_atr = max(float(atr_pct_v[ii]), 0.005)
                trending = bool(close[ii] > sma50[ii] and sma50[ii] > sma200[ii])

                # ── Phase 9: Pre-compute for fallback path ──
                _fb_structure = {}
                _fb_entry_qual = {}
                _fb_earnings = {}
                _fb_fundamentals = {}
                if _P9_ENGINES:
                    try:
                        h_col = "High" if "High" in hist.columns else "high"
                        l_col = "Low" if "Low" in hist.columns else "low"
                        _hi = hist[h_col].values.astype(float)
                        _lo = hist[l_col].values.astype(float)
                        _sd = StructureDetector()
                        _sr = _sd.analyze(close, _hi, _lo, volume)
                        _fb_structure = _sr.to_dict()
                    except Exception as _e9:
                        logger.debug("[Phase9-fb] structure: %s", _e9)
                    try:
                        _fb_earnings = get_earnings_info(ticker)
                    except Exception as _e9:
                        logger.debug("[Phase9-fb] earnings: %s", _e9)
                    try:
                        _fd = get_fundamentals(ticker)
                        _fb_fundamentals = {
                            "quality": _fd.get("quality_score"),
                            "pe": _fd.get("valuation", {}).get("pe_trailing"),
                            "roe": _fd.get("profitability", {}).get("roe"),
                            "rev_growth": _fd.get("growth", {}).get("revenue_growth"),
                            "moat": _fd.get("moat_indicators", {}).get(
                                "has_moat", False
                            ),
                        }
                    except Exception as _e9:
                        logger.debug("[Phase9-fb] fundamentals: %s", _e9)

                conf = _compute_4layer_confidence(
                    close,
                    sma20,
                    sma50,
                    sma200,
                    rsi_v,
                    atr_pct_v,
                    vol_ratio_v,
                    ii,
                    volume,
                    trending,
                    structure_result=_fb_structure,
                    entry_quality_result=_fb_entry_qual,
                    earnings_info=_fb_earnings,
                    fundamentals_info=_fb_fundamentals,
                    regime_label="UPTREND" if trending else "SIDEWAYS",
                    ticker_sector=_TICKER_SECTOR.get(ticker, "unknown"),
                )
                score = round(conf["composite"] / 10, 1)
                entry_price = round(float(close[ii]), 2)
                stop_price = round(entry_price * (1 - cur_atr * 2), 2)
                target_price = round(entry_price * 1.05, 2)
                risk = entry_price - stop_price
                reward = target_price - entry_price
                rr = round(reward / risk, 1) if risk > 0 else 0

                _fallback.append(
                    (
                        ticker,
                        {
                            "ticker": ticker,
                            "symbol": ticker,
                            "score": score,
                            "confidence": conf["composite"],
                            "grade": conf["grade"],
                            "direction": "LONG",
                            "strategy": "watch",
                            "entry_price": entry_price,
                            "target_price": target_price,
                            "stop_price": stop_price,
                            "risk_reward": rr,
                            "regime": "UPTREND" if trending else "SIDEWAYS",
                            "rsi": round(float(rsi_v[ii]), 1),
                            "vol_ratio": round(float(vol_ratio_v[ii]), 2),
                            "atr_pct": round(float(atr_pct_v[ii]) * 100, 2),
                            "calibrated_confidence": _enrich_calibration(
                                conf, "momentum"
                            ),
                            "action_state": _compute_action_state(conf, rr, trending),
                            "trust_strip": {
                                "mode": "WATCH",
                                "source": "yfinance",
                                "freshness": "delayed_15m",
                                "sample_size": None,
                                "assumptions": "no entry criteria met — ranked by technical strength",
                                "feature_stage": "BETA",
                            },
                            "reasons_for": _build_reasons_for(
                                close,
                                sma20,
                                sma50,
                                sma200,
                                rsi_v,
                                vol_ratio_v,
                                ii,
                                "momentum",
                                trending,
                            ),
                            "reasons_against": _build_reasons_against(
                                close,
                                sma20,
                                sma50,
                                sma200,
                                rsi_v,
                                vol_ratio_v,
                                atr_pct_v,
                                ii,
                                "momentum",
                            ),
                            "invalidation": f"Close below ${stop_price}",
                            "pre_mortem": "No strategy triggered — watch only",
                            "why_wait": "Wait for a defined entry setup before committing capital",
                            # Phase 9 fields (from pre-computed results)
                            "structure": _fb_structure,
                            "entry_quality": _fb_entry_qual,
                            "earnings": _fb_earnings,
                            "fundamentals": _fb_fundamentals,
                            "portfolio_gate": {},
                            "rs": (
                                _compute_rs_vs_benchmark(close, spy_close)
                                if spy_close is not None
                                else {"rs_composite": 100.0, "rs_status": "NEUTRAL"}
                            ),
                            "sector": _TICKER_SECTOR.get(ticker, "unknown"),
                        },
                    )
                )
            except Exception as _e_fb:
                logger.debug("[Scanner-fb] %s skip: %s", ticker, _e_fb)
                continue
        _fallback.sort(key=lambda x: x[1]["score"], reverse=True)
        recs = [r for _, r in _fallback[:limit]]
        logger.info(
            f"[Scanner] no strategy triggered — returning top {len(recs)} by strength"
        )

    # Sort by score desc
    recs.sort(key=lambda r: r["score"], reverse=True)

    # ── Sector correlation guard (P3) ──
    # Cap signals per sector cluster to prevent hidden concentration.
    # Walk the sorted list top-down; skip if sector already at capacity.
    sector_counts: dict[str, int] = {}
    filtered_recs: list = []
    demoted: list = []
    for rec in recs:
        sector = _TICKER_SECTOR.get(rec["ticker"], "Other")
        rec["sector"] = sector
        cur = sector_counts.get(sector, 0)
        if cur < _MAX_SIGNALS_PER_SECTOR:
            sector_counts[sector] = cur + 1
            filtered_recs.append(rec)
        else:
            rec["demoted_reason"] = (
                f"Sector cap ({sector}: {_MAX_SIGNALS_PER_SECTOR} max)"
            )
            demoted.append(rec)
    recs = filtered_recs  # demoted signals dropped from active list

    # Strategy scores (0-10 scale)
    scores = {}
    for s in strat_wins:
        total = strat_total[s]
        wins = strat_wins[s]
        scores[s] = round((wins / total * 10) if total > 0 else 5.0, 1)

    _scan_cache["recs"] = recs
    _scan_cache["scores"] = scores
    _scan_cache["ts"] = now
    _scan_cache["demoted"] = demoted
    logger.info(
        f"[Scanner] scanned {len(_SCAN_WATCHLIST)} tickers → "
        f"{len(recs)} signals ({len(demoted)} demoted by sector cap)"
    )
    return recs[:limit], scores


# ── P3: wire scan_signals onto app.state so routers never import from main ──
app.state.scan_signals = _scan_live_signals


@app.get("/api/recommendations", tags=["decision-layer"])
async def get_recommendations(limit: int = Query(10, ge=1, le=50)):
    """Get ranked trade recommendations.

    Priority: engine cache → live scanner fallback.
    The live scanner checks 24 popular tickers across 4 strategies
    using real-time market data when the engine is idle.
    """
    try:
        engine = _get_engine()
        regime = await _get_regime()
        regime_dict = (
            regime
            if isinstance(regime, dict)
            else (
                regime.__dict__
                if hasattr(regime, "__dict__")
                else {"label": str(regime)}
            )
        )
        regime_dict = _sanitize_for_json(regime_dict)

        # ── Read cached recommendations from live engine ──
        cached_recs: list = []
        strategy_scores: dict = {}
        no_trade_reason: str | None = None
        mode = "LIVE"

        if engine:
            cached_recs = list(getattr(engine, "_cached_recommendations", []))[:limit]
            strategy_scores = getattr(engine, "_cached_leaderboard", {})
            if hasattr(engine, "_no_trade_card") and engine._no_trade_card:
                no_trade_reason = str(engine._no_trade_card)
            if getattr(engine, "dry_run", False):
                mode = "PAPER"
        else:
            mode = "OFFLINE"

        # ── Fallback: live scanner when engine has no signals ──
        source = "engine_cache"
        scan_meta = None
        if not cached_recs:
            try:
                scanned, scan_scores = await _scan_live_signals(limit)
                tickers_checked = len(_SCAN_WATCHLIST)
                scan_meta = {
                    "tickers_checked": tickers_checked,
                    "signals_found": len(scanned),
                    "strategies": ["momentum", "breakout", "swing", "mean_reversion"],
                    "cache_ttl_sec": _SCAN_CACHE_TTL,
                }
                if scanned:
                    cached_recs = scanned
                    strategy_scores = scan_scores
                    source = "live_scanner"
                    mode = "SCAN"
                else:
                    source = "live_scanner"
                    mode = "SCAN"
                    if not no_trade_reason:
                        no_trade_reason = (
                            f"✅ Scanner ran successfully — checked "
                            f"{tickers_checked} tickers × 4 strategies. "
                            f"No setups met entry criteria right now. "
                            f"This is normal — it means the system is being "
                            f"selective. Check back in a few minutes."
                        )
            except Exception as exc:
                logger.warning(f"[Scanner] fallback failed: {exc}")
                source = "scanner_error"
                no_trade_reason = (
                    f"⚠ Scanner encountered an error: {exc}. "
                    "This is a system issue, not a market condition. "
                    "Try refreshing in a moment."
                )

        # ── Data freshness check (P3: stale data detection) ──
        scan_ts = _scan_cache.get("ts", 0.0) if _scan_cache else 0.0
        data_freshness = _check_data_freshness(
            scan_ts if scan_ts > 0 else None,
            label="scanner",
        )

        # ── Portfolio heat snapshot ──
        portfolio_heat_summary = None
        try:
            from src.engines.portfolio_heat import PortfolioHeatEngine

            phe = PortfolioHeatEngine()
            portfolio_heat_summary = phe.snapshot()
        except Exception:
            pass

        # ── Shadow-mode: record predictions for calibration ──
        try:
            from src.engines.shadow_tracker import shadow_tracker

            for rec in cached_recs:
                shadow_tracker.record_prediction(
                    ticker=rec.get("ticker", ""),
                    direction=rec.get("direction", "LONG"),
                    confidence=rec.get("confidence", 50),
                    strategy=rec.get("strategy", ""),
                    entry_price=rec.get("entry_price", 0),
                    target_price=rec.get("target_price", 0),
                    stop_price=rec.get("stop_price", 0),
                )
        except Exception:
            pass

        return _sanitize_for_json(
            {
                "status": "ok",
                "mode": mode,
                "regime": regime_dict,
                "recommendations": cached_recs,
                "count": len(cached_recs),
                "strategy_scores": strategy_scores,
                "no_trade_reason": no_trade_reason,
                "source": source,
                "scan_meta": scan_meta,
                "data_freshness": data_freshness,
                "portfolio_heat": portfolio_heat_summary,
                "trust_strip": {
                    "mode": mode,
                    "source": source,
                    "freshness": data_freshness,
                    "assumptions": "gross returns, no commissions or slippage applied",
                    "feature_stage": (
                        "PRODUCTION" if source == "engine_cache" else "BETA"
                    ),
                },
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            }
        )
    except Exception as e:
        logger.error(f"Recommendations endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/leaderboard", tags=["decision-layer"])
async def get_strategy_leaderboard():
    """Get strategy health scores and lifecycle state."""
    try:
        from src.engines.strategy_leaderboard import StrategyLeaderboard

        lb = StrategyLeaderboard()
        scores = lb.get_strategy_scores()
        rankings = lb.get_rankings()

        return {
            "status": "ok",
            "strategy_scores": scores,
            "rankings": rankings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Leaderboard endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/health", tags=["monitoring"])
async def api_health():
    """Engine health-check endpoint for monitoring."""
    try:
        engine = _get_engine()
        if engine:
            return await engine.health_check()
        return {
            "status": "ok",
            "engine": "not_initialised",
            "market_data": app.state.market_data.cache_stats(),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ─────────────────────────────────────────────────────────────
# Operator Console — enriched status for Phase 3
# ─────────────────────────────────────────────────────────────
@app.get("/api/ops/status", tags=["monitoring"])
async def ops_status():
    """Phase 3: Rich operator status for the Operator Console surface."""
    import time as _time

    engine = _get_engine()
    uptime_s = (datetime.now(timezone.utc) - startup_time).total_seconds()

    # Uptime formatting
    days = int(uptime_s // 86400)
    hours = int((uptime_s % 86400) // 3600)
    minutes = int((uptime_s % 3600) // 60)
    uptime_str = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"

    # Engine metrics
    running = False
    cycle_count = 0
    signals_today = 0
    trades_today = 0
    circuit_breaker = False
    circuit_breaker_reason = ""
    dry_run = True
    last_cycle = None
    cached_recs = 0

    if engine:
        running = bool(getattr(engine, "running", getattr(engine, "_running", False)))
        dry_run = getattr(engine, "dry_run", True)
        cycle_count = getattr(engine, "cycle_count", 0)
        signals_today = getattr(engine, "signals_today", 0)
        trades_today = getattr(engine, "trades_today", 0)
        circuit_breaker = getattr(engine, "circuit_breaker_triggered", False)
        circuit_breaker_reason = getattr(engine, "circuit_breaker_reason", "")
        cached_recs = len(getattr(engine, "_cached_recommendations", []))
        lc = getattr(engine, "last_cycle_time", None)
        if lc:
            last_cycle = str(lc)

    # Component health
    components = {}
    try:
        if engine:
            hc = await engine.health_check()
            components = hc.get("components", {})
    except Exception:
        pass

    try:
        from src.services.data_freshness_service import freshness_report

        fr = await freshness_report(app.state.market_data)
        components["market_data"] = fr.get("worst_tier") == "FRESH" or any(
            s.get("ok") for s in (fr.get("streams") or [])
        )
    except Exception:
        components.setdefault("market_data", False)

    # Market data stats
    cache_stats = {}
    try:
        cache_stats = app.state.market_data.cache_stats()
    except Exception:
        pass

    # Latency probe (time a simple regime fetch)
    t0 = _time.monotonic()
    try:
        await _get_regime()
        regime_latency_ms = round((_time.monotonic() - t0) * 1000, 1)
    except Exception:
        regime_latency_ms = -1

    return _sanitize_for_json(
        {
            "uptime": uptime_str,
            "uptime_seconds": round(uptime_s),
            "startup_time": startup_time.isoformat() + "Z",
            "version": APP_VERSION,
            "engine": {
                "running": running,
                "dry_run": dry_run,
                "cycle_count": cycle_count,
                "signals_today": signals_today,
                "trades_today": trades_today,
                "cached_recommendations": cached_recs,
                "circuit_breaker": circuit_breaker,
                "circuit_breaker_reason": circuit_breaker_reason,
                "last_cycle": last_cycle,
            },
            "components": components,
            "cache_stats": cache_stats,
            "latency": {
                "regime_ms": regime_latency_ms,
            },
            "trust": {
                "mode": "PAPER" if dry_run else "LIVE",
                "source": "engine + system",
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
            "phase9_engines": {
                "loaded": _P9_ENGINES,
                "breakout_monitor": (
                    {"active": len(getattr(BreakoutMonitor, "_active", {}))}
                    if _P9_ENGINES
                    else {}
                ),
                "decision_journal": (
                    {"entries": len(getattr(get_journal(), "_decisions", []))}
                    if _P9_ENGINES
                    else {}
                ),
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
                    if _P9_ENGINES
                    else []
                ),
            },
        }
    )


@app.get("/api/ops/endpoints", tags=["monitoring"])
async def ops_endpoints():
    """Phase 3: List all registered API endpoints for Data Catalog."""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method in ("GET", "POST", "PUT", "DELETE"):
                    tag = ""
                    if hasattr(route, "tags") and route.tags:
                        tag = route.tags[0]
                    desc = ""
                    if route.endpoint and route.endpoint.__doc__:
                        desc = route.endpoint.__doc__.strip().split("\n")[0]
                    routes.append(
                        {
                            "method": method,
                            "path": route.path,
                            "tag": tag,
                            "description": desc,
                        }
                    )
    routes.sort(key=lambda r: (r["path"], r["method"]))
    return {
        "count": len(routes),
        "endpoints": routes,
    }


# ═══════════════════════════════════════════════════════════════
# STRATEGY FACTORY — AI-assisted automated strategy generation,
# backtesting, scoring, walk-forward & Monte Carlo validation
# ═══════════════════════════════════════════════════════════════

# In-memory strategy library
_strategy_library: list = []
_factory_running: bool = False

# Strategy templates with parameterizable entry/exit logic
_STRATEGY_TEMPLATES = [
    {
        "id": "volume_momentum_breakout",
        "name": "Volume Momentum Breakout",
        "family": "momentum",
        "desc": "Buy when price breaks above N-day high on elevated volume with RSI confirmation",
        "params": {
            "lookback": [10, 20, 30],
            "vol_mult": [1.3, 1.5, 2.0],
            "rsi_min": [50, 55, 60],
        },
    },
    {
        "id": "atr_channel_breakout",
        "name": "ATR Channel Breakout",
        "family": "breakout",
        "desc": "Buy when price exceeds SMA + ATR multiplier, exit on SMA - ATR",
        "params": {
            "sma_len": [20, 30, 50],
            "atr_mult": [1.5, 2.0, 2.5],
            "atr_len": [14, 20],
        },
    },
    {
        "id": "macd_ema_hybrid",
        "name": "MACD EMA Hybrid",
        "family": "trend",
        "desc": "MACD bullish crossover above zero line + price above dual EMA filter",
        "params": {
            "fast": [8, 12],
            "slow": [21, 26],
            "signal": [7, 9],
            "ema_filter": [50, 100],
        },
    },
    {
        "id": "triple_ema_momentum",
        "name": "Triple EMA Momentum",
        "family": "trend",
        "desc": "Buy when EMA8 > EMA21 > EMA55 and momentum accelerating",
        "params": {"fast": [5, 8], "mid": [13, 21], "slow": [34, 55]},
    },
    {
        "id": "rsi_mean_reversion",
        "name": "RSI Mean Reversion",
        "family": "mean_reversion",
        "desc": "Buy oversold RSI bounces near MA support with volume confirmation",
        "params": {
            "rsi_len": [7, 14],
            "rsi_entry": [25, 30, 35],
            "rsi_exit": [60, 70],
            "ma_len": [20, 50],
        },
    },
    {
        "id": "dual_rsi_trend_filter",
        "name": "Dual RSI Trend Filter",
        "family": "mean_reversion",
        "desc": "Short-term RSI oversold + long-term RSI above 50 (trend filter)",
        "params": {
            "rsi_fast": [3, 5, 7],
            "rsi_slow": [14, 21],
            "rsi_fast_entry": [15, 25],
            "rsi_slow_min": [45, 50],
        },
    },
    {
        "id": "bollinger_breakout",
        "name": "Bollinger Band Breakout",
        "family": "breakout",
        "desc": "Buy squeeze release: price breaks upper BB after narrow bandwidth period",
        "params": {
            "bb_len": [20, 30],
            "bb_std": [1.5, 2.0, 2.5],
            "squeeze_pct": [0.03, 0.05],
        },
    },
    {
        "id": "stochastic_rsi_reversal",
        "name": "Stochastic RSI Reversal",
        "family": "mean_reversion",
        "desc": "StochRSI cross from oversold zone + price above MA support",
        "params": {
            "stoch_len": [14],
            "rsi_len": [14],
            "k_smooth": [3, 5],
            "d_smooth": [3, 5],
            "entry_level": [20, 30],
        },
    },
    {
        "id": "macd_crossover",
        "name": "MACD Crossover",
        "family": "trend",
        "desc": "Classic MACD signal line crossover with histogram confirmation",
        "params": {"fast": [12], "slow": [26], "signal": [9], "hist_min": [0, 0.1]},
    },
]


def _generate_strategy_code(template: dict, params: dict) -> str:
    """Generate executable Python signal code for a strategy variant."""
    tid = template["id"]
    lines = [
        "def generate_signals(df):",
        "    import numpy as np",
        "    sig = pd.Series(0, index=df.index)",
        "    close = df['Close'].values",
        "    volume = df['Volume'].values",
        "",
    ]

    if tid == "volume_momentum_breakout":
        lb, vm, rmin = (
            params.get("lookback", 20),
            params.get("vol_mult", 1.5),
            params.get("rsi_min", 55),
        )
        lines += [
            f"    vol_ma = pd.Series(volume).rolling({lb}).mean().values",
            f"    high_vol = volume > vol_ma * {vm}",
            "    rsi = ta.momentum.rsi(df['Close'], window=14).values",
            f"    hi_n = pd.Series(close).rolling({lb}).max().shift(1).values",
            f"    for i in range({lb}, len(close)):",
            f"        if close[i] > hi_n[i] and high_vol[i] and rsi[i] > {rmin}:",
            "            sig.iloc[i] = 1",
            "        elif rsi[i] > 75 or close[i] < pd.Series(close).rolling(10).mean().iloc[i]:",
            "            sig.iloc[i] = -1",
        ]
    elif tid == "atr_channel_breakout":
        sl, am, al = (
            params.get("sma_len", 20),
            params.get("atr_mult", 2.0),
            params.get("atr_len", 14),
        )
        lines += [
            f"    sma = pd.Series(close).rolling({sl}).mean().values",
            "    tr = np.maximum(df['High'].values-df['Low'].values, np.abs(df['High'].values-np.roll(close,1)))",
            f"    atr = pd.Series(tr).rolling({al}).mean().values",
            f"    upper = sma + atr * {am}",
            f"    lower = sma - atr * {am}",
            f"    for i in range({max(sl, al)}, len(close)):",
            "        if close[i] > upper[i]: sig.iloc[i] = 1",
            "        elif close[i] < lower[i]: sig.iloc[i] = -1",
        ]
    elif tid == "macd_ema_hybrid":
        f, s, sg, ef = (
            params.get("fast", 12),
            params.get("slow", 26),
            params.get("signal", 9),
            params.get("ema_filter", 50),
        )
        lines += [
            f"    ema_f = pd.Series(close).ewm(span={f}).mean().values",
            f"    ema_s = pd.Series(close).ewm(span={s}).mean().values",
            "    macd = ema_f - ema_s",
            f"    macd_sig = pd.Series(macd).ewm(span={sg}).mean().values",
            f"    ema_filt = pd.Series(close).ewm(span={ef}).mean().values",
            f"    for i in range({ef}, len(close)):",
            "        if macd[i] > macd_sig[i] and macd[i] > 0 and close[i] > ema_filt[i]: sig.iloc[i] = 1",
            "        elif macd[i] < macd_sig[i]: sig.iloc[i] = -1",
        ]
    elif tid == "triple_ema_momentum":
        f, m, s = params.get("fast", 8), params.get("mid", 21), params.get("slow", 55)
        lines += [
            f"    e1 = pd.Series(close).ewm(span={f}).mean().values",
            f"    e2 = pd.Series(close).ewm(span={m}).mean().values",
            f"    e3 = pd.Series(close).ewm(span={s}).mean().values",
            f"    for i in range({s}, len(close)):",
            "        if e1[i] > e2[i] > e3[i] and e1[i] > e1[i-1]: sig.iloc[i] = 1",
            "        elif e1[i] < e2[i]: sig.iloc[i] = -1",
        ]
    elif tid == "rsi_mean_reversion":
        rl, re, rx, ml = (
            params.get("rsi_len", 14),
            params.get("rsi_entry", 30),
            params.get("rsi_exit", 70),
            params.get("ma_len", 20),
        )
        lines += [
            f"    rsi = ta.momentum.rsi(df['Close'], window={rl}).values",
            f"    ma = pd.Series(close).rolling({ml}).mean().values",
            "    vol_ma = pd.Series(volume).rolling(20).mean().values",
            f"    for i in range({max(rl, ml)}, len(close)):",
            f"        if rsi[i] < {re} and close[i] > ma[i] * 0.97 and volume[i] > vol_ma[i]:",
            "            sig.iloc[i] = 1",
            f"        elif rsi[i] > {rx}: sig.iloc[i] = -1",
        ]
    elif tid == "dual_rsi_trend_filter":
        rf, rs, rfe, rsm = (
            params.get("rsi_fast", 5),
            params.get("rsi_slow", 14),
            params.get("rsi_fast_entry", 20),
            params.get("rsi_slow_min", 50),
        )
        lines += [
            f"    rsi_f = ta.momentum.rsi(df['Close'], window={rf}).values",
            f"    rsi_s = ta.momentum.rsi(df['Close'], window={rs}).values",
            f"    for i in range({rs}+5, len(close)):",
            f"        if rsi_f[i] < {rfe} and rsi_s[i] > {rsm}: sig.iloc[i] = 1",
            "        elif rsi_f[i] > 80: sig.iloc[i] = -1",
        ]
    elif tid == "bollinger_breakout":
        bl, bs, sq = (
            params.get("bb_len", 20),
            params.get("bb_std", 2.0),
            params.get("squeeze_pct", 0.04),
        )
        lines += [
            f"    sma = pd.Series(close).rolling({bl}).mean().values",
            f"    std = pd.Series(close).rolling({bl}).std().values",
            f"    upper = sma + std * {bs}",
            f"    lower = sma - std * {bs}",
            "    bw = (upper - lower) / sma",
            f"    bw_ma = pd.Series(bw).rolling({bl}).mean().values",
            f"    for i in range({bl}+5, len(close)):",
            f"        if bw[i-1] < {sq} and close[i] > upper[i]: sig.iloc[i] = 1",
            "        elif close[i] < sma[i]: sig.iloc[i] = -1",
        ]
    elif tid == "stochastic_rsi_reversal":
        stl, rl, ks, ds, el = (
            params.get("stoch_len", 14),
            params.get("rsi_len", 14),
            params.get("k_smooth", 3),
            params.get("d_smooth", 3),
            params.get("entry_level", 20),
        )
        lines += [
            f"    rsi = ta.momentum.rsi(df['Close'], window={rl}).values",
            "    rsi_s = pd.Series(rsi)",
            f"    ll = rsi_s.rolling({stl}).min()",
            f"    hh = rsi_s.rolling({stl}).max()",
            f"    k = ((rsi_s - ll) / (hh - ll + 1e-10) * 100).rolling({ks}).mean().values",
            f"    d = pd.Series(k).rolling({ds}).mean().values",
            "    ma50 = pd.Series(close).rolling(50).mean().values",
            "    for i in range(55, len(close)):",
            f"        if k[i] > d[i] and k[i-1] <= d[i-1] and k[i] < {el+20} and close[i] > ma50[i]:",
            "            sig.iloc[i] = 1",
            "        elif k[i] > 80 and k[i] < d[i]: sig.iloc[i] = -1",
        ]
    elif tid == "macd_crossover":
        f, s, sg = (
            params.get("fast", 12),
            params.get("slow", 26),
            params.get("signal", 9),
        )
        hm = params.get("hist_min", 0)
        lines += [
            f"    ema_f = pd.Series(close).ewm(span={f}).mean().values",
            f"    ema_s = pd.Series(close).ewm(span={s}).mean().values",
            "    macd = ema_f - ema_s",
            f"    macd_sig = pd.Series(macd).ewm(span={sg}).mean().values",
            "    hist = macd - macd_sig",
            f"    for i in range({s}+{sg}, len(close)):",
            f"        if macd[i] > macd_sig[i] and macd[i-1] <= macd_sig[i-1] and hist[i] > {hm}:",
            "            sig.iloc[i] = 1",
            "        elif macd[i] < macd_sig[i] and macd[i-1] >= macd_sig[i-1]:",
            "            sig.iloc[i] = -1",
        ]

    lines.append("    return sig")
    return "\n".join(lines)


def _run_strategy_backtest(close, high, low, volume, signals, dates_idx):
    """Run a vectorized backtest given signal array. Returns metrics dict."""
    import numpy as np

    n = len(close)
    if n < 60:
        return None

    trades = []
    position = None
    atr_arr = np.zeros(n)
    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))),
    )
    for i in range(14, n):
        atr_arr[i] = np.mean(tr[max(0, i - 14) : i])

    for i in range(50, n):
        if position is None and signals[i] == 1:
            position = {"idx": i, "price": close[i], "high": close[i]}
        elif position is not None:
            position["high"] = max(position["high"], close[i])
            # Exit conditions
            stop_hit = close[i] < position["price"] * 0.95  # 5% hard stop
            trail_hit = close[i] < position["high"] * 0.93  # 7% trailing
            sig_exit = signals[i] == -1
            time_exit = (i - position["idx"]) > 60  # max 60 bars
            if stop_hit or trail_hit or sig_exit or time_exit:
                pnl_pct = (close[i] / position["price"] - 1) * 100
                trades.append(
                    {
                        "entry_idx": position["idx"],
                        "exit_idx": i,
                        "entry_price": round(position["price"], 2),
                        "exit_price": round(close[i], 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "bars_held": i - position["idx"],
                        "exit_reason": (
                            "stop"
                            if stop_hit
                            else (
                                "trail"
                                if trail_hit
                                else "signal" if sig_exit else "time"
                            )
                        ),
                    }
                )
                position = None

    # Close remaining
    if position is not None:
        pnl_pct = (close[-1] / position["price"] - 1) * 100
        trades.append(
            {
                "entry_idx": position["idx"],
                "exit_idx": n - 1,
                "entry_price": round(position["price"], 2),
                "exit_price": round(close[-1], 2),
                "pnl_pct": round(pnl_pct, 2),
                "bars_held": n - 1 - position["idx"],
                "exit_reason": "end",
            }
        )

    if not trades:
        return None

    returns = [t["pnl_pct"] / 100 for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0.001

    # Equity curve
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r))

    # Max drawdown
    peak = equity[0]
    max_dd = 0
    for v in equity:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    # Sharpe
    if len(returns) > 1:
        avg_r = np.mean(returns)
        std_r = np.std(returns)
        sharpe = (
            round(
                avg_r
                / std_r
                * np.sqrt(252 / max(1, np.mean([t["bars_held"] for t in trades]))),
                2,
            )
            if std_r > 0
            else 0
        )
    else:
        sharpe = 0

    net_return = round((equity[-1] / 100 - 1) * 100, 2)
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0

    return {
        "trade_count": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "profit_factor": profit_factor,
        "sharpe": sharpe,
        "max_drawdown": round(max_dd, 2),
        "net_return": net_return,
        "avg_win": round(np.mean(wins) * 100, 2) if wins else 0,
        "avg_loss": round(np.mean(losses) * 100, 2) if losses else 0,
        "avg_bars_held": round(np.mean([t["bars_held"] for t in trades]), 1),
        "trades": trades[-20:],  # last 20 for detail view
        "equity": equity,
    }


def _walk_forward_test(close, high, low, volume, signals, n_folds=5):
    """Walk-forward analysis: train/test on rolling windows."""
    import numpy as np

    n = len(close)
    fold_size = n // n_folds
    if fold_size < 60:
        return None

    results = []
    for fold in range(1, n_folds):
        oos_start = fold * fold_size
        oos_end = min(oos_start + fold_size, n)
        m = _run_strategy_backtest(
            close[oos_start:oos_end],
            high[oos_start:oos_end],
            low[oos_start:oos_end],
            volume[oos_start:oos_end],
            signals[oos_start:oos_end],
            None,
        )
        if m:
            results.append(
                {
                    "fold": fold,
                    "net_return": m["net_return"],
                    "sharpe": m["sharpe"],
                    "profit_factor": m["profit_factor"],
                    "max_drawdown": m["max_drawdown"],
                    "trade_count": m["trade_count"],
                    "win_rate": m["win_rate"],
                }
            )

    if not results:
        return None

    avg_return = round(np.mean([r["net_return"] for r in results]), 2)
    avg_sharpe = round(np.mean([r["sharpe"] for r in results]), 2)
    consistency = round(
        sum(1 for r in results if r["net_return"] > 0) / len(results) * 100, 1
    )

    return {
        "folds": results,
        "avg_return": avg_return,
        "avg_sharpe": avg_sharpe,
        "consistency": consistency,
        "passed": consistency >= 60 and avg_sharpe > 0.3,
    }


def _monte_carlo_test(returns, n_sims=500):
    """Monte Carlo stress test: shuffle trade order, measure tail risk."""
    import numpy as np

    if len(returns) < 5:
        return None

    final_equities = []
    max_drawdowns = []

    for _ in range(n_sims):
        shuffled = np.random.permutation(returns)
        eq = [100.0]
        for r in shuffled:
            eq.append(eq[-1] * (1 + r))
        final_equities.append(eq[-1])

        peak = eq[0]
        mdd = 0
        for v in eq:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100
            if dd < mdd:
                mdd = dd
        max_drawdowns.append(mdd)

    final_equities.sort()
    max_drawdowns.sort()

    return {
        "n_sims": n_sims,
        "median_return": round((np.median(final_equities) / 100 - 1) * 100, 2),
        "p5_return": round((final_equities[int(n_sims * 0.05)] / 100 - 1) * 100, 2),
        "p25_return": round((final_equities[int(n_sims * 0.25)] / 100 - 1) * 100, 2),
        "p75_return": round((final_equities[int(n_sims * 0.75)] / 100 - 1) * 100, 2),
        "p95_return": round((final_equities[int(n_sims * 0.95)] / 100 - 1) * 100, 2),
        "prob_loss": round(sum(1 for e in final_equities if e < 100) / n_sims * 100, 1),
        "median_max_dd": round(np.median(max_drawdowns), 2),
        "worst_dd": round(min(max_drawdowns), 2),
        "prob_ruin": round(sum(1 for e in final_equities if e < 70) / n_sims * 100, 1),
        "passed": sum(1 for e in final_equities if e < 100) / n_sims < 0.4
        and min(max_drawdowns) > -50,
    }


# Pass/fail rules
_PASS_RULES = {
    "min_profit_factor": 1.3,
    "min_sharpe": 0.4,
    "max_drawdown": -25.0,
    "min_win_rate": 35.0,
    "min_trades": 10,
    "min_wf_consistency": 60.0,
    "max_prob_ruin": 15.0,
}


def _evaluate_strategy(metrics, wf_result, mc_result):
    """Apply pass/fail rules. Returns (passed, checks)."""
    checks = []

    def _check(name, passed, detail):
        checks.append({"name": name, "passed": passed, "detail": detail})

    _check(
        "Profit Factor ≥ 1.3",
        metrics["profit_factor"] >= _PASS_RULES["min_profit_factor"],
        f"{metrics['profit_factor']}",
    )
    _check(
        "Sharpe Ratio ≥ 0.4",
        metrics["sharpe"] >= _PASS_RULES["min_sharpe"],
        f"{metrics['sharpe']}",
    )
    _check(
        "Max Drawdown ≥ -25%",
        metrics["max_drawdown"] >= _PASS_RULES["max_drawdown"],
        f"{metrics['max_drawdown']}%",
    )
    _check(
        "Win Rate ≥ 35%",
        metrics["win_rate"] >= _PASS_RULES["min_win_rate"],
        f"{metrics['win_rate']}%",
    )
    _check(
        "Min 10 Trades",
        metrics["trade_count"] >= _PASS_RULES["min_trades"],
        f"{metrics['trade_count']}",
    )
    if wf_result:
        _check(
            "Walk-Forward ≥ 60%",
            wf_result["consistency"] >= _PASS_RULES["min_wf_consistency"],
            f"{wf_result['consistency']}%",
        )
    if mc_result:
        _check(
            "Monte Carlo Ruin < 15%",
            mc_result["prob_ruin"] <= _PASS_RULES["max_prob_ruin"],
            f"{mc_result['prob_ruin']}%",
        )

    passed = all(c["passed"] for c in checks)
    return passed, checks


@app.post("/api/strategy-factory/generate", tags=["factory"])
async def strategy_factory_generate(
    ticker: str = Query("SPY", description="Ticker to test on"),
    period: str = Query("2y", description="1y/2y/5y"),
    mode: str = Query("demo", description="demo or full"),
):
    """Generate, backtest, score, and rank strategy variants."""
    global _strategy_library, _factory_running
    import itertools

    import numpy as np
    import pandas as pd

    if _factory_running:
        return {"error": "Factory is already running. Wait for completion."}
    _factory_running = True

    try:
        ticker = validate_ticker(ticker)
        mds = app.state.market_data
        hist = await mds.get_history(ticker, period=period, interval="1d")
        if hist is None or hist.empty or len(hist) < 100:
            _factory_running = False
            return {"error": "Insufficient data"}

        c_col = "Close" if "Close" in hist.columns else "close"
        h_col = "High" if "High" in hist.columns else "high"
        l_col = "Low" if "Low" in hist.columns else "low"
        v_col = "Volume" if "Volume" in hist.columns else "volume"

        close = hist[c_col].values.astype(float)
        high = hist[h_col].values.astype(float)
        low = hist[l_col].values.astype(float)
        volume = hist[v_col].values.astype(float)
        dates_idx = hist.index
        n = len(close)

        results = []
        templates_to_run = (
            _STRATEGY_TEMPLATES if mode == "full" else _STRATEGY_TEMPLATES[:5]
        )

        for tmpl in templates_to_run:
            # Generate parameter combinations (limited in demo)
            param_keys = list(tmpl["params"].keys())
            param_vals = list(tmpl["params"].values())
            combos = list(itertools.product(*param_vals))
            if mode == "demo":
                combos = combos[:3]  # limit in demo
            else:
                combos = combos[:8]

            for combo in combos:
                params = dict(zip(param_keys, combo))
                variant_name = f"{tmpl['name']} ({', '.join(f'{k}={v}' for k, v in params.items())})"

                try:
                    # Generate code
                    code = _generate_strategy_code(tmpl, params)

                    # Generate signals using inline logic (safe, no exec)
                    signals = np.zeros(n)

                    if tmpl["id"] == "volume_momentum_breakout":
                        lb = params.get("lookback", 20)
                        vm = params.get("vol_mult", 1.5)
                        rmin = params.get("rsi_min", 55)
                        vol_ma = pd.Series(volume).rolling(lb).mean().values
                        rsi_delta = pd.Series(close).diff()
                        gain = rsi_delta.clip(lower=0).rolling(14).mean()
                        loss = (-rsi_delta.clip(upper=0)).rolling(14).mean()
                        rs = gain / (loss + 1e-10)
                        rsi = (100 - 100 / (1 + rs)).values
                        hi_n = pd.Series(close).rolling(lb).max().shift(1).values
                        for i in range(lb, n):
                            if (
                                not np.isnan(hi_n[i])
                                and close[i] > hi_n[i]
                                and volume[i] > vol_ma[i] * vm
                                and rsi[i] > rmin
                            ):
                                signals[i] = 1
                            elif rsi[i] > 75:
                                signals[i] = -1

                    elif tmpl["id"] == "atr_channel_breakout":
                        sl = params.get("sma_len", 20)
                        am = params.get("atr_mult", 2.0)
                        al = params.get("atr_len", 14)
                        sma = pd.Series(close).rolling(sl).mean().values
                        tr = np.maximum(high - low, np.abs(high - np.roll(close, 1)))
                        atr = pd.Series(tr).rolling(al).mean().values
                        for i in range(max(sl, al), n):
                            if close[i] > sma[i] + atr[i] * am:
                                signals[i] = 1
                            elif close[i] < sma[i] - atr[i] * am:
                                signals[i] = -1

                    elif tmpl["id"] == "macd_ema_hybrid":
                        f_p, s_p, sg_p, ef = (
                            params.get("fast", 12),
                            params.get("slow", 26),
                            params.get("signal", 9),
                            params.get("ema_filter", 50),
                        )
                        ema_f = pd.Series(close).ewm(span=f_p).mean().values
                        ema_s = pd.Series(close).ewm(span=s_p).mean().values
                        macd = ema_f - ema_s
                        macd_sig = pd.Series(macd).ewm(span=sg_p).mean().values
                        ema_filt = pd.Series(close).ewm(span=ef).mean().values
                        for i in range(ef, n):
                            if (
                                macd[i] > macd_sig[i]
                                and macd[i] > 0
                                and close[i] > ema_filt[i]
                            ):
                                signals[i] = 1
                            elif macd[i] < macd_sig[i]:
                                signals[i] = -1

                    elif tmpl["id"] == "triple_ema_momentum":
                        f_p, m_p, s_p = (
                            params.get("fast", 8),
                            params.get("mid", 21),
                            params.get("slow", 55),
                        )
                        e1 = pd.Series(close).ewm(span=f_p).mean().values
                        e2 = pd.Series(close).ewm(span=m_p).mean().values
                        e3 = pd.Series(close).ewm(span=s_p).mean().values
                        for i in range(s_p, n):
                            if e1[i] > e2[i] > e3[i] and e1[i] > e1[i - 1]:
                                signals[i] = 1
                            elif e1[i] < e2[i]:
                                signals[i] = -1

                    elif tmpl["id"] == "rsi_mean_reversion":
                        rl, re, rx, ml = (
                            params.get("rsi_len", 14),
                            params.get("rsi_entry", 30),
                            params.get("rsi_exit", 70),
                            params.get("ma_len", 20),
                        )
                        rsi_delta = pd.Series(close).diff()
                        gain = rsi_delta.clip(lower=0).rolling(rl).mean()
                        loss = (-rsi_delta.clip(upper=0)).rolling(rl).mean()
                        rsi = (100 - 100 / (1 + gain / (loss + 1e-10))).values
                        ma = pd.Series(close).rolling(ml).mean().values
                        vol_ma = pd.Series(volume).rolling(20).mean().values
                        for i in range(max(rl, ml), n):
                            if (
                                rsi[i] < re
                                and close[i] > ma[i] * 0.97
                                and volume[i] > vol_ma[i]
                            ):
                                signals[i] = 1
                            elif rsi[i] > rx:
                                signals[i] = -1

                    elif tmpl["id"] == "dual_rsi_trend_filter":
                        rf, rs_p, rfe, rsm = (
                            params.get("rsi_fast", 5),
                            params.get("rsi_slow", 14),
                            params.get("rsi_fast_entry", 20),
                            params.get("rsi_slow_min", 50),
                        )
                        delta = pd.Series(close).diff()
                        g1 = delta.clip(lower=0).rolling(rf).mean()
                        l1 = (-delta.clip(upper=0)).rolling(rf).mean()
                        rsi_f = (100 - 100 / (1 + g1 / (l1 + 1e-10))).values
                        g2 = delta.clip(lower=0).rolling(rs_p).mean()
                        l2 = (-delta.clip(upper=0)).rolling(rs_p).mean()
                        rsi_s = (100 - 100 / (1 + g2 / (l2 + 1e-10))).values
                        for i in range(rs_p + 5, n):
                            if rsi_f[i] < rfe and rsi_s[i] > rsm:
                                signals[i] = 1
                            elif rsi_f[i] > 80:
                                signals[i] = -1

                    elif tmpl["id"] == "bollinger_breakout":
                        bl, bs, sq = (
                            params.get("bb_len", 20),
                            params.get("bb_std", 2.0),
                            params.get("squeeze_pct", 0.04),
                        )
                        sma = pd.Series(close).rolling(bl).mean().values
                        std = pd.Series(close).rolling(bl).std().values
                        upper = sma + std * bs
                        bw = (upper - (sma - std * bs)) / (sma + 1e-10)
                        for i in range(bl + 5, n):
                            if bw[i - 1] < sq and close[i] > upper[i]:
                                signals[i] = 1
                            elif close[i] < sma[i]:
                                signals[i] = -1

                    elif tmpl["id"] == "stochastic_rsi_reversal":
                        stl, rl, ks, ds, el = (
                            params.get("stoch_len", 14),
                            params.get("rsi_len", 14),
                            params.get("k_smooth", 3),
                            params.get("d_smooth", 3),
                            params.get("entry_level", 20),
                        )
                        delta = pd.Series(close).diff()
                        g = delta.clip(lower=0).rolling(rl).mean()
                        l_val = (-delta.clip(upper=0)).rolling(rl).mean()
                        rsi = 100 - 100 / (1 + g / (l_val + 1e-10))
                        ll = rsi.rolling(stl).min()
                        hh = rsi.rolling(stl).max()
                        k = (
                            ((rsi - ll) / (hh - ll + 1e-10) * 100)
                            .rolling(ks)
                            .mean()
                            .values
                        )
                        d = pd.Series(k).rolling(ds).mean().values
                        ma50 = pd.Series(close).rolling(50).mean().values
                        for i in range(55, n):
                            if (
                                not np.isnan(k[i])
                                and not np.isnan(d[i])
                                and k[i] > d[i]
                                and k[i - 1] <= d[i - 1]
                                and k[i] < el + 20
                                and close[i] > ma50[i]
                            ):
                                signals[i] = 1
                            elif (
                                not np.isnan(k[i])
                                and not np.isnan(d[i])
                                and k[i] > 80
                                and k[i] < d[i]
                            ):
                                signals[i] = -1

                    elif tmpl["id"] == "macd_crossover":
                        f_p, s_p, sg_p = (
                            params.get("fast", 12),
                            params.get("slow", 26),
                            params.get("signal", 9),
                        )
                        hm = params.get("hist_min", 0)
                        ema_f = pd.Series(close).ewm(span=f_p).mean().values
                        ema_s = pd.Series(close).ewm(span=s_p).mean().values
                        macd = ema_f - ema_s
                        macd_sig = pd.Series(macd).ewm(span=sg_p).mean().values
                        hist_arr = macd - macd_sig
                        for i in range(s_p + sg_p, n):
                            if (
                                macd[i] > macd_sig[i]
                                and macd[i - 1] <= macd_sig[i - 1]
                                and hist_arr[i] > hm
                            ):
                                signals[i] = 1
                            elif (
                                macd[i] < macd_sig[i] and macd[i - 1] >= macd_sig[i - 1]
                            ):
                                signals[i] = -1

                    # Run backtest
                    metrics = _run_strategy_backtest(
                        close, high, low, volume, signals, dates_idx
                    )
                    if not metrics or metrics["trade_count"] < 3:
                        continue

                    # Walk-forward
                    wf = _walk_forward_test(close, high, low, volume, signals)

                    # Monte Carlo
                    mc_returns = [t["pnl_pct"] / 100 for t in metrics.get("trades", [])]
                    all_returns = [
                        t["pnl_pct"] / 100 for t in metrics.get("trades", [])
                    ]
                    if metrics["trade_count"] >= 5:
                        mc = _monte_carlo_test(all_returns)
                    else:
                        mc = None

                    # Evaluate pass/fail
                    passed, checks = _evaluate_strategy(metrics, wf, mc)

                    # Score (weighted composite)
                    score = (
                        min(metrics["profit_factor"], 5) * 15
                        + min(max(metrics["sharpe"], -1), 3) * 20
                        + min(metrics["win_rate"], 80) * 0.5
                        + max(0, metrics["max_drawdown"] + 30) * 1.5
                        + (wf["consistency"] * 0.3 if wf else 0)
                        + (10 if mc and mc["passed"] else 0)
                    )

                    results.append(
                        {
                            "id": f"{tmpl['id']}_{hash(str(combo)) % 10000}",
                            "name": variant_name,
                            "template": tmpl["name"],
                            "family": tmpl["family"],
                            "params": params,
                            "code": code,
                            "metrics": {
                                k: v
                                for k, v in metrics.items()
                                if k != "trades" and k != "equity"
                            },
                            "walk_forward": wf,
                            "monte_carlo": mc,
                            "passed": passed,
                            "checks": checks,
                            "score": round(score, 1),
                            "trades_sample": metrics.get("trades", [])[:10],
                            "equity_curve": [
                                round(v, 2)
                                for v in metrics.get("equity", [])[
                                    :: max(1, len(metrics.get("equity", [])) // 100)
                                ]
                            ],
                        }
                    )

                except Exception as e:
                    logger.debug("Strategy variant error %s: %s", variant_name, e)
                    continue

        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)

        # Assign ranks
        for i, r in enumerate(results):
            r["rank"] = i + 1

        _strategy_library = results
        _factory_running = False

        return _sanitize_for_json(
            {
                "ticker": ticker,
                "period": period,
                "mode": mode,
                "data_points": n,
                "strategies_generated": len(results),
                "strategies_passed": sum(1 for r in results if r["passed"]),
                "strategies_failed": sum(1 for r in results if not r["passed"]),
                "best_strategy": results[0] if results else None,
                "ranking": [
                    {
                        "rank": r["rank"],
                        "name": r["name"],
                        "family": r["family"],
                        "score": r["score"],
                        "passed": r["passed"],
                        "profit_factor": r["metrics"]["profit_factor"],
                        "sharpe": r["metrics"]["sharpe"],
                        "max_drawdown": r["metrics"]["max_drawdown"],
                        "win_rate": r["metrics"]["win_rate"],
                        "net_return": r["metrics"]["net_return"],
                        "trade_count": r["metrics"]["trade_count"],
                    }
                    for r in results
                ],
                "pass_rules": _PASS_RULES,
            }
        )

    except Exception as e:
        _factory_running = False
        logger.exception("Strategy factory error")
        return {"error": str(e)}


@app.get("/api/strategy-factory/library", tags=["factory"])
async def strategy_factory_library():
    """Return all generated strategies from the latest run."""
    return _sanitize_for_json(
        {
            "count": len(_strategy_library),
            "strategies": _strategy_library,
        }
    )


@app.get("/api/strategy-factory/detail/{strategy_id}", tags=["factory"])
async def strategy_factory_detail(strategy_id: str):
    """Return full detail for a specific strategy variant."""
    for s in _strategy_library:
        if s["id"] == strategy_id:
            return _sanitize_for_json(s)
    raise HTTPException(404, f"Strategy {strategy_id} not found")


@app.post("/api/strategy-factory/deploy/{strategy_id}", tags=["factory"])
async def strategy_factory_deploy(strategy_id: str):
    """Mark a strategy as deployed (paper-trade monitoring)."""
    for s in _strategy_library:
        if s["id"] == strategy_id:
            s["deployed"] = True
            s["deployed_at"] = datetime.now(timezone.utc).isoformat() + "Z"
            return {"status": "deployed", "strategy": s["name"]}
    raise HTTPException(404, f"Strategy {strategy_id} not found")



# live/brief, live/options → live_brief_options.py
# live/backtest → routers/live_backtest.py
# live/time-travel + analytics → live_time_travel.py + live_analytics.py


# ═══════════════════════════════════════════════════════════════════
# v7 PRODUCT SURFACE PAGES — Regime Screener · Portfolio Brief
# Compare Overlay · Performance Lab · Options Lab
# ═══════════════════════════════════════════════════════════════════


@app.get("/regime-screener", response_class=HTMLResponse, include_in_schema=False)
async def regime_screener_page(request: Request):
    """Serve the Regime Screener page."""
    return templates.TemplateResponse(request, "regime_screener.html")


@app.get("/portfolio-brief", response_class=HTMLResponse, include_in_schema=False)
async def portfolio_brief_page(request: Request):
    """Serve the Portfolio Brief page."""
    return templates.TemplateResponse(request, "portfolio_brief.html")


@app.get("/compare", response_class=HTMLResponse, include_in_schema=False)
async def compare_page(request: Request):
    """Serve the Compare Overlay page."""
    return templates.TemplateResponse(request, "compare.html")


@app.get("/performance-lab", response_class=HTMLResponse, include_in_schema=False)
async def performance_lab_page(request: Request):
    """Serve the Performance Lab page."""
    return templates.TemplateResponse(request, "performance_lab.html")


@app.get("/options-lab", response_class=HTMLResponse, include_in_schema=False)
async def options_lab_page(request: Request):
    """Serve the Options Lab page."""
    return templates.TemplateResponse(request, "options_lab.html")


@app.get("/macro-intel", response_class=HTMLResponse, include_in_schema=False)
async def macro_intel_page(request: Request):
    """Serve the Macro Intelligence page."""
    return templates.TemplateResponse(request, "macro_intel.html")



# v7 API surfaces → src/api/routers/v7_surfaces.py


# ══════════════════════════════════════════════════════════════════════
# Sprint 54 — Extracted routers (token optimization)
# ══════════════════════════════════════════════════════════════════════
from src.api.routers.intel import router as intel_router
from src.api.routers.portfolio import router as portfolio_router

app.include_router(intel_router)
app.include_router(portfolio_router)
from src.api.routers.decision import router as decision_router

app.include_router(decision_router)

from src.api.routers.playbook import router as playbook_router

app.include_router(playbook_router)


# Task management CRUD API
try:
    from src.api.routers.tasks import router as tasks_router

    app.include_router(tasks_router)
except Exception:
    logger.exception("[Router] Failed to load tasks router")

# Sprint 72 — Watchlist Decision Board + Command-K search
try:
    from src.api.routers.watchlist import router as watchlist_router

    app.include_router(watchlist_router)
except Exception:
    logger.exception("[Router] Failed to load watchlist router")

# Sprint 72 — Symbol Dossier (full decision card per ticker)
try:
    from src.api.routers.dossier import router as dossier_router

    app.include_router(dossier_router)
except Exception:
    logger.exception("[Router] Failed to load dossier router")


# Sprint 81 RISK-3 — Market intel extracted router
try:
    from src.api.routers.market_intel import router as market_intel_router

    app.include_router(market_intel_router)
except Exception:
    logger.exception("[Router] Failed to load market_intel router")

# Sprint 82 ARCH — Broker router extracted from main.py
try:
    from src.api.routers.broker import router as broker_router

    app.include_router(broker_router)
except Exception:
    logger.exception("[Router] Failed to load broker router")

# Sprint 82 ARCH — Health/observability router extracted from main.py
try:
    from src.api.routers.health import router as health_router

    app.include_router(health_router)
except Exception:
    logger.exception("[Router] Failed to load health router")

# Per-strategy realized-trade analytics (Sharpe / hit-rate / expectancy)
try:
    from src.api.routers.strategy_health import router as strategy_health_router

    app.include_router(strategy_health_router)
except Exception:
    logger.exception("[Router] Failed to load strategy_health router")

# Historical-simulation VaR (real 1y returns, no normality assumption)
try:
    from src.api.routers.portfolio_var import router as portfolio_var_router

    app.include_router(portfolio_var_router)
except Exception:
    logger.exception("[Router] Failed to load portfolio_var router")

# Pre-trade slippage gate (spread/ADV/cost guards before IBKR send)
try:
    from src.api.routers.slippage_gate import router as slippage_gate_router

    app.include_router(slippage_gate_router)
except Exception:
    logger.exception("[Router] Failed to load slippage_gate router")

# Data freshness watchdog (last-bar age per critical stream)
try:
    from src.api.routers.data_freshness import router as data_freshness_router

    app.include_router(data_freshness_router)
except Exception:
    logger.exception("[Router] Failed to load data_freshness router")

# Trade-ledger writer (closed_trades.jsonl)
try:
    from src.api.routers.ledger import router as ledger_router

    app.include_router(ledger_router)
except Exception:
    logger.exception("[Router] Failed to load ledger router")

# Position-level risk alerts (stop proximity, drawdown, concentration, stale)
try:
    from src.api.routers.position_alerts import router as position_alerts_router

    app.include_router(position_alerts_router)
except Exception:
    logger.exception("[Router] Failed to load position_alerts router")

# Brief regenerator (on-demand morning brief regen)
try:
    from src.api.routers.brief_regenerate import router as brief_regen_router

    app.include_router(brief_regen_router)
except Exception:
    logger.exception("[Router] Failed to load brief_regenerate router")

# Sprint N — Closed-trade ledger viewer (read-only paginated view + stats)
try:
    from src.api.routers.ledger_view import router as ledger_view_router

    app.include_router(ledger_view_router)
except Exception:
    logger.exception("[Router] Failed to load ledger_view router")


# Sprint 99 — Execution cost, Kelly sizing, MTF confluence
try:
    from src.api.routers.execution import router as execution_router

    app.include_router(execution_router)
except Exception:
    logger.exception("[Router] Failed to load execution router")

# Sprint 100 — Live risk guards (correlation, VaR, concentration)
try:
    from src.api.routers.risk_guard import router as risk_guard_router

    app.include_router(risk_guard_router)
except Exception:
    logger.exception("[Router] Failed to load risk_guard router")
# Sprint 106 — AlertService notification log + test endpoint
try:
    from src.api.routers.notify import router as notify_router

    app.include_router(notify_router)
except Exception:
    logger.exception("[Router] Failed to load notify router")

# Sprint 109 — Unified Sizing Advisor (Kelly + Thompson + decay + heat)
try:
    from src.api.routers.sizing import router as sizing_router

    app.include_router(sizing_router)
except Exception:
    logger.exception("[Router] Failed to load sizing router")

# Sprint 114 — Opportunity Scanner (Neal-style dual-engine screener)
try:
    from src.api.routers.opportunity_scanner import router as opp_scanner_router

    app.include_router(opp_scanner_router)
except Exception:
    logger.exception("[Router] Failed to load opportunity_scanner router")

# Sprint 117 — IBKR paper/live trading integration
try:
    from src.api.routers.ibkr import router as ibkr_router

    app.include_router(ibkr_router)
except Exception:
    logger.exception("[Router] Failed to load ibkr router")

# AI advisor — PM memos, expert views, trade review
try:
    from src.api.routers.ai_advisor import router as ai_advisor_router

    app.include_router(ai_advisor_router)
except Exception:
    logger.exception("[Router] Failed to load ai_advisor router")

# Options flow radar — unusual activity evidence layer
try:
    from src.api.routers.options_radar import router as options_radar_router

    app.include_router(options_radar_router)
except Exception:
    logger.exception("[Router] Failed to load options_radar router")

# Model fund / active manager sleeves
try:
    from src.api.routers.funds import router as funds_router

    app.include_router(funds_router)
except Exception:
    logger.exception("[Router] Failed to load funds router")

# Single-stock conviction stack (technical + flow + insider)
try:
    from src.api.routers.conviction import router as conviction_router

    app.include_router(conviction_router)
except Exception:
    logger.exception("[Router] Failed to load conviction router")

try:
    from src.api.routers.daily_decision import router as daily_decision_router

    app.include_router(daily_decision_router)
except Exception:
    logger.exception("[Router] Failed to load daily_decision router")

try:
    from src.api.routers.edgar_api import router as edgar_api_router

    app.include_router(edgar_api_router)
except Exception:
    logger.exception("[Router] Failed to load edgar_api router")

try:
    from src.api.routers.macro_fred import router as macro_fred_router

    app.include_router(macro_fred_router)
except Exception:
    logger.exception("[Router] Failed to load macro_fred router")

try:
    from src.api.routers.uncertainty import router as uncertainty_router

    app.include_router(uncertainty_router)
except Exception:
    logger.exception("[Router] Failed to load uncertainty router")

try:
    from src.api.routers.scenarios import router as scenarios_router

    app.include_router(scenarios_router)
except Exception:
    logger.exception("[Router] Failed to load scenarios router")

try:
    from src.api.routers.expert_committee_api import (
        router as expert_committee_api_router,
    )

    app.include_router(expert_committee_api_router)
except Exception:
    logger.exception("[Router] Failed to load expert_committee_api router")

try:
    from src.api.routers.live_market import router as live_market_router

    app.include_router(live_market_router)
except Exception:
    logger.exception("[Router] Failed to load live_market router")

try:
    from src.api.routers.live_quotes import router as live_quotes_router

    app.include_router(live_quotes_router)
except Exception:
    logger.exception("[Router] Failed to load live_quotes router")

try:
    from src.api.routers.live_chart import router as live_chart_router

    app.include_router(live_chart_router)
except Exception:
    logger.exception("[Router] Failed to load live_chart router")

try:
    from src.api.routers.live_dossier import router as live_dossier_router

    app.include_router(live_dossier_router)
except Exception:
    logger.exception("[Router] Failed to load live_dossier router")

try:
    from src.api.routers.live_brief_options import router as live_brief_options_router

    app.include_router(live_brief_options_router)
except Exception:
    logger.exception("[Router] Failed to load live_brief_options router")

try:
    from src.api.routers.cc_header import router as cc_header_router

    app.include_router(cc_header_router)
except Exception:
    logger.exception("[Router] Failed to load cc_header router")

try:
    from src.api.routers.live_backtest import router as live_backtest_router

    app.include_router(live_backtest_router)
except Exception:
    logger.exception("[Router] Failed to load live_backtest router")

try:
    from src.api.routers.live_time_travel import router as live_time_travel_router

    app.include_router(live_time_travel_router)
except Exception:
    logger.exception("[Router] Failed to load live_time_travel router")

try:
    from src.api.routers.v6_pro_desk import router as v6_pro_desk_router

    app.include_router(v6_pro_desk_router)
except Exception:
    logger.exception("[Router] Failed to load v6_pro_desk router")

try:
    from src.api.routers.v7_surfaces import router as v7_surfaces_router

    app.include_router(v7_surfaces_router)
except Exception:
    logger.exception("[Router] Failed to load v7_surfaces router")

try:
    from src.api.routers.stock_intel import router as stock_intel_router

    app.include_router(stock_intel_router)
except Exception:
    logger.exception("[Router] Failed to load stock_intel router")

try:
    from src.api.routers.decision_hub import router as decision_hub_router

    app.include_router(decision_hub_router)
except Exception:
    logger.exception("[Router] Failed to load decision_hub router")

try:
    from src.api.routers.portfolio_decision import router as portfolio_decision_router

    app.include_router(portfolio_decision_router)
except Exception:
    logger.exception("[Router] Failed to load portfolio_decision router")

try:
    from src.api.routers.platform_extras import router as platform_extras_router

    app.include_router(platform_extras_router)
except Exception:
    logger.exception("[Router] Failed to load platform_extras router")


if __name__ == "__main__":
    start()
