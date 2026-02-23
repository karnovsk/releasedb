"""
tests/test_sync_models.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the Pydantic config models in releasedb_validator.sync.models.

No API calls are made — these tests cover YAML validation only.
Run with: pytest tests/test_sync_models.py -v
"""

import pytest
from pydantic import ValidationError

from releasedb.sync.models import (
    FieldDef,
    ReleaseDBConfig,
    ReleaseTypeConfig,
    TeamConfig,
    ValidationDef,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_validation(**overrides) -> dict:
    base = {
        "name": "my-check",
        "runner_type": "docker",
        "runner_image": "my-image:latest",
        "script_url": "s3://bucket/script.py",
        "script_checksum": "sha256:aabb",
    }
    base.update(overrides)
    return base


def _minimal_release_type(**overrides) -> dict:
    base = {"slug": "my-type", "display_name": "My Type"}
    base.update(overrides)
    return base


def _minimal_config(**overrides) -> dict:
    base = {
        "team": {"slug": "my-team", "name": "My Team"},
        "release_types": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TeamConfig
# ---------------------------------------------------------------------------

class TestTeamConfig:
    def test_minimal_valid(self):
        t = TeamConfig(slug="my-team", name="My Team")
        assert t.slug == "my-team"
        assert t.contact_email is None
        assert t.metadata is None

    def test_full_valid(self):
        t = TeamConfig(
            slug="platform-eng",
            name="Platform Engineering",
            contact_email="platform@co.com",
            metadata={"slack_channel": "#releases"},
        )
        assert t.metadata["slack_channel"] == "#releases"

    def test_slug_required(self):
        with pytest.raises(ValidationError, match="slug"):
            TeamConfig(name="My Team")

    def test_name_required(self):
        with pytest.raises(ValidationError, match="name"):
            TeamConfig(slug="my-team")


# ---------------------------------------------------------------------------
# FieldDef
# ---------------------------------------------------------------------------

class TestFieldDef:
    def test_string_field(self):
        f = FieldDef(key="jira_ticket", label="JIRA Ticket", type="string")
        assert f.type == "string"
        assert not f.required
        assert f.options is None

    def test_enum_with_options(self):
        f = FieldDef(
            key="hw_rev",
            label="HW Revision",
            type="enum",
            options=["rev-a", "rev-b"],
        )
        assert f.options == ["rev-a", "rev-b"]

    def test_enum_without_options_raises(self):
        with pytest.raises(ValidationError, match="options.*required"):
            FieldDef(key="hw_rev", label="HW Revision", type="enum")

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            FieldDef(key="x", label="X", type="blob")  # not a valid type

    def test_key_must_be_snake_case(self):
        with pytest.raises(ValidationError):
            FieldDef(key="My Field", label="My Field", type="string")

    def test_all_types_accepted(self):
        for field_type in ("string", "number", "file", "bool", "date"):
            f = FieldDef(key="x", label="X", type=field_type)
            assert f.type == field_type

    def test_required_defaults_false(self):
        f = FieldDef(key="x", label="X", type="string")
        assert f.required is False

    def test_with_regex(self):
        f = FieldDef(
            key="sha",
            label="SHA",
            type="string",
            validation_regex="^[0-9a-f]{64}$",
        )
        assert f.validation_regex == "^[0-9a-f]{64}$"


# ---------------------------------------------------------------------------
# ValidationDef
# ---------------------------------------------------------------------------

class TestValidationDef:
    def test_docker_runner_valid(self):
        v = ValidationDef(**_minimal_validation())
        assert v.runner_type == "docker"
        assert v.is_blocking is True
        assert v.on_failure == "block"
        assert v.applies_to == "release"
        assert v.timeout_seconds == 300

    def test_script_body_allowed_without_url(self):
        v = ValidationDef(
            name="inline-check",
            runner_type="shell",
            script_body="echo hello",
        )
        assert v.script_body == "echo hello"
        assert v.script_url is None

    def test_script_url_requires_checksum(self):
        with pytest.raises(ValidationError, match="script_checksum.*required"):
            ValidationDef(
                name="my-check",
                runner_type="python",
                script_url="s3://bucket/script.py",
                # missing script_checksum
            )

    def test_no_script_source_raises(self):
        with pytest.raises(ValidationError, match="script_body.*script_url"):
            ValidationDef(name="my-check", runner_type="shell")

    def test_docker_without_runner_image_raises(self):
        with pytest.raises(ValidationError, match="runner_image.*required"):
            ValidationDef(
                name="my-check",
                runner_type="docker",
                script_url="s3://bucket/script.py",
                script_checksum="sha256:aabb",
                # missing runner_image
            )

    def test_invalid_runner_type_raises(self):
        with pytest.raises(ValidationError):
            ValidationDef(**_minimal_validation(runner_type="kubernetes"))

    def test_invalid_on_failure_raises(self):
        with pytest.raises(ValidationError):
            ValidationDef(**_minimal_validation(on_failure="explode"))

    def test_invalid_applies_to_raises(self):
        with pytest.raises(ValidationError):
            ValidationDef(**_minimal_validation(applies_to="team"))

    def test_timeout_minimum_enforced(self):
        with pytest.raises(ValidationError):
            ValidationDef(**_minimal_validation(timeout_seconds=5))

    def test_timeout_maximum_enforced(self):
        with pytest.raises(ValidationError):
            ValidationDef(**_minimal_validation(timeout_seconds=9999))

    def test_optional_environment(self):
        v = ValidationDef(**_minimal_validation(environment="prod"))
        assert v.environment == "prod"

    def test_env_vars(self):
        v = ValidationDef(**_minimal_validation(env_vars={"FOO": "bar"}))
        assert v.env_vars == {"FOO": "bar"}


# ---------------------------------------------------------------------------
# ReleaseTypeConfig
# ---------------------------------------------------------------------------

class TestReleaseTypeConfig:
    def test_minimal_valid(self):
        rt = ReleaseTypeConfig(**_minimal_release_type())
        assert rt.version_scheme == "semver"
        assert rt.requires_approval is True
        assert rt.artifact_cardinality == "single"
        assert rt.fields == []
        assert rt.validations == []

    def test_invalid_version_scheme_raises(self):
        with pytest.raises(ValidationError):
            ReleaseTypeConfig(**_minimal_release_type(version_scheme="freeform"))

    def test_invalid_cardinality_raises(self):
        with pytest.raises(ValidationError):
            ReleaseTypeConfig(**_minimal_release_type(artifact_cardinality="triple"))

    def test_duplicate_field_keys_raises(self):
        field = {"key": "sha", "label": "SHA", "type": "string"}
        with pytest.raises(ValidationError, match="duplicate field keys"):
            ReleaseTypeConfig(
                **_minimal_release_type(),
                fields=[field, field],
            )

    def test_duplicate_validation_names_raises(self):
        v = _minimal_validation()
        with pytest.raises(ValidationError, match="duplicate validation names"):
            ReleaseTypeConfig(
                **_minimal_release_type(),
                validations=[v, v],
            )

    def test_with_fields_and_validations(self):
        rt = ReleaseTypeConfig(
            slug="fw",
            display_name="Firmware",
            fields=[
                {"key": "sha256", "label": "SHA-256", "type": "string", "required": True}
            ],
            validations=[_minimal_validation()],
        )
        assert len(rt.fields) == 1
        assert rt.fields[0].key == "sha256"
        assert len(rt.validations) == 1


# ---------------------------------------------------------------------------
# ReleaseDBConfig (root)
# ---------------------------------------------------------------------------

class TestReleaseDBConfig:
    def test_minimal_valid(self):
        cfg = ReleaseDBConfig.model_validate(_minimal_config())
        assert cfg.team.slug == "my-team"
        assert cfg.release_types == []

    def test_with_release_types(self):
        cfg = ReleaseDBConfig.model_validate(
            _minimal_config(
                release_types=[
                    {
                        "slug": "fw",
                        "display_name": "Firmware",
                        "fields": [
                            {"key": "sha", "label": "SHA", "type": "string"}
                        ],
                        "validations": [_minimal_validation()],
                    }
                ]
            )
        )
        assert len(cfg.release_types) == 1
        assert cfg.release_types[0].fields[0].key == "sha"

    def test_duplicate_release_type_slugs_raises(self):
        rt = {"slug": "fw", "display_name": "Firmware"}
        with pytest.raises(ValidationError, match="Duplicate release_type slugs"):
            ReleaseDBConfig.model_validate(
                _minimal_config(release_types=[rt, rt])
            )

    def test_team_required(self):
        with pytest.raises(ValidationError, match="team"):
            ReleaseDBConfig.model_validate({"release_types": []})

    def test_full_example_parses(self):
        """Smoke test that the full template YAML structure parses correctly."""
        raw = {
            "team": {
                "slug": "platform-eng",
                "name": "Platform Engineering",
                "contact_email": "platform@co.com",
                "metadata": {"slack_channel": "#platform-releases"},
            },
            "release_types": [
                {
                    "slug": "firmware-drop",
                    "display_name": "Firmware Release",
                    "artifact_cardinality": "single",
                    "allowed_file_types": [".bin", ".hex"],
                    "requires_approval": True,
                    "version_scheme": "semver",
                    "fields": [
                        {
                            "key": "expected_sha256",
                            "label": "Expected SHA-256",
                            "type": "string",
                            "required": True,
                            "validation_regex": "^[0-9a-f]{64}$",
                        },
                        {
                            "key": "hw_rev",
                            "label": "HW Revision",
                            "type": "enum",
                            "required": True,
                            "options": ["rev-a", "rev-b"],
                        },
                    ],
                    "validations": [
                        {
                            "name": "firmware-integrity-check",
                            "runner_type": "docker",
                            "runner_image": "my-registry/fw-validator:1.0",
                            "script_url": "s3://bucket/validator.py",
                            "script_checksum": "sha256:aabb",
                            "applies_to": "artifact",
                            "is_blocking": True,
                            "on_failure": "block",
                            "timeout_seconds": 120,
                            "run_order": 10,
                        },
                    ],
                }
            ],
        }
        cfg = ReleaseDBConfig.model_validate(raw)
        assert cfg.team.slug == "platform-eng"
        rt = cfg.release_types[0]
        assert rt.slug == "firmware-drop"
        assert len(rt.fields) == 2
        assert len(rt.validations) == 1
        assert rt.validations[0].timeout_seconds == 120
