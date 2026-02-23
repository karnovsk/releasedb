from __future__ import annotations

from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import db, verify_token
from api.models.releases import (
    FieldDefCreate,
    FieldDefResponse,
    FieldDefUpdate,
    ReleaseTypeCreate,
    ReleaseTypeResponse,
    ReleaseTypeUpdate,
    ValidationDefCreate,
    ValidationDefResponse,
    ValidationDefUpdate,
)

router = APIRouter(tags=["release-types"], dependencies=[Depends(verify_token)])


# ── Release types ─────────────────────────────────────────────────────────────

@router.get("/release-types", response_model=list[ReleaseTypeResponse])
async def list_release_types(
    team_slug: Optional[str] = Query(None),
    conn: asyncpg.Connection = Depends(db),
):
    if team_slug:
        rows = await conn.fetch(
            """
            SELECT rtc.* FROM release_type_configs rtc
            JOIN teams t ON t.id = rtc.team_id
            WHERE t.slug=$1
            ORDER BY rtc.slug
            """,
            team_slug,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM release_type_configs ORDER BY slug"
        )
    return [dict(r) for r in rows]


@router.get("/release-types/{slug}", response_model=ReleaseTypeResponse)
async def get_release_type(slug: str, conn: asyncpg.Connection = Depends(db)):
    row = await conn.fetchrow(
        "SELECT * FROM release_type_configs WHERE slug=$1", slug
    )
    if not row:
        raise HTTPException(404, "Release type not found")
    return dict(row)


@router.post("/release-types", response_model=ReleaseTypeResponse, status_code=201)
async def create_release_type(
    body: ReleaseTypeCreate, conn: asyncpg.Connection = Depends(db)
):
    team = await conn.fetchrow("SELECT id FROM teams WHERE slug=$1", body.team_slug)
    if not team:
        raise HTTPException(404, f"Team '{body.team_slug}' not found")

    row = await conn.fetchrow(
        """
        INSERT INTO release_type_configs
          (team_id, slug, display_name, description, artifact_cardinality,
           artifact_naming_regex, allowed_file_types, requires_approval, version_scheme)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        team["id"],
        body.slug,
        body.display_name,
        body.description,
        body.artifact_cardinality,
        body.artifact_naming_regex,
        body.allowed_file_types,
        body.requires_approval,
        body.version_scheme,
    )
    return dict(row)


@router.patch("/release-types/{slug}", response_model=ReleaseTypeResponse)
async def update_release_type(
    slug: str, body: ReleaseTypeUpdate, conn: asyncpg.Connection = Depends(db)
):
    row = await conn.fetchrow(
        "SELECT * FROM release_type_configs WHERE slug=$1", slug
    )
    if not row:
        raise HTTPException(404, "Release type not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return dict(row)

    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"UPDATE release_type_configs SET {sets} WHERE slug=$1 RETURNING *",
        slug, *updates.values(),
    )
    return dict(updated)


# ── Field definitions ─────────────────────────────────────────────────────────

@router.get("/release-types/{slug}/fields", response_model=list[FieldDefResponse])
async def list_field_defs(slug: str, conn: asyncpg.Connection = Depends(db)):
    rt = await conn.fetchrow(
        "SELECT id FROM release_type_configs WHERE slug=$1", slug
    )
    if not rt:
        raise HTTPException(404, "Release type not found")
    rows = await conn.fetch(
        """
        SELECT * FROM release_type_field_defs
        WHERE release_type_config_id=$1
        ORDER BY display_order, field_key
        """,
        rt["id"],
    )
    return [dict(r) for r in rows]


@router.post(
    "/release-types/{slug}/fields",
    response_model=FieldDefResponse,
    status_code=201,
)
async def create_field_def(
    slug: str, body: FieldDefCreate, conn: asyncpg.Connection = Depends(db)
):
    rt = await conn.fetchrow(
        "SELECT id FROM release_type_configs WHERE slug=$1", slug
    )
    if not rt:
        raise HTTPException(404, "Release type not found")
    row = await conn.fetchrow(
        """
        INSERT INTO release_type_field_defs
          (release_type_config_id, field_key, label, field_type,
           is_required, enum_options, validation_regex, default_value, display_order)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        rt["id"],
        body.field_key,
        body.label,
        body.field_type,
        body.is_required,
        body.enum_options,
        body.validation_regex,
        body.default_value,
        body.display_order,
    )
    return dict(row)


