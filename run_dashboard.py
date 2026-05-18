#!/usr/bin/env python3
"""
TradingAI Pro - Web Dashboard Runner

Run this to start the web dashboard at http://localhost:8000

Features:
- Auto-reload on code changes
- Graceful shutdown handling
- Error logging to file
"""
import uvicorn
import sys
import os
import signal
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('dashboard.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


def _port() -> int:
    """Resolve the bind port for local and hosted environments."""
    return int(os.getenv("PORT", "8000"))


def _reload_enabled() -> bool:
    """Disable reload in hosted environments unless explicitly requested."""
    return os.getenv("UVICORN_RELOAD", "true").lower() in {"1", "true", "yes"}


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("🚀 TradingAI Pro Dashboard")
    print("=" * 60)
    print()
    port = _port()
    print(f"📊 Dashboard: http://localhost:{port}")
    print(f"📚 API Docs:  http://localhost:{port}/docs")
    print(f"📖 ReDoc:     http://localhost:{port}/redoc")
    print("📝 Logging to: dashboard.log")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    try:
        uvicorn.run(
            "src.api.main:app",
            host="0.0.0.0",
            port=port,
            reload=_reload_enabled(),
            log_level="info",
            access_log=True,
            timeout_keep_alive=30,
            limit_concurrency=100,
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise
