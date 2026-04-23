"""
TradingAI Bot - Broker Connectors

Supports:
- Futu (富途) - Hong Kong and US markets
- Interactive Brokers (IB) - Global markets
- MetaTrader 5 (MT5) - Forex, CFD, Crypto
- Paper Trading - Simulation mode
"""

_LAZY = {
    "BaseBroker": "src.brokers.base",
    "OrderResult": "src.brokers.base",
    "Position": "src.brokers.base",
    "AccountInfo": "src.brokers.base",
    "FutuBroker": "src.brokers.futu_broker",
    "IBBroker": "src.brokers.ib_broker",
    "PaperBroker": "src.brokers.paper_broker",
    "MetaTraderBroker": "src.brokers.mt5_broker",
    "BrokerManager": "src.brokers.broker_manager",
    "BrokerType": "src.brokers.broker_manager",
}

__all__ = list(_LAZY)


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
