"""
TradingAI Bot - Engines Package

Contains the core processing engines:
- FeatureEngine: Technical indicator computation
- SignalEngine: Signal generation and scoring
- GPTSignalValidator: LLM-based signal validation
- AIAdvisor: Chain-of-thought decision making
- AutoTradingEngine: 24/7 autonomous trading
"""
from src.engines.feature_engine import FeatureEngine
from src.engines.signal_engine import SignalEngine, RegimeDetector, RiskModel
from src.engines.gpt_validator import GPTSignalValidator
from src.engines.ai_advisor import AIAdvisor
from src.engines.auto_trading_engine import AutoTradingEngine

__all__ = [
    'FeatureEngine',
    'SignalEngine',
    'RegimeDetector',
    'RiskModel',
    'GPTSignalValidator',
    'AIAdvisor',
    'AutoTradingEngine',
]
