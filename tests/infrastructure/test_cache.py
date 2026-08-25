"""Unit tests for the Redis cache wrapper."""

from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.cache import CacheClient


def _redis_mock() -> MagicMock:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    return redis


async def test_get_json_returns_none_when_missing():
    client = CacheClient(_redis_mock())

    assert await client.get_json("missing-key") is None


async def test_set_json_serializes_value():
    redis = _redis_mock()
    client = CacheClient(redis)

    await client.set_json("k", {"a": 1}, ttl_seconds=60)

    redis.set.assert_awaited_once_with("k", '{"a": 1}', ex=60)


async def test_incr_sets_ttl_only_on_first_creation():
    redis = _redis_mock()
    redis.incr = AsyncMock(return_value=1)
    client = CacheClient(redis)

    count = await client.incr("rate:1.2.3.4", ttl_seconds=60)

    assert count == 1
    redis.expire.assert_awaited_once_with("rate:1.2.3.4", 60)


async def test_incr_does_not_reset_ttl_on_subsequent_calls():
    redis = _redis_mock()
    redis.incr = AsyncMock(return_value=2)
    client = CacheClient(redis)

    await client.incr("rate:1.2.3.4", ttl_seconds=60)

    redis.expire.assert_not_awaited()
