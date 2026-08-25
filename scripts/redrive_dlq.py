#!/usr/bin/env python3
"""Redrive messages from the ai.jobs dead-letter queue back to ai.jobs.

Use after fixing whatever caused a batch of jobs to fail permanently (a bug in
the worker, a bad upstream dependency) — republishes each dead-lettered message
to the main queue for reprocessing, then acks it off the DLQ.

Usage:
    uv run python scripts/redrive_dlq.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import aio_pika
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.rabbitmq import (  # noqa: E402
    DEAD_QUEUE_NAME,
    EXCHANGE_NAME,
    ROUTING_KEY,
)

load_dotenv()


async def redrive(limit: int | None, dry_run: bool) -> None:
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    connection = await aio_pika.connect_robust(url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(DEAD_QUEUE_NAME, durable=True, passive=True)
        exchange = await channel.get_exchange(EXCHANGE_NAME)

        redriven = 0
        while limit is None or redriven < limit:
            message = await queue.get(fail=False, no_ack=False)
            if message is None:
                break
            if dry_run:
                print(f"[dry-run] would redrive: {message.body[:200]!r}")
                await message.reject(requeue=True)
                break  # dry-run only ever peeks the first message
            await exchange.publish(
                aio_pika.Message(body=message.body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=ROUTING_KEY,
            )
            await message.ack()
            redriven += 1

        print(f"Redriven: {redriven}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(redrive(args.limit, args.dry_run))
