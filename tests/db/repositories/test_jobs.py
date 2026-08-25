"""Unit tests for JobRepository."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.db.repositories.jobs import JobRepository


def _session_returning(row):
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


async def test_create_adds_a_queued_job():
    session = _session_returning(None)
    repo = JobRepository(session)

    job = await repo.create("chat", {"session_id": "abc", "message": "hi"})

    assert job.job_type == "chat"
    assert job.status == "queued"
    assert job.input_payload == {"session_id": "abc", "message": "hi"}
    session.add.assert_called_once_with(job)


async def test_get_returns_none_when_missing():
    session = _session_returning(None)
    repo = JobRepository(session)

    assert await repo.get(uuid.uuid4()) is None


async def test_mark_completed_sets_status_and_result():
    row = MagicMock(status="processing", result=None)
    session = _session_returning(row)
    repo = JobRepository(session)

    await repo.mark_completed(uuid.uuid4(), {"reply": "hello"})

    assert row.status == "completed"
    assert row.result == {"reply": "hello"}


async def test_mark_failed_sets_status_and_error():
    row = MagicMock(status="processing", error=None)
    session = _session_returning(row)
    repo = JobRepository(session)

    await repo.mark_failed(uuid.uuid4(), "boom")

    assert row.status == "failed"
    assert row.error == "boom"
