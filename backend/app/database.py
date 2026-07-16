import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Database URL from environment or fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./siraj.db")

# Normalise URL for async drivers:
#  - postgresql:// → postgresql+asyncpg://
#  - postgres://    → postgresql+asyncpg://   (common Heroku/Replit alias)
if DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    # asyncpg does not support sslmode in the query string the same way;
    # strip it to avoid "unknown parameter" errors and use ssl=require connect_arg instead
    if "sslmode=" in DATABASE_URL:
        import re
        DATABASE_URL = re.sub(r"[?&]sslmode=[^&]*", "", DATABASE_URL).rstrip("?")

# For SQLite, we need check_same_thread=False
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

# Dependency injection helper for FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Bootstrap database tables
async def create_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
