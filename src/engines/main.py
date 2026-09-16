"""
TradingAI Bot — Engine Entrypoint (Sprint 12)

Production entrypoint for the AutoTradingEngine.
Called by Docker: `python -m src.engines.main`

Boot sequence:
  1. Configure structured logging
  2. Validate required configuration
  3. Run engine _boot() pre-flight checks
  4. Enter main loop
  5. Graceful shutdown on SIGINT/SIGTERM
"""

import argparse
import asyncio
import logging
import os
import signal
import sys

# Ensure project root is on path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.core.config import get_settings
from src.core.live_trading_gate import (
    assert_live_gate_or_paper,
    evaluate_live_trading_gate,
)
from src.core.logging_config import setup_logging
from src.core.trading_mode import resolve_execution_mode

logger = logging.getLogger("tradingai.main")


def validate_config() -> bool:
    """
    Validate that required environment / config values are present.
    Returns True if all critical settings are OK.
    """
    settings = get_settings()
    warnings = []
    errors = []

    # Critical: database
    db_url = getattr(settings, "database_url", "") or ""
    if not db_url or "localhost" in db_url:
        warnings.append("DATABASE_URL not set or points to localhost")

    # Important: at least one broker API key
    alpaca_key = os.environ.get("ALPACA_API_KEY", "")
    if not alpaca_key:
        warnings.append("ALPACA_API_KEY not set (paper broker OK)")

    # Important: notification channels
    discord_token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not discord_token:
        warnings.append("No notification channel configured (DISCORD_BOT_TOKEN)")

    # Optional: AI features (research_only — never grants deploy_open)
    from src.core.ai_provider import (
        openai_configured,
        provider_status,
        resolve_llm_provider,
    )

    ai = provider_status()
    if resolve_llm_provider().value == "stub":
        warnings.append(
            "No LLM configured — narratives and GPT validation use research stubs"
        )
    elif not openai_configured() and ai.get("azure_openai"):
        logger.info("Config: Azure OpenAI active (provider=%s)", ai.get("provider"))

    for w in warnings:
        logger.warning("Config: %s", w)
    for e in errors:
        logger.error("Config: %s", e)

    if errors:
        return False
    return True


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TradingAI autonomous engine")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Request live execution (also requires LIVE_TRADING=1 or TRADING_ENV=live)",
    )
    return parser.parse_args(argv)


async def run_engine(*, live_cli: bool = False):
    """Boot and run the AutoTradingEngine."""
    from src.engines.auto_trading_engine import AutoTradingEngine

    resolution = resolve_execution_mode(live_cli=live_cli)
    if resolution.ambiguous:
        raise SystemExit(1)

    live_requested = live_cli or not resolution.dry_run
    assert_live_gate_or_paper(live_requested=live_requested)
    gate = evaluate_live_trading_gate()
    dry_run = resolution.dry_run or gate.paper_by_construction
    cycle_interval = float(os.environ.get("CYCLE_INTERVAL", "60"))

    mode_label = "PAPER" if dry_run else "LIVE"
    logger.info(
        "Execution mode: %s (trading_mode=%s, live_gate=%s)",
        mode_label,
        resolution.reason,
        gate.reason,
    )

    engine = AutoTradingEngine(
        cycle_interval_seconds=cycle_interval,
        dry_run=dry_run,
    )

    # Pre-flight boot checks
    logger.info("Running pre-flight boot checks...")
    boot_ok = await engine._boot()
    if not boot_ok:
        logger.error("Boot checks failed — exiting")
        return

    # Register graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(_shutdown(engine, s)),
        )

    # Enter main loop
    await engine.run()


async def _shutdown(engine, sig):
    """Handle shutdown signal gracefully."""
    logger.info("Received signal %s — shutting down...", sig.name)
    await engine.graceful_shutdown()


def main(argv: list[str] | None = None):
    """CLI entrypoint."""
    args = _parse_args(argv)

    settings = get_settings()
    log_level = os.environ.get(
        "LOG_LEVEL",
        getattr(settings, "log_level", "INFO"),
    )
    log_file = os.environ.get("LOG_FILE", None)

    setup_logging(
        level=log_level,
        log_format="auto",
        log_file=log_file,
    )

    logger.info("=" * 60)
    logger.info("TradingAI Bot — Engine Starting")
    logger.info("=" * 60)

    if not validate_config():
        logger.error("Configuration validation failed")
        sys.exit(1)

    try:
        asyncio.run(run_engine(live_cli=args.live))
    except KeyboardInterrupt:
        logger.info("Engine stopped by keyboard interrupt")
    except SystemExit:
        raise
    except Exception as e:
        logger.critical("Engine fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
