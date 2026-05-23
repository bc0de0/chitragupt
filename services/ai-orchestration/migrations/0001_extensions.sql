-- 0001: Enable required PostgreSQL extensions
-- Must run before any table creation that depends on gen_random_uuid() or vector type.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector (voyage-large-2: dim=1536)
