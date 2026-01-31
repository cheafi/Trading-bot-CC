"""
TradingAI Bot - Database Connection
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from src.core.config import get_settings

settings = get_settings()

# Use the async database URL from settings (already in postgresql+asyncpg:// format)
database_url = settings.async_database_url

# Create async engine
engine = create_async_engine(
    database_url,
    echo=settings.log_level == "DEBUG",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base for ORM models
Base = declarative_base()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Check if database is healthy."""
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def init_database():
    """Initialize database connection."""
    # Test connection
    healthy = await check_database_health()
    if not healthy:
        raise ConnectionError("Cannot connect to database")
    
    return engine
