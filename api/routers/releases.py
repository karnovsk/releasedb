from __future__ import annotations

import json
from typing import Any, Literal, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import db, verify_token
from api.models.releases import (
    ApprovalCreate,
    ApprovalResponse,
    DeploymentResponse,
    DeploymentTrigger,
    LineageEdge,
    LineageResponse,
    PagedReleases,
    ReleaseCreate,
    ReleaseEventResponse,
    ReleaseResponse,
    ReleaseSummary,
    ReleaseUpdate,
    ValidationRunResponse,
    ValidationTrigger,
)

router = APIRouter(tags=["releases"], dependencies=[Depends(verify_token)])


async def _fetch_field_values(
    conn: asyncpg.Connection, release_id: UUID
) -> dict[str, str]:
    """Return {field_key: value} for a release, reading from the EAV table."""
    rows = await conn.fetch(
        """
        SELECT fd.field_key,
               COALESCE(rfv.value_text, rfv.value_number::text, rfv.value_date::text) AS val
        FROM release_field_values rfv
        JOIN release_type_field_defs fd ON fd.id = rfv.field_def_id
        WHERE rfv.release_id=$1
        """,
        release_id,
    )
    return {r["field_key"]: r["val"] for r in rows if r["val"] is not None}


async def _row_to_release(
    conn: asyncpg.Connection, row: asyncpg.Record
) -> dict[str, Any]:
    d = dict(row)
    d["field_values"] = await _fetch_field_values(conn, row["id"])
    dep_rows = await conn.fetch(
        "SELECT depends_on_id FROM release_dependencies WHERE release_id=$1",
        row["id"],
    )
    d["depends_on"] = [r["depends_on_id"] for r in dep_rows]
    return d


# ── Release CRUD ──────────────────────────────────────────────────────────────

