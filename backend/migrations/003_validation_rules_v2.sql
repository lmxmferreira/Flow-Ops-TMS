-- ============================================================
-- Migration: 003_validation_rules_v2.sql
-- Adapts existing tms.validation_rules table and creates
-- tms.validation_rule_sets for TMS-CORE-007
-- ============================================================

BEGIN;

-- ------------------------------------------------------------------ --
-- 1. Create validation_rule_sets (new table)
-- ------------------------------------------------------------------ --
CREATE TABLE tms.validation_rule_sets (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    transaction_type    VARCHAR(50)  NOT NULL,
    description         TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rule_set_name_type UNIQUE (name, transaction_type)
);

-- ------------------------------------------------------------------ --
-- 2. Alter existing tms.validation_rules to add missing columns
-- ------------------------------------------------------------------ --

-- transaction_type maps to applies_to_entity but typed/constrained
ALTER TABLE tms.validation_rules
    ADD COLUMN IF NOT EXISTS transaction_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS rule_type        VARCHAR(50),
    ADD COLUMN IF NOT EXISTS parameters       JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS rule_set_id      INTEGER REFERENCES tms.validation_rule_sets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS sort_order       INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_active        BOOLEAN NOT NULL DEFAULT TRUE;

-- Backfill transaction_type from applies_to_entity
UPDATE tms.validation_rules
SET transaction_type = CASE applies_to_entity
    WHEN 'purchase_order'  THEN 'purchase_order'
    WHEN 'order_release'   THEN 'order_release'
    WHEN 'shipment'        THEN 'shipment'
    ELSE applies_to_entity
END
WHERE transaction_type IS NULL;

-- Backfill rule_type from existing data (default to custom since
-- existing rows use validation_expression)
UPDATE tms.validation_rules
SET rule_type = 'custom'
WHERE rule_type IS NULL;

-- Backfill is_active from status column
UPDATE tms.validation_rules
SET is_active = (status = 'active')
WHERE is_active IS NULL;

-- Now add constraints
ALTER TABLE tms.validation_rules
    ALTER COLUMN transaction_type SET NOT NULL,
    ALTER COLUMN rule_type SET NOT NULL;

ALTER TABLE tms.validation_rules
    ADD CONSTRAINT chk_vr_rule_type CHECK (rule_type IN (
        'required','default_value','allowed_values','min_value','max_value','regex','custom'
    )),
    ADD CONSTRAINT chk_vr_transaction_type CHECK (transaction_type IN (
        'purchase_order','order_release','shipment'
    ));

CREATE INDEX IF NOT EXISTS idx_vr_tx_type_active
    ON tms.validation_rules(transaction_type, is_active);

CREATE INDEX IF NOT EXISTS idx_vr_rule_set
    ON tms.validation_rules(rule_set_id);

-- updated_at trigger for rule_sets
CREATE OR REPLACE FUNCTION tms.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validation_rule_sets_updated_at
BEFORE UPDATE ON tms.validation_rule_sets
FOR EACH ROW EXECUTE FUNCTION tms.set_updated_at();

-- ------------------------------------------------------------------ --
-- 3. Seed rule sets
-- ------------------------------------------------------------------ --
INSERT INTO tms.validation_rule_sets (name, transaction_type, description) VALUES
    ('PO Standard',            'purchase_order', 'Standard validation rules for all purchase orders'),
    ('Order Release Standard', 'order_release',  'Standard validation rules for order releases'),
    ('Shipment Standard',      'shipment',        'Standard validation rules for shipments')
ON CONFLICT (name, transaction_type) DO NOTHING;

-- ------------------------------------------------------------------ --
-- 4. Seed validation rules (purchase_order)
-- ------------------------------------------------------------------ --
WITH rs AS (SELECT id FROM tms.validation_rule_sets WHERE name = 'PO Standard')
INSERT INTO tms.validation_rules
    (rule_code, applies_to_entity, transaction_type, field_name, rule_type, parameters, error_message, severity, sort_order, rule_set_id, status)
SELECT
    'PO-' || field_name || '-' || rule_type,
    'purchase_order',
    'purchase_order',
    field_name, rule_type, parameters::jsonb, error_message, severity, sort_order,
    rs.id,
    'active'
FROM rs, (VALUES
    ('po_number',        'required',       '{}',                                                    'PO Number is required.',                           'error',   10),
    ('supplier_id',      'required',       '{}',                                                    'Supplier is required.',                            'error',   20),
    ('origin_id',        'required',       '{}',                                                    'Origin location is required.',                     'error',   30),
    ('destination_id',   'required',       '{}',                                                    'Destination location is required.',                'error',   40),
    ('incoterms',        'required',       '{}',                                                    'Incoterms are required.',                          'error',   50),
    ('currency',         'required',       '{}',                                                    'Currency is required.',                            'error',   60),
    ('currency',         'allowed_values', '{"values":["USD","CAD","EUR","GBP","MXN"]}',            'Currency must be a supported currency code.',      'error',   70),
    ('requested_ship_date', 'required',    '{}',                                                    'Requested ship date is required.',                 'error',   80),
    ('status',           'default_value',  '{"value":"draft"}',                                     'Status defaults to draft.',                       'warning', 90),
    ('status',           'allowed_values', '{"values":["draft","received","validated","on_hold","partially_released","fully_released","shipped","partially_received","closed","canceled","exception"]}', 'Invalid PO status.', 'error', 100),
    ('po_type',          'allowed_values', '{"values":["standard","blanket","transfer","drop_ship","supplier_direct","return","customer_linked"]}',     'Invalid PO type.',                            'error',  110),
    ('po_number',        'regex',          '{"pattern":"^[A-Za-z0-9\\-_]{3,50}$"}',                'PO Number must be 3–50 alphanumeric characters.', 'error',  120)
) AS v(field_name, rule_type, parameters, error_message, severity, sort_order)
ON CONFLICT (rule_code) DO NOTHING;

