# Config-as-Code — `releasedb-sync`

ReleaseDB configuration is managed as a YAML file that lives in your team's
repository. A CLI tool (`releasedb-sync`) reads the file and upserts the
configuration to the ReleaseDB API.

This keeps all team configuration in git — reviewed, diffed, and auditable —
without requiring a bespoke admin web UI for low-frequency setup tasks.

---

## Table of Contents

1. [Quick start](#quick-start)
2. [Getting the tool](#getting-the-tool)
3. [The `releasedb.yaml` file](#the-releasedbyaml-file)
   - [team](#team)
   - [release\_types](#release_types)
   - [fields](#fields)
   - [validations](#validations)
4. [Field type reference](#field-type-reference)
5. [Validation runner reference](#validation-runner-reference)
6. [CLI reference](#cli-reference)
7. [Environment variables](#environment-variables)
8. [Jenkins integration](#jenkins-integration)
9. [Dry-run workflow](#dry-run-workflow)
10. [Change semantics — what sync will and won't do](#change-semantics)
11. [First-time team onboarding checklist](#first-time-team-onboarding-checklist)

---

## Quick start

```bash
# 1. Copy the template
cp /path/to/releasedb.template.yaml ./releasedb.yaml

# 2. Edit your team details, release types, fields, and validators
$EDITOR releasedb.yaml

# 3. Preview what sync would do (no writes)
export RELEASEDB_API_URL=https://releasedb.internal
releasedb-sync --dry-run

# 4. Apply
export RELEASEDB_API_TOKEN=tok_...
releasedb-sync
```

Example output:

```
ReleaseDB Sync — apply — platform-eng

  + team  platform-eng
  + release_type  firmware-drop
  +   field  expected_sha256
  +   field  target_hw_revision
  +   field  jira_ticket
  +   validation  firmware-integrity-check
  +   validation  jira-ticket-open-check

  3 created,  0 updated,  0 unchanged
```

---

## Getting the tool

`releasedb-sync` is included in the `releasedb-validator` package.

```bash
# Install with pip
pip install releasedb-validator

# Or install the dev extras (includes alembic, psycopg2-binary)
pip install "releasedb-validator[dev]"

# Verify installation
releasedb-sync --help
```

---

## The `releasedb.yaml` file

A complete `releasedb.yaml` has two top-level keys: `team` and `release_types`.

```yaml
team:
  slug: platform-eng
  name: Platform Engineering
  contact_email: platform@company.com
  metadata:
    slack_channel: "#platform-releases"

release_types:
  - slug: firmware-drop
    display_name: Firmware Release
    ...
```

One file per team. One team block per file.

### `team`

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `slug` | string | yes | URL-safe identifier. **Never change after first sync** — it is the primary key everywhere. |
| `name` | string | yes | Human-readable team name shown in the UI. |
| `contact_email` | string | no | Distribution email for release notifications. |
| `metadata` | mapping | no | Arbitrary key/value pairs. Supported keys: `slack_channel`, `pagerduty_service`. |

### `release_types`

A list of release type configs. Each entry describes a category of releases
your team creates: what artifacts they contain, what metadata they carry, and
which validators must pass before they can be approved.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slug` | string | — | Unique across the org. Used in API paths and `RELEASEDB_*` env vars. |
| `display_name` | string | — | Human-readable name. |
| `description` | string | — | What kinds of releases this type covers. |
| `artifact_cardinality` | `single` \| `multi` | `single` | `single`: one artifact per release. `multi`: many artifacts (e.g. multi-arch). |
| `artifact_naming_regex` | string | — | Optional regex the artifact version string must match. |
| `allowed_file_types` | list of strings | — | Permitted extensions, e.g. `[".jar", ".whl"]`. Omit for any. |
| `requires_approval` | boolean | `true` | If true, releases must be approved before deployment. |
| `version_scheme` | `semver` \| `calver` \| `seq` | `semver` | Version scheme enforced on `release.version`. |
| `fields` | list | `[]` | Custom metadata fields. See [fields](#fields). |
| `validations` | list | `[]` | Validation scripts. See [validations](#validations). |

### `fields`

Custom metadata fields appear on the release creation form and are injected
into validator scripts as `RELEASEDB_FIELD_<KEY>` environment variables.

```yaml
fields:
  - key: expected_sha256
    label: Expected SHA-256
    type: string
    required: true
    validation_regex: "^[0-9a-f]{64}$"

  - key: target_hw_revision
    label: Target HW Revision
    type: enum
    required: true
    options: [rev-a, rev-b, rev-c]
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `key` | string | — | `snake_case` identifier. Becomes `RELEASEDB_FIELD_<KEY>` (uppercased) in validator env. |
| `label` | string | — | UI display name shown in forms and reports. |
| `type` | see [Field type reference](#field-type-reference) | — | Data type. |
| `required` | boolean | `false` | If true, releases cannot be submitted without this field. |
| `options` | list of strings | — | Required when `type: enum`. Lists the allowed values. |
| `validation_regex` | string | — | Optional regex applied to `string` and `enum` values client-side. |
| `default_value` | string | — | Pre-filled value shown in the release creation form. |

### `validations`

Validation scripts run before a release can be approved.

```yaml
validations:
  - name: firmware-integrity-check
    description: Verifies file presence and SHA-256 digest.
    runner_type: docker
    runner_image: my-registry/firmware-validator:1.2.0
    script_url: s3://my-bucket/validators/firmware_validator.py
    script_checksum: "sha256:aabbcc..."
    applies_to: artifact
    is_blocking: true
    on_failure: block
    timeout_seconds: 120
    run_order: 10
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | — | Unique within this release type. Shown in reports and logs. |
| `description` | string | — | What this validator checks. |
| `runner_type` | `shell` \| `python` \| `docker` \| `webhook` | — | How the script is executed. |
| `script_body` | string | — | Inline script source. Use for short scripts only. |
| `script_url` | string | — | S3 URI, git path, or HTTPS URL to the script. |
| `script_checksum` | string | — | `sha256:<hex>` of the script. **Required when `script_url` is set.** |
| `runner_image` | string | — | Docker image. **Required when `runner_type: docker`.** |
| `timeout_seconds` | integer | `300` | Max wall-clock seconds before the run is marked `timeout`. Range: 10–3600. |
| `env_vars` | mapping | — | Extra env vars injected at runtime, on top of standard `RELEASEDB_*` vars. |
| `is_blocking` | boolean | `true` | If true, a FAIL result prevents the release from advancing. |
| `on_failure` | `block` \| `warn` \| `notify` | `block` | What happens on non-zero exit. See below. |
| `applies_to` | `release` \| `artifact` \| `file` | `release` | Scope of the validation. |
| `run_order` | integer | `0` | Execution sequence. Lower numbers run first. Ties run in declaration order. |
| `environment` | string | — | Environment slug this validator applies to. Omit to run in **all** environments. |

**`on_failure` values:**

| Value | Behaviour |
|-------|-----------|
| `block` | Run fails → release halted (only meaningful when `is_blocking: true`) |
| `warn` | Failure recorded in the run report; release continues regardless |
| `notify` | Failure triggers a notification (Slack/email); release continues |

**`applies_to` values:**

| Value | Runs |
|-------|------|
| `release` | Once per release |
| `artifact` | Once per artifact in the release |
| `file` | Once per file in each artifact |

---

## Field type reference

| Type | YAML value | Description | `options` required |
|------|-----------|-------------|-------------------|
| String | `string` | Free-form text | No |
| Number | `number` | Numeric value (integer or float) | No |
| File | `file` | File upload reference | No |
| Enum | `enum` | One value from a fixed list | **Yes** |
| Boolean | `bool` | `true` or `false` | No |
| Date | `date` | ISO 8601 date (`2024-03-15`) | No |

---

## Validation runner reference

### `runner_type: docker`

```yaml
runner_type: docker
runner_image: my-registry/my-validator:1.0.0
script_url: s3://my-bucket/validators/my_validator.py
script_checksum: "sha256:..."
```

- The ReleaseDB runner pulls `runner_image` and executes the script inside it.
- Standard `RELEASEDB_*` environment variables are injected automatically.
- The script is downloaded from `script_url` and its digest verified against
  `script_checksum` before execution.

### `runner_type: python`

Runs the script with the Python interpreter on the runner host (no container).
Useful for lightweight validators that don't need isolated environments.

### `runner_type: shell`

Runs the script with `/bin/sh`. Suitable for simple checks or wrappers.

### `runner_type: webhook`

POSTs a JSON payload to `script_url`. The webhook must return HTTP 2xx for
PASS, HTTP 4xx/5xx for FAIL. Response body is captured as evidence.

### Computing `script_checksum`

```bash
# Linux / macOS
sha256sum validators/my_validator.py
# → aabbcc... validators/my_validator.py

# Format for the YAML:
script_checksum: "sha256:aabbcc..."
```

---

## CLI reference

### `releasedb-sync`

```
Usage: releasedb-sync [CONFIG] [OPTIONS]

Arguments:
  CONFIG    Path to the config file (default: releasedb.yaml)

Options:
  --dry-run           Preview changes without writing anything
  --api-url URL       ReleaseDB API base URL (env: RELEASEDB_API_URL)
  --api-token TOKEN   Bearer token for API auth (env: RELEASEDB_API_TOKEN)
  -h, --help          Show this message and exit
```

### `releasedb-validate`

```
Usage: releasedb-validate SCRIPT [OPTIONS]

Arguments:
  SCRIPT    Path to the validator script to execute

Options:
  --dry-run                 Inject synthetic RELEASEDB_* vars. No API calls made.
  --api-url URL             (dry-run) API URL to inject
  --release-name NAME       (dry-run) Release name to inject
  --version VERSION         (dry-run) Release version to inject
  --artifact-version VER    (dry-run) Artifact version to inject
  --files-dir DIR           (dry-run) Directory containing artifact files
  --team-slug SLUG          (dry-run) Team slug to inject
  --environment SLUG        (dry-run) Environment slug to inject
```

---

## Environment variables

### Required for `releasedb-sync`

| Variable | Description |
|----------|-------------|
| `RELEASEDB_API_URL` | Base URL of the ReleaseDB API, e.g. `https://releasedb.internal` |
| `RELEASEDB_API_TOKEN` | Bearer token with admin write access. Not required for `--dry-run`. |

### Injected into validator scripts by the runner

| Variable | Description |
|----------|-------------|
| `RELEASEDB_API_URL` | Base URL for result reporting |
| `RELEASEDB_API_TOKEN` | Bearer token for result reporting |
| `RELEASEDB_RESULT_ID` | UUID of the `validation_results` row to write outcome to |
| `RELEASEDB_RELEASE_ID` | UUID of the release being validated |
| `RELEASEDB_RELEASE_NAME` | Human-readable release name |
| `RELEASEDB_RELEASE_VERSION` | Release version string |
| `RELEASEDB_RELEASE_STATUS` | Current release status |
| `RELEASEDB_ARTIFACT_ID` | UUID of the artifact |
| `RELEASEDB_ARTIFACT_VERSION` | Artifact version |
| `RELEASEDB_ARTIFACT_DIGEST` | Manifest digest of the artifact |
| `RELEASEDB_ENVIRONMENT` | Target environment slug |
| `RELEASEDB_TEAM_SLUG` | Owning team slug |
| `RELEASEDB_FILES_DIR` | Local directory where artifact files are pre-fetched |
| `RELEASEDB_FIELD_<KEY>` | Custom release field values (key uppercased) |
| `RELEASEDB_DRY_RUN` | `"1"` when running locally without reporting back |

---

## Jenkins integration

### Setup pipeline (runs once, or on PR to `releasedb.yaml`)

```groovy
// Jenkinsfile.releasedb-setup
pipeline {
    agent { label 'python3' }

    triggers {
        // Re-run whenever releasedb.yaml changes on main
        pollSCM('H/5 * * * *')
    }

    stages {
        stage('Validate config') {
            steps {
                sh 'pip install releasedb-validator --quiet'
                sh '''
                    releasedb-sync --dry-run \
                        --api-url $RELEASEDB_API_URL
                '''
            }
        }

        stage('Apply config') {
            when { branch 'main' }
            steps {
                withCredentials([string(credentialsId: 'releasedb-admin-token',
                                        variable: 'RELEASEDB_API_TOKEN')]) {
                    sh '''
                        releasedb-sync \
                            --api-url  $RELEASEDB_API_URL \
                            --api-token $RELEASEDB_API_TOKEN
                    '''
                }
            }
        }
    }
}
```

**Tip:** Set up this pipeline to trigger only when `releasedb.yaml` changes,
not on every commit, by using a path filter or a separate `Jenkinsfile.setup`.

### Main CI pipeline (registers artifacts and triggers validation)

```groovy
// Jenkinsfile  — main build + release pipeline
pipeline {
    agent { label 'python3' }

    stages {
        stage('Build') { ... }

        stage('Register artifact') {
            steps {
                withCredentials([string(credentialsId: 'releasedb-token',
                                        variable: 'RELEASEDB_API_TOKEN')]) {
                    sh '''
                        curl -sf -X POST $RELEASEDB_API_URL/api/artifacts \
                            -H "Authorization: Bearer $RELEASEDB_API_TOKEN" \
                            -H "Content-Type: application/json" \
                            -d "{
                              \"release_type_slug\": \"firmware-drop\",
                              \"version\":           \"$BUILD_VERSION\",
                              \"git_commit_sha\":    \"$GIT_COMMIT\",
                              \"git_branch\":        \"$GIT_BRANCH\",
                              \"build_id\":          \"$BUILD_NUMBER\",
                              \"build_url\":         \"$BUILD_URL\"
                            }"
                    '''
                }
            }
        }

        stage('Validate') {
            steps {
                // ReleaseDB triggers the validation run and streams results back
                sh '''
                    curl -sf -X POST $RELEASEDB_API_URL/api/validation-runs \
                        -H "Authorization: Bearer $RELEASEDB_API_TOKEN" \
                        -H "Content-Type: application/json" \
                        -d "{\"release_name\": \"$RELEASE_NAME\", \"environment\": \"staging\"}"
                '''
            }
        }
    }
}
```

---

## Dry-run workflow

`--dry-run` is safe to run at any time — it makes only GET requests.

Recommended workflow for config changes:

```
1. Edit releasedb.yaml
2. releasedb-sync --dry-run        ← review the diff
3. Open a PR / code review
4. After merge: releasedb-sync     ← apply on main
```

The dry-run output uses symbols to indicate what would happen:

```
  + team  platform-eng              # would create
  ~ release_type  firmware-drop     # would update (changed: display_name)
  · field  expected_sha256          # no change
```

| Symbol | Meaning |
|--------|---------|
| `+` | Resource would be created |
| `~` | Resource would be updated (changed fields listed in brackets) |
| `·` | Resource is unchanged |

---

## Change semantics

### What sync WILL do

- **Create** any resource that doesn't exist in the API yet.
- **Update** any resource where at least one field has changed.
- **Skip** any resource that is already in sync with the YAML.

### What sync will NOT do

- **Delete** resources. Removing a release type, field, or validation from the
  YAML leaves the server-side record untouched. Deletions require explicit
  action via the ReleaseDB UI or API.
- **Rename** resources by changing a slug/key/name. Changing an identifier
  creates a NEW record; the old one is left in place.
- **Reorder** fields at runtime in ways that break existing releases. `display_order`
  is updated, but existing release field values are unaffected.

### Why no deletes?

- Deleting a validation definition that has existing `validation_results` rows
  linked to it would break the audit trail.
- Deleting a field def that has existing `release_field_values` would orphan
  historical data.
- Deletes are intentionally human-gated in the UI where the impact is visible.

---

## First-time team onboarding checklist

```
□ 1. Confirm your team slug is available
      releasedb-sync --dry-run --api-url https://releasedb.internal

□ 2. Confirm your environment slugs exist
      The platform team manages environments. Contact them if you need
      a new environment (e.g. "staging-eu") before referencing it.

□ 3. Upload your validator scripts to S3 (or equivalent)
      aws s3 cp validators/my_validator.py s3://my-bucket/validators/

□ 4. Compute and record script checksums
      sha256sum validators/my_validator.py

□ 5. Fill in releasedb.yaml, run --dry-run, fix any errors

□ 6. Open a PR for team review

□ 7. After merge, run releasedb-sync (apply)
      Or have the Jenkins setup pipeline do it automatically.

□ 8. Verify in the ReleaseDB UI that your team, release types, and
      validators appear correctly.

□ 9. Create a test release and trigger a validation run to confirm
      the end-to-end flow works.
```
