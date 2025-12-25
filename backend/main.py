import asyncio
import os
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.mcp_registry import close_mcp_registry, initialize_mcp_registry
from api.routers import actions as actions_router
from api.routers import health
from api.routers import incidents as incidents_router
from api.routers import query as query_router
from api.routers import threads as threads_router
from core.logging import configure_logging, get_logger
from core.settings import settings
from db.engine import dispose_engine

# Load .env into os.environ so third-party SDKs (Langfuse, etc.) can read
# their env vars directly — pydantic-settings reads .env into settings objects
# but does not populate os.environ.
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    logger.info("Starting %s (environment=%s)", settings.app_name, settings.environment)

    # Langfuse reads credentials from os.environ (LANGFUSE_PUBLIC_KEY,
    # LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL). load_dotenv() above ensures
    # the .env values are visible to the SDK.
    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        from langfuse import Langfuse

        Langfuse()  # initialises the global singleton; CallbackHandler() reuses it
        logger.info(
            "Langfuse tracing enabled (base_url=%s)",
            os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000"),
        )
    else:
        logger.info("Langfuse tracing disabled (LANGFUSE_PUBLIC_KEY not set)")

    # Initialize MCP client connections before building the graph so that
    # MCP-backed tools are available when agents resolve their tool lists.
    await initialize_mcp_registry()
    logger.info("Loop type: %s", type(asyncio.get_running_loop()).__name__)
    # Build the LangGraph with a Postgres checkpointer for HITL persistence.
    # AsyncPostgresSaver uses psycopg3; strip the SQLAlchemy driver prefix if present.
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        pg_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        async with AsyncPostgresSaver.from_conn_string(pg_url) as saver:
            await saver.setup()
            from agents.graph import build_graph

            app.state.graph = build_graph(checkpointer=saver)
            app.state.checkpointer_type = "postgres"
            logger.info("Graph initialised with AsyncPostgresSaver checkpointer")
            yield
    except Exception as exc:
        if settings.environment == "production":
            logger.critical("Postgres checkpointer unavailable in production: %s", exc)
            raise
        # Fall back to MemorySaver (single-process, non-persistent) so the app
        # still starts in development even if the Postgres checkpointer is unavailable.
        logger.error("Postgres checkpointer unavailable (%s); using MemorySaver", exc)
        from agents.graph import build_graph

        app.state.graph = build_graph()
        app.state.checkpointer_type = "memory"
        yield
    finally:
        # Flush any buffered Langfuse traces before process exit.
        if os.environ.get("LANGFUSE_PUBLIC_KEY"):
            try:
                from langfuse import get_client

                get_client().flush()
            except Exception:
                logger.warning("Langfuse flush failed", exc_info=True)

        await close_mcp_registry()
        await dispose_engine()
        logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(query_router.router, prefix="/api/v1")
app.include_router(actions_router.router, prefix="/api/v1")
app.include_router(incidents_router.router, prefix="/api/v1")
app.include_router(threads_router.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
