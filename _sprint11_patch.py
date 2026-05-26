"""
Sprint 11 — Wire _timed_phase into _run_cycle, add retry decorator,
integrate TradeOutcomeRepository into engine.

Patches auto_trading_engine.py:
  1) Import TradeOutcomeRepository
  2) Init trade_repo in __init__
  3) Wrap _run_cycle pipeline phases with _timed_phase
  4) Add _with_retry() decorator for broker calls
  5) Persist regime snapshot + health log in _run_cycle
  6) Persist trade outcome in _record_learning_outcome
"""
import pathlib
import ast
import sys

ROOT = pathlib.Path(__file__).resolve().parent
ENGINE = ROOT / "src" / "engines" / "auto_trading_engine.py"

src = ENGINE.read_text()

# ──────────────────────────────────────────────────────────────
# PATCH 1 — Import TradeOutcomeRepository
# ──────────────────────────────────────────────────────────────
anchor = "from src.core.errors import ("
repo_import = "from src.core.trade_repo import TradeOutcomeRepository\n"
if "TradeOutcomeRepository" not in src:
    src = src.replace(anchor, repo_import + anchor)
    print("OK 1: Imported TradeOutcomeRepository")
else:
    print("SKIP 1: Already imported")

# ──────────────────────────────────────────────────────────────
# PATCH 2 — Init trade_repo in __init__
# ──────────────────────────────────────────────────────────────
anchor2 = "self._cached_regime: Dict[str, Any] = {}"
repo_init = "self.trade_repo = TradeOutcomeRepository()\n        "
if "self.trade_repo" not in src:
    src = src.replace(anchor2, repo_init + anchor2)
    print("OK 2: Initialized trade_repo in __init__")
else:
    print("SKIP 2: trade_repo already initialized")

# ──────────────────────────────────────────────────────────────
# PATCH 3 — Wrap _run_cycle phases with _timed_phase
# ──────────────────────────────────────────────────────────────

# 3a. Context assembly
old_ctx = """        # Assemble decision context
        try:
            self._context = self.context_assembler.assemble_sync()"""
new_ctx = """        # Assemble decision context
        try:
            async with self._timed_phase("context_assembly"):
                self._context = self.context_assembler.assemble_sync()"""
if old_ctx in src and "_timed_phase" not in src.split("context_assembler.assemble_sync")[0].rsplit("Assemble decision", 1)[-1]:
    src = src.replace(old_ctx, new_ctx, 1)
    print("OK 3a: Wrapped context assembly with _timed_phase")
else:
    if "context_assembly" in src:
        print("SKIP 3a: already wrapped")
    else:
        src = src.replace(old_ctx, new_ctx, 1)
        print("OK 3a: Wrapped context assembly with _timed_phase")

# 3b. Signal generation
old_sig = "        # Generate signals for active markets\n        signals = await self._generate_signals(active_markets)"
new_sig = "        # Generate signals for active markets\n        async with self._timed_phase(\"signal_generation\"):\n            signals = await self._generate_signals(active_markets)"
if old_sig in src:
    src = src.replace(old_sig, new_sig, 1)
    print("OK 3b: Wrapped signal generation with _timed_phase")
else:
    print("SKIP 3b: signal gen already wrapped or not found")

# 3c. Signal validation
old_val = "        # Validate signals\n        validated = await self._validate_signals(signals)"
new_val = "        # Validate signals\n        async with self._timed_phase(\"signal_validation\"):\n            validated = await self._validate_signals(signals)"
if old_val in src:
    src = src.replace(old_val, new_val, 1)
    print("OK 3c: Wrapped signal validation with _timed_phase")
else:
    print("SKIP 3c: validation already wrapped or not found")

# 3d. Position monitoring
old_mon = "        # Monitor existing positions\n        await self._monitor_positions()"
new_mon = "        # Monitor existing positions\n        async with self._timed_phase(\"position_monitoring\"):\n            await self._monitor_positions()"
if old_mon in src:
    src = src.replace(old_mon, new_mon, 1)
    print("OK 3d: Wrapped position monitoring with _timed_phase")
else:
    print("SKIP 3d: monitoring already wrapped or not found")

# ──────────────────────────────────────────────────────────────
# PATCH 4 — Add _with_retry helper method
# ──────────────────────────────────────────────────────────────
retry_method = '''
    async def _with_retry(self, coro_func, *args, retries=3, delay=1.0, **kwargs):
        """Retry an async callable with exponential backoff."""
        last_exc = None
        for attempt in range(retries):
            try:
                return await coro_func(*args, **kwargs)
            except BrokerError as e:
                last_exc = e
                wait = delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d after BrokerError: %s (wait %.1fs)",
                    attempt + 1, retries, e, wait,
                )
                await asyncio.sleep(wait)
            except Exception as e:
                raise  # Non-retryable
        raise last_exc
'''

