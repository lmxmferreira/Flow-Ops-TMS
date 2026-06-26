-- ============================================================
-- Flow Ops TMS — Migration 002: Seed Data (v3 - all columns verified)
-- Run: PGPASSWORD=oms_dev_password psql -h localhost -p 5433 -U oms_user -d flow_ops_tms -f migration_002_seed.sql
-- ============================================================

BEGIN;
SET search_path = tms;

-- ============================================================
-- LOOKUP TYPES
-- ============================================================
INSERT INTO tms.lookup_types (lookup_type_id, lookup_type_code, lookup_type_name) VALUES
  (gen_random_uuid(), 'SHIPMENT_STATUS', 'Shipment Status'),
  (gen_random_uuid(), 'PO_STATUS',       'Purchase Order Status'),
  (gen_random_uuid(), 'RELEASE_STATUS',  'Order Release Status'),
  (gen_random_uuid(), 'CARRIER_STATUS',  'Carrier Status'),
  (gen_random_uuid(), 'INVOICE_STATUS',  'Carrier Invoice Status'),
  (gen_random_uuid(), 'FREIGHT_TERMS',   'Freight Terms'),
  (gen_random_uuid(), 'INCOTERMS',       'Incoterms'),
  (gen_random_uuid(), 'CURRENCY',        'Currency'),
  (gen_random_uuid(), 'PRIORITY',        'Priority'),
  (gen_random_uuid(), 'PAYMENT_TERMS',   'Payment Terms'),
  (gen_random_uuid(), 'PO_TYPE',         'PO Type'),
  (gen_random_uuid(), 'PARTY_TYPE',      'Party Type'),
  (gen_random_uuid(), 'ENTITY_STATUS',   'Entity Status'),
  (gen_random_uuid(), 'EXCEPTION_TYPE',  'Exception Type'),
  (gen_random_uuid(), 'DOCUMENT_TYPE',   'Document Type'),
  (gen_random_uuid(), 'TENDER_STATUS',   'Tender Status')
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION tms.ltype(code text) RETURNS uuid LANGUAGE sql AS $$
  SELECT lookup_type_id FROM tms.lookup_types WHERE lookup_type_code = code LIMIT 1
$$;

-- ============================================================
-- LOOKUP VALUES
-- ============================================================
INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('ENTITY_STATUS'), 'ACTIVE',    'Active',    1),
  (gen_random_uuid(), tms.ltype('ENTITY_STATUS'), 'INACTIVE',  'Inactive',  2),
  (gen_random_uuid(), tms.ltype('ENTITY_STATUS'), 'SUSPENDED', 'Suspended', 3)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'DRAFT',      'Draft',      1),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'PLANNED',    'Planned',    2),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'TENDERED',   'Tendered',   3),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'CONFIRMED',  'Confirmed',  4),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'IN_TRANSIT', 'In Transit', 5),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'DELIVERED',  'Delivered',  6),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'EXCEPTION',  'Exception',  7),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'CANCELLED',  'Cancelled',  8),
  (gen_random_uuid(), tms.ltype('SHIPMENT_STATUS'), 'CLOSED',     'Closed',     9)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'DRAFT',              'Draft',              1),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'OPEN',               'Open',               2),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'PARTIALLY_RELEASED', 'Partially Released', 3),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'FULLY_RELEASED',     'Fully Released',     4),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'SHIPPED',            'Shipped',            5),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'CLOSED',             'Closed',             6),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'CANCELLED',          'Cancelled',          7),
  (gen_random_uuid(), tms.ltype('PO_STATUS'), 'ON_HOLD',            'On Hold',            8)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'DRAFT',      'Draft',      1),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'READY',      'Ready',      2),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'PLANNED',    'Planned',    3),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'TENDERED',   'Tendered',   4),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'ACCEPTED',   'Accepted',   5),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'PICKED_UP',  'Picked Up',  6),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'IN_TRANSIT', 'In Transit', 7),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'DELIVERED',  'Delivered',  8),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'COMPLETED',  'Completed',  9),
  (gen_random_uuid(), tms.ltype('RELEASE_STATUS'), 'CANCELLED',  'Cancelled', 10)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('CARRIER_STATUS'), 'ACTIVE',        'Active',           1),
  (gen_random_uuid(), tms.ltype('CARRIER_STATUS'), 'INACTIVE',      'Inactive',         2),
  (gen_random_uuid(), tms.ltype('CARRIER_STATUS'), 'PENDING',       'Pending Approval', 3),
  (gen_random_uuid(), tms.ltype('CARRIER_STATUS'), 'SUSPENDED',     'Suspended',        4),
  (gen_random_uuid(), tms.ltype('CARRIER_STATUS'), 'NON_COMPLIANT', 'Non-Compliant',    5)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'RECEIVED',  'Received',  1),
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'MATCHED',   'Matched',   2),
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'EXCEPTION', 'Exception', 3),
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'DISPUTED',  'Disputed',  4),
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'APPROVED',  'Approved',  5),
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'PAID',      'Paid',      6),
  (gen_random_uuid(), tms.ltype('INVOICE_STATUS'), 'CANCELLED', 'Cancelled', 7)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('FREIGHT_TERMS'), 'PREPAID',     'Prepaid',       1),
  (gen_random_uuid(), tms.ltype('FREIGHT_TERMS'), 'COLLECT',     'Collect',       2),
  (gen_random_uuid(), tms.ltype('FREIGHT_TERMS'), 'THIRD_PARTY', 'Third Party',   3),
  (gen_random_uuid(), tms.ltype('FREIGHT_TERMS'), 'PREPAID_ADD', 'Prepaid & Add', 4)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('INCOTERMS'), 'EXW', 'EXW – Ex Works',               1),
  (gen_random_uuid(), tms.ltype('INCOTERMS'), 'FCA', 'FCA – Free Carrier',           2),
  (gen_random_uuid(), tms.ltype('INCOTERMS'), 'FOB', 'FOB – Free On Board',          3),
  (gen_random_uuid(), tms.ltype('INCOTERMS'), 'CIF', 'CIF – Cost Insurance Freight', 4),
  (gen_random_uuid(), tms.ltype('INCOTERMS'), 'DDP', 'DDP – Delivered Duty Paid',    5),
  (gen_random_uuid(), tms.ltype('INCOTERMS'), 'DAP', 'DAP – Delivered At Place',     6)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('CURRENCY'), 'USD', 'US Dollar',       1),
  (gen_random_uuid(), tms.ltype('CURRENCY'), 'EUR', 'Euro',            2),
  (gen_random_uuid(), tms.ltype('CURRENCY'), 'GBP', 'British Pound',   3),
  (gen_random_uuid(), tms.ltype('CURRENCY'), 'CAD', 'Canadian Dollar', 4),
  (gen_random_uuid(), tms.ltype('CURRENCY'), 'MXN', 'Mexican Peso',    5)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('PRIORITY'), 'LOW',    'Low',    1),
  (gen_random_uuid(), tms.ltype('PRIORITY'), 'NORMAL', 'Normal', 2),
  (gen_random_uuid(), tms.ltype('PRIORITY'), 'HIGH',   'High',   3),
  (gen_random_uuid(), tms.ltype('PRIORITY'), 'URGENT', 'Urgent', 4)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('PAYMENT_TERMS'), 'NET15', 'Net 15', 1),
  (gen_random_uuid(), tms.ltype('PAYMENT_TERMS'), 'NET30', 'Net 30', 2),
  (gen_random_uuid(), tms.ltype('PAYMENT_TERMS'), 'NET45', 'Net 45', 3),
  (gen_random_uuid(), tms.ltype('PAYMENT_TERMS'), 'NET60', 'Net 60', 4),
  (gen_random_uuid(), tms.ltype('PAYMENT_TERMS'), 'COD',   'COD',    5)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('PO_TYPE'), 'STANDARD',  'Standard',  1),
  (gen_random_uuid(), tms.ltype('PO_TYPE'), 'BLANKET',   'Blanket',   2),
  (gen_random_uuid(), tms.ltype('PO_TYPE'), 'TRANSFER',  'Transfer',  3),
  (gen_random_uuid(), tms.ltype('PO_TYPE'), 'DROP_SHIP', 'Drop Ship', 4),
  (gen_random_uuid(), tms.ltype('PO_TYPE'), 'RETURN',    'Return',    5)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('PARTY_TYPE'), 'CUSTOMER', 'Customer', 1),
  (gen_random_uuid(), tms.ltype('PARTY_TYPE'), 'SUPPLIER', 'Supplier', 2),
  (gen_random_uuid(), tms.ltype('PARTY_TYPE'), 'CARRIER',  'Carrier',  3),
  (gen_random_uuid(), tms.ltype('PARTY_TYPE'), 'BROKER',   'Broker',   4),
  (gen_random_uuid(), tms.ltype('PARTY_TYPE'), 'INTERNAL', 'Internal', 5)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('EXCEPTION_TYPE'), 'DELAY',      'Delay',           1),
  (gen_random_uuid(), tms.ltype('EXCEPTION_TYPE'), 'DAMAGE',     'Damage',          2),
  (gen_random_uuid(), tms.ltype('EXCEPTION_TYPE'), 'SHORTAGE',   'Shortage',        3),
  (gen_random_uuid(), tms.ltype('EXCEPTION_TYPE'), 'OVERAGE',    'Overage',         4),
  (gen_random_uuid(), tms.ltype('EXCEPTION_TYPE'), 'MISSED_PU',  'Missed Pickup',   5),
  (gen_random_uuid(), tms.ltype('EXCEPTION_TYPE'), 'MISSED_DLV', 'Missed Delivery', 6)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('DOCUMENT_TYPE'), 'BOL',     'Bill of Lading',    1),
  (gen_random_uuid(), tms.ltype('DOCUMENT_TYPE'), 'POD',     'Proof of Delivery', 2),
  (gen_random_uuid(), tms.ltype('DOCUMENT_TYPE'), 'INVOICE', 'Carrier Invoice',   3),
  (gen_random_uuid(), tms.ltype('DOCUMENT_TYPE'), 'PACKING', 'Packing List',      4),
  (gen_random_uuid(), tms.ltype('DOCUMENT_TYPE'), 'CUSTOMS', 'Customs Document',  5)
