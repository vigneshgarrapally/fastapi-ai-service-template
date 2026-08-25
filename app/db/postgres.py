"""Postgres async engine, session factory, and connection helpers."""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = structlog.get_logger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, pool_size: int = 10, max_overflow: int = 20) -> None:
    """Create the async engine and session factory. Called once at startup."""
    global _engine, _session_factory
    _engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
    )
    # expire_on_commit=False: a worker that reads a row, commits/closes that
    # transaction, then keeps using the detached object (e.g. across an LLM call
    # that runs outside any transaction) would otherwise hit DetachedInstanceError
    # on the first attribute access after commit. Do not flip this without
    # checking every worker that holds a row past its own transaction.
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("postgres.engine_created")


async def dispose_engine() -> None:
    """Dispose the engine connection pool. Called at shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("postgres.engine_disposed")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Postgres session factory not initialised — call init_engine() first.")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yield a transactional AsyncSession, auto-commit on success."""
    factory = get_session_factory()
    async with factory() as session, session.begin():
        yield session


async def ping() -> float:
    """Return the round-trip latency in ms for a SELECT 1 ping."""
    import time

    from sqlalchemy import text

    factory = get_session_factory()
    t0 = time.monotonic()
    async with factory() as session:
        await session.execute(text("SELECT 1"))
    return round((time.monotonic() - t0) * 1000, 2)


async def verify_connection() -> None:
    """Fail fast if Postgres is unreachable.

    ``init_engine()`` only builds a lazy connection pool — a bad or missing
    ``DATABASE_URL`` would otherwise go unnoticed until the first real query,
    well after the process reports itself started. Call this once, right after
    ``init_engine()``, so every entry point (API and every worker) crashes on
    boot instead of serving/consuming against a database it can never reach.
    """
    latency_ms = await ping()
    logger.info("postgres.connection_verified", latency_ms=latency_ms)
