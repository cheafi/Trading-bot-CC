"""
Sprint 24 – Hardened Risk & Position State Tests

Validates:
 1. Equity cache replaces $100k fallback
 2. Equity staleness guard blocks new trades
 3. Circuit breaker reads config (no class constants)
 4. Learning loop DB persistence uses real direction/confidence
 5. PositionManager save_state/load_state round-trip
 6. Position state survives simulated restart
 7. RiskCircuitBreaker param wiring
 8. Config has new circuit breaker fields
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

# ── Module stubs ─────────────────────────────────────────────────
_db_stub = types.ModuleType("src.core.database")
_db_stub.check_database_health = MagicMock(return_value=True)
sys.modules.setdefault("src.core.database", _db_stub)
for mod_name in (
    "sqlalchemy", "sqlalchemy.orm", "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "pydantic_settings", "discord", "discord.ext",
    "discord.ext.commands", "discord.ext.tasks",
    "tenacity",
):
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))

import pydantic
ps = sys.modules["pydantic_settings"]
ps.BaseSettings = pydantic.BaseModel

_tenacity = sys.modules["tenacity"]
_tenacity.retry = lambda *a, **kw: (lambda fn: fn)
_tenacity.stop_after_attempt = lambda *a, **kw: None
_tenacity.wait_exponential = lambda *a, **kw: None
_tenacity.retry_if_exception_type = lambda *a, **kw: None


# ── Load production modules ──────────────────────────────────────

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    with open(path) as f:
        return f.read()


_base = "src/core"
_models = _load("src.core.models", f"{_base}/models.py")
_config = _load("src.core.config", f"{_base}/config.py")
_errors = _load("src.core.errors", f"{_base}/errors.py")
_log = _load("src.core.logging_config", f"{_base}/logging_config.py")
_trade_repo = _load("src.core.trade_repo", f"{_base}/trade_repo.py")

# Scanners / algo
_mms = _load(
    "src.scanners.multi_market_scanner",
    "src/scanners/multi_market_scanner.py",
)
_ub = _load(
    "src.scanners.universe_builder",
    "src/scanners/universe_builder.py",
)
_pm = _load(
    "src.algo.position_manager",
    "src/algo/position_manager.py",
)

# Load ONLY the RiskCircuitBreaker class from the engine
# without importing the full module (which would pull in
# regime_router, ensembler, etc. and pollute sys.modules
# for later test files).
import ast as _ast

_ate_src = _read("src/engines/auto_trading_engine.py")

# Extract RiskCircuitBreaker class via exec in isolated namespace
_ns = {
    "datetime": datetime,
    "date": __import__("datetime").date,
    "timezone": timezone,
    "Optional": __import__("typing").Optional,
    "logging": __import__("logging"),
    "logger": __import__("logging").getLogger("test_cb"),
}
_tree = _ast.parse(_ate_src)
for _node in _ast.iter_child_nodes(_tree):
    if (isinstance(_node, _ast.ClassDef)
            and _node.name == "RiskCircuitBreaker"):
        _cb_code = _ast.get_source_segment(_ate_src, _node)
        exec(_cb_code, _ns)  # noqa: S102
        break

PositionManager = _pm.PositionManager
RiskParameters = _pm.RiskParameters
Position = _pm.Position
PositionStatus = _pm.PositionStatus
RiskCircuitBreaker = _ns["RiskCircuitBreaker"]
TradingConfig = _config.TradingConfig


# ═════════════════════════════════════════════════════════════════
# 1. EQUITY CACHE
# ═════════════════════════════════════════════════════════════════

class TestEquityCache(unittest.TestCase):

    def test_01_no_100k_fallback_in_get_equity(self):
        """_get_equity no longer returns hardcoded 100000.0."""
        src = _read("src/engines/auto_trading_engine.py")
        # Find the _get_equity method
        idx = src.index("async def _get_equity")
        method_end = src.index("\n    async def ", idx + 10)
        method = src[idx:method_end]
        self.assertNotIn(
            "100000.0", method,
            "_get_equity still has $100k fallback",
        )

    def test_02_cached_equity_attrs_exist(self):
        """Engine __init__ has equity cache attributes."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn("_last_known_equity", src)
        self.assertIn("_equity_fetched_at", src)
        self.assertIn("_equity_stale_minutes", src)

    def test_03_is_equity_stale_method_exists(self):
        """_is_equity_stale() method exists."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn("def _is_equity_stale", src)

    def test_04_stale_guard_blocks_execution(self):
        """Stale equity guard blocks trade execution."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("_is_equity_stale()")
        # Should be near execution loop
        context = src[max(0, idx - 200):idx + 200]
        self.assertIn(
            "skipping", context.lower(),
        )

    def test_05_position_sizing_no_100k(self):
        """Position sizing fallback doesn't use 100k."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _calculate_position_size")
        method = src[idx:idx + 3000]
        self.assertNotIn(
            "equity = 100000.0", method,
            "Position sizing still uses $100k phantom",
        )

    def test_06_fallback_uses_cached_equity(self):
        """Position sizing fallback references _last_known_equity."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _calculate_position_size")
        method = src[idx:idx + 3000]
        self.assertIn("_last_known_equity", method)


