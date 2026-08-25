"""Postgres repository for idempotency records.

Implements a three-phase claim/complete/fail protocol using
``INSERT ... ON CONFLICT DO NOTHING`` for an atomic claim.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import structlog
from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.idempotency import IdempotencyRecord

logger = structlog.get_logger(__name__)

_STALE_LOCK_MINUTES = 5


class IdempotencyError(Exception):
    pass


class IdempotencyPollTimeoutError(IdempotencyError):
    pass


class IdempotencyAttemptFailedError(IdempotencyError):
    pass


@dataclass
class ClaimResult:
    claimed: bool
    status: str
    result: dict[str, Any] | None = None
    fingerprint_mismatch: bool = False


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self,
        key: str,
        fingerprint: str,
        job_id: str | None = None,
    ) -> ClaimResult:
        now = datetime.now(UTC)
        expires = now + timedelta(hours=24)
        # INSERT ... ON CONFLICT DO NOTHING, *not* "INSERT and catch IntegrityError".
        # The request-scoped session is already inside `async with session.begin()`
        # (app/db/postgres.py:get_session) — a failing flush poisons that
        # transaction, and every statement after a rollback() inside a
        # context-managed transaction then raises InvalidRequestError. Letting
        # Postgres absorb the conflict keeps the outer transaction usable.
        stmt = (
            pg_insert(IdempotencyRecord)
            .values(
                idempotency_key=key,
                fingerprint=fingerprint,
                status="processing",
                locked_at=now,
                expires_at=expires,
                job_id=job_id,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(IdempotencyRecord.id)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        if inserted is not None:
            logger.info("idempotency.claimed", key=key)
            return ClaimResult(claimed=True, status="processing")
        return await self._inspect_existing(key, fingerprint, now)

    async def _inspect_existing(self, key: str, fingerprint: str, now: datetime) -> ClaimResult:
        result = await self._session.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return await self.claim(key, fingerprint)

        if row.fingerprint and row.fingerprint != fingerprint:
            return ClaimResult(claimed=False, status=row.status, fingerprint_mismatch=True)

        if row.status == "completed":
            logger.info("idempotency.cache_hit", key=key)
            return ClaimResult(
                claimed=False, status="completed", result=dict(row.response_snapshot or {})
            )

        if row.status == "failed":
            await self._session.execute(
                update(IdempotencyRecord)
                .where(
                    IdempotencyRecord.idempotency_key == key,
                    IdempotencyRecord.status == "failed",
                )
                .values(fingerprint=fingerprint, status="processing", locked_at=now)
            )
            return ClaimResult(claimed=True, status="processing")

        # Check for stale lock
        if row.locked_at:
            locked_at = row.locked_at if row.locked_at.tzinfo else row.locked_at.replace(tzinfo=UTC)
            if locked_at < now - timedelta(minutes=_STALE_LOCK_MINUTES):
                await self._session.execute(
                    update(IdempotencyRecord)
                    .where(
                        IdempotencyRecord.idempotency_key == key,
                        IdempotencyRecord.status == "processing",
                        IdempotencyRecord.locked_at == row.locked_at,
                    )
                    .values(fingerprint=fingerprint, status="processing", locked_at=now)
                )
                return ClaimResult(claimed=True, status="processing")

        return ClaimResult(claimed=False, status="processing")

    async def complete(self, key: str, fingerprint: str, result: dict[str, Any]) -> None:
        await self._session.execute(
            update(IdempotencyRecord)
            .where(
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.fingerprint == fingerprint,
                IdempotencyRecord.status == "processing",
            )
            .values(status="completed", response_snapshot=result)
        )

    async def fail(self, key: str, fingerprint: str) -> None:
        await self._session.execute(
            update(IdempotencyRecord)
            .where(
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.fingerprint == fingerprint,
                IdempotencyRecord.status == "processing",
            )
            .values(status="failed")
        )

    async def poll_for_completion(
        self,
        key: str,
        timeout_s: float = 45.0,
        poll_interval_s: float = 1.5,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            await asyncio.sleep(poll_interval_s)
            result = await self._session.execute(
                select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise IdempotencyError(f"Idempotency record {key} vanished during polling")
            if row.status == "completed":
                return dict(row.response_snapshot or {})
            if row.status == "failed":
                raise IdempotencyAttemptFailedError(f"Primary request for {key} failed.")
        raise IdempotencyPollTimeoutError(f"Timed out after {timeout_s}s waiting for {key}")

    async def delete_expired(self) -> int:
        """Delete all rows past their ``expires_at`` TTL. Returns rows deleted."""
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < datetime.now(UTC))
            ),
        )
        return result.rowcount or 0