@router.patch(
    "/release-types/{slug}/fields/{field_key}",
    response_model=FieldDefResponse,
)
async def update_field_def(
    slug: str,
    field_key: str,
    body: FieldDefUpdate,
    conn: asyncpg.Connection = Depends(db),
):
    rt = await conn.fetchrow(
        "SELECT id FROM release_type_configs WHERE slug=$1", slug
    )
    if not rt:
        raise HTTPException(404, "Release type not found")

    row = await conn.fetchrow(
        """
        SELECT * FROM release_type_field_defs
        WHERE release_type_config_id=$1 AND field_key=$2
        """,
        rt["id"], field_key,
    )
    if not row:
        raise HTTPException(404, f"Field '{field_key}' not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return dict(row)

    sets = ", ".join(f"{k}=${i+3}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"""
        UPDATE release_type_field_defs SET {sets}
        WHERE release_type_config_id=$1 AND field_key=$2
        RETURNING *
        """,
        rt["id"], field_key, *updates.values(),
    )
    return dict(updated)


# ── Validation definitions ────────────────────────────────────────────────────

@router.get(
    "/release-types/{slug}/validations",
    response_model=list[ValidationDefResponse],
)
async def list_validation_defs(slug: str, conn: asyncpg.Connection = Depends(db)):
    rt = await conn.fetchrow(
        "SELECT id FROM release_type_configs WHERE slug=$1", slug
    )
    if not rt:
        raise HTTPException(404, "Release type not found")
    rows = await conn.fetch(
        """
        SELECT * FROM validation_definitions
        WHERE release_type_config_id=$1
        ORDER BY run_order, name
        """,
        rt["id"],
    )
    return [dict(r) for r in rows]


@router.post(
    "/release-types/{slug}/validations",
    response_model=ValidationDefResponse,
    status_code=201,
)
async def create_validation_def(
    slug: str, body: ValidationDefCreate, conn: asyncpg.Connection = Depends(db)
):
    rt = await conn.fetchrow(
        "SELECT id FROM release_type_configs WHERE slug=$1", slug
    )
    if not rt:
        raise HTTPException(404, "Release type not found")

    env_id = None
    if body.environment_slug:
        env = await conn.fetchrow(
            "SELECT id FROM environments WHERE slug=$1", body.environment_slug
        )
        if not env:
            raise HTTPException(404, f"Environment '{body.environment_slug}' not found")
        env_id = env["id"]

    row = await conn.fetchrow(
        """
        INSERT INTO validation_definitions
          (release_type_config_id, environment_id, name, description, runner_type,
           script_body, script_url, script_checksum, runner_image, timeout_seconds,
           env_vars, is_blocking, on_failure, applies_to, run_order)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        RETURNING *
        """,
        rt["id"],
        env_id,
        body.name,
        body.description,
        body.runner_type,
        body.script_body,
        body.script_url,
        body.script_checksum,
        body.runner_image,
        body.timeout_seconds,
        body.env_vars,
        body.is_blocking,
        body.on_failure,
        body.applies_to,
        body.run_order,
    )
    return dict(row)


@router.patch(
    "/release-types/{slug}/validations/{name}",
    response_model=ValidationDefResponse,
)
async def update_validation_def(
    slug: str,
    name: str,
    body: ValidationDefUpdate,
    conn: asyncpg.Connection = Depends(db),
):
    rt = await conn.fetchrow(
        "SELECT id FROM release_type_configs WHERE slug=$1", slug
    )
    if not rt:
        raise HTTPException(404, "Release type not found")

    row = await conn.fetchrow(
        """
        SELECT * FROM validation_definitions
        WHERE release_type_config_id=$1 AND name=$2
        """,
        rt["id"], name,
    )
    if not row:
        raise HTTPException(404, f"Validation '{name}' not found")

    updates: dict[str, Any] = body.model_dump(exclude_none=True)

    # Resolve environment_slug → environment_id if provided
    if "environment_slug" in updates:
        env_slug = updates.pop("environment_slug")
        if env_slug:
            env = await conn.fetchrow(
                "SELECT id FROM environments WHERE slug=$1", env_slug
            )
            if not env:
                raise HTTPException(404, f"Environment '{env_slug}' not found")
            updates["environment_id"] = env["id"]
        else:
            updates["environment_id"] = None

    if not updates:
        return dict(row)

    sets = ", ".join(f"{k}=${i+3}" for i, k in enumerate(updates))
    updated = await conn.fetchrow(
        f"""
        UPDATE validation_definitions SET {sets}
        WHERE release_type_config_id=$1 AND name=$2
        RETURNING *
        """,
        rt["id"], name, *updates.values(),
    )
    return dict(updated)
