"""
examples/java_service_validator.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Example validation script for a Java microservice team.
Demonstrates: JAR checks, no-snapshots, version bumped, HTTP health check.

Registration in ReleaseDB:
    runner_type: docker
    runner_image: python:3.11-slim
    script_url: s3://releasedb-scripts/platform-team/java-service-check.py
    applies_to: artifact
    is_blocking: true
    timeout_seconds: 60
"""

from releasedb_validator import Validator
from releasedb_validator.checks import (
    extension_allowed,
    file_exists,
    http_healthy,
    no_snapshot_versions,
    semver_valid,
    version_bumped,
)


class JavaServiceValidator(Validator):
    name = "java-service-prerelease-check"

    def validate(self):
        ctx = self.ctx

        jar = ctx.artifact.file(f"{ctx.release.field('service_name', 'app')}.jar")

        # JAR must be present and valid extension
        result = self.check(file_exists(jar))
        if result.failed():
            self.abort("JAR file not found — cannot continue validation")

        self.check(extension_allowed(jar, [".jar"]))

        # No SNAPSHOT dependencies allowed in staging or production
        pom = ctx.artifact.file("pom.xml")
        if pom.exists():
            self.check(no_snapshot_versions(pom))

        # Version must be valid semver and must be bumped from last release
        self.check(semver_valid(ctx.artifact.version))
        previous_version = ctx.release.field("previous_version")
        if previous_version:
            self.check(version_bumped(ctx.artifact.version, previous_version))

        # Health check: staging endpoint must be reachable before prod promotion
        if ctx.release.environment in ("staging", "production"):
            staging_url = ctx.release.field("staging_health_url")
            if staging_url:
                self.check(http_healthy(
                    staging_url,
                    expected_status=200,
                    label="staging_health_check",
                ))


if __name__ == "__main__":
    JavaServiceValidator().run()
