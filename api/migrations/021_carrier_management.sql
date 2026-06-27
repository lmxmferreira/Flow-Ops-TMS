-- ============================================================
-- Migration: 021_carrier_management.sql
-- TMS-CAR-001 through TMS-CAR-015: Carrier Management & Tendering
-- Extends existing enterprise tables
-- ============================================================

BEGIN;

-- ── CAR-002: Extend carriers with missing attributes ───────────────
ALTER TABLE tms.carriers
    ADD COLUMN IF NOT EXISTS tax_id              TEXT,
    ADD COLUMN IF NOT EXISTS insurance_expiry    DATE,
    ADD COLUMN IF NOT EXISTS insurance_provider  TEXT,
    ADD COLUMN IF NOT EXISTS insurance_amount    NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS supported_modes     TEXT[],
    ADD COLUMN IF NOT EXISTS certifications      TEXT[],
    ADD COLUMN IF NOT EXISTS contact_name        TEXT,
    ADD COLUMN IF NOT EXISTS contact_email       TEXT,
    ADD COLUMN IF NOT EXISTS contact_phone       TEXT,
    ADD COLUMN IF NOT EXISTS notes               TEXT,
    ADD COLUMN IF NOT EXISTS blocked_reason      TEXT,
    ADD COLUMN IF NOT EXISTS is_compliant        BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS compliance_checked_at TIMESTAMPTZ;

-- ── CAR-010: Tender rules ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.tender_rules (
    rule_id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name           TEXT    NOT NULL,
    tender_method       TEXT    NOT NULL DEFAULT 'sequential',
    -- manual | automatic | sequential | waterfall | broadcast | spot_bid | contractual
    expiration_minutes  INTEGER NOT NULL DEFAULT 60,
    max_retenders       INTEGER NOT NULL DEFAULT 3,
    retender_on_reject  BOOLEAN NOT NULL DEFAULT TRUE,
    retender_on_expire  BOOLEAN NOT NULL DEFAULT TRUE,
    escalate_after_hrs  INTEGER,
    notification_emails TEXT[],
    applies_to_modes    TEXT[]  NOT NULL DEFAULT ARRAY['FTL','LTL'],
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── CAR-014: Carrier capacity commitments ─────────────────────────
CREATE TABLE IF NOT EXISTS tms.carrier_capacity (
    capacity_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID    NOT NULL REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    origin_region       TEXT,
    dest_region         TEXT,
    transport_mode      TEXT,
    equipment_type      TEXT,
    committed_loads_wk  INTEGER,
    committed_loads_mo  INTEGER,
    blackout_start      DATE,
    blackout_end        DATE,
    blackout_reason     TEXT,
    effective_date      DATE    NOT NULL DEFAULT CURRENT_DATE,
    expiry_date         DATE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cc_carrier ON tms.carrier_capacity(carrier_id, is_active);

-- ── CAR-011: Extend tenders with missing fields ────────────────────
ALTER TABLE tms.tenders
    ADD COLUMN IF NOT EXISTS tender_method      TEXT,
    ADD COLUMN IF NOT EXISTS retender_count     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS parent_tender_id   UUID    REFERENCES tms.tenders(tender_id),
    ADD COLUMN IF NOT EXISTS service_level      TEXT,
    ADD COLUMN IF NOT EXISTS integration_source TEXT,
    ADD COLUMN IF NOT EXISTS override_reason    TEXT,
    ADD COLUMN IF NOT EXISTS canceled_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS canceled_by        TEXT;

-- ── CAR-011: Extend tender_events ─────────────────────────────────
ALTER TABLE tms.tender_events
    ADD COLUMN IF NOT EXISTS event_type         TEXT,
    ADD COLUMN IF NOT EXISTS performed_by       TEXT,
    ADD COLUMN IF NOT EXISTS notes              TEXT;

-- ── CAR-015: Carrier onboarding ───────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.carrier_onboarding (
    onboarding_id       UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID    NOT NULL REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    status              TEXT    NOT NULL DEFAULT 'pending',
    -- pending | in_review | approved | rejected | suspended
    submitted_at        TIMESTAMPTZ,
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMPTZ,
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    required_docs       TEXT[]  NOT NULL DEFAULT ARRAY['W9','COI','MC_AUTH','CARRIER_AGREEMENT'],
    submitted_docs      TEXT[]  NOT NULL DEFAULT ARRAY[]::TEXT[],
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_co_status CHECK (status IN (
        'pending','in_review','approved','rejected','suspended'
    ))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_co_carrier ON tms.carrier_onboarding(carrier_id);

-- Seed tender rules
INSERT INTO tms.tender_rules
    (rule_name, tender_method, expiration_minutes, max_retenders, applies_to_modes)
VALUES
    ('FTL Sequential 2hr', 'sequential', 120, 3, ARRAY['FTL']),
    ('LTL Broadcast 1hr',  'broadcast',   60, 2, ARRAY['LTL']),
    ('Parcel Auto 30min',  'automatic',   30, 1, ARRAY['Parcel']),
    ('Spot Bid 4hr',       'spot_bid',   240, 1, ARRAY['FTL','LTL'])
ON CONFLICT DO NOTHING;

COMMIT;
