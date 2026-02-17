"""
releasedb_validator.reporting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Result model and the reporter that writes outcomes back to the ReleaseDB API.
Validation scripts never call the API directly — the base Validator class
handles this automatically via the reporter.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import requests


class ResultStatus(str, Enum):
    PASS    = "pass"
    FAIL    = "fail"
    WARN    = "warn"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Outcome of a single check within a validation script."""
    name: str
    status: ResultStatus
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def passed(self) -> bool:
        return self.status == ResultStatus.PASS

    def failed(self) -> bool:
        return self.status == ResultStatus.FAIL


@dataclass
class ValidationResult:
    """
    Aggregate result of a full validation script run.
    Maps directly to what gets written into validation_results.
    """
    status: ResultStatus
    checks: list[CheckResult] = field(default_factory=list)
    summary: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    @property
    def exit_code(self) -> int:
        return 0 if self.status in (ResultStatus.PASS, ResultStatus.WARN, ResultStatus.SKIPPED) else 1

    def to_api_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "evidence": {
                **self.evidence,
                "checks": [
                    {
                        "name": c.name,
                        "status": c.status.value,
                        "message": c.message,
                        "detail": c.detail,
                    }
                    for c in self.checks
                ],
                "summary": self.summary,
            },
            "duration_ms": self.duration_ms,
        }

    def print_summary(self) -> None:
        """Pretty-print result to stdout for CI logs."""
        icons = {
            ResultStatus.PASS:    "✓",
            ResultStatus.FAIL:    "✗",
            ResultStatus.WARN:    "⚠",
            ResultStatus.SKIPPED: "–",
        }
        print("\n── Validation Results ──────────────────────────────")
        for check in self.checks:
            icon = icons.get(check.status, "?")
            print(f"  {icon}  {check.name}: {check.message}")
            if check.detail:
                for k, v in check.detail.items():
                    print(f"       {k}: {v}")

        print(f"\n  Overall: {icons[self.status]} {self.status.value.upper()}")
        if self.summary:
            print(f"  {self.summary}")
        print("────────────────────────────────────────────────────\n")

        # Always emit structured JSON to stdout for evidence capture
        print("RELEASEDB_EVIDENCE:", json.dumps(self.to_api_payload()["evidence"]))


class Reporter:
    """
    Sends validation results back to the ReleaseDB API.
    In dry-run mode, only prints to stdout.
    """

    def __init__(self, api_url: str, api_token: str, result_id: str, dry_run: bool):
        self._api_url   = api_url.rstrip("/")
        self._api_token = api_token
        self._result_id = result_id
        self._dry_run   = dry_run

    def report(self, result: ValidationResult) -> None:
        result.print_summary()

        if self._dry_run:
            print("[dry-run] Would POST result to API — skipping.")
            return

        url = f"{self._api_url}/api/validation-results/{self._result_id}"
        payload = result.to_api_payload()

        try:
            resp = requests.patch(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            # Don't crash the script on reporting failure — the exit code
            # is already set correctly. Log and move on.
            print(f"[releasedb] WARNING: Failed to report result to API: {e}",
                  file=sys.stderr)
