-- ============================================================
-- Flow Ops TMS — Migration 005: Configurable Numbering Schemes
-- Run: PGPASSWORD=oms_dev_password psql -h localhost -p 5433 -U oms_user -d flow_ops_tms -f migration_005_numbering.sql
-- ============================================================

BEGIN;
SET search_path = tms;

CREATE TABLE IF NOT EXISTS tms.numbering_schemes (
    scheme_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         text NOT NULL UNIQUE, -- SHIPMENT | PURCHASE_ORDER | ORDER_RELEASE |
                                              -- LOAD | STOP | CARRIER_INVOICE | CLIENT_BILL |
                                              -- VOUCHER | CLAIM | DISPUTE
    scheme_name         text NOT NULL,
    prefix              text NOT NULL DEFAULT '',       -- e.g. SHP-
    suffix              text NOT NULL DEFAULT '',       -- e.g. -US
    separator           text NOT NULL DEFAULT '',       -- between prefix/counter/suffix
    padding             integer NOT NULL DEFAULT 6,     -- zero-pad length e.g. 6 → 000001
    include_year        boolean NOT NULL DEFAULT false, -- prepend current year e.g. SHP-2026-
    include_month       boolean NOT NULL DEFAULT false, -- prepend YYYYMM
    reset_period        text NOT NULL DEFAULT 'NEVER',  -- NEVER | YEARLY | MONTHLY
    next_value          bigint NOT NULL DEFAULT 1,
    last_reset_at       timestamptz,
    preview             text,                           -- computed preview, updated on save
    is_active           boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_numbering_schemes_touch_updated_at ON tms.numbering_schemes;
CREATE TRIGGER trg_numbering_schemes_touch_updated_at
    BEFORE UPDATE ON tms.numbering_schemes
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

-- Thread-safe number generation function
CREATE OR REPLACE FUNCTION tms.generate_number(p_entity_type text)
RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    v_scheme    tms.numbering_schemes%ROWTYPE;
    v_number    text;
    v_counter   text;
    v_year_part text := '';
BEGIN
    -- Lock the row for update to prevent concurrent duplicates
    SELECT * INTO v_scheme
    FROM tms.numbering_schemes
    WHERE entity_type = p_entity_type AND is_active = true
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No active numbering scheme found for entity type: %', p_entity_type;
    END IF;

    -- Handle reset period
    IF v_scheme.reset_period = 'YEARLY' AND
       (v_scheme.last_reset_at IS NULL OR
        EXTRACT(YEAR FROM now()) > EXTRACT(YEAR FROM v_scheme.last_reset_at)) THEN
        v_scheme.next_value := 1;
        UPDATE tms.numbering_schemes SET next_value = 1, last_reset_at = now()
        WHERE entity_type = p_entity_type;
    ELSIF v_scheme.reset_period = 'MONTHLY' AND
          (v_scheme.last_reset_at IS NULL OR
           TO_CHAR(now(),'YYYYMM') > TO_CHAR(v_scheme.last_reset_at,'YYYYMM')) THEN
        v_scheme.next_value := 1;
        UPDATE tms.numbering_schemes SET next_value = 1, last_reset_at = now()
        WHERE entity_type = p_entity_type;
    END IF;

    -- Build year/month part
    IF v_scheme.include_month THEN
        v_year_part := TO_CHAR(now(), 'YYYYMM') || v_scheme.separator;
    ELSIF v_scheme.include_year THEN
        v_year_part := TO_CHAR(now(), 'YYYY') || v_scheme.separator;
    END IF;

    -- Zero-pad counter
    v_counter := LPAD(v_scheme.next_value::text, v_scheme.padding, '0');

    -- Assemble number
    v_number := v_scheme.prefix || v_year_part || v_counter || v_scheme.suffix;

    -- Increment
    UPDATE tms.numbering_schemes
    SET next_value = next_value + 1
    WHERE entity_type = p_entity_type;

    RETURN v_number;
END;
$$;

-- Preview function (does not increment)
CREATE OR REPLACE FUNCTION tms.preview_number(p_entity_type text)
RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    v_scheme tms.numbering_schemes%ROWTYPE;
    v_year_part text := '';
BEGIN
    SELECT * INTO v_scheme FROM tms.numbering_schemes WHERE entity_type = p_entity_type LIMIT 1;
    IF NOT FOUND THEN RETURN 'N/A'; END IF;

    IF v_scheme.include_month THEN
        v_year_part := TO_CHAR(now(), 'YYYYMM') || v_scheme.separator;
    ELSIF v_scheme.include_year THEN
        v_year_part := TO_CHAR(now(), 'YYYY') || v_scheme.separator;
    END IF;

    RETURN v_scheme.prefix || v_year_part ||
           LPAD(v_scheme.next_value::text, v_scheme.padding, '0') ||
           v_scheme.suffix;
END;
$$;

-- ============================================================
-- SEED: DEFAULT SCHEMES FOR FLOW OPS TMS
-- ============================================================
INSERT INTO tms.numbering_schemes
    (entity_type, scheme_name, prefix, separator, padding, include_year, reset_period, next_value)
VALUES
  ('SHIPMENT',        'Shipment Numbers',         'SHP-', '-', 6, true,  'YEARLY',  1),
  ('PURCHASE_ORDER',  'Purchase Order Numbers',   'PO-',  '-', 6, true,  'YEARLY',  1),
  ('ORDER_RELEASE',   'Order Release Numbers',    'REL-', '-', 6, true,  'YEARLY',  1),
  ('LOAD',            'Load Numbers',             'LD-',  '-', 6, true,  'YEARLY',  1),
  ('STOP',            'Stop Numbers',             'STP-', '',  6, false, 'NEVER',   1),
  ('CARRIER_INVOICE', 'Carrier Invoice Numbers',  'CINV-','-', 6, true,  'YEARLY',  1),
  ('CLIENT_BILL',     'Client Bill Numbers',      'BILL-','-', 6, true,  'YEARLY',  1),
  ('VOUCHER',         'Voucher Numbers',          'VCH-', '-', 6, true,  'YEARLY',  1),
  ('CLAIM',           'Claim Numbers',            'CLM-', '-', 6, true,  'YEARLY',  1),
  ('DISPUTE',         'Dispute Numbers',          'DISP-','-', 6, true,  'YEARLY',  1)
ON CONFLICT (entity_type) DO NOTHING;

-- Update previews
UPDATE tms.numbering_schemes SET preview = tms.preview_number(entity_type);

COMMIT;
