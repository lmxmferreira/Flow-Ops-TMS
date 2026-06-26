-- ============================================================
-- Migration: 003_validation_rules.sql
-- TMS-CORE-007: Configurable validation rules, mandatory fields,
--               default values, and business rules by transaction type
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- Rule sets: named groupings (e.g. "PO Standard", "Shipment Hazmat")
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.validation_rule_sets (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    transaction_type    VARCHAR(50)  NOT NULL,   -- purchase_order | order_release | shipment
    description         TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rule_set_name_type UNIQUE (name, transaction_type)
);

-- ------------------------------------------------------------
-- Validation rules
-- rule_type:
--   required       – field must be non-null / non-empty
--   default_value  – field gets a default if not supplied
--   allowed_values – field must be one of a list
--   min_value      – numeric / date lower bound
--   max_value      – numeric / date upper bound
--   regex          – field must match pattern
--   custom         – arbitrary SQL expression or Python callable name
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tms.validation_rules (
    id                  SERIAL PRIMARY KEY,
    rule_set_id         INTEGER REFERENCES tms.validation_rule_sets(id) ON DELETE CASCADE,
    transaction_type    VARCHAR(50)  NOT NULL,
    field_name          VARCHAR(100) NOT NULL,
    rule_type           VARCHAR(50)  NOT NULL,
    parameters          JSONB        NOT NULL DEFAULT '{}',
    -- for default_value:   {"value": "draft"}
    -- for allowed_values:  {"values": ["draft","active","closed"]}
    -- for min_value:       {"value": 0}
    -- for regex:           {"pattern": "^PO-\\d{6}$"}
    -- for custom:          {"expression": "quantity > 0 AND quantity <= 999999"}
    error_message       TEXT         NOT NULL,
    severity            VARCHAR(20)  NOT NULL DEFAULT 'error',  -- error | warning
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    sort_order          INTEGER      NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_rule_type CHECK (rule_type IN (
        'required','default_value','allowed_values','min_value','max_value','regex','custom'
    )),
    CONSTRAINT chk_severity CHECK (severity IN ('error','warning')),
    CONSTRAINT chk_transaction_type CHECK (transaction_type IN (
        'purchase_order','order_release','shipment'
    ))
);

CREATE INDEX IF NOT EXISTS idx_validation_rules_tx_type
    ON tms.validation_rules(transaction_type, is_active);

CREATE INDEX IF NOT EXISTS idx_validation_rules_rule_set
    ON tms.validation_rules(rule_set_id);

-- updated_at trigger (reuse pattern from existing tables)
CREATE OR REPLACE FUNCTION tms.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_validation_rule_sets_updated_at'
    ) THEN
        CREATE TRIGGER trg_validation_rule_sets_updated_at
        BEFORE UPDATE ON tms.validation_rule_sets
        FOR EACH ROW EXECUTE FUNCTION tms.set_updated_at();
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_validation_rules_updated_at'
    ) THEN
        CREATE TRIGGER trg_validation_rules_updated_at
        BEFORE UPDATE ON tms.validation_rules
        FOR EACH ROW EXECUTE FUNCTION tms.set_updated_at();
    END IF;
END $$;

-- ============================================================
-- SEED DATA
-- ============================================================

-- Rule Sets
INSERT INTO tms.validation_rule_sets (name, transaction_type, description) VALUES
    ('PO Standard',            'purchase_order', 'Standard validation rules for all purchase orders'),
    ('Order Release Standard', 'order_release',  'Standard validation rules for order releases'),
    ('Shipment Standard',      'shipment',        'Standard validation rules for shipments')
ON CONFLICT (name, transaction_type) DO NOTHING;

-- ============================================================
-- PURCHASE ORDER rules
-- ============================================================
WITH rs AS (SELECT id FROM tms.validation_rule_sets WHERE name = 'PO Standard')
INSERT INTO tms.validation_rules
    (rule_set_id, transaction_type, field_name, rule_type, parameters, error_message, severity, sort_order)
SELECT rs.id, 'purchase_order', field_name, rule_type, parameters::jsonb, error_message, severity, sort_order
FROM rs, (VALUES
    ('po_number',        'required',       '{}',                                            'PO Number is required.',                              'error',   10),
    ('supplier_id',      'required',       '{}',                                            'Supplier is required.',                               'error',   20),
    ('origin_id',        'required',       '{}',                                            'Origin location is required.',                        'error',   30),
    ('destination_id',   'required',       '{}',                                            'Destination location is required.',                   'error',   40),
    ('incoterms',        'required',       '{}',                                            'Incoterms are required.',                             'error',   50),
    ('currency',         'required',       '{}',                                            'Currency is required.',                               'error',   60),
    ('currency',         'allowed_values', '{"values":["USD","CAD","EUR","GBP","MXN"]}',    'Currency must be a supported currency code.',         'error',   70),
    ('requested_ship_date', 'required',    '{}',                                            'Requested ship date is required.',                    'error',   80),
    ('status',           'default_value',  '{"value":"draft"}',                             'Status defaults to draft.',                          'warning', 90),
    ('status',           'allowed_values', '{"values":["draft","received","validated","on_hold","partially_released","fully_released","shipped","partially_received","closed","canceled","exception"]}',
                                                                                             'Invalid PO status.',                                 'error',  100),
    ('po_type',          'allowed_values', '{"values":["standard","blanket","transfer","drop_ship","supplier_direct","return","customer_linked"]}',
                                                                                             'Invalid PO type.',                                   'error',  110),
    ('po_number',        'regex',          '{"pattern":"^[A-Za-z0-9\\\\-_]{3,50}$"}',       'PO Number must be 3–50 alphanumeric characters.',    'error',  120)
) AS v(field_name, rule_type, parameters, error_message, severity, sort_order)
ON CONFLICT DO NOTHING;

