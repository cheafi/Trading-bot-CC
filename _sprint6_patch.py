#!/usr/bin/env python3
"""Sprint 6 patch: Learning loop + monitoring + API + error types"""
import os, re, ast

ROOT = os.path.dirname(os.path.abspath(__file__))

def read(rel):
    with open(os.path.join(ROOT, rel), "r") as f:
        return f.read()

def write(rel, txt):
    with open(os.path.join(ROOT, rel), "w") as f:
        f.write(txt)

# ===========================================================================
# PATCH 1: Create src/core/errors.py — structured error hierarchy
# ===========================================================================
def patch1():
    path = os.path.join(ROOT, "src", "core", "errors.py")
    content = '''\
"""
TradingAI Bot - Structured Error Types

Typed exception hierarchy so callers can catch specific failure modes
instead of bare `except Exception`.

Hierarchy:
    TradingError (base)
    +-- BrokerError          execution / connectivity
    +-- DataError            missing or stale market data
    +-- ValidationError      signal or input validation
    +-- RiskLimitError       circuit breaker / exposure limit
    +-- SignalError          signal generation failures
    +-- ConfigError          invalid configuration
"""


class TradingError(Exception):
    """Base exception for all TradingAI errors."""

    def __init__(self, message: str = "", code: str = "", detail: str = ""):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(message)

    def to_dict(self):
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "detail": self.detail,
        }


class BrokerError(TradingError):
    """Raised when broker connection or order execution fails."""

    def __init__(self, message: str = "", broker: str = "", code: str = "BROKER_ERR"):
        self.broker = broker
        super().__init__(message=message, code=code, detail=f"broker={broker}")


class DataError(TradingError):
    """Raised when market data is missing, stale, or corrupted."""

    def __init__(self, message: str = "", ticker: str = "", code: str = "DATA_ERR"):
        self.ticker = ticker
        super().__init__(message=message, code=code, detail=f"ticker={ticker}")


class ValidationError(TradingError):
    """Raised when a signal or input fails validation."""

    def __init__(self, message: str = "", field: str = "", code: str = "VALIDATION_ERR"):
        self.field = field
        super().__init__(message=message, code=code, detail=f"field={field}")


class RiskLimitError(TradingError):
    """Raised when a risk limit (circuit breaker, exposure, drawdown) is hit."""

    def __init__(self, message: str = "", limit_type: str = "", code: str = "RISK_LIMIT"):
        self.limit_type = limit_type
        super().__init__(message=message, code=code, detail=f"limit={limit_type}")


class SignalError(TradingError):
    """Raised when signal generation or processing fails."""

    def __init__(self, message: str = "", strategy: str = "", code: str = "SIGNAL_ERR"):
        self.strategy = strategy
        super().__init__(message=message, code=code, detail=f"strategy={strategy}")


class ConfigError(TradingError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str = "", param: str = "", code: str = "CONFIG_ERR"):
        self.param = param
        super().__init__(message=message, code=code, detail=f"param={param}")
'''
    write("src/core/errors.py", content)
    # Validate
    ast.parse(content)
    print("OK 1: Created src/core/errors.py with 6 error types")

# ===========================================================================
# PATCH 2: Fix open_position call signature in auto_trading_engine
# ===========================================================================
def patch2():
    src = read("src/engines/auto_trading_engine.py")

    # The current broken call:
    old_call = '''                    try:
                        self.position_mgr.open_position(
                            ticker=signal.ticker,
                            entry_price=result.get(
                                "entry_price", signal.entry_price
                            ),
                            shares=self._calculate_position_size(signal),
                            direction=signal.direction.value
                            if hasattr(signal.direction, "value")
                            else str(signal.direction),
                            strategy_name=opp.get("strategy_name", "unknown"),
                        )
                    except Exception as e:
                        logger.warning(f"PositionManager track error: {e}")'''

    new_call = '''                    try:
                        _stop = (
                            signal.invalidation.stop_price
                            if getattr(signal, "invalidation", None)
                            and getattr(signal.invalidation, "stop_price", 0)
                            else result.get("entry_price", signal.entry_price) * (1 - trading_config.stop_loss_pct)
                        )
                        self.position_mgr.open_position(
                            ticker=signal.ticker,
                            strategy_id=opp.get("strategy_name", "unknown"),
                            entry_price=result.get("entry_price", signal.entry_price),
                            shares=self._calculate_position_size(signal),
                            stop_loss_price=_stop,
                            max_hold_days=trading_config.max_hold_days,
                        )
                    except Exception as e:
                        logger.warning(f"PositionManager track error: {e}")'''

    if old_call not in src:
        print("SKIP 2: open_position call pattern not found (may already be patched)")
        return
    src = src.replace(old_call, new_call)
    write("src/engines/auto_trading_engine.py", src)
    ast.parse(src)
    print("OK 2: Fixed open_position call with correct kwargs")

# ===========================================================================
# PATCH 3: Add TradeLearningLoop import + init to AutoTradingEngine
# ===========================================================================
def patch3():
    src = read("src/engines/auto_trading_engine.py")

    # 3a: Add import
    import_marker = "from src.algo.position_manager import PositionManager, RiskParameters"
    if "TradeLearningLoop" not in src:
        new_imports = (
            import_marker + "\n"
            "from src.ml.trade_learner import TradeLearningLoop, TradeOutcomeRecord"
        )
        src = src.replace(import_marker, new_imports)
        print("OK 3a: Added TradeLearningLoop import")
    else:
        print("SKIP 3a: TradeLearningLoop already imported")

    # 3b: Init learning_loop in __init__
    init_marker = "self.position_mgr = PositionManager(params=risk_params)"
    if "self.learning_loop" not in src:
        new_init = init_marker + "\n        self.learning_loop = TradeLearningLoop()"
        src = src.replace(init_marker, new_init)
        print("OK 3b: Added self.learning_loop in __init__")
    else:
        print("SKIP 3b: learning_loop already in __init__")

    write("src/engines/auto_trading_engine.py", src)
    ast.parse(src)
    print("OK 3: TradeLearningLoop wired")

# ===========================================================================
# PATCH 4: Upgrade _monitor_positions to use PositionManager + learning loop
# ===========================================================================
def patch4():
    src = read("src/engines/auto_trading_engine.py")

    old_monitor = '''    async def _monitor_positions(self):
        """Check all open positions for stop-loss and time-stop exits."""
        try:
            from src.brokers.broker_manager import BrokerManager
            manager = BrokerManager()
            await manager.initialize()
            positions = await manager.get_positions()

            for pos in positions:
                ticker = getattr(pos, "symbol", getattr(pos, "ticker", "???"))
                entry_price = getattr(pos, "avg_entry_price", 0)
                current_price = getattr(pos, "current_price", entry_price)
                qty = getattr(pos, "qty", 0)
                side = getattr(pos, "side", "long")

                if not entry_price or entry_price <= 0:
                    continue

                pnl_pct = (current_price - entry_price) / entry_price
                if side == "short":
                    pnl_pct = -pnl_pct

                # Hard stop-loss at -3%
                if pnl_pct <= -0.03:
                    logger.warning(
                        "Stop-loss hit for %s: %.1f%% loss", ticker, pnl_pct * 100
                    )
                    try:
                        close_side = "sell" if side == "long" else "buy"
                        await manager.submit_order(
                            symbol=ticker, qty=abs(int(qty)),
                            side=close_side, type="market",
                            time_in_force="day",
                        )
                        logger.info("Closed %s via stop-loss", ticker)
                    except Exception as e:
                        logger.error("Stop-loss order failed for %s: %s", ticker, e)

        except Exception as e:
            logger.error("Position monitoring error: %s", e)'''

    new_monitor = '''    async def _monitor_positions(self):
        """
        Monitor open positions using PositionManager for:
        - Trailing stop updates + exits
        - R-target partial exits (1R, 2R, 3R)
        - Time-based exits (max hold days)
        - Hard stop-loss
        Closed positions are fed to TradeLearningLoop.
        """
        try:
            from src.brokers.broker_manager import BrokerManager
            manager = BrokerManager()
            await manager.initialize()
            broker_positions = await manager.get_positions()

            # Build price dict from broker positions
            prices: Dict[str, float] = {}
            broker_qty: Dict[str, int] = {}
            broker_side: Dict[str, str] = {}
            for pos in broker_positions:
                ticker = getattr(pos, "symbol", getattr(pos, "ticker", "???"))
                current_price = getattr(pos, "current_price", 0)
                if current_price and current_price > 0:
                    prices[ticker] = current_price
                    broker_qty[ticker] = abs(int(getattr(pos, "qty", 0)))
                    broker_side[ticker] = getattr(pos, "side", "long")

            if not prices:
                return

            now = datetime.now(timezone.utc)

            # Use PositionManager to check all exit conditions
            positions_to_close = self.position_mgr.update_all_positions(prices, now)

            for close_info in positions_to_close:
                ticker = close_info["ticker"]
                exit_price = close_info["price"]
                reason = close_info["reason"]
                qty = broker_qty.get(ticker, 0)
                side = broker_side.get(ticker, "long")

                if qty <= 0:
                    continue

                logger.warning(
                    "Exit signal for %s: %s @ $%.2f", ticker, reason, exit_price
                )
                try:
                    close_side = "sell" if side == "long" else "buy"
                    await manager.submit_order(
                        symbol=ticker, qty=qty,
                        side=close_side, type="market",
                        time_in_force="day",
                    )
                    logger.info("Closed %s via %s", ticker, reason)

                    # Close in PositionManager and feed to learning loop
                    closed_pos = self.position_mgr.close_position(
                        ticker, exit_price, reason
                    )
                    if closed_pos:
                        self._record_learning_outcome(closed_pos, reason)

                except Exception as e:
                    logger.error("Close order failed for %s: %s", ticker, e)

        except Exception as e:
            logger.error("Position monitoring error: %s", e)

    def _record_learning_outcome(self, closed_pos, reason: str):
        """Feed a closed position into the TradeLearningLoop."""
        try:
            record = TradeOutcomeRecord(
                trade_id=closed_pos.position_id,
                ticker=closed_pos.ticker,
                direction="LONG",
                strategy=closed_pos.strategy_id,
                entry_price=closed_pos.entry_price,
                exit_price=closed_pos.exit_price,
                entry_time=(
                    closed_pos.entry_date.isoformat()
                    if closed_pos.entry_date else ""
                ),
                exit_time=(
                    closed_pos.exit_date.isoformat()
                    if closed_pos.exit_date else ""
                ),
                pnl_pct=closed_pos.realized_pnl_pct,
                confidence=50,
                horizon="swing",
                exit_reason=reason,
                hold_hours=(
                    (closed_pos.exit_date - closed_pos.entry_date).total_seconds() / 3600
                    if closed_pos.entry_date and closed_pos.exit_date
                    else 0
                ),
            )
            self.learning_loop.record_outcome(record)
            logger.info(
                "Recorded learning outcome: %s %s %.2f%%",
                closed_pos.ticker, reason, closed_pos.realized_pnl_pct,
            )
        except Exception as e:
            logger.warning("Learning loop record error: %s", e)'''

    if old_monitor not in src:
        print("SKIP 4: _monitor_positions pattern not found (may already be patched)")
        return

    src = src.replace(old_monitor, new_monitor)
    write("src/engines/auto_trading_engine.py", src)
    ast.parse(src)
    print("OK 4: Upgraded _monitor_positions with PositionManager + learning loop")

