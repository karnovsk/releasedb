"""
api.dependencies
~~~~~~~~~~~~~~~~
FastAPI dependency functions: auth and DB connection.
"""

from __future__ import annotations

import os

import asyncpg
from fastapi import Depends, Header, HTTPException

from api.database import get_pool


async def verify_token(authorization: str = Header(...)) -> None:
    """Validate the Bearer token against RELEASEDB_API_TOKEN env var."""
    expected = os.environ.get("RELEASEDB_API_TOKEN", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


async def db(pool: asyncpg.Pool = Depends(get_pool)) -> asyncpg.Connection:
    async with pool.acquire() as conn:
        yield conn
