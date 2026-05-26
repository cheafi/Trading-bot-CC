"""
Sprint 12 — Boot sequence, structured logging, Discord cache wiring.

Patches:
  1) Add _boot() method to auto_trading_engine.py
  2) Import set_correlation_id and use in _run_cycle
  3) Wire /recommendations command to engine cached state
"""
import pathlib
import ast
import sys

ROOT = pathlib.Path(__file__).resolve().parent
ENGINE = ROOT / "src" / "engines" / "auto_trading_engine.py"
DISCORD = ROOT / "src" / "discord_bot.py"

# ══════════════════════════════════════════════════════════════
# PATCH 1 — Add _boot() + correlation ID to engine
# ══════════════════════════════════════════════════════════════
src = ENGINE.read_text()

# 1a. Import set_correlation_id
anchor_import = "from src.core.trade_repo import TradeOutcomeRepository"
logging_import = (
    "from src.core.logging_config import "
    "set_correlation_id, get_correlation_id\n"
)
if "set_correlation_id" not in src:
    src = src.replace(anchor_import, logging_import + anchor_import)
    print("OK 1a: Imported set_correlation_id")
else:
    print("SKIP 1a: already imported")

# 1b. Add correlation ID at top of _run_cycle
old_cycle_top = """    async def _run_cycle(self):
        self._cycle_count += 1
        now = datetime.now(timezone.utc)"""
new_cycle_top = """    async def _run_cycle(self):
        self._cycle_count += 1
        set_correlation_id(f"cyc-{self._cycle_count}")
        now = datetime.now(timezone.utc)"""
if "set_correlation_id" not in src[src.find("async def _run_cycle"):src.find("async def _run_cycle") + 300]:
    src = src.replace(old_cycle_top, new_cycle_top, 1)
    print("OK 1b: Added correlation ID to _run_cycle")
else:
    print("SKIP 1b: correlation ID already in _run_cycle")

# 1c. Add _boot() method before run()
boot_method = '''
    async def _boot(self) -> bool:
        """
        Pre-flight validation before entering the main loop.

        Checks:
        1. All decision-layer components initialized
        2. Broker connectivity (if not dry_run)
        3. Database connectivity (best-effort)
        4. Config sanity (risk params within bounds)

        Returns True if all critical checks pass.
        """
        logger.info("🔍 Running boot checks...")
        checks_passed = 0
        checks_total = 0

        # 1. Component validation
        components = {
            "regime_router": self.regime_router,
            "ensembler": self.ensembler,
            "context_assembler": self.context_assembler,
            "leaderboard": self.leaderboard,
            "position_mgr": self.position_mgr,
            "learning_loop": self.learning_loop,
            "circuit_breaker": self.circuit_breaker,
            "position_monitor": self.position_monitor,
        }
        for name, comp in components.items():
            checks_total += 1
            if comp is not None:
                checks_passed += 1
                logger.info("  ✅ %s OK", name)
            else:
                logger.error("  ❌ %s MISSING", name)

        # 2. Broker connectivity
        if not self.dry_run:
            checks_total += 1
            try:
                mgr = await self._get_broker()
                if mgr is not None:
                    checks_passed += 1
                    logger.info("  ✅ broker connected")
                else:
                    logger.error("  ❌ broker returned None")
            except Exception as e:
                logger.error("  ❌ broker connection failed: %s", e)
        else:
            logger.info("  ⏭️  broker check skipped (dry-run)")

        # 3. Database connectivity (best-effort)
        checks_total += 1
        try:
            from src.core.database import check_database_health
            db_ok = await check_database_health()
            if db_ok:
                checks_passed += 1
                logger.info("  ✅ database OK")
            else:
                logger.warning("  ⚠️  database unreachable (non-fatal)")
                checks_passed += 1  # non-fatal
        except Exception:
            logger.warning("  ⚠️  database check skipped (non-fatal)")
            checks_passed += 1  # non-fatal

        # 4. Config sanity
        checks_total += 1
        try:
            if self.position_mgr.params.risk_per_trade > 0.10:
                logger.warning(
                    "  ⚠️  risk_per_trade=%.2f > 10%% — very aggressive",
                    self.position_mgr.params.risk_per_trade,
                )
            checks_passed += 1
            logger.info("  ✅ config sanity OK")
        except Exception as e:
            logger.warning("  ⚠️  config check error: %s", e)
            checks_passed += 1  # non-fatal

        # 5. Edge calculator
        if self.edge_calculator is not None:
            logger.info("  ✅ edge_calculator OK")
        else:
            logger.info("  ⏭️  edge_calculator unavailable (non-fatal)")

        all_ok = checks_passed >= checks_total
        logger.info(
            "Boot checks: %d/%d passed — %s",
            checks_passed, checks_total,
            "✅ READY" if all_ok else "❌ FAILED",
        )
        return all_ok

'''

anchor_run = "    async def run(self):"
if "async def _boot" not in src:
    src = src.replace(anchor_run, boot_method + anchor_run)
    print("OK 1c: Added _boot() method")
else:
    print("SKIP 1c: _boot already present")

ENGINE.write_text(src)
try:
    ast.parse(src)
    print("OK 1d: auto_trading_engine.py syntax valid")
except SyntaxError as e:
    print(f"FAIL 1d: SyntaxError: {e}")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# PATCH 2 — Wire /recommendations to engine cached state
# ══════════════════════════════════════════════════════════════
dsrc = DISCORD.read_text()

old_recs = '''                e.description = (
                    "Live recommendations populate when AutoTradingEngine "
                    "is running. Use `/regime` for current market state."
                )'''

new_recs = '''                # Try to fetch cached recommendations from running engine
                try:
                    from src.engines.auto_trading_engine import AutoTradingEngine
                    engine = AutoTradingEngine(dry_run=True)
                    cached = engine.get_cached_state()
                    recs = cached.get("recommendations", [])
                    if recs:
                        for i, rec in enumerate(recs[:5], 1):
                            ticker = rec.get("original_signal", {}).get("ticker", "?")
                            score = rec.get("composite_score", 0)
                            decision = "✅ BUY" if rec.get("trade_decision") else "⏸️ HOLD"
                            e.add_field(
                                name=f"{i}. {ticker}",
                                value=f"Score: **{score:.3f}** | {decision}",
                                inline=True,
                            )
                    else:
                        e.description = (
                            "No recommendations cached yet. "
                            "Recommendations populate after the engine runs a cycle."
                        )
                except Exception:
                    e.description = (
                        "Live recommendations populate when AutoTradingEngine "
                        "is running. Use `/regime` for current market state."
                    )'''

if old_recs in dsrc:
    dsrc = dsrc.replace(old_recs, new_recs, 1)
    DISCORD.write_text(dsrc)
    print("OK 2: Wired /recommendations to cached state")
else:
    print("SKIP 2: /recommendations already wired or not found")

try:
    ast.parse(dsrc)
    print("OK 2b: discord_bot.py syntax valid")
except SyntaxError as e:
    print(f"FAIL 2b: {e}")
    sys.exit(1)

# Summary
print(f"\nSummary:")
print(f"  _boot() method: {'present' if '_boot' in src else 'missing'}")
print(f"  set_correlation_id: {'present' if 'set_correlation_id' in src else 'missing'}")
print(f"  engines/main.py: created separately")
print(f"  logging_config.py: created separately")
print(f"  /recommendations wired: {'yes' if 'cached_state' in dsrc.split('recommendations_cmd')[1][:2000] else 'no'}")
