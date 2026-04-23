"""
Performance Tracking - Monitor and analyze signal performance.

Tracks:
- Signal hit rates
- Risk/reward outcomes
- Strategy performance
- P&L analytics
"""
_LAZY = {
    "PerformanceTracker": ".performance_tracker",
    "SignalOutcome": ".performance_tracker",
    "PerformanceAnalytics": ".analytics",
    "StrategyMetrics": ".analytics",
    "BacktestAnalyzer": ".backtest_analyzer",
    "BacktestResult": ".backtest_analyzer",
}

__all__ = list(_LAZY)


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name], __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
