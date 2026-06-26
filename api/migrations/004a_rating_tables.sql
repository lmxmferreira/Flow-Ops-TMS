-- ============================================================
-- Migration 004a: Create rating tables only (no seed data)
-- ============================================================

BEGIN;

CREATE TABLE tms.carrier_rate_cards (
    rate_card_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id      UUID          REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    name            TEXT          NOT NULL,
    mode            TEXT          NOT NULL,
    currency        VARCHAR(3)    NOT NULL DEFAULT 'USD',
    effective_date  DATE          NOT NULL,
    expiry_date     DATE,
    status          TEXT          NOT NULL DEFAULT 'active',
    notes           TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rc_mode   CHECK (mode   IN ('FTL','LTL','Parcel','Rail','Ocean','Air','Intermodal')),
    CONSTRAINT chk_rc_status CHECK (status IN ('active','inactive','expired')),
    CONSTRAINT chk_rc_dates  CHECK (expiry_date IS NULL OR expiry_date > effective_date)
);
CREATE INDEX idx_rc_carrier_mode ON tms.carrier_rate_cards(carrier_id, mode, status);
CREATE INDEX idx_rc_effective    ON tms.carrier_rate_cards(effective_date, expiry_date);

CREATE TABLE tms.carrier_rate_lanes (
    lane_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_card_id      UUID        NOT NULL REFERENCES tms.carrier_rate_cards(rate_card_id) ON DELETE CASCADE,
    lane_name         TEXT        NOT NULL,
    origin_type       TEXT        NOT NULL DEFAULT 'any',
    origin_value      TEXT,
    destination_type  TEXT        NOT NULL DEFAULT 'any',
    destination_value TEXT,
    min_weight_kg     NUMERIC(12,3),
    max_weight_kg     NUMERIC(12,3),
    min_distance_km   NUMERIC(10,2),
    max_distance_km   NUMERIC(10,2),
    priority          INTEGER     NOT NULL DEFAULT 0,
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_lane_orig CHECK (origin_type      IN ('any','zip','state','country','region')),
    CONSTRAINT chk_lane_dest CHECK (destination_type IN ('any','zip','state','country','region'))
);
CREATE INDEX idx_lane_card     ON tms.carrier_rate_lanes(rate_card_id, is_active);
CREATE INDEX idx_lane_priority ON tms.carrier_rate_lanes(rate_card_id, priority DESC);

CREATE TABLE tms.carrier_rate_lines (
    rate_line_id  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lane_id       UUID          NOT NULL REFERENCES tms.carrier_rate_lanes(lane_id) ON DELETE CASCADE,
    charge_type   TEXT          NOT NULL,
    charge_code   TEXT          NOT NULL DEFAULT 'LINEHAUL',
    description   TEXT,
    rate_amount   NUMERIC(14,4) NOT NULL,
    currency      VARCHAR(3)    NOT NULL DEFAULT 'USD',
    uom           TEXT,
    min_charge    NUMERIC(14,4),
    max_charge    NUMERIC(14,4),
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    sort_order    INTEGER       NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rl_type CHECK (charge_type IN (
        'base_flat','per_mile','per_km','per_kg','per_lb',
        'per_pallet','per_carton','minimum','maximum'
    ))
);
CREATE INDEX idx_rl_lane ON tms.carrier_rate_lines(lane_id, is_active);

ALTER TABLE tms.fuel_surcharge_schedules
    ADD COLUMN IF NOT EXISTS name           TEXT,
    ADD COLUMN IF NOT EXISTS mode           TEXT,
    ADD COLUMN IF NOT EXISTS effective_date DATE,
    ADD COLUMN IF NOT EXISTS expiry_date    DATE,
    ADD COLUMN IF NOT EXISTS rate_type      TEXT          NOT NULL DEFAULT 'percentage',
    ADD COLUMN IF NOT EXISTS rate_value     NUMERIC(10,4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS basis          TEXT          NOT NULL DEFAULT 'linehaul',
    ADD COLUMN IF NOT EXISTS is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW();

UPDATE tms.fuel_surcharge_schedules SET name = schedule_code WHERE name IS NULL;

CREATE TABLE tms.accessorial_charges (
    accessorial_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id        UUID          REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    charge_code       TEXT          NOT NULL,
    description       TEXT          NOT NULL,
    charge_type       TEXT          NOT NULL DEFAULT 'flat',
    rate_amount       NUMERIC(14,4) NOT NULL,
    currency          VARCHAR(3)    NOT NULL DEFAULT 'USD',
    applies_to_modes  TEXT[]        DEFAULT ARRAY['FTL','LTL','Parcel'],
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_acc_type CHECK (charge_type IN ('flat','per_unit','percentage','per_mile','per_km'))
);
CREATE INDEX idx_acc_carrier ON tms.accessorial_charges(carrier_id, is_active);

CREATE TABLE tms.shipment_costs (
    cost_id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id     UUID          NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    rate_card_id    UUID          REFERENCES tms.carrier_rate_cards(rate_card_id),
    lane_id         UUID          REFERENCES tms.carrier_rate_lanes(lane_id),
    charge_code     TEXT          NOT NULL,
    charge_type     TEXT          NOT NULL,
    description     TEXT,
    quantity        NUMERIC(14,4),
    rate_amount     NUMERIC(14,4),
    amount          NUMERIC(14,4) NOT NULL,
    currency        VARCHAR(3)    NOT NULL DEFAULT 'USD',
    rated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    rated_by        TEXT          NOT NULL DEFAULT 'system',
    is_override     BOOLEAN       NOT NULL DEFAULT FALSE,
    override_reason TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sc_shipment ON tms.shipment_costs(shipment_id);
CREATE INDEX idx_sc_rated_at ON tms.shipment_costs(rated_at);

CREATE TRIGGER trg_carrier_rate_cards_updated_at
    BEFORE UPDATE ON tms.carrier_rate_cards
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

CREATE TRIGGER trg_carrier_rate_lanes_updated_at
    BEFORE UPDATE ON tms.carrier_rate_lanes
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

CREATE TRIGGER trg_carrier_rate_lines_updated_at
    BEFORE UPDATE ON tms.carrier_rate_lines
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

CREATE TRIGGER trg_accessorial_charges_updated_at
    BEFORE UPDATE ON tms.accessorial_charges
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

CREATE TRIGGER trg_shipment_costs_updated_at
    BEFORE UPDATE ON tms.shipment_costs
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

COMMIT;
