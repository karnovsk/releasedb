"""
releasedb.validator.cli
~~~~~~~~~~~~~~~~~~~~~~~
Entry point for the `releasedb-validate` command.

Runs a validator script with dry-run support, so teams can test their
validation scripts locally without a live ReleaseDB API connection.

Usage
-----
    # Run a script against real ReleaseDB context (set via RELEASEDB_* env vars)
    releasedb-validate my_validator.py

    # Run locally with a synthetic context — no API token required
    releasedb-validate my_validator.py --dry-run \
        --release-name firmware-2024.03.1 \
        --version 2024.03.1 \
        --artifact-version 2024.03.1 \
        --files-dir ./test-artifacts/
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="releasedb-validate",
        description=(
            "Run a ReleaseDB validation script.\n\n"
            "In normal use RELEASEDB_* environment variables are injected by the\n"
            "runner container.  Use --dry-run for local development."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  releasedb-validate my_validator.py --dry-run \\\n"
            "      --release-name acme-2024.03.1 --version 2024.03.1 \\\n"
            "      --files-dir ./test-artifacts/\n"
        ),
    )

    parser.add_argument("script", help="Path to the validator script to execute.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Inject synthetic RELEASEDB_* variables and set RELEASEDB_DRY_RUN=1.\n"
            "Results are printed to stdout; nothing is sent to the API."
        ),
    )

    # Dry-run context overrides
    dry = parser.add_argument_group("dry-run context (used only with --dry-run)")
    dry.add_argument("--api-url", default="http://localhost:8000", metavar="URL")
    dry.add_argument("--release-name", default="dry-run-release", metavar="NAME")
    dry.add_argument("--version", default="0.0.0", metavar="VERSION")
    dry.add_argument("--artifact-version", default="0.0.0", metavar="VERSION")
    dry.add_argument("--files-dir", default=".", metavar="DIR")
    dry.add_argument("--team-slug", default="dry-run-team", metavar="SLUG")
    dry.add_argument("--environment", default="dev", metavar="SLUG")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    script = Path(args.script)
    if not script.exists():
        print(f"error: script not found: {script}", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()

    if args.dry_run:
        env.update(
            {
                "RELEASEDB_DRY_RUN": "1",
                "RELEASEDB_API_URL": args.api_url,
                "RELEASEDB_API_TOKEN": "dry-run",
                "RELEASEDB_RESULT_ID": "00000000-0000-0000-0000-000000000000",
                "RELEASEDB_RELEASE_ID": "00000000-0000-0000-0000-000000000001",
                "RELEASEDB_RELEASE_NAME": args.release_name,
                "RELEASEDB_RELEASE_VERSION": args.version,
                "RELEASEDB_RELEASE_STATUS": "validating",
                "RELEASEDB_ARTIFACT_ID": "00000000-0000-0000-0000-000000000002",
                "RELEASEDB_ARTIFACT_VERSION": args.artifact_version,
                "RELEASEDB_ARTIFACT_DIGEST": "sha256:0000000000000000",
                "RELEASEDB_ENVIRONMENT": args.environment,
                "RELEASEDB_TEAM_SLUG": args.team_slug,
                "RELEASEDB_FILES_DIR": str(Path(args.files_dir).resolve()),
            }
        )

    proc = subprocess.run([sys.executable, str(script)], env=env)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
