"""Unit tests for IdempotencyRepository — the claim/complete/fail protocol.

Regression coverage for the specific bug this protocol is designed to avoid:
a duplicate request with the same X-Idempotency-Key but a *different* payload
must be rejected as a fingerprint mismatch, not silently treated as a cache hit.
"""

from unittest.mock import AsyncMock, MagicMock

from app.db.repositories.idempotency import IdempotencyRepository


def _session_with(insert_returns=None, existing_row=None):
    session = MagicMock()
    insert_result = MagicMock()
    insert_result.scalar_one_or_none = MagicMock(return_value=insert_returns)
    existing_result = MagicMock()
    existing_result.scalar_one_or_none = MagicMock(return_value=existing_row)
    session.execute = AsyncMock(side_effect=[insert_result, existing_result])
    return session


async def test_claim_succeeds_on_first_insert():
    session = _session_with(insert_returns="new-id")
    repo = IdempotencyRepository(session)

    result = await repo.claim("key-1", "fingerprint-a")

    assert result.claimed is True
    assert result.status == "processing"


async def test_claim_detects_fingerprint_mismatch():
    existing = MagicMock(fingerprint="fingerprint-a", status="processing", locked_at=None)
    session = _session_with(insert_returns=None, existing_row=existing)
    repo = IdempotencyRepository(session)

    result = await repo.claim("key-1", "fingerprint-b")

    assert result.claimed is False
    assert result.fingerprint_mismatch is True


async def test_claim_returns_cached_result_on_completed_hit():
    existing = MagicMock(
        fingerprint="fingerprint-a",
        status="completed",
        response_snapshot={"job_id": "abc"},
        locked_at=None,
    )
    session = _session_with(insert_returns=None, existing_row=existing)
    repo = IdempotencyRepository(session)

    result = await repo.claim("key-1", "fingerprint-a")

    assert result.claimed is False
    assert result.status == "completed"
    assert result.result == {"job_id": "abc"}
