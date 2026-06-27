"""
routers/platform.py
TMS-INT-001-015: Integration
TMS-RPT-001-010: Reporting & Analytics
TMS-SEC-001-010: Security, Roles, Audit & Compliance
TMS-WF-001-010: Workflow & Approval Management
TMS-UX-001-010: User Experience & Productivity
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import json as _json

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class IntegrationTxnCreate(BaseModel):
    direction: str = "inbound"
    integration_type: str
    source_system: Optional[str] = None
    target_system: Optional[str] = None
    message_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    payload: Optional[dict] = None

class IntegrationRetry(BaseModel):
    transaction_ids: list[str]

class WorkflowStartRequest(BaseModel):
    workflow_code: str
    entity_type: str
    entity_id: str
    amount: Optional[float] = None
    notes: Optional[str] = None

class WorkflowAction(BaseModel):
    action: str  # approve | reject | delegate | escalate | withdraw
    comments: Optional[str] = None
    delegated_to: Optional[str] = None
    reason_code: Optional[str] = None

class UserPreferenceUpdate(BaseModel):
    language: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    number_format: Optional[str] = None
    default_views: Optional[dict] = None
    dashboard_layout: Optional[dict] = None
    notification_settings: Optional[dict] = None

class SecurityAuditLog(BaseModel):
    action_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    reason_code: Optional[str] = None
    comments: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# TMS-INT: Integration Framework
# ══════════════════════════════════════════════════════════════════

@router.post("/integration/transactions", status_code=201)
async def log_integration_transaction(
    payload: IntegrationTxnCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """INT-010/012/015: Log inbound or outbound integration transaction."""
    txn_num = f"INT-{payload.direction.upper()[:3]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    p = payload.payload or {}
    result = await db.execute(text("""
        INSERT INTO tms.integration_transactions
            (transaction_number, direction, integration_type, source_system,
             target_system, message_type, entity_type, entity_id,
             status, payload_inbound, payload_outbound)
        VALUES
            (:txn_num, :direction, :int_type, :source,
             :target, :msg_type, :entity_type, CAST(:entity_id AS uuid),
             'received',
             CASE WHEN :direction = 'inbound' THEN CAST(:payload AS jsonb) ELSE NULL END,
             CASE WHEN :direction = 'outbound' THEN CAST(:payload AS jsonb) ELSE NULL END)
        RETURNING transaction_id, transaction_number
    """), {
        "txn_num":    txn_num,
        "direction":  payload.direction,
        "int_type":   payload.integration_type,
        "source":     payload.source_system,
        "target":     payload.target_system,
        "msg_type":   payload.message_type,
        "entity_type":payload.entity_type,
        "entity_id":  payload.entity_id,
        "payload":    _json.dumps(p),
    })
    row = dict(result.mappings().one())
    await db.commit()
    return {"transaction_id": str(row["transaction_id"]),
            "transaction_number": row["transaction_number"], "status": "received"}


@router.get("/integration/transactions")
async def list_integration_transactions(
    db: AsyncSession = Depends(get_db),
    integration_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """INT-012/014: Integration transaction log with monitoring."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if integration_type:
        conditions.append("integration_type = :int_type")
        params["int_type"] = integration_type
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if direction:
        conditions.append("direction = :direction")
        params["direction"] = direction
    if entity_type:
        conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type

    result = await db.execute(text(f"""
        SELECT * FROM tms.integration_transactions
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC LIMIT :limit
    """), params)
    rows = [dict(r) for r in result.mappings().all()]

    # Summary for monitoring dashboard (INT-014)
    summary_result = await db.execute(text("""
        SELECT status, COUNT(*) AS count FROM tms.integration_transactions
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY status
    """))
    summary = {r["status"]: int(r["count"]) for r in summary_result.mappings().all()}

    return {"total": len(rows), "last_24h_summary": summary, "transactions": rows}