-- ------------------------------------------------------------------ --
-- 5. Seed validation rules (order_release)
-- ------------------------------------------------------------------ --
WITH rs AS (SELECT id FROM tms.validation_rule_sets WHERE name = 'Order Release Standard')
INSERT INTO tms.validation_rules
    (rule_code, applies_to_entity, transaction_type, field_name, rule_type, parameters, error_message, severity, sort_order, rule_set_id, status)
SELECT
    'REL-' || field_name || '-' || rule_type,
    'order_release',
    'order_release',
    field_name, rule_type, parameters::jsonb, error_message, severity, sort_order,
    rs.id,
    'active'
FROM rs, (VALUES
    ('release_number',         'required',       '{}',                                                   'Release Number is required.',              'error',   10),
    ('shipper_id',             'required',       '{}',                                                   'Shipper is required.',                     'error',   20),
    ('consignee_id',           'required',       '{}',                                                   'Consignee is required.',                   'error',   30),
    ('origin_id',              'required',       '{}',                                                   'Origin location is required.',             'error',   40),
    ('destination_id',         'required',       '{}',                                                   'Destination location is required.',        'error',   50),
    ('requested_ship_date',    'required',       '{}',                                                   'Requested ship date is required.',         'error',   60),
    ('requested_delivery_date','required',       '{}',                                                   'Requested delivery date is required.',     'error',   70),
    ('mode',                   'required',       '{}',                                                   'Transportation mode is required.',         'error',   80),
    ('mode',                   'allowed_values', '{"values":["FTL","LTL","Parcel","Rail","Ocean","Air","Intermodal"]}', 'Invalid transportation mode.', 'error', 90),
    ('service_level',          'required',       '{}',                                                   'Service level is required.',               'error',  100),
    ('status',                 'default_value',  '{"value":"draft"}',                                    'Status defaults to draft.',               'warning', 110),
    ('status',                 'allowed_values', '{"values":["draft","ready_to_plan","planned","tendered","accepted","picked_up","in_transit","delivered","completed","canceled","closed"]}', 'Invalid order release status.', 'error', 120),
    ('freight_terms',          'allowed_values', '{"values":["Prepaid","Collect","Third Party","Prepaid & Add"]}', 'Invalid freight terms.',          'error',  130)
) AS v(field_name, rule_type, parameters, error_message, severity, sort_order)
ON CONFLICT (rule_code) DO NOTHING;

-- ------------------------------------------------------------------ --
-- 6. Seed validation rules (shipment)
-- ------------------------------------------------------------------ --
WITH rs AS (SELECT id FROM tms.validation_rule_sets WHERE name = 'Shipment Standard')
INSERT INTO tms.validation_rules
    (rule_code, applies_to_entity, transaction_type, field_name, rule_type, parameters, error_message, severity, sort_order, rule_set_id, status)
SELECT
    'SHP-' || field_name || '-' || rule_type,
    'shipment',
    'shipment',
    field_name, rule_type, parameters::jsonb, error_message, severity, sort_order,
    rs.id,
    'active'
FROM rs, (VALUES
    ('shipment_number',       'required',       '{}',                                                    'Shipment Number is required.',             'error',   10),
    ('carrier_id',            'required',       '{}',                                                    'Carrier is required.',                     'error',   20),
    ('origin_id',             'required',       '{}',                                                    'Origin location is required.',             'error',   30),
    ('destination_id',        'required',       '{}',                                                    'Destination location is required.',        'error',   40),
    ('planned_ship_date',     'required',       '{}',                                                    'Planned ship date is required.',           'error',   50),
    ('planned_delivery_date', 'required',       '{}',                                                    'Planned delivery date is required.',       'error',   60),
    ('mode',                  'required',       '{}',                                                    'Transportation mode is required.',         'error',   70),
    ('mode',                  'allowed_values', '{"values":["FTL","LTL","Parcel","Rail","Ocean","Air","Intermodal"]}', 'Invalid transportation mode.', 'error',  80),
    ('equipment_type',        'required',       '{}',                                                    'Equipment type is required.',             'warning',  90),
    ('status',                'default_value',  '{"value":"draft"}',                                     'Status defaults to draft.',               'warning', 100),
    ('status',                'allowed_values', '{"values":["draft","planned","tendered","confirmed","in_transit","delivered","completed","canceled","exception"]}', 'Invalid shipment status.', 'error', 110),
    ('total_weight',          'min_value',      '{"value":0}',                                           'Total weight must be >= 0.',              'error',   120),
    ('total_pieces',          'min_value',      '{"value":1}',                                           'Total pieces must be at least 1.',        'error',   130)
) AS v(field_name, rule_type, parameters, error_message, severity, sort_order)
ON CONFLICT (rule_code) DO NOTHING;

COMMIT;