ON CONFLICT DO NOTHING;

INSERT INTO tms.lookup_values (lookup_value_id, lookup_type_id, lookup_code, display_name, sort_order) VALUES
  (gen_random_uuid(), tms.ltype('TENDER_STATUS'), 'PENDING',   'Pending',   1),
  (gen_random_uuid(), tms.ltype('TENDER_STATUS'), 'SENT',      'Sent',      2),
  (gen_random_uuid(), tms.ltype('TENDER_STATUS'), 'ACCEPTED',  'Accepted',  3),
  (gen_random_uuid(), tms.ltype('TENDER_STATUS'), 'REJECTED',  'Rejected',  4),
  (gen_random_uuid(), tms.ltype('TENDER_STATUS'), 'EXPIRED',   'Expired',   5),
  (gen_random_uuid(), tms.ltype('TENDER_STATUS'), 'CANCELLED', 'Cancelled', 6)
ON CONFLICT DO NOTHING;

-- ============================================================
-- TRANSPORT MODES
-- ============================================================
INSERT INTO tms.transport_modes (transport_mode_id, mode_code, mode_name) VALUES
  (gen_random_uuid(), 'TRUCK',      'Truck / Road'),
  (gen_random_uuid(), 'AIR',        'Air Freight'),
  (gen_random_uuid(), 'OCEAN',      'Ocean Freight'),
  (gen_random_uuid(), 'RAIL',       'Rail'),
  (gen_random_uuid(), 'PARCEL',     'Parcel / Courier'),
  (gen_random_uuid(), 'INTERMODAL', 'Intermodal'),
  (gen_random_uuid(), 'LTL',        'Less Than Truckload'),
  (gen_random_uuid(), 'FTL',        'Full Truckload')
ON CONFLICT DO NOTHING;

-- ============================================================
-- SERVICE LEVELS
-- ============================================================
INSERT INTO tms.service_levels (service_level_id, service_level_code, service_level_name, transit_time_hours, priority_rank) VALUES
  (gen_random_uuid(), 'GROUND',    'Ground',         96,  5),
  (gen_random_uuid(), 'EXPRESS',   'Express',        48,  3),
  (gen_random_uuid(), 'SAME_DAY',  'Same Day',        8,  1),
  (gen_random_uuid(), 'NEXT_DAY',  'Next Day Air',   24,  2),
  (gen_random_uuid(), 'TWO_DAY',   '2-Day Air',      48,  3),
  (gen_random_uuid(), 'STD_OCEAN', 'Standard Ocean', 504, 10),
  (gen_random_uuid(), 'LTL_STD',   'LTL Standard',   120,  6),
  (gen_random_uuid(), 'FTL_STD',   'FTL Standard',    72,  4)
