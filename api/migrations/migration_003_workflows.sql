-- ============================================================
-- Flow Ops TMS — Migration 003: Workflow & Notification Engine
-- Run: PGPASSWORD=oms_dev_password psql -h localhost -p 5433 -U oms_user -d flow_ops_tms -f migration_003_workflows.sql
-- ============================================================

BEGIN;
SET search_path = tms;

-- ============================================================
-- WORKFLOW RULES
-- One rule = one trigger condition + one or more actions
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.workflow_rules (
    rule_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code           text NOT NULL UNIQUE,
    rule_name           text NOT NULL,
    rule_description    text,
    -- Trigger
    trigger_entity      text NOT NULL, -- SHIPMENT | PURCHASE_ORDER | ORDER_RELEASE | CARRIER_INVOICE
    trigger_event       text NOT NULL, -- STATUS_CHANGE | CREATED | UPDATED | OVERDUE
    trigger_status_from text,          -- status code before (null = any)
    trigger_status_to   text,          -- status code after (null = any)
    -- Scope filters (all optional — null means "any")
    filter_business_unit_id uuid REFERENCES tms.business_units(business_unit_id),
    filter_customer_party_id uuid REFERENCES tms.parties(party_id),
    filter_supplier_party_id uuid REFERENCES tms.parties(party_id),
    filter_carrier_id        uuid REFERENCES tms.carriers(carrier_id),
    filter_transport_mode_id uuid REFERENCES tms.transport_modes(transport_mode_id),
    filter_country           text,
    filter_shipment_type     text,
    filter_priority          text,
    -- Conditions (JSON for extensibility)
    conditions          jsonb NOT NULL DEFAULT '{}', -- e.g. {"min_weight": 10000, "min_value": 50000}
    -- Action
    action_type         text NOT NULL DEFAULT 'NOTIFY', -- NOTIFY | EMAIL | WEBHOOK
    action_recipients   jsonb NOT NULL DEFAULT '[]',    -- ["role:PLANNER", "user:uuid", "email:x@y.com"]
    notification_template text,
    -- Meta
    status              text NOT NULL DEFAULT 'ACTIVE', -- ACTIVE | INACTIVE
    priority_order      integer NOT NULL DEFAULT 100,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- WORKFLOW NOTIFICATIONS (execution log)
-- ============================================================
CREATE TABLE IF NOT EXISTS tms.workflow_notifications (
    notification_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id             uuid NOT NULL REFERENCES tms.workflow_rules(rule_id),
    -- What triggered it
    entity_type         text NOT NULL,
    entity_id           uuid NOT NULL,
    entity_number       text,          -- human-readable reference
    trigger_event       text NOT NULL,
    trigger_status_from text,
    trigger_status_to   text,
    -- Notification content
    title               text NOT NULL,
    message             text NOT NULL,
    -- Recipients & status
    recipient_user_id   uuid,          -- null = broadcast/role-based
    recipient_role      text,
    recipient_email     text,
    is_read             boolean NOT NULL DEFAULT false,
    read_at             timestamptz,
    -- Delivery
    delivery_status     text NOT NULL DEFAULT 'PENDING', -- PENDING | SENT | FAILED
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workflow_rules_trigger
    ON tms.workflow_rules(trigger_entity, trigger_event, status);
CREATE INDEX IF NOT EXISTS idx_workflow_notifications_entity
    ON tms.workflow_notifications(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_workflow_notifications_unread
    ON tms.workflow_notifications(is_read, created_at DESC)
    WHERE is_read = false;
CREATE INDEX IF NOT EXISTS idx_workflow_notifications_user
    ON tms.workflow_notifications(recipient_user_id, is_read, created_at DESC);

-- Updated_at trigger
CREATE TRIGGER trg_workflow_rules_touch_updated_at
    BEFORE UPDATE ON tms.workflow_rules
    FOR EACH ROW EXECUTE FUNCTION tms.touch_updated_at();

-- ============================================================
-- SEED: DEFAULT WORKFLOW RULES
-- ============================================================
INSERT INTO tms.workflow_rules (rule_id, rule_code, rule_name, rule_description,
    trigger_entity, trigger_event, trigger_status_from, trigger_status_to,
    action_type, action_recipients, notification_template, priority_order)
VALUES
  -- Shipment status changes
  (gen_random_uuid(), 'SHP-PICKUP',    'Shipment Picked Up',
   'Notify when a shipment transitions to In Transit',
   'SHIPMENT', 'STATUS_CHANGE', 'PLANNED', 'IN_TRANSIT',
   'NOTIFY', '["role:PLANNER","role:CUSTOMER_SERVICE"]',
   'Shipment {{entity_number}} has been picked up and is now in transit.',
   10),

  (gen_random_uuid(), 'SHP-DELIVERED', 'Shipment Delivered',
   'Notify when a shipment is delivered',
   'SHIPMENT', 'STATUS_CHANGE', 'IN_TRANSIT', 'DELIVERED',
   'NOTIFY', '["role:PLANNER","role:CUSTOMER_SERVICE","role:FINANCE"]',
   'Shipment {{entity_number}} has been delivered successfully.',
   10),

  (gen_random_uuid(), 'SHP-EXCEPTION', 'Shipment Exception',
   'Notify immediately when a shipment enters Exception status',
   'SHIPMENT', 'STATUS_CHANGE', NULL, 'EXCEPTION',
   'NOTIFY', '["role:PLANNER","role:CUSTOMER_SERVICE","role:MANAGER"]',
   'URGENT: Shipment {{entity_number}} has entered exception status. Immediate action required.',
   1),

  (gen_random_uuid(), 'SHP-CANCELLED', 'Shipment Cancelled',
   'Notify when a shipment is cancelled',
   'SHIPMENT', 'STATUS_CHANGE', NULL, 'CANCELLED',
   'NOTIFY', '["role:PLANNER","role:FINANCE"]',
   'Shipment {{entity_number}} has been cancelled.',
   20),

  (gen_random_uuid(), 'SHP-CREATED',   'New Shipment Created',
   'Notify planners when a new shipment is created',
   'SHIPMENT', 'CREATED', NULL, NULL,
   'NOTIFY', '["role:PLANNER"]',
   'New shipment {{entity_number}} has been created and is ready for planning.',
   50),

  -- Purchase Order events
  (gen_random_uuid(), 'PO-HOLD',       'PO Placed on Hold',
   'Notify when a PO is placed on hold',
   'PURCHASE_ORDER', 'STATUS_CHANGE', NULL, 'ON_HOLD',
   'NOTIFY', '["role:PLANNER","role:BUYER"]',
   'Purchase Order {{entity_number}} has been placed on hold.',
   10),

  (gen_random_uuid(), 'PO-RELEASED',   'PO Fully Released',
   'Notify when a PO is fully released to transport',
   'PURCHASE_ORDER', 'STATUS_CHANGE', NULL, 'FULLY_RELEASED',
   'NOTIFY', '["role:PLANNER"]',
   'Purchase Order {{entity_number}} is fully released and ready for shipment planning.',
   20),

  (gen_random_uuid(), 'PO-CREATED',    'New PO Received',
   'Notify when a new purchase order is created',
   'PURCHASE_ORDER', 'CREATED', NULL, NULL,
   'NOTIFY', '["role:PLANNER","role:BUYER"]',
   'New Purchase Order {{entity_number}} has been received.',
   50),

  -- Order Release events
  (gen_random_uuid(), 'REL-READY',     'Release Ready to Plan',
   'Notify planners when an order release is ready',
   'ORDER_RELEASE', 'STATUS_CHANGE', NULL, 'READY',
   'NOTIFY', '["role:PLANNER"]',
   'Order Release {{entity_number}} is ready for transportation planning.',
   10),

  (gen_random_uuid(), 'REL-DELIVERED', 'Release Delivered',
   'Notify when an order release is delivered',
   'ORDER_RELEASE', 'STATUS_CHANGE', NULL, 'DELIVERED',
   'NOTIFY', '["role:CUSTOMER_SERVICE","role:FINANCE"]',
   'Order Release {{entity_number}} has been delivered.',
   20),

  -- Carrier Invoice events
  (gen_random_uuid(), 'INV-DISPUTED',  'Invoice Disputed',
   'Notify finance when a carrier invoice is disputed',
   'CARRIER_INVOICE', 'STATUS_CHANGE', NULL, 'DISPUTED',
   'NOTIFY', '["role:FINANCE","role:MANAGER"]',
   'Carrier Invoice {{entity_number}} has been disputed and requires review.',
   10),

  (gen_random_uuid(), 'INV-APPROVED',  'Invoice Approved',
   'Notify finance when a carrier invoice is approved for payment',
   'CARRIER_INVOICE', 'STATUS_CHANGE', NULL, 'APPROVED',
   'NOTIFY', '["role:FINANCE"]',
   'Carrier Invoice {{entity_number}} has been approved and is ready for payment.',
   20)

ON CONFLICT DO NOTHING;

COMMIT;
