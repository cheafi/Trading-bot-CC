"""
TradingAI Bot - Engines Package

Contains the core processing engines:
- FeatureEngine: Technical indicator computation
- SignalEngine: Signal generation and scoring
- GPTSignalValidator: LLM-based signal validation
- AIAdvisor: Chain-of-thought decision making
- AutoTradingEngine: 24/7 autonomous trading
"""
_LAZY = {
    "FeatureEngine": "src.engines.feature_engine",
    "SignalEngine": "src.engines.signal_engine",
    "RegimeDetector": "src.engines.signal_engine",
    "RiskModel": "src.engines.signal_engine",
    "GPTSignalValidator": "src.engines.gpt_validator",
    "AIAdvisor": "src.engines.ai_advisor",
    "AutoTradingEngine": "src.engines.auto_trading_engine",
    # Phase 9 engines
    "StructureDetector": "src.engines.structure_detector",
    "EntryQualityEngine": "src.engines.entry_quality",
    "BreakoutMonitor": "src.engines.breakout_monitor",
    "PortfolioGate": "src.engines.portfolio_gate",
    "DecisionJournal": "src.engines.decision_persistence",
    "ExpertRecordStore": "src.engines.decision_persistence",
}

__all__ = list(_LAZY)


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
