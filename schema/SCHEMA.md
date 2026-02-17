# ReleaseDB — Schema v3

Inter-team release management · configurable release types per team ·
user-supplied validation scripts · artifact lineage & toolchain tracking

## Entity-Relationship Diagram

```mermaid
erDiagram

    %% ── CONFIG LAYER ─────────────────────────────────────────────────────────

    teams {
        uuid    id          PK
        varchar slug        UK
        varchar name
        varchar contact_email
        jsonb   metadata
        tstz    created_at
    }

    environments {
        uuid    id          PK
        varchar slug        UK
        varchar name
        int2    tier
        bool    requires_approval
        jsonb   config
    }

    tools {
        uuid    id              PK
        varchar name            UK
        text    description
        varchar source
        text    repo_url
        uuid    owned_by_team_id FK
        bool    is_active
        tstz    created_at
    }

    release_type_configs {
        uuid    id                   PK
        uuid    team_id              FK
        varchar slug                 UK
        varchar display_name
        text    description
        varchar artifact_cardinality
        text    artifact_naming_regex
        text[]  allowed_file_types
        bool    requires_approval
        varchar version_scheme
        bool    is_active
        tstz    created_at
        tstz    updated_at
    }

    release_type_field_defs {
        uuid    id                     PK
        uuid    release_type_config_id FK
        varchar field_key
        varchar label
        varchar field_type
        bool    is_required
        text[]  enum_options
        text    validation_regex
        int2    display_order
        text    default_value
    }

    validation_definitions {
        uuid    id                     PK
        uuid    release_type_config_id FK
        uuid    environment_id         FK
        varchar name
        text    description
        varchar runner_type
        text    script_body
        text    script_url
        varchar script_checksum
        text    runner_image
        int     timeout_seconds
        jsonb   env_vars
        bool    is_blocking
        varchar on_failure
        varchar applies_to
        int2    run_order
        bool    is_active
        varchar created_by
        tstz    created_at
        tstz    updated_at
    }

    %% ── RELEASE LAYER ────────────────────────────────────────────────────────

    releases {
        uuid    id                     PK
        uuid    release_type_config_id FK
        uuid    owning_team_id         FK
        varchar release_name           UK
        varchar version
        varchar status
        date    target_date
        text    notes
        varchar created_by
        tstz    created_at
        tstz    updated_at
    }

    release_field_values {
        uuid    id           PK
        uuid    release_id   FK
        uuid    field_def_id FK
        text    value_text
        numeric value_number
        date    value_date
        jsonb   value_json
    }

    %% ── ARTIFACT LAYER ───────────────────────────────────────────────────────

    artifacts {
        uuid    id                     PK
        uuid    release_id             FK
        uuid    release_type_config_id FK
        varchar version
        varchar git_commit_sha
        varchar git_branch
        varchar build_id
        text    build_url
        varchar manifest_digest
        jsonb   sbom
        jsonb   labels
        tstz    built_at
        tstz    created_at
    }

    artifact_files {
        uuid    id           PK
        uuid    artifact_id  FK
        uuid    field_def_id FK
        varchar filename
        varchar file_role
        text    storage_uri
        varchar media_type
        varchar digest
        bigint  size_bytes
        text    signature
        tstz    uploaded_at
    }

    artifact_tools {
        uuid    id               PK
        uuid    artifact_id      FK
        uuid    tool_id          FK
        varchar tool_version
        varchar git_commit_sha
        varchar git_branch
        text    runner_image
        text    invocation_flags
        jsonb   metadata
    }

    %% ── VALIDATION LAYER ─────────────────────────────────────────────────────

    validation_runs {
        uuid    id             PK
        uuid    release_id     FK
        uuid    environment_id FK
        varchar triggered_by
        varchar trigger_type
        varchar status
        tstz    started_at
        tstz    finished_at
    }

    validation_results {
        uuid    id                PK
        uuid    run_id            FK
        uuid    validation_def_id FK
        uuid    artifact_id       FK
        varchar status
        int2    exit_code
        text    stdout
        text    stderr
        text    log_url
        jsonb   evidence
        int     duration_ms
        tstz    evaluated_at
    }

    %% ── WORKFLOW LAYER ───────────────────────────────────────────────────────

    approvals {
        uuid    id                PK
        uuid    release_id        FK
        uuid    environment_id    FK
        uuid    approving_team_id FK
        varchar approver_identity
        varchar decision
        text    comment
        tstz    decided_at
    }

    deployments {
        uuid    id             PK
        uuid    release_id     FK
        uuid    environment_id FK
        uuid    artifact_id    FK
        varchar status
        varchar strategy
        varchar deployed_by
        tstz    started_at
        tstz    finished_at
        uuid    rollback_of    FK
    }

    release_events {
        uuid    id             PK
        uuid    release_id     FK
        varchar event_type
        varchar actor_identity
        uuid    actor_team_id  FK
        jsonb   payload
        tstz    occurred_at
    }

    %% ── RELATIONSHIPS ────────────────────────────────────────────────────────

    teams                  ||--o{ release_type_configs      : owns
    teams                  ||--o{ tools                     : "owns (internal)"
    teams                  ||--o{ releases                  : "owns (releasing team)"
    teams                  ||--o{ approvals                 : "signs off"
    teams                  ||--o{ release_events            : "actor team"

    environments           ||--o{ validation_definitions    : "scopes (null = all)"
    environments           ||--o{ validation_runs           : targets
    environments           ||--o{ approvals                 : gates
    environments           ||--o{ deployments               : receives

    release_type_configs   ||--o{ release_type_field_defs   : defines
    release_type_configs   ||--o{ validation_definitions    : has
    release_type_configs   ||--o{ releases                  : types
    release_type_configs   ||--o{ artifacts                 : shapes

    release_type_field_defs ||--o{ release_field_values     : filled_by
    release_type_field_defs ||--o{ artifact_files           : "typed file slot"

    releases               ||--o{ release_field_values      : carries
    releases               ||--o{ artifacts                 : produces
    releases               ||--o{ validation_runs           : triggers
    releases               ||--o{ approvals                 : needs
    releases               ||--o{ deployments               : executes
    releases               ||--o{ release_events            : logs

    artifacts              ||--o{ artifact_files            : contains
    artifacts              ||--o{ artifact_tools            : "built with"
    artifacts              ||--o{ validation_results        : "validated by"
    artifacts              ||--o{ deployments               : deployed_as

    tools                  ||--o{ artifact_tools            : used_in

    validation_runs        ||--o{ validation_results        : spawns

    deployments            ||--o| deployments               : "rollback of"
```

