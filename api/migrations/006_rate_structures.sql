-- ============================================================
-- Migration: 006_rate_structures.sql
-- TMS-RATE-003: Extended rate structure types
-- ============================================================

BEGIN;

-- Drop old constraint and replace with expanded set
ALTER TABLE tms.carrier_rate_lines
    DROP CONSTRAINT IF EXISTS chk_rl_charge_type;

ALTER TABLE tms.carrier_rate_lines
    ADD CONSTRAINT chk_rl_charge_type CHECK (charge_type IN (
        'base_flat',
        'per_mile',
        'per_km',
        'per_lb',
        'per_kg',
        'per_cwt',
        'per_pallet',
        'per_carton',
        'per_unit',
        'per_stop',
        'per_zone',
        'per_lane',
        'per_container',
        'percentage_of_value',
        'custom_formula',
        'minimum',
        'maximum'
    ));

-- Add formula_text column for custom_formula type
ALTER TABLE tms.carrier_rate_lines
    ADD COLUMN IF NOT EXISTS formula_text TEXT,
    ADD COLUMN IF NOT EXISTS zone_value   TEXT;   -- for per_zone: zone code/name

COMMIT;