# ═════════════════════════════════════════════════════════════════
# 2. CIRCUIT BREAKER CONFIG
# ═════════════════════════════════════════════════════════════════

class TestCircuitBreakerConfig(unittest.TestCase):

    def test_07_cb_accepts_params(self):
        """RiskCircuitBreaker __init__ accepts config params."""
        cb = RiskCircuitBreaker(
            max_daily_loss_pct=5.0,
            max_drawdown_pct=20.0,
            max_consecutive_losses=3,
            cooldown_minutes=30,
            max_open_positions=10,
        )
        self.assertEqual(cb.max_daily_loss_pct, 5.0)
        self.assertEqual(cb.max_drawdown_pct, 20.0)
        self.assertEqual(cb.max_consecutive_losses, 3)
        self.assertEqual(cb.cooldown_minutes, 30)
        self.assertEqual(cb.max_open_positions, 10)

    def test_08_cb_defaults_unchanged(self):
        """Default CB params match original values."""
        cb = RiskCircuitBreaker()
        self.assertEqual(cb.max_daily_loss_pct, 3.0)
        self.assertEqual(cb.max_drawdown_pct, 10.0)
        self.assertEqual(cb.max_consecutive_losses, 5)
        self.assertEqual(cb.cooldown_minutes, 60)
        self.assertEqual(cb.max_open_positions, 15)

    def test_09_no_class_constants(self):
        """No class-level MAX_* constants."""
        self.assertFalse(
            hasattr(RiskCircuitBreaker, "MAX_DAILY_LOSS_PCT"),
            "Class constant MAX_DAILY_LOSS_PCT still exists",
        )

    def test_10_daily_loss_triggers_at_custom(self):
        """Daily loss triggers at custom threshold."""
        cb = RiskCircuitBreaker(max_daily_loss_pct=1.0)
        cb.peak_equity = 10000
        # Under threshold
        result = cb.update(equity=10000, trade_pnl=-0.5)
        self.assertTrue(result)
        # Over threshold
        result = cb.update(equity=10000, trade_pnl=-0.6)
        self.assertFalse(result)

    def test_11_consecutive_losses_custom(self):
        """Consecutive losses trigger at custom count."""
        cb = RiskCircuitBreaker(max_consecutive_losses=2)
        cb.peak_equity = 10000
        cb.update(equity=10000, trade_pnl=-0.1)
        result = cb.update(equity=10000, trade_pnl=-0.1)
        self.assertFalse(result)

    def test_12_max_positions_custom(self):
        """Max positions triggers at custom limit."""
        cb = RiskCircuitBreaker(max_open_positions=3)
        cb.peak_equity = 10000
        # At limit
        result = cb.update(
            equity=10000, open_positions=3,
        )
        self.assertFalse(result)
        # Under limit
        result2 = cb.update(
            equity=10000, open_positions=2,
        )
        self.assertTrue(result2)

    def test_13_config_has_cb_fields(self):
        """TradingConfig has circuit breaker fields."""
        tc = TradingConfig()
        self.assertTrue(hasattr(tc, "max_daily_loss_pct"))
        self.assertTrue(
            hasattr(tc, "max_consecutive_losses"),
        )
        self.assertTrue(
            hasattr(tc, "circuit_breaker_cooldown_min"),
        )
        self.assertTrue(hasattr(tc, "max_open_positions"))

    def test_14_engine_wires_config_to_cb(self):
        """Engine __init__ passes config to circuit breaker."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "RiskCircuitBreaker(", src,
        )
        self.assertIn(
            "max_daily_loss_pct=", src,
        )
        self.assertIn(
            "max_consecutive_losses=", src,
        )


# ═════════════════════════════════════════════════════════════════
# 3. LEARNING LOOP DATA FIDELITY
# ═════════════════════════════════════════════════════════════════

class TestLearningDataFidelity(unittest.TestCase):

    def test_15_db_persist_uses_real_direction(self):
        """DB persistence dict uses _dir, not hardcoded 'LONG'."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("# Persist to database (best-effort)")
        block = src[idx:idx + 3000]
        # Should have "direction": _dir  not  "direction": "LONG"
        self.assertIn('"direction": _dir', block)
        self.assertNotIn(
            '"direction": "LONG"', block,
            "DB persistence still hardcodes LONG",
        )

    def test_16_db_persist_uses_real_confidence(self):
        """DB persistence uses _conf not hardcoded 50."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("# Persist to database (best-effort)")
        block = src[idx:idx + 3000]
        self.assertIn('"confidence": _conf', block)
        self.assertNotIn(
            '"confidence": 50', block,
            "DB persistence still hardcodes confidence=50",
        )

    def test_17_db_persist_uses_snapshot_fields(self):
        """DB persistence reads rsi/adx/volume from snapshot."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("# Persist to database (best-effort)")
        block = src[idx:idx + 3000]
        self.assertIn('_snapshot.get("rsi_at_entry")', block)
        self.assertIn('_snapshot.get("adx_at_entry")', block)
        self.assertIn(
            '_snapshot.get("relative_volume")', block,
        )
        self.assertIn(
            '_snapshot.get("composite_score")', block,
        )

    def test_18_db_persist_uses_hold_hours(self):
        """hold_hours uses the pre-computed _hold variable."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("# Persist to database (best-effort)")
        block = src[idx:idx + 3000]
        self.assertIn('"hold_hours": _hold', block)

    def test_19_feature_snapshot_passed(self):
        """feature_snapshot includes real snapshot data."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("# Persist to database (best-effort)")
        block = src[idx:idx + 3000]
        self.assertIn(
            '"feature_snapshot": _snapshot', block,
        )


