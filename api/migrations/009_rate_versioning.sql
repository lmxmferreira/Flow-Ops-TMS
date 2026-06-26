-- ============================================================
-- Migration: 009_rate_versioning.sql
-- TMS-RATE-008: Effective-dated carrier contracts with version control
-- ============================================================

BEGIN;

-- Add version control columns to carrier_rate_cards
ALTER TABLE tms.carrier_rate_cards
    ADD COLUMN IF NOT EXISTS version_number      INTEGER     NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS parent_rate_card_id UUID        REFERENCES tms.carrier_rate_cards(rate_card_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS superseded_by_id    UUID        REFERENCES tms.carrier_rate_cards(rate_card_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS superseded_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS change_reason       TEXT,
    ADD COLUMN IF NOT EXISTS changed_by          TEXT;

-- Index for version lookups
CREATE INDEX IF NOT EXISTS idx_rc_parent      ON tms.carrier_rate_cards(parent_rate_card_id) WHERE parent_rate_card_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rc_superseded  ON tms.carrier_rate_cards(superseded_by_id)    WHERE superseded_by_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rc_version     ON tms.carrier_rate_cards(carrier_id, mode, version_number);

-- Rate card version history log
CREATE TABLE IF NOT EXISTS tms.rate_card_audit_log (
    log_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_card_id    UUID        NOT NULL REFERENCES tms.carrier_rate_cards(rate_card_id) ON DELETE CASCADE,
    action          TEXT        NOT NULL,  -- created | versioned | superseded | status_changed
    old_status      TEXT,
    new_status      TEXT,
    old_expiry_date DATE,
    new_expiry_date DATE,
    version_number  INTEGER,
    change_reason   TEXT,
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rcal_card ON tms.rate_card_audit_log(rate_card_id, changed_at DESC);

-- Seed: mark existing cards as version 1
UPDATE tms.carrier_rate_cards SET version_number = 1 WHERE version_number IS NULL OR version_number = 0;

COMMIT;
