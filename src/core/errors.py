"""
TradingAI Bot - Structured Error Types

Typed exception hierarchy so callers can catch specific failure modes
instead of bare `except Exception`.

Hierarchy:
    TradingError (base)
    +-- BrokerError          execution / connectivity
    +-- DataError            missing or stale market data
    +-- ValidationError      signal or input validation
    +-- RiskLimitError       circuit breaker / exposure limit
    +-- SignalError          signal generation failures
    +-- ConfigError          invalid configuration
"""


class TradingError(Exception):
    """Base exception for all TradingAI errors."""

    def __init__(self, message: str = "", code: str = "", detail: str = ""):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(message)

    def to_dict(self):
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "detail": self.detail,
        }


class BrokerError(TradingError):
    """Raised when broker connection or order execution fails."""

    def __init__(self, message: str = "", broker: str = "", code: str = "BROKER_ERR"):
        self.broker = broker
        super().__init__(message=message, code=code, detail=f"broker={broker}")


class DataError(TradingError):
    """Raised when market data is missing, stale, or corrupted."""

    def __init__(self, message: str = "", ticker: str = "", code: str = "DATA_ERR"):
        self.ticker = ticker
        super().__init__(message=message, code=code, detail=f"ticker={ticker}")


class ValidationError(TradingError):
    """Raised when a signal or input fails validation."""

    def __init__(self, message: str = "", field: str = "", code: str = "VALIDATION_ERR"):
        self.field = field
        super().__init__(message=message, code=code, detail=f"field={field}")


class RiskLimitError(TradingError):
    """Raised when a risk limit (circuit breaker, exposure, drawdown) is hit."""

    def __init__(self, message: str = "", limit_type: str = "", code: str = "RISK_LIMIT"):
        self.limit_type = limit_type
        super().__init__(message=message, code=code, detail=f"limit={limit_type}")


class SignalError(TradingError):
    """Raised when signal generation or processing fails."""

    def __init__(self, message: str = "", strategy: str = "", code: str = "SIGNAL_ERR"):
        self.strategy = strategy
        super().__init__(message=message, code=code, detail=f"strategy={strategy}")


class ConfigError(TradingError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str = "", param: str = "", code: str = "CONFIG_ERR"):
        self.param = param
        super().__init__(message=message, code=code, detail=f"param={param}")