-- ============================================================
-- ORDER RELEASE rules
-- ============================================================
WITH rs AS (SELECT id FROM tms.validation_rule_sets WHERE name = 'Order Release Standard')
INSERT INTO tms.validation_rules
    (rule_set_id, transaction_type, field_name, rule_type, parameters, error_message, severity, sort_order)
SELECT rs.id, 'order_release', field_name, rule_type, parameters::jsonb, error_message, severity, sort_order
FROM rs, (VALUES
    ('release_number',       'required',       '{}',                                       'Release Number is required.',                         'error',   10),
    ('shipper_id',           'required',       '{}',                                       'Shipper is required.',                                'error',   20),
    ('consignee_id',         'required',       '{}',                                       'Consignee is required.',                              'error',   30),
    ('origin_id',            'required',       '{}',                                       'Origin location is required.',                        'error',   40),
    ('destination_id',       'required',       '{}',                                       'Destination location is required.',                   'error',   50),
    ('requested_ship_date',  'required',       '{}',                                       'Requested ship date is required.',                    'error',   60),
    ('requested_delivery_date','required',     '{}',                                       'Requested delivery date is required.',                'error',   70),
    ('mode',                 'required',       '{}',                                       'Transportation mode is required.',                    'error',   80),
    ('mode',                 'allowed_values', '{"values":["FTL","LTL","Parcel","Rail","Ocean","Air","Intermodal"]}',
                                                                                            'Invalid transportation mode.',                       'error',   90),
    ('service_level',        'required',       '{}',                                       'Service level is required.',                          'error',  100),
    ('status',               'default_value',  '{"value":"draft"}',                        'Status defaults to draft.',                          'warning', 110),
    ('status',               'allowed_values', '{"values":["draft","ready_to_plan","planned","tendered","accepted","picked_up","in_transit","delivered","completed","canceled","closed"]}',
                                                                                            'Invalid order release status.',                      'error',  120),
    ('freight_terms',        'allowed_values', '{"values":["Prepaid","Collect","Third Party","Prepaid & Add"]}',
                                                                                            'Invalid freight terms.',                             'error',  130)
) AS v(field_name, rule_type, parameters, error_message, severity, sort_order)
ON CONFLICT DO NOTHING;

-- ============================================================
-- SHIPMENT rules
-- ============================================================
WITH rs AS (SELECT id FROM tms.validation_rule_sets WHERE name = 'Shipment Standard')
INSERT INTO tms.validation_rules
    (rule_set_id, transaction_type, field_name, rule_type, parameters, error_message, severity, sort_order)
SELECT rs.id, 'shipment', field_name, rule_type, parameters::jsonb, error_message, severity, sort_order
FROM rs, (VALUES
    ('shipment_number',      'required',       '{}',                                       'Shipment Number is required.',                        'error',   10),
    ('carrier_id',           'required',       '{}',                                       'Carrier is required.',                                'error',   20),
    ('origin_id',            'required',       '{}',                                       'Origin location is required.',                        'error',   30),
    ('destination_id',       'required',       '{}',                                       'Destination location is required.',                   'error',   40),
    ('planned_ship_date',    'required',       '{}',                                       'Planned ship date is required.',                      'error',   50),
    ('planned_delivery_date','required',       '{}',                                       'Planned delivery date is required.',                  'error',   60),
    ('mode',                 'required',       '{}',                                       'Transportation mode is required.',                    'error',   70),
    ('mode',                 'allowed_values', '{"values":["FTL","LTL","Parcel","Rail","Ocean","Air","Intermodal"]}',
                                                                                            'Invalid transportation mode.',                       'error',   80),
    ('equipment_type',       'required',       '{}',                                       'Equipment type is required.',                         'warning', 90),
    ('status',               'default_value',  '{"value":"draft"}',                        'Status defaults to draft.',                          'warning', 100),
    ('status',               'allowed_values', '{"values":["draft","planned","tendered","confirmed","in_transit","delivered","completed","canceled","exception"]}',
                                                                                            'Invalid shipment status.',                           'error',  110),
    ('total_weight',         'min_value',      '{"value":0}',                              'Total weight must be greater than or equal to 0.',   'error',  120),
    ('total_pieces',         'min_value',      '{"value":1}',                              'Total pieces must be at least 1.',                   'error',  130)
) AS v(field_name, rule_type, parameters, error_message, severity, sort_order)
ON CONFLICT DO NOTHING;

COMMIT;
