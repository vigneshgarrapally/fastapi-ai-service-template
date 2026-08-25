"""RabbitMQ connection factory and topology declaration.

Topology — AI job queue
  Exchange:   ai.jobs        direct, durable
  Queue:      ai.jobs.q      durable, dead-letters -> ai.jobs.dlx
  Dead exch:  ai.jobs.dlx    fanout, durable
  Dead queue: ai.jobs.dlq    durable, bound to ai.jobs.dlx
  Routing key: submit

The API process calls ``connect()`` at startup (publisher, robust connection).
The worker process calls ``connect_robust()`` (auto-reconnects on restart) and
declares the same topology idempotently — safe to call from both sides.

To add a second queue for a different job type, copy this module's pattern
(exchange + queue + DLX + DLQ) rather than overloading this one queue with
multiple message shapes.
"""

from __future__ import annotations

import json
from typing import Any

import aio_pika
import structlog
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue, AbstractRobustConnection

logger = structlog.get_logger(__name__)

EXCHANGE_NAME = "ai.jobs"
DEAD_EXCHANGE_NAME = "ai.jobs.dlx"
QUEUE_NAME = "ai.jobs.q"
DEAD_QUEUE_NAME = "ai.jobs.dlq"
ROUTING_KEY = "submit"

SCHEMA_VERSION = 1

_connection: AbstractRobustConnection | None = None
_exchange: AbstractExchange | None = None


def get_publisher_connection_status() -> dict[str, bool]:
    """Return whether the API-process publisher connection is open.

    Lets callers (e.g. the health/readiness check) verify connectivity without
    reaching into this module's private connection globals directly.
    """
    return {"job_publisher": _connection is not None and not _connection.is_closed}


async def connect(url: str) -> None:
    """Connect to RabbitMQ for the API process (publisher).

    Uses a robust connection so the channel and exchange handle automatically
    recover after a broker restart. Called once at FastAPI startup.
    """
    global _connection, _exchange
    logger.info("infra.rabbitmq.connect.start")
    try:
        _connection = await aio_pika.connect_robust(url)
        channel = await _connection.channel()
        _exchange, _ = await declare_topology(channel)
        logger.info("infra.rabbitmq.connect.success", exchange=EXCHANGE_NAME)
    except Exception as exc:
        logger.error("infra.rabbitmq.connect.failed", error=str(exc))
        raise


async def connect_robust(url: str) -> AbstractRobustConnection:
    """Connect to RabbitMQ for the worker process (consumer).

    Returns a robust connection that auto-reconnects on broker restart without
    restarting the worker process.
    """
    return await aio_pika.connect_robust(url)


async def declare_topology(
    channel: AbstractChannel,
) -> tuple[AbstractExchange, AbstractQueue]:
    """Idempotently declare exchange, queue, and dead-letter bindings.

    Safe to call on both API startup and worker startup.
    """
    dead_exchange = await channel.declare_exchange(
        DEAD_EXCHANGE_NAME,
        type=aio_pika.ExchangeType.FANOUT,
        durable=True,
    )
    dead_queue = await channel.declare_queue(DEAD_QUEUE_NAME, durable=True)
    await dead_queue.bind(dead_exchange)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        type=aio_pika.ExchangeType.DIRECT,
        durable=True,
    )
    queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={"x-dead-letter-exchange": DEAD_EXCHANGE_NAME},
    )
    await queue.bind(exchange, routing_key=ROUTING_KEY)

    return exchange, queue


async def publish_job(message: dict[str, Any], environment: str) -> None:
    """Publish a job message to the ``ai.jobs`` exchange.

    Called by the API after writing the job row to Postgres with status=queued.
    Uses PERSISTENT delivery mode so messages survive a broker restart.
    """
    if _exchange is None:
        raise RuntimeError("RabbitMQ not connected — call connect() at startup")

    enriched = {**message, "environment": environment, "schema_version": SCHEMA_VERSION}
    body = json.dumps(enriched).encode()
    await _exchange.publish(
        aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=ROUTING_KEY,
    )
    logger.info("infra.rabbitmq.publish.success", job_id=message.get("job_id"))


async def disconnect() -> None:
    """Close the API-process RabbitMQ connection. Called at FastAPI shutdown."""
    global _connection, _exchange
    if _connection is not None:
        await _connection.close()
        _connection = None
        _exchange = None
        logger.info("infra.rabbitmq.disconnect.success")
