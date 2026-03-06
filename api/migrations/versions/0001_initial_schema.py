"""Initial schema — all 16 tables across 5 layers.

Revision ID: 0001
Revises:
Create Date: 2026-02-17

Layers created (in FK-dependency order):
  Config Layer    : teams, environments, tools, release_type_configs,
                    release_type_field_defs, validation_definitions
  Release Layer   : releases, release_field_values, release_dependencies
  Artifact Layer  : artifacts, artifact_files, artifact_tools
  Validation Layer: validation_runs, validation_results
  Workflow Layer  : approvals, deployments, release_events
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ------------------------------------------------------------------
    # Utility trigger function
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
    """)

    # ==================================================================
    # CONFIG LAYER
    # ==================================================================

    op.execute("""
        CREATE TABLE teams (
            id            uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            slug          varchar(80)  NOT NULL UNIQUE,
            name          varchar(120) NOT NULL,
            contact_email varchar(255),
            metadata      jsonb,
            created_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE environments (
            id                uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            slug              varchar(60)  NOT NULL UNIQUE,
            name              varchar(120) NOT NULL,
            tier              smallint     NOT NULL DEFAULT 0,
            requires_approval boolean      NOT NULL DEFAULT false,
            config            jsonb
        )
    """)

    op.execute("""
        CREATE TABLE tools (
            id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            name             varchar(120) NOT NULL UNIQUE,
            description      text,
            source           varchar(20)  NOT NULL
                                 CHECK (source IN ('internal', 'external', 'vendored')),
            repo_url         text,
            owned_by_team_id uuid         REFERENCES teams(id) ON DELETE SET NULL,
            is_active        boolean      NOT NULL DEFAULT true,
            created_at       timestamptz  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON tools (owned_by_team_id)")

    op.execute("""
        CREATE TABLE release_type_configs (
            id                   uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id              uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
            slug                 varchar(80)  NOT NULL UNIQUE,
            display_name         varchar(120) NOT NULL,
            description          text,
            artifact_cardinality varchar(10)  NOT NULL DEFAULT 'single'
                                     CHECK (artifact_cardinality IN ('single', 'multi')),
            artifact_naming_regex text,
            allowed_file_types   text[],
            requires_approval    boolean      NOT NULL DEFAULT true,
            version_scheme       varchar(20)  NOT NULL DEFAULT 'semver'
                                     CHECK (version_scheme IN ('semver', 'calver', 'seq')),
            is_active            boolean      NOT NULL DEFAULT true,
            created_at           timestamptz  NOT NULL DEFAULT now(),
            updated_at           timestamptz  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON release_type_configs (team_id)")
    op.execute("""
        CREATE TRIGGER trg_release_type_configs_updated_at
            BEFORE UPDATE ON release_type_configs
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    op.execute("""
        CREATE TABLE release_type_field_defs (
            id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            release_type_config_id uuid         NOT NULL
                                       REFERENCES release_type_configs(id) ON DELETE CASCADE,
            field_key              varchar(80)  NOT NULL,
            label                  varchar(120) NOT NULL,
            field_type             varchar(20)  NOT NULL
                                       CHECK (field_type IN ('string', 'number', 'file', 'enum', 'bool', 'date')),
            is_required            boolean      NOT NULL DEFAULT false,
            enum_options           text[],
            validation_regex       text,
            display_order          smallint     NOT NULL DEFAULT 0,
            default_value          text,
            UNIQUE (release_type_config_id, field_key)
        )
    """)
    op.execute("CREATE INDEX ON release_type_field_defs (release_type_config_id)")

    op.execute("""
        CREATE TABLE validation_definitions (
            id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            release_type_config_id uuid         NOT NULL
                                       REFERENCES release_type_configs(id) ON DELETE CASCADE,
            environment_id         uuid         REFERENCES environments(id) ON DELETE SET NULL,
            name                   varchar(120) NOT NULL,
            description            text,
            runner_type            varchar(30)  NOT NULL
                                       CHECK (runner_type IN ('shell', 'python', 'docker', 'webhook')),
            script_body            text,
            script_url             text,
            script_checksum        varchar(128),
            runner_image           text,
            timeout_seconds        integer      NOT NULL DEFAULT 300,
            env_vars               jsonb,
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
        )
    """)
    op.execute("CREATE INDEX ON validation_definitions (release_type_config_id)")
    op.execute("CREATE INDEX ON validation_definitions (environment_id)")
    op.execute("""
        CREATE TRIGGER trg_validation_definitions_updated_at
            BEFORE UPDATE ON validation_definitions
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # ==================================================================
    # PROJECTS
    # ==================================================================

    op.execute("""
        CREATE TABLE projects (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name            text NOT NULL,
            related_project text,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)

    # ==================================================================
    # RELEASE LAYER
    # ==================================================================

    op.execute("""
        CREATE TABLE releases (
            id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            release_type_config_id uuid         NOT NULL
                                       REFERENCES release_type_configs(id) ON DELETE RESTRICT,
            owning_team_id         uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
            release_name           varchar(160) NOT NULL UNIQUE,
            version                varchar(60)  NOT NULL,
            status                 varchar(30)  NOT NULL DEFAULT 'draft'
                                       CHECK (status IN (
                                           'draft', 'validating', 'approved',
                                           'deploying', 'deployed', 'failed', 'cancelled'
                                       )),
            target_date            date,
            notes                  text,
            created_by             varchar(255),
            project_id             uuid REFERENCES projects(id) ON DELETE SET NULL,
            created_at             timestamptz  NOT NULL DEFAULT now(),
            updated_at             timestamptz  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON releases (release_type_config_id)")
    op.execute("CREATE INDEX ON releases (owning_team_id)")
    op.execute("CREATE INDEX ON releases (status)")
    op.execute("CREATE INDEX ON releases (project_id)")
    op.execute("""
        CREATE TRIGGER trg_releases_updated_at
            BEFORE UPDATE ON releases
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    op.execute("""
        CREATE TABLE release_field_values (
            id           uuid     PRIMARY KEY DEFAULT gen_random_uuid(),
            release_id   uuid     NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
            field_def_id uuid     NOT NULL REFERENCES release_type_field_defs(id) ON DELETE RESTRICT,
            value_text   text,
            value_number numeric,
            value_date   date,
            value_json   jsonb,
            UNIQUE (release_id, field_def_id)
        )
    """)
    op.execute("CREATE INDEX ON release_field_values (release_id)")
    op.execute("CREATE INDEX ON release_field_values (field_def_id)")

    op.execute("""
        CREATE TABLE release_dependencies (
            release_id    uuid NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
            depends_on_id uuid NOT NULL REFERENCES releases(id) ON DELETE RESTRICT,
            PRIMARY KEY (release_id, depends_on_id),
            CHECK (release_id <> depends_on_id)
        )
    """)
    op.execute("CREATE INDEX ON release_dependencies (depends_on_id)")

    # ==================================================================
    # ARTIFACT LAYER
    # ==================================================================

    op.execute("""
        CREATE TABLE artifacts (
            id                     uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            release_id             uuid         NOT NULL REFERENCES releases(id) ON DELETE RESTRICT,
            release_type_config_id uuid         NOT NULL
                                       REFERENCES release_type_configs(id) ON DELETE RESTRICT,
            version                varchar(80),
            git_commit_sha         varchar(64),
            git_branch             varchar(160),
            build_id               varchar(120),
            build_url              text,
            manifest_digest        varchar(128),
            sbom                   jsonb,
            labels                 jsonb,
            built_at               timestamptz  NOT NULL,
            created_at             timestamptz  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON artifacts (release_id)")
    op.execute("CREATE INDEX ON artifacts (release_type_config_id)")
    op.execute("CREATE INDEX ON artifacts (git_commit_sha)")

    op.execute("""
        CREATE TABLE artifact_files (
            id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            artifact_id  uuid         NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
            field_def_id uuid         REFERENCES release_type_field_defs(id) ON DELETE SET NULL,
            filename     varchar(255) NOT NULL,
            file_role    varchar(60)
                             CHECK (file_role IN ('primary', 'signature', 'checksum', 'metadata')),
            storage_uri  text,
            media_type   varchar(120),
            digest       varchar(128) NOT NULL,
            size_bytes   bigint,
            signature    text,
            uploaded_at  timestamptz  NOT NULL DEFAULT now(),
            UNIQUE (artifact_id, digest)
        )
    """)
    op.execute("CREATE INDEX ON artifact_files (artifact_id)")
    op.execute("CREATE INDEX ON artifact_files (field_def_id)")

    op.execute("""
        CREATE TABLE artifact_tools (
            id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            artifact_id      uuid         NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
            tool_id          uuid         NOT NULL REFERENCES tools(id) ON DELETE RESTRICT,
            tool_version     varchar(80),
            git_commit_sha   varchar(64),
            git_branch       varchar(160),
            runner_image     text,
            invocation_flags text,
            metadata         jsonb,
            UNIQUE (artifact_id, tool_id)
        )
    """)
    op.execute("CREATE INDEX ON artifact_tools (artifact_id)")
    op.execute("CREATE INDEX ON artifact_tools (tool_id)")

    # ==================================================================
    # VALIDATION LAYER
    # ==================================================================

    op.execute("""
        CREATE TABLE validation_runs (
            id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
            release_id     uuid        NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
            environment_id uuid        NOT NULL REFERENCES environments(id) ON DELETE RESTRICT,
            triggered_by   varchar(255),
            trigger_type   varchar(20) NOT NULL DEFAULT 'manual'
                               CHECK (trigger_type IN ('manual', 'auto', 'webhook')),
            status         varchar(20) NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending', 'running', 'passed', 'failed', 'cancelled')),
            started_at     timestamptz,
            finished_at    timestamptz
        )
    """)
    op.execute("CREATE INDEX ON validation_runs (release_id, environment_id)")
    op.execute("CREATE INDEX ON validation_runs (status)")

    op.execute("""
        CREATE TABLE validation_results (
            id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id            uuid        NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
            validation_def_id uuid        NOT NULL REFERENCES validation_definitions(id) ON DELETE RESTRICT,
            artifact_id       uuid        REFERENCES artifacts(id) ON DELETE SET NULL,
            status            varchar(20) NOT NULL
                                  CHECK (status IN ('pass', 'fail', 'warn', 'skipped', 'timeout')),
            exit_code         smallint,
            stdout            text,
            stderr            text,
            log_url           text,
            evidence          jsonb,
            duration_ms       integer,
            evaluated_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON validation_results (run_id)")
    op.execute("CREATE INDEX ON validation_results (validation_def_id)")
    op.execute("CREATE INDEX ON validation_results (artifact_id)")

    # ==================================================================
    # WORKFLOW LAYER
    # ==================================================================

    op.execute("""
        CREATE TABLE approvals (
            id                uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            release_id        uuid         NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
            environment_id    uuid         NOT NULL REFERENCES environments(id) ON DELETE RESTRICT,
            approving_team_id uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
            approver_identity varchar(255) NOT NULL,
            decision          varchar(20)  NOT NULL
                                  CHECK (decision IN ('approved', 'rejected', 'deferred')),
            comment           text,
            decided_at        timestamptz  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON approvals (release_id)")
    op.execute("CREATE INDEX ON approvals (environment_id)")
    op.execute("CREATE INDEX ON approvals (approving_team_id)")

    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX ON deployments (release_id)")
    op.execute("CREATE INDEX ON deployments (environment_id)")
    op.execute("CREATE INDEX ON deployments (artifact_id)")
    op.execute("CREATE INDEX ON deployments (rollback_of)")

    op.execute("""
        CREATE TABLE release_events (
            id             uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
            release_id     uuid         NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
            event_type     varchar(60)  NOT NULL,
            actor_identity varchar(255),
            actor_team_id  uuid         REFERENCES teams(id) ON DELETE SET NULL,
            payload        jsonb,
            occurred_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON release_events (release_id, occurred_at DESC)")
    op.execute("CREATE INDEX ON release_events (event_type)")
    op.execute("CREATE INDEX ON release_events (actor_team_id)")

    # Enforce append-only at the database level
    op.execute("""
        CREATE RULE no_update_release_events
            AS ON UPDATE TO release_events DO INSTEAD NOTHING
    """)
    op.execute("""
        CREATE RULE no_delete_release_events
            AS ON DELETE TO release_events DO INSTEAD NOTHING
    """)


def downgrade() -> None:
    # Drop in reverse FK-dependency order

    # Workflow layer
    op.execute("DROP TABLE IF EXISTS release_events CASCADE")
    op.execute("DROP TABLE IF EXISTS deployments CASCADE")
    op.execute("DROP TABLE IF EXISTS approvals CASCADE")

    # Validation layer
    op.execute("DROP TABLE IF EXISTS validation_results CASCADE")
    op.execute("DROP TABLE IF EXISTS validation_runs CASCADE")

    # Artifact layer
    op.execute("DROP TABLE IF EXISTS artifact_tools CASCADE")
    op.execute("DROP TABLE IF EXISTS artifact_files CASCADE")
    op.execute("DROP TABLE IF EXISTS artifacts CASCADE")

    # Release layer
    op.execute("DROP TABLE IF EXISTS release_dependencies CASCADE")
    op.execute("DROP TABLE IF EXISTS release_field_values CASCADE")
    op.execute("DROP TABLE IF EXISTS releases CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")

    # Config layer
    op.execute("DROP TABLE IF EXISTS validation_definitions CASCADE")
    op.execute("DROP TABLE IF EXISTS release_type_field_defs CASCADE")
    op.execute("DROP TABLE IF EXISTS release_type_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS tools CASCADE")
    op.execute("DROP TABLE IF EXISTS environments CASCADE")
    op.execute("DROP TABLE IF EXISTS teams CASCADE")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at CASCADE")
