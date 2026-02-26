"""
releasedb.client
~~~~~~~~~~~~~~~~
Full HTTP client for the ReleaseDB API.

Usage::

    from releasedb import ReleaseDBClient

    client = ReleaseDBClient(
        api_url="https://releasedb.internal",
        api_token="tok_...",
    )

    # Create a release
    release = client.create_release(
        release_type_config_id="<uuid>",
        release_name="firmware-2025-q2-drop3",
        version="2.4.1",
        field_values={"expected_sha256": "abc123...", "jira_ticket": "FW-1234"},
    )

    # Submit an artifact to the release
    artifact = client.submit_artifact(
        release_id=release.id,
        version="2.4.1",
        git_commit_sha="abc123",
        git_branch="main",
        files=[
            {
                "filename": "firmware.bin",
                "digest": "sha256:...",
                "size_bytes": 512000,
                "file_role": "primary",
                "storage_uri": "s3://my-bucket/fw/firmware.bin",
            },
        ],
    )
"""

from __future__ import annotations

import datetime
from typing import Any, Optional
from uuid import UUID

import requests

from releasedb.exceptions import APIError, NotFoundError
from releasedb.models import (
    ApprovalResponse,
    ArtifactFileResponse,
    ArtifactResponse,
    DeploymentResponse,
    EnvironmentResponse,
    ProjectResponse,
    ReleaseEventResponse,
    ReleaseResponse,
    ReleaseTypeResponse,
    TeamResponse,
    ValidationResultResponse,
    ValidationRunResponse,
)


