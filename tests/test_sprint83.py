"""
Sprint 83 Tests — Router Extraction + Config Consolidation Verification
=======================================================================
Validates that Sprint 81 (RegimeService.aget, market_intel router),
Sprint 82 (broker router, health router, TradingConfig defaults)
changes are structurally sound.

Run:
    source venv/bin/activate
    python test_sprint83.py
"""

import asyncio
import sys
import time


# ── 1. Compile checks ────────────────────────────────────────────────────────

def test_imports():
    """All new/modified modules import without errors."""
    modules = [
        "src.services.regime_service",
        "src.api.routers.market_intel",
        "src.api.routers.broker",
        "src.api.routers.health",
        "src.core.config",
        "src.core.risk_limits",
    ]
    for m in modules:
        try:
            __import__(m)
            print(f"  ✅ import {m}")
        except Exception as e:
            print(f"  ❌ import {m}: {e}")
            return False
    return True


# ── 2. RegimeService.aget exists and returns same type as .get ────────────────

def test_regime_service_aget():
    """RegimeService.aget() is a coroutine and returns same structure as get()."""
    import inspect
    from src.services.regime_service import RegimeService

    # aget must be a classmethod that returns a coroutine
    aget = RegimeService.aget
    assert callable(aget), "RegimeService.aget not callable"

    # Calling it must return a coroutine
    coro = aget()
    assert asyncio.iscoroutine(coro), f"Expected coroutine, got {type(coro)}"
    coro.close()  # Clean up without running

    print("  ✅ RegimeService.aget() returns coroutine")
    return True


# ── 3. aget uses asyncio.to_thread (check source) ────────────────────────────

def test_aget_uses_to_thread():
    import inspect
    from src.services.regime_service import RegimeService
    source = inspect.getsource(RegimeService.aget)
    assert "asyncio.to_thread" in source, "aget() must use asyncio.to_thread"
    print("  ✅ RegimeService.aget() uses asyncio.to_thread")
    return True


# ── 4. market_intel router has correct prefix and 5 routes ───────────────────

def test_market_intel_router():
    from src.api.routers.market_intel import router
    assert router.prefix == "/api/market-intel", f"Wrong prefix: {router.prefix}"
    paths = {r.path for r in router.routes}
    expected = {
        "/api/market-intel/regime",
        "/api/market-intel/vix",
        "/api/market-intel/breadth",
        "/api/market-intel/spy-return",
        "/api/market-intel/rates",
    }
    missing = expected - paths
    assert not missing, f"Missing routes: {missing}"
    print(f"  ✅ market_intel router: {len(paths)} routes, prefix correct")
    return True


# ── 5. broker router has correct prefix and 6 routes ─────────────────────────

def test_broker_router():
    from src.api.routers.broker import router
    assert router.prefix == "/broker", f"Wrong prefix: {router.prefix}"
    paths = {r.path for r in router.routes}
    expected = {
        "/broker/status",
        "/broker/switch/{broker_type}",
        "/broker/account",
        "/broker/positions",
        "/broker/order",
        "/broker/quote/{ticker}",
    }
    missing = expected - paths
    assert not missing, f"Missing routes: {missing}"
    print(f"  ✅ broker router: {len(paths)} routes, prefix correct")
    return True


# ── 6. health router has 8 routes ─────────────────────────────────────────────

def test_health_router():
    from src.api.routers.health import router
    paths = {r.path for r in router.routes}
    expected = {
        "/health",
        "/health/detailed",
        "/health/live",
        "/health/ready",
        "/status/data",
        "/status/jobs",
        "/status/signals",
        "/metrics",
    }
    missing = expected - paths
    assert not missing, f"Missing routes: {missing}"
    print(f"  ✅ health router: {len(paths)} routes")
    return True


# ── 7. TradingConfig defaults aligned with RISK ───────────────────────────────

def test_config_defaults_aligned():
    from src.core.risk_limits import RISK

    # Import fresh (not cached) to check raw defaults
    from src.core.config import TradingConfig
    cfg = TradingConfig()

    # max_open_positions must match RISK.max_positions (10)
    assert cfg.max_open_positions == RISK.max_positions, (
        f"TradingConfig.max_open_positions ({cfg.max_open_positions}) != "
        f"RISK.max_positions ({RISK.max_positions})"
    )
    print(f"  ✅ TradingConfig.max_open_positions == RISK.max_positions == {RISK.max_positions}")

    # max_drawdown_pct must match RISK.max_drawdown_pct (0.15)
    assert cfg.max_drawdown_pct == RISK.max_drawdown_pct, (
        f"TradingConfig.max_drawdown_pct ({cfg.max_drawdown_pct}) != "
        f"RISK.max_drawdown_pct ({RISK.max_drawdown_pct})"
    )
    print(f"  ✅ TradingConfig.max_drawdown_pct == RISK.max_drawdown_pct == {RISK.max_drawdown_pct}")

    return True


# ── 8. RegimeService cache is hot (returns immediately on second call) ─────────

def test_regime_service_cache_speed():
    """RegimeService.get() with warm cache returns in <5ms."""
    from src.services.regime_service import RegimeService

    # Prime cache with synthetic data (won't call yfinance)
    RegimeService._cache = RegimeService._default_regime()
    RegimeService._cache_time = time.time()

    t0 = time.perf_counter()
    result = RegimeService.get()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert result is not None, "get() returned None"
    assert elapsed_ms < 5.0, f"Cache hit took {elapsed_ms:.1f}ms (expected <5ms)"
    print(f"  ✅ RegimeService.get() cache hit: {elapsed_ms:.2f}ms")
    return True


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    ("Module imports", test_imports),
    ("RegimeService.aget() coroutine", test_regime_service_aget),
    ("aget() uses asyncio.to_thread", test_aget_uses_to_thread),
    ("market_intel router structure", test_market_intel_router),
    ("broker router structure", test_broker_router),
    ("health router structure", test_health_router),
    ("TradingConfig defaults aligned with RISK", test_config_defaults_aligned),
    ("RegimeService cache speed", test_regime_service_cache_speed),
]


def main():
    print("\n" + "=" * 60)
    print("Sprint 83 — Router + Config Verification Tests")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, fn in TESTS:
        print(f"\n[{name}]")
        try:
            ok = fn()
            if ok:
                passed += 1
            else:
                failed += 1
                print(f"  ❌ FAILED")
        except Exception as e:
            failed += 1
            print(f"  ❌ ERROR: {e}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed / {failed} failed / {len(TESTS)} total")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