# ═════════════════════════════════════════════════════════════════
# 4. POSITION STATE PERSISTENCE
# ═════════════════════════════════════════════════════════════════

class TestPositionPersistence(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(
            self.tmpdir, "positions.json",
        )

    def tearDown(self):
        if os.path.exists(self.state_path):
            os.remove(self.state_path)
        os.rmdir(self.tmpdir)

    def _make_pm_with_position(self):
        pm = PositionManager(RiskParameters(
            account_size=50000,
            max_open_positions=10,
        ))
        pm.open_position(
            ticker="AAPL",
            strategy_id="momentum",
            entry_price=150.0,
            shares=100,
            stop_loss_price=145.0,
            sector="Technology",
        )
        return pm

    def test_20_save_state_creates_file(self):
        """save_state() writes a JSON file."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)
        self.assertTrue(os.path.exists(self.state_path))

    def test_21_save_state_json_valid(self):
        """Saved state is valid JSON."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)
        with open(self.state_path) as f:
            data = json.load(f)
        self.assertIn("positions", data)
        self.assertIn("current_equity", data)

    def test_22_round_trip_ticker(self):
        """save → load preserves ticker."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)

        pm2 = PositionManager(RiskParameters(
            account_size=50000,
        ))
        pm2.load_state(self.state_path)
        self.assertIn("AAPL", pm2.positions)

    def test_23_round_trip_entry_price(self):
        """save → load preserves entry_price."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        pos = pm2.positions["AAPL"]
        self.assertAlmostEqual(pos.entry_price, 150.0)

    def test_24_round_trip_stop_loss(self):
        """save → load preserves stop_loss_price."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        pos = pm2.positions["AAPL"]
        self.assertAlmostEqual(
            pos.stop_loss_price, 145.0,
        )

    def test_25_round_trip_shares(self):
        """save → load preserves share count."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertEqual(
            pm2.positions["AAPL"].shares, 100,
        )

    def test_26_round_trip_equity(self):
        """save → load preserves current_equity."""
        pm = self._make_pm_with_position()
        pm.current_equity = 48000.0
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertAlmostEqual(
            pm2.current_equity, 48000.0,
        )

    def test_27_round_trip_peak_equity(self):
        """save → load preserves peak_equity."""
        pm = self._make_pm_with_position()
        pm.peak_equity = 55000.0
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertAlmostEqual(pm2.peak_equity, 55000.0)

    def test_28_round_trip_strategy_id(self):
        """save → load preserves strategy_id."""
        pm = self._make_pm_with_position()
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertEqual(
            pm2.positions["AAPL"].strategy_id,
            "momentum",
        )

    def test_29_round_trip_multi_positions(self):
        """save → load preserves multiple positions."""
        pm = PositionManager(RiskParameters(
            account_size=100000,
            max_open_positions=10,
        ))
        pm.open_position(
            ticker="AAPL", strategy_id="s1",
            entry_price=150, shares=50,
            stop_loss_price=145,
        )
        pm.open_position(
            ticker="MSFT", strategy_id="s2",
            entry_price=300, shares=30,
            stop_loss_price=290,
        )
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertEqual(len(pm2.positions), 2)
        self.assertIn("AAPL", pm2.positions)
        self.assertIn("MSFT", pm2.positions)

    def test_30_load_missing_file_no_crash(self):
        """load_state with missing file doesn't crash."""
        pm = PositionManager()
        pm.load_state("/tmp/nonexistent_xyz.json")
        self.assertEqual(len(pm.positions), 0)

    def test_31_load_corrupt_json_no_crash(self):
        """load_state with corrupt JSON doesn't crash."""
        with open(self.state_path, "w") as f:
            f.write("{invalid json")
        pm = PositionManager()
        pm.load_state(self.state_path)
        self.assertEqual(len(pm.positions), 0)

    def test_32_round_trip_trailing_stop(self):
        """save → load preserves trailing_stop_price."""
        pm = self._make_pm_with_position()
        pm.positions["AAPL"].trailing_stop_price = 148.0
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertAlmostEqual(
            pm2.positions["AAPL"].trailing_stop_price,
            148.0,
        )

    def test_33_round_trip_r_targets(self):
        """save → load preserves R-target prices."""
        pm = self._make_pm_with_position()
        pos = pm.positions["AAPL"]
        self.assertGreater(pos.target_1r_price, 0)
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        pos2 = pm2.positions["AAPL"]
        self.assertAlmostEqual(
            pos2.target_1r_price, pos.target_1r_price,
        )

    def test_34_round_trip_consecutive_losses(self):
        """save → load preserves consecutive_losses."""
        pm = self._make_pm_with_position()
        pm.consecutive_losses = 3
        pm.save_state(self.state_path)

        pm2 = PositionManager()
        pm2.load_state(self.state_path)
        self.assertEqual(pm2.consecutive_losses, 3)


# ═════════════════════════════════════════════════════════════════
# 5. ENGINE INTEGRATION (source text)
# ═════════════════════════════════════════════════════════════════

class TestEngineIntegration(unittest.TestCase):

    def test_35_boot_loads_state(self):
        """_boot() calls position_mgr.load_state()."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("async def _boot")
        method = src[idx:idx + 5000]
        self.assertIn("load_state", method)

    def test_36_open_saves_state(self):
        """Position open path calls save_state()."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "# Sprint 24: persist state after open",
            src,
        )
        self.assertIn("save_state()", src)

    def test_37_close_saves_state(self):
        """Position close path calls save_state()."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "# Sprint 24: persist after close",
            src,
        )

    def test_38_equity_stale_guard_exists(self):
        """Equity stale guard in execution path."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn("_is_equity_stale()", src)

    def test_39_no_100k_in_sizing(self):
        """No $100,000 anywhere in position sizing."""
        src = _read("src/engines/auto_trading_engine.py")
        idx = src.index("def _calculate_position_size")
        # Read until next method
        end = src.find("\n    async def ", idx)
        if end == -1:
            end = idx + 3000
        method = src[idx:end]
        self.assertNotIn("100000", method)

    def test_40_config_wired_to_circuit_breaker(self):
        """Circuit breaker init passes TradingConfig values."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "max_daily_loss_pct=_tc.max_daily_loss_pct",
            src,
        )

    def test_41_cb_drawdown_from_config(self):
        """Drawdown threshold from config (fraction→%)."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "max_drawdown_pct=_tc.max_drawdown_pct * 100",
            src,
        )

    def test_42_cooldown_from_config(self):
        """Cooldown minutes from config."""
        src = _read("src/engines/auto_trading_engine.py")
        self.assertIn(
            "cooldown_minutes=_tc.circuit_breaker_cooldown_min",
            src,
        )


