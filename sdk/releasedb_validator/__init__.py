"""
releasedb-validator
~~~~~~~~~~~~~~~~~~~
SDK for writing ReleaseDB validation scripts.

Quick start
-----------
    from releasedb_validator import Validator
    from releasedb_validator.checks import file_exists, checksum_matches
    from releasedb_validator.context import ValidationContext

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

from releasedb_validator.base import Validator
from releasedb_validator.context import ValidationContext
from releasedb_validator.reporting import CheckResult, ResultStatus, ValidationResult

__all__ = [
    "Validator",
    "ValidationContext",
    "CheckResult",
    "ResultStatus",
    "ValidationResult",
]

__version__ = "1.0.0"