class ReleaseDBClient:
    """
    HTTP client for the ReleaseDB API.

    All methods return typed Pydantic model instances on success.
    Raises NotFoundError on 404, APIError on other non-2xx responses.
    """

    def __init__(
        self,
        api_url: str,
        api_token: str,
        timeout: int = 30,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        allow_404: bool = False,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        resp = self._session.request(method, url, timeout=self._timeout, **kwargs)

        if resp.status_code == 404:
            if allow_404:
                return None
            raise NotFoundError(f"{method} {url} — resource not found")
        if resp.status_code == 204:
            return {}
        if not resp.ok:
            raise APIError(method, url, resp.status_code, resp.text)

        return resp.json()

    # ── Teams ─────────────────────────────────────────────────────────────────

    def list_teams(self) -> list[TeamResponse]:
        data = self._request("GET", "/api/teams")
        return [TeamResponse(**row) for row in data]

    def get_team(self, slug: str) -> Optional[TeamResponse]:
        """Return team or None if not found."""
        data = self._request("GET", f"/api/teams/{slug}", allow_404=True)
        return TeamResponse(**data) if data is not None else None

    def create_team(self, payload: dict[str, Any]) -> TeamResponse:
        data = self._request("POST", "/api/teams", json=payload)
        return TeamResponse(**data)

    def update_team(self, slug: str, payload: dict[str, Any]) -> TeamResponse:
        data = self._request("PATCH", f"/api/teams/{slug}", json=payload)
        return TeamResponse(**data)

    # ── Environments ──────────────────────────────────────────────────────────

    def list_environments(self) -> list[EnvironmentResponse]:
        data = self._request("GET", "/api/environments")
        return [EnvironmentResponse(**row) for row in data]

    def get_environment(self, slug: str) -> Optional[EnvironmentResponse]:
        """Return environment or None if not found."""
        data = self._request("GET", f"/api/environments/{slug}", allow_404=True)
        return EnvironmentResponse(**data) if data is not None else None

    def create_environment(self, payload: dict[str, Any]) -> EnvironmentResponse:
        data = self._request("POST", "/api/environments", json=payload)
        return EnvironmentResponse(**data)

    def update_environment(self, slug: str, payload: dict[str, Any]) -> EnvironmentResponse:
        data = self._request("PATCH", f"/api/environments/{slug}", json=payload)
        return EnvironmentResponse(**data)

    # ── Release types ─────────────────────────────────────────────────────────

    def list_release_types(
        self, *, team_slug: Optional[str] = None
    ) -> list[ReleaseTypeResponse]:
        params = {"team_slug": team_slug} if team_slug else {}
        data = self._request("GET", "/api/release-types", params=params)
        return [ReleaseTypeResponse(**row) for row in data]

    def get_release_type(self, slug: str) -> Optional[ReleaseTypeResponse]:
        """Return release type config or None if not found."""
        data = self._request("GET", f"/api/release-types/{slug}", allow_404=True)
        return ReleaseTypeResponse(**data) if data is not None else None

    def create_release_type(self, payload: dict[str, Any]) -> ReleaseTypeResponse:
        data = self._request("POST", "/api/release-types", json=payload)
        return ReleaseTypeResponse(**data)

    def update_release_type(
        self, slug: str, payload: dict[str, Any]
    ) -> ReleaseTypeResponse:
        data = self._request("PATCH", f"/api/release-types/{slug}", json=payload)
        return ReleaseTypeResponse(**data)

    def get_field_defs(self, release_type_slug: str) -> list[dict[str, Any]]:
        """Return all field defs for a release type."""
        data = self._request("GET", f"/api/release-types/{release_type_slug}/fields")
        return data or []

    def create_field_def(
        self, release_type_slug: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/release-types/{release_type_slug}/fields", json=payload
        )

    def update_field_def(
        self, release_type_slug: str, field_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/release-types/{release_type_slug}/fields/{field_key}",
            json=payload,
        )

    def get_validation_defs(self, release_type_slug: str) -> list[dict[str, Any]]:
        """Return all validation defs for a release type."""
        data = self._request(
            "GET", f"/api/release-types/{release_type_slug}/validations"
        )
        return data or []

    def create_validation_def(
        self, release_type_slug: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/release-types/{release_type_slug}/validations",
            json=payload,
        )

    def update_validation_def(
        self, release_type_slug: str, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/release-types/{release_type_slug}/validations/{name}",
            json=payload,
        )

    # ── Projects ──────────────────────────────────────────────────────────────

    def list_projects(self) -> list[ProjectResponse]:
        data = self._request("GET", "/api/projects")
        return [ProjectResponse(**row) for row in data]

    def get_project(self, project_id: str | UUID) -> Optional[ProjectResponse]:
        """Return project or None if not found."""
        data = self._request("GET", f"/api/projects/{project_id}", allow_404=True)
        return ProjectResponse(**data) if data is not None else None

    def create_project(self, payload: dict[str, Any]) -> ProjectResponse:
        data = self._request("POST", "/api/projects", json=payload)
        return ProjectResponse(**data)

    def update_project(self, project_id: str | UUID, payload: dict[str, Any]) -> ProjectResponse:
        data = self._request("PATCH", f"/api/projects/{project_id}", json=payload)
        return ProjectResponse(**data)

    # ── Releases ──────────────────────────────────────────────────────────────

    def list_releases(
        self,
        *,
        team_slug: Optional[str] = None,
        status: Optional[str] = None,
        release_type_slug: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReleaseResponse]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if team_slug:
            params["team_slug"] = team_slug
        if status:
            params["status"] = status
        if release_type_slug:
            params["release_type_slug"] = release_type_slug
        data = self._request("GET", "/api/releases", params=params)
        return [ReleaseResponse(**row) for row in data]

    def get_release(self, release_id: str | UUID) -> ReleaseResponse:
        data = self._request("GET", f"/api/releases/{release_id}")
        return ReleaseResponse(**data)

    def create_release(
        self,
        *,
        release_type_config_id: str | UUID,
        release_name: str,
        version: str,
        target_date: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = None,
        project_id: Optional[str | UUID] = None,
        field_values: Optional[dict[str, str]] = None,
        depends_on: Optional[list[str | UUID]] = None,
    ) -> ReleaseResponse:
        """
        Create a new release (status: draft).

        Args:
            release_type_config_id: UUID of the release type config.
            release_name: Unique human-readable release identifier.
            version: Version string (must conform to the release type's version_scheme).
            target_date: Planned go-live date in "YYYY-MM-DD" format.
            notes: Release notes (Markdown supported).
            created_by: SSO identity / email of the person creating the release.
            field_values: Custom field values keyed by field_key.
            depends_on: List of upstream release UUIDs this release depends on.
        """
        payload: dict[str, Any] = {
            "release_type_config_id": str(release_type_config_id),
            "release_name": release_name,
            "version": version,
            "target_date": target_date,
            "notes": notes,
            "created_by": created_by,
            "field_values": field_values or {},
            "depends_on": [str(x) for x in (depends_on or [])],
        }
        if project_id is not None:
            payload["project_id"] = str(project_id)
        data = self._request("POST", "/api/releases", json=payload)
        return ReleaseResponse(**data)

    def update_release(
        self,
        release_id: str | UUID,
        *,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        target_date: Optional[str] = None,
    ) -> ReleaseResponse:
        payload = {k: v for k, v in {
            "status": status,
            "notes": notes,
            "target_date": target_date,
        }.items() if v is not None}
        data = self._request("PATCH", f"/api/releases/{release_id}", json=payload)
        return ReleaseResponse(**data)

    def get_release_events(
        self, release_id: str | UUID
    ) -> list[ReleaseEventResponse]:
        data = self._request("GET", f"/api/releases/{release_id}/events")
        return [ReleaseEventResponse(**row) for row in data]

    def get_release_lineage(self, release_id: str | UUID) -> dict:
        """
        Return the full ancestor graph for a release.

        Response shape: {"nodes": [ReleaseSummary, ...], "edges": [{"from_release_id": ..., "to_release_id": ...}]}
        Each edge represents a direct dependency: from_release_id depends on to_release_id.
        """
        return self._request("GET", f"/api/releases/{release_id}/lineage")

    # ── Artifacts ─────────────────────────────────────────────────────────────

    def get_artifact(self, artifact_id: str | UUID) -> ArtifactResponse:
        data = self._request("GET", f"/api/artifacts/{artifact_id}")
        return ArtifactResponse(**data)

    def submit_artifact(
        self,
        *,
        release_id: str | UUID,
        version: Optional[str] = None,
        git_commit_sha: Optional[str] = None,
        git_branch: Optional[str] = None,
        build_id: Optional[str] = None,
        build_url: Optional[str] = None,
        manifest_digest: Optional[str] = None,
        sbom: Optional[dict[str, Any]] = None,
        labels: Optional[dict[str, Any]] = None,
        built_at: Optional[str] = None,
        files: Optional[list[dict[str, Any]]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> ArtifactResponse:
        """
        Register an artifact (and its files and tools) in a single call.

        The release must already exist (create_release first).

        Args:
            release_id: UUID of the release this artifact belongs to.
            version: Artifact version string (semver, image tag, etc.).
            git_commit_sha: Source commit SHA.
            git_branch: Source branch name.
            build_id: CI pipeline run identifier.
            build_url: Link to the CI run.
            manifest_digest: Combined hash of all artifact files.
            sbom: Software bill of materials (arbitrary JSON).
            labels: Arbitrary key/value tags.
            built_at: ISO 8601 timestamp of when the artifact was built.
                      Defaults to now if not provided.
            files: List of file dicts with keys:
                   filename, digest, size_bytes, file_role, storage_uri, media_type
            tools: List of tool dicts with keys:
                   tool_name, tool_version, git_commit_sha, git_branch,
                   runner_image, invocation_flags
        """
        payload = {
            "release_id": str(release_id),
            "version": version,
            "git_commit_sha": git_commit_sha,
            "git_branch": git_branch,
            "build_id": build_id,
            "build_url": build_url,
            "manifest_digest": manifest_digest,
            "sbom": sbom,
            "labels": labels,
            "built_at": built_at or datetime.datetime.utcnow().isoformat(),
            "files": files or [],
            "tools": tools or [],
        }
        data = self._request("POST", "/api/artifacts", json=payload)
        return ArtifactResponse(**data)

    def list_artifact_files(
        self, artifact_id: str | UUID
    ) -> list[ArtifactFileResponse]:
        data = self._request("GET", f"/api/artifacts/{artifact_id}/files")
        return [ArtifactFileResponse(**row) for row in data]

    def add_artifact_file(
        self, artifact_id: str | UUID, payload: dict[str, Any]
    ) -> ArtifactFileResponse:
        data = self._request(
            "POST", f"/api/artifacts/{artifact_id}/files", json=payload
        )
        return ArtifactFileResponse(**data)

    def list_artifact_tools(
        self, artifact_id: str | UUID
    ) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/artifacts/{artifact_id}/tools") or []

    def find_artifacts(
        self,
        *,
        release_id: Optional[str | UUID] = None,
        tool_name: Optional[str] = None,
        git_sha: Optional[str] = None,
    ) -> list[ArtifactResponse]:
        params: dict[str, Any] = {}
        if release_id:
            params["release_id"] = str(release_id)
        if tool_name:
            params["tool_name"] = tool_name
        if git_sha:
            params["git_sha"] = git_sha
        data = self._request("GET", "/api/artifacts", params=params)
        return [ArtifactResponse(**row) for row in data]

    # ── Validation ────────────────────────────────────────────────────────────

    def trigger_validation(
        self,
        release_id: str | UUID,
        *,
        environment: str,
        triggered_by: Optional[str] = None,
    ) -> ValidationRunResponse:
        payload = {
            "environment": environment,
            "triggered_by": triggered_by,
            "trigger_type": "manual",
        }
        data = self._request(
            "POST", f"/api/releases/{release_id}/validate", json=payload
        )
        return ValidationRunResponse(**data)

    def list_validation_runs(
        self, release_id: str | UUID
    ) -> list[ValidationRunResponse]:
        data = self._request("GET", f"/api/releases/{release_id}/validation-runs")
        return [ValidationRunResponse(**row) for row in data]

    def get_validation_run(self, run_id: str | UUID) -> ValidationRunResponse:
        data = self._request("GET", f"/api/validation-runs/{run_id}")
        return ValidationRunResponse(**data)

    def update_validation_result(
        self,
        result_id: str | UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Called by validator scripts via the Reporter to write back check results."""
        return self._request(
            "PATCH", f"/api/validation-results/{result_id}", json=payload
        ) or {}

    # ── Approvals ─────────────────────────────────────────────────────────────

    def list_approvals(
        self, release_id: str | UUID
    ) -> list[ApprovalResponse]:
        data = self._request("GET", f"/api/releases/{release_id}/approvals")
        return [ApprovalResponse(**row) for row in data]

    def submit_approval(
        self,
        release_id: str | UUID,
        *,
        environment_id: str | UUID,
        approving_team_id: str | UUID,
        approver_identity: str,
        decision: str,
        comment: Optional[str] = None,
    ) -> ApprovalResponse:
        """
        Submit an approval decision for a release.

        Args:
            decision: One of "approved", "rejected", "deferred".
        """
        payload = {
            "environment_id": str(environment_id),
            "approving_team_id": str(approving_team_id),
            "approver_identity": approver_identity,
            "decision": decision,
            "comment": comment,
        }
        data = self._request(
            "POST", f"/api/releases/{release_id}/approvals", json=payload
        )
        return ApprovalResponse(**data)

    # ── Deployments ───────────────────────────────────────────────────────────

    def trigger_deployment(
        self,
        release_id: str | UUID,
        *,
        environment_id: str | UUID,
        artifact_id: str | UUID,
        strategy: Optional[str] = None,
        deployed_by: Optional[str] = None,
        rollback_of: Optional[str | UUID] = None,
    ) -> DeploymentResponse:
        """
        Trigger a deployment for a release.

        Args:
            strategy: One of "rolling", "blue-green", "canary".
        """
        payload = {
            "environment_id": str(environment_id),
            "artifact_id": str(artifact_id),
            "strategy": strategy,
            "deployed_by": deployed_by,
            "rollback_of": str(rollback_of) if rollback_of else None,
        }
        data = self._request(
            "POST", f"/api/releases/{release_id}/deploy", json=payload
        )
        return DeploymentResponse(**data)

    def get_deployment(self, deployment_id: str | UUID) -> DeploymentResponse:
        data = self._request("GET", f"/api/deployments/{deployment_id}")
        return DeploymentResponse(**data)

    def update_deployment_status(
        self,
        deployment_id: str | UUID,
        *,
        status: str,
        finished_at: Optional[str] = None,
    ) -> DeploymentResponse:
        """
        Update deployment status from a callback (e.g. Jenkins post-deploy step).

        Args:
            status: One of "running", "success", "failed".
        """
        payload: dict[str, Any] = {"status": status}
        if finished_at:
            payload["finished_at"] = finished_at
        data = self._request(
            "PATCH", f"/api/deployments/{deployment_id}", json=payload
        )
        return DeploymentResponse(**data)
