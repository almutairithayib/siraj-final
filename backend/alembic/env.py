"""Alembic env.py — async SQLAlchemy configuration for Siraj."""
import asyncio
import os
import re
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool

from alembic import context

# ── Alembic config object ────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so autogenerate can detect them ───────────────────────
# Importing Base pulls in every model via the __init__ that imports them all.
from backend.app.database import Base  # noqa: E402
import backend.app.models  # noqa: E402, F401  (side-effect: registers all mappers)

target_metadata = Base.metadata


# ── Resolve database URL (mirrors backend/app/database.py logic) ─────────────
def _get_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./siraj.db")
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        if "sslmode=" in url:
            url = re.sub(r"[?&]sslmode=[^&]*", "", url).rstrip("?")
    return url


# ── Offline mode (generate SQL without a live DB connection) ─────────────────
def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render column-level DEFAULT values so regenerated scripts are complete
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (async connection to live DB) ────────────────────────────────
def do_run_migrations(connection):
    url = connection.engine.url.render_as_string(hide_password=False)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite needs batch mode for ALTER TABLE emulation
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_get_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
