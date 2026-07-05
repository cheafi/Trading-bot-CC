"""
TradingAI Bot - Core Configuration
Loads settings from environment variables with validation.

Zero-dependency version — no pydantic import overhead.
"""

import logging
import os
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)


_dotenv_loaded = False


def _env_load_dotenv():
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    env_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        ".env",
    )
    if os.path.isfile(env_file):
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


def _env(key: str, default=None):
    """Read an environment variable (also checks .env on first call)."""
    _env_load_dotenv()
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    v = _env(key)
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    v = _env(key)
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    v = _env(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _env_list(key: str) -> List[str]:
    v = _env(key, "")
    if not v:
        return []
    return [x.strip() for x in v.split(",") if x.strip()]


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        _env_load_dotenv()

        # Service identification
        self.service_name = _env("SERVICE_NAME", "tradingai")
        self.environment = _env("ENVIRONMENT", "development")
        self.log_level = _env("LOG_LEVEL", "INFO")

        # Database
        self.postgres_user = _env("POSTGRES_USER", "tradingai")
        self.postgres_password = _env("POSTGRES_PASSWORD", "")
        self.postgres_db = _env("POSTGRES_DB", "tradingai")
        self.postgres_host = _env("POSTGRES_HOST", "postgres")
        self.postgres_port = _env_int("POSTGRES_PORT", 5432)

        # Redis
        self.redis_password = _env("REDIS_PASSWORD", "")
        self.redis_host = _env("REDIS_HOST", "redis")
        self.redis_port = _env_int("REDIS_PORT", 6379)

        # Market Data APIs
        self.polygon_api_key = _env("POLYGON_API_KEY")
        self.alpaca_api_key = _env("ALPACA_API_KEY")
        self.alpaca_secret_key = _env("ALPACA_SECRET_KEY")
        self.alpaca_endpoint = _env(
            "ALPACA_ENDPOINT",
            "https://paper-api.alpaca.markets/v2",
        )
        self.alpaca_paper = _env_bool("ALPACA_PAPER", True)

        # News APIs
        self.newsapi_key = _env("NEWSAPI_KEY")
        self.benzinga_api_key = _env("BENZINGA_API_KEY")
        self.finnhub_api_key = _env("FINNHUB_API_KEY")

        # Social APIs
        self.x_bearer_token = _env("X_BEARER_TOKEN")
        self.reddit_client_id = _env("REDDIT_CLIENT_ID")
        self.reddit_client_secret = _env("REDDIT_CLIENT_SECRET")
        self.reddit_user_agent = _env(
            "REDDIT_USER_AGENT", "TradingAI Bot/1.0"
        )

        # OpenAI
        self.openai_api_key = _env("OPENAI_API_KEY")
        self.openai_model = _env("OPENAI_MODEL", "gpt-5.2")
        self.openai_model_mini = _env("OPENAI_MODEL_MINI", "gpt-5.2-mini")

        # Azure OpenAI
        self.azure_tenant_id = _env("AZURE_TENANT_ID")
        self.azure_client_id = _env("AZURE_CLIENT_ID")
        self.azure_client_secret = _env("AZURE_CLIENT_SECRET")
        self.azure_openai_endpoint = _env("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_api_key = _env("AZURE_OPENAI_API_KEY")
        self.azure_openai_deployment = _env(
            "AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"
        )
        self.azure_openai_api_version = _env(
            "AZURE_OPENAI_API_VERSION", "2026-01-15-preview"
        )

        # Discord
        self.discord_webhook_url = _env("DISCORD_WEBHOOK_URL")
        self.discord_bot_token = _env("DISCORD_BOT_TOKEN")
        self.discord_channel_name = _env(
            "DISCORD_CHANNEL_NAME", "Trading CC"
        )

        # MetaTrader 5
        self.mt5_login: Optional[int] = (
            _env_int("MT5_LOGIN", 0) or None
        )
        self.mt5_password = _env("MT5_PASSWORD")
        self.mt5_server = _env("MT5_SERVER")
        self.mt5_path = _env("MT5_PATH")

        # Futu Broker
        self.futu_host = _env("FUTU_HOST", "127.0.0.1")
        self.futu_port = _env_int("FUTU_PORT", 11111)
        self.futu_trade_password = _env("FUTU_TRADE_PASSWORD")
        self.futu_unlock_pin = _env("FUTU_UNLOCK_PIN")
        self.futu_rsa_file = _env("FUTU_RSA_FILE")

        # Interactive Brokers
        self.ib_host = _env("IB_HOST", "127.0.0.1")
        self.ib_port = _env_int("IB_PORT", 7497)
        self.ib_client_id = _env_int("IB_CLIENT_ID", 1)
        self.ib_account = _env("IB_ACCOUNT")

        # Twilio / WhatsApp
        self.twilio_account_sid = _env("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = _env("TWILIO_AUTH_TOKEN")
        self.twilio_whatsapp_from = _env("TWILIO_WHATSAPP_FROM")
        self.whatsapp_to = _env("WHATSAPP_TO")

        # S3 Storage
        self.s3_access_key_id = _env("S3_ACCESS_KEY_ID")
        self.s3_secret_access_key = _env("S3_SECRET_ACCESS_KEY")
        self.s3_endpoint = _env("S3_ENDPOINT")
        self.s3_bucket = _env("S3_BUCKET")

        # API Security
        self.api_secret_key = _env("API_SECRET_KEY")

        # Monitoring
        self.grafana_user = _env("GRAFANA_USER", "admin")
        self.grafana_password = _env("GRAFANA_PASSWORD", "admin")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:"
            f"{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return (
            f"redis://:{self.redis_password}"
            f"@{self.redis_host}:{self.redis_port}/0"
        )

    @property
    def use_azure_openai(self) -> bool:
        return bool(
            self.azure_openai_endpoint and self.azure_client_id
        )

    @property
    def has_discord(self) -> bool:
        return bool(self.discord_webhook_url)

    @property
    def has_whatsapp(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_whatsapp_from
            and self.whatsapp_to
        )

    @property
    def has_s3(self) -> bool:
        return bool(self.s3_endpoint and self.s3_access_key_id)

    @property
    def has_mt5(self) -> bool:
        return bool(self.mt5_login and self.mt5_password)

    @property
    def has_discord_bot(self) -> bool:
        return bool(self.discord_bot_token)

    @property
    def has_futu(self) -> bool:
        return bool(self.futu_trade_password)

    @property
    def has_ib(self) -> bool:
        return bool(self.ib_host and self.ib_port)


class TradingConfig:
    """Trading-specific configuration."""

    def __init__(self):
        _env_load_dotenv()

        self.universe_source = _env("UNIVERSE_SOURCE", "sp500")
        self.custom_watchlist = _env_list("CUSTOM_WATCHLIST")

        # Risk parameters
        self.max_position_pct = _env_float("MAX_POSITION_PCT", 0.05)
        self.max_sector_pct = _env_float("MAX_SECTOR_PCT", 0.25)
        self.max_correlation = _env_float("MAX_CORRELATION", 0.70)
        self.max_portfolio_var = _env_float("MAX_PORTFOLIO_VAR", 0.025)
        # Sprint 82 CONFIG: aligned with RISK.max_drawdown_pct (was 0.10)
        self.max_drawdown_pct = _env_float("MAX_DRAWDOWN_PCT", 0.15)
        self.risk_per_trade = _env_float("RISK_PER_TRADE", 0.01)

        # Signal filters
        self.min_confidence = _env_int("MIN_CONFIDENCE", 50)
        self.max_vix_for_trading = _env_float(
            "MAX_VIX_FOR_TRADING", 40.0
        )

        # Regime router thresholds
        self.regime_vix_crisis = _env_float("REGIME_VIX_CRISIS", 35.0)
        self.regime_no_trade_entropy = _env_float(
            "REGIME_NO_TRADE_ENTROPY", 1.35
        )
        self.regime_min_confidence = _env_float(
            "REGIME_MIN_CONFIDENCE", 0.40
        )

        # Ensembler thresholds
        self.ensemble_min_score = _env_float(
            "ENSEMBLE_MIN_SCORE", 0.35
        )

        # Expression engine
        self.options_enabled = _env_bool("OPTIONS_ENABLED", False)
        self.max_option_allocation = _env_float(
            "MAX_OPTION_ALLOCATION", 0.20
        )
        self.min_option_oi = _env_int("MIN_OPTION_OI", 500)

        # Strategy leaderboard
        self.strategy_cooldown_score = _env_float(
            "STRATEGY_COOLDOWN_SCORE", 0.20
        )
        self.strategy_reduced_score = _env_float(
            "STRATEGY_REDUCED_SCORE", 0.35
        )
        self.strategy_retire_days = _env_int(
            "STRATEGY_RETIRE_DAYS", 90
        )

        # Circuit breaker
        self.max_daily_loss_pct = _env_float(
            "MAX_DAILY_LOSS_PCT", 3.0
        )
        self.max_consecutive_losses = _env_int(
            "MAX_CONSECUTIVE_LOSSES", 5
        )
        self.circuit_breaker_cooldown_min = _env_int(
            "CIRCUIT_BREAKER_COOLDOWN_MIN", 60
        )
        # Sprint 82 CONFIG: aligned with RISK.max_positions (was 15)
        self.max_open_positions = _env_int("MAX_OPEN_POSITIONS", 10)

        # Position management
        self.stop_loss_pct = _env_float("STOP_LOSS_PCT", 0.03)
        self.trailing_stop_pct = _env_float("TRAILING_STOP_PCT", 0.02)
        self.max_hold_days = _env_int("MAX_HOLD_DAYS", 30)

        # Signal dedup / anti-flip
        self.signal_cooldown_hours = _env_int(
            "SIGNAL_COOLDOWN_HOURS", 4
        )
        self.anti_flip_hours = _env_int("ANTI_FLIP_HOURS", 6)
        self.max_correlated_held = _env_int(
            "MAX_CORRELATED_HELD", 3
        )

        # Scheduling (Eastern Time)
        self.premarket_report_time = _env(
            "PREMARKET_REPORT_TIME", "06:30"
        )
        self.postmarket_report_time = _env(
            "POSTMARKET_REPORT_TIME", "16:30"
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# ── Self-learning override file ──────────────────────────────────
import json as _json
from pathlib import Path as _Path

_OVERRIDES_PATH = _Path("models/trading_config_overrides.json")


def _load_overrides() -> dict:
    """Load self-learning overrides from JSON file."""
    if _OVERRIDES_PATH.exists():
        try:
            with open(_OVERRIDES_PATH) as f:
                return _json.load(f)
        except Exception:
            pass
    return {}


def save_trading_config_override(key: str, value) -> None:
    """Persist a single parameter override from self-learning.

    Called by SelfLearningEngine.apply_adjustments() so that
    adjustments survive restarts and take effect on next config load.
    """
    overrides = _load_overrides()
    overrides[key] = value
    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_OVERRIDES_PATH, "w") as f:
        _json.dump(overrides, f, indent=2)
    # Invalidate the cached TradingConfig so next access picks up the override
    try:
        get_trading_config.cache_clear()
    except AttributeError:
        pass  # lru_cache may not have cache_clear in some Python versions


class _TradingConfigWithOverrides:
    """Proxy that applies self-learning overrides on top of base TradingConfig."""

    def __init__(self, base, overrides: dict):
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name: str):
        if name.startswith("_"):
            return getattr(self._base, name)
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)


@lru_cache()
def get_trading_config():
    """Get trading config with self-learning overrides applied.

    Overrides are stored in models/trading_config_overrides.json
    and written by SelfLearningEngine. They take precedence over
    environment variables.
    """
    base = TradingConfig()
    overrides = _load_overrides()
    if overrides:
        return _TradingConfigWithOverrides(base, overrides)
    return base


class _LazySettings:
    """Proxy that delays Settings() until first attribute access."""

    _instance = None

    def _load(self):
        if self._instance is None:
            self._instance = get_settings()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __repr__(self):
        return repr(self._load())


settings = _LazySettings()
