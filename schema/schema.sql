-- =============================================================================
-- ReleaseDB  —  PostgreSQL Schema  v3
-- =============================================================================
-- Table creation order respects FK dependencies.
-- All enum-like columns use CHECK constraints (easier to evolve than CREATE TYPE).
-- All FK columns have explicit indexes (PostgreSQL does not create them automatically).
-- updated_at columns are maintained by the set_updated_at() trigger.
-- release_events is append-only, enforced via RULE.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Utility trigger function — keeps updated_at current on every UPDATE
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


-- =============================================================================
-- CONFIG LAYER
-- =============================================================================

-- ---------------------------------------------------------------------------
-- teams
-- Organisational units. Each team owns release type configs and internal tools.
-- ---------------------------------------------------------------------------
CREATE TABLE teams (
    id            uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          varchar(80)  NOT NULL UNIQUE,          -- e.g. "platform-eng"
    name          varchar(120) NOT NULL,
    contact_email varchar(255),
    metadata      jsonb,                                  -- Slack channel, PD service, etc.
    created_at    timestamptz  NOT NULL DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- environments
-- Target deployment environments, ordered by promotion tier.
-- ---------------------------------------------------------------------------
CREATE TABLE environments (
    id                uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              varchar(60)  NOT NULL UNIQUE,       -- "dev" / "staging" / "prod"
    name              varchar(120) NOT NULL,
    tier              smallint     NOT NULL DEFAULT 0,    -- 0 = lowest (dev)
    requires_approval boolean      NOT NULL DEFAULT false,
    config            jsonb                               -- cluster, region, etc.
);


-- ---------------------------------------------------------------------------
-- tools
-- Controlled vocabulary of build tools. The only way to register a tool name
-- for use in artifact_tools — enforces spelling consistency across the org.
-- ---------------------------------------------------------------------------
CREATE TABLE tools (
    id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    name             varchar(120) NOT NULL UNIQUE,        -- e.g. "gcc", "protoc"
    description      text,
    source           varchar(20)  NOT NULL
                         CHECK (source IN ('internal', 'external', 'vendored')),
    repo_url         text,                                -- canonical source repo
    owned_by_team_id uuid         REFERENCES teams(id) ON DELETE SET NULL,
    is_active        boolean      NOT NULL DEFAULT true,
    created_at       timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX ON tools (owned_by_team_id);


-- ---------------------------------------------------------------------------
-- release_type_configs
-- One config per release type per team. Defines artifact shape, versioning,
-- and whether approval is required.
-- ---------------------------------------------------------------------------
CREATE TABLE release_type_configs (
    id                   uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id              uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
    slug                 varchar(80)  NOT NULL UNIQUE,    -- e.g. "firmware-drop"
    display_name         varchar(120) NOT NULL,
    description          text,
    -- Artifact shape
    artifact_cardinality varchar(10)  NOT NULL DEFAULT 'single'
                             CHECK (artifact_cardinality IN ('single', 'multi')),
    artifact_naming_regex text,                           -- optional pattern check on artifact name
    allowed_file_types   text[],                          -- e.g. '{".jar",".whl"}'
    -- Lifecycle
    requires_approval    boolean      NOT NULL DEFAULT true,
    version_scheme       varchar(20)  NOT NULL DEFAULT 'semver'
                             CHECK (version_scheme IN ('semver', 'calver', 'seq')),
    is_active            boolean      NOT NULL DEFAULT true,
    created_at           timestamptz  NOT NULL DEFAULT now(),
    updated_at           timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX ON release_type_configs (team_id);

CREATE TRIGGER trg_release_type_configs_updated_at
    BEFORE UPDATE ON release_type_configs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- release_type_field_defs
-- Schema of custom metadata fields a release must/can carry.
-- Each row = one field in the team's release form.
-- ---------------------------------------------------------------------------
CREATE TABLE release_type_field_defs (
    id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    release_type_config_id uuid         NOT NULL
                               REFERENCES release_type_configs(id) ON DELETE CASCADE,
    field_key              varchar(80)  NOT NULL,         -- snake_case identifier
    label                  varchar(120) NOT NULL,         -- UI display name
    field_type             varchar(20)  NOT NULL
                               CHECK (field_type IN ('string', 'number', 'file', 'enum', 'bool', 'date')),
    is_required            boolean      NOT NULL DEFAULT false,
    enum_options           text[],                        -- valid values when field_type = 'enum'
    validation_regex       text,                          -- client-side pattern check
    display_order          smallint     NOT NULL DEFAULT 0,
    default_value          text,
    UNIQUE (release_type_config_id, field_key)
);

CREATE INDEX ON release_type_field_defs (release_type_config_id);


-- ---------------------------------------------------------------------------
-- validation_definitions
-- User-supplied validation scripts / tools.
-- Belongs to a release type + environment pair (environment_id nullable = all envs).
-- ---------------------------------------------------------------------------
CREATE TABLE validation_definitions (
    id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    release_type_config_id uuid         NOT NULL
                               REFERENCES release_type_configs(id) ON DELETE CASCADE,
    environment_id         uuid         REFERENCES environments(id) ON DELETE SET NULL,
    name                   varchar(120) NOT NULL,
    description            text,
    -- Execution
    runner_type            varchar(30)  NOT NULL
                               CHECK (runner_type IN ('shell', 'python', 'docker', 'webhook')),
    script_body            text,                          -- inline script if small
    script_url             text,                          -- S3 / git path / URL
    script_checksum        varchar(128),                  -- sha256 of script for integrity
    runner_image           text,                          -- docker image if runner_type = 'docker'
    timeout_seconds        integer      NOT NULL DEFAULT 300,
    env_vars               jsonb,                         -- extra env vars injected at runtime
    -- Gate behaviour
    is_blocking            boolean      NOT NULL DEFAULT true,
    on_failure             varchar(20)  NOT NULL DEFAULT 'block'
                               CHECK (on_failure IN ('block', 'warn', 'notify')),
    applies_to             varchar(20)  NOT NULL DEFAULT 'release'
                               CHECK (applies_to IN ('release', 'artifact', 'file')),
    run_order              smallint     NOT NULL DEFAULT 0,
    is_active              boolean      NOT NULL DEFAULT true,
    created_by             varchar(255),
    created_at             timestamptz  NOT NULL DEFAULT now(),
    updated_at             timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX ON validation_definitions (release_type_config_id);
CREATE INDEX ON validation_definitions (environment_id);

CREATE TRIGGER trg_validation_definitions_updated_at
    BEFORE UPDATE ON validation_definitions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- RELEASE LAYER
-- =============================================================================

-- ---------------------------------------------------------------------------
-- releases
-- One row per release instance. Typed via release_type_config.
-- Custom metadata fields stored in release_field_values.
-- ---------------------------------------------------------------------------
CREATE TABLE releases (
    id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    release_type_config_id uuid         NOT NULL
                               REFERENCES release_type_configs(id) ON DELETE RESTRICT,
    owning_team_id         uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
    release_name           varchar(160) NOT NULL UNIQUE,  -- human-readable identifier
    version                varchar(60)  NOT NULL,         -- must conform to version_scheme
    status                 varchar(30)  NOT NULL DEFAULT 'draft'
                               CHECK (status IN (
                                   'draft', 'validating', 'approved',
                                   'deploying', 'deployed', 'failed', 'cancelled'
                               )),
    target_date            date,                          -- planned go-live
    notes                  text,                          -- release notes (Markdown ok)
    created_by             varchar(255),
    created_at             timestamptz  NOT NULL DEFAULT now(),
    updated_at             timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX ON releases (release_type_config_id);
CREATE INDEX ON releases (owning_team_id);
CREATE INDEX ON releases (status);

CREATE TRIGGER trg_releases_updated_at
    BEFORE UPDATE ON releases
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- release_field_values
-- EAV store for custom per-release metadata.
-- One row per (release × field_def). Type-split columns avoid untyped text blobs.
-- ---------------------------------------------------------------------------
CREATE TABLE release_field_values (
    id           uuid     PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id   uuid     NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    field_def_id uuid     NOT NULL REFERENCES release_type_field_defs(id) ON DELETE RESTRICT,
    value_text   text,            -- string / enum / bool
    value_number numeric,         -- number fields
    value_date   date,            -- date fields
    value_json   jsonb,           -- complex / array fields
    UNIQUE (release_id, field_def_id)
);

CREATE INDEX ON release_field_values (release_id);
CREATE INDEX ON release_field_values (field_def_id);


-- =============================================================================
-- ARTIFACT LAYER
-- =============================================================================

-- ---------------------------------------------------------------------------
-- artifacts
-- Logical artifact identity and provenance.
-- Physical files are in artifact_files; build tools in artifact_tools.
-- ---------------------------------------------------------------------------
CREATE TABLE artifacts (
    id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id             uuid         NOT NULL REFERENCES releases(id) ON DELETE RESTRICT,
    release_type_config_id uuid         NOT NULL
                               REFERENCES release_type_configs(id) ON DELETE RESTRICT,
    version                varchar(80),                   -- semver / image tag
    -- Source provenance
    git_commit_sha         varchar(64),                   -- source commit
    git_branch             varchar(160),
    build_id               varchar(120),                  -- CI pipeline run ID
    build_url              text,                          -- link to CI run
    -- Content
    manifest_digest        varchar(128),                  -- combined hash of all artifact files
    sbom                   jsonb,                         -- software bill of materials
    labels                 jsonb,                         -- arbitrary k/v tags
    built_at               timestamptz  NOT NULL,
    created_at             timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX ON artifacts (release_id);
CREATE INDEX ON artifacts (release_type_config_id);
CREATE INDEX ON artifacts (git_commit_sha);


-- ---------------------------------------------------------------------------
-- artifact_files
-- Physical files belonging to an artifact.
-- Single-file artifact → 1 row. Multi-file → N rows, each with its own digest.
-- Uniqueness is scoped to (artifact_id, digest) — the same binary may appear
-- legitimately in multiple separate artifacts (e.g. a shared base image layer).
-- ---------------------------------------------------------------------------
CREATE TABLE artifact_files (
    id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id  uuid         NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    field_def_id uuid         REFERENCES release_type_field_defs(id) ON DELETE SET NULL,
    filename     varchar(255) NOT NULL,
    file_role    varchar(60)
                     CHECK (file_role IN ('primary', 'signature', 'checksum', 'metadata')),
    storage_uri  text,                                    -- s3:// or file:// path
    media_type   varchar(120),                            -- MIME type
    digest       varchar(128) NOT NULL,                   -- sha256 of file contents
    size_bytes   bigint,
    signature    text,                                    -- cosign / sigstore signature
    uploaded_at  timestamptz  NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, digest)                          -- scoped uniqueness (not global)
);

CREATE INDEX ON artifact_files (artifact_id);
CREATE INDEX ON artifact_files (field_def_id);


-- ---------------------------------------------------------------------------
-- artifact_tools
-- Records which tools — and at which exact version / git commit — were used
-- to build each artifact. Many tools per artifact, each independently versioned.
-- ---------------------------------------------------------------------------
CREATE TABLE artifact_tools (
    id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id      uuid         NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    tool_id          uuid         NOT NULL REFERENCES tools(id) ON DELETE RESTRICT,
    tool_version     varchar(80),                         -- semver / release tag
    git_commit_sha   varchar(64),                         -- exact tool commit used
    git_branch       varchar(160),
    runner_image     text,                                -- docker image if containerised
    invocation_flags text,                                -- CLI flags used (for audit)
    metadata         jsonb,
    UNIQUE (artifact_id, tool_id)                        -- one entry per tool per artifact
);

CREATE INDEX ON artifact_tools (artifact_id);
CREATE INDEX ON artifact_tools (tool_id);


-- =============================================================================
-- VALIDATION LAYER
-- =============================================================================

-- ---------------------------------------------------------------------------
-- validation_runs
-- One run per (release × environment) pair. Spawns one result row per active
-- validation_definition that applies to the release type + environment.
-- ---------------------------------------------------------------------------
CREATE TABLE validation_runs (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id     uuid        NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    environment_id uuid        NOT NULL REFERENCES environments(id) ON DELETE RESTRICT,
    triggered_by   varchar(255),                          -- user or system actor
    trigger_type   varchar(20) NOT NULL DEFAULT 'manual'
                       CHECK (trigger_type IN ('manual', 'auto', 'webhook')),
    status         varchar(20) NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'running', 'passed', 'failed', 'cancelled')),
    started_at     timestamptz,
    finished_at    timestamptz
);

CREATE INDEX ON validation_runs (release_id, environment_id);
CREATE INDEX ON validation_runs (status);


-- ---------------------------------------------------------------------------
-- validation_results
-- Outcome of one validation_definition script within a run.
-- Stores stdout/stderr for full audit trail.
-- ---------------------------------------------------------------------------
CREATE TABLE validation_results (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            uuid        NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
    validation_def_id uuid        NOT NULL REFERENCES validation_definitions(id) ON DELETE RESTRICT,
    artifact_id       uuid        REFERENCES artifacts(id) ON DELETE SET NULL,
    status            varchar(20) NOT NULL
                          CHECK (status IN ('pass', 'fail', 'warn', 'skipped', 'timeout')),
    exit_code         smallint,
    stdout            text,                               -- truncated if very large
    stderr            text,
    log_url           text,                               -- link to full log in external store
    evidence          jsonb,                              -- structured output / metrics
    duration_ms       integer,
    evaluated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON validation_results (run_id);
CREATE INDEX ON validation_results (validation_def_id);
CREATE INDEX ON validation_results (artifact_id);


-- =============================================================================
-- WORKFLOW LAYER
-- =============================================================================

-- ---------------------------------------------------------------------------
-- approvals
-- Sign-off records — one row per (release × environment × approving_team).
-- ---------------------------------------------------------------------------
CREATE TABLE approvals (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id        uuid        NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    environment_id    uuid        NOT NULL REFERENCES environments(id) ON DELETE RESTRICT,
    approving_team_id uuid        NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
    approver_identity varchar(255) NOT NULL,              -- SSO / email of individual
    decision          varchar(20) NOT NULL
                          CHECK (decision IN ('approved', 'rejected', 'deferred')),
    comment           text,
    decided_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON approvals (release_id);
CREATE INDEX ON approvals (environment_id);
CREATE INDEX ON approvals (approving_team_id);


-- ---------------------------------------------------------------------------
-- deployments
-- Execution records per (release × environment). Self-referencing rollback_of
-- links a rollback deployment to the deployment it reverses.
-- ---------------------------------------------------------------------------
CREATE TABLE deployments (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id     uuid        NOT NULL REFERENCES releases(id) ON DELETE RESTRICT,
    environment_id uuid        NOT NULL REFERENCES environments(id) ON DELETE RESTRICT,
    artifact_id    uuid        NOT NULL REFERENCES artifacts(id) ON DELETE RESTRICT,
    status         varchar(20) NOT NULL DEFAULT 'queued'
                       CHECK (status IN ('queued', 'running', 'success', 'failed')),
    strategy       varchar(40) CHECK (strategy IN ('rolling', 'blue-green', 'canary')),
    deployed_by    varchar(255),
    started_at     timestamptz,
    finished_at    timestamptz,
    rollback_of    uuid        REFERENCES deployments(id) ON DELETE SET NULL
);

CREATE INDEX ON deployments (release_id);
CREATE INDEX ON deployments (environment_id);
CREATE INDEX ON deployments (artifact_id);
CREATE INDEX ON deployments (rollback_of);


-- ---------------------------------------------------------------------------
-- release_events
-- Immutable append-only activity log. Every state change, file upload, approval,
-- and deployment is recorded here. Never UPDATE or DELETE rows.
-- ---------------------------------------------------------------------------
CREATE TABLE release_events (
    id             uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id     uuid         NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    event_type     varchar(60)  NOT NULL,                 -- e.g. "status_changed", "file_uploaded"
    actor_identity varchar(255),                          -- who or what triggered the event
    actor_team_id  uuid         REFERENCES teams(id) ON DELETE SET NULL,
    payload        jsonb,                                 -- before/after state snapshot
    occurred_at    timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX ON release_events (release_id, occurred_at DESC);
CREATE INDEX ON release_events (event_type);
CREATE INDEX ON release_events (actor_team_id);

-- Enforce append-only at the database level
CREATE RULE no_update_release_events
    AS ON UPDATE TO release_events DO INSTEAD NOTHING;

CREATE RULE no_delete_release_events
    AS ON DELETE TO release_events DO INSTEAD NOTHING;
