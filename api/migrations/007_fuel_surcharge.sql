-- ============================================================
-- Migration: 007_fuel_surcharge.sql
-- TMS-RATE-006: Enhanced fuel surcharge calculation
-- Adds fuel indexes, base/current price, distance bands
-- ============================================================

BEGIN;

-- ------------------------------------------------------------------ --
-- 1. Fuel Price Indexes (e.g. DOE Weekly Diesel)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.fuel_indexes (
    fuel_index_id   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    index_code      TEXT          NOT NULL UNIQUE,
    index_name      TEXT          NOT NULL,
    description     TEXT,
    unit            TEXT          NOT NULL DEFAULT 'USD_PER_GALLON',
    current_price   NUMERIC(10,4) NOT NULL DEFAULT 0,
    price_updated_at TIMESTAMPTZ,
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------ --
-- 2. Fuel Index Price History
-- ------------------------------------------------------------------ --
CREATE TABLE tms.fuel_index_history (
    history_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    fuel_index_id   UUID          NOT NULL REFERENCES tms.fuel_indexes(fuel_index_id) ON DELETE CASCADE,
    price           NUMERIC(10,4) NOT NULL,
    effective_date  DATE          NOT NULL,
    source          TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fih_index_date ON tms.fuel_index_history(fuel_index_id, effective_date DESC);

-- ------------------------------------------------------------------ --
-- 3. Extend fuel_surcharge_schedules with index-based fields
-- ------------------------------------------------------------------ --
ALTER TABLE tms.fuel_surcharge_schedules
    ADD COLUMN IF NOT EXISTS calc_method      TEXT    NOT NULL DEFAULT 'fixed',
    -- fixed | index_based | sliding_scale | distance_band
    ADD COLUMN IF NOT EXISTS fuel_index_id    UUID    REFERENCES tms.fuel_indexes(fuel_index_id),
    ADD COLUMN IF NOT EXISTS base_fuel_price  NUMERIC(10,4),   -- index price when contract was set
    ADD COLUMN IF NOT EXISTS price_increment  NUMERIC(10,4),   -- per $ change in fuel price
    ADD COLUMN IF NOT EXISTS increment_rate   NUMERIC(10,4),   -- FSC rate change per increment
    ADD COLUMN IF NOT EXISTS distance_bands   JSONB,
    -- [{"min_km": 0, "max_km": 500, "rate": 15.0}, {"min_km": 500, "max_km": null, "rate": 18.5}]
    ADD COLUMN IF NOT EXISTS contract_rules   JSONB,
    -- arbitrary carrier-specific overrides
    ADD COLUMN IF NOT EXISTS notes            TEXT;

-- Add constraint for calc_method
ALTER TABLE tms.fuel_surcharge_schedules
    ADD CONSTRAINT chk_fsc_calc_method CHECK (calc_method IN (
        'fixed', 'index_based', 'sliding_scale', 'distance_band'
    ));

CREATE INDEX IF NOT EXISTS idx_fsc_fuel_index ON tms.fuel_surcharge_schedules(fuel_index_id)
    WHERE fuel_index_id IS NOT NULL;

-- Add FSC calculation log to shipment_costs (track what fuel price was used)
ALTER TABLE tms.shipment_costs
    ADD COLUMN IF NOT EXISTS fsc_fuel_price   NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS fsc_base_price   NUMERIC(10,4),
    ADD COLUMN IF NOT EXISTS fsc_index_code   TEXT;

-- Trigger for fuel_indexes updated_at
CREATE TRIGGER trg_fuel_indexes_updated_at
    BEFORE UPDATE ON tms.fuel_indexes
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

-- ------------------------------------------------------------------ --
-- 4. Seed: standard fuel indexes
-- ------------------------------------------------------------------ --
INSERT INTO tms.fuel_indexes (index_code, index_name, description, unit, current_price, price_updated_at)
VALUES
    ('DOE_DIESEL_US',   'DOE US Weekly Diesel',         'US Department of Energy weekly retail diesel price', 'USD_PER_GALLON', 3.85, NOW()),
    ('DOE_DIESEL_CA',   'DOE US-Canada Diesel Index',   'Cross-border diesel reference price',                'USD_PER_GALLON', 4.10, NOW()),
    ('OPIS_DIESEL',     'OPIS Diesel Spot',              'OPIS daily diesel spot price',                       'USD_PER_GALLON', 3.72, NOW()),
    ('PLATTS_JET',      'Platts Jet Fuel',               'Platts jet fuel index for air freight',              'USD_PER_GALLON', 2.95, NOW()),
    ('BRENT_CRUDE',     'Brent Crude Oil',               'Brent crude oil price',                              'USD_PER_BARREL',80.50, NOW())
ON CONFLICT (index_code) DO NOTHING;

-- Seed price history for DOE diesel
WITH idx AS (SELECT fuel_index_id FROM tms.fuel_indexes WHERE index_code = 'DOE_DIESEL_US')
INSERT INTO tms.fuel_index_history (fuel_index_id, price, effective_date, source)
SELECT fuel_index_id, price, effective_date::date, 'DOE EIA Weekly Survey'
FROM idx, (VALUES
    (3.85, '2026-06-23'),
    (3.91, '2026-06-16'),
    (3.88, '2026-06-09'),
    (3.95, '2026-06-02'),
    (4.02, '2026-05-26'),
    (4.15, '2026-05-19'),
    (4.08, '2026-05-12')
) AS v(price, effective_date)
ON CONFLICT DO NOTHING;

-- Update existing FSC seed records with index linkage
UPDATE tms.fuel_surcharge_schedules
SET
    fuel_index_id  = (SELECT fuel_index_id FROM tms.fuel_indexes WHERE index_code = 'DOE_DIESEL_US'),
    base_fuel_price = 3.50,
    calc_method    = 'fixed'
WHERE schedule_code LIKE 'FSC-%'
  AND calc_method = 'fixed';

COMMIT;
