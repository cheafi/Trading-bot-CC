"""
TradingAI Bot - Broker Connectors

Supports:
- Futu (富途) - Hong Kong and US markets
- Interactive Brokers (IB) - Global markets
- Paper Trading - Simulation mode
"""

from src.brokers.base import BaseBroker, OrderResult, Position, AccountInfo
from src.brokers.futu_broker import FutuBroker
from src.brokers.ib_broker import IBBroker
from src.brokers.paper_broker import PaperBroker

__all__ = [
    "BaseBroker",
    "OrderResult",
    "Position",
    "AccountInfo",
    "FutuBroker",
    "IBBroker", 
    "PaperBroker",
]
