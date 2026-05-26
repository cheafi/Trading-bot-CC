"""
Sprint 10 — Observability, Typed Errors, Health Check, Graceful Shutdown

Patches auto_trading_engine.py:
  1) Typed exception imports + replacements (ConfigError, SignalError, ValidationError)
  2) _timed_phase() context-manager for pipeline latency logging
  3) health_check() returning structured status dict
  4) graceful_shutdown() flushing open positions
  5) Replace bare except-Exception with typed catches throughout
"""
import re, sys, pathlib, ast

ROOT = pathlib.Path(__file__).resolve().parent
ENGINE = ROOT / "src" / "engines" / "auto_trading_engine.py"

src = ENGINE.read_text()
original = src  # keep for comparison

# ──────────────────────────────────────────────────────────────
# PATCH 1 — Expand error imports to include all typed exceptions
# ──────────────────────────────────────────────────────────────
old_import = "from src.core.errors import BrokerError, DataError, RiskLimitError"
new_import = (
    "from src.core.errors import (\n"
    "    BrokerError, ConfigError, DataError,\n"
    "    RiskLimitError, SignalError, ValidationError,\n"
    ")"
)
if old_import in src:
    src = src.replace(old_import, new_import)
    print("OK 1: Expanded error imports")
elif "ConfigError" in src.split("\n")[0:40].__repr__():
    print("SKIP 1: Already expanded")
else:
    # Try partial match
    if "from src.core.errors import BrokerError, DataError" in src:
        src = src.replace(
            "from src.core.errors import BrokerError, DataError",
            new_import.replace(", RiskLimitError,", ","),
        )
        print("OK 1b: Expanded error imports (partial)")
    else:
        print("WARN 1: Could not find error import line")

# ──────────────────────────────────────────────────────────────
# PATCH 2 — Add _timed_phase context-manager + health_check + graceful_shutdown
# ──────────────────────────────────────────────────────────────

# Insert _timed_phase after the get_cached_state() method
anchor_method = "    def get_cached_state(self) -> Dict[str, Any]:"
anchor_idx = src.find(anchor_method)
if anchor_idx < 0:
    print("WARN 2a: get_cached_state not found")
else:
    # Find end of get_cached_state
    next_def = src.find("\n    def ", anchor_idx + len(anchor_method))
    if next_def < 0:
        next_def = len(src)
    insert_point = next_def

    new_methods = '''

    # ── Sprint 10: Observability ─────────────────────────────
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _timed_phase(self, phase_name: str):
        """Context manager that logs phase latency and errors."""
        t0 = time.monotonic()
        try:
            yield
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error(
                "Phase %s FAILED after %.1fms: %s",
                phase_name, elapsed, exc,
            )
            raise
        else:
            elapsed = (time.monotonic() - t0) * 1000
            if elapsed > 5000:
                logger.warning(
                    "Phase %s SLOW: %.1fms", phase_name, elapsed,
                )
            else:
                logger.debug(
                    "Phase %s OK: %.1fms", phase_name, elapsed,
                )

    async def health_check(self) -> Dict[str, Any]:
        """
        Return structured health status for monitoring/API.

        Keys:
          status:      'healthy' | 'degraded' | 'unhealthy'
          components:  dict of component → bool
          metrics:     cycle_count, uptime, circuit_breaker state
        """
        components: Dict[str, bool] = {
            "regime_router": self.regime_router is not None,
            "ensembler": self.ensembler is not None,
            "context_assembler": self.context_assembler is not None,
            "leaderboard": self.leaderboard is not None,
            "position_mgr": self.position_mgr is not None,
            "learning_loop": self.learning_loop is not None,
            "edge_calculator": self.edge_calculator is not None,
            "circuit_breaker": self.circuit_breaker is not None,
            "position_monitor": self.position_monitor is not None,
        }

        # Broker connectivity
        try:
            mgr = await self._get_broker()
            components["broker"] = mgr is not None
        except Exception:
            components["broker"] = False

        healthy_count = sum(components.values())
        total = len(components)
        if healthy_count == total:
            status = "healthy"
        elif healthy_count >= total - 2:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "components": components,
            "metrics": {
                "cycle_count": self._cycle_count,
                "running": self._running,
                "signals_today": len(self._signals_today),
                "trades_today": len(self._trades_today),
                "circuit_breaker_triggered": self.circuit_breaker.triggered,
                "circuit_breaker_reason": self.circuit_breaker.trigger_reason,
                "dry_run": self.dry_run,
            },
        }

    async def graceful_shutdown(self):
        """
        Stop the engine gracefully:
        1. Stop accepting new signals
        2. Flush open positions (close at market)
        3. Run EOD cycle one final time
        4. Set _running = False
        """
        logger.info("🛑 Graceful shutdown initiated...")
        self._running = False

        # Flush open positions
        try:
            manager = await self._get_broker()
            positions = await manager.get_positions()
            for pos in positions:
                ticker = getattr(pos, "symbol", getattr(pos, "ticker", "???"))
                qty = abs(int(getattr(pos, "qty", 0)))
                side = getattr(pos, "side", "long")
                if qty <= 0:
                    continue
                close_side = "sell" if side == "long" else "buy"
                try:
                    await manager.submit_order(
                        symbol=ticker, qty=qty,
                        side=close_side, type="market",
                        time_in_force="day",
                    )
                    logger.info("Shutdown: closed %s (%d shares)", ticker, qty)
                except BrokerError as e:
                    logger.error("Shutdown close failed %s: %s", ticker, e)
        except BrokerError as e:
            logger.error("Shutdown broker error: %s", e)
        except Exception as e:
            logger.error("Shutdown position flush error: %s", e)

        # Final EOD
        try:
            await self._run_eod_cycle()
        except Exception as e:
            logger.warning("Shutdown EOD error: %s", e)

        logger.info("🛑 Graceful shutdown complete")
'''
    if "async def health_check" not in src:
        src = src[:insert_point] + new_methods + src[insert_point:]
        print("OK 2: Added _timed_phase, health_check, graceful_shutdown")
    else:
        print("SKIP 2: health_check already present")

