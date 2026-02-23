from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import db, verify_token
from api.models.artifacts import (
    ArtifactCreate,
    ArtifactFileResponse,
    ArtifactResponse,
)

router = APIRouter(tags=["artifacts"], dependencies=[Depends(verify_token)])


async def _fetch_files(conn: asyncpg.Connection, artifact_id: UUID) -> list[dict]:
    rows = await conn.fetch(
        "SELECT * FROM artifact_files WHERE artifact_id=$1 ORDER BY filename",
        artifact_id,
    )
    return [dict(r) for r in rows]


async def _row_to_artifact(
    conn: asyncpg.Connection, row: asyncpg.Record
) -> dict[str, Any]:
    d = dict(row)
    d["files"] = await _fetch_files(conn, row["id"])
    return d


@router.get("/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts(
    release_id: Optional[UUID] = Query(None),
    tool_name: Optional[str] = Query(None),
    git_sha: Optional[str] = Query(None),
    conn: asyncpg.Connection = Depends(db),
):
    conditions: list[str] = []
    params: list[Any] = []

    if release_id:
        params.append(release_id)
        conditions.append(f"a.release_id=${len(params)}")
    if git_sha:
        params.append(git_sha)
        conditions.append(f"a.git_commit_sha=${len(params)}")
    if tool_name:
        params.append(tool_name)
        conditions.append(f"EXISTS (SELECT 1 FROM artifact_tools at2 JOIN tools tl ON tl.id=at2.tool_id WHERE at2.artifact_id=a.id AND tl.name=${len(params)})")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await conn.fetch(
        f"SELECT a.* FROM artifacts a {where} ORDER BY a.created_at DESC",
        *params,
    )
    result = []
    for row in rows:
        result.append(await _row_to_artifact(conn, row))
    return result


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: UUID, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM artifacts WHERE id=$1", artifact_id)
    if not row:
        raise HTTPException(404, "Artifact not found")
    return await _row_to_artifact(conn, row)


@router.post("/artifacts", response_model=ArtifactResponse, status_code=201)
async def submit_artifact(body: ArtifactCreate, conn: asyncpg.Connection = Depends(db)):
    async with conn.transaction():
        # Fetch the release to get release_type_config_id
        release = await conn.fetchrow(
            "SELECT id, release_type_config_id FROM releases WHERE id=$1",
            body.release_id,
        )
        if not release:
            raise HTTPException(404, "Release not found")

        built_at = datetime.fromisoformat(body.built_at)

        # Insert artifact
        row = await conn.fetchrow(
            """
            INSERT INTO artifacts
              (release_id, release_type_config_id, version, git_commit_sha,
               git_branch, build_id, build_url, manifest_digest, sbom, labels, built_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING *
            """,
            release["id"],
            release["release_type_config_id"],
            body.version,
            body.git_commit_sha,
            body.git_branch,
            body.build_id,
            body.build_url,
            body.manifest_digest,
            body.sbom,
            body.labels,
            built_at,
        )

        # Insert files
        for f in body.files:
            await conn.execute(
                """
                INSERT INTO artifact_files
                  (artifact_id, filename, digest, file_role, storage_uri, media_type, size_bytes)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                row["id"],
                f.filename,
                f.digest,
                f.file_role,
                f.storage_uri,
                f.media_type,
                f.size_bytes,
            )

        # Insert tools (look up each by name)
        for t in body.tools:
            tool = await conn.fetchrow(
                "SELECT id FROM tools WHERE name=$1", t.tool_name
            )
            if not tool:
                raise HTTPException(404, f"Tool '{t.tool_name}' not found in tools registry")
            await conn.execute(
                """
                INSERT INTO artifact_tools
                  (artifact_id, tool_id, tool_version, git_commit_sha,
                   git_branch, runner_image, invocation_flags, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                ON CONFLICT (artifact_id, tool_id) DO NOTHING
                """,
                row["id"],
                tool["id"],
                t.tool_version,
                t.git_commit_sha,
                t.git_branch,
                t.runner_image,
                t.invocation_flags,
                t.metadata,
            )

    return await _row_to_artifact(conn, row)


@router.get(
    "/artifacts/{artifact_id}/files",
    response_model=list[ArtifactFileResponse],
)
async def list_artifact_files(
    artifact_id: UUID, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT id FROM artifacts WHERE id=$1", artifact_id)
    if not row:
        raise HTTPException(404, "Artifact not found")
    return await _fetch_files(conn, artifact_id)


@router.post(
    "/artifacts/{artifact_id}/files",
    response_model=ArtifactFileResponse,
    status_code=201,
)
async def add_artifact_file(
    artifact_id: UUID,
    body: dict,
    conn: asyncpg.Connection = Depends(db),
):
    row = await conn.fetchrow("SELECT id FROM artifacts WHERE id=$1", artifact_id)
    if not row:
        raise HTTPException(404, "Artifact not found")
    file_row = await conn.fetchrow(
        """
        INSERT INTO artifact_files
          (artifact_id, filename, digest, file_role, storage_uri, media_type, size_bytes)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        RETURNING *
        """,
        artifact_id,
        body.get("filename"),
        body.get("digest"),
        body.get("file_role"),
        body.get("storage_uri"),
        body.get("media_type"),
        body.get("size_bytes"),
    )
    return dict(file_row)


@router.get("/artifacts/{artifact_id}/tools")
async def list_artifact_tools(
    artifact_id: UUID, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT id FROM artifacts WHERE id=$1", artifact_id)
    if not row:
        raise HTTPException(404, "Artifact not found")
    rows = await conn.fetch(
        """
        SELECT at.*, tl.name AS tool_name, tl.source
        FROM artifact_tools at
        JOIN tools tl ON tl.id = at.tool_id
        WHERE at.artifact_id=$1
        ORDER BY tl.name
        """,
        artifact_id,
    )
    return [dict(r) for r in rows]
