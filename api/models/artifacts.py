from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class ArtifactFileIn(BaseModel):
    filename: str
    digest: str
    file_role: Optional[str] = None
    storage_uri: Optional[str] = None
    media_type: Optional[str] = None
    size_bytes: Optional[int] = None


class ArtifactToolIn(BaseModel):
    tool_name: str
    tool_version: Optional[str] = None
    git_commit_sha: Optional[str] = None
    git_branch: Optional[str] = None
    runner_image: Optional[str] = None
    invocation_flags: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ArtifactCreate(BaseModel):
    release_id: UUID
    version: Optional[str] = None
    git_commit_sha: Optional[str] = None
    git_branch: Optional[str] = None
    build_id: Optional[str] = None
    build_url: Optional[str] = None
    manifest_digest: Optional[str] = None
    sbom: Optional[dict[str, Any]] = None
    labels: Optional[dict[str, Any]] = None
    built_at: str  # ISO 8601 string
    files: list[ArtifactFileIn] = []
    tools: list[ArtifactToolIn] = []


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


class ValidationResultUpdate(BaseModel):
    status: str
    evidence: Optional[dict[str, Any]] = None
    duration_ms: Optional[int] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


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


class DeploymentUpdate(BaseModel):
    status: str
    finished_at: Optional[str] = None
