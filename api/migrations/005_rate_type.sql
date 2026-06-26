-- ============================================================
-- Migration: 005_rate_type.sql
-- TMS-RATE-002: Add rate type classification to carrier_rate_cards
-- ============================================================

BEGIN;

ALTER TABLE tms.carrier_rate_cards
    ADD COLUMN IF NOT EXISTS rate_type          TEXT NOT NULL DEFAULT 'contract',
    ADD COLUMN IF NOT EXISTS customer_party_id  UUID REFERENCES tms.parties(party_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS contract_reference TEXT,
    ADD COLUMN IF NOT EXISTS route_priority     INTEGER NOT NULL DEFAULT 0;

ALTER TABLE tms.carrier_rate_cards
    ADD CONSTRAINT chk_rc_rate_type CHECK (rate_type IN (
        'contract','tariff','spot','route_guide',
        'customer_specific','carrier_specific'
    ));

CREATE INDEX IF NOT EXISTS idx_rc_rate_type     ON tms.carrier_rate_cards(rate_type, status);
CREATE INDEX IF NOT EXISTS idx_rc_customer      ON tms.carrier_rate_cards(customer_party_id) WHERE customer_party_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rc_route_priority ON tms.carrier_rate_cards(route_priority DESC);

-- Update existing seed rate cards with appropriate rate types
UPDATE tms.carrier_rate_cards SET rate_type = 'contract'  WHERE name LIKE 'FTL%';
UPDATE tms.carrier_rate_cards SET rate_type = 'tariff'    WHERE name LIKE 'LTL%';
UPDATE tms.carrier_rate_cards SET rate_type = 'contract'  WHERE name LIKE 'Parcel%';

COMMIT;
