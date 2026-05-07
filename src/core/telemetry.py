"""
CC — Real Telemetry Tracker

Replaces placeholder/hardcoded health, status, and metrics endpoints
with actually tracked state. Every counter, timestamp, and staleness
value reflects real events — no synthetic numbers.

Usage:
    from src.core.telemetry import telemetry
    telemetry.record_signal_generated("momentum", "AAPL")
    telemetry.record_signal_rejected("momentum", "TSLA", "stale_data")
    telemetry.record_data_update("prices")
    telemetry.record_job_run("signal_generation", success=True, duration=12.5)
    telemetry.record_api_request("/api/signals")
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DataSourceState:
    """Tracked state for one data source."""

    last_update: Optional[datetime] = None
    update_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    threshold_seconds: int = 900  # default 15 min

    @property
    def staleness_seconds(self) -> float:
        if self.last_update is None:
            return float("inf")
        return (_utcnow() - self.last_update).total_seconds()

    @property
    def status(self) -> str:
        if self.last_update is None:
            return "no_data"
        s = self.staleness_seconds
        if s <= self.threshold_seconds:
            return "fresh"
        if s <= self.threshold_seconds * 2:
            return "stale"
        return "dead"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "staleness_seconds": (
                round(self.staleness_seconds, 1) if self.last_update else None
            ),
            "status": self.status,
            "threshold_seconds": self.threshold_seconds,
            "update_count": self.update_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }


@dataclass
class JobState:
    """Tracked state for one scheduled job."""

    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: str = "never_run"  # success / failure / running / never_run
    run_count: int = 0
    failure_count: int = 0
    last_duration_seconds: float = 0.0
    last_error: Optional[str] = None
    interval_minutes: int = 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "status": self.status,
            "interval_minutes": self.interval_minutes,
            "last_duration_seconds": round(self.last_duration_seconds, 2),
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
        }


class TelemetryTracker:
    """
    Central telemetry state — thread-safe, in-memory.
    Every counter and timestamp is real.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._startup_time = _utcnow()

        # Counters
        self._signals_generated: int = 0
        self._signals_rejected: int = 0
        self._api_requests: int = 0

        # By-strategy signal counts
        self._by_strategy_generated: Dict[str, int] = defaultdict(int)
        self._by_strategy_rejected: Dict[str, int] = defaultdict(int)

        # Rejection reasons
        self._rejection_reasons: Dict[str, int] = defaultdict(int)

        # Active signals
        self._active_signals: int = 0

        # Data sources
        self._data_sources: Dict[str, DataSourceState] = {
            "prices": DataSourceState(threshold_seconds=900),
            "news": DataSourceState(threshold_seconds=1800),
            "social": DataSourceState(threshold_seconds=3600),
            "options": DataSourceState(threshold_seconds=900),
        }

        # Jobs
        self._jobs: Dict[str, JobState] = {
            "signal_generation": JobState(interval_minutes=60),
            "price_ingestion": JobState(interval_minutes=2),
            "news_ingestion": JobState(interval_minutes=30),
            "daily_report": JobState(interval_minutes=1440),
        }

        # Last signal generation timestamp
        self._last_signal_generation: Optional[datetime] = None

    # ── Recording methods ─────────────────────────────────────

    def record_signal_generated(self, strategy: str, ticker: str) -> None:
        with self._lock:
            self._signals_generated += 1
            self._by_strategy_generated[strategy] += 1
            self._active_signals += 1
            self._last_signal_generation = _utcnow()

    def record_signal_rejected(self, strategy: str, ticker: str, reason: str) -> None:
        with self._lock:
            self._signals_rejected += 1
            self._by_strategy_rejected[strategy] += 1
            self._rejection_reasons[f"NO_TRADE_{reason}"] += 1

    def record_signal_closed(self) -> None:
        with self._lock:
            self._active_signals = max(0, self._active_signals - 1)

    def record_data_update(self, source: str, error: Optional[str] = None) -> None:
        with self._lock:
            if source not in self._data_sources:
                self._data_sources[source] = DataSourceState()
            ds = self._data_sources[source]
            if error:
                ds.error_count += 1
                ds.last_error = error
            else:
                ds.last_update = _utcnow()
                ds.update_count += 1

    def record_job_run(
        self,
        job_name: str,
        success: bool = True,
        duration: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            if job_name not in self._jobs:
                self._jobs[job_name] = JobState()
            job = self._jobs[job_name]
            job.last_run = _utcnow()
            job.run_count += 1
            job.last_duration_seconds = duration
            job.status = "success" if success else "failure"
            if not success:
                job.failure_count += 1
                job.last_error = error
            # Estimate next run
            job.next_run = _utcnow() + timedelta(minutes=job.interval_minutes)

    def record_api_request(self, path: str = "") -> None:
        with self._lock:
            self._api_requests += 1

    # ── Query methods (for endpoints) ─────────────────────────

    def get_uptime_seconds(self) -> float:
        return (_utcnow() - self._startup_time).total_seconds()

    def get_data_status(self) -> Dict[str, Any]:
        with self._lock:
            sources = {k: v.to_dict() for k, v in self._data_sources.items()}
            all_fresh = all(
                v.status == "fresh"
                for v in self._data_sources.values()
                if v.last_update is not None
            )
            any_data = any(
                v.last_update is not None for v in self._data_sources.values()
            )
            return {
                "timestamp": _utcnow().isoformat(),
                "all_sources_fresh": all_fresh and any_data,
                "can_generate_signals": all_fresh and any_data,
                "sources": sources,
            }

    def get_data_freshness_ready(self) -> bool:
        """For /health/ready — are price data fresh enough?"""
        with self._lock:
            prices = self._data_sources.get("prices")
            if prices is None or prices.last_update is None:
                return False
            return prices.staleness_seconds < prices.threshold_seconds

    def get_jobs_status(self) -> Dict[str, Any]:
        with self._lock:
            jobs = {k: v.to_dict() for k, v in self._jobs.items()}
            failures = [k for k, v in self._jobs.items() if v.status == "failure"]
            return {
                "timestamp": _utcnow().isoformat(),
                "total_jobs": len(self._jobs),
                "healthy_jobs": len(self._jobs) - len(failures),
                "failed_jobs": failures,
                "jobs": jobs,
            }

    def get_signals_status(self) -> Dict[str, Any]:
        with self._lock:
            today_gen = self._signals_generated
            today_rej = self._signals_rejected
            return {
                "timestamp": _utcnow().isoformat(),
                "last_generation": (
                    self._last_signal_generation.isoformat()
                    if self._last_signal_generation
                    else None
                ),
                "signals_today": {
                    "generated": today_gen,
                    "rejected": today_rej,
                    "active": self._active_signals,
                },
                "rejection_reasons": dict(self._rejection_reasons),
                "by_strategy": {
                    strategy: {
                        "generated": self._by_strategy_generated.get(strategy, 0),
                        "rejected": self._by_strategy_rejected.get(strategy, 0),
                    }
                    for strategy in set(
                        list(self._by_strategy_generated.keys())
                        + list(self._by_strategy_rejected.keys())
                    )
                },
            }

    def get_metrics_text(self) -> str:
        """Prometheus-compatible text format with REAL counters."""
        with self._lock:
            uptime = self.get_uptime_seconds()
            lines = [
                "# HELP tradingai_up Service is up",
                "# TYPE tradingai_up gauge",
                "tradingai_up 1",
                "",
                "# HELP tradingai_uptime_seconds Service uptime",
                "# TYPE tradingai_uptime_seconds counter",
                f"tradingai_uptime_seconds {uptime:.2f}",
                "",
                "# HELP tradingai_signals_generated_total Total signals generated",
                "# TYPE tradingai_signals_generated_total counter",
                f"tradingai_signals_generated_total {self._signals_generated}",
                "",
                "# HELP tradingai_signals_rejected_total Total signals rejected",
                "# TYPE tradingai_signals_rejected_total counter",
                f"tradingai_signals_rejected_total {self._signals_rejected}",
                "",
                "# HELP tradingai_signals_active Current active signals",
                "# TYPE tradingai_signals_active gauge",
                f"tradingai_signals_active {self._active_signals}",
                "",
                "# HELP tradingai_api_requests_total Total API requests",
                "# TYPE tradingai_api_requests_total counter",
                f"tradingai_api_requests_total {self._api_requests}",
                "",
                "# HELP tradingai_data_staleness_seconds Data staleness per source",
                "# TYPE tradingai_data_staleness_seconds gauge",
            ]
            for name, ds in self._data_sources.items():
                staleness = round(ds.staleness_seconds, 1) if ds.last_update else -1
                lines.append(
                    f'tradingai_data_staleness_seconds{{source="{name}"}} {staleness}'
                )
            lines.append("")
            # Job health
            lines.append("# HELP tradingai_job_failures_total Job failure count")
            lines.append("# TYPE tradingai_job_failures_total counter")
            for name, job in self._jobs.items():
                lines.append(
                    f'tradingai_job_failures_total{{job="{name}"}} {job.failure_count}'
                )
            return "\n".join(lines)


# ── Module-level singleton ────────────────────────────────────
telemetry = TelemetryTracker()
