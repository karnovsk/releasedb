from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.dependencies import db, verify_token
from api.models.releases import ValidationRunResponse

router = APIRouter(tags=["validation-runs"], dependencies=[Depends(verify_token)])


class ValidationRunUpdate(BaseModel):
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@router.get("/validation-runs/{run_id}", response_model=ValidationRunResponse)
async def get_validation_run(run_id: UUID, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM validation_runs WHERE id=$1", run_id)
    if not row:
        raise HTTPException(404, "Validation run not found")
    return dict(row)


@router.patch("/validation-runs/{run_id}", response_model=ValidationRunResponse)
async def update_validation_run(
    run_id: UUID, body: ValidationRunUpdate, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT * FROM validation_runs WHERE id=$1", run_id)
    if not row:
        raise HTTPException(404, "Validation run not found")

    updates = body.model_dump(exclude_none=True)
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"UPDATE validation_runs SET {sets} WHERE id=$1 RETURNING *",
        run_id, *updates.values(),
    )
    return dict(updated)
