-- ============================================================
-- Migration: 027_financials.sql
-- TMS-FIN-001 through TMS-FIN-010: Accruals, Accounting & Financial Controls
-- ============================================================

BEGIN;

-- ── FIN-001/002: Extend accruals ──────────────────────────────────
ALTER TABLE tms.accruals
    ADD COLUMN IF NOT EXISTS accrual_milestone  TEXT,
    -- planned | tendered | accepted | picked_up | delivered | completed | closed
    ADD COLUMN IF NOT EXISTS accrual_level      TEXT NOT NULL DEFAULT 'shipment',
    -- shipment | load | order | order_line | po | po_line
    -- | customer | supplier | project | cost_center | gl_account
    ADD COLUMN IF NOT EXISTS status             TEXT NOT NULL DEFAULT 'open',
    -- open | reversed | relieved | partially_relieved | closed
    ADD COLUMN IF NOT EXISTS gl_account_code    TEXT,
    ADD COLUMN IF NOT EXISTS cost_center_code   TEXT,
    ADD COLUMN IF NOT EXISTS project_code       TEXT,
    ADD COLUMN IF NOT EXISTS charge_code        TEXT,
    ADD COLUMN IF NOT EXISTS estimated_amount   NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS relieved_amount    NUMERIC(14,4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reversal_reason    TEXT,
    ADD COLUMN IF NOT EXISTS reversed_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reversed_by        TEXT,
    ADD COLUMN IF NOT EXISTS carrier_invoice_id UUID REFERENCES tms.carrier_invoices(carrier_invoice_id),
    ADD COLUMN IF NOT EXISTS created_by         TEXT;

CREATE INDEX IF NOT EXISTS idx_acc_shipment ON tms.accruals(shipment_id) WHERE shipment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_acc_status   ON tms.accruals(status);
CREATE INDEX IF NOT EXISTS idx_acc_period   ON tms.accruals(financial_period_id) WHERE financial_period_id IS NOT NULL;

-- ── FIN-004/005: GL distributions ─────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.gl_distributions (
    distribution_id     UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID    REFERENCES tms.shipments(shipment_id),
    carrier_invoice_id  UUID    REFERENCES tms.carrier_invoices(carrier_invoice_id),
    client_bill_id      UUID    REFERENCES tms.client_bills(client_bill_id),
    allocation_id       UUID    REFERENCES tms.charge_allocations(allocation_id),
    -- GL coding fields (FIN-005)
    gl_account_code     TEXT    NOT NULL,
    business_unit_code  TEXT,
    department_code     TEXT,
    cost_center_code    TEXT,
    project_code        TEXT,
    customer_code       TEXT,
    supplier_code       TEXT,
    carrier_code        TEXT,
    charge_code         TEXT,
    tax_code            TEXT,
    transport_mode      TEXT,
    -- Amounts
    debit_amount        NUMERIC(14,4) NOT NULL DEFAULT 0,
    credit_amount       NUMERIC(14,4) NOT NULL DEFAULT 0,
    currency_code       TEXT NOT NULL DEFAULT 'USD',
    base_currency_amount NUMERIC(14,4),
    exchange_rate       NUMERIC(12,6),
    -- Period
    accounting_date     DATE    NOT NULL DEFAULT CURRENT_DATE,
    fiscal_period       TEXT,
    -- Status
    status              TEXT    NOT NULL DEFAULT 'pending',
    -- pending | posted | reversed | error
    posted_at           TIMESTAMPTZ,
    exported_at         TIMESTAMPTZ,
    erp_journal_id      TEXT,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gld_shipment ON tms.gl_distributions(shipment_id) WHERE shipment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gld_gl_code  ON tms.gl_distributions(gl_account_code, fiscal_period);
CREATE INDEX IF NOT EXISTS idx_gld_status   ON tms.gl_distributions(status);

-- ── FIN-006: Financial periods ────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.financial_periods (
    period_id       UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    period_name     TEXT    NOT NULL,
    fiscal_year     INTEGER NOT NULL,
    period_number   INTEGER NOT NULL,
    start_date      DATE    NOT NULL,
    end_date        DATE    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'open',
    -- open | closing | closed | locked
    cutoff_date     DATE,
    closed_by       TEXT,
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_fp UNIQUE (fiscal_year, period_number)
);

-- Seed current + adjacent periods
INSERT INTO tms.financial_periods (period_name, fiscal_year, period_number, start_date, end_date, status)
VALUES
    ('FY2026-Q1', 2026, 1, '2026-01-01', '2026-03-31', 'closed'),
    ('FY2026-Q2', 2026, 2, '2026-04-01', '2026-06-30', 'open'),
    ('FY2026-Q3', 2026, 3, '2026-07-01', '2026-09-30', 'open'),
    ('FY2026-Q4', 2026, 4, '2026-10-01', '2026-12-31', 'open')
ON CONFLICT DO NOTHING;

-- ── FIN-007: Currency rate extensions ─────────────────────────────
ALTER TABLE tms.exchange_rates
    ADD COLUMN IF NOT EXISTS rate_type      TEXT NOT NULL DEFAULT 'spot',
    -- spot | average | closing | budget | custom
    ADD COLUMN IF NOT EXISTS is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS source         TEXT DEFAULT 'manual';

-- ── FIN-008: Tax calculation results ─────────────────────────────
CREATE TABLE IF NOT EXISTS tms.tax_calculations (
    tax_calc_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID    REFERENCES tms.shipments(shipment_id),
    carrier_invoice_id  UUID    REFERENCES tms.carrier_invoices(carrier_invoice_id),
    client_bill_id      UUID    REFERENCES tms.client_bills(client_bill_id),
    tax_rule_id         UUID    REFERENCES tms.tax_rules(tax_rule_id),
    taxable_amount      NUMERIC(14,4) NOT NULL,
    tax_rate            NUMERIC(8,4) NOT NULL,
    tax_amount          NUMERIC(14,4) NOT NULL,
    tax_code            TEXT,
    jurisdiction        TEXT,
    is_included         BOOLEAN NOT NULL DEFAULT FALSE,
    calculated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tc_shipment ON tms.tax_calculations(shipment_id) WHERE shipment_id IS NOT NULL;

-- ── FIN-009: Financial reconciliation ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.financial_reconciliation (
    recon_id            UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID    NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    recon_date          DATE    NOT NULL DEFAULT CURRENT_DATE,
    -- Cost columns
    planned_cost        NUMERIC(14,4),
    tendered_cost       NUMERIC(14,4),
    accrued_cost        NUMERIC(14,4),
    actual_carrier_cost NUMERIC(14,4),
    approved_payable    NUMERIC(14,4),
    paid_amount         NUMERIC(14,4),
    -- Revenue columns
    client_bill_amount  NUMERIC(14,4),
    received_amount     NUMERIC(14,4),
    -- Margin
    gross_margin        NUMERIC(14,4),
    margin_pct          NUMERIC(8,4),
    -- Status
    is_reconciled       BOOLEAN NOT NULL DEFAULT FALSE,
    variances           JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fr_shipment ON tms.financial_reconciliation(shipment_id);

-- ── FIN-010: Financial approvals ──────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.financial_approvals (
    approval_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_type       TEXT    NOT NULL,
    -- rate_override | invoice_approval | billing_adjustment | allocation_adjustment
    -- | payment_release | accounting_export
    entity_type         TEXT    NOT NULL,
    entity_id           UUID    NOT NULL,
    requested_by        TEXT    NOT NULL,
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    rejected_by         TEXT,
    rejected_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    status              TEXT    NOT NULL DEFAULT 'pending',
    -- pending | approved | rejected | expired | withdrawn
    amount              NUMERIC(14,4),
    notes               TEXT,
    expires_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fa_entity  ON tms.financial_approvals(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_fa_status  ON tms.financial_approvals(status, approval_type);
CREATE INDEX IF NOT EXISTS idx_fa_pending ON tms.financial_approvals(status) WHERE status = 'pending';

COMMIT;
