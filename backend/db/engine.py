from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.settings import settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.debug,
            pool_pre_ping=True,
        )
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