@router.get("/releases", response_model=PagedReleases)
async def list_releases(
    team_slug: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    release_type_slug: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db),
):
    conditions: list[str] = []
    filter_params: list[Any] = []

    if team_slug:
        filter_params.append(team_slug)
        conditions.append(f"t.slug=${len(filter_params)}")
    if status:
        filter_params.append(status)
        conditions.append(f"r.status=${len(filter_params)}")
    if release_type_slug:
        filter_params.append(release_type_slug)
        conditions.append(f"rtc.slug=${len(filter_params)}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    join = """
        JOIN release_type_configs rtc ON rtc.id = r.release_type_config_id
        JOIN teams t ON t.id = r.owning_team_id
    """

    total: int = await conn.fetchval(
        f"SELECT COUNT(*) FROM releases r {join} {where}",
        *filter_params,
    )

    page_params = filter_params + [limit, offset]
    rows = await conn.fetch(
        f"""
        SELECT r.* FROM releases r {join}
        {where}
        ORDER BY r.created_at DESC
        LIMIT ${len(page_params) - 1} OFFSET ${len(page_params)}
        """,
        *page_params,
    )
    items = [await _row_to_release(conn, row) for row in rows]
    return PagedReleases(items=items, total=total, limit=limit, offset=offset)


@router.get("/releases/{release_id}", response_model=ReleaseResponse)
async def get_release(release_id: UUID, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT * FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")
    return await _row_to_release(conn, row)


@router.post("/releases", response_model=ReleaseResponse, status_code=201)
async def create_release(body: ReleaseCreate, conn: asyncpg.Connection = Depends(db)):
    async with conn.transaction():
        # Fetch release type config and its owning team
        rtc = await conn.fetchrow(
            "SELECT * FROM release_type_configs WHERE id=$1",
            body.release_type_config_id,
        )
        if not rtc:
            raise HTTPException(404, "Release type config not found")

        # Fetch all field defs for this release type
        field_defs = await conn.fetch(
            "SELECT * FROM release_type_field_defs WHERE release_type_config_id=$1",
            rtc["id"],
        )

        # Validate required fields
        missing = [
            fd["field_key"]
            for fd in field_defs
            if fd["is_required"] and fd["field_key"] not in body.field_values
        ]
        if missing:
            raise HTTPException(
                422,
                f"Missing required field(s): {missing}",
            )

        # Insert the release
        row = await conn.fetchrow(
            """
            INSERT INTO releases
              (release_type_config_id, owning_team_id, release_name, version,
               target_date, notes, created_by, project_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            rtc["id"],
            rtc["team_id"],
            body.release_name,
            body.version,
            body.target_date,
            body.notes,
            body.created_by,
            body.project_id,
        )

        # Insert field values
        fd_map = {fd["field_key"]: fd for fd in field_defs}
        for key, value in body.field_values.items():
            fd = fd_map.get(key)
            if not fd:
                continue  # unknown field key — skip silently
            fd_type = fd["field_type"]
            await conn.execute(
                """
                INSERT INTO release_field_values
                  (release_id, field_def_id, value_text, value_number, value_date)
                VALUES ($1, $2, $3, $4, $5)
                """,
                row["id"],
                fd["id"],
                value if fd_type in ("string", "enum", "bool", "file") else None,
                float(value) if fd_type == "number" else None,
                value if fd_type == "date" else None,
            )

        # Insert dependency edges
        for parent_id in body.depends_on:
            parent = await conn.fetchrow(
                "SELECT id FROM releases WHERE id=$1", parent_id
            )
            if not parent:
                raise HTTPException(404, f"Dependency release not found: {parent_id}")
            await conn.execute(
                "INSERT INTO release_dependencies (release_id, depends_on_id) VALUES ($1, $2)",
                row["id"],
                parent_id,
            )

        # Append release_created event
        await conn.execute(
            """
            INSERT INTO release_events (release_id, event_type, actor_identity, payload)
            VALUES ($1, 'release_created', $2, $3)
            """,
            row["id"],
            body.created_by,
            json.dumps({"release_name": body.release_name, "version": body.version}),
        )

    return await _row_to_release(conn, row)


@router.patch("/releases/{release_id}", response_model=ReleaseResponse)
async def update_release(
    release_id: UUID, body: ReleaseUpdate, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT * FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await _row_to_release(conn, row)

    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"UPDATE releases SET {sets} WHERE id=$1 RETURNING *",
        release_id, *updates.values(),
    )

    if "status" in updates:
        await conn.execute(
            """
            INSERT INTO release_events (release_id, event_type, payload)
            VALUES ($1, 'status_changed', $2)
            """,
            release_id,
            json.dumps({"from": row["status"], "to": updates["status"]}),
        )

    return await _row_to_release(conn, updated)


# ── Validation ────────────────────────────────────────────────────────────────

@router.post(
    "/releases/{release_id}/validate",
    response_model=ValidationRunResponse,
    status_code=201,
)
async def trigger_validation(
    release_id: UUID,
    body: ValidationTrigger,
    conn: asyncpg.Connection = Depends(db),
):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")

    env = await conn.fetchrow(
        "SELECT id FROM environments WHERE slug=$1", body.environment
    )
    if not env:
        raise HTTPException(404, f"Environment '{body.environment}' not found")

    run = await conn.fetchrow(
        """
        INSERT INTO validation_runs
          (release_id, environment_id, triggered_by, trigger_type)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        release_id,
        env["id"],
        body.triggered_by,
        body.trigger_type,
    )
    return dict(run)


@router.get(
    "/releases/{release_id}/validation-runs",
    response_model=list[ValidationRunResponse],
)
async def list_validation_runs(
    release_id: UUID, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")
    runs = await conn.fetch(
        "SELECT * FROM validation_runs WHERE release_id=$1 ORDER BY started_at DESC NULLS FIRST",
        release_id,
    )
    return [dict(r) for r in runs]


# ── Approvals ─────────────────────────────────────────────────────────────────

@router.get("/releases/{release_id}/approvals", response_model=list[ApprovalResponse])
async def list_approvals(release_id: UUID, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")
    rows = await conn.fetch(
        "SELECT * FROM approvals WHERE release_id=$1 ORDER BY decided_at DESC",
        release_id,
    )
    return [dict(r) for r in rows]


@router.post(
    "/releases/{release_id}/approvals",
    response_model=ApprovalResponse,
    status_code=201,
)
async def submit_approval(
    release_id: UUID,
    body: ApprovalCreate,
    conn: asyncpg.Connection = Depends(db),
):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")

    approval = await conn.fetchrow(
        """
        INSERT INTO approvals
          (release_id, environment_id, approving_team_id, approver_identity,
           decision, comment)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        release_id,
        body.environment_id,
        body.approving_team_id,
        body.approver_identity,
        body.decision,
        body.comment,
    )

    await conn.execute(
        """
        INSERT INTO release_events (release_id, event_type, actor_identity, payload)
        VALUES ($1, 'approval_submitted', $2, $3)
        """,
        release_id,
        body.approver_identity,
        json.dumps({"decision": body.decision, "environment_id": str(body.environment_id)}),
    )

    return dict(approval)


# ── Deployments ───────────────────────────────────────────────────────────────

@router.post(
    "/releases/{release_id}/deploy",
    response_model=DeploymentResponse,
    status_code=201,
)
async def trigger_deployment(
    release_id: UUID,
    body: DeploymentTrigger,
    conn: asyncpg.Connection = Depends(db),
):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")

    deployment = await conn.fetchrow(
        """
        INSERT INTO deployments
          (release_id, environment_id, artifact_id, strategy, deployed_by, rollback_of)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        release_id,
        body.environment_id,
        body.artifact_id,
        body.strategy,
        body.deployed_by,
        body.rollback_of,
    )

    await conn.execute(
        """
        INSERT INTO release_events (release_id, event_type, actor_identity, payload)
        VALUES ($1, 'deployment_triggered', $2, $3)
        """,
        release_id,
        body.deployed_by,
        json.dumps({
            "environment_id": str(body.environment_id),
            "artifact_id": str(body.artifact_id),
            "strategy": body.strategy,
        }),
    )

    return dict(deployment)


# ── Events ────────────────────────────────────────────────────────────────────

@router.get(
    "/releases/{release_id}/events",
    response_model=list[ReleaseEventResponse],
)
async def list_release_events(
    release_id: UUID, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")
    events = await conn.fetch(
        """
        SELECT * FROM release_events
        WHERE release_id=$1
        ORDER BY occurred_at ASC
        """,
        release_id,
    )
    result = []
    for r in events:
        d = dict(r)
        if isinstance(d.get("payload"), str):
            d["payload"] = json.loads(d["payload"])
        result.append(d)
    return result


# ── Lineage ───────────────────────────────────────────────────────────────────

@router.get("/releases/{release_id}/lineage", response_model=LineageResponse)
async def get_release_lineage(
    release_id: UUID,
    direction: Literal["ancestors", "descendants", "both"] = Query("both"),
    conn: asyncpg.Connection = Depends(db),
):
    row = await conn.fetchrow("SELECT id FROM releases WHERE id=$1", release_id)
    if not row:
        raise HTTPException(404, "Release not found")

    # Ancestors: follow depends_on_id upward from the given release.
    # UNION (not UNION ALL) deduplicates, naturally terminating any cycles.
    _ANCESTOR_CTE = """
        WITH RECURSIVE ancestors AS (
            SELECT release_id, depends_on_id
            FROM release_dependencies
            WHERE release_id = $1
          UNION
            SELECT rd.release_id, rd.depends_on_id
            FROM release_dependencies rd
            JOIN ancestors a ON rd.release_id = a.depends_on_id
        )
        SELECT release_id, depends_on_id FROM ancestors
    """

    # Descendants: find releases that depend on the given release, then follow forward.
    _DESCENDANT_CTE = """
        WITH RECURSIVE descendants AS (
            SELECT release_id, depends_on_id
            FROM release_dependencies
            WHERE depends_on_id = $1
          UNION
            SELECT rd.release_id, rd.depends_on_id
            FROM release_dependencies rd
            JOIN descendants d ON rd.depends_on_id = d.release_id
        )
        SELECT release_id, depends_on_id FROM descendants
    """

    edge_rows = []
    if direction in ("ancestors", "both"):
        edge_rows += list(await conn.fetch(_ANCESTOR_CTE, release_id))
    if direction in ("descendants", "both"):
        edge_rows += list(await conn.fetch(_DESCENDANT_CTE, release_id))

    # Deduplicate edges (both CTEs may return overlapping rows for the given node).
    seen: set[tuple] = set()
    unique_edges = []
    for r in edge_rows:
        key = (r["release_id"], r["depends_on_id"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(r)

    node_ids = {release_id}
    for r in unique_edges:
        node_ids.add(r["release_id"])
        node_ids.add(r["depends_on_id"])

    node_rows = await conn.fetch(
        "SELECT id, release_name, version, status FROM releases WHERE id = ANY($1)",
        list(node_ids),
    )

    return LineageResponse(
        nodes=[ReleaseSummary(**dict(r)) for r in node_rows],
        edges=[
            LineageEdge(
                from_release_id=r["release_id"],
                to_release_id=r["depends_on_id"],
            )
            for r in unique_edges
        ],
    )