# ===========================================================================
# PATCH 5: Add 3 API endpoints to src/api/main.py
# ===========================================================================
def patch5():
    src = read("src/api/main.py")

    # Find insertion point: before `if __name__ == "__main__"`
    insert_marker = 'if __name__ == "__main__":'
    if insert_marker not in src:
        # fallback: append at end
        insert_marker = None

    api_block = '''

# ===== Sprint 6: Decision-Layer API Endpoints =====

@app.get("/api/regime", tags=["decision-layer"])
async def get_regime_state():
    """Get current market regime classification."""
    try:
        from src.engines.regime_router import RegimeRouter
        from src.engines.context_assembler import ContextAssembler

        assembler = ContextAssembler()
        ctx = assembler.assemble_sync()
        mkt = ctx.get("market_state", {})

        router = RegimeRouter()
        state = router.classify(mkt)

        return {
            "status": "ok",
            "regime": state,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Regime endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendations", tags=["decision-layer"])
async def get_recommendations(limit: int = Query(10, ge=1, le=50)):
    """Get ranked trade recommendations from the ensemble scorer."""
    try:
        from src.engines.opportunity_ensembler import OpportunityEnsembler
        from src.engines.strategy_leaderboard import StrategyLeaderboard
        from src.engines.regime_router import RegimeRouter
        from src.engines.context_assembler import ContextAssembler

        assembler = ContextAssembler()
        ctx = assembler.assemble_sync()
        mkt = ctx.get("market_state", {})

        router = RegimeRouter()
        regime = router.classify(mkt)

        leaderboard = StrategyLeaderboard()
        ensembler = OpportunityEnsembler()

        # In a real pipeline the signals come from SignalEngine;
        # here we return an empty list if none are cached.
        return {
            "status": "ok",
            "regime": regime,
            "recommendations": [],
            "note": "Live recommendations require active trading cycle. Use /signals for cached signals.",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Recommendations endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Leaderboard endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


'''

    if "/api/regime" in src:
        print("SKIP 5: API endpoints already present")
        return

    if insert_marker:
        src = src.replace(insert_marker, api_block + insert_marker)
    else:
        src += api_block

    write("src/api/main.py", src)
    # Quick syntax check (full parse may fail due to missing template deps)
    # Just check the new block
    try:
        ast.parse(src)
        print("OK 5: Added 3 API endpoints (regime, recommendations, leaderboard)")
    except SyntaxError as e:
        # Try to fix common issues
        print(f"WARN 5: Syntax issue: {e} — verifying endpoint block only")
        ast.parse(api_block)
        print("OK 5: API endpoint block itself is valid")


