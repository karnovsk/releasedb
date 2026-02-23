# releasedb

Python SDK for [ReleaseDB](https://your-releasedb-instance) — query releases, submit artifacts, trigger validation, manage approvals and deployments.

The package provides two capabilities:

1. **Python client** — full API access via `ReleaseDBClient` (synchronous, `requests`-based).
2. **Validator SDK** (optional) — write validation scripts executed by the ReleaseDB runner. Only needed if ReleaseDB runs your scripts for you.

---

## Install

```bash
pip install releasedb
```

---

## Client quickstart

```python
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
    created_by="ci-pipeline",
    field_values={
        "expected_sha256": "a3f2b1c0...",
        "jira_ticket": "FW-1234",
    },
)

# Submit an artifact
artifact = client.submit_artifact(
    release_id=release.id,
    version="2.4.1",
    git_commit_sha="abc123",
    git_branch="main",
    build_id="jenkins-1234",
    files=[
        {
            "filename": "firmware.bin",
            "digest": "sha256:a3f2b1c0...",
            "size_bytes": 512000,
            "file_role": "primary",
            "storage_uri": "s3://my-bucket/fw/firmware.bin",
        }
    ],
)

# Trigger validation
run = client.trigger_validation(release.id, environment="staging")

# Submit approval
client.submit_approval(
    release.id,
    environment_id="<prod-env-id>",
    approver_identity="jane.doe@company.com",
    decision="approved",
    comment="All checks green.",
)

# Trigger deployment
deployment = client.trigger_deployment(
    release.id,
    environment="production",
    artifact_id=artifact.id,
    strategy="rolling",
    deployed_by="ci-pipeline",
)
```

---

## Client API reference

### `ReleaseDBClient(api_url, api_token)`

All methods raise `NotFoundError` for 404 responses and `APIError` for other non-2xx responses.

#### Teams

| Method | Description |
|--------|-------------|
| `list_teams()` | List all teams |
| `get_team(slug)` | Get a team by slug |
| `create_team(payload)` | Create a team |
| `update_team(slug, payload)` | Update a team |

#### Environments

| Method | Description |
|--------|-------------|
| `list_environments()` | List all environments |
| `get_environment(slug)` | Get an environment by slug |
| `create_environment(payload)` | Create an environment |
| `update_environment(slug, payload)` | Update an environment |

#### Release Types

| Method | Description |
|--------|-------------|
| `list_release_types(*, team_slug=None)` | List release types, optionally filtered |
| `get_release_type(slug)` | Get a release type by slug |
| `create_release_type(payload)` | Create a release type |
| `update_release_type(slug, payload)` | Update a release type |
| `get_field_defs(release_type_slug)` | List field definitions |
| `create_field_def(release_type_slug, payload)` | Add a field definition |
| `update_field_def(release_type_slug, field_key, payload)` | Update a field definition |
| `get_validation_defs(release_type_slug)` | List validation definitions |
| `create_validation_def(release_type_slug, payload)` | Add a validation definition |
| `update_validation_def(release_type_slug, name, payload)` | Update a validation definition |

#### Releases

| Method | Description |
|--------|-------------|
| `list_releases(*, team_slug=None, status=None, release_type_slug=None, limit=50, offset=0)` | List releases |
| `get_release(release_id)` | Get a release by ID |
| `create_release(*, release_type_config_id, release_name, version, ...)` | Create a release |
| `update_release(release_id, *, status=None, notes=None)` | Update a release |
| `get_release_events(release_id)` | Get the full audit trail for a release |

#### Artifacts

| Method | Description |
|--------|-------------|
| `get_artifact(artifact_id)` | Get an artifact by ID |
| `submit_artifact(*, release_id, version, ...)` | Submit an artifact with files and tools |
| `list_artifact_files(artifact_id)` | List files for an artifact |
| `add_artifact_file(artifact_id, payload)` | Add a file to an artifact |
| `list_artifact_tools(artifact_id)` | List tools used to build an artifact |
| `find_artifacts(*, release_id=None, tool_name=None, git_sha=None)` | Search artifacts |

#### Validation

| Method | Description |
|--------|-------------|
| `trigger_validation(release_id, *, environment)` | Start a validation run |
| `list_validation_runs(release_id)` | List validation runs for a release |
| `get_validation_run(run_id)` | Get a validation run by ID |
| `update_validation_result(result_id, payload)` | Update a validation result (used by validator scripts) |

#### Approvals & Deployments

| Method | Description |
|--------|-------------|
| `list_approvals(release_id)` | List approvals for a release |
| `submit_approval(release_id, *, environment_id, approver_identity, decision, comment=None)` | Submit an approval |
| `trigger_deployment(release_id, *, environment, artifact_id, strategy=None, deployed_by=None)` | Trigger a deployment |
| `get_deployment(deployment_id)` | Get a deployment by ID |
| `update_deployment_status(deployment_id, *, status)` | Update deployment status |

---

## (Optional) Validator SDK

> Only needed if ReleaseDB executes your validation scripts for you.
> If your team validates externally and reports results via `update_validation_result()`, skip this section.

### Quickstart

```python
# my_validator.py
from releasedb.validator import Validator
from releasedb.validator.checks import file_exists, checksum_matches, semver_valid

class FirmwareIntegrityCheck(Validator):
    name = "firmware-integrity-check"

    def validate(self):
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

**Exit codes:** 0 = pass or skipped, 1 = fail.

### Context object

```python
self.ctx.release.name                  # "firmware-2025-q2-drop3"
self.ctx.release.version               # "2.4.1"
self.ctx.release.environment           # "staging"
self.ctx.release.team_slug             # "firmware-team"
self.ctx.release.field("jira")         # custom field value (or None)
self.ctx.release.require_field("key")  # raises if missing

self.ctx.artifact.id                   # UUID
self.ctx.artifact.version              # "2.4.1"
self.ctx.artifact.digest               # "sha256:abc123..."
self.ctx.artifact.file("fw.bin")       # Path to pre-fetched file
self.ctx.artifact.files()              # [Path, ...] all pre-fetched files
```

### Built-in checks

| Check | What it does |
|-------|-------------|
| `file_exists(path)` | File is present and non-empty |
| `checksum_matches(path, digest)` | SHA256 (or md5/sha1) matches expected |
| `file_size_within(path, max_bytes)` | File does not exceed size limit |
| `extension_allowed(path, [".bin"])` | File extension in allowed set |
| `json_schema_valid(path, schema)` | JSON/YAML matches jsonschema |
| `no_snapshot_versions(path)` | No SNAPSHOT/dev/alpha deps in manifest |
| `http_healthy(url)` | HTTP endpoint returns expected status |
| `semver_valid(version)` | Version string follows semver |
| `version_bumped(current, previous)` | current > previous |
| `env_var_set(name)` | Environment variable is present |

### Control flow

```python
def validate(self):
    # Skip entirely (exit 0, status = skipped)
    if condition:
        self.skip("Reason")
        return

    # Abort immediately on a critical failure
    result = self.check(file_exists(binary))
    if result.failed():
        self.abort("Binary missing — cannot continue")

    # Inspect results inline
    r = self.check(checksum_matches(binary, expected))
    if r.failed():
        pass  # handle, then continue
```

### Local testing

Run without a live ReleaseDB instance:

```bash
releasedb-validate my_validator.py --dry-run \
    --release-name firmware-2025.03.1 \
    --version 2025.03.1 \
    --files-dir ./test-artifacts/
```

Or in Python:

```python
from releasedb.validator.context import ValidationContext

ctx = ValidationContext.for_dry_run(
    release_name="local-test",
    environment="staging",
    field_values={"expected_sha256": "abc123..."},
    files_dir="./test_artifacts",
)
FirmwareIntegrityCheck(ctx=ctx).run()
```

### Writing custom checks

```python
from releasedb.validator.reporting import CheckResult, ResultStatus

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

## CLI reference

| Command | Description |
|---------|-------------|
| `releasedb-sync [CONFIG]` | Sync a `releasedb.yaml` to the API. Add `--dry-run` to preview. |
| `releasedb-validate SCRIPT` | Run a validator script. Add `--dry-run` for local testing without a live API. |