## Layer Summary

| Layer | Tables | Purpose |
|---|---|---|
| **Config** | teams, environments, tools, release\_type\_configs, release\_type\_field\_defs, validation\_definitions | Static configuration owned by teams |
| **Release** | releases, release\_field\_values | Named release instances with custom metadata |
| **Artifact** | artifacts, artifact\_files, artifact\_tools | Build outputs with provenance and toolchain |
| **Validation** | validation\_runs, validation\_results | Script execution records and outcomes |
| **Workflow** | approvals, deployments, release\_events | Sign-off, deployment execution, audit log |

## Key Design Decisions

### Controlled tool vocabulary (`tools` + `artifact_tools`)
Build tools must be registered in `tools` before they can be referenced in
`artifact_tools`. This enforces consistent naming across all teams and makes
cross-artifact toolchain queries reliable.

### EAV for custom release fields (`release_type_field_defs` + `release_field_values`)
Teams define their own metadata fields per release type. Values are stored in a
type-split EAV table (`value_text / value_number / value_date / value_json`)
rather than a single untyped `text` column. Trade-off: queries joining many
custom fields are verbose but type-safe.

### `artifact_files` digest scoped to `(artifact_id, digest)`
The unique constraint is `(artifact_id, digest)`, not `digest` globally. The
same binary (e.g. a shared base image layer) may legitimately appear in multiple
separate artifacts.

### `release_events` is append-only
Enforced at the database level via `CREATE RULE`. Rows are never updated or
deleted — this is the authoritative audit trail.

### `deployments.rollback_of` self-reference
A rollback deployment points to the deployment it reverses, creating an explicit
rollback chain without a separate table.

## Implementation Notes

See [`schema.sql`](schema.sql) for the full executable DDL.
See [`../sdk/migrations/`](../sdk/migrations/) for Alembic migration scripts.

All `updated_at` columns are maintained automatically by the `set_updated_at()`
trigger function. Enum-like columns use `CHECK` constraints rather than
`CREATE TYPE` for easier evolution.