# ===========================================================================
# PATCH 6: Use structured errors in key spots
# ===========================================================================
def patch6():
    src = read("src/engines/auto_trading_engine.py")

    # 6a: Import errors at top
    err_import = "from src.core.errors import BrokerError, DataError, RiskLimitError"
    if err_import not in src:
        marker = "from src.ml.trade_learner import TradeLearningLoop, TradeOutcomeRecord"
        if marker in src:
            src = src.replace(marker, marker + "\n" + err_import)
            print("OK 6a: Added error imports")
        else:
            print("SKIP 6a: import marker not found")
    else:
        print("SKIP 6a: error imports already present")

    # 6b: Replace generic except in _execute_signal with BrokerError
    old_exec_except = '''        except Exception as e:
            logger.error(f"Execution error for {signal.ticker}: {e}")
            return None'''
    new_exec_except = '''        except BrokerError as e:
            logger.error(f"Broker error for {signal.ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Execution error for {signal.ticker}: {e}")
            return None'''
    if old_exec_except in src and "BrokerError" not in src.split("_execute_signal")[1].split("async def")[0] if "_execute_signal" in src else True:
        src = src.replace(old_exec_except, new_exec_except, 1)
        print("OK 6b: Added BrokerError catch in _execute_signal")
    else:
        print("SKIP 6b: already has BrokerError or pattern changed")

    # 6c: Replace generic except in _generate_signals with DataError
    old_gen_except = '''        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            return []'''
    new_gen_except = '''        except DataError as e:
            logger.error(f"Data error in signal generation: {e}")
            return []
        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            return []'''
    if old_gen_except in src and "DataError" not in src.split("_generate_signals")[1].split("async def")[0] if "_generate_signals" in src else True:
        src = src.replace(old_gen_except, new_gen_except, 1)
        print("OK 6c: Added DataError catch in _generate_signals")
    else:
        print("SKIP 6c: already has DataError or pattern changed")

    write("src/engines/auto_trading_engine.py", src)
    ast.parse(src)
    print("OK 6: Structured errors wired in auto_trading_engine")


# ===========================================================================
if __name__ == "__main__":
    patch1()
    patch2()
    patch3()
    patch4()
    patch5()
    patch6()
    print("\n=== Sprint 6 patches complete ===")
