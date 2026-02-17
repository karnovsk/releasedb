# ReleaseDB

Inter-team release management · configurable release types · user-supplied validation · artifact lineage tracking.

ReleaseDB sits above Jenkins, Artifactory, and S3. It tracks identity, provenance, validation results, approvals, and deployments — without replacing any of them.

---

## Repository Structure

```
releasedb/
├── docs/
│   ├── USER_GUIDE.md          ← End-to-end usage guide
│   └── SYNC.md                ← Config-as-code setup guide (releasedb-sync)
├── schema/
│   ├── SCHEMA.md              ← ER diagram (renders in GitHub / VS Code)
│   ├── schema_v3.html         ← Interactive schema reference (open in browser)
│   └── schema.sql             ← Executable PostgreSQL DDL
├── sdk/
│   ├── releasedb_validator/   ← Python package source
│   │   ├── sync/              ← releasedb-sync tool (config-as-code)
│   │   ├── checks/            ← Built-in validation checks
│   │   ├── context/           ← Runtime context (artifact, release, runner)
│   │   └── reporting/         ← Result models and API reporter
│   ├── migrations/            ← Alembic database migrations
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── examples/              ← Example validation scripts
│   ├── tests/                 ← Unit tests
│   ├── pyproject.toml
│   └── README.md              ← SDK quickstart and API reference
└── releasedb.template.yaml    ← Team config template (copy and edit)
```

---

## Quick Links

| Document | What it covers |
|---|---|
| [User Guide](docs/USER_GUIDE.md) | Configuring release types, registering artifacts, writing validators, running validation, approvals, deployments |
| [Sync Guide](docs/SYNC.md) | Config-as-code setup with `releasedb-sync` — YAML schema, CLI reference, Jenkins integration |
| [Schema (ER diagram)](schema/SCHEMA.md) | Mermaid ER diagram — all 15 tables and their relationships |
| [Schema (interactive)](schema/schema_v3.html) | Open in a browser for the navigable, layered schema reference |
| [Schema (DDL)](schema/schema.sql) | Executable PostgreSQL DDL — the source of truth for the database |
| [SDK README](sdk/README.md) | Python package quickstart and API reference |

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
pip install releasedb-validator
```

### Writing a Validation Script

```python
from releasedb_validator import Validator
from releasedb_validator.checks import file_exists, checksum_matches

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

## Database Setup

The schema targets PostgreSQL 13+.

```bash
# Apply via Alembic
cd sdk/
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg2://user:pass@localhost/releasedb
alembic -c migrations/alembic.ini upgrade head

# Or apply the DDL directly
psql releasedb < schema/schema.sql
```

---

## Running Tests

```bash
cd sdk/
pip install -e ".[dev]"
pytest tests/ -v
```

---

## CLI Reference

| Command | Description |
|---|---|
| `releasedb-sync [CONFIG]` | Sync a `releasedb.yaml` to the API. Add `--dry-run` to preview. |
| `releasedb-validate SCRIPT` | Run a validator script. Add `--dry-run` for local testing without a live API. |
