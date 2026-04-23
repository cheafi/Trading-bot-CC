"""
TradingAI Bot - Backtest Package
Backtesting and strategy validation tools.
"""
__all__ = ["Backtester", "Trade"]


def __getattr__(name):
    if name in ("Backtester", "Trade"):
        from src.backtest.backtester import Backtester, Trade

        return Backtester if name == "Backtester" else Trade
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