# ═════════════════════════════════════════════════════════════════
# 6. CIRCUIT BREAKER FUNCTIONAL
# ═════════════════════════════════════════════════════════════════

class TestCircuitBreakerFunctional(unittest.TestCase):

    def test_43_drawdown_triggers(self):
        """Drawdown beyond threshold triggers breaker."""
        cb = RiskCircuitBreaker(max_drawdown_pct=5.0)
        cb.peak_equity = 10000
        result = cb.update(equity=9400)
        self.assertFalse(result)
        self.assertTrue(cb.triggered)
        self.assertIn("Drawdown", cb.trigger_reason)

    def test_44_cooldown_blocks(self):
        """Triggered breaker blocks during cooldown."""
        cb = RiskCircuitBreaker(cooldown_minutes=10)
        cb.peak_equity = 10000
        cb.update(equity=10000, trade_pnl=-5.0)
        self.assertTrue(cb.triggered)
        # Still blocked
        result = cb.update(equity=10000)
        self.assertFalse(result)

    def test_45_cooldown_expires(self):
        """Breaker allows trading after cooldown."""
        cb = RiskCircuitBreaker(cooldown_minutes=1)
        cb.peak_equity = 10000
        cb.update(equity=10000, trade_pnl=-5.0)
        self.assertTrue(cb.triggered)
        # Simulate expired cooldown
        cb.trigger_time = (
            datetime.now(timezone.utc) - timedelta(minutes=2)
        )
        # Reset daily_pnl so it doesn't re-trigger
        cb.daily_pnl = 0.0
        cb.consecutive_losses = 0
        result = cb.update(equity=10000)
        self.assertTrue(result)
        self.assertFalse(cb.triggered)

    def test_46_winning_trade_resets_losses(self):
        """Positive trade resets consecutive losses."""
        cb = RiskCircuitBreaker(max_consecutive_losses=3)
        cb.peak_equity = 10000
        cb.update(equity=10000, trade_pnl=-0.1)
        cb.update(equity=10000, trade_pnl=-0.1)
        self.assertEqual(cb.consecutive_losses, 2)
        cb.update(equity=10000, trade_pnl=0.5)
        self.assertEqual(cb.consecutive_losses, 0)

    def test_47_daily_reset(self):
        """New day resets daily PnL."""
        cb = RiskCircuitBreaker()
        cb.peak_equity = 10000
        cb.daily_pnl = -2.0
        from datetime import date as _date
        cb.today = _date(2020, 1, 1)  # force "yesterday"
        cb.update(equity=10000)
        self.assertEqual(cb.daily_pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
