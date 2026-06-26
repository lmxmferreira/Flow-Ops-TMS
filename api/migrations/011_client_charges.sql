-- ============================================================
-- Migration: 011_client_charges.sql
-- TMS-RATE-010: Client charges separate from carrier costs
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tms.client_charges (
    client_charge_id  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id       UUID          NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    carrier_cost_id   UUID          REFERENCES tms.shipment_costs(cost_id) ON DELETE SET NULL,
    charge_code       TEXT          NOT NULL,
    charge_type       TEXT          NOT NULL,
    description       TEXT,
    calculation_basis TEXT,
    quantity          NUMERIC(14,4),
    rate_amount       NUMERIC(14,4) NOT NULL DEFAULT 0,
    amount            NUMERIC(14,4) NOT NULL DEFAULT 0,
    currency          VARCHAR(3)    NOT NULL DEFAULT 'USD',
    -- Markup over carrier cost
    markup_type       TEXT          NOT NULL DEFAULT 'none',
    -- none | fixed | percentage
    markup_value      NUMERIC(10,4) NOT NULL DEFAULT 0,
    markup_amount     NUMERIC(14,4) NOT NULL DEFAULT 0,
    -- Tax
    tax_rate          NUMERIC(8,4)  NOT NULL DEFAULT 0,
    tax_amount        NUMERIC(14,4) NOT NULL DEFAULT 0,
    -- Billing status
    billed_flag       BOOLEAN       NOT NULL DEFAULT FALSE,
    billed_at         TIMESTAMPTZ,
    invoice_id        UUID,
    -- Audit
    is_override       BOOLEAN       NOT NULL DEFAULT FALSE,
    override_reason   TEXT,
    created_by        TEXT,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_cc_markup_type CHECK (markup_type IN ('none','fixed','percentage'))
);

CREATE INDEX IF NOT EXISTS idx_cc_shipment   ON tms.client_charges(shipment_id);
CREATE INDEX IF NOT EXISTS idx_cc_carrier_cost ON tms.client_charges(carrier_cost_id) WHERE carrier_cost_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cc_billed     ON tms.client_charges(shipment_id, billed_flag);

-- Trigger for updated_at
DO $$ BEGIN
    CREATE TRIGGER trg_client_charges_updated_at
        BEFORE UPDATE ON tms.client_charges
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
