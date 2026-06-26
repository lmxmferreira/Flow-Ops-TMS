-- ============================================================
-- Migration: 016_reason_codes.sql
-- TMS-RATE-015: Manual charges, adjustments, overrides, approvals
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tms.adjustment_reason_codes (
    reason_code_id  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    reason_code     TEXT    NOT NULL UNIQUE,
    description     TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'adjustment',
    -- adjustment | override | approval | manual_charge | dispute
    applies_to      TEXT[]  NOT NULL DEFAULT ARRAY['carrier','client'],
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_rc_category CHECK (category IN (
        'adjustment','override','approval','manual_charge','dispute'
    ))
);

CREATE INDEX IF NOT EXISTS idx_arc_code     ON tms.adjustment_reason_codes(reason_code);
CREATE INDEX IF NOT EXISTS idx_arc_category ON tms.adjustment_reason_codes(category, is_active);

COMMIT;

-- Seed standard reason codes
INSERT INTO tms.adjustment_reason_codes
    (reason_code, description, category, applies_to, requires_approval)
VALUES
    ('RATE_ERROR',        'Incorrect rate applied',                   'override',       ARRAY['carrier','client'], FALSE),
    ('FUEL_ADJUSTMENT',   'Fuel surcharge correction',                'adjustment',     ARRAY['carrier','client'], FALSE),
    ('WEIGHT_CORRECTION', 'Weight discrepancy corrected',             'adjustment',     ARRAY['carrier'],          FALSE),
    ('DETENTION_ACTUAL',  'Actual detention charges from carrier',    'manual_charge',  ARRAY['carrier'],          FALSE),
    ('ACCESSORIAL_ADD',   'Additional accessorial charge',            'manual_charge',  ARRAY['carrier','client'], FALSE),
    ('CUSTOMER_DISPUTE',  'Client disputed charge',                   'dispute',        ARRAY['client'],           TRUE),
    ('CARRIER_CONCESSION','Carrier credit or concession',             'adjustment',     ARRAY['carrier'],          FALSE),
    ('INVOICE_VARIANCE',  'Carrier invoice differs from estimate',    'override',       ARRAY['carrier'],          TRUE),
    ('MANAGEMENT_FEE',    'Management fee adjustment',                'adjustment',     ARRAY['client'],           FALSE),
    ('CONTRACTUAL_ADJ',   'Contractual rate adjustment',              'override',       ARRAY['carrier','client'], TRUE),
    ('DATA_CORRECTION',   'Data entry error corrected',               'override',       ARRAY['carrier','client'], FALSE),
    ('APPROVED_OVERRIDE', 'Management approved override',             'approval',       ARRAY['carrier','client'], FALSE),
    ('CREDIT_NOTE',       'Credit note applied',                      'adjustment',     ARRAY['carrier','client'], TRUE),
    ('SURCHARGE_WAIVER',  'Surcharge waived by carrier',              'adjustment',     ARRAY['carrier'],          FALSE),
    ('BILLING_ADJUSTMENT','Client billing adjustment',                'adjustment',     ARRAY['client'],           TRUE)
ON CONFLICT (reason_code) DO NOTHING;
