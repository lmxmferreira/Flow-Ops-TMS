-- ============================================================
-- Migration 004b: Rating seed data (run outside transaction
-- so tables survive if seed fails)
-- ============================================================

DO $$
DECLARE
    v_carrier_id  UUID;
    v_card_ftl    UUID;
    v_card_ltl    UUID;
    v_card_parcel UUID;
    v_lane_ftl    UUID;
    v_lane_ltl    UUID;
    v_lane_parcel UUID;
BEGIN
    SELECT carrier_id INTO v_carrier_id FROM tms.carriers LIMIT 1;

    IF v_carrier_id IS NULL THEN
        RAISE NOTICE 'No carriers found — skipping seed data.';
        RETURN;
    END IF;

    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    VALUES (v_carrier_id, 'FTL Standard 2025', 'FTL', 'USD', '2025-01-01', '2025-12-31')
    RETURNING rate_card_id INTO v_card_ftl;

    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    VALUES (v_carrier_id, 'LTL Standard 2025', 'LTL', 'USD', '2025-01-01', '2025-12-31')
    RETURNING rate_card_id INTO v_card_ltl;

    INSERT INTO tms.carrier_rate_cards (carrier_id, name, mode, currency, effective_date, expiry_date)
    VALUES (v_carrier_id, 'Parcel Standard 2025', 'Parcel', 'USD', '2025-01-01', '2025-12-31')
    RETURNING rate_card_id INTO v_card_parcel;

    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    VALUES (v_card_ftl, 'FTL - Any to Any', 'any', 'any', 0)
    RETURNING lane_id INTO v_lane_ftl;

    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    VALUES (v_card_ltl, 'LTL - Any to Any', 'any', 'any', 0)
    RETURNING lane_id INTO v_lane_ltl;

    INSERT INTO tms.carrier_rate_lanes (rate_card_id, lane_name, origin_type, destination_type, priority)
    VALUES (v_card_parcel, 'Parcel - Any to Any', 'any', 'any', 0)
    RETURNING lane_id INTO v_lane_parcel;

    INSERT INTO tms.carrier_rate_lines
        (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    VALUES
        (v_lane_ftl, 'base_flat', 'LINEHAUL', 'FTL Base Charge',    250.00, NULL, 200.00, 10),
        (v_lane_ftl, 'per_mile',  'LINEHAUL', 'FTL Per Mile Rate',    2.85, 'mi', NULL,   20),
        (v_lane_ftl, 'minimum',   'MINIMUM',  'FTL Minimum Charge', 500.00, NULL, NULL,   30);

    INSERT INTO tms.carrier_rate_lines
        (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    VALUES
        (v_lane_ltl, 'per_lb',     'LINEHAUL', 'LTL Per Pound Rate',   0.18, 'lb',     45.00, 10),
        (v_lane_ltl, 'per_pallet', 'LINEHAUL', 'LTL Per Pallet Rate', 38.00, 'pallet', NULL,  20),
        (v_lane_ltl, 'minimum',    'MINIMUM',  'LTL Minimum Charge',  85.00, NULL,     NULL,  30);

    INSERT INTO tms.carrier_rate_lines
        (lane_id, charge_type, charge_code, description, rate_amount, uom, min_charge, sort_order)
    VALUES
        (v_lane_parcel, 'base_flat', 'LINEHAUL', 'Parcel Base Fee',       8.50, NULL, NULL,  10),
        (v_lane_parcel, 'per_kg',    'LINEHAUL', 'Parcel Per KG Rate',    1.25, 'kg', NULL,  20),
        (v_lane_parcel, 'minimum',   'MINIMUM',  'Parcel Minimum Charge', 12.00, NULL, NULL, 30);

    INSERT INTO tms.fuel_surcharge_schedules
        (schedule_code, carrier_id, name, mode, effective_date, expiry_date, rate_type, rate_value, basis, is_active)
    VALUES
        ('FSC-FTL-2025',    v_carrier_id, 'FTL Fuel Surcharge 2025',    'FTL',    '2025-01-01', '2025-12-31', 'percentage', 18.5, 'linehaul', TRUE),
        ('FSC-LTL-2025',    v_carrier_id, 'LTL Fuel Surcharge 2025',    'LTL',    '2025-01-01', '2025-12-31', 'percentage', 22.0, 'linehaul', TRUE),
        ('FSC-PARCEL-2025', v_carrier_id, 'Parcel Fuel Surcharge 2025', 'Parcel', '2025-01-01', '2025-12-31', 'percentage', 15.0, 'linehaul', TRUE)
    ON CONFLICT (schedule_code) DO NOTHING;

    INSERT INTO tms.accessorial_charges
        (carrier_id, charge_code, description, charge_type, rate_amount, applies_to_modes)
    VALUES
        (v_carrier_id, 'LIFTGATE',    'Liftgate Service',      'flat',     75.00, ARRAY['FTL','LTL','Parcel']),
        (v_carrier_id, 'RESIDENTIAL', 'Residential Delivery',  'flat',     45.00, ARRAY['LTL','Parcel']),
        (v_carrier_id, 'DETENTION',   'Detention (per hour)',   'per_unit', 85.00, ARRAY['FTL','LTL']),
        (v_carrier_id, 'INSIDEDEL',   'Inside Delivery',        'flat',     95.00, ARRAY['LTL','Parcel']),
        (v_carrier_id, 'REDELIVERY',  'Redelivery Attempt',     'flat',     65.00, ARRAY['LTL','Parcel']),
        (v_carrier_id, 'APPOINTMENT', 'Appointment Scheduling', 'flat',     35.00, ARRAY['FTL','LTL','Parcel']);

    RAISE NOTICE 'Seed data inserted for carrier %', v_carrier_id;
END;
$$;