ON CONFLICT DO NOTHING;

-- ============================================================
-- EQUIPMENT TYPES (max_weight, max_volume — no _value suffix)
-- ============================================================
INSERT INTO tms.equipment_types (equipment_type_id, equipment_code, equipment_name, max_weight, max_volume) VALUES
  (gen_random_uuid(), 'DV53',    '53-ft Dry Van',           45000, 2800),
  (gen_random_uuid(), 'FLATBED', 'Flatbed 48-ft',           48000, NULL),
  (gen_random_uuid(), 'REEFER',  '53-ft Refrigerated Van',  44000, 2700),
  (gen_random_uuid(), 'CONT20',  '20-ft ISO Container',     47900, 1172),
  (gen_random_uuid(), 'CONT40',  '40-ft ISO Container',     58800, 2385),
  (gen_random_uuid(), 'PARCEL',  'Parcel / Small Package',  NULL,  NULL),
  (gen_random_uuid(), 'LTLVAN',  'LTL Van',                 20000, 1400),
  (gen_random_uuid(), 'CHASSIS', 'Container Chassis',       NULL,  NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- UNIT OF MEASURES (uom_category_id nullable, status_id nullable)
-- ============================================================
INSERT INTO tms.unit_of_measures (uom_id, uom_code, uom_name) VALUES
  (gen_random_uuid(), 'EA',  'Each'),
  (gen_random_uuid(), 'CS',  'Case'),
  (gen_random_uuid(), 'PAL', 'Pallet'),
  (gen_random_uuid(), 'KG',  'Kilogram'),
  (gen_random_uuid(), 'LB',  'Pound'),
  (gen_random_uuid(), 'MT',  'Metric Ton'),
  (gen_random_uuid(), 'M3',  'Cubic Meter'),
  (gen_random_uuid(), 'CF',  'Cubic Foot'),
  (gen_random_uuid(), 'M',   'Meter'),
  (gen_random_uuid(), 'FT',  'Foot')
ON CONFLICT DO NOTHING;

-- ============================================================
-- CHARGE CODES (billable_flag, payable_flag — no is_billable_to_client)
-- ============================================================
INSERT INTO tms.charge_codes (charge_code_id, charge_code, charge_name, billable_flag, payable_flag) VALUES
  (gen_random_uuid(), 'LINEHAUL',    'Line Haul',            true,  true),
  (gen_random_uuid(), 'FUEL',        'Fuel Surcharge',       true,  true),
  (gen_random_uuid(), 'LIFTGATE',    'Liftgate',             true,  true),
  (gen_random_uuid(), 'DETENTION',   'Detention',            true,  true),
  (gen_random_uuid(), 'REDELIVERY',  'Redelivery',           true,  true),
  (gen_random_uuid(), 'RESIDENTIAL', 'Residential Delivery', true,  true),
  (gen_random_uuid(), 'STOPOFF',     'Stop-Off Charge',      true,  true),
  (gen_random_uuid(), 'LUMPER',      'Lumper Service',       true,  true),
  (gen_random_uuid(), 'STORAGE',     'Storage',              true,  true),
  (gen_random_uuid(), 'TAX',         'Tax',                  false, true),
  (gen_random_uuid(), 'DISCOUNT',    'Discount',             false, false),
  (gen_random_uuid(), 'ADJUSTMENT',  'Manual Adjustment',    false, false)
ON CONFLICT DO NOTHING;

-- ============================================================
-- COST CENTERS (business_unit_id nullable)
-- ============================================================
INSERT INTO tms.cost_centers (cost_center_id, cost_center_code, cost_center_name) VALUES
  (gen_random_uuid(), 'CC-OPS-US',  'US Operations'),
  (gen_random_uuid(), 'CC-OPS-MX',  'Mexico Operations'),
  (gen_random_uuid(), 'CC-FINANCE', 'Finance & Audit'),
  (gen_random_uuid(), 'CC-TECH',    'Technology'),
  (gen_random_uuid(), 'CC-CORP',    'Corporate')
ON CONFLICT DO NOTHING;

-- ============================================================
-- PARTIES
-- ============================================================
INSERT INTO tms.parties (party_id, party_code, party_name, party_type_id, tax_identifier, status_id) VALUES
  (gen_random_uuid(), 'CUST-001', 'Acme Corporation',      (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='CUSTOMER' LIMIT 1), '12-3456789', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1)),
  (gen_random_uuid(), 'CUST-002', 'Global Retail Inc',     (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='CUSTOMER' LIMIT 1), '98-7654321', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1)),
  (gen_random_uuid(), 'CUST-003', 'Metro Distribution Co', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='CUSTOMER' LIMIT 1), '55-1234567', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1)),
  (gen_random_uuid(), 'SUPP-001', 'Pacific Supply Co',     (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='SUPPLIER' LIMIT 1), '33-9876543', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1)),
  (gen_random_uuid(), 'SUPP-002', 'Eastern Manufacturing', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='SUPPLIER' LIMIT 1), '44-5678901', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1)),
  (gen_random_uuid(), 'SUPP-003', 'Gulf Coast Suppliers',  (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='SUPPLIER' LIMIT 1), '77-2345678', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1)),
  (gen_random_uuid(), 'SUPP-004', 'Coastal Imports Ltd',   (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='SUPPLIER' LIMIT 1), '88-3456789', (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1))
ON CONFLICT DO NOTHING;

