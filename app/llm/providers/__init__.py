from __future__ import annotations

import openai


def _extract_retry_after(exc: openai.RateLimitError) -> int | None:
    try:
        headers = getattr(exc, "response", None) and exc.response.headers
        if headers and "retry-after" in headers:
            return int(headers["retry-after"])
    except Exception:
        pass
    return None
