-- ============================================================
-- Migration: 004_rating_v2.sql
-- TMS-RATE-001: Carrier freight cost calculation at shipment level
-- Note: tms.fuel_surcharge_schedules already exists with different
--       structure — we add our columns to it instead of recreating it.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------------ --
-- 1. Carrier Rate Cards  (one per carrier + mode)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.carrier_rate_cards (
    rate_card_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID          REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    name                TEXT          NOT NULL,
    mode                TEXT          NOT NULL,
    currency            VARCHAR(3)    NOT NULL DEFAULT 'USD',
    effective_date      DATE          NOT NULL,
    expiry_date         DATE,
    status              TEXT          NOT NULL DEFAULT 'active',
    notes               TEXT,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rc_mode   CHECK (mode   IN ('FTL','LTL','Parcel','Rail','Ocean','Air','Intermodal')),
    CONSTRAINT chk_rc_status CHECK (status IN ('active','inactive','expired')),
    CONSTRAINT chk_rc_dates  CHECK (expiry_date IS NULL OR expiry_date > effective_date)
);

CREATE INDEX idx_rc_carrier_mode ON tms.carrier_rate_cards(carrier_id, mode, status);
CREATE INDEX idx_rc_effective    ON tms.carrier_rate_cards(effective_date, expiry_date);

-- ------------------------------------------------------------------ --
-- 2. Carrier Rate Lanes
-- ------------------------------------------------------------------ --
CREATE TABLE tms.carrier_rate_lanes (
    lane_id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_card_id        UUID          NOT NULL REFERENCES tms.carrier_rate_cards(rate_card_id) ON DELETE CASCADE,
    lane_name           TEXT          NOT NULL,
    origin_type         TEXT          NOT NULL DEFAULT 'any',
    origin_value        TEXT,
    destination_type    TEXT          NOT NULL DEFAULT 'any',
    destination_value   TEXT,
    min_weight_kg       NUMERIC(12,3),
    max_weight_kg       NUMERIC(12,3),
    min_distance_km     NUMERIC(10,2),
    max_distance_km     NUMERIC(10,2),
    priority            INTEGER       NOT NULL DEFAULT 0,
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_lane_origin_type      CHECK (origin_type      IN ('any','zip','state','country','region')),
    CONSTRAINT chk_lane_destination_type CHECK (destination_type IN ('any','zip','state','country','region'))
);

CREATE INDEX idx_lane_card     ON tms.carrier_rate_lanes(rate_card_id, is_active);
CREATE INDEX idx_lane_priority ON tms.carrier_rate_lanes(rate_card_id, priority DESC);

-- ------------------------------------------------------------------ --
-- 3. Carrier Rate Lines
-- ------------------------------------------------------------------ --
CREATE TABLE tms.carrier_rate_lines (
    rate_line_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lane_id             UUID          NOT NULL REFERENCES tms.carrier_rate_lanes(lane_id) ON DELETE CASCADE,
    charge_type         TEXT          NOT NULL,
    charge_code         TEXT          NOT NULL DEFAULT 'LINEHAUL',
    description         TEXT,
    rate_amount         NUMERIC(14,4) NOT NULL,
    currency            VARCHAR(3)    NOT NULL DEFAULT 'USD',
    uom                 TEXT,
    min_charge          NUMERIC(14,4),
    max_charge          NUMERIC(14,4),
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    sort_order          INTEGER       NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rl_charge_type CHECK (charge_type IN (
        'base_flat','per_mile','per_km','per_kg','per_lb',
        'per_pallet','per_carton','minimum','maximum'
    ))
);

CREATE INDEX idx_rl_lane ON tms.carrier_rate_lines(lane_id, is_active);

