"""
examples/firmware_validator.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Example validation script for a firmware team.
Demonstrates: file checks, checksum, size limit, custom field access.

Registration in ReleaseDB:
    runner_type: docker
    runner_image: python:3.11-slim
    script_url: s3://releasedb-scripts/firmware-team/integrity-check.py
    applies_to: artifact
    is_blocking: true
    timeout_seconds: 120
    env_vars: {}
"""

from releasedb_validator import Validator
from releasedb_validator.checks import (
    checksum_matches,
    extension_allowed,
    file_exists,
    file_size_within,
    no_snapshot_versions,
    semver_valid,
)

MAX_FIRMWARE_SIZE = 32 * 1024 * 1024  # 32 MB


class FirmwareIntegrityValidator(Validator):
    name = "firmware-integrity-check"

    def validate(self):
        ctx = self.ctx

        # Skip entirely in dev environment — we don't gate dev builds
        if ctx.release.environment == "dev":
            self.skip("Integrity checks not enforced in dev environment")
            return

        # Access a required custom release field
        expected_sha256 = ctx.release.require_field("expected_sha256")

        # The primary binary
        binary = ctx.artifact.file("firmware.bin")
        self.check(file_exists(binary))
        self.check(extension_allowed(binary, [".bin"]))
        self.check(file_size_within(binary, MAX_FIRMWARE_SIZE))
        self.check(checksum_matches(binary, expected_sha256))

        # Accompanying checksum file must also be present
        checksum_file = ctx.artifact.file("firmware.sha256")
        self.check(file_exists(checksum_file, label="checksum_file_present"))

        # Version must be valid semver
        self.check(semver_valid(ctx.artifact.version))

        # Optional: warn if a changelog is missing (non-blocking)
        changelog = ctx.artifact.file("CHANGELOG.md")
        result = self.check(file_exists(changelog, label="changelog_present"))
        # Note: file_exists returns FAIL if missing, but we only want a WARN here.
        # Override the status for non-critical checks:
        if result.failed():
            from releasedb_validator.reporting import ResultStatus
            result.status = ResultStatus.WARN  # degrade to warning


if __name__ == "__main__":
    FirmwareIntegrityValidator().run()
