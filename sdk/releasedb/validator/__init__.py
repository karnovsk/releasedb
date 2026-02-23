"""
releasedb.validator
~~~~~~~~~~~~~~~~~~~
Optional validator SDK for writing ReleaseDB validation scripts.

This sub-package is optional — teams that validate in their own environment
do not need to import from here. Use it only if you want ReleaseDB to
execute your validation scripts in the runner container.

Quick start
-----------
    from releasedb.validator import Validator
    from releasedb.validator.checks import file_exists, checksum_matches
    from releasedb.validator.context import ValidationContext

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

from releasedb.validator.base import Validator
from releasedb.validator.context import ValidationContext
from releasedb.validator.reporting import CheckResult, ResultStatus, ValidationResult

__all__ = [
    "Validator",
    "ValidationContext",
    "CheckResult",
    "ResultStatus",
    "ValidationResult",
]
