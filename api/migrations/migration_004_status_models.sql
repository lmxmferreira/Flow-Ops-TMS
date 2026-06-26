-- ============================================================
-- Flow Ops TMS — Migration 004: Status Models (v2 - using existing schema)
-- Uses existing tms.status_models + tms.status_values tables
-- Adds tms.status_transitions table
-- Run: PGPASSWORD=oms_dev_password psql -h localhost -p 5433 -U oms_user -d flow_ops_tms -f migration_004_status_models.sql
-- ============================================================

BEGIN;
SET search_path = tms;

-- ============================================================
-- ADD MISSING COLUMNS TO status_values
-- ============================================================
ALTER TABLE tms.status_values
    ADD COLUMN IF NOT EXISTS status_color     text DEFAULT '#9CA3AF',
    ADD COLUMN IF NOT EXISTS requires_reason  boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS requires_approval boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS description      text;

-- ============================================================
-- STATUS TRANSITIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.status_transitions (
    transition_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status_model_id     uuid NOT NULL REFERENCES tms.status_models(status_model_id) ON DELETE CASCADE,
    from_status_code    text,       -- null = any / initial creation
    to_status_code      text NOT NULL,
    transition_name     text NOT NULL,
    allowed_roles       jsonb NOT NULL DEFAULT '[]',
    requires_reason     boolean NOT NULL DEFAULT false,
    requires_approval   boolean NOT NULL DEFAULT false,
    trigger_workflow    boolean NOT NULL DEFAULT true,
    is_active           boolean NOT NULL DEFAULT true,
    sort_order          integer NOT NULL DEFAULT 100,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (status_model_id, from_status_code, to_status_code)
);

CREATE INDEX IF NOT EXISTS idx_status_transitions_model
    ON tms.status_transitions(status_model_id, from_status_code);

-- ============================================================
-- SEED: STATUS MODELS (one per entity type)
-- ============================================================
INSERT INTO tms.status_models (status_model_id, model_code, model_name, applies_to_entity, description) VALUES
  ('00000001-0001-0001-0001-000000000001', 'SHIPMENT',        'Shipment Status Model',        'SHIPMENT',        'Lifecycle statuses for shipments'),
  ('00000001-0001-0001-0001-000000000002', 'PURCHASE_ORDER',  'Purchase Order Status Model',  'PURCHASE_ORDER',  'Lifecycle statuses for purchase orders'),
  ('00000001-0001-0001-0001-000000000003', 'ORDER_RELEASE',   'Order Release Status Model',   'ORDER_RELEASE',   'Lifecycle statuses for order releases'),
  ('00000001-0001-0001-0001-000000000004', 'LOAD',            'Load Status Model',            'LOAD',            'Lifecycle statuses for loads'),
  ('00000001-0001-0001-0001-000000000005', 'STOP',            'Stop Status Model',            'STOP',            'Lifecycle statuses for shipment stops'),
  ('00000001-0001-0001-0001-000000000006', 'CARRIER_INVOICE', 'Carrier Invoice Status Model', 'CARRIER_INVOICE', 'Lifecycle statuses for carrier invoices'),
  ('00000001-0001-0001-0001-000000000007', 'CLIENT_BILL',     'Client Bill Status Model',     'CLIENT_BILL',     'Lifecycle statuses for client bills'),
  ('00000001-0001-0001-0001-000000000008', 'VOUCHER',         'Voucher Status Model',         'VOUCHER',         'Lifecycle statuses for payment vouchers'),
  ('00000001-0001-0001-0001-000000000009', 'DISPUTE',         'Dispute Status Model',         'DISPUTE',         'Lifecycle statuses for disputes'),
  ('00000001-0001-0001-0001-000000000010', 'PAYMENT',         'Payment Status Model',         'PAYMENT',         'Lifecycle statuses for payments')
ON CONFLICT (model_code) DO NOTHING;

-- ============================================================
-- SEED: STATUS VALUES
-- ============================================================

