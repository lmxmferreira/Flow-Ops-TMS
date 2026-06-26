-- ============================================================
-- Migration: 004_rating.sql
-- TMS-RATE-001: Carrier freight cost calculation at shipment level
-- Hierarchy: Rate Card → Lane → Rate Lines
-- ============================================================

BEGIN;

-- ------------------------------------------------------------------ --
-- 1. Carrier Rate Cards  (one per carrier + mode)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.carrier_rate_cards (
    rate_card_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID        REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    name                TEXT        NOT NULL,
    mode                TEXT        NOT NULL,   -- FTL | LTL | Parcel | Rail | Ocean | Air | Intermodal
    currency            VARCHAR(3)  NOT NULL DEFAULT 'USD',
    effective_date      DATE        NOT NULL,
    expiry_date         DATE,
    status              TEXT        NOT NULL DEFAULT 'active',  -- active | inactive | expired
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rc_mode CHECK (mode IN ('FTL','LTL','Parcel','Rail','Ocean','Air','Intermodal')),
    CONSTRAINT chk_rc_status CHECK (status IN ('active','inactive','expired')),
    CONSTRAINT chk_rc_dates CHECK (expiry_date IS NULL OR expiry_date > effective_date)
);

CREATE INDEX idx_rc_carrier_mode ON tms.carrier_rate_cards(carrier_id, mode, status);
CREATE INDEX idx_rc_effective    ON tms.carrier_rate_cards(effective_date, expiry_date);

-- ------------------------------------------------------------------ --
-- 2. Carrier Rate Lanes  (one per origin→destination pair under a card)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.carrier_rate_lanes (
    lane_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_card_id        UUID        NOT NULL REFERENCES tms.carrier_rate_cards(rate_card_id) ON DELETE CASCADE,
    lane_name           TEXT        NOT NULL,
    origin_type         TEXT        NOT NULL DEFAULT 'any',  -- any | zip | state | country | region
    origin_value        TEXT,       -- e.g. "ON", "M5V", "CA", "NORTHEAST"
    destination_type    TEXT        NOT NULL DEFAULT 'any',
    destination_value   TEXT,
    min_weight_kg       NUMERIC(12,3),
    max_weight_kg       NUMERIC(12,3),
    min_distance_km     NUMERIC(10,2),
    max_distance_km     NUMERIC(10,2),
    priority            INTEGER     NOT NULL DEFAULT 0,  -- higher = more specific, wins tie-break
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_lane_origin_type      CHECK (origin_type      IN ('any','zip','state','country','region')),
    CONSTRAINT chk_lane_destination_type CHECK (destination_type IN ('any','zip','state','country','region'))
);

CREATE INDEX idx_lane_card     ON tms.carrier_rate_lanes(rate_card_id, is_active);
CREATE INDEX idx_lane_priority ON tms.carrier_rate_lanes(rate_card_id, priority DESC);

-- ------------------------------------------------------------------ --
-- 3. Carrier Rate Lines  (charge components per lane)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.carrier_rate_lines (
    rate_line_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    lane_id             UUID        NOT NULL REFERENCES tms.carrier_rate_lanes(lane_id) ON DELETE CASCADE,
    charge_type         TEXT        NOT NULL,   -- base_flat | per_mile | per_km | per_kg | per_lb | per_pallet | per_carton | minimum | maximum
    charge_code         TEXT        NOT NULL DEFAULT 'LINEHAUL',
    description         TEXT,
    rate_amount         NUMERIC(14,4) NOT NULL,
    currency            VARCHAR(3)  NOT NULL DEFAULT 'USD',
    uom                 TEXT,       -- km | mi | kg | lb | pallet | carton (null for flat)
    min_charge          NUMERIC(14,4),
    max_charge          NUMERIC(14,4),
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    sort_order          INTEGER     NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rl_charge_type CHECK (charge_type IN (
        'base_flat','per_mile','per_km','per_kg','per_lb','per_pallet','per_carton','minimum','maximum'
    ))
);

CREATE INDEX idx_rl_lane ON tms.carrier_rate_lines(lane_id, is_active);

