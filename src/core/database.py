"""
TradingAI Bot - Database Connection

Features:
- Async PostgreSQL connection with asyncpg
- Connection pooling with health checks
- Automatic retry on connection failures
- Session management with context managers
- TimescaleDB support for time-series data
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy import text, event
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Use the async database URL from settings (already in postgresql+asyncpg:// format)
database_url = settings.async_database_url

# Create async engine with optimized settings for production
engine = create_async_engine(
    database_url,
    echo=settings.log_level == "DEBUG",
    pool_size=10,           # Increased for better concurrency
    max_overflow=20,        # Allow more connections under load
    pool_pre_ping=True,     # Verify connections before use
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_timeout=30,        # Wait up to 30s for connection
    connect_args={
        "command_timeout": 60,  # Query timeout
        "prepared_statement_cache_size": 500,  # Cache prepared statements
    }
)

# Session factory with optimized settings
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,        # Manual flush for better control
)

# For use when we need a fresh connection (e.g., after fork)
AsyncSessionLocal = async_session_maker

# Base for ORM models
Base = declarative_base()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session with automatic transaction management.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get read-only database session (no commit).
    
    Use for SELECT queries to avoid unnecessary transaction overhead.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, OSError)),
    reraise=True
)
async def check_database_health() -> bool:
    """
    Check if database is healthy with retry logic.
    
    Returns:
        True if database is accessible and healthy
    """
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


async def check_timescale_extension() -> bool:
    """Check if TimescaleDB extension is available."""
    try:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
            )
            return result.fetchone() is not None
    except Exception:
        return False


async def init_database() -> bool:
    """
    Initialize database connection and verify setup.
    
    Returns:
        True if initialization successful
    
    Raises:
        ConnectionError if database is not accessible
    """
    # Test connection
    healthy = await check_database_health()
    if not healthy:
        raise ConnectionError("Cannot connect to database")
    
    # Check for TimescaleDB
    has_timescale = await check_timescale_extension()
    if has_timescale:
        logger.info("TimescaleDB extension detected")
    else:
        logger.info("Running without TimescaleDB (standard PostgreSQL)")
    
    logger.info("Database connection initialized successfully")
    return True


async def close_database():
    """Close all database connections gracefully."""
    await engine.dispose()
    logger.info("Database connections closed")