-- SHIPMENT
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000001', 'DRAFT',      'Draft',      10, true,  false, '#9CA3AF', 'Created, not yet planned'),
  ('00000001-0001-0001-0001-000000000001', 'PLANNED',    'Planned',    20, false, false, '#3B82F6', 'Carrier and route assigned'),
  ('00000001-0001-0001-0001-000000000001', 'TENDERED',   'Tendered',   30, false, false, '#F59E0B', 'Sent to carrier awaiting acceptance'),
  ('00000001-0001-0001-0001-000000000001', 'CONFIRMED',  'Confirmed',  40, false, false, '#6366F1', 'Carrier accepted'),
  ('00000001-0001-0001-0001-000000000001', 'IN_TRANSIT', 'In Transit', 50, false, false, '#F97316', 'Picked up and in motion'),
  ('00000001-0001-0001-0001-000000000001', 'DELIVERED',  'Delivered',  60, false, false, '#22C55E', 'Delivered to destination'),
  ('00000001-0001-0001-0001-000000000001', 'EXCEPTION',  'Exception',  70, false, false, '#EF4444', 'Active exception requiring attention'),
  ('00000001-0001-0001-0001-000000000001', 'CANCELLED',  'Cancelled',  80, false, true,  '#DC2626', 'Cancelled before execution'),
  ('00000001-0001-0001-0001-000000000001', 'CLOSED',     'Closed',     90, false, true,  '#6B7280', 'Closed after financials settled')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- PURCHASE ORDER
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000002', 'DRAFT',              'Draft',              10, true,  false, '#9CA3AF', 'Being created'),
  ('00000001-0001-0001-0001-000000000002', 'OPEN',               'Open',               20, false, false, '#3B82F6', 'Received and available for release'),
  ('00000001-0001-0001-0001-000000000002', 'ON_HOLD',            'On Hold',            30, false, false, '#F59E0B', 'Held, no releases allowed'),
  ('00000001-0001-0001-0001-000000000002', 'PARTIALLY_RELEASED', 'Partially Released', 40, false, false, '#6366F1', 'Some lines released'),
  ('00000001-0001-0001-0001-000000000002', 'FULLY_RELEASED',     'Fully Released',     50, false, false, '#8B5CF6', 'All lines released'),
  ('00000001-0001-0001-0001-000000000002', 'SHIPPED',            'Shipped',            60, false, false, '#F97316', 'All quantities shipped'),
  ('00000001-0001-0001-0001-000000000002', 'CLOSED',             'Closed',             70, false, true,  '#22C55E', 'All quantities accounted for'),
  ('00000001-0001-0001-0001-000000000002', 'CANCELLED',          'Cancelled',          80, false, true,  '#DC2626', 'PO cancelled')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- ORDER RELEASE
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000003', 'DRAFT',      'Draft',      10, true,  false, '#9CA3AF', 'Being built'),
  ('00000001-0001-0001-0001-000000000003', 'READY',      'Ready',      20, false, false, '#3B82F6', 'Ready for planning'),
  ('00000001-0001-0001-0001-000000000003', 'PLANNED',    'Planned',    30, false, false, '#6366F1', 'Assigned to a shipment'),
  ('00000001-0001-0001-0001-000000000003', 'TENDERED',   'Tendered',   40, false, false, '#F59E0B', 'Shipment tendered to carrier'),
  ('00000001-0001-0001-0001-000000000003', 'ACCEPTED',   'Accepted',   50, false, false, '#8B5CF6', 'Carrier accepted'),
  ('00000001-0001-0001-0001-000000000003', 'PICKED_UP',  'Picked Up',  60, false, false, '#F97316', 'Picked up by carrier'),
  ('00000001-0001-0001-0001-000000000003', 'IN_TRANSIT', 'In Transit', 70, false, false, '#FB923C', 'In motion'),
  ('00000001-0001-0001-0001-000000000003', 'DELIVERED',  'Delivered',  80, false, false, '#22C55E', 'Delivered'),
  ('00000001-0001-0001-0001-000000000003', 'COMPLETED',  'Completed',  90, false, true,  '#16A34A', 'Confirmed and closed'),
  ('00000001-0001-0001-0001-000000000003', 'CANCELLED',  'Cancelled', 100, false, true,  '#DC2626', 'Cancelled')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- LOAD
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000004', 'PLANNED',    'Planned',    10, true,  false, '#3B82F6', 'Load created'),
  ('00000001-0001-0001-0001-000000000004', 'TENDERED',   'Tendered',   20, false, false, '#F59E0B', 'Tendered to carrier'),
  ('00000001-0001-0001-0001-000000000004', 'ACCEPTED',   'Accepted',   30, false, false, '#6366F1', 'Carrier accepted'),
  ('00000001-0001-0001-0001-000000000004', 'DISPATCHED', 'Dispatched', 40, false, false, '#8B5CF6', 'Driver dispatched'),
  ('00000001-0001-0001-0001-000000000004', 'PICKED_UP',  'Picked Up',  50, false, false, '#F97316', 'First stop complete'),
  ('00000001-0001-0001-0001-000000000004', 'IN_TRANSIT', 'In Transit', 60, false, false, '#FB923C', 'Moving between stops'),
  ('00000001-0001-0001-0001-000000000004', 'DELIVERED',  'Delivered',  70, false, false, '#22C55E', 'All stops completed'),
  ('00000001-0001-0001-0001-000000000004', 'COMPLETED',  'Completed',  80, false, true,  '#16A34A', 'Closed out'),
  ('00000001-0001-0001-0001-000000000004', 'CANCELLED',  'Cancelled',  90, false, true,  '#DC2626', 'Cancelled')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- STOP
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000005', 'SCHEDULED',   'Scheduled',   10, true,  false, '#3B82F6', 'Appointment scheduled'),
  ('00000001-0001-0001-0001-000000000005', 'CONFIRMED',   'Confirmed',   20, false, false, '#6366F1', 'Appointment confirmed'),
  ('00000001-0001-0001-0001-000000000005', 'ARRIVED',     'Arrived',     30, false, false, '#F59E0B', 'Driver checked in'),
  ('00000001-0001-0001-0001-000000000005', 'IN_PROGRESS', 'In Progress', 40, false, false, '#F97316', 'Loading/unloading underway'),
  ('00000001-0001-0001-0001-000000000005', 'COMPLETED',   'Completed',   50, false, true,  '#22C55E', 'Stop complete'),
  ('00000001-0001-0001-0001-000000000005', 'MISSED',      'Missed',      60, false, true,  '#EF4444', 'Driver did not arrive'),
  ('00000001-0001-0001-0001-000000000005', 'CANCELLED',   'Cancelled',   70, false, true,  '#DC2626', 'Cancelled')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- CARRIER INVOICE
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000006', 'RECEIVED',  'Received',  10, true,  false, '#9CA3AF', 'Invoice received'),
  ('00000001-0001-0001-0001-000000000006', 'MATCHED',   'Matched',   20, false, false, '#3B82F6', 'Matched to shipment'),
  ('00000001-0001-0001-0001-000000000006', 'EXCEPTION', 'Exception', 30, false, false, '#EF4444', 'Variance found'),
  ('00000001-0001-0001-0001-000000000006', 'DISPUTED',  'Disputed',  40, false, false, '#DC2626', 'Formally disputed'),
  ('00000001-0001-0001-0001-000000000006', 'APPROVED',  'Approved',  50, false, false, '#22C55E', 'Approved for payment'),
  ('00000001-0001-0001-0001-000000000006', 'EXPORTED',  'Exported',  60, false, false, '#6366F1', 'Sent to AP'),
  ('00000001-0001-0001-0001-000000000006', 'PAID',      'Paid',      70, false, true,  '#16A34A', 'Payment confirmed'),
  ('00000001-0001-0001-0001-000000000006', 'CANCELLED', 'Cancelled', 80, false, true,  '#6B7280', 'Voided')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- CLIENT BILL
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000007', 'DRAFT',          'Draft',          10, true,  false, '#9CA3AF', 'Being prepared'),
  ('00000001-0001-0001-0001-000000000007', 'PENDING_REVIEW', 'Pending Review', 20, false, false, '#F59E0B', 'Ready for review'),
  ('00000001-0001-0001-0001-000000000007', 'APPROVED',       'Approved',       30, false, false, '#6366F1', 'Approved to send'),
  ('00000001-0001-0001-0001-000000000007', 'SENT',           'Sent',           40, false, false, '#3B82F6', 'Delivered to customer'),
  ('00000001-0001-0001-0001-000000000007', 'DISPUTED',       'Disputed',       50, false, false, '#EF4444', 'Customer disputed'),
  ('00000001-0001-0001-0001-000000000007', 'PARTIALLY_PAID', 'Partially Paid', 60, false, false, '#F97316', 'Partial payment received'),
  ('00000001-0001-0001-0001-000000000007', 'PAID',           'Paid',           70, false, true,  '#22C55E', 'Paid in full'),
  ('00000001-0001-0001-0001-000000000007', 'CANCELLED',      'Cancelled',      80, false, true,  '#DC2626', 'Cancelled'),
  ('00000001-0001-0001-0001-000000000007', 'CLOSED',         'Closed',         90, false, true,  '#6B7280', 'Closed')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- VOUCHER
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000008', 'DRAFT',     'Draft',     10, true,  false, '#9CA3AF', 'Being created'),
  ('00000001-0001-0001-0001-000000000008', 'APPROVED',  'Approved',  20, false, false, '#22C55E', 'Approved for payment run'),
  ('00000001-0001-0001-0001-000000000008', 'SCHEDULED', 'Scheduled', 30, false, false, '#3B82F6', 'Payment scheduled'),
  ('00000001-0001-0001-0001-000000000008', 'PAID',      'Paid',      40, false, true,  '#16A34A', 'Payment disbursed'),
  ('00000001-0001-0001-0001-000000000008', 'VOID',      'Void',      50, false, true,  '#DC2626', 'Voided')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- DISPUTE
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000009', 'OPEN',      'Open',      10, true,  false, '#EF4444', 'Dispute filed'),
  ('00000001-0001-0001-0001-000000000009', 'IN_REVIEW', 'In Review', 20, false, false, '#F59E0B', 'Under review'),
  ('00000001-0001-0001-0001-000000000009', 'ESCALATED', 'Escalated', 30, false, false, '#DC2626', 'Escalated to management'),
  ('00000001-0001-0001-0001-000000000009', 'RESOLVED',  'Resolved',  40, false, true,  '#22C55E', 'Resolved'),
  ('00000001-0001-0001-0001-000000000009', 'CLOSED',    'Closed',    50, false, true,  '#6B7280', 'Closed')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- PAYMENT
