"""
TradingAI Bot - AI-Powered Multi-Market Trading System

Covers US, HK, JP equities and Crypto markets.
Supports Futu, Interactive Brokers, MetaTrader 5, and Paper Trading.

Modules:
    core     - Configuration, models, database
    algo     - Strategy library (VCP, momentum, swing, earnings)
    engines  - Feature extraction, signal generation, GPT validation, AI advisor
    ingestors - Market data, news, social, real-time WebSocket feeds
    brokers  - Unified broker interface (Futu, IB, MT5, Paper)
    ml       - Alpha factors, RL agents, trade outcome learning
    scanners - Pattern, sector, momentum, volume scanners
    notifications - Telegram, Discord, WhatsApp, Slack
    performance  - P&L analytics, backtest analysis
    research     - News/earnings/macro intelligence
    backtest     - Backtesting frameworks
    scheduler    - Job scheduling
    api          - FastAPI REST dashboard
"""

__version__ = "2.0.0"
__author__ = "TradingAI Team"

__all__ = [
    "__version__",
    "__author__",
]
