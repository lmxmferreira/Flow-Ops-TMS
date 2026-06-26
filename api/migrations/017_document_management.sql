-- ============================================================
-- Migration: 017_document_management.sql
-- TMS-DOC-001 through TMS-DOC-010: Full Document Management
-- ============================================================

BEGIN;

-- ── DOC-002: Document Types ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_types (
    document_type_id    UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    type_code           TEXT    NOT NULL UNIQUE,
    type_name           TEXT    NOT NULL,
    category            TEXT    NOT NULL DEFAULT 'transport',
    -- transport | customs | financial | compliance | carrier | proof
    description         TEXT,
    requires_signature  BOOLEAN NOT NULL DEFAULT FALSE,
    is_transmittable    BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── DOC-003: Document Templates ───────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_templates (
    template_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type_id    UUID    NOT NULL REFERENCES tms.document_types(document_type_id),
    template_name       TEXT    NOT NULL,
    template_format     TEXT    NOT NULL DEFAULT 'pdf',
    -- pdf | html | docx | zpl | png
    template_body       TEXT,   -- Jinja2/handlebars template
    -- Scoping (NULL = applies to all)
    customer_party_id   UUID    REFERENCES tms.parties(party_id),
    carrier_id          UUID    REFERENCES tms.carriers(carrier_id),
    supplier_party_id   UUID    REFERENCES tms.parties(party_id),
    business_unit_id    UUID    REFERENCES tms.business_units(business_unit_id),
    country_code        TEXT,
    transport_mode      TEXT,
    shipment_type       TEXT,
    is_default          BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    version             INTEGER NOT NULL DEFAULT 1,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dt_type     ON tms.document_templates(document_type_id, is_active);
CREATE INDEX IF NOT EXISTS idx_dt_customer ON tms.document_templates(customer_party_id) WHERE customer_party_id IS NOT NULL;

-- ── DOC-001/008: Documents (master store + versioning) ─────────────
CREATE TABLE IF NOT EXISTS tms.documents (
    document_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type_id    UUID    NOT NULL REFERENCES tms.document_types(document_type_id),
    template_id         UUID    REFERENCES tms.document_templates(template_id),
    document_number     TEXT    NOT NULL,
    document_name       TEXT    NOT NULL,
    document_format     TEXT    NOT NULL DEFAULT 'pdf',
    -- pdf | html | docx | zpl | png | csv | xml | edi
    -- Storage
    file_path           TEXT,   -- path/URL to stored file
    file_size_bytes     BIGINT,
    file_hash           TEXT,   -- SHA256 for integrity
    -- Content (for generated docs stored inline)
    content_text        TEXT,
    content_data        BYTEA,
    -- Version control (DOC-008)
    version_number      INTEGER NOT NULL DEFAULT 1,
    parent_document_id  UUID    REFERENCES tms.documents(document_id),
    is_current_version  BOOLEAN NOT NULL DEFAULT TRUE,
    -- Status
    status              TEXT    NOT NULL DEFAULT 'draft',
    -- draft | generated | sent | delivered | signed | archived | voided
    -- Source
    generated_by        TEXT    NOT NULL DEFAULT 'system',
    -- system | user | carrier | customer | supplier | edi | api | email
    upload_source       TEXT,
    -- Transmission
    transmitted_at      TIMESTAMPTZ,
    transmitted_to      TEXT,
    transmission_method TEXT,   -- email | edi | api | portal | print | fax
    -- Expiry / retention
    expires_at          DATE,
    retain_until        DATE,
    -- OCR (DOC-010)
    ocr_status          TEXT    DEFAULT 'not_requested',
    -- not_requested | pending | completed | failed
    ocr_extracted_data  JSONB,
    -- Audit
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_doc_status CHECK (status IN (
        'draft','generated','sent','delivered','signed','archived','voided'
    )),
    CONSTRAINT chk_doc_ocr CHECK (ocr_status IN (
        'not_requested','pending','completed','failed'
    ))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_number   ON tms.documents(document_number);
CREATE INDEX IF NOT EXISTS idx_doc_type            ON tms.documents(document_type_id, status);
CREATE INDEX IF NOT EXISTS idx_doc_parent          ON tms.documents(parent_document_id) WHERE parent_document_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_doc_current         ON tms.documents(document_type_id, is_current_version) WHERE is_current_version = TRUE;

-- ── DOC-005: Document Associations ────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_associations (
    association_id      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID    NOT NULL REFERENCES tms.documents(document_id) ON DELETE CASCADE,
    entity_type         TEXT    NOT NULL,
    -- shipment | stop | po_header | po_line | order_release
    -- | carrier_invoice | client_bill | claim | dispute | payment
    entity_id           UUID    NOT NULL,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_da_entity_type CHECK (entity_type IN (
        'shipment','stop','po_header','po_line','order_release',
        'carrier_invoice','client_bill','claim','dispute','payment'
    ))
);

CREATE INDEX IF NOT EXISTS idx_da_document ON tms.document_associations(document_id);
CREATE INDEX IF NOT EXISTS idx_da_entity   ON tms.document_associations(entity_type, entity_id);

-- ── DOC-006: Required Document Rules ──────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_required_rules (
    rule_id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name           TEXT    NOT NULL,
    document_type_id    UUID    NOT NULL REFERENCES tms.document_types(document_type_id),
    trigger_event       TEXT    NOT NULL,
    -- shipment_completion | billing | invoice_approval
    -- | payment_release | customs_clearance | closure
    entity_type         TEXT    NOT NULL DEFAULT 'shipment',
    -- Scoping
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

-- ── DOC-009: Document Access Rules ────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.document_access_rules (
    access_rule_id      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type_id    UUID    REFERENCES tms.document_types(document_type_id),
    -- NULL = applies to all doc types
    party_type          TEXT,   -- customer | carrier | supplier | internal
    role_code           TEXT,   -- specific role
    business_unit_id    UUID    REFERENCES tms.business_units(business_unit_id),
    can_view            BOOLEAN NOT NULL DEFAULT TRUE,
    can_download        BOOLEAN NOT NULL DEFAULT TRUE,
    can_upload          BOOLEAN NOT NULL DEFAULT FALSE,
    can_delete          BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Triggers
DO $$ BEGIN
    CREATE TRIGGER trg_doc_templates_updated_at
        BEFORE UPDATE ON tms.document_templates
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_documents_updated_at
        BEFORE UPDATE ON tms.documents
        FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- ── Seed document types (DOC-002) ─────────────────────────────────
INSERT INTO tms.document_types
    (type_code, type_name, category, description, requires_signature, is_transmittable)
VALUES
    ('BOL',           'Bill of Lading',              'transport',   'Standard Bill of Lading',                          TRUE,  TRUE),
    ('MBOL',          'Master Bill of Lading',        'transport',   'Master/Ocean Bill of Lading',                      TRUE,  TRUE),
    ('PACKING_LIST',  'Packing List',                 'transport',   'Itemized list of shipment contents',               FALSE, TRUE),
    ('SHIP_LABEL',    'Shipping Label',               'transport',   'Carrier shipping label/barcode',                   FALSE, TRUE),
    ('CARRIER_CONF',  'Carrier Confirmation',         'carrier',     'Carrier booking/tender confirmation',               FALSE, TRUE),
    ('DELIVERY_NOTE', 'Delivery Note',                'transport',   'Delivery advice document',                         FALSE, TRUE),
    ('POD',           'Proof of Delivery',            'proof',       'Signed proof of delivery',                         TRUE,  TRUE),
    ('POP',           'Proof of Pickup',              'proof',       'Proof of pickup/collection',                       TRUE,  TRUE),
    ('COMM_INVOICE',  'Commercial Invoice',           'financial',   'Commercial invoice for goods',                     FALSE, TRUE),
    ('CUSTOMS_DECL',  'Customs Declaration',          'customs',     'Customs entry/clearance declaration',              FALSE, TRUE),
    ('CERT_ORIGIN',   'Certificate of Origin',        'customs',     'Certificate of country of origin',                 TRUE,  TRUE),
    ('MANIFEST',      'Shipment Manifest',            'transport',   'Carrier manifest / load list',                     FALSE, TRUE),
    ('SHIP_INSTR',    'Shipping Instructions',        'transport',   'Shipper instructions to carrier',                  FALSE, TRUE),
    ('HAZMAT_DECL',   'Hazmat Declaration',           'compliance',  'Dangerous goods declaration',                      TRUE,  TRUE),
    ('TEMP_RECORD',   'Temperature Record',           'compliance',  'Cold chain temperature monitoring record',          FALSE, TRUE),
    ('CARR_INVOICE',  'Carrier Invoice',              'financial',   'Carrier freight invoice',                          FALSE, TRUE),
    ('CLIENT_BILL',   'Client Bill',                  'financial',   'Client billing document',                          FALSE, TRUE),
    ('WEIGHT_CERT',   'Weight Certificate',           'compliance',  'Certified weight/scale ticket',                    TRUE,  FALSE),
    ('LUMPER_RCPT',   'Lumper Receipt',               'financial',   'Third-party unloading receipt',                    TRUE,  FALSE),
    ('INSPECTION',    'Inspection Report',            'compliance',  'Cargo inspection report',                          FALSE, FALSE)
ON CONFLICT (type_code) DO NOTHING;

-- Seed required document rules
DO $$
BEGIN
    INSERT INTO tms.document_required_rules
        (rule_name, document_type_id, trigger_event, entity_type, is_blocking, is_active)
    SELECT
        'Require BOL before shipment completion',
        document_type_id, 'shipment_completion', 'shipment', TRUE, TRUE
    FROM tms.document_types WHERE type_code = 'BOL'
    ON CONFLICT DO NOTHING;

    INSERT INTO tms.document_required_rules
        (rule_name, document_type_id, trigger_event, entity_type, is_blocking, is_active)
    SELECT
        'Require POD before billing',
        document_type_id, 'billing', 'shipment', TRUE, TRUE
    FROM tms.document_types WHERE type_code = 'POD'
    ON CONFLICT DO NOTHING;

    INSERT INTO tms.document_required_rules
        (rule_name, document_type_id, trigger_event, entity_type, is_blocking, is_active)
    SELECT
        'Require Carrier Invoice before payment',
        document_type_id, 'payment_release', 'shipment', TRUE, TRUE
    FROM tms.document_types WHERE type_code = 'CARR_INVOICE'
    ON CONFLICT DO NOTHING;

    INSERT INTO tms.document_required_rules
        (rule_name, document_type_id, trigger_event, entity_type, is_blocking, is_active)
    SELECT
        'Require Customs Declaration for clearance',
        document_type_id, 'customs_clearance', 'shipment', TRUE, TRUE
    FROM tms.document_types WHERE type_code = 'CUSTOMS_DECL'
    ON CONFLICT DO NOTHING;
END $$;
