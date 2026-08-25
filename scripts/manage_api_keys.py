#!/usr/bin/env python3
"""CLI for managing API keys — create, list, deactivate, delete.

Usage:
    uv run python scripts/manage_api_keys.py create --label "local-dev"
    uv run python scripts/manage_api_keys.py list
    uv run python scripts/manage_api_keys.py deactivate <prefix>
    uv run python scripts/manage_api_keys.py delete <prefix>

Environment variables (loaded from .env):
    DATABASE_URL    PostgreSQL connection string
    API_KEY_SALT    Salt for SHA-256 hashing (default: change-me-in-production)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.auth import API_KEY_PREFIX  # noqa: E402
from app.core.security import hash_with_salt  # noqa: E402
from app.db.models.api_key import ApiKey  # noqa: E402

load_dotenv()


def _session_factory() -> tuple[object, async_sessionmaker[AsyncSession]]:
    db_url = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )
    engine = create_async_engine(db_url, echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _salt() -> str:
    return os.getenv("API_KEY_SALT", "change-me-in-production")


def _new_key(salt: str) -> tuple[str, str, str]:
    """Return (raw_key, raw_prefix, hashed_key)."""
    raw = f"{API_KEY_PREFIX}_" + secrets.token_hex(32)
    prefix = raw[:19]
    return raw, prefix, hash_with_salt(raw, salt)


async def create(session_factory: async_sessionmaker[AsyncSession], label: str) -> None:
    raw, prefix, hashed = _new_key(_salt())
    async with session_factory() as session, session.begin():
        session.add(ApiKey(key_hash=hashed, raw_prefix=prefix, label=label, is_active=True))
    print(f"Created key for '{label}' (prefix {prefix}).")
    print(f"RAW KEY — save this now, it will never be shown again:\n\n  {raw}\n")


async def list_keys(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
        rows = result.scalars().all()
    if not rows:
        print("No API keys found.")
        return
    for row in rows:
        status = "active" if row.is_active else "inactive"
        last_used = row.last_used_at.isoformat() if row.last_used_at else "never"
        print(f"{row.raw_prefix}  {row.label:<24}  {status:<8}  last used: {last_used}")


async def set_active(
    session_factory: async_sessionmaker[AsyncSession], prefix: str, active: bool
) -> None:
    async with session_factory() as session, session.begin():
        result = await session.execute(
            update(ApiKey).where(ApiKey.raw_prefix == prefix).values(is_active=active)
        )
    if result.rowcount == 0:
        print(f"No key found with prefix {prefix}.")
    else:
        print(f"Key {prefix} {'activated' if active else 'deactivated'}.")


async def delete_key(session_factory: async_sessionmaker[AsyncSession], prefix: str) -> None:
    async with session_factory() as session, session.begin():
        result = await session.execute(delete(ApiKey).where(ApiKey.raw_prefix == prefix))
    if result.rowcount == 0:
        print(f"No key found with prefix {prefix}.")
    else:
        print(f"Key {prefix} deleted.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--label", required=True)

    sub.add_parser("list")

    p_deactivate = sub.add_parser("deactivate")
    p_deactivate.add_argument("prefix")

    p_reactivate = sub.add_parser("reactivate")
    p_reactivate.add_argument("prefix")

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("prefix")

    args = parser.parse_args()

    engine, factory = _session_factory()
    try:
        if args.command == "create":
            await create(factory, args.label)
        elif args.command == "list":
            await list_keys(factory)
        elif args.command == "deactivate":
            await set_active(factory, args.prefix, active=False)
        elif args.command == "reactivate":
            await set_active(factory, args.prefix, active=True)
        elif args.command == "delete":
            await delete_key(factory, args.prefix)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