-- ------------------------------------------------------------------ --
-- 4. Fuel Surcharge Schedules
-- ------------------------------------------------------------------ --
CREATE TABLE tms.fuel_surcharge_schedules (
    fsc_id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID        REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    name                TEXT        NOT NULL,
    mode                TEXT,       -- null = all modes
    effective_date      DATE        NOT NULL,
    expiry_date         DATE,
    rate_type           TEXT        NOT NULL DEFAULT 'percentage',  -- percentage | per_mile | per_km | flat
    rate_value          NUMERIC(10,4) NOT NULL,
    basis               TEXT        NOT NULL DEFAULT 'linehaul',    -- linehaul | gross | distance
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_fsc_rate_type CHECK (rate_type IN ('percentage','per_mile','per_km','flat')),
    CONSTRAINT chk_fsc_basis     CHECK (basis     IN ('linehaul','gross','distance'))
);

CREATE INDEX idx_fsc_carrier ON tms.fuel_surcharge_schedules(carrier_id, is_active);

-- ------------------------------------------------------------------ --
-- 5. Accessorial Charge Definitions
-- ------------------------------------------------------------------ --
CREATE TABLE tms.accessorial_charges (
    accessorial_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id          UUID        REFERENCES tms.carriers(carrier_id) ON DELETE CASCADE,
    charge_code         TEXT        NOT NULL,
    description         TEXT        NOT NULL,
    charge_type         TEXT        NOT NULL DEFAULT 'flat',  -- flat | per_unit | percentage | per_mile | per_km
    rate_amount         NUMERIC(14,4) NOT NULL,
    currency            VARCHAR(3)  NOT NULL DEFAULT 'USD',
    applies_to_modes    TEXT[]      DEFAULT ARRAY['FTL','LTL','Parcel'],
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_acc_charge_type CHECK (charge_type IN ('flat','per_unit','percentage','per_mile','per_km'))
);

CREATE INDEX idx_acc_carrier ON tms.accessorial_charges(carrier_id, is_active);

-- ------------------------------------------------------------------ --
-- 6. Shipment Costs  (rated cost breakdown per shipment)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.shipment_costs (
    cost_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    rate_card_id        UUID        REFERENCES tms.carrier_rate_cards(rate_card_id),
    lane_id             UUID        REFERENCES tms.carrier_rate_lanes(lane_id),
    charge_code         TEXT        NOT NULL,
    charge_type         TEXT        NOT NULL,  -- base_flat | per_mile | per_km | per_kg | per_lb | per_pallet | per_carton | fuel_surcharge | accessorial | minimum | maximum
    description         TEXT,
    quantity            NUMERIC(14,4),
    rate_amount         NUMERIC(14,4),
    amount              NUMERIC(14,4) NOT NULL,
    currency            VARCHAR(3)  NOT NULL DEFAULT 'USD',
    rated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rated_by            TEXT        NOT NULL DEFAULT 'system',  -- system | user:<id>
    is_override         BOOLEAN     NOT NULL DEFAULT FALSE,
    override_reason     TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sc_shipment ON tms.shipment_costs(shipment_id);
CREATE INDEX idx_sc_rated_at ON tms.shipment_costs(rated_at);

-- ------------------------------------------------------------------ --
-- Triggers: updated_at
-- ------------------------------------------------------------------ --
DO $$ BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'carrier_rate_cards','carrier_rate_lanes','carrier_rate_lines',
        'fuel_surcharge_schedules','accessorial_charges','shipment_costs'
    ]) LOOP
        EXECUTE format('
            CREATE TRIGGER trg_%s_updated_at
            BEFORE UPDATE ON tms.%s
            FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at()',
            tbl, tbl);
    END LOOP;
END $$;

-- ------------------------------------------------------------------ --
-- Seed Data: sample rate cards for demo carriers
-- ------------------------------------------------------------------ --

-- We'll insert rate cards for any existing active carriers.
-- If no carriers exist yet, seed a placeholder.

