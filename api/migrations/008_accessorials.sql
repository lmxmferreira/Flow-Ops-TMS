-- ============================================================
-- Migration: 008_accessorials.sql
-- TMS-RATE-007: Full accessorial charge catalog
-- ============================================================

BEGIN;

-- Add calculation_inputs and unit columns to accessorial_charges
ALTER TABLE tms.accessorial_charges
    ADD COLUMN IF NOT EXISTS calculation_basis TEXT NOT NULL DEFAULT 'flat',
    -- flat | per_hour | per_day | per_mile | per_km | per_unit | percentage | per_cwt
    ADD COLUMN IF NOT EXISTS input_label       TEXT,   -- human label for the input quantity (e.g. "Hours", "Days")
    ADD COLUMN IF NOT EXISTS min_units         NUMERIC(10,2),
    ADD COLUMN IF NOT EXISTS max_units         NUMERIC(10,2),
    ADD COLUMN IF NOT EXISTS free_units        NUMERIC(10,2),  -- free hours/days before charge starts
    ADD COLUMN IF NOT EXISTS calculation_notes TEXT;

-- Add constraint
DO $$ BEGIN
    ALTER TABLE tms.accessorial_charges
        ADD CONSTRAINT chk_acc_calc_basis CHECK (calculation_basis IN (
            'flat','per_hour','per_day','per_mile','per_km',
            'per_unit','percentage','per_cwt'
        ));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;

