-- ============================================================
-- Migration: 028_exc_yard.sql
-- TMS-EXC-001-010 + TMS-YARD-001-010
-- ============================================================
BEGIN;

-- ── Extend exceptions ──────────────────────────────────────────────
ALTER TABLE tms.exceptions
    ADD COLUMN IF NOT EXISTS exception_type    TEXT,
    -- delay|missed_pickup|missed_delivery|damage|shortage|overage
    -- |refusal|temp_excursion|customs_hold|compliance|carrier_no_show
    -- |rate_failure|invoice_variance|missing_document|integration_failure
    ADD COLUMN IF NOT EXISTS severity          TEXT NOT NULL DEFAULT 'warning',
    ADD COLUMN IF NOT EXISTS status            TEXT NOT NULL DEFAULT 'open',
    -- open|in_progress|escalated|resolved|closed|overridden
    ADD COLUMN IF NOT EXISTS queue_name        TEXT,
    ADD COLUMN IF NOT EXISTS shipment_id       UUID REFERENCES tms.shipments(shipment_id),
    ADD COLUMN IF NOT EXISTS comments          TEXT,
    ADD COLUMN IF NOT EXISTS root_cause        TEXT,
    ADD COLUMN IF NOT EXISTS resolution_notes  TEXT,
    ADD COLUMN IF NOT EXISTS is_blocking       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS override_reason   TEXT,
    ADD COLUMN IF NOT EXISTS overridden_by     TEXT,
    ADD COLUMN IF NOT EXISTS overridden_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS escalated_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source            TEXT NOT NULL DEFAULT 'manual',
    -- manual|automated|integration|tracking
    ADD COLUMN IF NOT EXISTS created_by        TEXT;

CREATE INDEX IF NOT EXISTS idx_exc_shipment  ON tms.exceptions(shipment_id) WHERE shipment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_exc_status    ON tms.exceptions(status, is_blocking);
CREATE INDEX IF NOT EXISTS idx_exc_type      ON tms.exceptions(exception_type);

-- ── EXC-008/009/010: Extend claims ────────────────────────────────
ALTER TABLE tms.claims
    ADD COLUMN IF NOT EXISTS claim_type        TEXT NOT NULL DEFAULT 'damage',
    -- loss|damage|shortage|delay|temp_failure|service_failure|overcharge
    ADD COLUMN IF NOT EXISTS status            TEXT NOT NULL DEFAULT 'draft',
    -- draft|submitted|under_review|approved|rejected|settled|closed|withdrawn
    ADD COLUMN IF NOT EXISTS exception_id      UUID REFERENCES tms.exceptions(exception_id),
    ADD COLUMN IF NOT EXISTS shipment_stop_id  UUID REFERENCES tms.shipment_stops(shipment_stop_id),
    ADD COLUMN IF NOT EXISTS claimed_amount    NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS approved_amount   NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS settlement_amount NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS carrier_response  TEXT,
    ADD COLUMN IF NOT EXISTS carrier_responded_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS supporting_docs   TEXT[],
    ADD COLUMN IF NOT EXISTS credit_created    BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS credit_amount     NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS created_by        TEXT;

CREATE INDEX IF NOT EXISTS idx_clm_shipment ON tms.claims(shipment_id) WHERE shipment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clm_status   ON tms.claims(status);

-- ── YARD-001/002/003: Extend appointments ─────────────────────────
ALTER TABLE tms.appointments
    ADD COLUMN IF NOT EXISTS appointment_type  TEXT NOT NULL DEFAULT 'pickup',
    -- pickup|delivery|cross_dock|drop_trailer|live_load|live_unload
    ADD COLUMN IF NOT EXISTS scheduled_by      TEXT,
    ADD COLUMN IF NOT EXISTS scheduled_by_type TEXT,
    -- internal|carrier|supplier|customer|warehouse|integration
    ADD COLUMN IF NOT EXISTS duration_minutes  INTEGER NOT NULL DEFAULT 60,
    ADD COLUMN IF NOT EXISTS actual_arrival    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS actual_departure  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS no_show           BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS detention_minutes INTEGER,
    ADD COLUMN IF NOT EXISTS reminder_sent     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS confirmed_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancel_reason     TEXT,
    ADD COLUMN IF NOT EXISTS notes             TEXT;

CREATE INDEX IF NOT EXISTS idx_apt_location ON tms.appointments(location_id, appointment_start_datetime);
CREATE INDEX IF NOT EXISTS idx_apt_shipment ON tms.appointments(shipment_stop_id);

-- ── YARD-002: Facility calendars ──────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.facility_schedules (
    schedule_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES tms.locations(location_id) ON DELETE CASCADE,
    day_of_week     INTEGER,
    -- 0=Sun,1=Mon,...,6=Sat; NULL=specific date
    specific_date   DATE,
    open_time       TIME,
    close_time      TIME,
    max_appointments INTEGER NOT NULL DEFAULT 10,
    is_closed       BOOLEAN NOT NULL DEFAULT FALSE,
    close_reason    TEXT,
    -- holiday|maintenance|blackout|capacity
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fs_location ON tms.facility_schedules(location_id, day_of_week);

-- ── YARD-006/007: Extend gate_transactions ────────────────────────
ALTER TABLE tms.gate_transactions
    ADD COLUMN IF NOT EXISTS transaction_type  TEXT NOT NULL DEFAULT 'check_in',
    -- check_in|check_out
    ADD COLUMN IF NOT EXISTS driver_name       TEXT,
    ADD COLUMN IF NOT EXISTS driver_license    TEXT,
    ADD COLUMN IF NOT EXISTS carrier_id        UUID REFERENCES tms.carriers(carrier_id),
    ADD COLUMN IF NOT EXISTS tractor_number    TEXT,
    ADD COLUMN IF NOT EXISTS trailer_number    TEXT,
    ADD COLUMN IF NOT EXISTS container_number  TEXT,
    ADD COLUMN IF NOT EXISTS seal_number       TEXT,
    ADD COLUMN IF NOT EXISTS chassis_number    TEXT,
    ADD COLUMN IF NOT EXISTS is_empty          BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS transaction_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS performed_by      TEXT,
    ADD COLUMN IF NOT EXISTS notes             TEXT;

CREATE INDEX IF NOT EXISTS idx_gt_location  ON tms.gate_transactions(location_id, transaction_at DESC);
CREATE INDEX IF NOT EXISTS idx_gt_shipment  ON tms.gate_transactions(shipment_id) WHERE shipment_id IS NOT NULL;

-- ── YARD-008/009: Extend yard_locations ───────────────────────────
ALTER TABLE tms.yard_locations
    ADD COLUMN IF NOT EXISTS zone_code         TEXT,
    ADD COLUMN IF NOT EXISTS is_occupied       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS current_asset_type TEXT,
    -- trailer|container|chassis|tractor
    ADD COLUMN IF NOT EXISTS current_asset_id  TEXT,
    ADD COLUMN IF NOT EXISTS occupied_since    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_empty          BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS notes             TEXT;

CREATE INDEX IF NOT EXISTS idx_yl_location ON tms.yard_locations(location_id) WHERE location_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_yl_occupied ON tms.yard_locations(is_occupied) WHERE is_occupied = TRUE;

COMMIT;
