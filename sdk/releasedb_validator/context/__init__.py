"""
releasedb_validator.context
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parses the environment variables injected by the ReleaseDB validation runner
into a clean, typed object. Validation scripts never call os.environ directly.

Environment variables injected by ReleaseDB runner
---------------------------------------------------
RELEASEDB_API_URL          Base URL of the ReleaseDB API
RELEASEDB_API_TOKEN        Bearer token for result reporting
RELEASEDB_RESULT_ID        validation_results.id to write outcome to
RELEASEDB_RELEASE_ID       releases.id being validated
RELEASEDB_RELEASE_NAME     Human-readable release name
RELEASEDB_RELEASE_VERSION  Release version string
RELEASEDB_RELEASE_STATUS   Current release status
RELEASEDB_ARTIFACT_ID      artifacts.id
RELEASEDB_ARTIFACT_VERSION Artifact version
RELEASEDB_ARTIFACT_DIGEST  manifest_digest of the artifact
RELEASEDB_ENVIRONMENT      Target environment slug (e.g. "staging")
RELEASEDB_TEAM_SLUG        Owning team slug
RELEASEDB_FILES_DIR        Local directory where artifact files are pre-fetched
RELEASEDB_FIELD_*          release_field_values, e.g. RELEASEDB_FIELD_JIRA_TICKET
RELEASEDB_DRY_RUN          "1" if running locally without reporting back
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ArtifactContext:
    """Metadata about the artifact being validated."""
    id: str
    version: str
    digest: str
    # Directory where files are pre-fetched by the runner (may be empty
    # if the validator fetches them itself via storage_uri)
    files_dir: Path

    def file(self, filename: str) -> Path:
        """Return the path to a pre-fetched artifact file."""
        return self.files_dir / filename

    def files(self) -> list[Path]:
        """Return all pre-fetched files in the artifact directory."""
        if not self.files_dir.exists():
            return []
        return sorted(self.files_dir.iterdir())


@dataclass(frozen=True)
class ReleaseContext:
    """Metadata about the release being validated."""
    id: str
    name: str
    version: str
    status: str
    team_slug: str
    environment: str
    # Custom field values declared by release_type_field_defs
    # Keys are lowercased field_key values
    field_values: dict[str, str] = field(default_factory=dict)

    def field(self, key: str, default: str | None = None) -> str | None:
        """Get a custom release field value by key."""
        return self.field_values.get(key.lower(), default)

    def require_field(self, key: str) -> str:
        """Get a custom release field value, raising if missing."""
        value = self.field_values.get(key.lower())
        if value is None:
            raise ValueError(
                f"Required release field '{key}' not found. "
                f"Available fields: {list(self.field_values.keys())}"
            )
        return value


@dataclass(frozen=True)
class RunnerContext:
    """Runtime context provided by the validation runner."""
    api_url: str
    api_token: str
    result_id: str
    dry_run: bool


@dataclass(frozen=True)
class ValidationContext:
    """
    Complete context available to every validation script.
    Obtain via: ctx = ValidationContext.from_env()
    """
    release: ReleaseContext
    artifact: ArtifactContext
    runner: RunnerContext

    @classmethod
    def from_env(cls) -> "ValidationContext":
        """
        Build a ValidationContext from injected environment variables.
        Raises EnvironmentError with a clear message if required vars are missing.
        """
        missing = []

        def require(var: str) -> str:
            val = os.environ.get(var)
            if not val:
                missing.append(var)
                return ""
            return val

        api_url    = require("RELEASEDB_API_URL")
        api_token  = require("RELEASEDB_API_TOKEN")
        result_id  = require("RELEASEDB_RESULT_ID")
        release_id = require("RELEASEDB_RELEASE_ID")
        artifact_id = require("RELEASEDB_ARTIFACT_ID")

        if missing and os.environ.get("RELEASEDB_DRY_RUN") != "1":
            raise EnvironmentError(
                f"Missing required ReleaseDB environment variables: {missing}\n"
                "Are you running this script outside the ReleaseDB runner? "
                "Set RELEASEDB_DRY_RUN=1 for local development."
            )

        # Collect custom field values: RELEASEDB_FIELD_<KEY> → field_values[key]
        field_values = {}
        prefix = "RELEASEDB_FIELD_"
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                field_key = env_key[len(prefix):].lower()
                field_values[field_key] = env_val

        files_dir = Path(os.environ.get("RELEASEDB_FILES_DIR", "/tmp/releasedb/files"))

        return cls(
            release=ReleaseContext(
                id=release_id,
                name=os.environ.get("RELEASEDB_RELEASE_NAME", ""),
                version=os.environ.get("RELEASEDB_RELEASE_VERSION", ""),
                status=os.environ.get("RELEASEDB_RELEASE_STATUS", ""),
                team_slug=os.environ.get("RELEASEDB_TEAM_SLUG", ""),
                environment=os.environ.get("RELEASEDB_ENVIRONMENT", ""),
                field_values=field_values,
            ),
            artifact=ArtifactContext(
                id=artifact_id,
                version=os.environ.get("RELEASEDB_ARTIFACT_VERSION", ""),
                digest=os.environ.get("RELEASEDB_ARTIFACT_DIGEST", ""),
                files_dir=files_dir,
            ),
            runner=RunnerContext(
                api_url=api_url,
                api_token=api_token,
                result_id=result_id,
                dry_run=os.environ.get("RELEASEDB_DRY_RUN") == "1",
            ),
        )

    @classmethod
    def for_dry_run(
        cls,
        *,
        release_name: str = "dry-run-release",
        release_version: str = "0.0.0",
        team_slug: str = "my-team",
        environment: str = "staging",
        artifact_version: str = "0.0.0",
        files_dir: str | Path = "/tmp/releasedb/files",
        field_values: dict[str, str] | None = None,
    ) -> "ValidationContext":
        """
        Build a ValidationContext for local development and testing.
        Does not require any environment variables.

        Example:
            ctx = ValidationContext.for_dry_run(
                release_name="firmware-2025-q2",
                field_values={"jira_ticket": "FW-1234"},
                files_dir="./test_artifacts",
            )
        """
        return cls(
            release=ReleaseContext(
                id="dry-run-release-id",
                name=release_name,
                version=release_version,
                status="validating",
                team_slug=team_slug,
                environment=environment,
                field_values=field_values or {},
            ),
            artifact=ArtifactContext(
                id="dry-run-artifact-id",
                version=artifact_version,
                digest="dry-run-digest",
                files_dir=Path(files_dir),
            ),
            runner=RunnerContext(
                api_url="http://localhost:8000",
                api_token="dry-run-token",
                result_id="dry-run-result-id",
                dry_run=True,
            ),
        )
