"""Shared test configuration for MCP server tests.

Sets DATABASE_URL from the backend .env if not already set, so tests can run
locally without manual env setup. Skips all tests if the database is unreachable.
"""

import os
from pathlib import Path

import pytest


def _load_database_url():
    """Read DATABASE_URL from backend/.env if not in environment."""
    if os.environ.get("DATABASE_URL"):
        return
    backend_env = Path(__file__).parent.parent / "backend" / ".env"
    if backend_env.exists():
        for line in backend_env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()
                return


_load_database_url()

_db_available: bool | None = None
_db_error: str | None = None


def _check_db():
    """Probe the database once and cache the result."""
    global _db_available, _db_error
    if _db_available is not None:
        return
    try:
        import asyncio

        from settings import get_settings
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        async def _probe():
            engine = create_async_engine(get_settings().DATABASE_URL)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()

        asyncio.run(_probe())
        _db_available = True
    except Exception as exc:
        _db_available = False
        _db_error = str(exc)


@pytest.fixture(autouse=True)
def _skip_if_no_db():
    """Skip every test if the database is unreachable."""
    _check_db()
    if not _db_available:
        pytest.skip(f"Database unavailable ({_db_error})")