-- Seed all 14 required accessorial types (bare DO block, no transaction)
DO $$
DECLARE v_carrier_id UUID;
BEGIN
    SELECT carrier_id INTO v_carrier_id FROM tms.carriers LIMIT 1;
    IF v_carrier_id IS NULL THEN
        RAISE NOTICE 'No carriers found, skipping accessorial seed.';
        RETURN;
    END IF;

    INSERT INTO tms.accessorial_charges
        (carrier_id, charge_code, description, charge_type, calculation_basis,
         rate_amount, currency, applies_to_modes, input_label, free_units,
         min_units, max_units, calculation_notes, is_active)
    VALUES
        -- Detention (per hour after free time)
        (v_carrier_id, 'DETENTION',    'Detention (per hour after 2 free hours)',
         'per_unit', 'per_hour', 85.00, 'USD', ARRAY['FTL','LTL'],
         'Hours', 2, 0, 24,
         'Charged per hour after 2 free hours at pickup or delivery.', TRUE),

        -- Layover (flat per day driver is held)
        (v_carrier_id, 'LAYOVER',      'Driver Layover (per day)',
         'per_unit', 'per_day', 350.00, 'USD', ARRAY['FTL'],
         'Days', 0, 1, 7,
         'Charged when driver is required to layover due to shipper/consignee scheduling.', TRUE),

        -- Stop-off charge (per extra stop)
        (v_carrier_id, 'STOPOFF',      'Stop-Off Charge (per additional stop)',
         'per_unit', 'per_unit', 125.00, 'USD', ARRAY['FTL','LTL'],
         'Additional Stops', 0, 1, NULL,
         'Charged for each stop beyond the origin and primary destination.', TRUE),

        -- Liftgate pickup
        (v_carrier_id, 'LIFTGATE_PU',  'Liftgate Pickup',
         'flat', 'flat', 85.00, 'USD', ARRAY['LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Liftgate required at pickup location.', TRUE),

        -- Liftgate delivery
        (v_carrier_id, 'LIFTGATE_DEL', 'Liftgate Delivery',
         'flat', 'flat', 85.00, 'USD', ARRAY['LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Liftgate required at delivery location.', TRUE),

        -- Inside delivery
        (v_carrier_id, 'INSIDEDEL',    'Inside Delivery',
         'flat', 'flat', 95.00, 'USD', ARRAY['LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Delivery inside the building beyond the threshold.', TRUE),

        -- Inside pickup
        (v_carrier_id, 'INSIDEPU',     'Inside Pickup',
         'flat', 'flat', 95.00, 'USD', ARRAY['LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Pickup inside the building beyond the threshold.', TRUE),

        -- Residential delivery
        (v_carrier_id, 'RESIDENTIAL',  'Residential Delivery',
         'flat', 'flat', 55.00, 'USD', ARRAY['LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Delivery to a residential address.', TRUE),

        -- Lumper service
        (v_carrier_id, 'LUMPER',       'Lumper Service',
         'per_unit', 'per_hour', 45.00, 'USD', ARRAY['FTL','LTL'],
         'Hours', 0, 1, 12,
         'Third-party labor for loading or unloading.', TRUE),

        -- Redelivery attempt
        (v_carrier_id, 'REDELIVERY',   'Redelivery Attempt',
         'flat', 'flat', 75.00, 'USD', ARRAY['LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Charged for each additional delivery attempt after first failed attempt.', TRUE),

        -- Storage (per day after free days)
        (v_carrier_id, 'STORAGE',      'Storage (per day after 2 free days)',
         'per_unit', 'per_day', 45.00, 'USD', ARRAY['FTL','LTL','Parcel'],
         'Days', 2, 0, NULL,
         'Charged per day after 2 free days of storage at terminal.', TRUE),

        -- Chassis usage (ocean/intermodal)
        (v_carrier_id, 'CHASSIS',      'Chassis Usage (per day)',
         'per_unit', 'per_day', 35.00, 'USD', ARRAY['Ocean','Intermodal','Rail'],
         'Days', 0, 1, NULL,
         'Daily chassis rental fee for container transport.', TRUE),

        -- Toll charges (pass-through)
        (v_carrier_id, 'TOLLS',        'Toll Charges (pass-through)',
         'flat', 'flat', 0.00, 'USD', ARRAY['FTL','LTL'],
         NULL, NULL, NULL, NULL,
         'Actual toll charges passed through at cost.', TRUE),

        -- Demurrage (ocean/rail)
        (v_carrier_id, 'DEMURRAGE',    'Demurrage (per day after free days)',
         'per_unit', 'per_day', 150.00, 'USD', ARRAY['Ocean','Rail','Intermodal'],
         'Days', 3, 0, NULL,
         'Charged when container is held at port/terminal beyond free days.', TRUE),

        -- Customs clearance
        (v_carrier_id, 'CUSTOMS',      'Customs Clearance Fee',
         'flat', 'flat', 175.00, 'USD', ARRAY['Ocean','Air','Intermodal'],
         NULL, NULL, NULL, NULL,
         'Fee for customs brokerage and clearance services.', TRUE),

        -- Customs bond
        (v_carrier_id, 'CUSTOMS_BOND', 'Customs Bond',
         'percentage', 'percentage', 0.50, 'USD', ARRAY['Ocean','Air'],
         NULL, NULL, NULL, NULL,
         '0.5% of shipment value for single-entry customs bond.', TRUE),

        -- Temperature surcharge
        (v_carrier_id, 'TEMP_CONTROL', 'Temperature Control Surcharge',
         'flat', 'flat', 225.00, 'USD', ARRAY['FTL','LTL'],
         NULL, NULL, NULL, NULL,
         'Surcharge for refrigerated or heated transport.', TRUE),

        -- Appointment scheduling
        (v_carrier_id, 'APPOINTMENT',  'Appointment Scheduling',
         'flat', 'flat', 35.00, 'USD', ARRAY['FTL','LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Fee for scheduling a specific delivery appointment.', TRUE),

        -- Hazmat surcharge
        (v_carrier_id, 'HAZMAT',       'Hazardous Materials Surcharge',
         'flat', 'flat', 195.00, 'USD', ARRAY['FTL','LTL','Parcel'],
         NULL, NULL, NULL, NULL,
         'Surcharge for shipments containing hazardous materials.', TRUE),

        -- Overweight/overlength
        (v_carrier_id, 'OVERLENGTH',   'Overlength/Oversize Surcharge',
         'flat', 'flat', 150.00, 'USD', ARRAY['FTL','LTL'],
         NULL, NULL, NULL, NULL,
         'Surcharge for shipments exceeding standard length or size limits.', TRUE)

    ON CONFLICT (charge_code) DO UPDATE SET
        description        = EXCLUDED.description,
        calculation_basis  = EXCLUDED.calculation_basis,
        input_label        = EXCLUDED.input_label,
        free_units         = EXCLUDED.free_units,
        calculation_notes  = EXCLUDED.calculation_notes;

    RAISE NOTICE 'Seeded 20 accessorial charges for carrier %', v_carrier_id;
END $$;
