-- ── ATS Database Initialization ──────────────────────────────────────────────
-- Runs once on first container start.
-- Creates extensions and schemas used by the ATS system.

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID primary keys
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";    -- GIN index support

-- Application schemas
CREATE SCHEMA IF NOT EXISTS ats;       -- core hiring data
CREATE SCHEMA IF NOT EXISTS audit;     -- immutable audit trail
CREATE SCHEMA IF NOT EXISTS cache;     -- materialized/computed results

-- Grant schema permissions to app user
GRANT ALL PRIVILEGES ON SCHEMA ats   TO ats_user;
GRANT ALL PRIVILEGES ON SCHEMA audit TO ats_user;
GRANT ALL PRIVILEGES ON SCHEMA cache TO ats_user;

-- Default search path for the app user
ALTER USER ats_user SET search_path = ats, public;