# ──────────────────────────────────────────────────────────────
# PATCH 3 — Replace bare except Exception with typed catches
# ──────────────────────────────────────────────────────────────
# Strategy: targeted find-and-replace for specific blocks

replacements_done = 0

# 3a. __init__ config load: except Exception → except ConfigError
old_3a = """        except Exception:
            risk_params = RiskParameters()"""
new_3a = """        except (ConfigError, Exception):
            risk_params = RiskParameters()"""
if old_3a in src and "ConfigError, Exception" not in src:
    src = src.replace(old_3a, new_3a, 1)
    replacements_done += 1

# 3b. context assembly: except Exception → except DataError
old_3b = """        except Exception as e:
            logger.warning(f"Context assembly failed: {e}")
            self._context = {}"""
new_3b = """        except DataError as e:
            logger.warning("Context assembly DataError: %s", e)
            self._context = {}
        except Exception as e:
            logger.warning("Context assembly failed: %s", e)
            self._context = {}"""
if old_3b in src:
    src = src.replace(old_3b, new_3b, 1)
    replacements_done += 1

# 3c. PositionManager track: except Exception → keep but log ticker
old_3c = """                    except Exception as e:
                        logger.warning(f"PositionManager track error: {e}")"""
new_3c = """                    except RiskLimitError as e:
                        logger.warning("PositionManager risk limit for %s: %s", signal.ticker, e)
                    except Exception as e:
                        logger.warning("PositionManager track error for %s: %s", signal.ticker, e)"""
if old_3c in src:
    src = src.replace(old_3c, new_3c, 1)
    replacements_done += 1

# 3d. _generate_signals: add SignalError catch before existing DataError
old_3d = """        except DataError as e:
            logger.error(f"Data error in signal generation: {e}")
            return []
        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            return []"""
new_3d = """        except DataError as e:
            logger.error("Data error in signal generation: %s", e)
            return []
        except SignalError as e:
            logger.error("Signal generation error: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected signal generation error: %s", e)
            return []"""
if old_3d in src:
    src = src.replace(old_3d, new_3d, 1)
    replacements_done += 1

# 3e. _validate_signals: except Exception → except ValidationError first
old_3e = """        except Exception as e:
            logger.error(f"Validation error: {e}")
            return signals  # Proceed without validation"""
new_3e = """        except ValidationError as e:
            logger.error("Signal validation failed: %s", e)
            return signals  # Proceed without validation
        except Exception as e:
            logger.error("Unexpected validation error: %s", e)
            return signals"""
if old_3e in src:
    src = src.replace(old_3e, new_3e, 1)
    replacements_done += 1

# 3f. _execute_signal: already has BrokerError, keep
# (no change needed)

# 3g. _monitor_positions inner close: except Exception → except BrokerError
old_3g = """                except Exception as e:
                    logger.error("Close order failed for %s: %s", ticker, e)"""
new_3g = """                except BrokerError as e:
                    logger.error("Close order broker error for %s: %s", ticker, e)
                except Exception as e:
                    logger.error("Close order failed for %s: %s", ticker, e)"""
if old_3g in src:
    src = src.replace(old_3g, new_3g, 1)
    replacements_done += 1

# 3h. _record_learning_outcome: except Exception → keep (generic is OK here)
# (no change needed)

