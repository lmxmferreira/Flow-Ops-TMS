-- ============================================================
-- Migration: 018_master_data.sql
-- TMS-MD-001 through TMS-MD-010: Master Data Module
-- ============================================================

BEGIN;

-- ── MD-001/002: Extend locations with master data fields ───────────
ALTER TABLE tms.locations
    ADD COLUMN IF NOT EXISTS location_subtype      TEXT,
    -- supplier | customer | warehouse | port | terminal | ramp
    -- | distribution_center | cross_dock | store | yard | service_point
    ADD COLUMN IF NOT EXISTS operating_hours_start TIME,
    ADD COLUMN IF NOT EXISTS operating_hours_end   TIME,
    ADD COLUMN IF NOT EXISTS operating_days        TEXT[],
    -- ['MON','TUE','WED','THU','FRI']
    ADD COLUMN IF NOT EXISTS appointment_required  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS appointment_lead_hrs  INTEGER,
    ADD COLUMN IF NOT EXISTS dock_count            INTEGER,
    ADD COLUMN IF NOT EXISTS contact_name          TEXT,
    ADD COLUMN IF NOT EXISTS contact_phone         TEXT,
    ADD COLUMN IF NOT EXISTS contact_email         TEXT,
    ADD COLUMN IF NOT EXISTS equipment_restrictions TEXT[],
    -- ['NO_53FT','REEFER_ONLY']
    ADD COLUMN IF NOT EXISTS accessorial_rules     JSONB,
    ADD COLUMN IF NOT EXISTS special_instructions  TEXT,
    ADD COLUMN IF NOT EXISTS geo_validated         BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS geo_validated_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS version_number        INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS approved_by           TEXT,
    ADD COLUMN IF NOT EXISTS approved_at           TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_loc_subtype  ON tms.locations(location_subtype) WHERE location_subtype IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_loc_active   ON tms.locations(is_active);

