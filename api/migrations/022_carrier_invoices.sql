-- ============================================================
-- Migration: 022_carrier_invoices.sql
-- TMS-CINV-001 through TMS-CINV-015: Carrier Invoice Management
-- ============================================================

BEGIN;

-- ── Extend carrier_invoices with missing fields ────────────────────
ALTER TABLE tms.carrier_invoices
    ADD COLUMN IF NOT EXISTS invoice_type        TEXT NOT NULL DEFAULT 'standard',
    -- standard | accessorial_only | supplemental | correction | credit | debit | reversal
    ADD COLUMN IF NOT EXISTS source_channel      TEXT NOT NULL DEFAULT 'manual',
    -- manual | spreadsheet | edi | api | portal | generated
    ADD COLUMN IF NOT EXISTS parent_invoice_id   UUID REFERENCES tms.carrier_invoices(carrier_invoice_id),
    ADD COLUMN IF NOT EXISTS shipment_id         UUID REFERENCES tms.shipments(shipment_id),
    ADD COLUMN IF NOT EXISTS status              TEXT NOT NULL DEFAULT 'received',
    -- received | pending_validation | matched | exception | disputed
    -- | approved | rejected | exported | paid | partially_paid | canceled | reversed | closed
    ADD COLUMN IF NOT EXISTS matched_amount      NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS variance_amount     NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS variance_pct        NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS is_duplicate        BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS duplicate_of_id     UUID,
    ADD COLUMN IF NOT EXISTS on_hold             BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS hold_reason         TEXT,
    ADD COLUMN IF NOT EXISTS held_by             TEXT,
    ADD COLUMN IF NOT EXISTS held_at             TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approved_by         TEXT,
    ADD COLUMN IF NOT EXISTS approved_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS exported_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS paid_amount         NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS paid_at             TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS payment_reference   TEXT,
    ADD COLUMN IF NOT EXISTS closed_at           TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS notes               TEXT,
    ADD COLUMN IF NOT EXISTS created_by          TEXT;

DO $$ BEGIN
    ALTER TABLE tms.carrier_invoices
        ADD CONSTRAINT chk_ci_status CHECK (status IN (
            'received','pending_validation','matched','exception','disputed',
            'approved','rejected','exported','paid','partially_paid',
            'canceled','reversed','closed'
        ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE tms.carrier_invoices
        ADD CONSTRAINT chk_ci_type CHECK (invoice_type IN (
            'standard','accessorial_only','supplemental','correction',
            'credit','debit','reversal'
        ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_ci_carrier    ON tms.carrier_invoices(carrier_id, status);
CREATE INDEX IF NOT EXISTS idx_ci_shipment   ON tms.carrier_invoices(shipment_id) WHERE shipment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ci_status     ON tms.carrier_invoices(status);
CREATE INDEX IF NOT EXISTS idx_ci_hold       ON tms.carrier_invoices(on_hold) WHERE on_hold = TRUE;
CREATE INDEX IF NOT EXISTS idx_ci_due        ON tms.carrier_invoices(due_date) WHERE status NOT IN ('paid','closed','canceled');

-- ── Extend carrier_invoice_lines ───────────────────────────────────
ALTER TABLE tms.carrier_invoice_lines
    ADD COLUMN IF NOT EXISTS charge_code         TEXT,
    ADD COLUMN IF NOT EXISTS matched_cost_id     UUID REFERENCES tms.shipment_costs(cost_id),
    ADD COLUMN IF NOT EXISTS match_status        TEXT NOT NULL DEFAULT 'unmatched',
    -- unmatched | matched | variance | disputed | approved
    ADD COLUMN IF NOT EXISTS variance_amount     NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS on_hold             BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS hold_reason         TEXT;

-- ── CINV-013: Invoice audit history ───────────────────────────────
CREATE TABLE IF NOT EXISTS tms.carrier_invoice_audit (
    audit_id            UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_invoice_id  UUID    NOT NULL REFERENCES tms.carrier_invoices(carrier_invoice_id) ON DELETE CASCADE,
    event_type          TEXT    NOT NULL,
    -- created | status_changed | matched | exception | disputed | approved | paid | hold | exported
    from_status         TEXT,
    to_status           TEXT,
    amount_before       NUMERIC(14,4),
    amount_after        NUMERIC(14,4),
    notes               TEXT,
    performed_by        TEXT,
    performed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cia_invoice ON tms.carrier_invoice_audit(carrier_invoice_id);
CREATE INDEX IF NOT EXISTS idx_cia_date    ON tms.carrier_invoice_audit(performed_at DESC);

-- ── CINV-007: Duplicate detection config ──────────────────────────
CREATE TABLE IF NOT EXISTS tms.invoice_duplicate_rules (
    rule_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name       TEXT    NOT NULL,
    check_fields    TEXT[]  NOT NULL DEFAULT ARRAY['carrier_id','carrier_invoice_number'],
    -- carrier_id | invoice_number | invoice_date | invoice_total | shipment_ref
    tolerance_days  INTEGER NOT NULL DEFAULT 0,
    tolerance_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO tms.invoice_duplicate_rules (rule_name, check_fields)
VALUES
    ('Exact Match', ARRAY['carrier_id','carrier_invoice_number']),
    ('Same Carrier + Amount + Date', ARRAY['carrier_id','invoice_total_amount','invoice_date'])
ON CONFLICT DO NOTHING;

COMMIT;
