"""
App State — Lazy singleton management for shared services.
Extracted from main.py (Sprint 118) to reduce monolith complexity.

All stateful engine access goes through these getters.
Routers should use request.app.state.* for read access,
or import these getters for lazy initialization.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def init_shared_services(app) -> None:
    """Register shared singletons on app.state.

    Called once at startup. Services are lazily initialized
    on first access via their respective getters.
    """
    from src.engines.regime_router import RegimeRouter
    from src.services.market_data import get_market_data_service

    app.state.market_data = get_market_data_service()
    app.state.regime_router = RegimeRouter()
    app.state.regime_cache = None
    app.state.regime_cache_ts = 0.0
    app.state.macro_intel_cache = None
    app.state.macro_intel_cache_ts = 0.0

    # Engine singletons — lazy init
    app.state.engine = None
    app.state.engine_init_done = False
    app.state.expert_council = None
    app.state.expert_council_init = False
    app.state.learning_loop = None
    app.state.learning_loop_init = False
    app.state.meta_ensemble = None
    app.state.meta_ensemble_init = False

    # Scanner state
    app.state.scanner_service = None
    app.state.scan_signals = None
    app.state.scan_watchlist = []
    app.state.live_indices = []
    app.state.live_sectors = []

    logger.info("[AppState] shared services registered on app.state")


def get_engine(app) -> Optional[Any]:
    """Lazy-init AutoTradingEngine singleton."""
    if not app.state.engine_init_done:
        try:
            from src.engines.auto_trading_engine import AutoTradingEngine

            engine = AutoTradingEngine(dry_run=True)
            engine.market_data = app.state.market_data
            if hasattr(engine, "context_assembler"):
                engine.context_assembler.market_data = app.state.market_data
            app.state.engine = engine
            logger.info("[AppState] AutoTradingEngine created")
        except Exception as exc:
            logger.warning("[AppState] engine init failed: %s", exc)
            app.state.engine = None
        app.state.engine_init_done = True
    return app.state.engine


def get_expert_council(app) -> Optional[Any]:
    """Lazy-init ExpertCouncil singleton."""
    if not app.state.expert_council_init:
        try:
            from src.engines.expert_council import ExpertCouncil

            app.state.expert_council = ExpertCouncil()
            logger.info("[AppState] ExpertCouncil created")
        except Exception as exc:
            logger.warning("[AppState] ExpertCouncil init failed: %s", exc)
            app.state.expert_council = None
        app.state.expert_council_init = True
    return app.state.expert_council


def get_learning_loop(app) -> Optional[Any]:
    """Lazy-init LearningLoopPipeline singleton."""
    if not app.state.learning_loop_init:
        try:
            from src.engines.learning_loop import LearningLoopPipeline

            app.state.learning_loop = LearningLoopPipeline()
            logger.info("[AppState] LearningLoopPipeline created")
        except Exception as exc:
            logger.warning("[AppState] LearningLoopPipeline init failed: %s", exc)
            app.state.learning_loop = None
        app.state.learning_loop_init = True
    return app.state.learning_loop


def get_meta_ensemble(app) -> Optional[Any]:
    """Lazy-init MetaEnsemble singleton."""
    if not app.state.meta_ensemble_init:
        try:
            from src.engines.meta_ensemble import MetaEnsemble

            app.state.meta_ensemble = MetaEnsemble()
            logger.info("[AppState] MetaEnsemble created")
        except Exception as exc:
            logger.warning("[AppState] MetaEnsemble init failed: %s", exc)
            app.state.meta_ensemble = None
        app.state.meta_ensemble_init = True
    return app.state.meta_ensemble


async def get_regime(app) -> Any:
    """Return cached RegimeState, refreshing every 60s.

    Single source of truth — all endpoints read from here.
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
        logger.warning("[AppState] regime classify error: %s", exc)
        if app.state.regime_cache:
            return app.state.regime_cache
        from src.engines.regime_router import RegimeState

        return RegimeState()
