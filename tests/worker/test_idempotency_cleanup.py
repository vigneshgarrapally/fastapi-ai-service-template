"""Unit test for the idempotency cleanup background loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.worker.idempotency_cleanup import run_idempotency_cleanup_loop


async def test_cleanup_loop_deletes_expired_records_then_cancels():
    settings = MagicMock()
    settings.worker.idem_cleanup_interval_seconds = 0

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock()
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    session_factory = MagicMock(return_value=session)

    with (
        patch("app.worker.idempotency_cleanup.get_session_factory", return_value=session_factory),
        patch(
            "app.worker.idempotency_cleanup.IdempotencyRepository.delete_expired",
            new=AsyncMock(return_value=3),
        ),
    ):
        task = asyncio.create_task(run_idempotency_cleanup_loop(settings))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
