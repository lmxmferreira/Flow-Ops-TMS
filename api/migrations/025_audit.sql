-- ============================================================
-- Migration: 025_audit.sql
-- TMS-AUDIT-001 through TMS-AUDIT-020: Freight Audit, Dispute & Pay
-- ============================================================

BEGIN;

-- ── Extend freight_audit_results ──────────────────────────────────
ALTER TABLE tms.freight_audit_results
    ADD COLUMN IF NOT EXISTS audit_type         TEXT NOT NULL DEFAULT 'auto',
    -- auto | manual | re_audit
    ADD COLUMN IF NOT EXISTS exception_type     TEXT,
    -- overcharge | undercharge | missing_charge | duplicate | invalid
    -- | incorrect_fuel | unauthorized_accessorial | incorrect_tax
    -- | incorrect_currency | incorrect_distance | incorrect_reference
    ADD COLUMN IF NOT EXISTS disposition        TEXT NOT NULL DEFAULT 'pending',
    -- pending | approved | rejected | disputed | short_pay | override | escalated
    ADD COLUMN IF NOT EXISTS override_reason    TEXT,
    ADD COLUMN IF NOT EXISTS overridden_by      TEXT,
    ADD COLUMN IF NOT EXISTS overridden_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS shipment_id        UUID REFERENCES tms.shipments(shipment_id),
    ADD COLUMN IF NOT EXISTS charge_code        TEXT,
    ADD COLUMN IF NOT EXISTS audit_rule_name    TEXT;

CREATE INDEX IF NOT EXISTS idx_far_invoice   ON tms.freight_audit_results(carrier_invoice_id);
CREATE INDEX IF NOT EXISTS idx_far_status    ON tms.freight_audit_results(audit_status_id, disposition);
CREATE INDEX IF NOT EXISTS idx_far_shipment  ON tms.freight_audit_results(shipment_id) WHERE shipment_id IS NOT NULL;

-- ── AUDIT-004: Audit tolerance config ─────────────────────────────
CREATE TABLE IF NOT EXISTS tms.audit_tolerances (
    tolerance_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    tolerance_name      TEXT    NOT NULL,
    carrier_id          UUID    REFERENCES tms.carriers(carrier_id),
    transport_mode      TEXT,
    charge_code         TEXT,
    variance_pct        NUMERIC(5,2) NOT NULL DEFAULT 5.0,
    variance_amount     NUMERIC(14,4) NOT NULL DEFAULT 10.0,
    use_pct             BOOLEAN NOT NULL DEFAULT TRUE,
    -- if TRUE use variance_pct, else use variance_amount
    auto_approve        BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO tms.audit_tolerances (tolerance_name, variance_pct, variance_amount, use_pct)
VALUES
    ('Default 5%',        5.0, 10.0, TRUE),
    ('Linehaul 2%',       2.0, 25.0, TRUE),
    ('Fuel 3%',           3.0, 15.0, TRUE),
    ('Accessorial $25',   5.0, 25.0, FALSE),
    ('Tax Exact',         0.0,  0.0, TRUE)
ON CONFLICT DO NOTHING;

-- ── Extend disputes ────────────────────────────────────────────────
ALTER TABLE tms.disputes
    ADD COLUMN IF NOT EXISTS dispute_reason_text TEXT,
    ADD COLUMN IF NOT EXISTS expected_amount     NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS audit_result_id     UUID REFERENCES tms.freight_audit_results(freight_audit_result_id),
    ADD COLUMN IF NOT EXISTS carrier_responded_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS response_channel    TEXT,
    -- portal | email | edi | api
    ADD COLUMN IF NOT EXISTS resolved_by         TEXT,
    ADD COLUMN IF NOT EXISTS payment_blocked     BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS created_by          TEXT;

CREATE INDEX IF NOT EXISTS idx_disp_invoice  ON tms.disputes(carrier_invoice_id) WHERE carrier_invoice_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_disp_status   ON tms.disputes(dispute_status_id);

-- ── Extend vouchers ────────────────────────────────────────────────
ALTER TABLE tms.vouchers
    ADD COLUMN IF NOT EXISTS payment_status     TEXT NOT NULL DEFAULT 'pending',
    -- pending | exported | paid | partial_paid | short_pay
    -- | held | reversed | failed | confirmed
    ADD COLUMN IF NOT EXISTS payment_amount     NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS payment_reference  TEXT,
    ADD COLUMN IF NOT EXISTS payment_date       DATE,
    ADD COLUMN IF NOT EXISTS payment_method     TEXT,
    -- ach | wire | check | credit_card
    ADD COLUMN IF NOT EXISTS erp_voucher_id     TEXT,
    ADD COLUMN IF NOT EXISTS remittance_sent    BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS remittance_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS hold_reason        TEXT,
    ADD COLUMN IF NOT EXISTS created_by         TEXT;

CREATE INDEX IF NOT EXISTS idx_vou_status  ON tms.vouchers(payment_status);
CREATE INDEX IF NOT EXISTS idx_vou_carrier ON tms.vouchers(payee_party_id, payment_status);

-- ── AUDIT-019: Audit history ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.audit_history (
    history_id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_invoice_id  UUID    NOT NULL REFERENCES tms.carrier_invoices(carrier_invoice_id) ON DELETE CASCADE,
    event_type          TEXT    NOT NULL,
    -- received | audit_started | auto_approved | exception_raised | disputed
    -- | dispute_resolved | approved | rejected | voucher_created | exported
    -- | payment_received | payment_confirmed | closed
    from_status         TEXT,
    to_status           TEXT,
    amount              NUMERIC(14,4),
    performed_by        TEXT,
    notes               TEXT,
    performed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ah_invoice ON tms.audit_history(carrier_invoice_id, performed_at DESC);

COMMIT;
