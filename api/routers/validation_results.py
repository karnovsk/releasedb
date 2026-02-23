from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import db, verify_token
from api.models.artifacts import ValidationResultResponse, ValidationResultUpdate

router = APIRouter(tags=["validation-results"], dependencies=[Depends(verify_token)])


@router.get("/validation-results/{result_id}", response_model=ValidationResultResponse)
async def get_validation_result(
    result_id: UUID, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow(
        "SELECT * FROM validation_results WHERE id=$1", result_id
    )
    if not row:
        raise HTTPException(404, "Validation result not found")
    return dict(row)


@router.patch(
    "/validation-results/{result_id}", response_model=ValidationResultResponse
)
async def update_validation_result(
    result_id: UUID,
    body: ValidationResultUpdate,
    conn: asyncpg.Connection = Depends(db),
):
    """
    Called by validator scripts (via Reporter) to write back check results.
    Also called by the runner infrastructure to record timeouts, exit codes, etc.
    """
    row = await conn.fetchrow(
        "SELECT * FROM validation_results WHERE id=$1", result_id
    )
    if not row:
        raise HTTPException(404, "Validation result not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return dict(row)

    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"UPDATE validation_results SET {sets} WHERE id=$1 RETURNING *",
        result_id, *updates.values(),
    )
    return dict(updated)