-- ============================================================
-- LOCATIONS (country_id is uuid FK, not country_code text)
-- Use status_id from ACTIVE lookup value
-- ============================================================
DO $$
DECLARE v_active uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE' LIMIT 1);
BEGIN
  INSERT INTO tms.locations (location_id, location_code, location_name, address_line1, city, state_province, postal_code, latitude, longitude, status_id) VALUES
    (gen_random_uuid(), 'WH-DALLAS',    'Dallas Distribution Center', '4500 Logistics Blvd',   'Dallas',      'TX', '75201',  32.7767,  -96.7970, v_active),
    (gen_random_uuid(), 'WH-LA',        'Los Angeles Warehouse',      '1200 Harbor Blvd',      'Los Angeles', 'CA', '90001',  33.9425, -118.4081, v_active),
    (gen_random_uuid(), 'WH-CHICAGO',   'Chicago Crossdock',          '800 Industrial Dr',     'Chicago',     'IL', '60601',  41.8781,  -87.6298, v_active),
    (gen_random_uuid(), 'WH-MIAMI',     'Miami Port Facility',        '1 Port Blvd',           'Miami',       'FL', '33132',  25.7617,  -80.1918, v_active),
    (gen_random_uuid(), 'WH-NYC',       'New York DC',                '500 Commerce Ave',      'New York',    'NY', '10001',  40.7128,  -74.0060, v_active),
    (gen_random_uuid(), 'WH-HOUSTON',   'Houston Hub',                '3200 Port Rd',          'Houston',     'TX', '77001',  29.7604,  -95.3698, v_active),
    (gen_random_uuid(), 'WH-MONTERREY', 'Monterrey Mexico DC',        'Av Industrial 4500',    'Monterrey',   'NL', '64000',  25.6866, -100.3161, v_active),
    (gen_random_uuid(), 'CUST-ACME',    'Acme Corp - Chicago Plant',  '200 Manufacturing Way', 'Chicago',     'IL', '60602',  41.8800,  -87.6250, v_active),
    (gen_random_uuid(), 'CUST-GRI',     'Global Retail - Atlanta DC', '9000 Retail Park Dr',   'Atlanta',     'GA', '30301',  33.7490,  -84.3880, v_active),
    (gen_random_uuid(), 'SUPP-PAC',     'Pacific Supply - Oakland',   '100 Port View Ave',     'Oakland',     'CA', '94601',  37.8044, -122.2712, v_active)
  ON CONFLICT DO NOTHING;
END $$;

-- ============================================================
-- CARRIERS
-- ============================================================
-- Carriers: insert as parties first, then carrier records (party_id links them)
DO $$
DECLARE
  v_carrier_type uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='CARRIER' LIMIT 1);
  v_active       uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ACTIVE'  LIMIT 1);
  v_net30        uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='NET30'   LIMIT 1);
  p_fedex uuid; p_ups uuid; p_xpo uuid; p_saia uuid;
  p_estes uuid; p_olddom uuid; p_werner uuid; p_jbh uuid;
BEGIN
  -- Insert carrier parties
  p_fedex  := gen_random_uuid();
  p_ups    := gen_random_uuid();
  p_xpo    := gen_random_uuid();
  p_saia   := gen_random_uuid();
  p_estes  := gen_random_uuid();
  p_olddom := gen_random_uuid();
  p_werner := gen_random_uuid();
  p_jbh    := gen_random_uuid();

  INSERT INTO tms.parties (party_id, party_code, party_name, party_type_id, status_id, payment_terms_id) VALUES
    (p_fedex,  'CAR-FEDEX',  'FedEx Freight',        v_carrier_type, v_active, v_net30),
    (p_ups,    'CAR-UPS',    'UPS Freight',           v_carrier_type, v_active, v_net30),
    (p_xpo,    'CAR-XPO',    'XPO Logistics',        v_carrier_type, v_active, v_net30),
    (p_saia,   'CAR-SAIA',   'Saia LTL Freight',     v_carrier_type, v_active, v_net30),
    (p_estes,  'CAR-ESTES',  'Estes Express Lines',  v_carrier_type, v_active, v_net30),
    (p_olddom, 'CAR-OLDDOM', 'Old Dominion Freight', v_carrier_type, v_active, v_net30),
    (p_werner, 'CAR-WERNER', 'Werner Enterprises',   v_carrier_type, v_active, v_net30),
    (p_jbh,    'CAR-JBH',    'J.B. Hunt Transport',  v_carrier_type, v_active, v_net30)
  ON CONFLICT DO NOTHING;

  -- Insert carrier records linked to parties
  INSERT INTO tms.carriers (carrier_id, party_id, scac, mc_number, dot_number, status_id) VALUES
    (gen_random_uuid(), p_fedex,  'FXFE', 'MC-123456', 'DOT-111111', v_active),
    (gen_random_uuid(), p_ups,    'UPSS', 'MC-234567', 'DOT-222222', v_active),
    (gen_random_uuid(), p_xpo,    'XPOL', 'MC-345678', 'DOT-333333', v_active),
    (gen_random_uuid(), p_saia,   'SAIA', 'MC-456789', 'DOT-444444', v_active),
    (gen_random_uuid(), p_estes,  'EXLA', 'MC-567890', 'DOT-555555', v_active),
    (gen_random_uuid(), p_olddom, 'ODFL', 'MC-678901', 'DOT-666666', v_active),
    (gen_random_uuid(), p_werner, 'WERN', 'MC-789012', 'DOT-777777', v_active),
    (gen_random_uuid(), p_jbh,    'JBHT', 'MC-890123', 'DOT-888888', v_active)
  ON CONFLICT DO NOTHING;
END $$;

-- ============================================================
-- ITEMS (no freight_class column — it's a lookup FK)
-- ============================================================
INSERT INTO tms.items (item_id, item_number, item_description, weight_value, weight_uom_id, hazardous_flag) VALUES
  (gen_random_uuid(), 'ITEM-001', 'Industrial Pump Assembly',      450.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false),
  (gen_random_uuid(), 'ITEM-002', 'Electronic Control Panels',     220.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false),
  (gen_random_uuid(), 'ITEM-003', 'Steel Pipe Fittings',           680.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false),
  (gen_random_uuid(), 'ITEM-004', 'Chemical Drums (Hazmat)',       250.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), true),
  (gen_random_uuid(), 'ITEM-005', 'Refrigerated Pharmaceuticals',  180.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false),
  (gen_random_uuid(), 'ITEM-006', 'Automotive Parts Kit',          320.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false),
  (gen_random_uuid(), 'ITEM-007', 'Consumer Electronics Boxes',     85.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false),
  (gen_random_uuid(), 'ITEM-008', 'Textile Rolls',                 510.00, (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1), false)
ON CONFLICT DO NOTHING;

