"""
api.database
~~~~~~~~~~~~
asyncpg connection pool management.
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def init_pool(database_url: Optional[str] = None) -> None:
    global _pool
    url = database_url or os.environ["DATABASE_URL"]
    _pool = await asyncpg.create_pool(url, min_size=2, max_size=10)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool
