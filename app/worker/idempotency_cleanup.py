"""Background task: periodically delete expired idempotency records."""

import asyncio

import structlog

from app.core.config import Settings
from app.db.postgres import get_session_factory
from app.db.repositories.idempotency import IdempotencyRepository

logger = structlog.get_logger(__name__)


async def run_idempotency_cleanup_loop(settings: Settings) -> None:
    """Run forever, deleting expired idempotency records on an interval.

    Cancelled by the worker's shutdown path (``asyncio.Task.cancel()``); the
    ``CancelledError`` propagates out of ``asyncio.sleep`` and this function
    returns cleanly.
    """
    interval = settings.worker.idem_cleanup_interval_seconds
    session_factory = get_session_factory()

    while True:
        await asyncio.sleep(interval)
        try:
            async with session_factory() as session, session.begin():
                deleted = await IdempotencyRepository(session).delete_expired()
            if deleted:
                logger.info("idempotency.cleanup.deleted", count=deleted)
        except Exception as exc:
            logger.error("idempotency.cleanup.failed", error=str(exc))
