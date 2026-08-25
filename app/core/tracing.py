"""OpenTelemetry distributed tracing setup.

Exports spans via OTLP gRPC (e.g. to Tempo/Jaeger through an OTel collector).
No-op when ``settings.observability.otel_endpoint`` is empty.

Two public setup functions are provided:

``setup_tracing(app, settings)``
    For the **API process** — sets up the TracerProvider and instruments
    FastAPI and httpx. Imports ``FastAPIInstrumentor`` lazily so this module
    doesn't require the FastAPI instrumentation package in a worker-only process.

``setup_tracing_worker(settings)``
    For **worker processes** — sets up the same TracerProvider and instruments
    httpx, but skips FastAPI instrumentation (workers have no HTTP server).

Both share ``shutdown_tracing()`` for teardown.

Middleware order note (API only)
---------------------------------
``setup_tracing`` must be called **after** all ``app.add_middleware()`` calls.
In Starlette's LIFO middleware stack the last-registered middleware runs
outermost (receives the request first). Calling ``setup_tracing`` last ensures
the OTel middleware starts the trace span before ``RequestContextMiddleware``
binds the ``traceID`` context variable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import Settings

if TYPE_CHECKING:
    # Only imported for the type hint below — this module must stay importable
    # in a worker-only process that never installs the FastAPI extra.
    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def _init_provider(settings: Settings) -> SDKTracerProvider | None:
    """Create, configure, and register the global TracerProvider.

    Returns the provider if tracing is enabled, or ``None`` when
    ``settings.observability.otel_endpoint`` is empty (tracing disabled).
    """
    if not settings.observability.otel_endpoint:
        logger.debug("tracing.disabled", reason="otel_endpoint not set")
        return None

    service_name = settings.observability.otel_service_name or settings.app.app_name

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": settings.app.environment,
        }
    )
    provider = SDKTracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.observability.otel_endpoint,
                insecure=True,
            )
        )
    )
    trace.set_tracer_provider(provider)
    return provider


def setup_tracing(app: FastAPI, settings: Settings) -> None:
    """Configure tracing for the API process.

    Sets up the TracerProvider and instruments FastAPI (every HTTP request
    becomes a root span) and httpx (every outbound LLM call becomes a child span).
    """
    provider = _init_provider(settings)
    if provider is None:
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    service_name = settings.observability.otel_service_name or settings.app.app_name

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "tracing.enabled",
        endpoint=settings.observability.otel_endpoint,
        service=service_name,
        process="api",
    )


def setup_tracing_worker(settings: Settings) -> None:
    """Configure tracing for worker processes.

    Same as ``setup_tracing`` but skips FastAPI instrumentation — workers have
    no HTTP server. Instruments httpx (LLM calls).
    """
    provider = _init_provider(settings)
    if provider is None:
        return

    service_name = settings.observability.otel_service_name or settings.app.app_name

    HTTPXClientInstrumentor().instrument()

    logger.info(
        "tracing.enabled",
        endpoint=settings.observability.otel_endpoint,
        service=service_name,
        process="worker",
    )


def shutdown_tracing() -> None:
    """Flush the span buffer and shut down the TracerProvider.

    Safe to call even when tracing was not enabled — the default NoOp provider
    silently ignores the shutdown call.
    """
    provider = trace.get_tracer_provider()
    if isinstance(provider, SDKTracerProvider):
        provider.shutdown()