@router.patch("/integration/transactions/{txn_id}/status")
async def update_integration_status(
    txn_id: str,
    status: str,
    error_message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """INT-012: Update transaction status, acknowledge, mark processed."""
    await db.execute(text("""
        UPDATE tms.integration_transactions
        SET status = :status,
            error_message = :error,
            processed_at  = CASE WHEN :status = 'completed' THEN NOW() ELSE processed_at END,
            acknowledged  = CASE WHEN :status IN ('completed','rejected') THEN TRUE ELSE acknowledged END,
            ack_at        = CASE WHEN :status IN ('completed','rejected') THEN NOW() ELSE ack_at END
        WHERE transaction_id = CAST(:id AS uuid)
    """), {"status": status, "error": error_message, "id": txn_id})
    await db.commit()
    return {"transaction_id": txn_id, "status": status}


@router.post("/integration/retry")
async def retry_transactions(
    payload: IntegrationRetry,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """INT-012: Retry failed integration transactions."""
    retried = 0
    for txn_id in payload.transaction_ids:
        await db.execute(text("""
            UPDATE tms.integration_transactions
            SET status = 'retrying', retry_count = retry_count + 1, last_retry_at = NOW()
            WHERE transaction_id = CAST(:id AS uuid) AND status IN ('failed','rejected')
        """), {"id": txn_id})
        retried += 1
    await db.commit()
    return {"retried": retried, "transaction_ids": payload.transaction_ids}


@router.get("/integration/mappings")
async def list_mappings(
    integration_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """INT-013: List data cross-reference mappings."""
    conditions = ["is_active = TRUE"]
    params: dict[str, Any] = {}
    if integration_type:
        conditions.append("integration_type = :int_type")
        params["int_type"] = integration_type
    result = await db.execute(text(f"""
        SELECT * FROM tms.integration_mappings
        WHERE {' AND '.join(conditions)} ORDER BY mapping_name
    """), params)
    return [dict(r) for r in result.mappings().all()]


# ══════════════════════════════════════════════════════════════════
# TMS-RPT: Reporting & Analytics
# ══════════════════════════════════════════════════════════════════

@router.get("/reports/operational")
async def operational_dashboard(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """RPT-001: Operational dashboard — shipment status, exceptions, milestones."""
    # Shipment status breakdown
    shp_result = await db.execute(text("""
        SELECT pl.current_stage, COUNT(*) AS count
        FROM tms.shipments s
        LEFT JOIN tms.process_lifecycle pl ON pl.shipment_id = s.shipment_id
        GROUP BY pl.current_stage ORDER BY pl.current_stage
    """))
    shp_status = {r["current_stage"] or "untracked": int(r["count"]) for r in shp_result.mappings().all()}

    # Tender status
    tender_result = await db.execute(text("""
        SELECT lv.display_name AS status, COUNT(*) AS count
        FROM tms.tenders t
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = t.tender_status_id
        GROUP BY lv.display_name ORDER BY count DESC
    """))
    tender_status = {r["status"] or "unknown": int(r["count"]) for r in tender_result.mappings().all()}

    # Open exceptions by severity
    exc_result = await db.execute(text("""
        SELECT severity, COUNT(*) AS count FROM tms.exceptions
        WHERE status NOT IN ('resolved','closed','overridden')
        GROUP BY severity ORDER BY severity
    """))
    exceptions = {r["severity"]: int(r["count"]) for r in exc_result.mappings().all()}

    # Appointments today
    appt_result = await db.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE no_show = TRUE) AS no_shows,
               COUNT(*) FILTER (WHERE cancelled_at IS NOT NULL) AS cancelled
        FROM tms.appointments
        WHERE DATE(appointment_start_datetime) = CURRENT_DATE
    """))
    appts = dict(appt_result.mappings().one())

    return {
        "shipment_status":  shp_status,
        "tender_status":    tender_status,
        "open_exceptions":  exceptions,
        "today_appointments": {k: int(v or 0) for k, v in appts.items()},
    }


@router.get("/reports/po-status")
async def po_report(
    db: AsyncSession = Depends(get_db),
    customer_party_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """RPT-002: PO report — open, unreleased, shipped, remaining quantities."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if customer_party_id:
        conditions.append("po.buyer_party_id = CAST(:cust_id AS uuid)")
        params["cust_id"] = customer_party_id

    result = await db.execute(text(f"""
        SELECT po.purchase_order_id, po.purchase_order_number,
               COUNT(pol.purchase_order_line_id) AS line_count,
               SUM(pol.ordered_quantity) AS total_ordered,
               SUM(COALESCE(orl.released_qty, 0)) AS released_qty,
               SUM(pol.ordered_quantity) - SUM(COALESCE(orl.released_qty, 0)) AS remaining_qty,
               po.po_status
        FROM tms.purchase_orders po
        JOIN tms.purchase_order_lines pol ON pol.purchase_order_id = po.purchase_order_id
        LEFT JOIN tms.po_line_quantity_ledger orl ON orl.purchase_order_line_id = pol.purchase_order_line_id
        WHERE {' AND '.join(conditions)}
        GROUP BY po.purchase_order_id, po.purchase_order_number, po.po_status
        ORDER BY po.purchase_order_number
        LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/reports/shipments")
async def shipment_report(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    customer_party_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """RPT-003: Shipment report by customer, carrier, lane, mode, date."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if carrier_id:
        conditions.append("s.carrier_id = CAST(:carrier_id AS uuid)")
        params["carrier_id"] = carrier_id
    if customer_party_id:
        conditions.append("s.customer_party_id = CAST(:cust_id AS uuid)")
        params["cust_id"] = customer_party_id
    if from_date:
        conditions.append("s.planned_pickup_date >= CAST(:from_date AS date)")
        params["from_date"] = from_date
    if to_date:
        conditions.append("s.planned_pickup_date <= CAST(:to_date AS date)")
        params["to_date"] = to_date

    result = await db.execute(text(f"""
        SELECT s.shipment_id, s.shipment_number, s.planned_pickup_date,
               s.planned_delivery_date, p.party_name AS carrier_name,
               pc.party_name AS customer_name, pl.current_stage,
               COALESCE(sc.total_cost, 0) AS carrier_cost
        FROM tms.shipments s
        LEFT JOIN tms.carriers c ON c.carrier_id = s.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.parties pc ON pc.party_id = s.customer_party_id
        LEFT JOIN tms.process_lifecycle pl ON pl.shipment_id = s.shipment_id
        LEFT JOIN (SELECT shipment_id, SUM(amount) AS total_cost
                   FROM tms.shipment_costs GROUP BY shipment_id) sc
               ON sc.shipment_id = s.shipment_id
        WHERE {' AND '.join(conditions)}
        ORDER BY s.planned_pickup_date DESC LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/reports/carrier-performance")
async def carrier_performance_report(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """RPT-004: Carrier KPIs — acceptance, OTP, OTD, invoice accuracy, claims."""
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if carrier_id:
        conditions.append("c.carrier_id = CAST(:carrier_id AS uuid)")
        params["carrier_id"] = carrier_id

    result = await db.execute(text(f"""
        SELECT c.carrier_id, p.party_name AS carrier_name, c.scac,
               AVG(cs.tender_acceptance_pct)    AS avg_acceptance_pct,
               AVG(cs.avg_response_minutes)     AS avg_response_min,
               AVG(cs.on_time_pickup_pct)       AS avg_otp_pct,
               AVG(cs.on_time_delivery_pct)     AS avg_otd_pct,
               AVG(cs.invoice_accuracy_pct)     AS avg_invoice_accuracy,
               SUM(cs.claims_count)             AS total_claims,
               AVG(cs.total_score)              AS avg_score
        FROM tms.carriers c
        JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.carrier_scorecards cs ON cs.carrier_id = c.carrier_id
        WHERE {' AND '.join(conditions)}
        GROUP BY c.carrier_id, p.party_name, c.scac
        ORDER BY avg_score DESC NULLS LAST
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/reports/financial")
async def financial_report(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """RPT-006/008: Financial and reconciliation reports."""
    # Carrier cost summary
    cost_result = await db.execute(text("""
        SELECT charge_code, SUM(amount) AS total, COUNT(*) AS count
        FROM tms.shipment_costs GROUP BY charge_code ORDER BY total DESC LIMIT 10
    """))
    carrier_costs = [dict(r) for r in cost_result.mappings().all()]

    # Invoice aging
    aging_result = await db.execute(text("""
        SELECT
            CASE WHEN due_date IS NULL THEN 'no_due_date'
                 WHEN CURRENT_DATE <= due_date THEN 'current'
                 WHEN (CURRENT_DATE - due_date) <= 30 THEN '1_30_days'
                 WHEN (CURRENT_DATE - due_date) <= 60 THEN '31_60_days'
                 ELSE 'over_60_days' END AS bucket,
            COUNT(*) AS count,
            SUM(invoice_total_amount) AS total
        FROM tms.carrier_invoices
        WHERE status NOT IN ('paid','closed','canceled','reversed')
        GROUP BY bucket
    """))
    inv_aging = {r["bucket"]: {"count": int(r["count"]), "total": float(r["total"] or 0)}
                 for r in aging_result.mappings().all()}

    # Reconciliation summary
    recon_result = await db.execute(text("""
        SELECT
            SUM(actual_carrier_cost) AS total_carrier_cost,
            SUM(client_bill_amount)  AS total_billed,
            SUM(gross_margin)        AS total_margin,
            AVG(margin_pct)          AS avg_margin_pct,
            COUNT(*) FILTER (WHERE is_reconciled = TRUE)  AS reconciled,
            COUNT(*) FILTER (WHERE is_reconciled = FALSE) AS unreconciled
        FROM tms.financial_reconciliation
    """))
    recon = dict(recon_result.mappings().one())

    return {
        "carrier_costs_by_charge": carrier_costs,
        "invoice_aging":           inv_aging,
        "reconciliation_summary": {k: float(v or 0) if v is not None else 0
                                   for k, v in recon.items()
                                   if k not in ('reconciled','unreconciled')},
        "reconciliation_counts":  {
            "reconciled":   int(recon.get("reconciled") or 0),
            "unreconciled": int(recon.get("unreconciled") or 0),
        },
    }


@router.get("/reports/allocation")
async def allocation_report(
    shipment_id: Optional[str] = Query(None),
    gl_account_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """RPT-007: Cost allocation by shipment, PO, GL, cost center, carrier."""
    conditions = ["ca.is_current_version = TRUE"]
    params: dict[str, Any] = {}
    if shipment_id:
        conditions.append("ca.shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id
    if gl_account_code:
        conditions.append("ca.gl_account_code = :gl_code")
        params["gl_code"] = gl_account_code

    result = await db.execute(text(f"""
        SELECT ca.allocation_type, ca.charge_category, ca.gl_account_code,
               ca.responsible_party_type, ca.allocation_basis,
               COUNT(*) AS lines, SUM(ca.allocation_amount) AS total
        FROM tms.charge_allocations ca
        WHERE {' AND '.join(conditions)}
        GROUP BY ca.allocation_type, ca.charge_category, ca.gl_account_code,
                 ca.responsible_party_type, ca.allocation_basis
        ORDER BY total DESC
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/reports/configs", status_code=201)
async def save_report_config(
    report_name: str,
    report_type: str,
    parameters: dict,
    is_scheduled: bool = False,
    output_format: str = "json",
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """RPT-009: Save configurable report for reuse or scheduling."""
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        INSERT INTO tms.report_configs
            (report_name, report_type, parameters, is_scheduled, output_format, created_by)
        VALUES (:name, :type, CAST(:params AS jsonb), :scheduled, :format, :user)
        RETURNING config_id
    """), {
        "name":      report_name, "type":      report_type,
        "params":    _json.dumps(parameters),
        "scheduled": is_scheduled, "format": output_format, "user": user_id,
    })
    await db.commit()
    return {"config_id": str(result.scalar()), "report_name": report_name}


# ══════════════════════════════════════════════════════════════════
# TMS-SEC: Security, Roles, Audit & Compliance
# ══════════════════════════════════════════════════════════════════

@router.get("/security/roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """SEC-001/002: List all roles with permissions."""
    result = await db.execute(text("""
        SELECT role_id, role_code, role_name, role_type, permissions, is_active FROM tms.tms_roles WHERE is_active = TRUE ORDER BY role_type, role_name
    """))
    return [dict(r) for r in result.mappings().all()]


@router.get("/security/permissions-check")
async def check_permission(
    resource: str,
    action: str,
    role_code: str = "PLANNER",
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """SEC-002/003/004: Check if a role has permission for an action."""
    result = await db.execute(text("""
        SELECT permissions FROM tms.tms_roles WHERE role_code = :code AND is_active = TRUE
    """), {"code": role_code})
    row = result.mappings().one_or_none()
    if not row:
        return {"allowed": False, "reason": "Role not found"}

    perms = row["permissions"] or {}
    resource_perms = perms.get(resource, perms.get("all", []))
    allowed = action in resource_perms or "admin" in resource_perms

    return {
        "role_code":       role_code,
        "resource":        resource,
        "action":          action,
        "allowed":         allowed,
        "role_permissions":resource_perms,
    }


@router.post("/security/audit-log", status_code=201)
async def log_security_event(
    payload: SecurityAuditLog,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """SEC-007/008: Record immutable security audit event."""
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        INSERT INTO tms.security_audit_log
            (user_id, action_type, entity_type, entity_id,
             old_value, new_value, reason_code, comments)
        VALUES
            (:user_id, :action_type, :entity_type, CAST(:entity_id AS uuid),
             CAST(:old_value AS jsonb), CAST(:new_value AS jsonb),
             :reason_code, :comments)
        RETURNING log_id
    """), {
        "user_id":     user_id,
        "action_type": payload.action_type,
        "entity_type": payload.entity_type,
        "entity_id":   payload.entity_id,
        "old_value":   _json.dumps(payload.old_value) if payload.old_value else None,
        "new_value":   _json.dumps(payload.new_value) if payload.new_value else None,
        "reason_code": payload.reason_code,
        "comments":    payload.comments,
    })
    await db.commit()
    return {"log_id": str(result.scalar()), "user_id": user_id}


@router.get("/security/audit-log")
async def get_audit_log(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """SEC-007/009: Query immutable audit trail."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if user_id:
        conditions.append("user_id = :user_id")
        params["user_id"] = user_id
    if action_type:
        conditions.append("action_type = :action_type")
        params["action_type"] = action_type
    if entity_type:
        conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    if from_date:
        conditions.append("performed_at >= CAST(:from_date AS date)")
        params["from_date"] = from_date

    result = await db.execute(text(f"""
        SELECT * FROM tms.security_audit_log
        WHERE {' AND '.join(conditions)}
        ORDER BY performed_at DESC LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/security/retention-policies")
async def list_retention_policies(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """SEC-010: Data retention, archival, and purge policies."""
    result = await db.execute(text("""
        SELECT * FROM tms.data_retention_policies WHERE is_active = TRUE ORDER BY entity_type
    """))
    return [dict(r) for r in result.mappings().all()]


# ══════════════════════════════════════════════════════════════════
# TMS-WF: Workflow & Approval Management
# ══════════════════════════════════════════════════════════════════

@router.get("/workflows/definitions")
async def list_workflow_definitions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """WF-001/009: List workflow definitions with steps."""
    result = await db.execute(text("""
        SELECT * FROM tms.tms_workflow_definitions WHERE is_active = TRUE ORDER BY workflow_name
    """))
    return [dict(r) for r in result.mappings().all()]


@router.post("/workflows/start", status_code=201)
async def start_workflow(
    payload: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """WF-001/002/003: Start a workflow instance for an entity."""
    user_id = user.get("email", "system")

    # Load workflow definition
    wf_result = await db.execute(text("""
        SELECT * FROM tms.tms_workflow_definitions
        WHERE workflow_code = :code AND is_active = TRUE
    """), {"code": payload.workflow_code})
    wf = wf_result.mappings().one_or_none()
    if not wf:
        raise HTTPException(404, f"Workflow '{payload.workflow_code}' not found.")
    wf = dict(wf)

    result = await db.execute(text("""
        INSERT INTO tms.tms_workflow_instances
            (workflow_id, entity_type, entity_id, requested_by, amount, notes,
             status, current_step, step_history)
        VALUES
            (CAST(:wf_id AS uuid), :entity_type, CAST(:entity_id AS uuid),
             :requested_by, CAST(:amount AS numeric), :notes,
             'in_progress', 1, '[]')
        RETURNING instance_id
    """), {
        "wf_id":       str(wf["workflow_id"]),
        "entity_type": payload.entity_type,
        "entity_id":   payload.entity_id,
        "requested_by":user_id,
        "amount":      payload.amount,
        "notes":       payload.notes,
    })
    instance_id = str(result.scalar())
    await db.commit()

    steps = wf.get("steps") or []
    first_step = steps[0] if steps else {}
    return {
        "instance_id":   instance_id,
        "workflow_code": payload.workflow_code,
        "entity_type":   payload.entity_type,
        "entity_id":     payload.entity_id,
        "status":        "in_progress",
        "current_step":  1,
        "approver_role": first_step.get("role"),
    }


@router.patch("/workflows/{instance_id}/action")
async def workflow_action(
    instance_id: str,
    payload: WorkflowAction,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """WF-004/006/007: Approve, reject, delegate, escalate, or withdraw."""
    user_id = user.get("email", "system")
    if payload.action not in ("approve","reject","delegate","escalate","withdraw"):
        raise HTTPException(400, "Invalid action.")

    # Load instance + workflow
    inst_result = await db.execute(text("""
        SELECT wi.*, wd.steps, wd.workflow_name
        FROM tms.tms_workflow_instances wi
        JOIN tms.tms_workflow_definitions wd ON wd.workflow_id = wi.workflow_id
        WHERE wi.instance_id = CAST(:id AS uuid)
    """), {"id": instance_id})
    inst = inst_result.mappings().one_or_none()
    if not inst:
        raise HTTPException(404, "Workflow instance not found.")
    inst = dict(inst)

    steps = inst.get("steps") or []
    current_step = int(inst.get("current_step") or 1)
    history = inst.get("step_history") or []

    # Record step action
    history.append({
        "step":     current_step,
        "action":   payload.action,
        "by":       user_id,
        "at":       str(datetime.utcnow()),
        "comments": payload.comments,
        "reason":   payload.reason_code,
    })

    if payload.action == "approve":
        # Advance to next step or complete
        if current_step >= len(steps):
            new_status = "approved"
            next_step = current_step
        else:
            new_status = "in_progress"
            next_step = current_step + 1
    elif payload.action in ("reject","withdraw"):
        new_status = "rejected" if payload.action == "reject" else "withdrawn"
        next_step = current_step
    elif payload.action == "escalate":
        new_status = "escalated"
        next_step = current_step
    else:  # delegate
        new_status = "in_progress"
        next_step = current_step

    await db.execute(text("""
        UPDATE tms.tms_workflow_instances
        SET status       = :status,
            current_step = :next_step,
            step_history = CAST(:history AS jsonb),
            completed_at = CASE WHEN :status IN ('approved','rejected','withdrawn') THEN NOW() ELSE NULL END
        WHERE instance_id = CAST(:id AS uuid)
    """), {
        "status":    new_status,
        "next_step": next_step,
        "history":   _json.dumps(history),
        "id":        instance_id,
    })
    await db.commit()

    return {
        "instance_id": instance_id,
        "action":      payload.action,
        "new_status":  new_status,
        "next_step":   next_step,
        "actioned_by": user_id,
    }


@router.get("/workflows/worklist")
async def get_worklist(
    db: AsyncSession = Depends(get_db),
    role_code: Optional[str] = Query(None),
    status: Optional[str] = Query("in_progress"),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """WF-008: Approval worklist by role and status."""
    result = await db.execute(text(f"""
        SELECT wi.*, wd.workflow_name, wd.workflow_code, wd.steps
        FROM tms.tms_workflow_instances wi
        JOIN tms.tms_workflow_definitions wd ON wd.workflow_id = wi.workflow_id
        WHERE wi.status = :status
        ORDER BY wi.requested_at ASC
        LIMIT :limit
    """), {"status": status or "in_progress", "limit": limit})
    items = [dict(r) for r in result.mappings().all()]

    return {
        "total": len(items),
        "status": status,
        "items": items,
    }


# ══════════════════════════════════════════════════════════════════
# TMS-UX: User Experience & Productivity
# ══════════════════════════════════════════════════════════════════

@router.get("/ux/search")
async def global_search(
    q: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """UX-002: Global search across all key entity reference numbers."""
    results: list[dict] = []

    # Search reference index (catches POs, shipments, invoices, BOLs, etc.)
    ref_result = await db.execute(text("""
        SELECT ref_number, ref_type, entity_type, entity_id
        FROM tms.reference_index
        WHERE ref_number ILIKE :q AND is_active = TRUE
        LIMIT 10
    """), {"q": f"%{q}%"})
    results.extend([{**dict(r), "source": "reference_index"} for r in ref_result.mappings().all()])

    # Assets (BOL, PRO, trailer, container)
    asset_result = await db.execute(text("""
        SELECT ea.asset_type AS ref_type, ea.asset_value AS ref_number,
               'shipment' AS entity_type, ea.shipment_id AS entity_id
        FROM tms.exec_assets ea
        WHERE ea.asset_value ILIKE :q LIMIT 5
    """), {"q": f"%{q}%"})
    results.extend([{**dict(r), "source": "assets"} for r in asset_result.mappings().all()])

    # Direct shipment number match
    if not any(r["entity_type"] == "shipment" for r in results):
        shp_result = await db.execute(text("""
            SELECT shipment_id AS entity_id, shipment_number AS ref_number, 'shipment' AS entity_type
            FROM tms.shipments WHERE shipment_number ILIKE :q LIMIT 5
        """), {"q": f"%{q}%"})
        results.extend([{**dict(r), "ref_type": "shipment_number", "source": "shipments"}
                        for r in shp_result.mappings().all()])

    return {"query": q, "total": len(results), "results": results}


@router.get("/ux/preferences/{user_id}")
async def get_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """UX-008: Get user preferences."""
    result = await db.execute(text("""
        SELECT * FROM tms.user_preferences WHERE user_id = :user_id
    """), {"user_id": user_id})
    row = result.mappings().one_or_none()
    if not row:
        return {"user_id": user_id, "language": "en", "timezone": "UTC",
                "date_format": "YYYY-MM-DD", "number_format": "1,234.56",
                "default_views": {}, "dashboard_layout": {}, "notification_settings": {}}
    return dict(row)


@router.put("/ux/preferences/{user_id}")
async def save_preferences(
    user_id: str,
    payload: UserPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """UX-008: Save/update user preferences."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No preferences provided.")

    set_parts = [f"{k} = :{k}" for k in data if k not in ("default_views","dashboard_layout","notification_settings")]
    json_parts = [f"{k} = CAST(:{k} AS jsonb)" for k in data if k in ("default_views","dashboard_layout","notification_settings")]
    all_parts = set_parts + json_parts + ["updated_at = NOW()"]

    params = {k: (_json.dumps(v) if isinstance(v, dict) else v) for k, v in data.items()}
    params["user_id"] = user_id

    await db.execute(text(f"""
        INSERT INTO tms.user_preferences (user_id, {', '.join(data.keys())})
        VALUES (:user_id, {', '.join([f':{k}' for k in data.keys()])})
        ON CONFLICT (user_id) DO UPDATE SET {', '.join(all_parts)}
    """), params)
    await db.commit()
    return {"user_id": user_id, "updated": list(data.keys())}


@router.get("/ux/contextual-links/{entity_type}/{entity_id}")
async def get_contextual_links(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """UX-010: Contextual links between related objects."""
    links: dict = {}

    if entity_type == "shipment":
        # POs
        po_r = await db.execute(text("""
            SELECT DISTINCT po.purchase_order_id, po.purchase_order_number
            FROM tms.shipment_order_releases sor
            JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
            JOIN tms.order_release_lines orl ON orl.order_release_id = ore.order_release_id
            JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
            JOIN tms.purchase_orders po ON po.purchase_order_id = pol.purchase_order_id
            WHERE sor.shipment_id = CAST(:id AS uuid)
        """), {"id": entity_id})
        links["purchase_orders"] = [dict(r) for r in po_r.mappings().all()]

        # Carrier invoices
        ci_r = await db.execute(text("""
            SELECT carrier_invoice_id, carrier_invoice_number, status, invoice_total_amount
            FROM tms.carrier_invoices WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": entity_id})
        links["carrier_invoices"] = [dict(r) for r in ci_r.mappings().all()]

        # Client bills
        cb_r = await db.execute(text("""
            SELECT DISTINCT cb.client_bill_id, cb.client_bill_number, cb.status
            FROM tms.client_bill_lines cbl
            JOIN tms.client_bills cb ON cb.client_bill_id = cbl.client_bill_id
            WHERE cbl.shipment_id = CAST(:id AS uuid)
        """), {"id": entity_id})
        links["client_bills"] = [dict(r) for r in cb_r.mappings().all()]

        # Claims
        clm_r = await db.execute(text("""
            SELECT claim_id, claim_number, claim_type, status, claimed_amount
            FROM tms.claims WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": entity_id})
        links["claims"] = [dict(r) for r in clm_r.mappings().all()]

        # Exceptions
        exc_r = await db.execute(text("""
            SELECT exception_id, exception_number, exception_type, severity, status
            FROM tms.exceptions WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": entity_id})
        links["exceptions"] = [dict(r) for r in exc_r.mappings().all()]

        # Allocations
        alloc_r = await db.execute(text("""
            SELECT COUNT(*) AS count, SUM(allocation_amount) AS total
            FROM tms.charge_allocations
            WHERE shipment_id = CAST(:id AS uuid) AND is_current_version = TRUE
        """), {"id": entity_id})
        alloc = dict(alloc_r.mappings().one())
        links["allocations"] = {"count": int(alloc["count"]), "total": float(alloc["total"] or 0)}

    return {"entity_type": entity_type, "entity_id": entity_id, "links": links}
