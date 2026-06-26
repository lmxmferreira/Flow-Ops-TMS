-- ============================================================
-- Migration: 012_billing_rules.sql
-- TMS-RATE-011: Client-specific billing rule engine
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tms.client_billing_rules (
    rule_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_party_id   UUID        NOT NULL REFERENCES tms.parties(party_id) ON DELETE CASCADE,
    rule_name           TEXT        NOT NULL,
    rule_type           TEXT        NOT NULL,
    -- markup | margin | pass_through | management_fee | fixed_fee | minimum_billing | fsc_billing
    applies_to_modes    TEXT[]      NOT NULL DEFAULT ARRAY['FTL','LTL','Parcel'],
    applies_to_charges  TEXT[]      NOT NULL DEFAULT ARRAY['all'],
    -- e.g. ['LINEHAUL'] or ['all']
    rule_params         JSONB       NOT NULL DEFAULT '{}',
    -- markup:        {"markup_type":"percentage","markup_value":15}
    -- margin:        {"target_margin_pct":20,"adjust_to_meet":true}
    -- pass_through:  {"charge_codes":["FSC","TOLLS"]}
    -- management_fee:{"fee_type":"percentage","fee_value":2.5,"basis":"carrier_total"}
    -- fixed_fee:     {"amount":50,"currency":"USD","description":"Admin Fee"}
    -- minimum_billing:{"minimum_amount":500,"currency":"USD"}
    -- fsc_billing:   {"billing_method":"pass_through"} or {"markup_pct":5}
    priority            INTEGER     NOT NULL DEFAULT 0,
    effective_date      DATE        NOT NULL DEFAULT CURRENT_DATE,
    expiry_date         DATE,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    notes               TEXT,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_cbr_rule_type CHECK (rule_type IN (
        'markup','margin','pass_through','management_fee',
        'fixed_fee','minimum_billing','fsc_billing'
    ))
);

CREATE INDEX IF NOT EXISTS idx_cbr_customer   ON tms.client_billing_rules(customer_party_id, is_active);
CREATE INDEX IF NOT EXISTS idx_cbr_type       ON tms.client_billing_rules(rule_type, is_active);
CREATE INDEX IF NOT EXISTS idx_cbr_effective  ON tms.client_billing_rules(effective_date, expiry_date);

DO $$ BEGIN
    CREATE TRIGGER trg_cbr_updated_at
        BEFORE UPDATE ON tms.client_billing_rules
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;

-- Seed example rules for Acme Corporation
DO $$
DECLARE v_customer_id UUID;
BEGIN
    SELECT party_id INTO v_customer_id FROM tms.parties WHERE party_code = 'CUST-001' LIMIT 1;
    IF v_customer_id IS NULL THEN
        RAISE NOTICE 'CUST-001 not found, skipping seed.'; RETURN;
    END IF;

    INSERT INTO tms.client_billing_rules
        (customer_party_id, rule_name, rule_type, applies_to_modes,
         applies_to_charges, rule_params, priority, effective_date, is_active)
    VALUES
        (v_customer_id, 'Standard 15% Markup on Linehaul', 'markup',
         ARRAY['FTL','LTL'], ARRAY['base_flat','per_mile','per_km','per_cwt'],
         '{"markup_type":"percentage","markup_value":15}', 10, CURRENT_DATE, TRUE),

        (v_customer_id, 'FSC Pass-Through', 'pass_through',
         ARRAY['FTL','LTL','Parcel'], ARRAY['fuel_surcharge'],
         '{"charge_codes":["FSC"]}', 20, CURRENT_DATE, TRUE),

        (v_customer_id, 'Accessorials Pass-Through', 'pass_through',
         ARRAY['FTL','LTL','Parcel'], ARRAY['accessorial'],
         '{"charge_codes":["all"]}', 30, CURRENT_DATE, TRUE),

        (v_customer_id, 'Monthly Management Fee 2%', 'management_fee',
         ARRAY['FTL','LTL','Parcel'], ARRAY['all'],
         '{"fee_type":"percentage","fee_value":2.5,"basis":"carrier_total","description":"Management Fee"}',
         40, CURRENT_DATE, TRUE),

        (v_customer_id, 'Minimum Billing $500', 'minimum_billing',
         ARRAY['FTL','LTL'], ARRAY['all'],
         '{"minimum_amount":500,"currency":"USD"}', 50, CURRENT_DATE, TRUE)

    ON CONFLICT DO NOTHING;
    RAISE NOTICE 'Billing rules seeded for customer %', v_customer_id;
END $$;
