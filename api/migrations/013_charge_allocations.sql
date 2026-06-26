-- ============================================================
-- Migration: 013_charge_allocations.sql
-- TMS-RATE-012: Multi-level billing charge allocation
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tms.charge_allocations (
    allocation_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source charge (client charge being allocated)
    client_charge_id    UUID        REFERENCES tms.client_charges(client_charge_id) ON DELETE CASCADE,
    shipment_cost_id    UUID        REFERENCES tms.shipment_costs(cost_id) ON DELETE CASCADE,
    -- Allocation level (one of these will be populated)
    allocation_type     TEXT        NOT NULL,
    -- shipment | stop | order_release | po_header | po_line | customer | project | cost_center
    shipment_id         UUID        REFERENCES tms.shipments(shipment_id)           ON DELETE SET NULL,
    stop_id             UUID        REFERENCES tms.shipment_stops(stop_id)          ON DELETE SET NULL,
    release_id          UUID,
    purchase_order_id   UUID        REFERENCES tms.purchase_orders(purchase_order_id) ON DELETE SET NULL,
    po_line_id          UUID        REFERENCES tms.purchase_order_lines(purchase_order_line_id) ON DELETE SET NULL,
    customer_party_id   UUID        REFERENCES tms.parties(party_id)               ON DELETE SET NULL,
    project_id          UUID        REFERENCES tms.projects(project_id)             ON DELETE SET NULL,
    cost_center_id      UUID        REFERENCES tms.cost_centers(cost_center_id)     ON DELETE SET NULL,
    -- Allocation detail
    allocation_basis    TEXT        NOT NULL DEFAULT 'equal',
    -- equal | weight | value | volume | manual
    allocation_pct      NUMERIC(8,4) NOT NULL DEFAULT 100,
    allocation_amount   NUMERIC(14,4) NOT NULL DEFAULT 0,
    currency            VARCHAR(3)  NOT NULL DEFAULT 'USD',
    -- Audit
    notes               TEXT,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ca_type CHECK (allocation_type IN (
        'shipment','stop','order_release','po_header',
        'po_line','customer','project','cost_center'
    )),
    CONSTRAINT chk_ca_basis CHECK (allocation_basis IN (
        'equal','weight','value','volume','manual'
    ))
);

CREATE INDEX IF NOT EXISTS idx_ca_client_charge  ON tms.charge_allocations(client_charge_id);
CREATE INDEX IF NOT EXISTS idx_ca_shipment       ON tms.charge_allocations(shipment_id);
CREATE INDEX IF NOT EXISTS idx_ca_po             ON tms.charge_allocations(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_ca_po_line        ON tms.charge_allocations(po_line_id);
CREATE INDEX IF NOT EXISTS idx_ca_cost_center    ON tms.charge_allocations(cost_center_id);
CREATE INDEX IF NOT EXISTS idx_ca_project        ON tms.charge_allocations(project_id);
CREATE INDEX IF NOT EXISTS idx_ca_type           ON tms.charge_allocations(allocation_type);

DO $$ BEGIN
    CREATE TRIGGER trg_ca_updated_at
        BEFORE UPDATE ON tms.charge_allocations
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
