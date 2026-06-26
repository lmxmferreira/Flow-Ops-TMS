-- ============================================================
-- Migration: 007_fuel_surcharge_v2.sql
-- TMS-RATE-006: Enhanced fuel surcharge calculation
-- Fixed: existing fuel_index_id FK points to lookup_values
-- We use a separate column tms_fuel_index_id for our new table
-- ============================================================

BEGIN;

-- 1. Fuel Price Indexes
CREATE TABLE IF NOT EXISTS tms.fuel_indexes (
    fuel_index_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    index_code       TEXT          NOT NULL UNIQUE,
    index_name       TEXT          NOT NULL,
    description      TEXT,
    unit             TEXT          NOT NULL DEFAULT 'USD_PER_GALLON',
    current_price    NUMERIC(10,4) NOT NULL DEFAULT 0,
    price_updated_at TIMESTAMPTZ,
    is_active        BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 2. Fuel Index Price History
CREATE TABLE IF NOT EXISTS tms.fuel_index_history (
    history_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    fuel_index_id   UUID          NOT NULL REFERENCES tms.fuel_indexes(fuel_index_id) ON DELETE CASCADE,
    price           NUMERIC(10,4) NOT NULL,
    effective_date  DATE          NOT NULL,
    source          TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fih_index_date
    ON tms.fuel_index_history(fuel_index_id, effective_date DESC);

-- 3. Extend fuel_surcharge_schedules
--    Use tms_fuel_index_id (separate from existing fuel_index_id → lookup_values)
ALTER TABLE tms.fuel_surcharge_schedules
    ADD COLUMN IF NOT EXISTS calc_method       TEXT          NOT NULL DEFAULT 'fixed',
    ADD COLUMN IF NOT EXISTS tms_fuel_index_id UUID          REFERENCES tms.fuel_indexes(fuel_index_id),
    ADD COLUMN IF NOT EXISTS base_fuel_price   NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS price_increment   NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS increment_rate    NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS distance_bands    JSONB,
    ADD COLUMN IF NOT EXISTS contract_rules    JSONB,
    ADD COLUMN IF NOT EXISTS fsc_notes         TEXT;

DO $$ BEGIN
    ALTER TABLE tms.fuel_surcharge_schedules
        ADD CONSTRAINT chk_fsc_calc_method CHECK (calc_method IN (
            'fixed','index_based','sliding_scale','distance_band'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_fsc_tms_fuel_index
    ON tms.fuel_surcharge_schedules(tms_fuel_index_id)
    WHERE tms_fuel_index_id IS NOT NULL;

-- 4. Add FSC audit columns to shipment_costs
ALTER TABLE tms.shipment_costs
    ADD COLUMN IF NOT EXISTS fsc_fuel_price  NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS fsc_base_price  NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS fsc_index_code  TEXT;

-- Trigger
DO $$ BEGIN
    CREATE TRIGGER trg_fuel_indexes_updated_at
        BEFORE UPDATE ON tms.fuel_indexes
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;

-- Seed outside transaction so failure doesn't roll back DDL
INSERT INTO tms.fuel_indexes (index_code, index_name, description, unit, current_price, price_updated_at)
VALUES
    ('DOE_DIESEL_US',  'DOE US Weekly Diesel',       'US DOE weekly retail diesel price', 'USD_PER_GALLON', 3.85, NOW()),
    ('DOE_DIESEL_CA',  'DOE US-Canada Diesel',        'Cross-border diesel reference',     'USD_PER_GALLON', 4.10, NOW()),
    ('OPIS_DIESEL',    'OPIS Diesel Spot',             'OPIS daily diesel spot price',      'USD_PER_GALLON', 3.72, NOW()),
    ('PLATTS_JET',     'Platts Jet Fuel',              'Platts jet fuel for air freight',   'USD_PER_GALLON', 2.95, NOW()),
    ('BRENT_CRUDE',    'Brent Crude Oil',              'Brent crude oil price',             'USD_PER_BARREL',80.50, NOW())
ON CONFLICT (index_code) DO NOTHING;

-- Seed price history
DO $$
DECLARE v_id UUID;
BEGIN
    SELECT fuel_index_id INTO v_id FROM tms.fuel_indexes WHERE index_code = 'DOE_DIESEL_US';
    IF v_id IS NOT NULL THEN
        INSERT INTO tms.fuel_index_history (fuel_index_id, price, effective_date, source)
        VALUES
            (v_id, 3.85, '2026-06-23', 'DOE EIA'),
            (v_id, 3.91, '2026-06-16', 'DOE EIA'),
            (v_id, 3.88, '2026-06-09', 'DOE EIA'),
            (v_id, 3.95, '2026-06-02', 'DOE EIA'),
            (v_id, 4.02, '2026-05-26', 'DOE EIA'),
            (v_id, 4.15, '2026-05-19', 'DOE EIA'),
            (v_id, 4.08, '2026-05-12', 'DOE EIA')
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Link existing FSC seed records to DOE index
UPDATE tms.fuel_surcharge_schedules
SET tms_fuel_index_id = (SELECT fuel_index_id FROM tms.fuel_indexes WHERE index_code = 'DOE_DIESEL_US'),
    base_fuel_price   = 3.50,
    calc_method       = 'fixed'
WHERE schedule_code LIKE 'FSC-%';
