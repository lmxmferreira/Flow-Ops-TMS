-- Migration: 030_nfr_ac.sql
-- TMS-NFR + TMS-AC: Non-Functional Requirements & Acceptance Criteria
BEGIN;

-- NFR-004/005/010: System health monitoring
CREATE TABLE IF NOT EXISTS tms.system_health_checks (
    check_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_name      TEXT NOT NULL,
    check_type      TEXT NOT NULL,
    -- database|api|integration|batch|queue|service
    status          TEXT NOT NULL DEFAULT 'unknown',
    -- healthy|degraded|unhealthy|unknown
    response_ms     INTEGER,
    message         TEXT,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NFR-005: Batch job monitoring
CREATE TABLE IF NOT EXISTS tms.batch_job_log (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name        TEXT NOT NULL,
    job_type        TEXT NOT NULL,
    -- rating|allocation|audit|billing|integration|archive|report
    status          TEXT NOT NULL DEFAULT 'running',
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_failed    INTEGER NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_by      TEXT
);
CREATE INDEX IF NOT EXISTS idx_bjl_name   ON tms.batch_job_log(job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_bjl_status ON tms.batch_job_log(status);

-- NFR-009: External reconciliation configs
CREATE TABLE IF NOT EXISTS tms.reconciliation_configs (
    config_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_name     TEXT NOT NULL,
    -- erp|wms|oms|carrier|payment|accounting|customer
    entity_type     TEXT NOT NULL,
    match_fields    TEXT[] NOT NULL DEFAULT ARRAY['reference_number'],
    tolerance_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO tms.reconciliation_configs (system_name, entity_type, match_fields) VALUES
    ('ERP',     'purchase_order',   ARRAY['po_number','po_total']),
    ('ERP',     'carrier_invoice',  ARRAY['invoice_number','invoice_amount']),
    ('WMS',     'shipment',         ARRAY['shipment_number','quantity']),
    ('CARRIER', 'tracking',         ARRAY['shipment_number','milestone'])
ON CONFLICT DO NOTHING;

COMMIT;
