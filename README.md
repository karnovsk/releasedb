# releasedb

Inter-team release management · configurable release types · user-supplied validation · artifact lineage tracking.

## Repository Structure

```
releasedb/
├── docs/
│   └── USER_GUIDE.md          ← Start here
├── schema/
│   └── schema_v3.html         ← Interactive database schema (open in browser)
└── sdk/
    ├── releasedb_validator/   ← Python package source
    ├── examples/              ← Example validation scripts
    ├── tests/                 ← Unit tests
    ├── pyproject.toml
    └── README.md              ← SDK-specific docs
```

## Quick Links

- **[User Guide](docs/USER_GUIDE.md)** — how to configure release types, register artifacts, write validators, run validation, approve and deploy
- **[Schema](schema/schema_v3.html)** — open in a browser for the interactive, navigable database schema
- **[SDK README](sdk/README.md)** — Python package quickstart and API reference

## SDK Install

```bash
pip install releasedb-validator
```

## Writing a Validation Script

```python
from releasedb_validator import Validator
from releasedb_validator.checks import file_exists, checksum_matches

class MyValidator(Validator):
    name = "my-check"

    def validate(self):
        binary = self.ctx.artifact.file("app.bin")
        digest = self.ctx.release.require_field("expected_sha256")
        self.check(file_exists(binary))
        self.check(checksum_matches(binary, digest))

if __name__ == "__main__":
    MyValidator().run()
```

## Running Tests

```bash
cd sdk/
pip install -e ".[dev]"
pytest tests/ -v
```
