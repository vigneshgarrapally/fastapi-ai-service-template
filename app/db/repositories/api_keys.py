"""Postgres repository for API keys."""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_key import ApiKey

logger = structlog.get_logger(__name__)


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_active(self, key_hash: str) -> dict[str, Any] | None:
        result = await self._session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "key": row.key_hash,
            "raw_prefix": row.raw_prefix,
            "client_name": row.label,
            "is_active": row.is_active,
        }

    async def touch_last_used(self, key_hash: str) -> None:
        await self._session.execute(
            update(ApiKey).where(ApiKey.key_hash == key_hash).values(last_used_at=datetime.now(UTC))
        )

    async def insert(self, doc: dict[str, Any]) -> str:
        row = ApiKey(
            key_hash=doc["key"],
            raw_prefix=doc.get("raw_prefix", ""),
            label=doc.get("client_name", ""),
            is_active=doc.get("is_active", True),
        )
        self._session.add(row)
        await self._session.flush()
        return str(row.id)
