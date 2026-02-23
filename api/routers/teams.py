from __future__ import annotations

import json
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import db, verify_token
from api.models.teams import TeamCreate, TeamResponse, TeamUpdate

router = APIRouter(tags=["teams"], dependencies=[Depends(verify_token)])


def _row_to_team(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        d["metadata"] = json.loads(d["metadata"])
    return d


@router.get("/teams", response_model=list[TeamResponse])
async def list_teams(conn: asyncpg.Connection = Depends(db)):
    rows = await conn.fetch("SELECT * FROM teams ORDER BY name")
    return [_row_to_team(r) for r in rows]


@router.get("/teams/{slug}", response_model=TeamResponse)
async def get_team(slug: str, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM teams WHERE slug=$1", slug)
    if not row:
        raise HTTPException(404, "Team not found")
    return _row_to_team(row)


@router.post("/teams", response_model=TeamResponse, status_code=201)
async def create_team(body: TeamCreate, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow(
        """
        INSERT INTO teams (slug, name, contact_email, metadata)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        body.slug,
        body.name,
        body.contact_email,
        json.dumps(body.metadata) if body.metadata else None,
    )
    return _row_to_team(row)


@router.patch("/teams/{slug}", response_model=TeamResponse)
async def update_team(slug: str, body: TeamUpdate, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM teams WHERE slug=$1", slug)
    if not row:
        raise HTTPException(404, "Team not found")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_team(row)
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())
    if "metadata" in updates:
        idx = list(updates.keys()).index("metadata")
        values[idx] = json.dumps(values[idx]) if values[idx] else None
    updated = await conn.fetchrow(
        f"UPDATE teams SET {sets} WHERE slug=$1 RETURNING *",
        slug, *values,
    )
    return _row_to_team(updated)
