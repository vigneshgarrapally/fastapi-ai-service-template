"""Postgres repository for the generic async job queue."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job_type: str, input_payload: dict[str, Any]) -> Job:
        job = Job(job_type=job_type, input_payload=input_payload, status="queued")
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> Job | None:
        result = await self._session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def mark_processing(self, job_id: uuid.UUID) -> None:
        job = await self.get(job_id)
        if job is not None:
            job.status = "processing"

    async def mark_completed(self, job_id: uuid.UUID, result: dict[str, Any]) -> None:
        job = await self.get(job_id)
        if job is not None:
            job.status = "completed"
            job.result = result

    async def mark_failed(self, job_id: uuid.UUID, error: str) -> None:
        job = await self.get(job_id)
        if job is not None:
            job.status = "failed"
            job.error = error
