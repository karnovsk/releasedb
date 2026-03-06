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
│   ├── routers/               ← One file per resource group
│   ├── migrations/            ← Alembic database migrations
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   └── tests/                 ← API integration tests (requires Postgres)
├── sdk/
│   ├── releasedb/             ← Python package source
│   │   ├── client.py          ← ReleaseDBClient (full API access)
│   │   ├── models.py          ← Pydantic response models
│   │   ├── exceptions.py      ← APIError, NotFoundError
│   │   ├── validator/         ← Optional validator SDK
│   │   └── sync/              ← releasedb-sync tool (config-as-code)
│   ├── examples/              ← Example validation scripts
│   ├── tests/                 ← SDK unit tests (no live DB required)
│   ├── pyproject.toml
│   └── README.md              ← SDK quickstart and API reference
├── ui/
│   ├── src/
│   │   ├── pages/             ← ReleasesPage, ReleaseDetailPage
│   │   ├── components/        ← StatusBadge and shared UI
│   │   ├── api/               ← Typed fetch wrapper
│   │   └── types.ts           ← Shared TypeScript interfaces
│   ├── vite.config.ts
│   └── package.json
├── scripts/                   ← Utility scripts (seed_demo.py, etc.)
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
| [Schema (ER diagram)](schema/SCHEMA.md) | Mermaid ER diagram — all 18 tables and their relationships |
| [Schema (interactive)](https://karnovsk.github.io/releasedb/schema/schema_v3.html) | Navigable, layered schema reference — open in a browser |
| [Schema (DDL)](schema/schema.sql) | Executable PostgreSQL DDL — the source of truth for the database |
| [SDK README](sdk/README.md) | Python package quickstart and API reference |
| [Executive Overview](https://karnovsk.github.io/releasedb/docs/executive-overview.html) | 10-slide presentation: problem, capabilities, stakeholders, current state, open decisions |

---

## Demo & Examples

| Resource | What it does | How to use |
|---|---|---|
| **[Seed script](scripts/seed_demo.py)** | Populates the DB with 3 teams, 3 envs, 2 projects, 14 releases, and a multi-level lineage graph | `python scripts/seed_demo.py` (API must be running) |
| **[Validator example](sdk/examples/firmware_validator.py)** | Full working validator: file existence, checksum, semver checks | Copy and adapt for your team's release type |
| **[Team config template](releasedb.template.yaml)** | Config-as-code YAML template with all options annotated | `cp releasedb.template.yaml releasedb.yaml`, then edit |
| **[Interactive schema](schema/schema_v3.html)** | Navigable HTML reference for all 18 DB tables | Open in browser |
| **[API docs](http://localhost:8000/docs)** | Auto-generated Swagger UI for all endpoints | Start the API server, then open in browser |

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

## SDK

```bash
pip install releasedb
```

The `releasedb` package provides a Python client, an optional validator SDK for writing validation scripts, and the `releasedb-sync` config-as-code CLI. See the **[SDK README](sdk/README.md)** for the full reference and examples.

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
pip install -r api/tests/requirements.txt
```

### 3. Apply migrations to the dev database

```bash
DATABASE_URL=postgresql+psycopg2://releasedb:releasedb@localhost/releasedb \
  alembic -c api/migrations/alembic.ini upgrade head
```

### 4. Start the API server

```bash
DATABASE_URL=postgresql://releasedb:releasedb@localhost/releasedb \
  RELEASEDB_API_TOKEN=devtoken \
  uvicorn api.main:app --reload
```

Interactive API docs available at `http://localhost:8000/docs`.

### 5. Seed demo data (optional)

Populate the database with a realistic multi-team dataset for exploring the UI:

```bash
python scripts/seed_demo.py
```

This creates:

| What | Detail |
|---|---|
| **Teams** | Platform Engineering, Backend Services, Firmware Team |
| **Environments** | dev (tier 1), staging (tier 2), prod (tier 3, requires approval) |
| **Projects** | Customer Portal, IoT Platform |
| **Release types** | backend-service, firmware-image, infra-module |
| **Releases** | 14 across all statuses — deployed, validating, approved, draft, failed, cancelled |

Releases are linked with dependencies to form a multi-level lineage graph, suitable for testing the DAG view in the Web UI.

The script requires the API to be running. Override the defaults with environment variables:

```bash
RELEASEDB_URL=http://localhost:8000 RELEASEDB_TOKEN=devtoken python scripts/seed_demo.py
```

> **Note:** The script does not check for existing data — run it against a freshly migrated database to avoid duplicate entries. To reset: `alembic downgrade base && alembic upgrade head` (see step 3).

### 6. Start the Web UI

```bash
cd ui
npm install
npm run dev
```

Open `http://localhost:5173` in a browser. The UI proxies API requests to `http://localhost:8000` automatically (configured in `vite.config.ts`).

---

## Web UI

ReleaseDB ships a read-only web dashboard built with Vite + React + AG Grid + React Flow.

**Releases table** — filterable, sortable grid showing all releases across teams. Columns: release name, project, version, status, owning team, target date. Click any row to open the detail view.

**Release detail** — tabbed view per release:
- **Details** — metadata, custom field values, project link
- **Artifacts** — build outputs with file provenance
- **Validation** — run history and per-check results
- **Approvals** — sign-off records per environment
- **Deployments** — deployment history and rollback chains
- **Events** — full audit log
- **Lineage** — interactive DAG showing upstream and downstream release dependencies (rendered with React Flow + Dagre layout)

---

## Running Tests

### Unit tests (no database required)

```bash
pytest sdk/tests/ -v
```

### Integration tests (requires Postgres via `docker compose up -d`)

```bash
pytest api/tests/ -v
```

The integration test suite automatically runs Alembic migrations against
`releasedb_test` before the first test, and truncates all tables between tests
so each test starts with a clean database. The dev database is not affected.

To use a different test database:

```bash
TEST_DATABASE_URL=postgresql://user:pass@host/mydb pytest api/tests/ -v
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

