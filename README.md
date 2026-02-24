# ReleaseDB

Inter-team release management · configurable release types · user-supplied validation · release lineage tracking.

ReleaseDB sits above Jenkins, Artifactory, and S3. It tracks identity, provenance, validation results, approvals, and deployments — without replacing any of them.

---

## Repository Structure

```
releasedb/
├── docs/
│   ├── USER_GUIDE.md          ← End-to-end usage guide
│   ├── SYNC.md                ← Config-as-code setup guide (releasedb-sync)
│   └── executive-overview.html ← Executive presentation (open in browser)
├── schema/
│   ├── SCHEMA.md              ← ER diagram (renders in GitHub / VS Code)
│   ├── schema_v3.html         ← Interactive schema reference (open in browser)
│   └── schema.sql             ← Executable PostgreSQL DDL
├── api/
│   ├── main.py                ← FastAPI application entrypoint
│   ├── database.py            ← asyncpg connection pool
│   ├── dependencies.py        ← Auth and DB injection
│   ├── models/                ← Pydantic request/response models
│   └── routers/               ← One file per resource group
├── sdk/
│   ├── releasedb/             ← Python package source
│   │   ├── client.py          ← ReleaseDBClient (full API access)
│   │   ├── models.py          ← Pydantic response models
│   │   ├── exceptions.py      ← APIError, NotFoundError
│   │   ├── validator/         ← Optional validator SDK
│   │   └── sync/              ← releasedb-sync tool (config-as-code)
│   ├── migrations/            ← Alembic database migrations
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── examples/              ← Example validation scripts
│   ├── tests/                 ← SDK unit tests (no live DB required)
│   ├── pyproject.toml
│   └── README.md              ← SDK quickstart and API reference
├── tests/                     ← API integration tests (requires Postgres)
├── docker/
│   └── init-test-db.sql       ← Creates releasedb_test on first container start
├── docker-compose.yml         ← Local Postgres (dev + test databases)
├── pytest.ini                 ← pytest configuration
└── releasedb.template.yaml    ← Team config template (copy and edit)
```

---

## Quick Links

