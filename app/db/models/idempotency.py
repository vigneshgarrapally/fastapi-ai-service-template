"""Postgres model for idempotency_records."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKey


def _default_expires() -> datetime:
    return datetime.now(UTC) + timedelta(hours=24)


class IdempotencyRecord(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "idempotency_records"

    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    # "processing" | "completed" | "failed"
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    response_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_default_expires, nullable=False
    )