-- ============================================================
-- PURCHASE ORDERS
-- ============================================================
DO $$
DECLARE
  v_open    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='OPEN'               LIMIT 1);
  v_part    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='PARTIALLY_RELEASED' LIMIT 1);
  v_hold    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='ON_HOLD'            LIMIT 1);
  v_std     uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='STANDARD'           LIMIT 1);
  v_usd     uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='USD'                LIMIT 1);
  v_fob     uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='FOB'                LIMIT 1);
  v_prepaid uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='PREPAID'            LIMIT 1);
  v_net30   uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='NET30'              LIMIT 1);
  v_normal  uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='NORMAL'             LIMIT 1);
  v_high    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='HIGH'               LIMIT 1);
  v_supp1   uuid := (SELECT party_id FROM tms.parties WHERE party_code='SUPP-001' LIMIT 1);
  v_supp2   uuid := (SELECT party_id FROM tms.parties WHERE party_code='SUPP-002' LIMIT 1);
  v_supp3   uuid := (SELECT party_id FROM tms.parties WHERE party_code='SUPP-003' LIMIT 1);
  v_supp4   uuid := (SELECT party_id FROM tms.parties WHERE party_code='SUPP-004' LIMIT 1);
  v_cust1   uuid := (SELECT party_id FROM tms.parties WHERE party_code='CUST-001' LIMIT 1);
  v_loc_pac     uuid := (SELECT location_id FROM tms.locations WHERE location_code='SUPP-PAC'   LIMIT 1);
  v_loc_dallas  uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-DALLAS'  LIMIT 1);
  v_loc_la      uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-LA'      LIMIT 1);
  v_loc_chicago uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-CHICAGO' LIMIT 1);
  v_loc_miami   uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-MIAMI'   LIMIT 1);
  v_loc_nyc     uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-NYC'     LIMIT 1);
  v_loc_houston uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-HOUSTON' LIMIT 1);
  v_uom_ea uuid := (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='EA' LIMIT 1);
  v_uom_cs uuid := (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='CS' LIMIT 1);
  v_uom_kg uuid := (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1);
  v_item1  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-001' LIMIT 1);
  v_item2  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-002' LIMIT 1);
  v_item3  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-003' LIMIT 1);
  v_item5  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-005' LIMIT 1);
  v_item6  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-006' LIMIT 1);
  v_item7  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-007' LIMIT 1);
  v_po1 uuid; v_po2 uuid; v_po3 uuid; v_po4 uuid; v_po5 uuid;
BEGIN
  -- PO 1: Pacific Supply → Dallas
  v_po1 := gen_random_uuid();
  INSERT INTO tms.purchase_orders (purchase_order_id, purchase_order_number, status_id,
    purchase_order_type_id, supplier_party_id, buyer_party_id,
    ship_from_location_id, ship_to_location_id,
    incoterm_id, freight_terms_id, currency_id, payment_terms_id, priority_id,
    requested_ship_date, requested_delivery_date, source_reference)
  VALUES (v_po1, 'PO-2026-0001', v_open, v_std, v_supp1, v_cust1,
    v_loc_pac, v_loc_dallas, v_fob, v_prepaid, v_usd, v_net30, v_normal,
    '2026-07-01', '2026-07-10', 'ERP-REF-10001');
  INSERT INTO tms.purchase_order_lines (purchase_order_id, line_number, item_id, item_description,
    ordered_quantity, releasable_quantity, released_quantity, shipped_quantity,
    delivered_quantity, received_quantity, canceled_quantity, remaining_quantity,
    quantity_uom_id, weight_value, weight_uom_id, line_value, currency_id, status_id)
  VALUES
    (v_po1, '1', v_item1, 'Industrial Pump Assembly',  50,  50,  0, 0, 0, 0, 0,  50, v_uom_ea, 22500, v_uom_kg, 125000.00, v_usd, v_open),
    (v_po1, '2', v_item6, 'Automotive Parts Kit',     200, 200,  0, 0, 0, 0, 0, 200, v_uom_cs, 64000, v_uom_kg,  48000.00, v_usd, v_open);

  -- PO 2: Eastern Manufacturing → Chicago (partially released)
  v_po2 := gen_random_uuid();
  INSERT INTO tms.purchase_orders (purchase_order_id, purchase_order_number, status_id,
    purchase_order_type_id, supplier_party_id, buyer_party_id,
    ship_from_location_id, ship_to_location_id,
    incoterm_id, freight_terms_id, currency_id, payment_terms_id, priority_id,
    requested_ship_date, requested_delivery_date, source_reference)
  VALUES (v_po2, 'PO-2026-0002', v_part, v_std, v_supp2, v_cust1,
    v_loc_houston, v_loc_chicago, v_fob, v_prepaid, v_usd, v_net30, v_high,
    '2026-06-28', '2026-07-05', 'ERP-REF-10002');
  INSERT INTO tms.purchase_order_lines (purchase_order_id, line_number, item_id, item_description,
    ordered_quantity, releasable_quantity, released_quantity, shipped_quantity,
    delivered_quantity, received_quantity, canceled_quantity, remaining_quantity,
    quantity_uom_id, weight_value, weight_uom_id, line_value, currency_id, status_id)
  VALUES
    (v_po2, '1', v_item2, 'Electronic Control Panels', 100,  60,  40,  40, 0, 0, 0,  60, v_uom_ea,  22000, v_uom_kg, 85000.00, v_usd, v_part),
    (v_po2, '2', v_item3, 'Steel Pipe Fittings',       500, 300, 200, 200, 0, 0, 0, 300, v_uom_cs, 340000, v_uom_kg, 62500.00, v_usd, v_part);

  -- PO 3: Gulf Coast → Miami
  v_po3 := gen_random_uuid();
  INSERT INTO tms.purchase_orders (purchase_order_id, purchase_order_number, status_id,
    purchase_order_type_id, supplier_party_id, buyer_party_id,
    ship_from_location_id, ship_to_location_id,
    incoterm_id, freight_terms_id, currency_id, payment_terms_id, priority_id,
    requested_ship_date, requested_delivery_date, source_reference)
  VALUES (v_po3, 'PO-2026-0003', v_open, v_std, v_supp3, v_cust1,
    v_loc_houston, v_loc_miami, v_fob, v_prepaid, v_usd, v_net30, v_normal,
    '2026-07-05', '2026-07-15', 'ERP-REF-10003');
  INSERT INTO tms.purchase_order_lines (purchase_order_id, line_number, item_id, item_description,
    ordered_quantity, releasable_quantity, released_quantity, shipped_quantity,
    delivered_quantity, received_quantity, canceled_quantity, remaining_quantity,
    quantity_uom_id, weight_value, weight_uom_id, line_value, currency_id, status_id)
  VALUES
    (v_po3, '1', v_item5, 'Refrigerated Pharmaceuticals', 80, 80, 0, 0, 0, 0, 0, 80, v_uom_cs, 14400, v_uom_kg, 96000.00, v_usd, v_open);

  -- PO 4: Coastal Imports → NYC
  v_po4 := gen_random_uuid();
  INSERT INTO tms.purchase_orders (purchase_order_id, purchase_order_number, status_id,
    purchase_order_type_id, supplier_party_id, buyer_party_id,
    ship_from_location_id, ship_to_location_id,
    incoterm_id, freight_terms_id, currency_id, payment_terms_id, priority_id,
    requested_ship_date, requested_delivery_date, source_reference)
  VALUES (v_po4, 'PO-2026-0004', v_open, v_std, v_supp4, v_cust1,
    v_loc_la, v_loc_nyc, v_fob, v_prepaid, v_usd, v_net30, v_normal,
    '2026-07-10', '2026-07-20', 'ERP-REF-10004');
  INSERT INTO tms.purchase_order_lines (purchase_order_id, line_number, item_id, item_description,
    ordered_quantity, releasable_quantity, released_quantity, shipped_quantity,
    delivered_quantity, received_quantity, canceled_quantity, remaining_quantity,
    quantity_uom_id, weight_value, weight_uom_id, line_value, currency_id, status_id)
  VALUES
    (v_po4, '1', v_item7, 'Consumer Electronics Boxes', 1000, 1000, 0, 0, 0, 0, 0, 1000, v_uom_cs, 85000, v_uom_kg, 250000.00, v_usd, v_open);

  -- PO 5: Pacific Supply → LA (on hold)
  v_po5 := gen_random_uuid();
  INSERT INTO tms.purchase_orders (purchase_order_id, purchase_order_number, status_id,
    purchase_order_type_id, supplier_party_id, buyer_party_id,
    ship_from_location_id, ship_to_location_id,
    incoterm_id, freight_terms_id, currency_id, payment_terms_id, priority_id,
    requested_ship_date, requested_delivery_date, source_reference, hold_flag)
  VALUES (v_po5, 'PO-2026-0005', v_hold, v_std, v_supp1, v_cust1,
    v_loc_pac, v_loc_la, v_fob, v_prepaid, v_usd, v_net30, v_high,
    '2026-07-15', '2026-07-25', 'ERP-REF-10005', true);
  INSERT INTO tms.purchase_order_lines (purchase_order_id, line_number, item_id, item_description,
    ordered_quantity, releasable_quantity, released_quantity, shipped_quantity,
    delivered_quantity, received_quantity, canceled_quantity, remaining_quantity,
    quantity_uom_id, weight_value, weight_uom_id, line_value, currency_id, status_id)
  VALUES
    (v_po5, '1', v_item1, 'Industrial Pump Assembly', 25, 0, 0, 0, 0, 0, 0, 0, v_uom_ea, 11250, v_uom_kg, 62500.00, v_usd, v_hold);
