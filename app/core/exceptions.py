"""Global exception handler for unhandled errors.

Registered in ``app/main.py`` via
``app.add_exception_handler(Exception, global_exception_handler)``.

Any exception that propagates out of an endpoint without being caught by FastAPI's
built-in validation machinery is routed here. The handler logs the full exception
(including traceback) through structlog and returns a generic HTTP 500 response so
internal error details are never leaked to API consumers.
"""

import traceback

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unhandled exception by logging it and returning HTTP 500.

    Acts as a final safety net so uncaught bugs produce a structured log entry
    with full traceback context (``exc_info=exc``) rather than an unformatted
    crash dump. The response body is deliberately generic to avoid leaking stack
    traces or internal state to API consumers.

    Args:
        request: The incoming FastAPI ``Request`` object. Used to attach ``path``
            and ``method`` context to the log entry.
        exc: The unhandled exception instance.

    Returns:
        A ``JSONResponse`` with HTTP 500 and body ``{"detail": "Internal server error"}``.

    Note:
        FastAPI's built-in ``RequestValidationError`` and ``HTTPException``
        handlers run **before** this handler, so 422 and intentional HTTP errors
        are never routed here.
    """
    settings = get_settings()

    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )

    content = {"detail": "Internal server error"}

    # In development/debug mode, include the traceback in the response body
    if settings.app.environment == "development" or settings.app.debug:
        content["exception"] = str(exc)
        content["traceback"] = traceback.format_exc()

    return JSONResponse(
        status_code=500,
        content=content,
    )
