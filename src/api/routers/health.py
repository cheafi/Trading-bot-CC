"""
Health & Observability Router — Sprint 82
==========================================
Extracted from main.py (was 8 inline @app.get routes, lines ~1109-1256).

Endpoints:
    GET /health              — basic health (no auth)
    GET /health/detailed     — DB health (auth)
    GET /health/live         — Kubernetes liveness probe
    GET /health/ready        — Kubernetes readiness probe
    GET /status/data         — data freshness (auth)
    GET /status/jobs         — scheduler job status (auth)
    GET /status/signals      — signal generation stats (auth)
    GET /metrics             — Prometheus-style text metrics
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from src.api.deps import verify_api_key
from src.core.telemetry import telemetry
from src.core.version import APP_VERSION

router = APIRouter(tags=["health"])


# ── Shared response model ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Service status: healthy, degraded, or unhealthy")
    timestamp: str = Field(..., description="ISO timestamp of health check")
    version: str = Field(..., description="API version")
    database: Optional[str] = Field(None, description="Database connection status")
    redis: Optional[str] = Field(None, description="Redis connection status")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime in seconds")
    phase9_engines: Optional[dict] = Field(None, description="Phase 9 engine status")


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, summary="Basic health check")
async def health_check():
    """
    Basic health check endpoint.

    Returns service status and version information.
    No authentication required.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "uptime_seconds": telemetry.get_uptime_seconds(),
    }


@router.get(
    "/health/detailed",
    response_model=HealthResponse,
    summary="Detailed health check with component status",
)
async def detailed_health_check(_: bool = Depends(verify_api_key)):
    """Detailed health check with component status."""
    from src.core.database import check_database_health

    try:
        db_health = await check_database_health()
        db_status = "connected" if db_health else "disconnected"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "database": db_status,
    }


@router.get("/health/live", summary="Kubernetes liveness probe")
async def health_live():
    """Simple liveness check - is the process alive?"""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready", summary="Kubernetes readiness probe")
async def health_ready(request: Request):
    """
    Readiness check - can the service handle traffic?
    Checks DB and data freshness.
    """
    from src.core.database import check_database_health

    checks: Dict[str, Any] = {
        "database": False,
        "market_data": False,
        "data_freshness": False,
    }

    try:
        checks["database"] = await check_database_health()
    except Exception:
        pass

    try:
        mds = request.app.state.market_data
        q = await mds.get_quote("SPY")
        checks["market_data"] = q is not None and q.get("price", 0) > 0
    except Exception:
        pass

    try:
        checks["data_freshness"] = telemetry.get_data_freshness_ready()
    except Exception:
        pass

    return {
        "ready": all(checks.values()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/status/data", summary="Data freshness per source")
async def status_data(_: bool = Depends(verify_api_key)):
    """
    Check data freshness for each data source.
    Returns last update time and staleness status — all values tracked live.
    """
    return telemetry.get_data_status()


@router.get("/status/jobs", summary="Scheduler job status")
async def status_jobs(_: bool = Depends(verify_api_key)):
    """Get status of scheduled jobs — all values tracked live."""
    return telemetry.get_jobs_status()


@router.get("/status/signals", summary="Signal generation status")
async def status_signals(_: bool = Depends(verify_api_key)):
    """Get signal generation statistics — all values tracked live."""
    return telemetry.get_signals_status()


@router.get("/metrics", summary="Prometheus-style metrics")
async def metrics():
    """
    Prometheus-compatible metrics endpoint.
    Returns metrics in text format — all counters are real.
    """
    telemetry.record_api_request("/metrics")
    return Response(
        content=telemetry.get_metrics_text(),
        media_type="text/plain",
    )
