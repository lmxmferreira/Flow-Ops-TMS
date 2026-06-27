-- ============================================================
-- Migration: 020_core_platform.sql
-- TMS-CORE-008, 009, 010: Core Enterprise Platform features
-- ============================================================

BEGIN;

-- CORE-010: Saved searches
CREATE TABLE IF NOT EXISTS tms.saved_searches (
    search_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    search_name     TEXT        NOT NULL,
    entity_type     TEXT        NOT NULL,
    filters         JSONB       NOT NULL DEFAULT '{}',
    sort_by         TEXT,
    sort_dir        TEXT        NOT NULL DEFAULT 'asc',
    is_shared       BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ss_entity  ON tms.saved_searches(entity_type);
CREATE INDEX IF NOT EXISTS idx_ss_creator ON tms.saved_searches(created_by);
CREATE INDEX IF NOT EXISTS idx_ss_shared  ON tms.saved_searches(is_shared) WHERE is_shared = TRUE;

DO $$ BEGIN
    CREATE TRIGGER trg_ss_updated_at
        BEFORE UPDATE ON tms.saved_searches
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;