-- ── MD-003: Location aliases & external system IDs ─────────────────
CREATE TABLE IF NOT EXISTS tms.location_aliases (
    alias_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID    NOT NULL REFERENCES tms.locations(location_id) ON DELETE CASCADE,
    alias_type      TEXT    NOT NULL DEFAULT 'alias',
    -- alias | external_id | customer_code | supplier_code | erp_code
    alias_value     TEXT    NOT NULL,
    source_system   TEXT,
    party_id        UUID    REFERENCES tms.parties(party_id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_la_location ON tms.location_aliases(location_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_la_unique ON tms.location_aliases(alias_type, alias_value, source_system) WHERE is_active = TRUE;

-- ── MD-004: Item master ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.item_master (
    item_id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    item_number         TEXT    NOT NULL UNIQUE,
    description         TEXT    NOT NULL,
    -- Weight & dimensions
    weight_kg           NUMERIC(10,4),
    weight_lb           NUMERIC(10,4),
    length_cm           NUMERIC(10,4),
    width_cm            NUMERIC(10,4),
    height_cm           NUMERIC(10,4),
    cube_m3             NUMERIC(10,6),
    -- Freight classification
    freight_class       TEXT,
    -- 50|55|60|65|70|77.5|85|92.5|100|110|125|150|175|200|250|300|400|500
    nmfc_code           TEXT,
    commodity_code      TEXT,
    commodity_desc      TEXT,
    -- Hazmat
    is_hazmat           BOOLEAN NOT NULL DEFAULT FALSE,
    hazmat_class        TEXT,
    hazmat_un_number    TEXT,
    hazmat_packing_grp  TEXT,
    -- Temperature
    requires_temp_ctrl  BOOLEAN NOT NULL DEFAULT FALSE,
    temp_min_c          NUMERIC(6,2),
    temp_max_c          NUMERIC(6,2),
    -- Packaging
    packaging_type      TEXT,
    -- pallet | carton | drum | crate | bag | roll | piece
    units_per_pallet    INTEGER,
    units_per_carton    INTEGER,
    is_stackable        BOOLEAN NOT NULL DEFAULT TRUE,
    max_stack_height    INTEGER,
    -- UOM
    base_uom            TEXT    NOT NULL DEFAULT 'EA',
    -- Status / lifecycle (MD-009)
    status              TEXT    NOT NULL DEFAULT 'active',
    version_number      INTEGER NOT NULL DEFAULT 1,
    effective_date      DATE    NOT NULL DEFAULT CURRENT_DATE,
    expiry_date         DATE,
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_im_status CHECK (status IN ('draft','active','inactive','archived'))
);
CREATE INDEX IF NOT EXISTS idx_im_freight_class ON tms.item_master(freight_class);
CREATE INDEX IF NOT EXISTS idx_im_hazmat        ON tms.item_master(is_hazmat) WHERE is_hazmat = TRUE;
CREATE INDEX IF NOT EXISTS idx_im_status        ON tms.item_master(status);

-- ── MD-005: Item aliases ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.item_aliases (
    item_alias_id   UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id         UUID    NOT NULL REFERENCES tms.item_master(item_id) ON DELETE CASCADE,
    alias_type      TEXT    NOT NULL DEFAULT 'alias',
    -- alias | customer_part | supplier_part | upc | ean | sku | erp_code
    alias_value     TEXT    NOT NULL,
    source_system   TEXT,
    party_id        UUID    REFERENCES tms.parties(party_id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ia_item ON tms.item_aliases(item_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ia_unique ON tms.item_aliases(alias_type, alias_value) WHERE is_active = TRUE;

-- ── MD-006/007/008: Charge code master ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.charge_code_master (
    charge_code_id      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    charge_code         TEXT    NOT NULL UNIQUE,
    charge_name         TEXT    NOT NULL,
    -- MD-007: Classification
    charge_category     TEXT    NOT NULL DEFAULT 'freight',
    -- freight | fuel | accessorial | tax | duty | adjustment
    -- | discount | fee | credit | surcharge
    applies_to          TEXT    NOT NULL DEFAULT 'both',
    -- carrier | client | both
    -- MD-008: GL mapping
    gl_account_code     TEXT,
    billing_category    TEXT,
    -- MD-008: Rules
    audit_rule_code     TEXT,
    allocation_rule     TEXT,
    tax_rule_code       TEXT,
    -- External mappings
    external_code_edi   TEXT,
    external_code_erp   TEXT,
    external_code_tms   TEXT,
    -- Status (MD-009)
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    effective_date      DATE    NOT NULL DEFAULT CURRENT_DATE,
    expiry_date         DATE,
    version_number      INTEGER NOT NULL DEFAULT 1,
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ccm_category CHECK (charge_category IN (
        'freight','fuel','accessorial','tax','duty',
        'adjustment','discount','fee','credit','surcharge'
    ))
);
CREATE INDEX IF NOT EXISTS idx_ccm_category ON tms.charge_code_master(charge_category, is_active);

-- ── MD-009: Master data audit/version history ──────────────────────
CREATE TABLE IF NOT EXISTS tms.master_data_audit (
    audit_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     TEXT    NOT NULL,
    -- location | item | charge_code | carrier | customer | supplier
    entity_id       UUID    NOT NULL,
    action          TEXT    NOT NULL,
    -- created | updated | approved | deactivated | version_bumped | bulk_import
    version_before  INTEGER,
    version_after   INTEGER,
    changed_fields  TEXT[],
    old_values      JSONB,
    new_values      JSONB,
    performed_by    TEXT,
    performed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_mda_entity   ON tms.master_data_audit(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_mda_date     ON tms.master_data_audit(performed_at DESC);

-- Triggers for updated_at
DO $$ BEGIN
    CREATE TRIGGER trg_item_master_updated_at
        BEFORE UPDATE ON tms.item_master
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_ccm_updated_at
        BEFORE UPDATE ON tms.charge_code_master
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- ── Seed charge codes (MD-007) ─────────────────────────────────────
INSERT INTO tms.charge_code_master
    (charge_code, charge_name, charge_category, applies_to, gl_account_code, billing_category)
VALUES
    ('LINEHAUL',    'Line Haul Freight',        'freight',     'both', '5010', 'Transportation'),
    ('FUEL_SUR',    'Fuel Surcharge',            'fuel',        'both', '5020', 'Fuel'),
    ('LIFTGATE',    'Liftgate Service',          'accessorial', 'both', '5030', 'Accessorial'),
    ('INSIDE_DEL',  'Inside Delivery',           'accessorial', 'both', '5030', 'Accessorial'),
    ('APPT',        'Appointment Fee',           'accessorial', 'both', '5030', 'Accessorial'),
    ('DETENTION',   'Detention',                 'accessorial', 'carrier', '5030', 'Accessorial'),
    ('REDELIVERY',  'Redelivery',                'accessorial', 'both', '5030', 'Accessorial'),
    ('HAZMAT',      'Hazardous Materials',       'surcharge',   'both', '5040', 'Surcharge'),
    ('OVERSIZE',    'Oversize/Overweight',       'surcharge',   'both', '5040', 'Surcharge'),
    ('RESIDENTIAL', 'Residential Delivery',      'accessorial', 'both', '5030', 'Accessorial'),
    ('STORAGE',     'Storage Charge',            'fee',         'both', '5050', 'Other Fees'),
    ('CUSTOMS_FEE', 'Customs Clearance Fee',     'duty',        'both', '5060', 'Customs'),
    ('TAX_GST',     'GST/HST Tax',               'tax',         'client','5070', 'Tax'),
    ('DISCOUNT',    'Volume Discount',           'discount',    'client','5080', 'Discount'),
    ('CREDIT_NOTE', 'Credit Note',               'credit',      'client','5090', 'Credit'),
    ('ADJ_MANUAL',  'Manual Adjustment',         'adjustment',  'both', '5100', 'Adjustment'),
    ('MGMT_FEE',    'Management Fee',            'fee',         'client','5110', 'Management'),
    ('LUMPER',      'Lumper/Unloading',          'accessorial', 'carrier','5030','Accessorial'),
    ('TOLLS',       'Toll Charges',              'fee',         'carrier','5120','Other Fees'),
    ('TEMP_CTRL',   'Temperature Control',       'surcharge',   'both', '5040', 'Surcharge')
ON CONFLICT (charge_code) DO NOTHING;