-- ------------------------------------------------------------------ --
-- 4. Fuel Surcharge — add TMS app columns to existing enterprise table
-- ------------------------------------------------------------------ --
ALTER TABLE tms.fuel_surcharge_schedules
    ADD COLUMN IF NOT EXISTS name          TEXT,
    ADD COLUMN IF NOT EXISTS mode          TEXT,
    ADD COLUMN IF NOT EXISTS effective_date DATE,
    ADD COLUMN IF NOT EXISTS expiry_date   DATE,
    ADD COLUMN IF NOT EXISTS rate_type     TEXT    NOT NULL DEFAULT 'percentage',
    ADD COLUMN IF NOT EXISTS rate_value    NUMERIC(10,4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS basis         TEXT    NOT NULL DEFAULT 'linehaul',
    ADD COLUMN IF NOT EXISTS is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Backfill name from schedule_code for existing rows
UPDATE tms.fuel_surcharge_schedules SET name = schedule_code WHERE name IS NULL;

-- ------------------------------------------------------------------ --
-- 5. Accessorial Charges
-- ------------------------------------------------------------------ --
CREATE TABLE tms.accessorial_charges (
    accessorial_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID          REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    charge_code         TEXT          NOT NULL,
    description         TEXT          NOT NULL,
    charge_type         TEXT          NOT NULL DEFAULT 'flat',
    rate_amount         NUMERIC(14,4) NOT NULL,
    currency            VARCHAR(3)    NOT NULL DEFAULT 'USD',
    applies_to_modes    TEXT[]        DEFAULT ARRAY['FTL','LTL','Parcel'],
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_acc_charge_type CHECK (charge_type IN (
        'flat','per_unit','percentage','per_mile','per_km'
    ))
);

CREATE INDEX idx_acc_carrier ON tms.accessorial_charges(carrier_id, is_active);

-- ------------------------------------------------------------------ --
-- 6. Shipment Costs
-- ------------------------------------------------------------------ --
CREATE TABLE tms.shipment_costs (
    cost_id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID          NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    rate_card_id        UUID          REFERENCES tms.carrier_rate_cards(rate_card_id),
    lane_id             UUID          REFERENCES tms.carrier_rate_lanes(lane_id),
    charge_code         TEXT          NOT NULL,
    charge_type         TEXT          NOT NULL,
    description         TEXT,
    quantity            NUMERIC(14,4),
    rate_amount         NUMERIC(14,4),
    amount              NUMERIC(14,4) NOT NULL,
    currency            VARCHAR(3)    NOT NULL DEFAULT 'USD',
    rated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    rated_by            TEXT          NOT NULL DEFAULT 'system',
    is_override         BOOLEAN       NOT NULL DEFAULT FALSE,
    override_reason     TEXT,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sc_shipment ON tms.shipment_costs(shipment_id);
CREATE INDEX idx_sc_rated_at ON tms.shipment_costs(rated_at);

-- ------------------------------------------------------------------ --
-- 7. updated_at triggers for new tables only
-- ------------------------------------------------------------------ --
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

-- ------------------------------------------------------------------ --
-- 8. Seed: rate cards, lanes, rate lines, FSC, accessorials
--    Uses first 3 active carriers if they exist; safe if none exist.
-- ------------------------------------------------------------------ --

DO $$
DECLARE
    v_carrier_id  UUID;
    v_card_ftl    UUID;
    v_card_ltl    UUID;
    v_card_parcel UUID;
    v_lane_ftl    UUID;
    v_lane_ltl    UUID;
    v_lane_parcel UUID;
BEGIN
    SELECT carrier_id INTO v_carrier_id
    FROM tms.carriers WHERE status = 'ACTIVE' LIMIT 1;

    IF v_carrier_id IS NULL THEN
        RAISE NOTICE 'No active carriers found — skipping seed data.';
        RETURN;
    END IF;

    -- Rate Cards
    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    VALUES (v_carrier_id, 'FTL Standard 2025', 'FTL', 'USD', '2025-01-01', '2025-12-31')
    RETURNING rate_card_id INTO v_card_ftl;

    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    VALUES (v_carrier_id, 'LTL Standard 2025', 'LTL', 'USD', '2025-01-01', '2025-12-31')
    RETURNING rate_card_id INTO v_card_ltl;

    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    VALUES (v_carrier_id, 'Parcel Standard 2025', 'Parcel', 'USD', '2025-01-01', '2025-12-31')
    RETURNING rate_card_id INTO v_card_parcel;

    -- Lanes
    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    VALUES (v_card_ftl, 'FTL - Any to Any', 'any', 'any', 0)
    RETURNING lane_id INTO v_lane_ftl;

    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    VALUES (v_card_ltl, 'LTL - Any to Any', 'any', 'any', 0)
    RETURNING lane_id INTO v_lane_ltl;

    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    VALUES (v_card_parcel, 'Parcel - Any to Any', 'any', 'any', 0)
    RETURNING lane_id INTO v_lane_parcel;

    -- FTL Rate Lines
    INSERT INTO tms.carrier_rate_lines (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order) VALUES
        (v_lane_ftl, 'base_flat', 'LINEHAUL', 'FTL Base Charge',     250.00, NULL, 200.00, 10),
        (v_lane_ftl, 'per_mile',  'LINEHAUL', 'FTL Per Mile Rate',     2.85, 'mi', NULL,   20),
        (v_lane_ftl, 'minimum',   'MINIMUM',  'FTL Minimum Charge',  500.00, NULL, NULL,   30);

    -- LTL Rate Lines
    INSERT INTO tms.carrier_rate_lines (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order) VALUES
        (v_lane_ltl, 'per_lb',     'LINEHAUL', 'LTL Per Pound Rate',   0.18, 'lb',     45.00, 10),
        (v_lane_ltl, 'per_pallet', 'LINEHAUL', 'LTL Per Pallet Rate', 38.00, 'pallet', NULL,  20),
        (v_lane_ltl, 'minimum',    'MINIMUM',  'LTL Minimum Charge',  85.00, NULL,     NULL,  30);

    -- Parcel Rate Lines
    INSERT INTO tms.carrier_rate_lines (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order) VALUES
        (v_lane_parcel, 'base_flat', 'LINEHAUL', 'Parcel Base Fee',       8.50, NULL, NULL,  10),
        (v_lane_parcel, 'per_kg',    'LINEHAUL', 'Parcel Per KG Rate',    1.25, 'kg', NULL,  20),
        (v_lane_parcel, 'minimum',   'MINIMUM',  'Parcel Minimum Charge', 12.00, NULL, NULL, 30);

    -- Fuel Surcharges
    INSERT INTO tms.fuel_surcharge_schedules
        (schedule_code, carrier_id, name, mode, effective_date, expiry_date, rate_type, rate_value, basis, is_active)
    VALUES
        ('FSC-FTL-2025',    v_carrier_id, 'FTL Fuel Surcharge 2025',    'FTL',    '2025-01-01', '2025-12-31', 'percentage', 18.5, 'linehaul', TRUE),
        ('FSC-LTL-2025',    v_carrier_id, 'LTL Fuel Surcharge 2025',    'LTL',    '2025-01-01', '2025-12-31', 'percentage', 22.0, 'linehaul', TRUE),
        ('FSC-PARCEL-2025', v_carrier_id, 'Parcel Fuel Surcharge 2025', 'Parcel', '2025-01-01', '2025-12-31', 'percentage', 15.0, 'linehaul', TRUE)
    ON CONFLICT (schedule_code) DO NOTHING;

    -- Accessorials
    INSERT INTO tms.accessorial_charges (carrier_id, charge_code, description, charge_type, rate_amount, applies_to_modes) VALUES
        (v_carrier_id, 'LIFTGATE',    'Liftgate Service',      'flat',     75.00, ARRAY['FTL','LTL','Parcel']),
        (v_carrier_id, 'RESIDENTIAL', 'Residential Delivery',  'flat',     45.00, ARRAY['LTL','Parcel']),
        (v_carrier_id, 'DETENTION',   'Detention (per hour)',   'per_unit', 85.00, ARRAY['FTL','LTL']),
        (v_carrier_id, 'INSIDEDEL',   'Inside Delivery',        'flat',     95.00, ARRAY['LTL','Parcel']),
        (v_carrier_id, 'REDELIVERY',  'Redelivery Attempt',     'flat',     65.00, ARRAY['LTL','Parcel']),
        (v_carrier_id, 'APPOINTMENT', 'Appointment Scheduling', 'flat',     35.00, ARRAY['FTL','LTL','Parcel']);

    RAISE NOTICE 'Seed data inserted for carrier %', v_carrier_id;
END;
$$;

COMMIT;
