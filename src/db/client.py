"""Async PostgreSQL connection pool and query helpers."""

import os
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    """Get or create the global async connection pool."""
    global _pool
    if _pool is None:
        uri = os.environ["DATABASE_URI"]
        _pool = AsyncConnectionPool(
            conninfo=uri,
            min_size=2,
            max_size=20,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    """Close the global pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def execute(query: str, *args: Any) -> None:
    """Execute a query without returning results."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(query, args)


async def fetch_one(query: str, *args: Any) -> dict[str, Any] | None:
    """Execute a query and return a single row."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(query, args)
        return await cursor.fetchone()


async def fetch_all(query: str, *args: Any) -> list[dict[str, Any]]:
    """Execute a query and return all rows."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(query, args)
        return await cursor.fetchall()


@asynccontextmanager
async def transaction():
    """Context manager for a database transaction."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute("BEGIN")
        try:
            yield conn
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise
