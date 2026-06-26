-- ============================================================
-- Migration: 017_document_management_v2.sql
-- TMS-DOC-001 through TMS-DOC-010
-- Uses existing enterprise schema tables where possible
-- ============================================================

BEGIN;

-- ── DOC-002: Document Types table ─────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_types (
    document_type_id    UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    type_code           TEXT    NOT NULL UNIQUE,
    type_name           TEXT    NOT NULL,
    category            TEXT    NOT NULL DEFAULT 'transport',
    description         TEXT,
    requires_signature  BOOLEAN NOT NULL DEFAULT FALSE,
    is_transmittable    BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Extend existing documents table ───────────────────────────────
ALTER TABLE tms.documents
    ADD COLUMN IF NOT EXISTS template_id         UUID,
    ADD COLUMN IF NOT EXISTS document_format     TEXT NOT NULL DEFAULT 'pdf',
    ADD COLUMN IF NOT EXISTS file_size_bytes     BIGINT,
    ADD COLUMN IF NOT EXISTS content_text        TEXT,
    ADD COLUMN IF NOT EXISTS content_data        BYTEA,
    ADD COLUMN IF NOT EXISTS status              TEXT NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS generated_by        TEXT NOT NULL DEFAULT 'system',
    ADD COLUMN IF NOT EXISTS upload_source       TEXT,
    ADD COLUMN IF NOT EXISTS is_current_version  BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS parent_document_id  UUID,
    ADD COLUMN IF NOT EXISTS transmitted_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS transmitted_to      TEXT,
    ADD COLUMN IF NOT EXISTS transmission_method TEXT,
    ADD COLUMN IF NOT EXISTS expires_at          DATE,
    ADD COLUMN IF NOT EXISTS retain_until        DATE,
    ADD COLUMN IF NOT EXISTS ocr_status          TEXT NOT NULL DEFAULT 'not_requested',
    ADD COLUMN IF NOT EXISTS ocr_extracted_data  JSONB,
    ADD COLUMN IF NOT EXISTS created_by          TEXT;

DO $$ BEGIN
    ALTER TABLE tms.documents
        ADD CONSTRAINT chk_doc_status CHECK (status IN (
            'draft','generated','sent','delivered','signed','archived','voided'
        ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE tms.documents
        ADD CONSTRAINT chk_doc_ocr CHECK (ocr_status IN (
            'not_requested','pending','completed','failed'
        ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_doc_type    ON tms.documents(document_type_id);
CREATE INDEX IF NOT EXISTS idx_doc_status  ON tms.documents(status) WHERE status != 'voided';
CREATE INDEX IF NOT EXISTS idx_doc_current ON tms.documents(is_current_version) WHERE is_current_version = TRUE;

-- ── DOC-003: Custom templates table (avoid conflict with existing) ─
CREATE TABLE IF NOT EXISTS tms.doc_templates (
    doc_template_id     UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type_id    UUID    NOT NULL REFERENCES tms.document_types(document_type_id),
    template_name       TEXT    NOT NULL,
    template_format     TEXT    NOT NULL DEFAULT 'pdf',
    template_body       TEXT,
    customer_party_id   UUID    REFERENCES tms.parties(party_id),
    carrier_id          UUID    REFERENCES tms.carriers(carrier_id),
    country_code        TEXT,
    transport_mode      TEXT,
    is_default          BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    version             INTEGER NOT NULL DEFAULT 1,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dct_type     ON tms.doc_templates(document_type_id, is_active);
CREATE INDEX IF NOT EXISTS idx_dct_customer ON tms.doc_templates(customer_party_id) WHERE customer_party_id IS NOT NULL;

-- ── DOC-006: Required document rules ──────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_required_rules (
    rule_id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name           TEXT    NOT NULL,
    document_type_id    UUID    NOT NULL REFERENCES tms.document_types(document_type_id),
    trigger_event       TEXT    NOT NULL,
    entity_type         TEXT    NOT NULL DEFAULT 'shipment',
    transport_mode      TEXT,
    country_code        TEXT,
    customer_party_id   UUID    REFERENCES tms.parties(party_id),
    is_blocking         BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_drr_event CHECK (trigger_event IN (
        'shipment_completion','billing','invoice_approval',
        'payment_release','customs_clearance','closure','tender_acceptance'
    ))
);

CREATE INDEX IF NOT EXISTS idx_drr_event ON tms.document_required_rules(trigger_event, is_active);

-- ── DOC-009: Document access rules ────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_access_rules (
    access_rule_id      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type_id    UUID    REFERENCES tms.document_types(document_type_id),
    party_type          TEXT,
    role_code           TEXT,
    business_unit_id    UUID    REFERENCES tms.business_units(business_unit_id),
    can_view            BOOLEAN NOT NULL DEFAULT TRUE,
    can_download        BOOLEAN NOT NULL DEFAULT TRUE,
    can_upload          BOOLEAN NOT NULL DEFAULT FALSE,
    can_delete          BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger for doc_templates
DO $$ BEGIN
    CREATE TRIGGER trg_doc_templates_updated_at
        BEFORE UPDATE ON tms.doc_templates
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- ── Seed document types ────────────────────────────────────────────
INSERT INTO tms.document_types
    (type_code, type_name, category, description, requires_signature, is_transmittable)
VALUES
    ('BOL',          'Bill of Lading',           'transport',   'Standard Bill of Lading',              TRUE,  TRUE),
    ('MBOL',         'Master Bill of Lading',     'transport',   'Master/Ocean Bill of Lading',          TRUE,  TRUE),
    ('PACKING_LIST', 'Packing List',              'transport',   'Itemized list of contents',            FALSE, TRUE),
    ('SHIP_LABEL',   'Shipping Label',            'transport',   'Carrier shipping label',               FALSE, TRUE),
    ('CARRIER_CONF', 'Carrier Confirmation',      'carrier',     'Carrier booking confirmation',         FALSE, TRUE),
    ('DELIVERY_NOTE','Delivery Note',             'transport',   'Delivery advice document',             FALSE, TRUE),
    ('POD',          'Proof of Delivery',         'proof',       'Signed proof of delivery',             TRUE,  TRUE),
    ('POP',          'Proof of Pickup',           'proof',       'Proof of pickup/collection',           TRUE,  TRUE),
    ('COMM_INVOICE', 'Commercial Invoice',        'financial',   'Commercial invoice for goods',         FALSE, TRUE),
    ('CUSTOMS_DECL', 'Customs Declaration',       'customs',     'Customs entry/clearance declaration',  FALSE, TRUE),
    ('CERT_ORIGIN',  'Certificate of Origin',     'customs',     'Certificate of country of origin',     TRUE,  TRUE),
    ('MANIFEST',     'Shipment Manifest',         'transport',   'Carrier manifest/load list',           FALSE, TRUE),
    ('SHIP_INSTR',   'Shipping Instructions',     'transport',   'Shipper instructions to carrier',      FALSE, TRUE),
    ('HAZMAT_DECL',  'Hazmat Declaration',        'compliance',  'Dangerous goods declaration',          TRUE,  TRUE),
    ('TEMP_RECORD',  'Temperature Record',        'compliance',  'Cold chain temperature record',        FALSE, TRUE),
    ('CARR_INVOICE', 'Carrier Invoice',           'financial',   'Carrier freight invoice',              FALSE, TRUE),
    ('CLIENT_BILL',  'Client Bill',               'financial',   'Client billing document',              FALSE, TRUE),
    ('WEIGHT_CERT',  'Weight Certificate',        'compliance',  'Certified weight/scale ticket',        TRUE,  FALSE),
    ('LUMPER_RCPT',  'Lumper Receipt',            'financial',   'Third-party unloading receipt',        TRUE,  FALSE),
    ('INSPECTION',   'Inspection Report',         'compliance',  'Cargo inspection report',              FALSE, FALSE)
ON CONFLICT (type_code) DO NOTHING;

-- Seed required document rules
DO $$
DECLARE v_bol_id UUID; v_pod_id UUID; v_inv_id UUID; v_cus_id UUID;
BEGIN
    SELECT document_type_id INTO v_bol_id FROM tms.document_types WHERE type_code='BOL';
    SELECT document_type_id INTO v_pod_id FROM tms.document_types WHERE type_code='POD';
    SELECT document_type_id INTO v_inv_id FROM tms.document_types WHERE type_code='CARR_INVOICE';
    SELECT document_type_id INTO v_cus_id FROM tms.document_types WHERE type_code='CUSTOMS_DECL';

    IF v_bol_id IS NOT NULL THEN
        INSERT INTO tms.document_required_rules
            (rule_name, document_type_id, trigger_event, entity_type, is_blocking)
        VALUES
            ('Require BOL before completion', v_bol_id, 'shipment_completion', 'shipment', TRUE),
            ('Require POD before billing',    v_pod_id, 'billing',             'shipment', TRUE),
            ('Require Invoice before payment',v_inv_id, 'payment_release',     'shipment', TRUE),
            ('Require Customs for clearance', v_cus_id, 'customs_clearance',   'shipment', TRUE)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
