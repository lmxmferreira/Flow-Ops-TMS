-- ============================================================
-- Migration: 029_int_rpt_sec_wf_ux.sql
-- TMS-INT, RPT, SEC, WF, UX
-- ============================================================
BEGIN;

-- ── INT-010/012/013/014/015: Integration framework ────────────────
CREATE TABLE IF NOT EXISTS tms.integration_transactions (
    transaction_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_number  TEXT NOT NULL,
    direction           TEXT NOT NULL DEFAULT 'inbound',
    -- inbound | outbound
    integration_type    TEXT NOT NULL,
    -- erp_po | erp_ap | erp_ar | wms | carrier_edi | carrier_api
    -- | visibility | tax | telematics | payment | parcel | custom
    source_system       TEXT,
    target_system       TEXT,
    message_type        TEXT,
    -- 204|990|214|210|211|212|856|810|850|api_webhook|flat_file|api_rest
    entity_type         TEXT,
    -- purchase_order|shipment|invoice|payment|bill|accrual|tracking
    entity_id           UUID,
    status              TEXT NOT NULL DEFAULT 'received',
    -- received|processing|completed|failed|retrying|rejected|duplicate
    payload_inbound     JSONB,
    payload_outbound    JSONB,
    error_message       TEXT,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    last_retry_at       TIMESTAMPTZ,
    acknowledged        BOOLEAN NOT NULL DEFAULT FALSE,
    ack_at              TIMESTAMPTZ,
    processed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_it_status  ON tms.integration_transactions(status, direction);
CREATE INDEX IF NOT EXISTS idx_it_entity  ON tms.integration_transactions(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_it_type    ON tms.integration_transactions(integration_type, created_at DESC);

-- ── INT-013: Data mappings/cross-references ────────────────────────
CREATE TABLE IF NOT EXISTS tms.integration_mappings (
    mapping_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_name    TEXT NOT NULL,
    integration_type TEXT NOT NULL,
    source_field    TEXT NOT NULL,
    source_value    TEXT NOT NULL,
    target_field    TEXT NOT NULL,
    target_value    TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_im_lookup ON tms.integration_mappings(integration_type, source_field, source_value);

-- ── RPT-009: Saved report configs ─────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.report_configs (
    config_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_name     TEXT NOT NULL,
    report_type     TEXT NOT NULL,
    -- operational|po|shipment|carrier_performance|stop|financial
    -- |allocation|reconciliation|export|drilldown
    parameters      JSONB NOT NULL DEFAULT '{}',
    is_scheduled    BOOLEAN NOT NULL DEFAULT FALSE,
    schedule_cron   TEXT,
    output_format   TEXT NOT NULL DEFAULT 'json',
    -- json|csv|xlsx|pdf|api
    created_by      TEXT,
    is_shared       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rc_type ON tms.report_configs(report_type, created_by);

-- ── SEC-001/002/003/004: Role & permission config ─────────────────
CREATE TABLE IF NOT EXISTS tms.user_roles (
    role_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_code       TEXT NOT NULL UNIQUE,
    role_name       TEXT NOT NULL,
    role_type       TEXT NOT NULL DEFAULT 'internal',
    -- internal|carrier|supplier|customer|auditor|admin|provider
    permissions     JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO tms.user_roles (role_code, role_name, role_type, permissions) VALUES
    ('PLANNER',       'Transportation Planner',   'internal', '{"shipments":["read","write"],"orders":["read","write"],"rates":["read"]}'),
    ('DISPATCHER',    'Dispatcher',               'internal', '{"shipments":["read","write"],"tenders":["read","write"],"tracking":["write"]}'),
    ('CARRIER_MGR',   'Carrier Manager',          'internal', '{"carriers":["read","write"],"tenders":["read","write"],"scorecards":["read","write"]}'),
    ('FINANCE',       'Finance User',             'internal', '{"invoices":["read","write","approve"],"billing":["read","write","approve"],"payments":["approve"]}'),
    ('AUDITOR',       'Auditor',                  'auditor',  '{"audit_trail":["read"],"reports":["read"],"all_records":["read"]}'),
    ('CARRIER',       'Carrier Portal User',      'carrier',  '{"tenders":["read","respond"],"tracking":["write"],"invoices":["read","write"]}'),
    ('CUSTOMER',      'Customer Portal User',     'customer', '{"shipments":["read"],"bills":["read","dispute"],"tracking":["read"]}'),
    ('SUPPLIER',      'Supplier Portal User',     'supplier', '{"orders":["read"],"shipments":["read"],"appointments":["read","write"]}'),
    ('ADMIN',         'System Administrator',     'admin',    '{"all":["read","write","admin"]}')
ON CONFLICT DO NOTHING;

-- ── SEC-007/008: Immutable audit trail ────────────────────────────
CREATE TABLE IF NOT EXISTS tms.security_audit_log (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    -- create|update|delete|approve|override|login|logout|export|view_sensitive
    entity_type     TEXT,
    entity_id       UUID,
    old_value       JSONB,
    new_value       JSONB,
    source_system   TEXT NOT NULL DEFAULT 'tms_web',
    transaction_type TEXT,
    reason_code     TEXT,
    comments        TEXT,
    ip_address      TEXT,
    session_id      TEXT,
    performed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sal_user   ON tms.security_audit_log(user_id, performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sal_entity ON tms.security_audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_sal_action ON tms.security_audit_log(action_type, performed_at DESC);

-- ── SEC-010: Data retention policies ─────────────────────────────
CREATE TABLE IF NOT EXISTS tms.data_retention_policies (
    policy_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name     TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    retention_days  INTEGER NOT NULL,
    archive_after_days INTEGER,
    legal_hold      BOOLEAN NOT NULL DEFAULT FALSE,
    purge_allowed   BOOLEAN NOT NULL DEFAULT FALSE,
    country_code    TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO tms.data_retention_policies (policy_name, entity_type, retention_days, archive_after_days, purge_allowed)
VALUES
    ('Shipment Records 7yr',  'shipment',        2555, 365, FALSE),
    ('Invoice Records 7yr',   'carrier_invoice', 2555, 365, FALSE),
    ('Audit Log 10yr',        'audit_log',       3650,   0, FALSE),
    ('Integration Log 2yr',   'integration',      730, 180, TRUE),
    ('Documents 7yr',         'document',        2555, 365, FALSE)
ON CONFLICT DO NOTHING;

-- ── WF-001/002/003/004/005/006: Workflow engine ───────────────────
CREATE TABLE IF NOT EXISTS tms.workflow_definitions (
    workflow_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_code   TEXT NOT NULL UNIQUE,
    workflow_name   TEXT NOT NULL,
    workflow_type   TEXT NOT NULL,
    -- approval|notification|automation|escalation
    trigger_entity  TEXT NOT NULL,
    trigger_event   TEXT NOT NULL,
    steps           JSONB NOT NULL DEFAULT '[]',
    -- [{step:1,approver_role,amount_min,amount_max,parallel,timeout_hrs}]
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    version         INTEGER NOT NULL DEFAULT 1,
    effective_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO tms.workflow_definitions (workflow_code, workflow_name, workflow_type, trigger_entity, trigger_event, steps)
VALUES
    ('RATE_OVERRIDE_APPROVAL', 'Rate Override Approval', 'approval', 'shipment_cost', 'rate_override',
     '[{"step":1,"role":"CARRIER_MGR","timeout_hrs":4},{"step":2,"role":"FINANCE","amount_min":1000,"timeout_hrs":8}]'),
    ('INVOICE_EXCEPTION_APPROVAL', 'Invoice Exception Approval', 'approval', 'carrier_invoice', 'exception',
     '[{"step":1,"role":"FINANCE","timeout_hrs":24},{"step":2,"role":"ADMIN","escalation":true,"timeout_hrs":48}]'),
    ('BILLING_ADJUSTMENT_APPROVAL', 'Billing Adjustment Approval', 'approval', 'client_bill', 'adjustment',
     '[{"step":1,"role":"FINANCE","timeout_hrs":8}]'),
    ('PAYMENT_RELEASE_APPROVAL', 'Payment Release Approval', 'approval', 'voucher', 'payment_release',
     '[{"step":1,"role":"FINANCE","timeout_hrs":24},{"step":2,"role":"ADMIN","amount_min":10000,"timeout_hrs":4}]')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS tms.workflow_instances (
    instance_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL REFERENCES tms.workflow_definitions(workflow_id),
    entity_type     TEXT NOT NULL,
    entity_id       UUID NOT NULL,
    current_step    INTEGER NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'pending',
    -- pending|in_progress|approved|rejected|escalated|expired|withdrawn
    requested_by    TEXT NOT NULL,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    amount          NUMERIC(14,4),
    notes           TEXT,
    step_history    JSONB NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_wi_entity  ON tms.workflow_instances(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_wi_status  ON tms.workflow_instances(status);
CREATE INDEX IF NOT EXISTS idx_wi_pending ON tms.workflow_instances(status, current_step) WHERE status = 'in_progress';

-- ── UX-008: User preferences ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS tms.user_preferences (
    pref_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL UNIQUE,
    language        TEXT NOT NULL DEFAULT 'en',
    timezone        TEXT NOT NULL DEFAULT 'UTC',
    date_format     TEXT NOT NULL DEFAULT 'YYYY-MM-DD',
    number_format   TEXT NOT NULL DEFAULT '1,234.56',
    default_views   JSONB NOT NULL DEFAULT '{}',
    dashboard_layout JSONB NOT NULL DEFAULT '{}',
    notification_settings JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
