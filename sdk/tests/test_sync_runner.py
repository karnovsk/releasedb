"""
tests/test_sync_runner.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for SyncRunner.

All API calls are mocked — no live ReleaseDB server required.
Run with: pytest tests/test_sync_runner.py -v
"""

from unittest.mock import MagicMock, call, patch

import pytest

from releasedb.sync.client import ReleaseDBClient
from releasedb.sync.models import ReleaseDBConfig
from releasedb.sync.runner import SyncRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> MagicMock:
    """Return a MagicMock that stands in for ReleaseDBClient."""
    client = MagicMock(spec=ReleaseDBClient)
    # Default: nothing exists yet (all GETs return None / [])
    client.get_team.return_value = None
    client.get_release_type.return_value = None
    client.get_field_defs.return_value = []
    client.get_validation_defs.return_value = []
    client.get_environment.return_value = {"id": "abc", "slug": "prod"}
    return client


def _simple_config(*, with_field=False, with_validation=False) -> ReleaseDBConfig:
    raw: dict = {
        "team": {"slug": "my-team", "name": "My Team"},
        "release_types": [
            {
                "slug": "my-type",
                "display_name": "My Type",
                "fields": [],
                "validations": [],
            }
        ],
    }
    if with_field:
        raw["release_types"][0]["fields"] = [
            {"key": "ticket", "label": "Ticket", "type": "string"}
        ]
    if with_validation:
        raw["release_types"][0]["validations"] = [
            {
                "name": "my-check",
                "runner_type": "docker",
                "runner_image": "my-image:1",
                "script_url": "s3://b/script.py",
                "script_checksum": "sha256:aabb",
            }
        ]
    return ReleaseDBConfig.model_validate(raw)


# ---------------------------------------------------------------------------
# Team sync
# ---------------------------------------------------------------------------

class TestTeamSync:
    def test_creates_team_when_not_exists(self):
        client = _make_client()
        runner = SyncRunner(client=client)
        runner.run(_simple_config())

        client.create_team.assert_called_once()
        payload = client.create_team.call_args[1]["payload"] \
            if "payload" in client.create_team.call_args[1] \
            else client.create_team.call_args[0][0]
        assert payload["slug"] == "my-team"

    def test_skips_team_when_unchanged(self):
        client = _make_client()
        client.get_team.return_value = {
            "slug": "my-team",
            "name": "My Team",
            "contact_email": None,
            "metadata": None,
        }
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config())

        client.create_team.assert_not_called()
        client.update_team.assert_not_called()
        team_skips = [c for c in result.changes if "team" in c.resource and c.action == "skip"]
        assert len(team_skips) == 1

    def test_updates_team_when_name_changed(self):
        client = _make_client()
        client.get_team.return_value = {
            "slug": "my-team",
            "name": "Old Name",      # different from config
            "contact_email": None,
            "metadata": None,
        }
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config())

        client.update_team.assert_called_once()
        update = [c for c in result.changes if "team" in c.resource and c.action == "update"]
        assert len(update) == 1
        assert "name" in update[0].changed_keys

    def test_dry_run_does_not_create_team(self):
        client = _make_client()
        runner = SyncRunner(client=client, dry_run=True)
        runner.run(_simple_config())

        client.create_team.assert_not_called()
        client.update_team.assert_not_called()

    def test_dry_run_does_not_update_team(self):
        client = _make_client()
        client.get_team.return_value = {
            "slug": "my-team",
            "name": "Old Name",
            "contact_email": None,
            "metadata": None,
        }
        runner = SyncRunner(client=client, dry_run=True)
        runner.run(_simple_config())

        client.update_team.assert_not_called()


# ---------------------------------------------------------------------------
# Release type sync
# ---------------------------------------------------------------------------

