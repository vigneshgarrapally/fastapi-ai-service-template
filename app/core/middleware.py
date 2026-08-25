"""Per-request structlog context injection middleware.

Binds ``request_id``, ``service``, ``env``, and (when OTel tracing is active)
``traceID`` into structlog's async context variables at the start of every request
so that all log lines emitted during the request lifecycle automatically carry
these fields in JSON output.

The binding works because ``setup_logging()`` registers
``structlog.contextvars.merge_contextvars`` as the first shared processor, which
merges the context into every log event before rendering.

OTel integration
-----------------
When OTel tracing is active, the OTel middleware runs outermost (registered after
this middleware in the LIFO stack) and starts the trace span before this
middleware executes. ``get_current_span()`` therefore returns a live, valid span,
and its ``trace_id`` is bound as ``traceID`` into structlog — useful for
Grafana's Loki -> Tempo derived-field links to jump from a log line to its trace.

Usage — registered in ``app/main.py`` via ``app.add_middleware()``.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inject request context into structlog for the lifetime of each request.

    On every inbound request:

    1. Reads the ``X-Request-ID`` header if present, otherwise generates a new
       UUID4 — lets upstream callers propagate their own correlation ID end-to-end.
    2. Clears any stale context left over from a previous request on the same
       coroutine (important for multi-worker deployments).
    3. Binds ``request_id``, ``service``, and ``env`` into structlog's async
       context so every ``logger.*()`` call within the handler emits these fields
       automatically.
    4. When OTel tracing is active, binds ``traceID`` into structlog and sets
       ``request_id`` as a span attribute for trace <-> log cross-navigation.
    5. Echoes the ``X-Request-ID`` back in the response header so callers can
       correlate their request with the log entry.
    6. Clears the context after the response is sent.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Wrap each request with structured logging context.

        Args:
            request: The incoming Starlette ``Request``.
            call_next: The next middleware or route handler in the chain.

        Returns:
            The response with ``X-Request-ID`` header attached.
        """
        settings = get_settings()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Clear stale context from any previous request on this coroutine
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            service=settings.app.app_name,
            env=settings.app.environment,
        )

        try:
            from opentelemetry import trace as otel_trace

            span = otel_trace.get_current_span()
            ctx = span.get_span_context()
            if ctx.is_valid:
                structlog.contextvars.bind_contextvars(traceID=format(ctx.trace_id, "032x"))
                span.set_attribute("request_id", request_id)
        except ImportError:
            pass

        response = await call_next(request)

        # Echo the ID back so callers can correlate with log entries
        response.headers["X-Request-ID"] = request_id

        # Clean up — belt-and-suspenders alongside the clear on next entry
        structlog.contextvars.clear_contextvars()
        return response
