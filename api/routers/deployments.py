from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import db, verify_token
from api.models.artifacts import DeploymentUpdate
from api.models.releases import DeploymentResponse

router = APIRouter(tags=["deployments"], dependencies=[Depends(verify_token)])


@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow(
        "SELECT * FROM deployments WHERE id=$1", deployment_id
    )
    if not row:
        raise HTTPException(404, "Deployment not found")
    return dict(row)


@router.patch("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: UUID,
    body: DeploymentUpdate,
    conn: asyncpg.Connection = Depends(db),
):
    """
    Called by Jenkins or other CI/CD systems as a post-deploy callback
    to update the deployment status.
    """
    row = await conn.fetchrow(
        "SELECT * FROM deployments WHERE id=$1", deployment_id
    )
    if not row:
        raise HTTPException(404, "Deployment not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return dict(row)

    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"UPDATE deployments SET {sets} WHERE id=$1 RETURNING *",
        deployment_id, *updates.values(),
    )
    return dict(updated)