WITH carrier_sample AS (
    SELECT carrier_id FROM tms.carriers WHERE status = 'ACTIVE' LIMIT 3
),
-- FTL card
ftl_card AS (
    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    SELECT carrier_id, 'FTL Standard 2025', 'FTL', 'USD', '2025-01-01', '2025-12-31'
    FROM carrier_sample
    LIMIT 1
    RETURNING rate_card_id
),
-- LTL card
ltl_card AS (
    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    SELECT carrier_id, 'LTL Standard 2025', 'LTL', 'USD', '2025-01-01', '2025-12-31'
    FROM carrier_sample
    LIMIT 1
    RETURNING rate_card_id
),
-- Parcel card
parcel_card AS (
    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    SELECT carrier_id, 'Parcel Standard 2025', 'Parcel', 'USD', '2025-01-01', '2025-12-31'
    FROM carrier_sample
    LIMIT 1
    RETURNING rate_card_id
),
-- FTL lane: any → any (catch-all)
ftl_lane AS (
    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    SELECT rate_card_id, 'North America - Any to Any', 'any', 'any', 0
    FROM ftl_card
    RETURNING lane_id
),
-- LTL lane: any → any
ltl_lane AS (
    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    SELECT rate_card_id, 'LTL - Any to Any', 'any', 'any', 0
    FROM ltl_card
    RETURNING lane_id
),
-- Parcel lane: any → any
parcel_lane AS (
    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    SELECT rate_card_id, 'Parcel - Any to Any', 'any', 'any', 0
    FROM parcel_card
    RETURNING lane_id
),
-- FTL rate lines: flat + per_mile
ftl_lines AS (
    INSERT INTO tms.carrier_rate_lines
        (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    SELECT lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order
    FROM ftl_lane, (VALUES
        ('base_flat', 'LINEHAUL', 'FTL Base Charge',    250.00,  NULL,   200.00, 10),
        ('per_mile',  'LINEHAUL', 'FTL Per Mile Rate',    2.85,  'mi',   NULL,   20),
        ('minimum',   'MINIMUM',  'FTL Minimum Charge',  500.00,  NULL,   NULL,   30)
    ) AS v(charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    RETURNING rate_line_id
),
-- LTL rate lines: per_lb + per_pallet
ltl_lines AS (
    INSERT INTO tms.carrier_rate_lines
        (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    SELECT lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order
    FROM ltl_lane, (VALUES
        ('per_lb',     'LINEHAUL', 'LTL Per Pound Rate',   0.18, 'lb',  45.00, 10),
        ('per_pallet', 'LINEHAUL', 'LTL Per Pallet Rate', 38.00, 'pallet', NULL, 20),
        ('minimum',    'MINIMUM',  'LTL Minimum Charge',   85.00, NULL,  NULL,  30)
    ) AS v(charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    RETURNING rate_line_id
),
-- Parcel rate lines: per_kg
parcel_lines AS (
    INSERT INTO tms.carrier_rate_lines
        (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    SELECT lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order
    FROM parcel_lane, (VALUES
        ('base_flat', 'LINEHAUL', 'Parcel Base Fee',      8.50, NULL,  NULL,   10),
        ('per_kg',    'LINEHAUL', 'Parcel Per KG Rate',   1.25, 'kg',  NULL,   20),
        ('minimum',   'MINIMUM',  'Parcel Minimum Charge',12.00, NULL,  NULL,  30)
    ) AS v(charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    RETURNING rate_line_id
),
-- FSC schedules
fsc AS (
    INSERT INTO tms.fuel_surcharge_schedules
        (carrier_id, name, mode, effective_date, expiry_date, rate_type, rate_value, basis)
    SELECT carrier_id, name, mode, '2025-01-01'::date, '2025-12-31'::date, rate_type, rate_value, basis
    FROM carrier_sample,
    (VALUES
        ('FTL Fuel Surcharge 2025',    'FTL',    'percentage', 18.5, 'linehaul'),
        ('LTL Fuel Surcharge 2025',    'LTL',    'percentage', 22.0, 'linehaul'),
        ('Parcel Fuel Surcharge 2025', 'Parcel', 'percentage', 15.0, 'linehaul')
    ) AS v(name, mode, rate_type, rate_value, basis)
    RETURNING fsc_id
),
-- Accessorials
acc AS (
    INSERT INTO tms.accessorial_charges
        (carrier_id, charge_code, description, charge_type, rate_amount, applies_to_modes)
    SELECT carrier_id, charge_code, description, charge_type, rate_amount, applies_to_modes::text[]
    FROM carrier_sample,
    (VALUES
        ('LIFTGATE',   'Liftgate Service',        'flat',       75.00, '{FTL,LTL,Parcel}'),
        ('RESIDENTIAL','Residential Delivery',     'flat',       45.00, '{LTL,Parcel}'),
        ('DETENTION',  'Detention (per hour)',     'per_unit',   85.00, '{FTL,LTL}'),
        ('INSIDEDEL',  'Inside Delivery',          'flat',       95.00, '{LTL,Parcel}'),
        ('REDELIVERY', 'Redelivery Attempt',       'flat',       65.00, '{LTL,Parcel}'),
        ('APPOINTMENT','Appointment Scheduling',   'flat',       35.00, '{FTL,LTL,Parcel}')
    ) AS v(charge_code, description, charge_type, rate_amount, applies_to_modes)
    RETURNING accessorial_id
)
SELECT 'Seed complete' AS result;

COMMIT;
