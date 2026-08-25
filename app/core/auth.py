"""API key authentication for protected endpoints.

Every request to a protected endpoint must include an ``X-API-Key`` header whose
value is a raw key of the form ``ak_<64 hex chars>``.

Authentication flow
--------------------
1. FastAPI extracts the raw key from the ``X-API-Key`` header via ``APIKeyHeader``.
2. ``_hash_key`` computes ``SHA-256(raw_key + API_KEY_SALT)`` to get the stored hash.
3. ``_verify`` looks up the hash in the ``api_keys`` table and checks ``is_active``.
4. On success, ``touch_last_used`` stamps ``last_used_at`` asynchronously.
5. The resolved key document is injected into the endpoint as ``ApiKeyDep``.

Keys are generated offline with ``scripts/manage_api_keys.py``. Only the hash is
ever persisted — the raw key is shown once at generation time and never stored.
"""

from typing import Annotated, Any

import structlog
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.core.dependencies import ApiKeyRepoDep
from app.core.security import hash_with_salt

logger = structlog.get_logger(__name__)

API_KEY_PREFIX = "ak"

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_key(raw_key: str) -> str:
    """Compute the stored hash for a raw API key."""
    settings = get_settings()
    return hash_with_salt(raw_key, settings.secrets.api_key_salt)


async def _verify(
    raw_key: Annotated[str | None, Security(_api_key_header)],
    repo: ApiKeyRepoDep,
) -> dict[str, Any]:
    """FastAPI dependency that validates the ``X-API-Key`` header.

    Args:
        raw_key: The raw API key from the ``X-API-Key`` request header. ``None``
            if the header is absent (``auto_error=False``).
        repo:    Injected ``ApiKeyRepository`` for the current request.

    Returns:
        The key document as a plain ``dict``. Endpoints that only need the
        side-effect (auth guard) should annotate the parameter as ``_auth: ApiKeyDep``.

    Raises:
        HTTPException (401): If the header is absent or the key does not match
            any active entry.

    Note:
        Logs only the first 8 characters of the raw key on failure — never the
        full value — to prevent accidental secret leakage in log output.
    """
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    hashed = _hash_key(raw_key)
    doc = await repo.find_active(hashed)

    if doc is None:
        logger.warning("auth.invalid_key", prefix=raw_key[:8] if len(raw_key) >= 8 else "short")
        raise HTTPException(status_code=401, detail="Invalid API key")

    await repo.touch_last_used(hashed)
    logger.debug("auth.ok", client=doc.get("client_name"), prefix=doc.get("raw_prefix"))
    return doc


ApiKeyDep = Annotated[dict[str, Any], Depends(_verify)]
