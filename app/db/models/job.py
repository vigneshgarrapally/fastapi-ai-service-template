"""Postgres model for the generic async job queue.

One table for every "submit now, process later" job type — distinguish by
``job_type`` rather than adding a table per capability. If a job type grows
enough bespoke columns to need its own table, that's the signal to split it out.
"""

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Job(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "jobs"

    # e.g. "chat" — which worker consumer handles this job.
    job_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # "queued" | "processing" | "completed" | "failed"
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
