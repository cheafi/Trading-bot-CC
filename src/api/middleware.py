"""
Middleware — Rate limiter and request processing.
Extracted from main.py (Sprint 118) to reduce monolith complexity.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter with automatic cleanup."""

    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300

    async def is_allowed(self, client_id: str) -> bool:
        async with self._lock:
            now = time.time()
            minute_ago = now - 60
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > minute_ago
            ]
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale_clients(now)
            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False
            self.requests[client_id].append(now)
            return True

    def _cleanup_stale_clients(self, now: float):
        minute_ago = now - 60
        stale = [
            cid for cid, ts in self.requests.items() if not ts or max(ts) < minute_ago
        ]
        for cid in stale:
            del self.requests[cid]
        self._last_cleanup = now

    def get_remaining(self, client_id: str) -> int:
        now = time.time()
        minute_ago = now - 60
        recent = [t for t in self.requests.get(client_id, []) if t > minute_ago]
        return max(0, self.requests_per_minute - len(recent))


# Global instance
rate_limiter = RateLimiter(requests_per_minute=120)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware — 120 req/min per client."""

    async def dispatch(self, request: Request, call_next):
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
        remaining = rate_limiter.get_remaining(client_id)
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
