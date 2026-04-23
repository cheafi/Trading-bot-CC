"""
TradingAI Bot - Scheduler Package
Job scheduling for data ingestion, signal generation, and reporting.
"""
__all__ = ["TradingScheduler"]


def __getattr__(name):
    if name == "TradingScheduler":
        from src.scheduler.main import TradingScheduler

        return TradingScheduler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