END $$;

-- ============================================================
-- ORDER RELEASES
-- ============================================================
DO $$
DECLARE
  v_ready   uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='READY'      LIMIT 1);
  v_transit uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='IN_TRANSIT' LIMIT 1);
  v_prepaid uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='PREPAID'    LIMIT 1);
  v_high    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='HIGH'       LIMIT 1);
  v_normal  uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='NORMAL'     LIMIT 1);
  v_usd     uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='USD'        LIMIT 1);
  v_po2         uuid := (SELECT purchase_order_id FROM tms.purchase_orders WHERE purchase_order_number='PO-2026-0002' LIMIT 1);
  v_supp2       uuid := (SELECT party_id FROM tms.parties WHERE party_code='SUPP-002' LIMIT 1);
  v_cust1       uuid := (SELECT party_id FROM tms.parties WHERE party_code='CUST-001' LIMIT 1);
  v_loc_houston uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-HOUSTON' LIMIT 1);
  v_loc_chicago uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-CHICAGO' LIMIT 1);
  v_tm_truck    uuid := (SELECT transport_mode_id FROM tms.transport_modes WHERE mode_code='TRUCK' LIMIT 1);
  v_tm_ltl      uuid := (SELECT transport_mode_id FROM tms.transport_modes WHERE mode_code='LTL'   LIMIT 1);
  v_sl_ftl      uuid := (SELECT service_level_id FROM tms.service_levels WHERE service_level_code='FTL_STD' LIMIT 1);
  v_sl_ltl      uuid := (SELECT service_level_id FROM tms.service_levels WHERE service_level_code='LTL_STD' LIMIT 1);
  v_uom_ea uuid := (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='EA' LIMIT 1);
  v_uom_cs uuid := (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='CS' LIMIT 1);
  v_uom_kg uuid := (SELECT uom_id FROM tms.unit_of_measures WHERE uom_code='KG' LIMIT 1);
  v_item2  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-002' LIMIT 1);
  v_item3  uuid := (SELECT item_id FROM tms.items WHERE item_number='ITEM-003' LIMIT 1);
  v_pol2_1 uuid := (SELECT pol.purchase_order_line_id FROM tms.purchase_order_lines pol JOIN tms.purchase_orders po ON po.purchase_order_id=pol.purchase_order_id WHERE po.purchase_order_number='PO-2026-0002' AND pol.line_number='1' LIMIT 1);
  v_pol2_2 uuid := (SELECT pol.purchase_order_line_id FROM tms.purchase_order_lines pol JOIN tms.purchase_orders po ON po.purchase_order_id=pol.purchase_order_id WHERE po.purchase_order_number='PO-2026-0002' AND pol.line_number='2' LIMIT 1);
  v_rel1 uuid; v_rel2 uuid;
BEGIN
  v_rel1 := gen_random_uuid();
  INSERT INTO tms.order_releases (order_release_id, order_release_number, status_id,
    source_purchase_order_id, supplier_party_id, customer_party_id,
    shipper_location_id, consignee_location_id,
    transport_mode_id, service_level_id, freight_terms_id, priority_id,
    requested_ship_date, requested_delivery_date)
  VALUES (v_rel1, 'REL-2026-0001', v_transit,
    v_po2, v_supp2, v_cust1, v_loc_houston, v_loc_chicago,
    v_tm_truck, v_sl_ftl, v_prepaid, v_high,
    '2026-06-28', '2026-07-05');
  INSERT INTO tms.order_release_lines (order_release_id, line_number, purchase_order_line_id,
    item_id, quantity, quantity_uom_id, weight_value, weight_uom_id,
    line_value, currency_id, status_id)
  VALUES
    (v_rel1, '1', v_pol2_1, v_item2,  40, v_uom_ea,   8800, v_uom_kg, 34000.00, v_usd, v_transit),
    (v_rel1, '2', v_pol2_2, v_item3, 200, v_uom_cs, 136000, v_uom_kg, 25000.00, v_usd, v_transit);

  v_rel2 := gen_random_uuid();
  INSERT INTO tms.order_releases (order_release_id, order_release_number, status_id,
    source_purchase_order_id, supplier_party_id, customer_party_id,
    shipper_location_id, consignee_location_id,
    transport_mode_id, service_level_id, freight_terms_id, priority_id,
    requested_ship_date, requested_delivery_date)
  VALUES (v_rel2, 'REL-2026-0002', v_ready,
    v_po2, v_supp2, v_cust1, v_loc_houston, v_loc_chicago,
    v_tm_ltl, v_sl_ltl, v_prepaid, v_normal,
    '2026-07-05', '2026-07-12');
  INSERT INTO tms.order_release_lines (order_release_id, line_number, purchase_order_line_id,
    item_id, quantity, quantity_uom_id, weight_value, weight_uom_id,
    line_value, currency_id, status_id)
  VALUES
    (v_rel2, '1', v_pol2_2, v_item3, 100, v_uom_cs, 68000, v_uom_kg, 12500.00, v_usd, v_ready);
