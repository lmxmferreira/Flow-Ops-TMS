-- ============================================================
-- Migration: 026_billing.sql
-- TMS-BILL-001 through TMS-BILL-020: Client Billing & Receivables
-- ============================================================

BEGIN;

-- ── Extend client_bills ────────────────────────────────────────────
ALTER TABLE tms.client_bills
    ADD COLUMN IF NOT EXISTS bill_level       TEXT NOT NULL DEFAULT 'shipment',
    -- shipment | order | order_line | order_release | po_header | po_line
    -- | customer | project | cost_center | stop | consolidated | billing_cycle
    ADD COLUMN IF NOT EXISTS billing_cycle_id UUID,
    ADD COLUMN IF NOT EXISTS contract_id      UUID,
    ADD COLUMN IF NOT EXISTS status           TEXT NOT NULL DEFAULT 'draft',
    -- draft | pending_approval | approved | sent | disputed
    -- | partially_paid | paid | canceled | credited | rebilled | closed
    ADD COLUMN IF NOT EXISTS on_hold          BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS hold_reason      TEXT,
    ADD COLUMN IF NOT EXISTS approved_by      TEXT,
    ADD COLUMN IF NOT EXISTS approved_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sent_at          TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sent_channel     TEXT,
    -- email | portal | edi | api | print | accounting_export
    ADD COLUMN IF NOT EXISTS payment_status   TEXT NOT NULL DEFAULT 'unpaid',
    -- unpaid | partial | paid | disputed | written_off
    ADD COLUMN IF NOT EXISTS paid_amount      NUMERIC(14,4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS outstanding_amount NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS is_duplicate_check BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS parent_bill_id   UUID REFERENCES tms.client_bills(client_bill_id),
    ADD COLUMN IF NOT EXISTS erp_bill_id      TEXT,
    ADD COLUMN IF NOT EXISTS notes            TEXT,
    ADD COLUMN IF NOT EXISTS created_by       TEXT;

DO $$ BEGIN
    ALTER TABLE tms.client_bills ADD CONSTRAINT chk_cb_status CHECK (status IN (
        'draft','pending_approval','approved','sent','disputed',
        'partially_paid','paid','canceled','credited','rebilled','closed'
    ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_cb_customer ON tms.client_bills(customer_party_id, status);
CREATE INDEX IF NOT EXISTS idx_cb_status   ON tms.client_bills(status);
CREATE INDEX IF NOT EXISTS idx_cb_due      ON tms.client_bills(due_date) WHERE status NOT IN ('paid','closed','canceled');
CREATE INDEX IF NOT EXISTS idx_cb_hold     ON tms.client_bills(on_hold) WHERE on_hold = TRUE;

-- ── Extend client_bill_lines ───────────────────────────────────────
ALTER TABLE tms.client_bill_lines
    ADD COLUMN IF NOT EXISTS charge_code      TEXT,
    ADD COLUMN IF NOT EXISTS billing_rule_id  UUID REFERENCES tms.client_billing_rules(rule_id),
    ADD COLUMN IF NOT EXISTS carrier_cost_id  UUID REFERENCES tms.shipment_costs(cost_id),
    ADD COLUMN IF NOT EXISTS markup_pct       NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS margin_pct       NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS is_taxable       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS allocation_ref   TEXT,
    ADD COLUMN IF NOT EXISTS notes            TEXT;

-- ── BILL-020: Billing audit history ───────────────────────────────
CREATE TABLE IF NOT EXISTS tms.bill_audit_history (
    history_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_bill_id  UUID NOT NULL REFERENCES tms.client_bills(client_bill_id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    amount          NUMERIC(14,4),
    performed_by    TEXT,
    notes           TEXT,
    performed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bah_bill ON tms.bill_audit_history(client_bill_id, performed_at DESC);

-- ── BILL-008: Billing hold reasons config ─────────────────────────
CREATE TABLE IF NOT EXISTS tms.billing_hold_reasons (
    hold_reason_code TEXT PRIMARY KEY,
    description      TEXT NOT NULL,
    auto_release     BOOLEAN NOT NULL DEFAULT FALSE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE
);
INSERT INTO tms.billing_hold_reasons (hold_reason_code, description, auto_release) VALUES
    ('INCOMPLETE_SHIPMENT',    'Shipment not yet complete',             TRUE),
    ('MISSING_POD',            'Proof of delivery missing',             TRUE),
    ('INCOMPLETE_ALLOCATION',  'Cost allocation not finalized',         TRUE),
    ('MISSING_CUSTOMER_REF',   'Required customer reference missing',   FALSE),
    ('UNRESOLVED_DISPUTE',     'Active billing dispute',                TRUE),
    ('FAILED_VALIDATION',      'Billing validation failed',             FALSE),
    ('APPROVAL_REQUIRED',      'Pending billing approval',              TRUE),
    ('MANUAL_HOLD',            'Manually placed on hold',               FALSE)
ON CONFLICT DO NOTHING;

-- ── BILL-012: Billing disputes ────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.billing_disputes (
    dispute_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_bill_id  UUID NOT NULL REFERENCES tms.client_bills(client_bill_id) ON DELETE CASCADE,
    dispute_reason  TEXT NOT NULL,
    disputed_amount NUMERIC(14,4) NOT NULL,
    notes           TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    -- open | under_review | resolved | closed
    opened_by       TEXT,
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ,
    resolution_notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_bd_bill ON tms.billing_disputes(client_bill_id);

COMMIT;
