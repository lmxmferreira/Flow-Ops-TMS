-- ============================================================
-- Migration: 019_e2e_traceability.sql
-- TMS-E2E-001 through TMS-E2E-010: End-to-End Traceability
-- ============================================================

BEGIN;

-- ── E2E-001: Process lifecycle tracker ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.process_lifecycle (
    lifecycle_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID        NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    -- Stage completion flags
    po_linked           BOOLEAN     NOT NULL DEFAULT FALSE,
    po_linked_at        TIMESTAMPTZ,
    released            BOOLEAN     NOT NULL DEFAULT FALSE,
    released_at         TIMESTAMPTZ,
    shipment_planned    BOOLEAN     NOT NULL DEFAULT FALSE,
    shipment_planned_at TIMESTAMPTZ,
    tendered            BOOLEAN     NOT NULL DEFAULT FALSE,
    tendered_at         TIMESTAMPTZ,
    tender_accepted     BOOLEAN     NOT NULL DEFAULT FALSE,
    tender_accepted_at  TIMESTAMPTZ,
    in_transit          BOOLEAN     NOT NULL DEFAULT FALSE,
    in_transit_at       TIMESTAMPTZ,
    delivered           BOOLEAN     NOT NULL DEFAULT FALSE,
    delivered_at        TIMESTAMPTZ,
    costed              BOOLEAN     NOT NULL DEFAULT FALSE,
    costed_at           TIMESTAMPTZ,
    allocated           BOOLEAN     NOT NULL DEFAULT FALSE,
    allocated_at        TIMESTAMPTZ,
    carrier_invoiced    BOOLEAN     NOT NULL DEFAULT FALSE,
    carrier_invoiced_at TIMESTAMPTZ,
    audited             BOOLEAN     NOT NULL DEFAULT FALSE,
    audited_at          TIMESTAMPTZ,
    payment_approved    BOOLEAN     NOT NULL DEFAULT FALSE,
    payment_approved_at TIMESTAMPTZ,
    client_billed       BOOLEAN     NOT NULL DEFAULT FALSE,
    client_billed_at    TIMESTAMPTZ,
    closed              BOOLEAN     NOT NULL DEFAULT FALSE,
    closed_at           TIMESTAMPTZ,
    -- Current stage
    current_stage       TEXT        NOT NULL DEFAULT 'planned',
    -- exceptions
    has_exceptions      BOOLEAN     NOT NULL DEFAULT FALSE,
    exception_count     INTEGER     NOT NULL DEFAULT 0,
    -- Audit
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_plc_stage CHECK (current_stage IN (
        'planned','released','tendered','accepted','in_transit',
        'delivered','costed','allocated','invoiced','audited',
        'payment_approved','billed','closed','exception'
    ))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_plc_shipment ON tms.process_lifecycle(shipment_id);
CREATE INDEX IF NOT EXISTS idx_plc_stage ON tms.process_lifecycle(current_stage);
CREATE INDEX IF NOT EXISTS idx_plc_exceptions ON tms.process_lifecycle(has_exceptions) WHERE has_exceptions = TRUE;

-- ── E2E-008: Universal reference index ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.reference_index (
    ref_index_id    UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    ref_number      TEXT    NOT NULL,
    ref_type        TEXT    NOT NULL,
    -- po_number | shipment_number | bol_number | invoice_number
    -- | bill_number | release_number | voucher_number | tracking_number
    entity_type     TEXT    NOT NULL,
    -- purchase_order | shipment | order_release | document | carrier_invoice | client_bill
    entity_id       UUID    NOT NULL,
    -- Optional cross-references
    parent_ref      TEXT,
    parent_type     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ri_ref    ON tms.reference_index(ref_number);
CREATE INDEX IF NOT EXISTS idx_ri_type   ON tms.reference_index(ref_type, entity_type);
CREATE INDEX IF NOT EXISTS idx_ri_entity ON tms.reference_index(entity_type, entity_id);

-- ── E2E-007: Charge traceability chain ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.traceability_links (
    link_id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source charge
    shipment_cost_id    UUID    REFERENCES tms.shipment_costs(cost_id) ON DELETE CASCADE,
    client_charge_id    UUID    REFERENCES tms.client_charges(client_charge_id) ON DELETE CASCADE,
    -- Source rate/contract
    rate_card_id        UUID    REFERENCES tms.carrier_rate_cards(rate_card_id),
    contract_reference  TEXT,
    -- Allocation
    allocation_id       UUID    REFERENCES tms.charge_allocations(allocation_id),
    -- Invoice / bill / payment
    carrier_invoice_ref TEXT,
    carrier_invoice_id  UUID,
    client_bill_ref     TEXT,
    client_bill_id      UUID,
    voucher_ref         TEXT,
    payment_ref         TEXT,
    payment_id          UUID,
    -- Adjustment / audit
    is_manual_adjustment BOOLEAN NOT NULL DEFAULT FALSE,
    adjustment_reason   TEXT,
    audit_result        TEXT,
    -- Audit
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tl_cost     ON tms.traceability_links(shipment_cost_id) WHERE shipment_cost_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tl_charge   ON tms.traceability_links(client_charge_id) WHERE client_charge_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tl_invoice  ON tms.traceability_links(carrier_invoice_id) WHERE carrier_invoice_id IS NOT NULL;

-- ── E2E-003: PO line quantity ledger ──────────────────────────────
CREATE TABLE IF NOT EXISTS tms.po_line_quantity_ledger (
    ledger_id           UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_line_id UUID NOT NULL REFERENCES tms.purchase_order_lines(purchase_order_line_id) ON DELETE CASCADE,
    -- Quantity buckets
    ordered_qty         NUMERIC(14,4) NOT NULL DEFAULT 0,
    released_qty        NUMERIC(14,4) NOT NULL DEFAULT 0,
    planned_qty         NUMERIC(14,4) NOT NULL DEFAULT 0,
    shipped_qty         NUMERIC(14,4) NOT NULL DEFAULT 0,
    delivered_qty       NUMERIC(14,4) NOT NULL DEFAULT 0,
    received_qty        NUMERIC(14,4) NOT NULL DEFAULT 0,
    canceled_qty        NUMERIC(14,4) NOT NULL DEFAULT 0,
    -- Computed
    remaining_qty       NUMERIC(14,4) GENERATED ALWAYS AS
        (ordered_qty - released_qty - canceled_qty) STORED,
    uom                 TEXT,
    -- Audit
    last_event          TEXT,
    last_event_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_polql_line ON tms.po_line_quantity_ledger(purchase_order_line_id);

-- ── E2E-010: Exception log ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.lifecycle_exceptions (
    exception_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID    REFERENCES tms.shipments(shipment_id) ON DELETE SET NULL,
    entity_type         TEXT    NOT NULL,
    entity_id           UUID,
    exception_type      TEXT    NOT NULL,
    -- missing_document | quantity_mismatch | cost_variance | invoice_mismatch
    -- | unmatched_invoice | overdue | rate_expired | allocation_error
    severity            TEXT    NOT NULL DEFAULT 'warning',
    -- info | warning | error | critical
    description         TEXT    NOT NULL,
    lifecycle_stage     TEXT,
    is_resolved         BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_by         TEXT,
    resolved_at         TIMESTAMPTZ,
    resolution_notes    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_le_shipment  ON tms.lifecycle_exceptions(shipment_id) WHERE shipment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_le_resolved  ON tms.lifecycle_exceptions(is_resolved, severity);
CREATE INDEX IF NOT EXISTS idx_le_type      ON tms.lifecycle_exceptions(exception_type);

DO $$ BEGIN
    CREATE TRIGGER trg_plc_updated_at
        BEFORE UPDATE ON tms.process_lifecycle
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_polql_updated_at
        BEFORE UPDATE ON tms.po_line_quantity_ledger
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- Seed lifecycle records for existing shipments
INSERT INTO tms.process_lifecycle (shipment_id, po_linked, released, shipment_planned, costed, current_stage)
SELECT s.shipment_id, TRUE, TRUE, TRUE, TRUE, 'costed'
FROM tms.shipments s
WHERE NOT EXISTS (
    SELECT 1 FROM tms.process_lifecycle p WHERE p.shipment_id = s.shipment_id
)
ON CONFLICT DO NOTHING;

-- Seed reference index for existing shipments
INSERT INTO tms.reference_index (ref_number, ref_type, entity_type, entity_id)
SELECT s.shipment_number, 'shipment_number', 'shipment', s.shipment_id
FROM tms.shipments s
WHERE NOT EXISTS (
    SELECT 1 FROM tms.reference_index r
    WHERE r.entity_id = s.shipment_id AND r.ref_type = 'shipment_number'
)
ON CONFLICT DO NOTHING;

-- Seed reference index for existing POs
INSERT INTO tms.reference_index (ref_number, ref_type, entity_type, entity_id)
SELECT p.po_number, 'po_number', 'purchase_order', p.purchase_order_id
FROM tms.purchase_orders p
WHERE NOT EXISTS (
    SELECT 1 FROM tms.reference_index r
    WHERE r.entity_id = p.purchase_order_id AND r.ref_type = 'po_number'
)
ON CONFLICT DO NOTHING;