END $$;

-- ============================================================
-- SHIPMENTS
-- ============================================================
DO $$
DECLARE
  v_in_transit uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='IN_TRANSIT' LIMIT 1);
  v_planned    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='PLANNED'    LIMIT 1);
  v_delivered  uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='DELIVERED'  LIMIT 1);
  v_exception  uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='EXCEPTION'  LIMIT 1);
  v_prepaid    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='PREPAID'    LIMIT 1);
  v_carrier_fedex uuid := (SELECT c.carrier_id FROM tms.carriers c JOIN tms.parties p ON p.party_id=c.party_id WHERE p.party_code='CAR-FEDEX'  LIMIT 1);
  v_carrier_xpo   uuid := (SELECT c.carrier_id FROM tms.carriers c JOIN tms.parties p ON p.party_id=c.party_id WHERE p.party_code='CAR-XPO'    LIMIT 1);
  v_carrier_saia  uuid := (SELECT c.carrier_id FROM tms.carriers c JOIN tms.parties p ON p.party_id=c.party_id WHERE p.party_code='CAR-SAIA'   LIMIT 1);
  v_carrier_jbh   uuid := (SELECT c.carrier_id FROM tms.carriers c JOIN tms.parties p ON p.party_id=c.party_id WHERE p.party_code='CAR-JBH'    LIMIT 1);
  v_loc_houston uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-HOUSTON' LIMIT 1);
  v_loc_chicago uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-CHICAGO' LIMIT 1);
  v_loc_dallas  uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-DALLAS'  LIMIT 1);
  v_loc_la      uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-LA'      LIMIT 1);
  v_loc_miami   uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-MIAMI'   LIMIT 1);
  v_loc_nyc     uuid := (SELECT location_id FROM tms.locations WHERE location_code='WH-NYC'     LIMIT 1);
  v_tm_truck    uuid := (SELECT transport_mode_id FROM tms.transport_modes WHERE mode_code='TRUCK' LIMIT 1);
  v_tm_ltl      uuid := (SELECT transport_mode_id FROM tms.transport_modes WHERE mode_code='LTL'   LIMIT 1);
  v_sl_ftl      uuid := (SELECT service_level_id FROM tms.service_levels WHERE service_level_code='FTL_STD' LIMIT 1);
  v_sl_ltl      uuid := (SELECT service_level_id FROM tms.service_levels WHERE service_level_code='LTL_STD' LIMIT 1);
  v_eq_dv53     uuid := (SELECT equipment_type_id FROM tms.equipment_types WHERE equipment_code='DV53'   LIMIT 1);
  v_eq_ltl      uuid := (SELECT equipment_type_id FROM tms.equipment_types WHERE equipment_code='LTLVAN' LIMIT 1);
  v_rel1        uuid := (SELECT order_release_id FROM tms.order_releases WHERE order_release_number='REL-2026-0001' LIMIT 1);
  v_rel2        uuid := (SELECT order_release_id FROM tms.order_releases WHERE order_release_number='REL-2026-0002' LIMIT 1);
  v_shp1 uuid; v_shp2 uuid; v_shp3 uuid; v_shp4 uuid; v_shp5 uuid;
BEGIN
  v_shp1 := gen_random_uuid();
  INSERT INTO tms.shipments (shipment_id, shipment_number, shipment_status_id,
    carrier_id, origin_location_id, destination_location_id,
    transport_mode_id, service_level_id, equipment_type_id, freight_terms_id,
    planned_pickup_datetime, planned_delivery_datetime, actual_pickup_datetime,
    total_weight, pallet_count, carton_count)
  VALUES (v_shp1, 'SHP-2026-0001', v_in_transit,
    v_carrier_xpo, v_loc_houston, v_loc_chicago,
    v_tm_truck, v_sl_ftl, v_eq_dv53, v_prepaid,
    '2026-06-28 08:00', '2026-07-02 17:00', '2026-06-28 09:15',
    144800, 18, 240);
  INSERT INTO tms.shipment_order_releases (shipment_id, order_release_id) VALUES (v_shp1, v_rel1);

  v_shp2 := gen_random_uuid();
  INSERT INTO tms.shipments (shipment_id, shipment_number, shipment_status_id,
    carrier_id, origin_location_id, destination_location_id,
    transport_mode_id, service_level_id, equipment_type_id, freight_terms_id,
    planned_pickup_datetime, planned_delivery_datetime,
    total_weight, pallet_count, carton_count)
  VALUES (v_shp2, 'SHP-2026-0002', v_planned,
    v_carrier_saia, v_loc_houston, v_loc_chicago,
    v_tm_ltl, v_sl_ltl, v_eq_ltl, v_prepaid,
    '2026-07-05 08:00', '2026-07-09 17:00',
    68000, 12, 100);
  INSERT INTO tms.shipment_order_releases (shipment_id, order_release_id) VALUES (v_shp2, v_rel2);

  v_shp3 := gen_random_uuid();
  INSERT INTO tms.shipments (shipment_id, shipment_number, shipment_status_id,
    carrier_id, origin_location_id, destination_location_id,
    transport_mode_id, service_level_id, equipment_type_id, freight_terms_id,
    planned_pickup_datetime, planned_delivery_datetime,
    actual_pickup_datetime, actual_delivery_datetime,
    total_weight, pallet_count, carton_count, closeout_completed_flag)
  VALUES (v_shp3, 'SHP-2026-0003', v_delivered,
    v_carrier_fedex, v_loc_la, v_loc_dallas,
    v_tm_truck, v_sl_ftl, v_eq_dv53, v_prepaid,
    '2026-06-20 08:00', '2026-06-23 17:00',
    '2026-06-20 07:45', '2026-06-23 14:30',
    86000, 22, 200, true);

  v_shp4 := gen_random_uuid();
  INSERT INTO tms.shipments (shipment_id, shipment_number, shipment_status_id,
    carrier_id, origin_location_id, destination_location_id,
    transport_mode_id, service_level_id, equipment_type_id, freight_terms_id,
    planned_pickup_datetime, planned_delivery_datetime,
    total_weight, pallet_count, carton_count)
  VALUES (v_shp4, 'SHP-2026-0004', v_planned,
    v_carrier_jbh, v_loc_dallas, v_loc_nyc,
    v_tm_truck, v_sl_ftl, v_eq_dv53, v_prepaid,
    '2026-07-08 08:00', '2026-07-11 17:00',
    85000, 40, 1000);

  v_shp5 := gen_random_uuid();
  INSERT INTO tms.shipments (shipment_id, shipment_number, shipment_status_id,
    carrier_id, origin_location_id, destination_location_id,
    transport_mode_id, service_level_id, equipment_type_id, freight_terms_id,
    planned_pickup_datetime, planned_delivery_datetime, actual_pickup_datetime,
    total_weight, pallet_count, carton_count)
  VALUES (v_shp5, 'SHP-2026-0005', v_exception,
    v_carrier_fedex, v_loc_miami, v_loc_nyc,
    v_tm_truck, v_sl_ftl, v_eq_dv53, v_prepaid,
    '2026-06-25 08:00', '2026-06-28 17:00', '2026-06-25 10:30',
    14400, 8, 80);
