# ReleaseDB — User Guide

> Inter-team release management · configurable release types · user-supplied validation · artifact lineage

---

## Table of Contents

1. [Overview](#1-overview)
2. [Core Concepts](#2-core-concepts)
3. [Getting Started](#3-getting-started)
4. [Configuring Your Team's Release Type](#4-configuring-your-teams-release-type)
5. [Registering Artifacts from Jenkins](#5-registering-artifacts-from-jenkins)
6. [Creating a Release](#6-creating-a-release)
7. [Writing Validation Scripts](#7-writing-validation-scripts)
8. [Registering Validation Scripts](#8-registering-validation-scripts)
9. [Running Validation](#9-running-validation)
10. [Approvals](#10-approvals)
11. [Deployment](#11-deployment)
12. [Artifact Lineage & Toolchain Tracking](#12-artifact-lineage--toolchain-tracking)
13. [Local Development & Testing](#13-local-development--testing)
14. [API Reference](#14-api-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Overview

ReleaseDB is an internal release management platform that gives every team a single place to:

- **Register build artifacts** with full provenance (git commit, CI run, build tools used)
- **Define their own release schema** — some teams ship one file, others ship many; each team configures their own fields
- **Run configurable validation** — teams supply their own validation scripts; ReleaseDB executes them and records results
- **Coordinate cross-team releases** — approvals, environment promotion, and a complete audit trail

ReleaseDB does **not** replace Jenkins, Artifactory, or S3. It sits above them as the coordination and audit layer.

```
Jenkins builds → artifacts stored in S3/Artifactory/NFS
                        ↓
              ReleaseDB tracks identity, provenance,
              validation results, approvals, deployments
```

---

## 2. Core Concepts

### Release Type Config
Each team defines a **release type config** once. It specifies:
- What fields a release must carry (e.g. `jira_ticket`, `expected_sha256`, `target_hw_revision`)
- Whether releases need approval before deployment
- The versioning scheme (semver, calver, or sequential)
- What file types are allowed

### Artifact
A versioned build output, linked to a specific git commit and CI run. An artifact can have one or many files depending on the team's config. Every artifact records which **tools** (and at what git version) were used to build it.

### Release
A named, versioned release instance. It references an artifact, carries the team's custom metadata fields, and moves through a lifecycle: `draft → validating → approved → deploying → deployed`.

### Validation Definition
A user-supplied script registered against a release type + environment. ReleaseDB executes it in a Docker container and records the result. Exit 0 = pass. Anything else = fail.

### Environment
A deployment target (e.g. `dev`, `staging`, `production`) with an optional promotion tier and approval requirement.

---

## 3. Getting Started

### Prerequisites
- Access to the ReleaseDB API (ask your platform team for the URL and a token)
- A Jenkins pipeline for your service
- The `releasedb-shared` Jenkins library loaded in your `Jenkinsfile`

### Install the validator SDK (for writing validation scripts)
```bash
pip install releasedb-validator
```

### Verify API access
```bash
curl -H "Authorization: Bearer $RELEASEDB_TOKEN" \
  https://releasedb.internal/api/teams
```

---

## 4. Configuring Your Team's Release Type

This is done once by a team admin, either via the UI or the API.

### Via the API

**Step 1 — Create the release type config**

```bash
curl -X POST https://releasedb.internal/api/release-type-configs \
  -H "Authorization: Bearer $RELEASEDB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "<your-team-id>",
    "slug": "firmware-drop",
    "display_name": "Firmware Release",
    "artifact_cardinality": "multi",
    "allowed_file_types": [".bin", ".sha256", ".md"],
    "requires_approval": true,
    "version_scheme": "semver"
  }'
```

**Step 2 — Define custom fields**

Each field your team needs to track on a release gets its own row:

```bash
# Required field: Jira ticket
curl -X POST https://releasedb.internal/api/release-type-field-defs \
  -d '{
    "release_type_config_id": "<config-id>",
    "field_key": "jira_ticket",
    "label": "Jira Ticket",
    "field_type": "string",
    "is_required": true,
    "validation_regex": "^[A-Z]+-[0-9]+$",
    "display_order": 1
  }'

# Required field: expected SHA256 for integrity check
curl -X POST https://releasedb.internal/api/release-type-field-defs \
  -d '{
    "release_type_config_id": "<config-id>",
    "field_key": "expected_sha256",
    "label": "Expected SHA256",
    "field_type": "string",
    "is_required": true,
    "display_order": 2
  }'

# Optional field: target hardware revision
curl -X POST https://releasedb.internal/api/release-type-field-defs \
  -d '{
    "release_type_config_id": "<config-id>",
    "field_key": "target_hw_revision",
    "label": "Target HW Revision",
    "field_type": "enum",
    "enum_options": ["A1", "B2", "C3"],
    "is_required": false,
    "display_order": 3
  }'
```

**Available field types:** `string`, `number`, `file`, `enum`, `bool`, `date`

---

## 5. Registering Artifacts from Jenkins

Use the `releasedb-shared` Jenkins library. It handles file upload to S3/Artifactory and metadata registration in one call.

### Single-file artifact
```groovy
@Library('releasedb-shared') _

pipeline {
  stages {
    stage('Build') {
      steps {
        sh 'make firmware.bin'
      }
    }

    stage('Register Artifact') {
      steps {
        script {
          def artifactId = releasedb.registerArtifact(
            releaseTypeSlug: 'firmware-drop',
            version: env.BUILD_VERSION,
            files: ['build/firmware.bin'],
            gitCommit: env.GIT_COMMIT,
            gitBranch: env.BRANCH_NAME,
            buildUrl: env.BUILD_URL,
            tools: [
              [slug: 'gcc',   version: '13.2.0', gitSha: 'abc123'],
              [slug: 'cmake', version: '3.28.1', gitSha: 'def456'],
            ]
          )
          // Store for downstream stages
          env.RELEASEDB_ARTIFACT_ID = artifactId
        }
      }
    }
  }
}
```

### Multi-file artifact
```groovy
releasedb.registerArtifact(
  releaseTypeSlug: 'ml-model-release',
  version: env.MODEL_VERSION,
  files: [
    'dist/model.pt',
    'dist/model.sha256',
    'dist/config.yaml',
    'dist/CHANGELOG.md',
  ],
  gitCommit: env.GIT_COMMIT,
  gitBranch: env.BRANCH_NAME,
  buildUrl: env.BUILD_URL,
  tools: [
    [slug: 'pytorch', version: '2.1.0', gitSha: 'ghi789'],
    [slug: 'python',  version: '3.11.4', gitSha: 'jkl012'],
  ]
)
```

### What happens internally
1. Files are uploaded to S3 or Artifactory (based on file type and team config)
2. SHA256 digest is computed for each file
3. A combined `manifest_digest` is computed across all files
4. `artifacts`, `artifact_files`, and `artifact_tools` rows are created
5. The `artifact_id` UUID is returned for use in release creation

---

## 6. Creating a Release

Once an artifact is registered, create a release against it.

### Via the API

```bash
curl -X POST https://releasedb.internal/api/releases \
  -H "Authorization: Bearer $RELEASEDB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "release_type_config_id": "<config-id>",
    "release_name": "firmware-2025-q2-drop3",
    "version": "2.4.1",
    "artifact_id": "<artifact-id>",
    "target_date": "2025-06-30",
    "notes": "Adds support for HW revision B2. Fixes thermal throttling bug.",
    "field_values": {
      "jira_ticket": "FW-1234",
      "expected_sha256": "a3f2b1c0...",
      "target_hw_revision": "B2"
    }
  }'
```

ReleaseDB will validate:
- All required fields are present
- Field types match the definition (enum values, regex patterns, etc.)
- The artifact belongs to the correct release type

The release starts in `draft` status.

### Release lifecycle

```
draft → validating → approved → deploying → deployed
                  ↘                       ↘
                  failed               cancelled
```

---

## 7. Writing Validation Scripts

Validation scripts use the `releasedb-validator` Python SDK. Install it:

```bash
pip install releasedb-validator
```

### Minimal example

```python
from releasedb_validator import Validator
from releasedb_validator.checks import file_exists, checksum_matches

class IntegrityCheck(Validator):
    name = "integrity-check"

    def validate(self):
        binary = self.ctx.artifact.file("firmware.bin")
        expected = self.ctx.release.require_field("expected_sha256")

        self.check(file_exists(binary))
        self.check(checksum_matches(binary, expected))

if __name__ == "__main__":
    IntegrityCheck().run()
```

**The contract:** exit 0 = pass, anything else = fail. The SDK handles this automatically.

### Available context

Inside `validate()`, `self.ctx` gives you:

```python
# Release metadata
self.ctx.release.name              # "firmware-2025-q2-drop3"
self.ctx.release.version           # "2.4.1"
self.ctx.release.environment       # "staging"
self.ctx.release.team_slug         # "firmware-team"
self.ctx.release.field("key")      # custom field value (or None)
self.ctx.release.require_field("key")  # custom field value (raises if missing)

# Artifact metadata
self.ctx.artifact.version          # "2.4.1"
self.ctx.artifact.digest           # "sha256:abc123..."
self.ctx.artifact.file("name.bin") # Path to a pre-fetched file
self.ctx.artifact.files()          # [Path, ...] all pre-fetched files
```

### Built-in checks

| Check | Purpose |
|---|---|
| `file_exists(path)` | File is present and non-empty |
| `checksum_matches(path, digest)` | SHA256 (or md5/sha1) matches expected |
| `file_size_within(path, max_bytes)` | File does not exceed size limit |
| `extension_allowed(path, [".bin"])` | Extension in allowed set |
| `json_schema_valid(path, schema)` | JSON/YAML matches a jsonschema schema |
| `no_snapshot_versions(path)` | No SNAPSHOT/dev/alpha deps in a manifest |
| `http_healthy(url)` | HTTP endpoint returns expected status |
| `semver_valid(version)` | Version is valid semver |
| `version_bumped(current, previous)` | current > previous |
| `env_var_set(name)` | Environment variable is present |

### Control flow

```python
def validate(self):
    # Skip entirely — exits 0 with status "skipped"
    if self.ctx.release.environment == "dev":
        self.skip("Not enforced in dev")
        return

    # Abort on critical failure — records FAIL and stops immediately
    result = self.check(file_exists(binary))
    if result.failed():
        self.abort("Binary missing — cannot continue")

    # Downgrade a failure to a warning for non-critical checks
    result = self.check(file_exists(changelog))
    if result.failed():
        result.status = ResultStatus.WARN
```

### Writing custom checks

Any function returning a `CheckResult` works:

```python
from releasedb_validator.reporting import CheckResult, ResultStatus

def elf_header_valid(path) -> CheckResult:
    magic = open(path, "rb").read(4)
    if magic == b"\x7fELF":
        return CheckResult(name="elf_header", status=ResultStatus.PASS,
                           message="Valid ELF binary")
    return CheckResult(name="elf_header", status=ResultStatus.FAIL,
                       message=f"Invalid ELF magic: {magic!r}")

# In your validator:
self.check(elf_header_valid(self.ctx.artifact.file("firmware.bin")))
```

---

## 8. Registering Validation Scripts

Once your script is written and tested, upload it to S3 and register it in ReleaseDB.

### Step 1 — Upload to S3

```bash
aws s3 cp my_validator.py \
  s3://releasedb-scripts/firmware-team/integrity-check.py

# Compute the checksum (ReleaseDB verifies this before executing)
sha256sum my_validator.py
# → a3f2b1c0... my_validator.py
```

### Step 2 — Register with ReleaseDB

```bash
curl -X POST https://releasedb.internal/api/validation-definitions \
  -H "Authorization: Bearer $RELEASEDB_TOKEN" \
  -d '{
    "release_type_config_id": "<config-id>",
    "environment_id": null,
    "name": "firmware-integrity-check",
    "description": "Verifies binary presence, SHA256 digest, and semver version",
    "runner_type": "docker",
    "runner_image": "python:3.11-slim",
    "script_url": "s3://releasedb-scripts/firmware-team/integrity-check.py",
    "script_checksum": "sha256:a3f2b1c0...",
    "timeout_seconds": 120,
    "is_blocking": true,
    "on_failure": "block",
    "applies_to": "artifact",
    "run_order": 1
  }'
```

**Key fields:**
- `environment_id: null` — runs for all environments. Set to a specific env ID to restrict.
- `is_blocking: true` — a failure prevents the release from proceeding.
- `on_failure: "block" | "warn" | "notify"` — what happens on failure.
- `run_order` — controls execution sequence when multiple scripts are registered.

### Updating a script

When you update your script, re-upload to S3 and update the registration with the new checksum:

```bash
curl -X PATCH https://releasedb.internal/api/validation-definitions/<id> \
  -d '{
    "script_url": "s3://releasedb-scripts/firmware-team/integrity-check-v2.py",
    "script_checksum": "sha256:newchecksum..."
  }'
```

> **Security note:** ReleaseDB verifies `script_checksum` before every execution. If the file in S3 has been modified without updating the registration, the validation run will fail with a checksum error.

---

## 9. Running Validation

### Trigger manually

```bash
curl -X POST \
  "https://releasedb.internal/api/releases/<release-id>/validate?environment=staging" \
  -H "Authorization: Bearer $RELEASEDB_TOKEN"
```

### Trigger automatically

Set `trigger_type: "auto"` in your release type config to trigger validation automatically when a release is created or promoted to a new environment.

### What happens

1. A `validation_runs` row is created
2. All active `validation_definitions` for this release type + environment are queued
3. Each script runs in its `runner_image` container with:
   - Artifact files pre-fetched to `RELEASEDB_FILES_DIR`
   - All `RELEASEDB_*` env vars injected
   - Custom release field values available as `RELEASEDB_FIELD_<KEY>`
4. Results are written to `validation_results` with stdout, stderr, exit code, and structured evidence
5. If any blocking script fails, the release status transitions to `failed`

### Viewing results

```bash
curl https://releasedb.internal/api/releases/<release-id>/validation-runs \
  -H "Authorization: Bearer $RELEASEDB_TOKEN"
```

---

## 10. Approvals

Environments with `requires_approval: true` need explicit sign-off before deployment.

### Submitting an approval

```bash
curl -X POST https://releasedb.internal/api/releases/<release-id>/approvals \
  -H "Authorization: Bearer $RELEASEDB_TOKEN" \
  -d '{
    "environment_id": "<prod-env-id>",
    "decision": "approved",
    "comment": "Validated on staging. All checks green. Signed off by firmware lead."
  }'
```

**Decisions:** `approved` | `rejected` | `deferred`

### Multi-team approvals

If multiple teams need to sign off, each submits their own approval record. The release will not proceed until all required teams have approved. Teams are notified via the contact details in their `teams.metadata` (Slack, email, etc.).

---

## 11. Deployment

Once validated and approved, trigger deployment:

```bash
curl -X POST \
  "https://releasedb.internal/api/releases/<release-id>/deploy?environment=production" \
  -H "Authorization: Bearer $RELEASEDB_TOKEN" \
  -d '{
    "strategy": "rolling",
    "deployed_by": "jane.doe@company.com"
  }'
```

**Strategies:** `rolling` | `blue-green` | `canary`

ReleaseDB fires a webhook to your Jenkins deploy job with the artifact's `storage_uri`. Jenkins deploys and calls back to update the deployment status.

### Rollback

A rollback is modelled as a new deployment with `rollback_of` pointing to the original:

```bash
curl -X POST \
  "https://releasedb.internal/api/releases/<release-id>/deploy?environment=production" \
  -d '{
    "strategy": "rolling",
    "rollback_of": "<original-deployment-id>"
  }'
```

This keeps the full deployment chain queryable — you can always see what was deployed, when, by whom, and whether it was a rollback.

---

## 12. Artifact Lineage & Toolchain Tracking

### Querying which tools built an artifact

```bash
curl https://releasedb.internal/api/artifacts/<artifact-id>/tools \
  -H "Authorization: Bearer $RELEASEDB_TOKEN"
```

Returns:
```json
[
  { "tool": "gcc",   "version": "13.2.0", "git_commit_sha": "abc123" },
  { "tool": "cmake", "version": "3.28.1", "git_commit_sha": "def456" }
]
```

### Finding all artifacts built with a specific tool commit

Useful after a toolchain compromise — find every artifact that used a specific tool at a specific commit:

```bash
curl "https://releasedb.internal/api/artifacts?tool_slug=gcc&git_sha=abc123" \
  -H "Authorization: Bearer $RELEASEDB_TOKEN"
```

### Audit trail

Every state change is recorded in `release_events` with actor, timestamp, and before/after payload. The full history of a release is always available:

```bash
curl https://releasedb.internal/api/releases/<release-id>/events
```

---

## 13. Local Development & Testing

### Run your validator locally without a ReleaseDB instance

```python
from releasedb_validator import ValidationContext

if __name__ == "__main__":
    ctx = ValidationContext.for_dry_run(
        release_name="local-test",
        environment="staging",
        artifact_version="2.4.1",
        files_dir="./test_artifacts",        # local directory with test files
        field_values={
            "jira_ticket": "FW-1234",
            "expected_sha256": "abc123...",
        }
    )
    FirmwareIntegrityCheck(ctx=ctx).run()
```

Or use the environment variable:
```bash
RELEASEDB_DRY_RUN=1 python my_validator.py
```

In dry-run mode, results are printed to stdout but **not** sent to the API.

### Unit testing your validator

```python
import time
from releasedb_validator.context import ValidationContext
from releasedb_validator.reporting import ResultStatus

def test_passes_with_valid_binary(tmp_path):
    binary = tmp_path / "firmware.bin"
    binary.write_bytes(b"valid firmware data")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()

    ctx = ValidationContext.for_dry_run(
        files_dir=tmp_path,
        field_values={"expected_sha256": digest}
    )
    v = FirmwareIntegrityCheck(ctx=ctx)
    v._start_time = time.monotonic()
    v.validate()
    result = v._aggregate(duration_ms=0)

    assert result.status == ResultStatus.PASS
```

Run tests with:
```bash
cd sdk/
pytest tests/ -v
```

---

## 14. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/teams` | List teams |
| `POST` | `/api/release-type-configs` | Create release type config |
| `POST` | `/api/release-type-field-defs` | Add field to a release type |
| `POST` | `/api/validation-definitions` | Register a validation script |
| `PATCH` | `/api/validation-definitions/:id` | Update a validation script |
| `POST` | `/api/artifacts` | Register an artifact |
| `GET` | `/api/artifacts/:id/tools` | List tools used to build an artifact |
| `POST` | `/api/releases` | Create a release |
| `GET` | `/api/releases/:id` | Get release details |
| `POST` | `/api/releases/:id/validate` | Trigger validation |
| `GET` | `/api/releases/:id/validation-runs` | List validation runs |
| `POST` | `/api/releases/:id/approvals` | Submit an approval |
| `POST` | `/api/releases/:id/deploy` | Trigger deployment |
| `GET` | `/api/releases/:id/events` | Get full audit trail |

All endpoints require `Authorization: Bearer <token>`.

---

## 15. Troubleshooting

**Validation fails with "checksum mismatch on script"**
The script in S3 was modified after registration. Re-upload the script and update `script_checksum` via `PATCH /api/validation-definitions/:id`.

**`require_field()` raises a ValueError**
The field key doesn't match what's defined in `release_type_field_defs`. Check the key spelling (it's lowercased) and ensure the field value was included when the release was created.

**Artifact files not found in `RELEASEDB_FILES_DIR`**
The runner pre-fetches files before executing your script. If a file is missing, it was not registered in `artifact_files`. Check the artifact registration step in Jenkins — ensure all expected files are listed in the `files` array.

**Release stuck in `validating`**
One or more validation jobs may have timed out or failed to report back. Check `/api/releases/:id/validation-runs` for runs with `status: "running"` and an old `started_at`. Contact the platform team if a run appears hung.

**`RELEASEDB_DRY_RUN` has no effect in production**
Dry-run mode is controlled by the `RELEASEDB_DRY_RUN` environment variable. The ReleaseDB runner does not inject this variable — it is only for local development. Do not set it in your `validation_definitions.env_vars`.

---

*For questions or to report issues, contact the platform team or open a ticket in the `RDBX` Jira project.*