class TestReleaseTypeSync:
    def test_creates_release_type_when_not_exists(self):
        client = _make_client()
        runner = SyncRunner(client=client)
        runner.run(_simple_config())

        client.create_release_type.assert_called_once()

    def test_skips_release_type_when_unchanged(self):
        client = _make_client()
        client.get_release_type.return_value = {
            "slug": "my-type",
            "team_slug": "my-team",
            "display_name": "My Type",
            "description": None,
            "artifact_cardinality": "single",
            "artifact_naming_regex": None,
            "allowed_file_types": None,
            "requires_approval": True,
            "version_scheme": "semver",
        }
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config())

        client.create_release_type.assert_not_called()
        client.update_release_type.assert_not_called()
        rt_skips = [
            c for c in result.changes
            if "release_type" in c.resource and c.action == "skip"
        ]
        assert len(rt_skips) == 1

    def test_updates_release_type_when_display_name_changed(self):
        client = _make_client()
        client.get_release_type.return_value = {
            "slug": "my-type",
            "team_slug": "my-team",
            "display_name": "Old Display Name",
            "description": None,
            "artifact_cardinality": "single",
            "artifact_naming_regex": None,
            "allowed_file_types": None,
            "requires_approval": True,
            "version_scheme": "semver",
        }
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config())

        client.update_release_type.assert_called_once()
        updates = [
            c for c in result.changes
            if "release_type" in c.resource and c.action == "update"
        ]
        assert "display_name" in updates[0].changed_keys

    def test_dry_run_does_not_create_release_type(self):
        client = _make_client()
        runner = SyncRunner(client=client, dry_run=True)
        runner.run(_simple_config())

        client.create_release_type.assert_not_called()


# ---------------------------------------------------------------------------
# Field definition sync
# ---------------------------------------------------------------------------

class TestFieldSync:
    def test_creates_field_when_not_exists(self):
        client = _make_client()
        runner = SyncRunner(client=client)
        runner.run(_simple_config(with_field=True))

        client.create_field_def.assert_called_once()
        args = client.create_field_def.call_args[0]
        assert args[0] == "my-type"     # release_type_slug
        assert args[1]["field_key"] == "ticket"

    def test_skips_field_when_unchanged(self):
        client = _make_client()
        client.get_field_defs.return_value = [
            {
                "field_key": "ticket",
                "label": "Ticket",
                "field_type": "string",
                "is_required": False,
                "enum_options": None,
                "validation_regex": None,
                "default_value": None,
            }
        ]
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config(with_field=True))

        client.create_field_def.assert_not_called()
        client.update_field_def.assert_not_called()
        field_skips = [c for c in result.changes if "field" in c.resource and c.action == "skip"]
        assert len(field_skips) == 1

    def test_updates_field_when_label_changed(self):
        client = _make_client()
        client.get_field_defs.return_value = [
            {
                "field_key": "ticket",
                "label": "Old Label",    # different
                "field_type": "string",
                "is_required": False,
                "enum_options": None,
                "validation_regex": None,
                "default_value": None,
            }
        ]
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config(with_field=True))

        client.update_field_def.assert_called_once()
        updates = [c for c in result.changes if "field" in c.resource and c.action == "update"]
        assert "label" in updates[0].changed_keys

    def test_dry_run_does_not_create_field(self):
        client = _make_client()
        runner = SyncRunner(client=client, dry_run=True)
        runner.run(_simple_config(with_field=True))

        client.create_field_def.assert_not_called()


# ---------------------------------------------------------------------------
# Validation definition sync
# ---------------------------------------------------------------------------