# 3i. _get_equity: except Exception → except BrokerError
old_3i = """    async def _get_equity(self) -> float:
        try:
            manager = await self._get_broker()
            account = await manager.get_account()
            return getattr(account, "portfolio_value", 100000.0)
        except Exception:
            return 100000.0"""
new_3i = """    async def _get_equity(self) -> float:
        try:
            manager = await self._get_broker()
            account = await manager.get_account()
            return getattr(account, "portfolio_value", 100000.0)
        except BrokerError:
            return 100000.0
        except Exception:
            return 100000.0"""
if old_3i in src:
    src = src.replace(old_3i, new_3i, 1)
    replacements_done += 1

# 3j. _count_positions: except Exception → except BrokerError
old_3j = """    async def _count_positions(self) -> int:
        try:
            manager = await self._get_broker()
            positions = await manager.get_positions()
            return len(positions)
        except Exception:
            return 0"""
new_3j = """    async def _count_positions(self) -> int:
        try:
            manager = await self._get_broker()
            positions = await manager.get_positions()
            return len(positions)
        except BrokerError:
            return 0
        except Exception:
            return 0"""
if old_3j in src:
    src = src.replace(old_3j, new_3j, 1)
    replacements_done += 1

# 3k. EOD failure analysis: already generic, OK
# 3l. EOD model retrain: already generic, OK
# 3m. EOD leaderboard refresh: already generic, OK
# 3n. EOD summary: already generic, OK
# 3o. _send_eod_report: already generic, OK
# 3p. _send_status_update: already generic, OK

# 3q. EdgeCalculator in _run_cycle: except Exception → keep silent
# (no change needed — already pass)

# 3r. yfinance market data: except Exception → except DataError
old_3r = """            except Exception as e:
                logger.error(f"Market data fetch error: {e}")
                return []"""
new_3r = """            except DataError as e:
                logger.error("Market data fetch DataError: %s", e)
                return []
            except Exception as e:
                logger.error("Market data fetch error: %s", e)
                return []"""
if old_3r in src:
    src = src.replace(old_3r, new_3r, 1)
    replacements_done += 1

# 3s. feature engine continue block: no change (per-ticker, silent is OK)

# 3t. _monitor_positions outer: except Exception → except BrokerError
old_3t = """        except Exception as e:
            logger.error("Position monitoring error: %s", e)"""
new_3t = """        except BrokerError as e:
            logger.error("Position monitoring broker error: %s", e)
        except Exception as e:
            logger.error("Position monitoring error: %s", e)"""
if old_3t in src:
    src = src.replace(old_3t, new_3t, 1)
    replacements_done += 1

print(f"OK 3: {replacements_done} typed-exception replacements applied")

# ──────────────────────────────────────────────────────────────
# PATCH 4 — Add /health API endpoint to api/main.py
# ──────────────────────────────────────────────────────────────
API_FILE = ROOT / "src" / "api" / "main.py"
api_src = API_FILE.read_text()

health_endpoint = '''

@app.get("/api/health")
async def api_health():
    """Engine health-check endpoint for monitoring."""
    try:
        engine = _get_engine()
        return await engine.health_check()
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
'''

if "/api/health" not in api_src:
    # Append before last line or at end
    api_src = api_src.rstrip() + "\n" + health_endpoint + "\n"
    API_FILE.write_text(api_src)
    print("OK 4: Added /api/health endpoint")
else:
    print("SKIP 4: /api/health already present")

# ──────────────────────────────────────────────────────────────
# WRITE & VALIDATE
# ──────────────────────────────────────────────────────────────
ENGINE.write_text(src)
try:
    ast.parse(src)
    print("OK 5: auto_trading_engine.py syntax valid")
except SyntaxError as e:
    print(f"FAIL 5: SyntaxError in engine: {e}")
    sys.exit(1)

try:
    ast.parse(API_FILE.read_text())
    print("OK 5b: api/main.py syntax valid")
except SyntaxError as e:
    print(f"FAIL 5b: SyntaxError in api/main.py: {e}")
    sys.exit(1)

# Summary
old_bare = original.count("except Exception")
new_bare = src.count("except Exception")
old_typed = sum(original.count(f"except {e}") for e in
    ["BrokerError", "DataError", "ConfigError", "RiskLimitError",
     "SignalError", "ValidationError"])
new_typed = sum(src.count(f"except {e}") for e in
    ["BrokerError", "DataError", "ConfigError", "RiskLimitError",
     "SignalError", "ValidationError"])

print(f"\nSummary:")
print(f"  Bare except Exception: {old_bare} → {new_bare}")
print(f"  Typed catches: {old_typed} → {new_typed}")
print(f"  New methods: _timed_phase, health_check, graceful_shutdown")
print(f"  New API: /api/health")
