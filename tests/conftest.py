"""
Shared pytest fixtures for async FastAPI tests.

Sets up an isolated in-memory SQLite database for every test session so that
auth (and future) tests never touch the real development database.
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Point to an in-memory SQLite DB before any app module is imported
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)

from backend.app.main import app  # noqa: E402  (must come after env override)
from backend.app.database import Base, get_db  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a fresh async engine backed by an in-memory SQLite database."""
    _engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        # Import all models so Base.metadata is fully populated
        import backend.app.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture()
async def db_session(engine):
    """Yield a transactional AsyncSession that is rolled back after each test."""
    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session):
    """
    Return an httpx AsyncClient wired to the FastAPI app, with the
    real *get_db* dependency swapped out for the test-scoped session.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
