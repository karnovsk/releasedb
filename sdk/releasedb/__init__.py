"""
releasedb
~~~~~~~~~
Python SDK for the ReleaseDB release management system.

Primary entry points
--------------------
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
        field_values={"expected_sha256": "abc123..."},
    )

    # Submit an artifact
    artifact = client.submit_artifact(
        release_id=release.id,
        version="2.4.1",
        git_commit_sha="abc123",
        files=[{"filename": "firmware.bin", "digest": "sha256:...", ...}],
    )

Optional: writing validation scripts
-------------------------------------
    from releasedb.validator import Validator
    from releasedb.validator.checks import file_exists, checksum_matches

    class FirmwareIntegrityCheck(Validator):
        name = "firmware-integrity-check"

        def validate(self):
            binary = self.ctx.artifact.file("firmware.bin")
            digest = self.ctx.release.require_field("expected_sha256")
            self.check(file_exists(binary))
            self.check(checksum_matches(binary, digest))

    if __name__ == "__main__":
        FirmwareIntegrityCheck().run()
"""

from releasedb.client import ReleaseDBClient
from releasedb.exceptions import APIError, NotFoundError, ReleaseDBError, ValidationError
from releasedb.models import (
    ApprovalResponse,
    ArtifactFileResponse,
    ArtifactResponse,
    DeploymentResponse,
    EnvironmentResponse,
    ReleaseEventResponse,
    ReleaseResponse,
    ReleaseTypeResponse,
    TeamResponse,
    ValidationResultResponse,
    ValidationRunResponse,
)

__version__ = "2.0.0"

__all__ = [
    "ReleaseDBClient",
    # Exceptions
    "ReleaseDBError",
    "APIError",
    "NotFoundError",
    "ValidationError",
    # Response models
    "TeamResponse",
    "EnvironmentResponse",
    "ReleaseTypeResponse",
    "ReleaseResponse",
    "ArtifactResponse",
    "ArtifactFileResponse",
    "ValidationRunResponse",
    "ValidationResultResponse",
    "ApprovalResponse",
    "DeploymentResponse",
    "ReleaseEventResponse",
]
