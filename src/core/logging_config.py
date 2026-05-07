"""
TradingAI Bot — Structured Logging (Sprint 12)

Production-ready JSON logging with:
- Structured JSON output for log aggregators (ELK, Datadog, CloudWatch)
- Correlation ID per engine cycle for request tracing
- Human-readable console format for development
- Configurable via LOG_FORMAT env var ('json' | 'text')
"""
import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ── Correlation ID (per-cycle tracing) ──────────────────────
_correlation_id: ContextVar[str] = ContextVar(
    "correlation_id", default=""
)


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set (or generate) a correlation ID for the current context."""
    cid = cid or uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    return _correlation_id.get("")


# ── JSON Formatter ──────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """
    Emit each log record as a single JSON line.

    Fields:
      ts, level, logger, message, correlation_id,
      module, funcName, lineno, exc_info (if any)
    """

    def format(self, record: logging.LogRecord) -> str:
        doc: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        cid = get_correlation_id()
        if cid:
            doc["correlation_id"] = cid
        if record.exc_info and record.exc_info[1]:
            doc["exception"] = self.formatException(record.exc_info)
        # Extra fields added via `logger.info("msg", extra={...})`
        for key in ("phase", "latency_ms", "ticker", "cycle"):
            val = getattr(record, key, None)
            if val is not None:
                doc[key] = val
        return json.dumps(doc, default=str)


# ── Human-readable Formatter ───────────────────────────────
class ConsoleFormatter(logging.Formatter):
    """Rich console format with optional correlation ID."""

    FMT = (
        "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s"
    )

    def __init__(self):
        super().__init__(self.FMT, datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        cid = get_correlation_id()
        if cid:
            record.msg = f"[{cid}] {record.msg}"
        return super().format(record)


# ── Setup helper ────────────────────────────────────────────
def setup_logging(
    level: str = "INFO",
    log_format: str = "auto",
    log_file: Optional[str] = None,
) -> None:
    """
    Configure root logger for the application.

    Args:
        level: DEBUG / INFO / WARNING / ERROR
        log_format: 'json', 'text', or 'auto' (json if LOG_FORMAT=json
                     or running in Docker, else text)
        log_file: Optional path to a log file
    """
    if log_format == "auto":
        env_fmt = os.environ.get("LOG_FORMAT", "").lower()
        if env_fmt == "json" or os.path.exists("/.dockerenv"):
            log_format = "json"
        else:
            log_format = "text"

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console.setFormatter(JSONFormatter())
    else:
        console.setFormatter(ConsoleFormatter())
    root.addHandler(console)

    # File handler (always JSON for machine parsing)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(JSONFormatter())
        root.addHandler(fh)

    # Quiet noisy libraries
    for lib in ["urllib3", "asyncio", "aiohttp", "yfinance"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.getLogger(__name__).debug(
        "Logging configured: format=%s level=%s", log_format, level
    )
