"""
releasedb_validator.sync.runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Core sync logic: compare desired config against current API state and apply
the minimum set of creates/updates needed to converge.

Design notes
------------
- Resources are never deleted.  Removing a release type or field from the YAML
  leaves the server-side record untouched.  This is intentional: deletions are
  destructive and require explicit human action via the UI or API.
- Each resource is identified by its slug/key/name.  If the identifier changes
  in the YAML, the old record is left in place and a new one is created.
- On dry-run, no mutating API calls are made.  The output shows exactly what
  would happen if --dry-run were removed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Optional

from .client import ReleaseDBClient
from .models import FieldDef, ReleaseDBConfig, ReleaseTypeConfig, ValidationDef


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class Change:
    action: str          # "create" | "update" | "skip"
    resource: str        # human-readable description
    changed_keys: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    changes: list[Change] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def creates(self) -> int:
        return sum(1 for c in self.changes if c.action == "create")

    @property
    def updates(self) -> int:
        return sum(1 for c in self.changes if c.action == "update")

    @property
    def skips(self) -> int:
        return sum(1 for c in self.changes if c.action == "skip")

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_GREEN = "\033[32m"
_BLUE = "\033[34m"
_GREY = "\033[90m"
_RED = "\033[31m"
_BOLD = "\033[1m"


def _no_colour(stream: Any = sys.stdout) -> bool:
    """Return True if the stream doesn't support ANSI codes."""
    import os
    return not stream.isatty() or os.environ.get("NO_COLOR") is not None


def _fmt(text: str, colour: str, stream: Any = sys.stdout) -> str:
    if _no_colour(stream):
        return text
    return f"{colour}{text}{_RESET}"


def _print_change(action: str, label: str, changed_keys: list[str], dry_run: bool) -> None:
    prefix = "(dry-run) " if dry_run else ""
    if action == "create":
        symbol = _fmt("+", _GREEN)
        suffix = ""
    elif action == "update":
        symbol = _fmt("~", _BLUE)
        suffix = f"  [{', '.join(changed_keys)}]" if changed_keys else ""
    else:  # skip
        symbol = _fmt("·", _GREY)
        suffix = ""
    print(f"  {symbol} {prefix}{label}{suffix}")


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------

