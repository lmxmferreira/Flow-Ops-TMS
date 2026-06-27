-- ============================================================
-- Migration: 023_allocation.sql
-- TMS-ALLOC-001 through TMS-ALLOC-015: Cost Allocation
-- ============================================================

BEGIN;

-- ── Extend charge_allocations with missing fields ──────────────────
ALTER TABLE tms.charge_allocations
    ADD COLUMN IF NOT EXISTS allocation_version  INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS gl_account_code     TEXT,
    ADD COLUMN IF NOT EXISTS responsible_party_id UUID REFERENCES tms.parties(party_id),
    ADD COLUMN IF NOT EXISTS responsible_party_type TEXT,
    -- customer | supplier | internal | carrier | shared
    ADD COLUMN IF NOT EXISTS charge_category     TEXT,
    -- freight | fuel | accessorial | tax | duty | surcharge | adjustment | discount
    ADD COLUMN IF NOT EXISTS is_manual_adjustment BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS adjustment_reason   TEXT,
    ADD COLUMN IF NOT EXISTS adjusted_by         TEXT,
    ADD COLUMN IF NOT EXISTS adjusted_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_current_version  BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_ca_version  ON tms.charge_allocations(shipment_id, allocation_version);
CREATE INDEX IF NOT EXISTS idx_ca_current  ON tms.charge_allocations(is_current_version) WHERE is_current_version = TRUE;
CREATE INDEX IF NOT EXISTS idx_ca_gl       ON tms.charge_allocations(gl_account_code) WHERE gl_account_code IS NOT NULL;

-- ── ALLOC-004: Allocation rules ────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.allocation_rules (
    rule_id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name           TEXT    NOT NULL,
    -- Scope — all NULL = applies to everything
    charge_category     TEXT,
    -- freight | fuel | accessorial | tax | duty | surcharge | adjustment | discount | ALL
    charge_code         TEXT,
    customer_party_id   UUID    REFERENCES tms.parties(party_id),
    carrier_id          UUID    REFERENCES tms.carriers(carrier_id),
    transport_mode      TEXT,
    business_unit_id    UUID    REFERENCES tms.business_units(business_unit_id),
    -- Allocation method (ALLOC-003)
    allocation_method   TEXT    NOT NULL DEFAULT 'equal',
    -- weight | volume | cube | chargeable_weight | quantity | pallet_count
    -- | carton_count | value | distance | stop_count | percentage | fixed | equal | custom
    allocation_level    TEXT    NOT NULL DEFAULT 'shipment',
    -- shipment | load | stop | order_release | order_line | po | po_line
    -- Responsible party (ALLOC-008)
    responsible_type    TEXT,
    -- customer | supplier | internal | carrier | shared
    gl_account_code     TEXT,
    priority            INTEGER NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ar_category ON tms.allocation_rules(charge_category, is_active);
CREATE INDEX IF NOT EXISTS idx_ar_priority ON tms.allocation_rules(priority DESC);

-- ── ALLOC-013: Allocation version history ─────────────────────────
CREATE TABLE IF NOT EXISTS tms.allocation_versions (
    version_id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id         UUID    NOT NULL REFERENCES tms.shipments(shipment_id) ON DELETE CASCADE,
    version_number      INTEGER NOT NULL,
    allocation_method   TEXT,
    total_allocated     NUMERIC(14,4),
    total_source        NUMERIC(14,4),
    is_balanced         BOOLEAN NOT NULL DEFAULT FALSE,
    triggered_by        TEXT,
    -- manual | cost_change | quantity_change | rule_change | recalculation
    snapshot            JSONB,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_av_shipment ON tms.allocation_versions(shipment_id, version_number DESC);

DO $$ BEGIN
    CREATE TRIGGER trg_ar_updated_at
        BEFORE UPDATE ON tms.allocation_rules
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- Seed default allocation rules
INSERT INTO tms.allocation_rules
    (rule_name, charge_category, allocation_method, allocation_level, responsible_type, priority)
VALUES
    ('Linehaul by Weight',      'freight',     'weight',    'po_line',   'customer', 10),
    ('Fuel by Weight',          'fuel',        'weight',    'po_line',   'customer', 20),
    ('Accessorial to Customer', 'accessorial', 'equal',     'stop',      'customer', 30),
    ('Tax Pass-through',        'tax',         'percentage','po_line',   'customer', 40),
    ('Duty to Supplier',        'duty',        'value',     'po_line',   'supplier', 50),
    ('Surcharge Equal Split',   'surcharge',   'equal',     'po_line',   'customer', 60),
    ('Discount Equal Split',    'discount',    'equal',     'po_line',   'customer', 70),
    ('Default Equal Split',     NULL,          'equal',     'shipment',  'customer',  0)
ON CONFLICT DO NOTHING;
