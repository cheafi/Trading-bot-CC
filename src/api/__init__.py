"""
TradingAI Bot - API Package
FastAPI-based REST API for the trading bot.
"""

__all__ = ['app']


def __getattr__(name):
    if name == "app":
        from src.api.main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