def _changed_keys(existing: dict[str, Any], desired: dict[str, Any], keys: list[str]) -> list[str]:
    """Return the subset of keys where existing and desired differ."""
    return [k for k in keys if existing.get(k) != desired.get(k)]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class SyncRunner:
    """
    Walks a ReleaseDBConfig and converges each resource via the API.

    Parameters
    ----------
    client:
        Configured ReleaseDBClient pointing at the target server.
    dry_run:
        When True, the runner makes only GET requests.  No data is written.
        Output shows what would change if dry_run were False.
    """

    def __init__(self, client: ReleaseDBClient, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run
        self.result = SyncResult()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, config: ReleaseDBConfig) -> SyncResult:
        mode = "dry-run" if self.dry_run else "apply"
        print(f"\n{_fmt('ReleaseDB Sync', _BOLD)} — {mode} — {config.team.slug}\n")

        self._validate_environment_refs(config)

        self._sync_team(config.team)

        for rt in config.release_types:
            self._sync_release_type(config.team.slug, rt)

        self._print_summary()
        return self.result

    # ------------------------------------------------------------------
    # Summary output
    # ------------------------------------------------------------------

    def _print_summary(self) -> None:
        r = self.result
        parts = [
            _fmt(f"{r.creates} created", _GREEN if r.creates else _GREY),
            _fmt(f"{r.updates} updated", _BLUE if r.updates else _GREY),
            _fmt(f"{r.skips} unchanged", _GREY),
        ]
        print(f"\n  {',  '.join(parts)}")

        if r.errors:
            print()
            for err in r.errors:
                print(f"  {_fmt('✗', _RED)} {err}", file=sys.stderr)

        print()

    # ------------------------------------------------------------------
    # Change recording
    # ------------------------------------------------------------------

    def _record(self, action: str, label: str, changed_keys: list[str] | None = None) -> None:
        keys = changed_keys or []
        self.result.changes.append(Change(action=action, resource=label, changed_keys=keys))
        _print_change(action, label, keys, self.dry_run)

    # ------------------------------------------------------------------
    # Pre-flight: validate environment references
    # ------------------------------------------------------------------

    def _validate_environment_refs(self, config: ReleaseDBConfig) -> None:
        """Verify that any environment slugs referenced in validations exist."""
        slugs_to_check: set[str] = set()
        for rt in config.release_types:
            for vdef in rt.validations:
                if vdef.environment:
                    slugs_to_check.add(vdef.environment)

        for slug in sorted(slugs_to_check):
            env = self.client.get_environment(slug)
            if env is None:
                self.result.errors.append(
                    f"environment '{slug}' not found — create it before syncing"
                )

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def _sync_team(self, team: Any) -> None:
        payload: dict[str, Any] = {
            "slug": team.slug,
            "name": team.name,
            "contact_email": team.contact_email,
            "metadata": team.metadata,
        }

        existing = self.client.get_team(team.slug)

        if existing is None:
            if not self.dry_run:
                self.client.create_team(payload)
            self._record("create", f"team  {team.slug}")
        else:
            changed = _changed_keys(existing, payload, ["name", "contact_email", "metadata"])
            if changed:
                if not self.dry_run:
                    self.client.update_team(team.slug, payload)
                self._record("update", f"team  {team.slug}", changed)
            else:
                self._record("skip", f"team  {team.slug}")

    # ------------------------------------------------------------------
    # Release types
    # ------------------------------------------------------------------

    def _sync_release_type(self, team_slug: str, rt: ReleaseTypeConfig) -> None:
        payload: dict[str, Any] = {
            "slug": rt.slug,
            "team_slug": team_slug,
            "display_name": rt.display_name,
            "description": rt.description,
            "artifact_cardinality": rt.artifact_cardinality,
            "artifact_naming_regex": rt.artifact_naming_regex,
            "allowed_file_types": rt.allowed_file_types,
            "requires_approval": rt.requires_approval,
            "version_scheme": rt.version_scheme,
        }

        existing = self.client.get_release_type(rt.slug)

        if existing is None:
            if not self.dry_run:
                self.client.create_release_type(payload)
            self._record("create", f"  release_type  {rt.slug}")
        else:
            changed = _changed_keys(
                existing,
                payload,
                [
                    "display_name",
                    "description",
                    "artifact_cardinality",
                    "artifact_naming_regex",
                    "allowed_file_types",
                    "requires_approval",
                    "version_scheme",
                ],
            )
            if changed:
                if not self.dry_run:
                    self.client.update_release_type(rt.slug, payload)
                self._record("update", f"  release_type  {rt.slug}", changed)
            else:
                self._record("skip", f"  release_type  {rt.slug}")

        self._sync_fields(rt.slug, rt.fields)
        self._sync_validations(rt.slug, rt.validations)

    # ------------------------------------------------------------------
    # Field definitions
    # ------------------------------------------------------------------

    def _sync_fields(self, rt_slug: str, fields: list[FieldDef]) -> None:
        existing_map = {
            f["field_key"]: f for f in self.client.get_field_defs(rt_slug)
        }

        for order, fdef in enumerate(fields):
            payload: dict[str, Any] = {
                "field_key": fdef.key,
                "label": fdef.label,
                "field_type": fdef.type,
                "is_required": fdef.required,
                "enum_options": fdef.options,
                "validation_regex": fdef.validation_regex,
                "default_value": fdef.default_value,
                "display_order": order,
            }

            existing = existing_map.get(fdef.key)

            if existing is None:
                if not self.dry_run:
                    self.client.create_field_def(rt_slug, payload)
                self._record("create", f"    field  {fdef.key}")
            else:
                changed = _changed_keys(
                    existing,
                    payload,
                    [
                        "label",
                        "field_type",
                        "is_required",
                        "enum_options",
                        "validation_regex",
                        "default_value",
                    ],
                )
                if changed:
                    if not self.dry_run:
                        self.client.update_field_def(rt_slug, fdef.key, payload)
                    self._record("update", f"    field  {fdef.key}", changed)
                else:
                    self._record("skip", f"    field  {fdef.key}")

    # ------------------------------------------------------------------
    # Validation definitions
    # ------------------------------------------------------------------

    def _sync_validations(self, rt_slug: str, validations: list[ValidationDef]) -> None:
        existing_map = {
            v["name"]: v for v in self.client.get_validation_defs(rt_slug)
        }

        for order, vdef in enumerate(validations):
            payload: dict[str, Any] = {
                "name": vdef.name,
                "description": vdef.description,
                "runner_type": vdef.runner_type,
                "script_body": vdef.script_body,
                "script_url": vdef.script_url,
                "script_checksum": vdef.script_checksum,
                "runner_image": vdef.runner_image,
                "timeout_seconds": vdef.timeout_seconds,
                "env_vars": vdef.env_vars,
                "is_blocking": vdef.is_blocking,
                "on_failure": vdef.on_failure,
                "applies_to": vdef.applies_to,
                "run_order": vdef.run_order if vdef.run_order else order,
                "environment_slug": vdef.environment,
            }

            existing = existing_map.get(vdef.name)

            if existing is None:
                if not self.dry_run:
                    self.client.create_validation_def(rt_slug, payload)
                self._record("create", f"    validation  {vdef.name}")
            else:
                changed = _changed_keys(
                    existing,
                    payload,
                    [
                        "runner_type",
                        "script_url",
                        "script_checksum",
                        "runner_image",
                        "timeout_seconds",
                        "is_blocking",
                        "on_failure",
                        "applies_to",
                        "run_order",
                        "environment_slug",
                    ],
                )
                if changed:
                    if not self.dry_run:
                        self.client.update_validation_def(rt_slug, vdef.name, payload)
                    self._record("update", f"    validation  {vdef.name}", changed)
                else:
                    self._record("skip", f"    validation  {vdef.name}")
