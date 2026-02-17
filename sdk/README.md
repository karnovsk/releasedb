# releasedb-validator

Python SDK for writing [ReleaseDB](https://your-releasedb-instance) validation scripts.

Instead of writing raw Python that parses env vars, calls the API, and manages exit codes,
you subclass `Validator`, implement `validate()`, and call `run()`. Everything else is handled.

---

## Install

```bash
pip install releasedb-validator
# or, pinned to a specific version for reproducible scripts:
pip install releasedb-validator==1.0.0
```

---

## Quickstart

```python
# my_validator.py
from releasedb_validator import Validator
from releasedb_validator.checks import file_exists, checksum_matches, semver_valid

class FirmwareIntegrityCheck(Validator):
    name = "firmware-integrity-check"

    def validate(self):
        # Skip non-blocking environments
        if self.ctx.release.environment == "dev":
            self.skip("Not enforced in dev")
            return

        binary = self.ctx.artifact.file("firmware.bin")
        expected = self.ctx.release.require_field("expected_sha256")

        self.check(file_exists(binary))
        self.check(checksum_matches(binary, expected))
        self.check(semver_valid(self.ctx.artifact.version))

if __name__ == "__main__":
    FirmwareIntegrityCheck().run()
```

**Exit codes:** 0 = pass or warn, 1 = fail. The runner reads this to set `validation_results.status`.

---

## Context object

`self.ctx` gives you everything injected by the runner:

```python
self.ctx.release.name              # "firmware-2025-q2-drop3"
self.ctx.release.version           # "2.4.1"
self.ctx.release.environment       # "staging"
self.ctx.release.team_slug         # "firmware-team"
self.ctx.release.field("jira")     # custom field value (or None)
self.ctx.release.require_field("x")# custom field value (raises if missing)

self.ctx.artifact.id               # UUID
self.ctx.artifact.version          # "2.4.1"
self.ctx.artifact.digest           # "sha256:abc123..."
self.ctx.artifact.file("fw.bin")   # Path to pre-fetched file
self.ctx.artifact.files()          # [Path, ...] all pre-fetched files
```

---

## Built-in checks

| Check | What it does |
|---|---|
| `file_exists(path)` | File is present and non-empty |
| `checksum_matches(path, digest)` | sha256 (or md5/sha1) matches expected |
| `file_size_within(path, max_bytes)` | File does not exceed size limit |
| `extension_allowed(path, [".bin"])` | File extension in allowed set |
| `json_schema_valid(path, schema)` | JSON/YAML matches jsonschema |
| `no_snapshot_versions(path)` | No SNAPSHOT/dev/alpha deps in manifest |
| `http_healthy(url)` | HTTP endpoint returns expected status |
| `semver_valid(version)` | Version string follows semver |
| `version_bumped(current, previous)` | current > previous |
| `env_var_set(name)` | Environment variable is present |

Every check returns a `CheckResult`. Pass it to `self.check()` to record it.

---

## Control flow

```python
def validate(self):
    # Skip everything (exit 0, status = skipped)
    if condition:
        self.skip("Reason")
        return

    # Abort immediately on a critical failure
    result = self.check(file_exists(binary))
    if result.failed():
        self.abort("Binary missing — cannot continue")  # records FAIL, stops

    # Inspect results inline
    r = self.check(checksum_matches(binary, expected))
    if r.failed():
        # do something extra, then continue
        pass
```

---

## Local development

Run your script locally without a ReleaseDB instance:

```python
if __name__ == "__main__":
    import sys

    if "--dry-run" in sys.argv:
        ctx = ValidationContext.for_dry_run(
            release_name="local-test",
            environment="staging",
            field_values={"expected_sha256": "abc123..."},
            files_dir="./test_artifacts",
        )
        FirmwareIntegrityCheck(ctx=ctx).run()
    else:
        FirmwareIntegrityCheck().run()
```

Or set the environment variable:
```bash
RELEASEDB_DRY_RUN=1 python my_validator.py
```

---

## Writing custom checks

A check is just a function that returns a `CheckResult`:

```python
from releasedb_validator.reporting import CheckResult, ResultStatus

def elf_header_valid(path) -> CheckResult:
    data = open(path, "rb").read(4)
    if data[:4] == b"\x7fELF":
        return CheckResult(name="elf_header", status=ResultStatus.PASS,
                           message="Valid ELF binary")
    return CheckResult(name="elf_header", status=ResultStatus.FAIL,
                       message=f"Invalid ELF magic bytes: {data!r}")

# In your validator:
self.check(elf_header_valid(binary))
```

---

## Testing your validator

```python
# test_my_validator.py
from releasedb_validator.context import ValidationContext
from releasedb_validator.reporting import ResultStatus

def test_passes_with_valid_artifact(tmp_path):
    binary = tmp_path / "firmware.bin"
    binary.write_bytes(b"valid firmware data")

    ctx = ValidationContext.for_dry_run(
        field_values={"expected_sha256": sha256_of(binary)},
        files_dir=tmp_path,
    )
    v = FirmwareIntegrityCheck(ctx=ctx)
    v._start_time = time.monotonic()
    v.validate()
    result = v._aggregate(duration_ms=0)

    assert result.status == ResultStatus.PASS
```

---

## How results flow to the database

```
validate() runs checks
       │
       ▼
_aggregate() → ValidationResult
       │
       ▼
Reporter.report() → PATCH /api/validation-results/{result_id}
       │                    ↓
       │             validation_results.status
       │             validation_results.evidence  ← structured check output
       │             validation_results.exit_code
       │             validation_results.stdout
       ▼
sys.exit(0 or 1)  ← picked up by runner
```

---

## Registering a script in ReleaseDB

```json
{
  "name": "firmware-integrity-check",
  "runner_type": "docker",
  "runner_image": "python:3.11-slim",
  "script_url": "s3://releasedb-scripts/firmware-team/validator.py",
  "script_checksum": "sha256:...",
  "applies_to": "artifact",
  "is_blocking": true,
  "timeout_seconds": 120,
  "env_vars": {}
}
```

The runner will:
1. Verify `script_checksum` before executing
2. Pre-fetch artifact files to `RELEASEDB_FILES_DIR`
3. Inject all `RELEASEDB_*` env vars
4. Execute the script in the `runner_image` container
5. Capture stdout/stderr and write to `validation_results`
