"""
Market Scanners - AI-powered stock scanning and pattern recognition.
"""
_LAZY = {
    "PatternScanner": ".pattern_scanner",
    "ChartPattern": ".pattern_scanner",
    "SectorScanner": ".sector_scanner",
    "MomentumScanner": ".momentum_scanner",
    "VolumeScanner": ".volume_scanner",
    "MarketMonitor": ".market_monitor",
}

__all__ = list(_LAZY)


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name], __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