class TestValidationSync:
    def test_creates_validation_when_not_exists(self):
        client = _make_client()
        runner = SyncRunner(client=client)
        runner.run(_simple_config(with_validation=True))

        client.create_validation_def.assert_called_once()
        args = client.create_validation_def.call_args[0]
        assert args[0] == "my-type"
        assert args[1]["name"] == "my-check"

    def test_skips_validation_when_unchanged(self):
        client = _make_client()
        client.get_validation_defs.return_value = [
            {
                "name": "my-check",
                "runner_type": "docker",
                "script_url": "s3://b/script.py",
                "script_checksum": "sha256:aabb",
                "runner_image": "my-image:1",
                "timeout_seconds": 300,
                "is_blocking": True,
                "on_failure": "block",
                "applies_to": "release",
                "run_order": 0,
                "environment_slug": None,
            }
        ]
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config(with_validation=True))

        client.create_validation_def.assert_not_called()
        client.update_validation_def.assert_not_called()
        v_skips = [
            c for c in result.changes
            if "validation" in c.resource and c.action == "skip"
        ]
        assert len(v_skips) == 1

    def test_updates_validation_when_runner_image_changed(self):
        client = _make_client()
        client.get_validation_defs.return_value = [
            {
                "name": "my-check",
                "runner_type": "docker",
                "script_url": "s3://b/script.py",
                "script_checksum": "sha256:aabb",
                "runner_image": "my-image:OLD",   # different
                "timeout_seconds": 300,
                "is_blocking": True,
                "on_failure": "block",
                "applies_to": "release",
                "run_order": 0,
                "environment_slug": None,
            }
        ]
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config(with_validation=True))

        client.update_validation_def.assert_called_once()
        updates = [
            c for c in result.changes
            if "validation" in c.resource and c.action == "update"
        ]
        assert "runner_image" in updates[0].changed_keys

    def test_dry_run_does_not_create_validation(self):
        client = _make_client()
        runner = SyncRunner(client=client, dry_run=True)
        runner.run(_simple_config(with_validation=True))

        client.create_validation_def.assert_not_called()


# ---------------------------------------------------------------------------
# Environment reference validation
# ---------------------------------------------------------------------------

class TestEnvironmentValidation:
    def test_missing_environment_recorded_as_error(self):
        client = _make_client()
        client.get_environment.return_value = None   # environment doesn't exist

        raw = {
            "team": {"slug": "my-team", "name": "My Team"},
            "release_types": [
                {
                    "slug": "my-type",
                    "display_name": "My Type",
                    "validations": [
                        {
                            "name": "prod-check",
                            "runner_type": "docker",
                            "runner_image": "img:1",
                            "script_url": "s3://b/s.py",
                            "script_checksum": "sha256:aa",
                            "environment": "prod",
                        }
                    ],
                }
            ],
        }
        config = ReleaseDBConfig.model_validate(raw)
        runner = SyncRunner(client=client)
        result = runner.run(config)

        assert not result.ok
        assert any("prod" in e for e in result.errors)

    def test_valid_environment_no_error(self):
        client = _make_client()
        client.get_environment.return_value = {"slug": "prod"}

        raw = {
            "team": {"slug": "my-team", "name": "My Team"},
            "release_types": [
                {
                    "slug": "my-type",
                    "display_name": "My Type",
                    "validations": [
                        {
                            "name": "prod-check",
                            "runner_type": "docker",
                            "runner_image": "img:1",
                            "script_url": "s3://b/s.py",
                            "script_checksum": "sha256:aa",
                            "environment": "prod",
                        }
                    ],
                }
            ],
        }
        config = ReleaseDBConfig.model_validate(raw)
        runner = SyncRunner(client=client)
        result = runner.run(config)

        assert result.ok


# ---------------------------------------------------------------------------
# SyncResult counters
# ---------------------------------------------------------------------------

class TestSyncResultCounters:
    def test_creates_counted(self):
        client = _make_client()
        runner = SyncRunner(client=client)
        result = runner.run(_simple_config(with_field=True, with_validation=True))

        # team + release_type + field + validation = 4 creates
        assert result.creates == 4
        assert result.updates == 0

    def test_skips_counted(self):
        existing_team = {
            "slug": "my-team",
            "name": "My Team",
            "contact_email": None,
            "metadata": None,
        }
        existing_rt = {
            "slug": "my-type",
            "team_slug": "my-team",
            "display_name": "My Type",
            "description": None,
            "artifact_cardinality": "single",
            "artifact_naming_regex": None,
            "allowed_file_types": None,
            "requires_approval": True,
            "version_scheme": "semver",
        }
        client = _make_client()
        client.get_team.return_value = existing_team
        client.get_release_type.return_value = existing_rt

        runner = SyncRunner(client=client)
        result = runner.run(_simple_config())

        assert result.skips == 2   # team + release_type
        assert result.creates == 0
        assert result.updates == 0
        assert result.ok