END $$;

-- ============================================================
-- CARRIER INVOICES
-- carrier_invoices: invoiced_amount → invoice_total_amount
--                  status_id       → carrier_invoice_status_id
-- carrier_invoice_lines: amount → line_amount, rate → rate_amount
-- ============================================================
DO $$
DECLARE
  v_received uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='RECEIVED' LIMIT 1);
  v_approved uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='APPROVED' LIMIT 1);
  v_disputed uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='DISPUTED' LIMIT 1);
  v_usd      uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='USD'      LIMIT 1);
  v_net30    uuid := (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='NET30'    LIMIT 1);
  v_carrier_xpo   uuid := (SELECT c.carrier_id FROM tms.carriers c JOIN tms.parties p ON p.party_id=c.party_id WHERE p.party_code='CAR-XPO'   LIMIT 1);
  v_carrier_fedex uuid := (SELECT c.carrier_id FROM tms.carriers c JOIN tms.parties p ON p.party_id=c.party_id WHERE p.party_code='CAR-FEDEX' LIMIT 1);
  v_shp1 uuid := (SELECT shipment_id FROM tms.shipments WHERE shipment_number='SHP-2026-0001' LIMIT 1);
  v_shp3 uuid := (SELECT shipment_id FROM tms.shipments WHERE shipment_number='SHP-2026-0003' LIMIT 1);
  v_shp5 uuid := (SELECT shipment_id FROM tms.shipments WHERE shipment_number='SHP-2026-0005' LIMIT 1);
  v_cc_lh   uuid := (SELECT charge_code_id FROM tms.charge_codes WHERE charge_code='LINEHAUL'  LIMIT 1);
  v_cc_fuel uuid := (SELECT charge_code_id FROM tms.charge_codes WHERE charge_code='FUEL'      LIMIT 1);
  v_cc_det  uuid := (SELECT charge_code_id FROM tms.charge_codes WHERE charge_code='DETENTION' LIMIT 1);
  v_inv1 uuid; v_inv2 uuid; v_inv3 uuid;
BEGIN
  v_inv1 := gen_random_uuid();
  INSERT INTO tms.carrier_invoices (carrier_invoice_id, carrier_invoice_number, carrier_id,
    invoice_date, due_date, currency_id, payment_terms_id,
    invoice_total_amount, carrier_invoice_status_id)
  VALUES (v_inv1, 'XPO-INV-88441', v_carrier_xpo,
    '2026-07-03', '2026-08-02', v_usd, v_net30, 4855.50, v_received);
  INSERT INTO tms.carrier_invoice_lines (carrier_invoice_id, line_number, shipment_id,
    charge_code_id, description, quantity, rate_amount, line_amount)
  VALUES
    (v_inv1, '1', v_shp1, v_cc_lh,   'Line Haul Houston-Chicago', 1, 3900.00, 3900.00),
    (v_inv1, '2', v_shp1, v_cc_fuel, 'Fuel Surcharge 24.5%',      1,  955.50,  955.50);

  v_inv2 := gen_random_uuid();
  INSERT INTO tms.carrier_invoices (carrier_invoice_id, carrier_invoice_number, carrier_id,
    invoice_date, due_date, currency_id, payment_terms_id,
    invoice_total_amount, carrier_invoice_status_id)
  VALUES (v_inv2, 'FX-INV-22110', v_carrier_fedex,
    '2026-06-24', '2026-07-24', v_usd, v_net30, 3275.00, v_approved);
  INSERT INTO tms.carrier_invoice_lines (carrier_invoice_id, line_number, shipment_id,
    charge_code_id, description, quantity, rate_amount, line_amount)
  VALUES
    (v_inv2, '1', v_shp3, v_cc_lh,   'Line Haul LA-Dallas', 1, 2800.00, 2800.00),
    (v_inv2, '2', v_shp3, v_cc_fuel, 'Fuel Surcharge',      1,  475.00,  475.00);

  v_inv3 := gen_random_uuid();
  INSERT INTO tms.carrier_invoices (carrier_invoice_id, carrier_invoice_number, carrier_id,
    invoice_date, due_date, currency_id, payment_terms_id,
    invoice_total_amount, carrier_invoice_status_id)
  VALUES (v_inv3, 'FX-INV-22215', v_carrier_fedex,
    '2026-06-29', '2026-07-29', v_usd, v_net30, 2950.00, v_disputed);
  INSERT INTO tms.carrier_invoice_lines (carrier_invoice_id, line_number, shipment_id,
    charge_code_id, description, quantity, rate_amount, line_amount)
  VALUES
    (v_inv3, '1', v_shp5, v_cc_lh,   'Line Haul Miami-NYC', 1, 2200.00, 2200.00),
    (v_inv3, '2', v_shp5, v_cc_fuel, 'Fuel Surcharge',      1,  425.00,  425.00),
    (v_inv3, '3', v_shp5, v_cc_det,  'Detention 3hrs',      3,  108.33,  325.00);
END $$;

DROP FUNCTION IF EXISTS tms.ltype(text);

COMMIT;
