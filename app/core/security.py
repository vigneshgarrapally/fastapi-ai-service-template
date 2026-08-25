import hashlib
import json
from typing import Any


def hash_with_salt(raw_key: str, salt: str) -> str:
    """Compute the SHA-256 hash of a raw key combined with a salt.

    Single source of truth for API key hashing across the application and
    management scripts.

    Args:
        raw_key: The full raw API key string.
        salt:    The secret salt value.

    Returns:
        Hex-encoded SHA-256 digest of the salted key.
    """
    salted = raw_key + salt
    return hashlib.sha256(salted.encode()).hexdigest()


def fingerprint_body(body: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 fingerprint of a request body dict.

    The body is serialized as canonical JSON (sorted keys, no extra whitespace)
    before hashing, so the fingerprint is stable regardless of key ordering in
    the original request.

    Used by the idempotency layer to detect "key collisions" — where a client
    reuses an idempotency key with a different request payload.

    Args:
        body: Request body as a dict (typically from Pydantic ``model_dump()``).

    Returns:
        Hex-encoded SHA-256 digest of the canonical JSON representation.
    """
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
