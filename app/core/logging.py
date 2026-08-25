"""Structured logging configuration using structlog.

Configures the global structlog pipeline once at process startup via
``setup_logging()``. Every process (API, worker, CLI script) calls this function
as its very first action so all subsequent log calls produce consistently
structured output.

Architecture
------------
structlog is bridged into stdlib ``logging`` via ``ProcessorFormatter`` so that
both app logs (structlog) and third-party logs (uvicorn, sqlalchemy, etc.) pass
through the same formatting pipeline. This ensures every line written to stdout
is valid JSON in production — critical for log aggregators.

Log formats
-----------
- **development** (``ENVIRONMENT=development``): Human-readable coloured output
  via ``structlog.dev.ConsoleRenderer``.
- **production / staging**: Machine-readable JSON via ``structlog.processors.JSONRenderer``.

Log levels
----------
- ``app.*`` loggers: controlled by ``LOG_LEVEL`` (or ``DEBUG=true``).
- Third-party stdlib loggers: capped at ``WARNING`` so their INFO/DEBUG chatter
  never drowns out application logs.
"""

import logging
import sys

import structlog

from app.core.config import get_settings


def _inject_static_fields(
    logger: structlog.types.WrappedLogger,
    method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Add service and env to every log entry if not already present.

    Runs after ``merge_contextvars`` so per-request context vars (bound by
    ``RequestContextMiddleware``) take precedence — ``setdefault`` only fills the
    value when the key is absent. For startup / background logs that run outside
    a request context these fields are always injected here.
    """
    settings = get_settings()
    event_dict.setdefault("service", settings.app.app_name)
    event_dict.setdefault("env", settings.app.environment)
    return event_dict


def setup_logging() -> None:
    """Configure structlog and the stdlib ``logging`` module.

    Reads ``Settings.log_level`` and ``Settings.environment`` to choose the
    appropriate output format and minimum severity level. When ``Settings.debug``
    is ``True`` the effective level is unconditionally set to ``DEBUG``.

    This function is idempotent — calling it multiple times reconfigures
    structlog each time but does not accumulate duplicate handlers. In practice
    it should only be called once per process.

    Note:
        Must be called **before** any ``structlog.get_logger()`` call so that the
        pipeline is wired up before the first log event is emitted.
    """
    settings = get_settings()

    log_level = getattr(logging, settings.app.log_level.upper(), logging.INFO)
    if settings.app.debug:
        log_level = logging.DEBUG

    # Processors shared by both the structlog pipeline and the ProcessorFormatter
    # foreign_pre_chain (applied to third-party stdlib log records).
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_static_fields,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.app.environment == "development":
        final_processors: list[structlog.types.Processor] = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        final_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    # structlog pipeline: processors hand off to ProcessorFormatter via
    # wrap_for_formatter instead of rendering directly.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    # ProcessorFormatter renders both structlog events and foreign stdlib records
    # through the same pipeline so every stdout line is identically formatted.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=final_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Third-party packages at WARNING; app.* at full log_level.
    root_logger.setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(log_level)
