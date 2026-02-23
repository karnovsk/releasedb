from __future__ import annotations

import json
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import db, verify_token
from api.models.teams import EnvironmentCreate, EnvironmentResponse, EnvironmentUpdate

router = APIRouter(tags=["environments"], dependencies=[Depends(verify_token)])


def _row_to_env(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("config"), str):
        d["config"] = json.loads(d["config"])
    return d


@router.get("/environments", response_model=list[EnvironmentResponse])
async def list_environments(conn: asyncpg.Connection = Depends(db)):
    rows = await conn.fetch("SELECT * FROM environments ORDER BY tier, slug")
    return [_row_to_env(r) for r in rows]


@router.get("/environments/{slug}", response_model=EnvironmentResponse)
async def get_environment(slug: str, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM environments WHERE slug=$1", slug)
    if not row:
        raise HTTPException(404, "Environment not found")
    return _row_to_env(row)


@router.post("/environments", response_model=EnvironmentResponse, status_code=201)
async def create_environment(body: EnvironmentCreate, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow(
        """
        INSERT INTO environments (slug, name, tier, requires_approval, config)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        body.slug,
        body.name,
        body.tier,
        body.requires_approval,
        json.dumps(body.config) if body.config else None,
    )
    return _row_to_env(row)


@router.patch("/environments/{slug}", response_model=EnvironmentResponse)
async def update_environment(
    slug: str, body: EnvironmentUpdate, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT * FROM environments WHERE slug=$1", slug)
    if not row:
        raise HTTPException(404, "Environment not found")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_env(row)
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())
    if "config" in updates:
        idx = list(updates.keys()).index("config")
        values[idx] = json.dumps(values[idx]) if values[idx] else None
    updated = await conn.fetchrow(
        f"UPDATE environments SET {sets} WHERE slug=$1 RETURNING *",
        slug, *values,
    )
    return _row_to_env(updated)
