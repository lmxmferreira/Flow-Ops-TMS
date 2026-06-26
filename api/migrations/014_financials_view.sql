-- ============================================================
-- Migration: 014_financials_view.sql
-- TMS-RATE-013: Shipment financial summary view
-- ============================================================

BEGIN;

-- Add approved financial tracking to shipment_costs
ALTER TABLE tms.shipment_costs
    ADD COLUMN IF NOT EXISTS is_estimated     BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS approved_amount  NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS approved_by      TEXT,
    ADD COLUMN IF NOT EXISTS approved_at      TIMESTAMPTZ;

-- Add estimated flag to client_charges
ALTER TABLE tms.client_charges
    ADD COLUMN IF NOT EXISTS is_estimated     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS approved_amount  NUMERIC(14,4),
    ADD COLUMN IF NOT EXISTS approved_by      TEXT,
    ADD COLUMN IF NOT EXISTS approved_at      TIMESTAMPTZ;

-- Financial summary view
CREATE OR REPLACE VIEW tms.v_shipment_financials AS
SELECT
    s.shipment_id,
    s.shipment_number,
    -- Estimated carrier cost (all cost lines)
    COALESCE(SUM(sc.amount) FILTER (WHERE sc.is_estimated = TRUE),  0) AS estimated_carrier_cost,
    -- Actual carrier cost (override or non-estimated lines)
    COALESCE(SUM(COALESCE(sc.approved_amount, sc.amount))
             FILTER (WHERE sc.is_override = TRUE OR sc.is_estimated = FALSE), 0) AS actual_carrier_cost,
    -- Total carrier cost (best available)
    COALESCE(SUM(COALESCE(sc.approved_amount, sc.amount)), 0)            AS total_carrier_cost,
    -- Client billable amount
    COALESCE(SUM(cc.amount), 0)                                          AS client_billable_amount,
    -- Approved financial amount
    COALESCE(SUM(COALESCE(cc.approved_amount, cc.amount)), 0)            AS approved_financial_amount,
    -- Gross margin (billable - carrier cost)
    COALESCE(SUM(cc.amount), 0)
        - COALESCE(SUM(COALESCE(sc.approved_amount, sc.amount)), 0)      AS gross_margin,
    -- Gross margin % 
    CASE
        WHEN COALESCE(SUM(cc.amount), 0) > 0
        THEN ROUND(
            (COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(COALESCE(sc.approved_amount, sc.amount)), 0))
            / COALESCE(SUM(cc.amount), 0) * 100, 2)
        ELSE 0
    END AS gross_margin_pct,
    -- Variance (estimated vs actual carrier cost)
    COALESCE(SUM(sc.amount) FILTER (WHERE sc.is_estimated = TRUE), 0)
        - COALESCE(SUM(COALESCE(sc.approved_amount, sc.amount))
                   FILTER (WHERE sc.is_override = TRUE OR sc.is_estimated = FALSE), 0)
                                                                         AS variance,
    -- Counts and flags
    COUNT(DISTINCT sc.cost_id)                                           AS carrier_cost_lines,
    COUNT(DISTINCT cc.client_charge_id)                                  AS client_charge_lines,
    BOOL_OR(sc.is_override)                                              AS has_overrides,
    BOOL_OR(cc.approved_at IS NOT NULL)                                  AS has_approvals,
    -- Currency
    COALESCE(MIN(sc.currency), 'USD')                                    AS currency,
    -- Timestamps
    MAX(sc.rated_at)                                                     AS last_rated_at,
    MAX(cc.created_at)                                                   AS last_billed_at
FROM tms.shipments s
LEFT JOIN tms.shipment_costs  sc ON sc.shipment_id = s.shipment_id
LEFT JOIN tms.client_charges  cc ON cc.shipment_id = s.shipment_id
GROUP BY s.shipment_id, s.shipment_number;

COMMIT;
