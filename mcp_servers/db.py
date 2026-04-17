"""Shared async database session factory — single connection pool for all domains."""

from settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        s = get_settings()
        _engine = create_async_engine(s.DATABASE_URL, pool_pre_ping=True)
        _session_factory = async_sessionmaker(
            bind=_engine, expire_on_commit=False, autoflush=False
        )
    return _session_factory
