"""
Langfuse observability helper — SafeLangfuse pattern, Langfuse v4 SDK.

API used here (langfuse>=4.x):
  - Langfuse(public_key, secret_key, host)  -> client instance
  - client.auth_check()                     -> verify credentials
  - Langfuse.create_trace_id(seed=...)      -> deterministic UUID (class/static method)
  - client.start_as_current_observation(
        as_type="span", name=...,
        trace_context={"trace_id": ...})    -> context manager; yields a LangfuseSpan
  - span.update(input=..., output=...,
        metadata=..., level=...,
        status_message=...)                -> update the span observation
  - CallbackHandler()                       -> auto-attaches to the active span when invoked,
                                               MUST be created inside the with-block

Usage pattern in callers::

    langfuse = get_langfuse()
    span_ctx = contextlib.nullcontext()
    if langfuse:
        trace_id = langfuse.create_trace_id(seed=f"chat-{session_id}-{uuid4()}")
        span_ctx = langfuse.start_trace_span("chat-turn", trace_id)

    with span_ctx as span:
        callbacks = []
        if span:
            span.update(input=...)
            handler = langfuse.get_langchain_handler()  # inside the with block!
            if handler:
                callbacks = [handler]
        result = await graph.ainvoke(state, config={"callbacks": callbacks})
        if span:
            span.update(output=...)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal

import structlog

if TYPE_CHECKING:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

logger = structlog.get_logger(__name__)

_instance: SafeLangfuse | None = None


class SafeLangfuse:
    """Langfuse v4 wrapper with auth check and graceful degradation."""

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "https://cloud.langfuse.com",
    ) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._host = host
        self._client: Langfuse | None = None
        self._is_connected: bool = False

    def connect(self) -> None:
        """Initialize the Langfuse client and verify credentials.

        Sets environment variables first so that ``CallbackHandler()`` (which
        uses the global client) picks up the same credentials automatically.

        Raises:
            RuntimeError: If the auth check fails or the client cannot connect.
        """
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", self._public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", self._secret_key)
        os.environ.setdefault("LANGFUSE_HOST", self._host)

        from langfuse import Langfuse

        self._client = Langfuse(
            public_key=self._public_key,
            secret_key=self._secret_key,
            host=self._host,
        )

        if not self._client.auth_check():
            raise RuntimeError(
                "Langfuse auth check failed — verify LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"
            )

        self._is_connected = True
        logger.info("langfuse.connected", host=self._host)

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def create_trace_id(self, seed: str) -> str:
        """Create a deterministic trace ID from a seed string.

        Pre-generated before the graph runs so it can be persisted immediately —
        no race conditions, no separate get-trace-id call needed.
        """
        from langfuse import Langfuse as _Langfuse

        return str(_Langfuse.create_trace_id(seed=seed))

    def start_trace_span(self, name: str, trace_id: str) -> Any:
        """Return a context manager creating an observation span rooted to trace_id.

        Returns a no-op context manager (``contextlib.nullcontext``) if not connected.
        """
        import contextlib

        if not self._is_connected or self._client is None:
            return contextlib.nullcontext()

        try:
            return self._client.start_as_current_observation(
                as_type="span",
                name=name,
                trace_context={"trace_id": trace_id},
            )
        except Exception as exc:
            logger.warning("langfuse.start_span_failed", error=str(exc))
            return contextlib.nullcontext()

    def get_langchain_handler(self) -> CallbackHandler | None:
        """Create a LangChain CallbackHandler.

        Must be called INSIDE the ``start_trace_span`` context so the handler
        auto-attaches to the currently active trace/span.
        """
        if not self._is_connected:
            return None
        try:
            from langfuse.langchain import CallbackHandler

            return CallbackHandler()
        except Exception as exc:
            logger.warning("langfuse.handler_create_failed", error=str(exc))
            return None

    def create_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
        data_type: Literal["NUMERIC", "BOOLEAN"] = "NUMERIC",
    ) -> None:
        """Create a score on an existing trace (e.g. an eval result or user feedback).

        Silently no-ops if not connected or if the call fails.
        """
        if not self._is_connected or self._client is None:
            return
        try:
            self._client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
                data_type=data_type,
            )
        except Exception as exc:
            logger.warning("langfuse.create_score_failed", error=str(exc))

    def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception as exc:
                logger.warning("langfuse.flush_failed", error=str(exc))

    def shutdown(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
                self._client.shutdown()
            except Exception as exc:
                logger.warning("langfuse.shutdown_failed", error=str(exc))
            finally:
                self._client = None
                self._is_connected = False


def init_langfuse() -> SafeLangfuse:
    """Initialize the global SafeLangfuse instance. Call once at app startup.

    Silently disabled (not an error) when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
    are unset — the Observability component also covers OTel tracing and
    Prometheus metrics, neither of which need a Langfuse account, so this must
    not block startup just because LLM tracing specifically isn't configured
    yet. ``get_langfuse()`` always returns a usable (if disconnected) instance;
    every method on it already no-ops safely when disconnected.

    Raises:
        RuntimeError: Only if the auth check against the Langfuse server fails
            (a real credential error), never for keys being merely absent.
    """
    global _instance

    from app.core.config import get_settings

    settings = get_settings()

    safe = SafeLangfuse(
        public_key=settings.secrets.langfuse_public_key,
        secret_key=settings.secrets.langfuse_secret_key,
        host=settings.observability.langfuse_host,
    )
    if not settings.secrets.langfuse_public_key or not settings.secrets.langfuse_secret_key:
        logger.info("langfuse.disabled", reason="LANGFUSE_PUBLIC_KEY/SECRET_KEY not set")
        _instance = safe
        return _instance

    safe.connect()
    _instance = safe
    return _instance


def get_langfuse() -> SafeLangfuse:
    """Get the global SafeLangfuse instance.

    Raises:
        RuntimeError: If called before ``init_langfuse()``.
    """
    if _instance is None:
        raise RuntimeError("Langfuse not initialized — init_langfuse() must be called at startup")
    return _instance


def shutdown_langfuse() -> None:
    """Flush and shut down the global Langfuse instance. Call at app shutdown."""
    global _instance
    if _instance is not None:
        _instance.shutdown()
        _instance = None
