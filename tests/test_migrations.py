"""
Test that Alembic migrations match the current SQLAlchemy models.

How it works
------------
1. A fresh, empty SQLite database is created in a temp file.
2. ``alembic upgrade head`` is run against that database to apply every
   migration in history.
3. Alembic's ``compare_metadata`` helper is used to diff the resulting schema
   against the in-memory SQLAlchemy model metadata.
4. The test fails (with a human-readable diff) if any differences are found,
   which means a developer added/renamed a column but forgot to generate a
   migration.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

# Absolute path to the project root (one level above ``tests/``).
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_migrations_match_models() -> None:
    """Apply all migrations to a fresh SQLite DB and assert no schema drift."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # aiosqlite URL is what alembic / env.py expects; plain sqlite:// is used
    # below only for the synchronous comparison step.
    async_db_url = f"sqlite+aiosqlite:///{db_path}"
    sync_db_url = f"sqlite:///{db_path}"

    env = {**os.environ, "DATABASE_URL": async_db_url}

    try:
        # ── Step 1: run every migration against the blank database ───────────
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "alembic upgrade head failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        # ── Step 2: import models so their metadata is fully populated ────────
        # These imports must happen *after* env is set up and *inside* the test
        # so that Base.metadata is not stale from a previous import.
        from backend.app.database import Base  # noqa: F401
        import backend.app.models  # noqa: F401, F811

        # ── Step 3: compare migrated schema vs model metadata ─────────────────
        # Use a plain synchronous SQLite connection for the diff — no async needed.
        engine = sa.create_engine(sync_db_url)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diffs = compare_metadata(ctx, Base.metadata)
        engine.dispose()

        # ── Step 4: assert no drift ────────────────────────────────────────────
        assert not diffs, (
            "Schema drift detected: the SQLAlchemy models and the Alembic "
            "migrations are out of sync.\n"
            "Run the following command to generate the missing migration:\n\n"
            "    alembic revision --autogenerate -m '<describe your change>'\n\n"
            "Differences found:\n"
            + "\n".join(f"  {d}" for d in diffs)
        )

    finally:
        Path(db_path).unlink(missing_ok=True)
