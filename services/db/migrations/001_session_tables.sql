-- Migration 001: Core session and entity tables
-- Implements the structured storage layer defined in docs/sprints/sprint0/DATABASE.md
-- RLS is enforced on every table; all tenant-scoped queries must set app.tenant_id

-- ============================================================
-- Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "btree_gist"; -- composite GiST for range overlap checks

-- ============================================================
-- Shared helpers
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ============================================================
-- workspaces
-- Top-level tenant unit. One workspace per organisation.
-- ============================================================

CREATE TABLE workspaces (
  workspace_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                  TEXT        NOT NULL,
  plan                  TEXT        NOT NULL DEFAULT 'starter', -- starter | pro | enterprise
  data_residency        TEXT        NOT NULL DEFAULT 'eu-west',
  compliance_flags      TEXT[]      NOT NULL DEFAULT '{}',       -- ['gdpr','hipaa','fca', ...]
  monthly_budget_cap_usd NUMERIC(10,4) NOT NULL DEFAULT 50.0,
  retention_days        INT         NOT NULL DEFAULT 365,
  sso_config            JSONB,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER workspaces_updated_at
  BEFORE UPDATE ON workspaces
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspaces_tenant_isolation ON workspaces
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- projects
-- One project per client engagement. Scoped to a workspace.
-- ============================================================

CREATE TABLE projects (
  project_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID        NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  name                  TEXT        NOT NULL,
  domain                TEXT,         -- 'financial_services' | 'healthcare' | 'logistics' | ...
  status                TEXT        NOT NULL DEFAULT 'active', -- active | archived | signed_off
  budget_cap_usd        NUMERIC(10,4),
  cost_incurred_usd     NUMERIC(10,4) NOT NULL DEFAULT 0,
  target_spec_date      DATE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX projects_workspace_idx ON projects (workspace_id);

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY projects_tenant_isolation ON projects
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- sessions
-- One session per BA conversation. Holds the mutable state
-- that the Rust kernel owns. JSON blob mirrors SessionState struct.
-- ============================================================

CREATE TABLE sessions (
  session_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID        NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  project_id            UUID        NOT NULL REFERENCES projects(project_id)   ON DELETE CASCADE,
  ba_user_id            TEXT        NOT NULL, -- external identity (email or SSO sub)
  current_phase         TEXT        NOT NULL DEFAULT 'ProblemIntake',
  phase_history         JSONB       NOT NULL DEFAULT '[]',   -- [{phase, entered_at, exited_at}]
  revisit_target        TEXT,                                 -- phase name if in revisit mode
  revisit_history       JSONB       NOT NULL DEFAULT '[]',   -- [{from_phase, to_phase, at}]
  state_blob            JSONB       NOT NULL DEFAULT '{}',   -- full SessionState snapshot (cache)
  documents_indexed     UUID[]      NOT NULL DEFAULT '{}',
  regulatory_context    TEXT,
  cost_usd              NUMERIC(10,6) NOT NULL DEFAULT 0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX sessions_workspace_idx  ON sessions (workspace_id);
CREATE INDEX sessions_project_idx    ON sessions (project_id);
CREATE INDEX sessions_ba_user_idx    ON sessions (workspace_id, ba_user_id);

CREATE TRIGGER sessions_updated_at
  BEFORE UPDATE ON sessions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY sessions_tenant_isolation ON sessions
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- ac_status
-- Per-session acceptance criterion tracking.
-- Written by the Rust kernel when AcUpdate events arrive from Python.
-- ============================================================

CREATE TABLE ac_status (
  ac_status_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  workspace_id          UUID        NOT NULL,
  criterion_id          TEXT        NOT NULL, -- e.g. 'S1-AC-01', 'GATE-REGULATED-SOURCE-DOC'
  met                   BOOLEAN     NOT NULL DEFAULT FALSE,
  waived                BOOLEAN     NOT NULL DEFAULT FALSE,
  evidence              TEXT,
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, criterion_id)
);

CREATE INDEX ac_status_session_idx ON ac_status (session_id);

ALTER TABLE ac_status ENABLE ROW LEVEL SECURITY;

CREATE POLICY ac_status_tenant_isolation ON ac_status
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- actors
-- People, teams, and external systems identified in a session.
-- ============================================================

CREATE TABLE actors (
  actor_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  project_id            UUID        NOT NULL REFERENCES projects(project_id),
  workspace_id          UUID        NOT NULL,
  name                  TEXT        NOT NULL,
  role                  TEXT,
  actor_type            TEXT        NOT NULL DEFAULT 'human', -- human | team | external_system
  authority_level       TEXT,   -- decision_maker | contributor | observer | external
  source_chunk_ids      UUID[]  NOT NULL DEFAULT '{}',
  confidence            NUMERIC(3,2) NOT NULL DEFAULT 1.0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX actors_session_idx   ON actors (session_id);
CREATE INDEX actors_project_idx   ON actors (project_id, workspace_id);

ALTER TABLE actors ENABLE ROW LEVEL SECURITY;

CREATE POLICY actors_tenant_isolation ON actors
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- requirements
-- Functional and non-functional requirements extracted from the session.
-- source_chunk_ids links back to document_chunks for provenance.
-- ============================================================

CREATE TABLE requirements (
  requirement_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  project_id            UUID        NOT NULL REFERENCES projects(project_id),
  workspace_id          UUID        NOT NULL,
  req_code              TEXT        NOT NULL, -- e.g. 'REQ-001'
  req_type              TEXT        NOT NULL, -- functional | non_functional
  description           TEXT        NOT NULL,
  priority              TEXT        NOT NULL DEFAULT 'must', -- must | should | could
  source_chunk_ids      UUID[]      NOT NULL DEFAULT '{}',
  confidence_score      NUMERIC(3,2) NOT NULL DEFAULT 1.0,
  source                TEXT        NOT NULL DEFAULT 'conversation', -- conversation | document
  status                TEXT        NOT NULL DEFAULT 'draft', -- draft | confirmed | rejected
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX requirements_session_idx  ON requirements (session_id);
CREATE INDEX requirements_project_idx  ON requirements (project_id, workspace_id);
CREATE INDEX requirements_type_idx     ON requirements (session_id, req_type);

CREATE TRIGGER requirements_updated_at
  BEFORE UPDATE ON requirements
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;

CREATE POLICY requirements_tenant_isolation ON requirements
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- constraints_captured
-- Real-world limits: timeline, budget, regulatory, data residency, security.
-- Table name avoids conflict with SQL reserved word CONSTRAINT.
-- ============================================================

CREATE TABLE constraints_captured (
  constraint_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  project_id            UUID        NOT NULL REFERENCES projects(project_id),
  workspace_id          UUID        NOT NULL,
  constraint_code       TEXT        NOT NULL, -- e.g. 'CON-001'
  constraint_type       TEXT        NOT NULL, -- timeline | budget | regulatory | data_residency | security | technical | other
  description           TEXT        NOT NULL,
  source_chunk_ids      UUID[]      NOT NULL DEFAULT '{}',
  confidence_score      NUMERIC(3,2) NOT NULL DEFAULT 1.0,
  source                TEXT        NOT NULL DEFAULT 'conversation',
  status                TEXT        NOT NULL DEFAULT 'draft',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX constraints_session_idx  ON constraints_captured (session_id);
CREATE INDEX constraints_project_idx  ON constraints_captured (project_id, workspace_id);
CREATE INDEX constraints_type_idx     ON constraints_captured (session_id, constraint_type);

ALTER TABLE constraints_captured ENABLE ROW LEVEL SECURITY;

CREATE POLICY constraints_tenant_isolation ON constraints_captured
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- assumptions
-- Things treated as true but not yet verified.
-- ============================================================

CREATE TABLE assumptions (
  assumption_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  project_id            UUID        NOT NULL REFERENCES projects(project_id),
  workspace_id          UUID        NOT NULL,
  assumption_code       TEXT        NOT NULL, -- e.g. 'ASS-001'
  description           TEXT        NOT NULL,
  risk_if_false         TEXT,
  source_chunk_ids      UUID[]      NOT NULL DEFAULT '{}',
  source                TEXT        NOT NULL DEFAULT 'conversation',
  status                TEXT        NOT NULL DEFAULT 'open', -- open | confirmed | invalidated
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX assumptions_session_idx ON assumptions (session_id);
CREATE INDEX assumptions_project_idx ON assumptions (project_id, workspace_id);

ALTER TABLE assumptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY assumptions_tenant_isolation ON assumptions
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- open_questions
-- Gaps explicitly acknowledged as unanswered.
-- ============================================================

CREATE TABLE open_questions (
  question_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  workspace_id          UUID        NOT NULL,
  description           TEXT        NOT NULL,
  assigned_to           TEXT,
  phase_raised          TEXT        NOT NULL,
  resolved              BOOLEAN     NOT NULL DEFAULT FALSE,
  resolved_at           TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX open_questions_session_idx ON open_questions (session_id, resolved);

ALTER TABLE open_questions ENABLE ROW LEVEL SECURITY;

CREATE POLICY open_questions_tenant_isolation ON open_questions
  USING (workspace_id = current_setting('app.tenant_id')::UUID);
