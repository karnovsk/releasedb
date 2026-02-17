"""
releasedb_validator.sync.cli
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Entry point for the `releasedb-sync` command.

Usage
-----
    releasedb-sync [CONFIG] [OPTIONS]

    # Preview changes without writing anything
    releasedb-sync releasedb.yaml --dry-run

    # Apply configuration
    releasedb-sync releasedb.yaml

Environment variables
---------------------
    RELEASEDB_API_URL    Base URL of the ReleaseDB API server
    RELEASEDB_API_TOKEN  Bearer token with admin write access

Both can be overridden by their corresponding CLI flags.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from .client import APIError, ReleaseDBClient
from .models import ReleaseDBConfig
from .runner import SyncRunner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="releasedb-sync",
        description=(
            "Sync a releasedb.yaml config file to the ReleaseDB API.\n\n"
            "Resources are NEVER deleted — removing a release type or field\n"
            "from the YAML leaves the server-side record untouched."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  releasedb-sync                          # sync ./releasedb.yaml\n"
            "  releasedb-sync --dry-run                # preview without writing\n"
            "  releasedb-sync path/to/my-config.yaml   # explicit file path\n"
        ),
    )

    parser.add_argument(
        "config",
        nargs="?",
        default="releasedb.yaml",
        metavar="CONFIG",
        help="Path to the config file (default: releasedb.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them. Safe to run in CI.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("RELEASEDB_API_URL"),
        metavar="URL",
        help="ReleaseDB API base URL (env: RELEASEDB_API_URL)",
    )
    parser.add_argument(
        "--api-token",
        default=os.environ.get("RELEASEDB_API_TOKEN"),
        metavar="TOKEN",
        help="Bearer token for API auth (env: RELEASEDB_API_TOKEN)",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------
    errors: list[str] = []

    if not args.api_url:
        errors.append(
            "--api-url (or RELEASEDB_API_URL) is required"
        )

    if not args.api_token and not args.dry_run:
        errors.append(
            "--api-token (or RELEASEDB_API_TOKEN) is required "
            "(or use --dry-run to skip authentication)"
        )

    config_path = Path(args.config)
    if not config_path.exists():
        errors.append(f"config file not found: {config_path}")

    if errors:
        for msg in errors:
            print(f"error: {msg}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Parse and validate YAML
    # ------------------------------------------------------------------
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"error: invalid YAML in {config_path}:\n  {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, dict):
        print(
            f"error: {config_path} must be a YAML mapping at the top level",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        config = ReleaseDBConfig.model_validate(raw)
    except ValidationError as exc:
        print(f"error: config validation failed in {config_path}:", file=sys.stderr)
        for err in exc.errors():
            loc = " → ".join(str(p) for p in err["loc"])
            print(f"  {loc}: {err['msg']}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Run sync
    # ------------------------------------------------------------------
    client = ReleaseDBClient(
        api_url=args.api_url,
        api_token=args.api_token or "dry-run-no-token",
    )
    runner = SyncRunner(client=client, dry_run=args.dry_run)

    try:
        result = runner.run(config)
    except APIError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
