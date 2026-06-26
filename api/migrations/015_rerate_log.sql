-- ============================================================
-- Migration: 015_rerate_log.sql
-- TMS-RATE-014: Re-rating log and change tracking
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tms.rerate_log (
    rerate_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    trigger_reason      TEXT        NOT NULL,
    -- rate_change | shipment_fact_change | contract_change | tax_change | allocation_change | manual
    changed_fields      TEXT[]      DEFAULT ARRAY[]::TEXT[],
    -- Before amounts
    prev_carrier_cost   NUMERIC(14,4),
    prev_client_charge  NUMERIC(14,4),
    prev_margin         NUMERIC(14,4),
    -- After amounts
    new_carrier_cost    NUMERIC(14,4),
    new_client_charge   NUMERIC(14,4),
    new_margin          NUMERIC(14,4),
    -- Change deltas
    carrier_cost_delta  NUMERIC(14,4),
    client_charge_delta NUMERIC(14,4),
    margin_delta        NUMERIC(14,4),
    -- Status
    status              TEXT        NOT NULL DEFAULT 'completed',
    -- pending | completed | failed
    error_message       TEXT,
    -- Who / when
    triggered_by        TEXT,
    completed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes               TEXT,

    CONSTRAINT chk_rl_reason CHECK (trigger_reason IN (
        'rate_change','shipment_fact_change','contract_change',
        'tax_change','allocation_change','manual','initial_rating'
    ))
);

CREATE INDEX IF NOT EXISTS idx_rl_shipment ON tms.rerate_log(shipment_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_rl_reason   ON tms.rerate_log(trigger_reason);

COMMIT;
