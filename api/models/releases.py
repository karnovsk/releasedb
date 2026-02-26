from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class ReleaseTypeCreate(BaseModel):
    slug: str
    team_slug: str
    display_name: str
    description: Optional[str] = None
    artifact_cardinality: str = "single"
    artifact_naming_regex: Optional[str] = None
    allowed_file_types: Optional[list[str]] = None
    requires_approval: bool = True
    version_scheme: str = "semver"


class ReleaseTypeUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    artifact_cardinality: Optional[str] = None
    artifact_naming_regex: Optional[str] = None
    allowed_file_types: Optional[list[str]] = None
    requires_approval: Optional[bool] = None
    version_scheme: Optional[str] = None
    is_active: Optional[bool] = None


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


class FieldDefCreate(BaseModel):
    field_key: str
    label: str
    field_type: str
    is_required: bool = False
    enum_options: Optional[list[str]] = None
    validation_regex: Optional[str] = None
    default_value: Optional[str] = None
    display_order: int = 0


class FieldDefUpdate(BaseModel):
    label: Optional[str] = None
    field_type: Optional[str] = None
    is_required: Optional[bool] = None
    enum_options: Optional[list[str]] = None
    validation_regex: Optional[str] = None
    default_value: Optional[str] = None
    display_order: Optional[int] = None


class FieldDefResponse(BaseModel):
    id: UUID
    release_type_config_id: UUID
    field_key: str
    label: str
    field_type: str
    is_required: bool
    enum_options: Optional[list[str]] = None
    validation_regex: Optional[str] = None
    display_order: int
    default_value: Optional[str] = None


class ValidationDefCreate(BaseModel):
    name: str
    description: Optional[str] = None
    runner_type: str
    script_body: Optional[str] = None
    script_url: Optional[str] = None
    script_checksum: Optional[str] = None
    runner_image: Optional[str] = None
    timeout_seconds: int = 300
    env_vars: Optional[dict[str, str]] = None
    is_blocking: bool = True
    on_failure: str = "block"
    applies_to: str = "release"
    run_order: int = 0
    environment_slug: Optional[str] = None


class ValidationDefUpdate(BaseModel):
    description: Optional[str] = None
    runner_type: Optional[str] = None
    script_body: Optional[str] = None
    script_url: Optional[str] = None
    script_checksum: Optional[str] = None
    runner_image: Optional[str] = None
    timeout_seconds: Optional[int] = None
    env_vars: Optional[dict[str, str]] = None
    is_blocking: Optional[bool] = None
    on_failure: Optional[str] = None
    applies_to: Optional[str] = None
    run_order: Optional[int] = None
    environment_slug: Optional[str] = None
    is_active: Optional[bool] = None


class ValidationDefResponse(BaseModel):
    id: UUID
    release_type_config_id: UUID
    environment_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    runner_type: str
    script_body: Optional[str] = None
    script_url: Optional[str] = None
    script_checksum: Optional[str] = None
    runner_image: Optional[str] = None
    timeout_seconds: int
    env_vars: Optional[dict[str, Any]] = None
    is_blocking: bool
    on_failure: str
    applies_to: str
    run_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReleaseCreate(BaseModel):
    release_type_config_id: UUID
    release_name: str
    version: str
    target_date: Optional[date] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    project_id: Optional[UUID] = None
    field_values: dict[str, str] = {}
    depends_on: list[UUID] = []


class ReleaseUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    target_date: Optional[date] = None
    project_id: Optional[UUID] = None


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
    project_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    field_values: dict[str, str] = {}
    depends_on: list[UUID] = []


class ValidationTrigger(BaseModel):
    environment: str
    triggered_by: Optional[str] = None
    trigger_type: str = "manual"


class ValidationRunResponse(BaseModel):
    id: UUID
    release_id: UUID
    environment_id: UUID
    triggered_by: Optional[str] = None
    trigger_type: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ApprovalCreate(BaseModel):
    environment_id: UUID
    approving_team_id: UUID
    approver_identity: str
    decision: str
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: UUID
    release_id: UUID
    environment_id: UUID
    approving_team_id: UUID
    approver_identity: str
    decision: str
    comment: Optional[str] = None
    decided_at: datetime


class DeploymentTrigger(BaseModel):
    environment_id: UUID
    artifact_id: UUID
    strategy: Optional[str] = None
    deployed_by: Optional[str] = None
    rollback_of: Optional[UUID] = None


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


class ReleaseSummary(BaseModel):
    id: UUID
    release_name: str
    version: str
    status: str


class LineageEdge(BaseModel):
    from_release_id: UUID
    to_release_id: UUID


class LineageResponse(BaseModel):
    nodes: list[ReleaseSummary]
    edges: list[LineageEdge]


class PagedReleases(BaseModel):
    items: list[ReleaseResponse]
    total: int
    limit: int
    offset: int
