"""
releasedb.models
~~~~~~~~~~~~~~~~
Pydantic v2 response models returned by ReleaseDBClient methods.
These mirror the JSON shape returned by the ReleaseDB API.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    contact_email: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class EnvironmentResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    tier: int
    requires_approval: bool
    config: Optional[dict[str, Any]] = None


class ReleaseTypeResponse(BaseModel):
    id: UUID
    team_id: UUID
    slug: str
    display_name: str
    description: Optional[str] = None
    artifact_cardinality: str
    artifact_naming_regex: Optional[str] = None
    allowed_file_types: Optional[list[str]] = None
    requires_approval: bool
    version_scheme: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReleaseResponse(BaseModel):
    id: UUID
    release_type_config_id: UUID
    owning_team_id: UUID
    release_name: str
    version: str
    status: str
    target_date: Optional[date] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    field_values: dict[str, str] = {}
    depends_on: list[UUID] = []


class ArtifactFileResponse(BaseModel):
    id: UUID
    artifact_id: UUID
    filename: str
    file_role: Optional[str] = None
    storage_uri: Optional[str] = None
    media_type: Optional[str] = None
    digest: str
    size_bytes: Optional[int] = None
    uploaded_at: datetime


class ArtifactResponse(BaseModel):
    id: UUID
    release_id: UUID
    release_type_config_id: UUID
    version: Optional[str] = None
    git_commit_sha: Optional[str] = None
    git_branch: Optional[str] = None
    build_id: Optional[str] = None
    build_url: Optional[str] = None
    manifest_digest: Optional[str] = None
    sbom: Optional[dict[str, Any]] = None
    labels: Optional[dict[str, Any]] = None
    built_at: datetime
    created_at: datetime
    files: list[ArtifactFileResponse] = []


class ValidationRunResponse(BaseModel):
    id: UUID
    release_id: UUID
    environment_id: UUID
    triggered_by: Optional[str] = None
    trigger_type: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ValidationResultResponse(BaseModel):
    id: UUID
    run_id: UUID
    validation_def_id: UUID
    artifact_id: Optional[UUID] = None
    status: str
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    log_url: Optional[str] = None
    evidence: Optional[dict[str, Any]] = None
    duration_ms: Optional[int] = None
    evaluated_at: datetime


class ApprovalResponse(BaseModel):
    id: UUID
    release_id: UUID
    environment_id: UUID
    approving_team_id: UUID
    approver_identity: str
    decision: str
    comment: Optional[str] = None
    decided_at: datetime


class DeploymentResponse(BaseModel):
    id: UUID
    release_id: UUID
    environment_id: UUID
    artifact_id: UUID
    status: str
    strategy: Optional[str] = None
    deployed_by: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    rollback_of: Optional[UUID] = None


class ReleaseEventResponse(BaseModel):
    id: UUID
    release_id: UUID
    event_type: str
    actor_identity: Optional[str] = None
    actor_team_id: Optional[UUID] = None
    payload: Optional[dict[str, Any]] = None
    occurred_at: datetime
