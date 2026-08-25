"""Worker handler for ``job_type == "chat"`` messages on the ``ai.jobs`` queue.

Deleted by the template's post-generation cleanup alongside the rest of
``app/worker/`` when ``include_worker`` is declined, and directly when
``include_ai_service`` is declined — so this file needs no Jinja conditionals
of its own.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.jobs import JobRepository
from app.features.ai.service import chat

logger = structlog.get_logger(__name__)


async def handle_chat_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Process one ``chat`` job: run the agent turn and record the outcome.

    Args:
        session: An ``AsyncSession`` already inside an open transaction (see
            ``app/worker/main.py``'s session-per-message pattern). Never
            shared across messages.
        payload: The decoded RabbitMQ message body. Must contain ``job_id``;
            ``session_id``/``message`` are read from the job's own
            ``input_payload`` after loading it from Postgres.

    Note:
        Catches any exception broadly and records it on the job row instead
        of letting it propagate. This sits at the top of the per-message call
        stack, inside ``message.process()`` in ``app/worker/main.py`` — an
        uncaught exception here would break RabbitMQ's ack handling, so a
        broad ``except Exception`` is the correct boundary, not a violation
        of "don't add unnecessary error handling".
    """
    repo = JobRepository(session)
    job_id = uuid.UUID(str(payload["job_id"]))
    job = await repo.get(job_id)
    if job is None:
        logger.warning("worker.chat_job.not_found", job_id=str(job_id))
        return

    await repo.mark_processing(job_id)
    try:
        session_id = str(job.input_payload["session_id"])
        message = str(job.input_payload["message"])
        reply = await chat(session_id, message)
    except Exception as exc:
        logger.error("worker.chat_job.failed", job_id=str(job_id), error=str(exc))
        await repo.mark_failed(job_id, str(exc))
        return

    await repo.mark_completed(job_id, {"reply": reply})
    logger.info("worker.chat_job.completed", job_id=str(job_id))
