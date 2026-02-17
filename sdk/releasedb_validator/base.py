"""
releasedb_validator.base
~~~~~~~~~~~~~~~~~~~~~~~~
The Validator base class. Teams subclass this, implement validate(),
and call run() as the script entrypoint.

Usage
-----
    from releasedb_validator import Validator
    from releasedb_validator.checks import file_exists, checksum_matches
    from releasedb_validator.reporting import ResultStatus

    class MyValidator(Validator):
        name = "firmware-integrity-check"

        def validate(self):
            binary = self.ctx.artifact.file("firmware.bin")
            expected_digest = self.ctx.release.require_field("expected_sha256")

            self.check(file_exists(binary))
            self.check(checksum_matches(binary, expected_digest))

    if __name__ == "__main__":
        MyValidator().run()
"""

from __future__ import annotations

import sys
import time
import traceback
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from releasedb_validator.context import ValidationContext
from releasedb_validator.reporting import (
    CheckResult,
    Reporter,
    ResultStatus,
    ValidationResult,
)

if TYPE_CHECKING:
    pass


class Validator(ABC):
    """
    Base class for all ReleaseDB validation scripts.

    Subclass this, set a `name`, implement `validate()`, then call `run()`.

    The `validate()` method should call `self.check()` for each individual
    check. Any check with status FAIL will cause the overall result to be FAIL.
    A check with status WARN will cause the overall result to be WARN (unless
    another check is FAIL). SKIP is informational only.

    To skip validation entirely based on a condition:
        def validate(self):
            if self.ctx.release.environment == "dev":
                self.skip("Skipping integrity checks in dev environment")
                return
            ...

    To fail immediately without running further checks:
        def validate(self):
            if not self.ctx.artifact.files():
                self.abort("No artifact files found — cannot validate")
            ...
    """

    # Override this in subclasses with a descriptive name
    name: str = "unnamed-validator"

    def __init__(self, ctx: ValidationContext | None = None):
        """
        Initialise the validator.

        Args:
            ctx: ValidationContext to use. If None, loads from environment
                 variables (production mode). Pass a context explicitly
                 for testing.
        """
        self.ctx: ValidationContext = ctx or ValidationContext.from_env()
        self._checks: list[CheckResult] = []
        self._skipped: bool = False
        self._skip_reason: str = ""
        self._start_time: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, result: CheckResult) -> CheckResult:
        """
        Record a check result. Returns the result so callers can inspect it
        inline if needed.

        Example:
            result = self.check(file_exists(path))
            if result.failed():
                self.abort("Critical file missing")
        """
        self._checks.append(result)
        status_symbol = {"pass": "✓", "fail": "✗", "warn": "⚠", "skipped": "–"}.get(
            result.status.value, "?"
        )
        print(f"  {status_symbol}  [{result.status.value.upper():7}] {result.name}: {result.message}")
        return result

    def skip(self, reason: str) -> None:
        """
        Mark this entire validation as skipped with a reason.
        Call this then return immediately from validate().
        """
        self._skipped = True
        self._skip_reason = reason
        print(f"  –  [SKIPPED] {reason}")

    def abort(self, reason: str) -> None:
        """
        Immediately fail validation with a reason, without running more checks.
        Raises _AbortValidation — do not catch this.
        """
        self._checks.append(CheckResult(
            name="abort",
            status=ResultStatus.FAIL,
            message=reason,
        ))
        raise _AbortValidation(reason)

    @abstractmethod
    def validate(self) -> None:
        """
        Implement your validation logic here.
        Call self.check() for each check you want to run.
        """

    def run(self) -> None:
        """
        Entrypoint. Calls validate(), aggregates results, reports back
        to the API, and exits with the appropriate exit code.

        Always call this as:
            if __name__ == "__main__":
                MyValidator().run()
        """
        reporter = Reporter(
            api_url=self.ctx.runner.api_url,
            api_token=self.ctx.runner.api_token,
            result_id=self.ctx.runner.result_id,
            dry_run=self.ctx.runner.dry_run,
        )

        print(f"\n── {self.name} ──────────────────────────────────────")
        print(f"   Release : {self.ctx.release.name} ({self.ctx.release.version})")
        print(f"   Artifact: {self.ctx.artifact.version} [{self.ctx.artifact.digest[:16]}…]")
        print(f"   Env     : {self.ctx.release.environment}")
        print(f"   Team    : {self.ctx.release.team_slug}")
        if self.ctx.runner.dry_run:
            print("   Mode    : DRY RUN")
        print()

        self._start_time = time.monotonic()

        try:
            self.validate()
        except _AbortValidation:
            pass  # checks already recorded
        except Exception as e:
            # Unhandled exception in validate() → FAIL with traceback
            self._checks.append(CheckResult(
                name="unhandled_exception",
                status=ResultStatus.FAIL,
                message=f"Unhandled exception: {type(e).__name__}: {e}",
                detail={"traceback": traceback.format_exc()},
            ))

        duration_ms = int((time.monotonic() - self._start_time) * 1000)
        result = self._aggregate(duration_ms)

        reporter.report(result)
        sys.exit(result.exit_code)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _aggregate(self, duration_ms: int) -> ValidationResult:
        if self._skipped:
            return ValidationResult(
                status=ResultStatus.SKIPPED,
                checks=[],
                summary=self._skip_reason,
                duration_ms=duration_ms,
            )

        if not self._checks:
            return ValidationResult(
                status=ResultStatus.WARN,
                checks=[],
                summary="No checks were run",
                duration_ms=duration_ms,
            )

        statuses = {c.status for c in self._checks}
        if ResultStatus.FAIL in statuses:
            overall = ResultStatus.FAIL
        elif ResultStatus.WARN in statuses:
            overall = ResultStatus.WARN
        else:
            overall = ResultStatus.PASS

        failed  = [c for c in self._checks if c.status == ResultStatus.FAIL]
        passed  = [c for c in self._checks if c.status == ResultStatus.PASS]
        warned  = [c for c in self._checks if c.status == ResultStatus.WARN]
        skipped = [c for c in self._checks if c.status == ResultStatus.SKIPPED]

        parts = [f"{len(passed)} passed"]
        if failed:  parts.append(f"{len(failed)} failed")
        if warned:  parts.append(f"{len(warned)} warned")
        if skipped: parts.append(f"{len(skipped)} skipped")
        summary = ", ".join(parts) + f" in {duration_ms}ms"

        return ValidationResult(
            status=overall,
            checks=self._checks,
            summary=summary,
            duration_ms=duration_ms,
        )


class _AbortValidation(Exception):
    """Internal signal raised by Validator.abort(). Not part of public API."""