INSERT INTO tms.status_values (status_model_id, status_code, status_name, sort_order, is_initial, is_terminal, status_color, description) VALUES
  ('00000001-0001-0001-0001-000000000010', 'PENDING',    'Pending',    10, true,  false, '#9CA3AF', 'Initiated, not processed'),
  ('00000001-0001-0001-0001-000000000010', 'ON_HOLD',    'On Hold',    20, false, false, '#F59E0B', 'On hold pending review'),
  ('00000001-0001-0001-0001-000000000010', 'PROCESSING', 'Processing', 30, false, false, '#3B82F6', 'Sent to bank'),
  ('00000001-0001-0001-0001-000000000010', 'COMPLETED',  'Completed',  40, false, true,  '#22C55E', 'Successfully processed'),
  ('00000001-0001-0001-0001-000000000010', 'FAILED',     'Failed',     50, false, false, '#EF4444', 'Failed — retry required'),
  ('00000001-0001-0001-0001-000000000010', 'REVERSED',   'Reversed',   60, false, true,  '#DC2626', 'Reversed or returned')
ON CONFLICT (status_model_id, status_code) DO NOTHING;

-- ============================================================
-- SEED: STATUS TRANSITIONS
-- ============================================================

-- SHIPMENT transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000001', NULL,         'DRAFT',      'Create Shipment',     '["PLANNER","ADMIN"]',              false),
  ('00000001-0001-0001-0001-000000000001', 'DRAFT',      'PLANNED',    'Plan Shipment',       '["PLANNER","ADMIN"]',              true),
  ('00000001-0001-0001-0001-000000000001', 'PLANNED',    'TENDERED',   'Tender to Carrier',   '["PLANNER","DISPATCHER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000001', 'TENDERED',   'CONFIRMED',  'Confirm Acceptance',  '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000001', 'CONFIRMED',  'IN_TRANSIT', 'Mark Picked Up',      '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000001', 'IN_TRANSIT', 'DELIVERED',  'Mark Delivered',      '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000001', 'IN_TRANSIT', 'EXCEPTION',  'Raise Exception',     '["DISPATCHER","PLANNER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000001', 'EXCEPTION',  'IN_TRANSIT', 'Resolve Exception',   '["PLANNER","ADMIN"]',              true),
  ('00000001-0001-0001-0001-000000000001', 'DELIVERED',  'CLOSED',     'Close Shipment',      '["FINANCE","ADMIN"]',              false),
  ('00000001-0001-0001-0001-000000000001', 'PLANNED',    'CANCELLED',  'Cancel Shipment',     '["PLANNER","ADMIN"]',              true),
  ('00000001-0001-0001-0001-000000000001', 'DRAFT',      'CANCELLED',  'Cancel Draft',        '["PLANNER","ADMIN"]',              false)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- PURCHASE ORDER transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000002', NULL,                'DRAFT',              'Create PO',          '["BUYER","ADMIN"]',            false),
  ('00000001-0001-0001-0001-000000000002', 'DRAFT',             'OPEN',               'Submit PO',          '["BUYER","ADMIN"]',            true),
  ('00000001-0001-0001-0001-000000000002', 'OPEN',              'ON_HOLD',            'Place on Hold',      '["BUYER","PLANNER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000002', 'ON_HOLD',           'OPEN',               'Release Hold',       '["BUYER","ADMIN"]',            true),
  ('00000001-0001-0001-0001-000000000002', 'OPEN',              'PARTIALLY_RELEASED', 'Partial Release',    '["PLANNER","ADMIN"]',          true),
  ('00000001-0001-0001-0001-000000000002', 'PARTIALLY_RELEASED','FULLY_RELEASED',     'Full Release',       '["PLANNER","ADMIN"]',          true),
  ('00000001-0001-0001-0001-000000000002', 'FULLY_RELEASED',    'SHIPPED',            'Mark Shipped',       '["PLANNER","ADMIN"]',          true),
  ('00000001-0001-0001-0001-000000000002', 'SHIPPED',           'CLOSED',             'Close PO',           '["BUYER","FINANCE","ADMIN"]',  false),
  ('00000001-0001-0001-0001-000000000002', 'OPEN',              'CANCELLED',          'Cancel PO',          '["BUYER","ADMIN"]',            true)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- ORDER RELEASE transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000003', NULL,        'DRAFT',      'Create Release',     '["PLANNER","ADMIN"]',              false),
  ('00000001-0001-0001-0001-000000000003', 'DRAFT',     'READY',      'Mark Ready',         '["PLANNER","ADMIN"]',              true),
  ('00000001-0001-0001-0001-000000000003', 'READY',     'PLANNED',    'Assign to Shipment', '["PLANNER","ADMIN"]',              true),
  ('00000001-0001-0001-0001-000000000003', 'PLANNED',   'TENDERED',   'Tender',             '["PLANNER","DISPATCHER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000003', 'TENDERED',  'ACCEPTED',   'Accept',             '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000003', 'ACCEPTED',  'PICKED_UP',  'Confirm Pickup',     '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000003', 'PICKED_UP', 'IN_TRANSIT', 'In Transit',         '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000003', 'IN_TRANSIT','DELIVERED',  'Confirm Delivery',   '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000003', 'DELIVERED', 'COMPLETED',  'Complete',           '["PLANNER","FINANCE","ADMIN"]',    false),
  ('00000001-0001-0001-0001-000000000003', 'READY',     'CANCELLED',  'Cancel',             '["PLANNER","ADMIN"]',              true)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- CARRIER INVOICE transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000006', NULL,        'RECEIVED',  'Receive Invoice',      '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000006', 'RECEIVED',  'MATCHED',   'Match to Shipment',    '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000006', 'RECEIVED',  'EXCEPTION', 'Flag Exception',       '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000006', 'MATCHED',   'EXCEPTION', 'Flag Exception',       '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000006', 'EXCEPTION', 'DISPUTED',  'Raise Dispute',        '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000006', 'MATCHED',   'APPROVED',  'Approve',              '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000006', 'EXCEPTION', 'APPROVED',  'Override Approve',     '["FINANCE","MANAGER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000006', 'DISPUTED',  'APPROVED',  'Approve After Dispute','["FINANCE","MANAGER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000006', 'APPROVED',  'EXPORTED',  'Export to AP',         '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000006', 'EXPORTED',  'PAID',      'Confirm Payment',      '["FINANCE","ADMIN"]',           false)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- CLIENT BILL transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000007', NULL,            'DRAFT',          'Create Bill',       '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000007', 'DRAFT',         'PENDING_REVIEW', 'Submit for Review', '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000007', 'PENDING_REVIEW','APPROVED',       'Approve Bill',      '["FINANCE","MANAGER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000007', 'APPROVED',      'SENT',           'Send to Customer',  '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000007', 'SENT',          'DISPUTED',       'Customer Disputes', '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000007', 'SENT',          'PAID',           'Full Payment',      '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000007', 'PAID',          'CLOSED',         'Close Bill',        '["FINANCE","ADMIN"]',           false)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- VOUCHER transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000008', NULL,       'DRAFT',     'Create Voucher',   '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000008', 'DRAFT',    'APPROVED',  'Approve Voucher',  '["FINANCE","MANAGER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000008', 'APPROVED', 'SCHEDULED', 'Schedule Payment', '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000008', 'SCHEDULED','PAID',      'Confirm Payment',  '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000008', 'APPROVED', 'VOID',      'Void Voucher',     '["FINANCE","ADMIN"]',           false)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- DISPUTE transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000009', NULL,       'OPEN',      'Open Dispute',      '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000009', 'OPEN',     'IN_REVIEW', 'Start Review',      '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000009', 'IN_REVIEW','ESCALATED', 'Escalate',          '["FINANCE","MANAGER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000009', 'IN_REVIEW','RESOLVED',  'Resolve',           '["FINANCE","MANAGER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000009', 'RESOLVED', 'CLOSED',    'Close Dispute',     '["FINANCE","ADMIN"]',           false)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- PAYMENT transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000010', NULL,         'PENDING',    'Initiate Payment', '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000010', 'PENDING',    'ON_HOLD',    'Place on Hold',    '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000010', 'ON_HOLD',    'PENDING',    'Release Hold',     '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000010', 'PENDING',    'PROCESSING', 'Send to Bank',     '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000010', 'PROCESSING', 'COMPLETED',  'Confirm Payment',  '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000010', 'PROCESSING', 'FAILED',     'Mark Failed',      '["FINANCE","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000010', 'FAILED',     'PENDING',    'Retry Payment',    '["FINANCE","ADMIN"]',           false),
  ('00000001-0001-0001-0001-000000000010', 'COMPLETED',  'REVERSED',   'Reverse Payment',  '["FINANCE","MANAGER","ADMIN"]', true)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- LOAD transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000004', NULL,        'PLANNED',    'Create Load',      '["PLANNER","ADMIN"]',              false),
  ('00000001-0001-0001-0001-000000000004', 'PLANNED',   'TENDERED',   'Tender Load',      '["PLANNER","DISPATCHER","ADMIN"]', true),
  ('00000001-0001-0001-0001-000000000004', 'TENDERED',  'ACCEPTED',   'Accept',           '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000004', 'ACCEPTED',  'DISPATCHED', 'Dispatch Driver',  '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000004', 'DISPATCHED','PICKED_UP',  'Confirm Pickup',   '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000004', 'PICKED_UP', 'IN_TRANSIT', 'Depart Stop',      '["DISPATCHER","DRIVER","ADMIN"]',  false),
  ('00000001-0001-0001-0001-000000000004', 'IN_TRANSIT','DELIVERED',  'Complete Delivery','["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000004', 'DELIVERED', 'COMPLETED',  'Close Load',       '["PLANNER","FINANCE","ADMIN"]',    false),
  ('00000001-0001-0001-0001-000000000004', 'PLANNED',   'CANCELLED',  'Cancel Load',      '["PLANNER","ADMIN"]',              true)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

-- STOP transitions
INSERT INTO tms.status_transitions (status_model_id, from_status_code, to_status_code, transition_name, allowed_roles, trigger_workflow) VALUES
  ('00000001-0001-0001-0001-000000000005', NULL,          'SCHEDULED',   'Schedule Stop',    '["PLANNER","DISPATCHER","ADMIN"]', false),
  ('00000001-0001-0001-0001-000000000005', 'SCHEDULED',   'CONFIRMED',   'Confirm Appt',     '["PLANNER","DISPATCHER","ADMIN"]', false),
  ('00000001-0001-0001-0001-000000000005', 'CONFIRMED',   'ARRIVED',     'Driver Check-in',  '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000005', 'ARRIVED',     'IN_PROGRESS', 'Start Activities', '["DISPATCHER","DRIVER","ADMIN"]',  false),
  ('00000001-0001-0001-0001-000000000005', 'IN_PROGRESS', 'COMPLETED',   'Complete Stop',    '["DISPATCHER","DRIVER","ADMIN"]',  true),
  ('00000001-0001-0001-0001-000000000005', 'SCHEDULED',   'MISSED',      'Mark Missed',      '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000005', 'CONFIRMED',   'MISSED',      'Mark Missed',      '["DISPATCHER","ADMIN"]',           true),
  ('00000001-0001-0001-0001-000000000005', 'SCHEDULED',   'CANCELLED',   'Cancel Stop',      '["PLANNER","ADMIN"]',              false)
ON CONFLICT (status_model_id, from_status_code, to_status_code) DO NOTHING;

COMMIT;
