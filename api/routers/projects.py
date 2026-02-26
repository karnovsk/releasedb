from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import db, verify_token
from api.models.projects import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(tags=["projects"], dependencies=[Depends(verify_token)])


def _row_to_project(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(conn: asyncpg.Connection = Depends(db)):
    rows = await conn.fetch("SELECT * FROM projects ORDER BY name")
    return [_row_to_project(r) for r in rows]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM projects WHERE id=$1", project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return _row_to_project(row)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow(
        """
        INSERT INTO projects (name, related_project)
        VALUES ($1, $2)
        RETURNING *
        """,
        body.name,
        body.related_project,
    )
    return _row_to_project(row)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    conn: asyncpg.Connection = Depends(db),
):
    row = await conn.fetchrow("SELECT * FROM projects WHERE id=$1", project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_project(row)
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())
    updated = await conn.fetchrow(
        f"UPDATE projects SET {sets} WHERE id=$1 RETURNING *",
        project_id, *values,
    )
    return _row_to_project(updated)