| Document | What it covers |
|---|---|
| [User Guide](docs/USER_GUIDE.md) | Configuring release types, registering artifacts, writing validators, running validation, approvals, deployments |
| [Sync Guide](docs/SYNC.md) | Config-as-code setup with `releasedb-sync` — YAML schema, CLI reference, Jenkins integration |
| [Schema (ER diagram)](schema/SCHEMA.md) | Mermaid ER diagram — all 15 tables and their relationships |
| [Schema (interactive)](https://karnovsk.github.io/releasedb/schema/schema_v3.html) | Navigable, layered schema reference — open in a browser |
| [Schema (DDL)](schema/schema.sql) | Executable PostgreSQL DDL — the source of truth for the database |
| [SDK README](sdk/README.md) | Python package quickstart and API reference |
| [Executive Overview](https://karnovsk.github.io/releasedb/docs/executive-overview.html) | 10-slide presentation: problem, capabilities, stakeholders, current state, open decisions |

---

## Team Onboarding — Config-as-Code

Team configuration (release types, custom fields, validation scripts) lives in a
`releasedb.yaml` file in your repository. The `releasedb-sync` command reads it
and upserts the configuration to the ReleaseDB API.

```bash
# 1. Copy the template
cp releasedb.template.yaml ./releasedb.yaml

# 2. Edit: set your team slug, define release types, fields, and validators
$EDITOR releasedb.yaml

# 3. Preview what would change (no writes)
export RELEASEDB_API_URL=https://releasedb.internal
releasedb-sync --dry-run

# 4. Apply
export RELEASEDB_API_TOKEN=tok_...
releasedb-sync
```

See the [Sync Guide](docs/SYNC.md) for the full YAML schema reference, Jenkins
integration examples, and the team onboarding checklist.

---

## SDK Install

```bash
pip install releasedb
```

The `releasedb` package provides two capabilities:

1. **Python client** — query releases, submit artifacts, trigger validation, manage approvals and deployments via `ReleaseDBClient`.
2. **Validator SDK** (optional) — write validation scripts executed by the ReleaseDB runner. Only needed if ReleaseDB runs your validation scripts for you.

### Python Client Quickstart

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
    field_values={"expected_sha256": "abc123...", "jira_ticket": "FW-1234"},
)

# Submit an artifact from CI
artifact = client.submit_artifact(
    release_id=release.id,
    version="2.4.1",
    git_commit_sha="abc123",
    git_branch="main",
    build_id="jenkins-1234",
    files=[
        {
            "filename": "firmware.bin",
            "digest": "sha256:...",
            "size_bytes": 512000,
            "file_role": "primary",
            "storage_uri": "s3://my-bucket/fw/firmware.bin",
        }
    ],
)

# Trigger validation
run = client.trigger_validation(release.id, environment="staging")
```

See the [SDK README](sdk/README.md) for the full client API reference.

### (Optional) Writing a Validation Script

> Validation scripts are **optional**. Your team may validate in your own environment
> and report results via the API, or skip validation entirely if your release type
> doesn't require it.

```python
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
```

### Testing a Validator Locally

```bash
# Run against a local directory of test artifacts — no live API required
releasedb-validate my_validator.py --dry-run \
    --release-name firmware-2024.03.1 \
    --version 2024.03.1 \
    --files-dir ./test-artifacts/
```

---

## Local Development

### 1. Start Postgres

A single Docker container serves both the dev database (`releasedb`) and the
integration test database (`releasedb_test`). Both are created automatically on
first start.

```bash
docker compose up -d
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
# source .venv/bin/activate     # macOS / Linux

pip install --upgrade pip setuptools
pip install -r api/requirements.txt
pip install -e "sdk/.[dev]"
pip install -r tests/requirements.txt
```

### 3. Apply migrations to the dev database

```bash
DATABASE_URL=postgresql+psycopg2://releasedb:releasedb@localhost/releasedb \
  alembic -c sdk/migrations/alembic.ini upgrade head
```

### 4. Start the API server

```bash
DATABASE_URL=postgresql://releasedb:releasedb@localhost/releasedb \
  RELEASEDB_API_TOKEN=devtoken \
  uvicorn api.main:app --reload
```

Interactive API docs available at `http://localhost:8000/docs`.

---

## Running Tests

### Unit tests (no database required)

```bash
pytest sdk/tests/ -v
```

### Integration tests (requires Postgres via `docker compose up -d`)

```bash
pytest tests/ -v
```

The integration test suite automatically runs Alembic migrations against
`releasedb_test` before the first test, and truncates all tables between tests
so each test starts with a clean database. The dev database is not affected.

To use a different test database:

```bash
TEST_DATABASE_URL=postgresql://user:pass@host/mydb pytest tests/ -v
```

---

## CLI Reference

| Command | Description |
|---|---|
| `releasedb-sync [CONFIG]` | Sync a `releasedb.yaml` to the API. Add `--dry-run` to preview. |
| `releasedb-validate SCRIPT` | Run a validator script. Add `--dry-run` for local testing without a live API. |

---

## Open Items

### 1. Marking releases as canonical

Releases move through a lifecycle (`draft → validating → approved → deploying → deployed`), but there is no way to mark a specific release as "the blessed version for this product" independently of its lifecycle status — for example, to designate `v2.4.1` as the current stable release while `v2.5.0-rc1` is still in validation.

Potential approaches:

- **Flag on `releases`** — add `is_canonical boolean DEFAULT false`. Simple; queryable. Requires a convention for when to set it and whether only one release per team/type can be canonical at a time.
- **Separate `release_tags` table** — a named tag (e.g. `stable`, `lts`, `latest`) pointing to a release. More flexible; supports multiple named pointers (GA, LTS, latest) and allows external systems to pull by stable name.
- **Rely on `releases.status = 'deployed'`** — treat the most recently deployed release as implicitly canonical. No schema change; may be sufficient for simple cases.

Decision needed: is this a display/query concern (filter by deployed releases) or does it need a first-class schema concept? The answer depends on whether external systems (registries, deployment tools, release notes pages) need to resolve "the current release" by a stable name independently of deployment status.

---

### 2. Release and lineage dashboard

A read-only web view showing existing releases, their provenance, lineage chains, and validation status.

**Off-the-shelf options to evaluate:**

| Tool | Fit | Notes |
|---|---|---|
| **Retool** | High | Connects directly to PostgreSQL; drag-and-drop tables, lineage tree via custom component; no frontend code needed; hosted or self-hosted |
| **Metabase** | Medium | Strong for tabular views and filters; limited for graph/tree visualisation of lineage |
| **Grafana** | Medium | Good dashboards for time-series validation metrics; not designed for relational record browsing |
| **Superset** | Medium | SQL-driven; good for aggregate views, weak on record-level drill-down |
| **Bespoke (FastAPI + HTMX)** | High control | ~300 lines for a read-only release browser; full control over lineage tree rendering; no JS framework needed |

Minimum viable view: release list (filterable by team, release type, status) → release detail (provenance, artifacts, validation results, lineage chain). Retool covers this in a day; a bespoke view takes a sprint but is fully ownable.
