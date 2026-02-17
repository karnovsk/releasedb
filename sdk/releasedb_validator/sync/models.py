"""
releasedb_validator.sync.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pydantic v2 models for releasedb.yaml config files.

These models represent the user-facing YAML schema — not the API wire format.
The runner translates from these models to API payloads.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamConfig(BaseModel):
    """Top-level team identity."""
    slug: str = Field(
        description="URL-safe identifier, e.g. 'platform-eng'. "
                    "Must be unique across the organisation.",
    )
    name: str = Field(description="Human-readable team name.")
    contact_email: Optional[str] = Field(
        default=None,
        description="Team distribution email for release notifications.",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Arbitrary key/value pairs: Slack channel, PagerDuty service, etc.",
    )


# ---------------------------------------------------------------------------
# Custom field definitions
# ---------------------------------------------------------------------------

class FieldDef(BaseModel):
    """One custom metadata field on a release form."""
    key: str = Field(
        description="snake_case identifier used in RELEASEDB_FIELD_* env vars.",
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    label: str = Field(description="UI display name shown in forms and reports.")
    type: Literal["string", "number", "file", "enum", "bool", "date"] = Field(
        description="Data type. Use 'enum' with options: for a fixed choice list.",
    )
    required: bool = Field(
        default=False,
        description="If true, a release cannot be submitted without this field.",
    )
    options: Optional[list[str]] = Field(
        default=None,
        description="Required when type is 'enum'. Lists the allowed values.",
    )
    validation_regex: Optional[str] = Field(
        default=None,
        description="Optional regex applied to string/enum values on the client.",
    )
    default_value: Optional[str] = Field(
        default=None,
        description="Pre-filled value shown in the release form.",
    )

    @model_validator(mode="after")
    def options_required_for_enum(self) -> "FieldDef":
        if self.type == "enum" and not self.options:
            raise ValueError(
                f"field '{self.key}': 'options' is required when type is 'enum'"
            )
        return self


# ---------------------------------------------------------------------------
# Validation script definitions
# ---------------------------------------------------------------------------

class ValidationDef(BaseModel):
    """One validation script/tool registered against a release type."""
    name: str = Field(
        description="Unique name within this release type. Used in reports and logs.",
    )
    description: Optional[str] = Field(
        default=None,
        description="What this validator checks. Shown in validation run reports.",
    )
    runner_type: Literal["shell", "python", "docker", "webhook"] = Field(
        description="How the script is executed.",
    )

    # Script location — exactly one of script_body or script_url should be set
    script_body: Optional[str] = Field(
        default=None,
        description="Inline script source. Use for short scripts (< 20 lines). "
                    "Prefer script_url for anything larger.",
    )
    script_url: Optional[str] = Field(
        default=None,
        description="S3 URI, git path, or HTTPS URL to the script. "
                    "Paired with script_checksum for integrity verification.",
    )
    script_checksum: Optional[str] = Field(
        default=None,
        description="SHA-256 of the script file, e.g. 'sha256:abc123...'. "
                    "Required when script_url is set.",
    )

    # Docker runner
    runner_image: Optional[str] = Field(
        default=None,
        description="Docker image to run the script in. Required when runner_type is 'docker'.",
    )

    # Execution
    timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Maximum wall-clock seconds before the run is marked as 'timeout'.",
    )
    env_vars: Optional[dict[str, str]] = Field(
        default=None,
        description="Extra environment variables injected at runtime, on top of "
                    "the standard RELEASEDB_* variables.",
    )

    # Gate behaviour
    is_blocking: bool = Field(
        default=True,
        description="If true, a FAIL result prevents the release from advancing.",
    )
    on_failure: Literal["block", "warn", "notify"] = Field(
        default="block",
        description="What happens when the script exits non-zero:\n"
                    "  block  — release is halted (only meaningful when is_blocking=true)\n"
                    "  warn   — failure recorded but release continues\n"
                    "  notify — failure triggers a notification; release continues",
    )
    applies_to: Literal["release", "artifact", "file"] = Field(
        default="release",
        description="Scope of the validation:\n"
                    "  release  — runs once per release\n"
                    "  artifact — runs once per artifact in the release\n"
                    "  file     — runs once per file in each artifact",
    )
    run_order: int = Field(
        default=0,
        ge=0,
        description="Execution sequence within the release type. "
                    "Lower numbers run first. Defaults to declaration order.",
    )
    environment: Optional[str] = Field(
        default=None,
        description="Environment slug this validator applies to "
                    "(e.g. 'staging', 'prod'). Omit to run in all environments.",
    )

    @model_validator(mode="after")
    def script_source_check(self) -> "ValidationDef":
        if not self.script_body and not self.script_url:
            raise ValueError(
                f"validation '{self.name}': one of 'script_body' or 'script_url' is required"
            )
        if self.script_url and not self.script_checksum:
            raise ValueError(
                f"validation '{self.name}': 'script_checksum' is required when "
                f"'script_url' is set (ensures the script hasn't changed)"
            )
        if self.runner_type == "docker" and not self.runner_image:
            raise ValueError(
                f"validation '{self.name}': 'runner_image' is required when "
                f"runner_type is 'docker'"
            )
        return self


# ---------------------------------------------------------------------------
# Release type configuration
# ---------------------------------------------------------------------------

class ReleaseTypeConfig(BaseModel):
    """Complete configuration for one release type owned by a team."""
    slug: str = Field(
        description="URL-safe identifier, e.g. 'firmware-drop'. "
                    "Must be unique across the organisation.",
    )
    display_name: str = Field(description="Human-readable name shown in the UI.")
    description: Optional[str] = Field(
        default=None,
        description="What kinds of releases this type covers.",
    )

    # Artifact shape
    artifact_cardinality: Literal["single", "multi"] = Field(
        default="single",
        description="'single' — one artifact per release (most common).\n"
                    "'multi'  — multiple artifacts per release (e.g. multi-arch builds).",
    )
    artifact_naming_regex: Optional[str] = Field(
        default=None,
        description="Optional regex the artifact version string must match.",
    )
    allowed_file_types: Optional[list[str]] = Field(
        default=None,
        description="Permitted file extensions, e.g. ['.jar', '.whl']. "
                    "Omit to allow any extension.",
    )

    # Lifecycle
    requires_approval: bool = Field(
        default=True,
        description="If true, releases must be explicitly approved before deployment.",
    )
    version_scheme: Literal["semver", "calver", "seq"] = Field(
        default="semver",
        description="Versioning scheme enforced on release.version:\n"
                    "  semver — semantic versioning (1.2.3)\n"
                    "  calver — calendar versioning (2024.03.1)\n"
                    "  seq    — monotonically increasing integer",
    )

    # Custom metadata fields
    fields: list[FieldDef] = Field(
        default_factory=list,
        description="Custom metadata fields that appear on the release form.",
    )

    # Validation scripts
    validations: list[ValidationDef] = Field(
        default_factory=list,
        description="Validation scripts that run before this release type can be approved.",
    )

    @model_validator(mode="after")
    def unique_field_keys(self) -> "ReleaseTypeConfig":
        keys = [f.key for f in self.fields]
        duplicates = {k for k in keys if keys.count(k) > 1}
        if duplicates:
            raise ValueError(
                f"release_type '{self.slug}': duplicate field keys: {duplicates}"
            )
        return self

    @model_validator(mode="after")
    def unique_validation_names(self) -> "ReleaseTypeConfig":
        names = [v.name for v in self.validations]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(
                f"release_type '{self.slug}': duplicate validation names: {duplicates}"
            )
        return self


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------

class ReleaseDBConfig(BaseModel):
    """Root model — the complete contents of a releasedb.yaml file."""
    team: TeamConfig
    release_types: list[ReleaseTypeConfig] = Field(
        default_factory=list,
        description="Release type configurations owned by this team.",
    )

    @model_validator(mode="after")
    def unique_release_type_slugs(self) -> "ReleaseDBConfig":
        slugs = [rt.slug for rt in self.release_types]
        duplicates = {s for s in slugs if slugs.count(s) > 1}
        if duplicates:
            raise ValueError(f"Duplicate release_type slugs: {duplicates}")
        return self
