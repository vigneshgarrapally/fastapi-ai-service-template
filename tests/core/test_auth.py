"""Unit tests for the X-API-Key auth dependency."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.auth import _hash_key, _verify


async def test_verify_rejects_missing_key():
    with pytest.raises(HTTPException) as exc_info:
        await _verify(None, repo=MagicMock())
    assert exc_info.value.status_code == 401


async def test_verify_rejects_unknown_key():
    repo = MagicMock()
    repo.find_active = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await _verify("ak_deadbeef", repo=repo)
    assert exc_info.value.status_code == 401


async def test_verify_accepts_known_key_and_touches_last_used():
    doc = {"key": _hash_key("ak_realkey"), "client_name": "test-client"}
    repo = MagicMock()
    repo.find_active = AsyncMock(return_value=doc)
    repo.touch_last_used = AsyncMock()

    result = await _verify("ak_realkey", repo=repo)

    assert result == doc
    repo.touch_last_used.assert_awaited_once_with(doc["key"])
