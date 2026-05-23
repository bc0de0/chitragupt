-- 0004: Cost log table — owned by Python service
-- Authoritative record of every LLM API call with token counts and USD cost.
-- Append-only: no UPDATE or DELETE. Basis for budget tracking and audit.

CREATE TABLE IF NOT EXISTS cost_log (
    log_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID            NOT NULL,
    session_id      UUID            NOT NULL,
    llm_feature     TEXT            NOT NULL,
    model_id        TEXT            NOT NULL,
    cost_usd        NUMERIC(10, 6)  NOT NULL,
    budget_stage    TEXT            NOT NULL,
    input_tokens    INTEGER         NOT NULL DEFAULT 0,
    output_tokens   INTEGER         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cost_log_session   ON cost_log(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_log_workspace ON cost_log(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cost_log_model     ON cost_log(model_id);
