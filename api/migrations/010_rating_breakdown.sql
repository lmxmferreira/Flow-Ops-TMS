-- ============================================================
-- Migration: 010_rating_breakdown.sql
-- TMS-RATE-009: Detailed rating breakdown with tax and audit fields
-- ============================================================

BEGIN;

ALTER TABLE tms.shipment_costs
    ADD COLUMN IF NOT EXISTS calculation_basis  TEXT,
    ADD COLUMN IF NOT EXISTS tax_rate           NUMERIC(8,4)  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS tax_amount         NUMERIC(14,4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS override_reason    TEXT,
    ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ   NOT NULL DEFAULT NOW();

-- Index for fast breakdown lookups
CREATE INDEX IF NOT EXISTS idx_sc_shipment_charge
    ON tms.shipment_costs(shipment_id, charge_type);

COMMIT;
