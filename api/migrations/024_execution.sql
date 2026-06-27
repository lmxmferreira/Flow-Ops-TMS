-- ============================================================
-- Migration: 024_execution.sql
-- TMS-EXEC-001 through TMS-EXEC-015: Execution, Tracking & Visibility
-- ============================================================

BEGIN;

-- ── EXEC-002/003: Extend tracking_events ──────────────────────────
ALTER TABLE tms.tracking_events
    ADD COLUMN IF NOT EXISTS event_code          TEXT,
    -- tendered|accepted|dispatched|arrived_pickup|picked_up|departed_pickup
    -- |arrived_delivery|delivered|departed_delivery|completed|closed|exception
    ADD COLUMN IF NOT EXISTS event_source        TEXT NOT NULL DEFAULT 'manual',
    -- manual|mobile|portal|edi|api|telematics|gps|visibility|geofence
    ADD COLUMN IF NOT EXISTS performed_by        TEXT,
    ADD COLUMN IF NOT EXISTS notes               TEXT,
    ADD COLUMN IF NOT EXISTS is_correction       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS override_reason     TEXT;

CREATE INDEX IF NOT EXISTS idx_te_shipment  ON tms.tracking_events(shipment_id, event_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_te_code      ON tms.tracking_events(event_code);
CREATE INDEX IF NOT EXISTS idx_te_location  ON tms.tracking_events(latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- ── EXEC-004: Proof of delivery/pickup ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.proof_of_execution (
    proof_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    shipment_stop_id    UUID        REFERENCES tms.shipment_stops(shipment_stop_id),
    proof_type          TEXT        NOT NULL DEFAULT 'pod',
    -- pod | pop (pickup) | signature | photo | exception
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_by         TEXT,
    capture_source      TEXT        NOT NULL DEFAULT 'manual',
    latitude            NUMERIC(10,6),
    longitude           NUMERIC(10,6),
    signatory_name      TEXT,
    signatory_title     TEXT,
    signature_data      TEXT,
    -- base64 or URL
    photo_url           TEXT,
    document_id         UUID        REFERENCES tms.documents(document_id),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_poe_shipment ON tms.proof_of_execution(shipment_id);
CREATE INDEX IF NOT EXISTS idx_poe_type     ON tms.proof_of_execution(proof_type);

-- ── EXEC-005: Asset/reference assignment ──────────────────────────
CREATE TABLE IF NOT EXISTS tms.shipment_assets (
    asset_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    asset_type          TEXT        NOT NULL,
    -- trailer|tractor|container|chassis|driver|seal|tracking_number
    -- |pro_number|bol_number|container_number
    asset_value         TEXT        NOT NULL,
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by         TEXT,
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_sa_shipment ON tms.shipment_assets(shipment_id);
CREATE INDEX IF NOT EXISTS idx_sa_type     ON tms.shipment_assets(asset_type, asset_value);

-- ── EXEC-008: ETA calculations ────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.shipment_etas (
    eta_id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    shipment_stop_id    UUID        REFERENCES tms.shipment_stops(shipment_stop_id),
    calculated_eta      TIMESTAMPTZ NOT NULL,
    planned_arrival     TIMESTAMPTZ,
    variance_minutes    INTEGER,
    -- positive = late, negative = early
    is_at_risk          BOOLEAN     NOT NULL DEFAULT FALSE,
    is_late             BOOLEAN     NOT NULL DEFAULT FALSE,
    confidence_pct      NUMERIC(5,2),
    calculation_source  TEXT        NOT NULL DEFAULT 'manual',
    -- manual | telematics | algorithm | carrier_provided
    calculated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eta_shipment ON tms.shipment_etas(shipment_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_eta_risk     ON tms.shipment_etas(is_at_risk) WHERE is_at_risk = TRUE;

-- ── EXEC-009: Geofence events ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.geofence_events (
    geofence_event_id   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    shipment_stop_id    UUID        REFERENCES tms.shipment_stops(shipment_stop_id),
    event_type          TEXT        NOT NULL,
    -- arrival | departure
    location_name       TEXT,
    geofence_radius_m   INTEGER     NOT NULL DEFAULT 500,
    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude            NUMERIC(10,6),
    longitude           NUMERIC(10,6),
    auto_milestone      TEXT,
    -- if set, auto-creates this milestone on trigger
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gfe_shipment ON tms.geofence_events(shipment_id);

-- ── EXEC-010/014: Alert configs ───────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.exec_alerts (
    alert_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    alert_type          TEXT        NOT NULL,
    -- late_pickup|late_delivery|missing_update|failed_delivery
    -- |refused|damaged|short|over|disputed|at_risk|exception
    severity            TEXT        NOT NULL DEFAULT 'warning',
    title               TEXT        NOT NULL,
    message             TEXT,
    delivery_channels   TEXT[]      NOT NULL DEFAULT ARRAY['portal'],
    -- email|portal|sms|webhook|api
    recipient_emails    TEXT[],
    webhook_url         TEXT,
    is_sent             BOOLEAN     NOT NULL DEFAULT FALSE,
    sent_at             TIMESTAMPTZ,
    is_resolved         BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ea_shipment  ON tms.exec_alerts(shipment_id);
CREATE INDEX IF NOT EXISTS idx_ea_unresolved ON tms.exec_alerts(is_resolved, severity) WHERE is_resolved = FALSE;

-- ── EXEC-012: Status update subscriptions ─────────────────────────
CREATE TABLE IF NOT EXISTS tms.status_subscriptions (
    subscription_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         TEXT        NOT NULL DEFAULT 'shipment',
    entity_id           UUID        NOT NULL,
    subscriber_type     TEXT        NOT NULL,
    -- customer|supplier|erp|wms|oms|carrier|external
    subscriber_name     TEXT        NOT NULL,
    delivery_channel    TEXT        NOT NULL DEFAULT 'email',
    -- email|portal|sms|webhook|api
    endpoint            TEXT,
    -- email address or webhook URL
    milestone_codes     TEXT[],
    -- which milestones to notify on (null = all)
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ss_entity ON tms.status_subscriptions(entity_type, entity_id, is_active);

COMMIT;
