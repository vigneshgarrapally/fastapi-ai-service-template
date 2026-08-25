"""Unit tests for ApiKeyRepository."""

from unittest.mock import AsyncMock, MagicMock

from app.db.repositories.api_keys import ApiKeyRepository


def _session_returning(row):
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result)
    return session


async def test_find_active_returns_none_for_unknown_hash():
    repo = ApiKeyRepository(_session_returning(None))

    assert await repo.find_active("unknown-hash") is None


async def test_find_active_returns_key_document():
    row = MagicMock(key_hash="h", raw_prefix="ak_1234", label="my-client", is_active=True)
    repo = ApiKeyRepository(_session_returning(row))

    doc = await repo.find_active("h")

    assert doc == {
        "key": "h",
        "raw_prefix": "ak_1234",
        "client_name": "my-client",
        "is_active": True,
    }
