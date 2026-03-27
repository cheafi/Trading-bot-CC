"""
TradingAI Bot - Core Configuration
Loads settings from environment variables with validation.

Features:
- Type-safe configuration with Pydantic
- Environment variable loading with defaults
- Computed properties for derived values
- Validation for critical settings
"""
from functools import lru_cache
from typing import Optional, List, Literal
from pydantic_settings import BaseSettings
from pydantic import Field, computed_field, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service identification
    service_name: str = Field(default="tradingai", alias="SERVICE_NAME")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Database - individual components
    postgres_user: str = Field(default="tradingai", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="tradingai", alias="POSTGRES_DB")
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    
    # Redis
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    
    # Market Data APIs
    polygon_api_key: Optional[str] = Field(default=None, alias="POLYGON_API_KEY")
    alpaca_api_key: Optional[str] = Field(default=None, alias="ALPACA_API_KEY")
    alpaca_secret_key: Optional[str] = Field(default=None, alias="ALPACA_SECRET_KEY")
    alpaca_endpoint: str = Field(
        default="https://paper-api.alpaca.markets/v2", 
        alias="ALPACA_ENDPOINT"
    )
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")
    
    # News APIs
    newsapi_key: Optional[str] = Field(default=None, alias="NEWSAPI_KEY")
    benzinga_api_key: Optional[str] = Field(default=None, alias="BENZINGA_API_KEY")
    finnhub_api_key: Optional[str] = Field(default=None, alias="FINNHUB_API_KEY")
    
    # Social APIs
    x_bearer_token: Optional[str] = Field(default=None, alias="X_BEARER_TOKEN")
    reddit_client_id: Optional[str] = Field(default=None, alias="REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = Field(default=None, alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="TradingAI Bot/1.0", alias="REDDIT_USER_AGENT")
    
    # OpenAI (standard) - optional fallback
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.2", alias="OPENAI_MODEL")
    openai_model_mini: str = Field(default="gpt-5.2-mini", alias="OPENAI_MODEL_MINI")
    
    # Azure OpenAI (preferred)
    azure_tenant_id: Optional[str] = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: Optional[str] = Field(default=None, alias="AZURE_CLIENT_SECRET")
    azure_openai_endpoint: Optional[str] = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: Optional[str] = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str = Field(default="gpt-5.2", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2026-01-15-preview", alias="AZURE_OPENAI_API_VERSION")
    
    # Telegram Notifications
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")

    # Discord Notifications (optional)
    discord_webhook_url: Optional[str] = Field(default=None, alias="DISCORD_WEBHOOK_URL")
    discord_bot_token: Optional[str] = Field(default=None, alias="DISCORD_BOT_TOKEN")
    discord_channel_name: str = Field(default="Trading CC", alias="DISCORD_CHANNEL_NAME")
    
    # MetaTrader 5 (Forex/CFD/Crypto)
    mt5_login: Optional[int] = Field(default=None, alias="MT5_LOGIN")
    mt5_password: Optional[str] = Field(default=None, alias="MT5_PASSWORD")
    mt5_server: Optional[str] = Field(default=None, alias="MT5_SERVER")
    mt5_path: Optional[str] = Field(default=None, alias="MT5_PATH")
    
    # Futu Broker (富途)
    futu_host: str = Field(default="127.0.0.1", alias="FUTU_HOST")
    futu_port: int = Field(default=11111, alias="FUTU_PORT")
    futu_trade_password: Optional[str] = Field(default=None, alias="FUTU_TRADE_PASSWORD")
    futu_unlock_pin: Optional[str] = Field(default=None, alias="FUTU_UNLOCK_PIN")
    futu_rsa_file: Optional[str] = Field(default=None, alias="FUTU_RSA_FILE")
    
    # Interactive Brokers
    ib_host: str = Field(default="127.0.0.1", alias="IB_HOST")
    ib_port: int = Field(default=7497, alias="IB_PORT")  # 7497 for TWS, 4001 for Gateway
    ib_client_id: int = Field(default=1, alias="IB_CLIENT_ID")
    ib_account: Optional[str] = Field(default=None, alias="IB_ACCOUNT")
    
    # Twilio / WhatsApp (optional)
    twilio_account_sid: Optional[str] = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: Optional[str] = Field(default=None, alias="TWILIO_WHATSAPP_FROM")
    whatsapp_to: Optional[str] = Field(default=None, alias="WHATSAPP_TO")
    
    # S3 Storage (Massive / S3-compatible)
    s3_access_key_id: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: Optional[str] = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    s3_endpoint: Optional[str] = Field(default=None, alias="S3_ENDPOINT")
    s3_bucket: Optional[str] = Field(default=None, alias="S3_BUCKET")
    
    # API Security
    api_secret_key: Optional[str] = Field(default=None, alias="API_SECRET_KEY")
    
    # Monitoring
    grafana_user: str = Field(default="admin", alias="GRAFANA_USER")
    grafana_password: str = Field(default="admin", alias="GRAFANA_PASSWORD")
    
    @computed_field
    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @computed_field
    @property
    def async_database_url(self) -> str:
        """Construct async database URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @computed_field
    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
    
    @property
    def use_azure_openai(self) -> bool:
        """Check if Azure OpenAI should be used."""
        return bool(self.azure_openai_endpoint and self.azure_client_id)
    
    @property
    def has_telegram(self) -> bool:
        """Check if Telegram is configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_discord(self) -> bool:
        """Check if Discord webhook is configured."""
        return bool(self.discord_webhook_url)

    @property
    def has_whatsapp(self) -> bool:
        """Check if Twilio WhatsApp is configured."""
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_whatsapp_from
            and self.whatsapp_to
        )
    
    @property
    def has_s3(self) -> bool:
        """Check if S3 storage is configured."""
        return bool(self.s3_endpoint and self.s3_access_key_id)
    
    @property
    def has_mt5(self) -> bool:
        """Check if MetaTrader 5 is configured."""
        return bool(self.mt5_login and self.mt5_password)
    
    @property
    def has_discord_bot(self) -> bool:
        """Check if Discord bot (interactive) is configured."""
        return bool(self.discord_bot_token)
    
    @property
    def has_futu(self) -> bool:
        """Check if Futu is configured."""
        return bool(self.futu_trade_password)
    
    @property
    def has_ib(self) -> bool:
        """Check if Interactive Brokers is configured."""
        return bool(self.ib_host and self.ib_port)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


class TradingConfig(BaseSettings):
    """Trading-specific configuration."""
    
    # Universe
    universe_source: str = Field(default="sp500", alias="UNIVERSE_SOURCE")
    custom_watchlist: List[str] = Field(default_factory=list, alias="CUSTOM_WATCHLIST")
    
    # Risk parameters
    max_position_pct: float = Field(default=0.05, alias="MAX_POSITION_PCT")
    max_sector_pct: float = Field(default=0.25, alias="MAX_SECTOR_PCT")
    max_correlation: float = Field(default=0.70, alias="MAX_CORRELATION")
    max_portfolio_var: float = Field(default=0.025, alias="MAX_PORTFOLIO_VAR")
    max_drawdown_pct: float = Field(default=0.10, alias="MAX_DRAWDOWN_PCT")
    risk_per_trade: float = Field(default=0.01, alias="RISK_PER_TRADE")
    
    # Signal filters
    min_confidence: int = Field(default=50, alias="MIN_CONFIDENCE")
    max_vix_for_trading: float = Field(default=40.0, alias="MAX_VIX_FOR_TRADING")

    # Regime router thresholds
    regime_vix_crisis: float = Field(default=35.0, alias="REGIME_VIX_CRISIS")
    regime_no_trade_entropy: float = Field(default=1.35, alias="REGIME_NO_TRADE_ENTROPY")
    regime_min_confidence: float = Field(default=0.40, alias="REGIME_MIN_CONFIDENCE")

    # Ensembler thresholds
    ensemble_min_score: float = Field(default=0.35, alias="ENSEMBLE_MIN_SCORE")

    # Expression engine
    options_enabled: bool = Field(default=False, alias="OPTIONS_ENABLED")
    max_option_allocation: float = Field(default=0.20, alias="MAX_OPTION_ALLOCATION")
    min_option_oi: int = Field(default=500, alias="MIN_OPTION_OI")

    # Strategy leaderboard
    strategy_cooldown_score: float = Field(default=0.20, alias="STRATEGY_COOLDOWN_SCORE")
    strategy_reduced_score: float = Field(default=0.35, alias="STRATEGY_REDUCED_SCORE")
    strategy_retire_days: int = Field(default=90, alias="STRATEGY_RETIRE_DAYS")

    # Circuit breaker
    max_daily_loss_pct: float = Field(default=3.0, alias="MAX_DAILY_LOSS_PCT")
    max_consecutive_losses: int = Field(default=5, alias="MAX_CONSECUTIVE_LOSSES")
    circuit_breaker_cooldown_min: int = Field(default=60, alias="CIRCUIT_BREAKER_COOLDOWN_MIN")
    max_open_positions: int = Field(default=15, alias="MAX_OPEN_POSITIONS")

    # Position management
    stop_loss_pct: float = Field(default=0.03, alias="STOP_LOSS_PCT")
    trailing_stop_pct: float = Field(default=0.02, alias="TRAILING_STOP_PCT")
    max_hold_days: int = Field(default=30, alias="MAX_HOLD_DAYS")
    
    # Scheduling (Eastern Time)
    premarket_report_time: str = Field(default="06:30", alias="PREMARKET_REPORT_TIME")
    postmarket_report_time: str = Field(default="16:30", alias="POSTMARKET_REPORT_TIME")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache()
def get_trading_config() -> TradingConfig:
    """Get cached trading config instance."""
    return TradingConfig()


# Global settings instance for convenience
settings = get_settings()