anchor4 = "    async def _get_broker(self):"
if "_with_retry" not in src:
    src = src.replace(anchor4, retry_method + "\n" + anchor4)
    print("OK 4: Added _with_retry method")
else:
    print("SKIP 4: _with_retry already present")

# ──────────────────────────────────────────────────────────────
# PATCH 5 — Persist regime snapshot after classification
# ──────────────────────────────────────────────────────────────
old_regime = '        if not self._regime_state.get("should_trade", True):'
persist_regime = """        # Persist regime snapshot to DB
        try:
            import json as _json
            await self.trade_repo.save_regime_snapshot({
                "snapshot_time": now.isoformat(),
                "risk_regime": self._regime_state.get("risk_regime", ""),
                "trend_regime": self._regime_state.get("trend_regime", ""),
                "volatility_regime": self._regime_state.get("volatility_regime", ""),
                "composite_regime": self._regime_state.get("regime", ""),
                "should_trade": self._regime_state.get("should_trade", True),
                "entropy": self._regime_state.get("entropy", 0),
                "vix_level": self._regime_state.get("vix", 0),
                "pct_above_sma50": self._regime_state.get("pct_above_sma50", 0),
                "context_snapshot": _json.dumps(
                    {k: str(v) for k, v in list(self._regime_state.items())[:20]},
                    default=str,
                ),
            })
        except Exception:
            pass  # DB persistence is best-effort

"""
if "save_regime_snapshot" not in src:
    src = src.replace(old_regime, persist_regime + "        " + old_regime.lstrip())
    print("OK 5: Added regime snapshot persistence")
else:
    print("SKIP 5: regime persistence already present")

# ──────────────────────────────────────────────────────────────
# PATCH 6 — Persist trade outcome in _record_learning_outcome
# ──────────────────────────────────────────────────────────────
old_record_end = '''            logger.info(
                "Recorded learning outcome: %s %s %.2f%%",
                closed_pos.ticker, reason, closed_pos.realized_pnl_pct,
            )
        except Exception as e:
            logger.warning("Learning loop record error: %s", e)'''

new_record_end = '''            logger.info(
                "Recorded learning outcome: %s %s %.2f%%",
                closed_pos.ticker, reason, closed_pos.realized_pnl_pct,
            )

            # Persist to database (best-effort)
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    self.trade_repo.save_outcome({
                        "trade_id": closed_pos.position_id,
                        "ticker": closed_pos.ticker,
                        "direction": "LONG",
                        "strategy": closed_pos.strategy_id,
                        "entry_price": closed_pos.entry_price,
                        "exit_price": closed_pos.exit_price,
                        "entry_time": (
                            closed_pos.entry_date.isoformat()
                            if closed_pos.entry_date else None
                        ),
                        "exit_time": (
                            closed_pos.exit_date.isoformat()
                            if closed_pos.exit_date else None
                        ),
                        "pnl_pct": closed_pos.realized_pnl_pct,
                        "confidence": 50,
                        "horizon": "swing",
                        "exit_reason": reason,
                        "regime_at_entry": self._cached_regime.get("regime"),
                        "vix_at_entry": self._cached_regime.get("vix"),
                        "rsi_at_entry": None,
                        "adx_at_entry": None,
                        "relative_volume": None,
                        "setup_grade": None,
                        "composite_score": None,
                        "hold_hours": (
                            (closed_pos.exit_date - closed_pos.entry_date
                             ).total_seconds() / 3600
                            if closed_pos.entry_date and closed_pos.exit_date
                            else 0
                        ),
                        "feature_snapshot": None,
                    })
                )
            except Exception:
                pass  # DB persistence is best-effort

        except Exception as e:
            logger.warning("Learning loop record error: %s", e)'''

if "save_outcome" not in src:
    src = src.replace(old_record_end, new_record_end, 1)
    print("OK 6: Added DB persistence in _record_learning_outcome")
else:
    print("SKIP 6: save_outcome already present")

# ──────────────────────────────────────────────────────────────
# WRITE & VALIDATE
# ──────────────────────────────────────────────────────────────
ENGINE.write_text(src)
try:
    ast.parse(src)
    print("OK 7: auto_trading_engine.py syntax valid")
except SyntaxError as e:
    print(f"FAIL 7: SyntaxError: {e}")
    sys.exit(1)

# Count metrics
print(f"\nSummary:")
print(f"  _timed_phase usages: {src.count('_timed_phase')}")
print(f"  TradeOutcomeRepository refs: {src.count('trade_repo')}")
print(f"  _with_retry method: {'present' if '_with_retry' in src else 'missing'}")
print(f"  save_regime_snapshot: {'present' if 'save_regime_snapshot' in src else 'missing'}")
print(f"  save_outcome: {'present' if 'save_outcome' in src else 'missing'}")
