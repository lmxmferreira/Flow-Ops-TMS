"""
routers/core_platform.py
TMS-CORE-008, CORE-009, CORE-010: Core Enterprise Platform
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
import json as _json

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class SavedSearchCreate(BaseModel):
    search_name: str
    entity_type: str
    filters: dict
    sort_by: Optional[str] = None
    sort_dir: str = "asc"
    is_shared: bool = False

class AlertCreate(BaseModel):
    alert_type: str
    title: str
    message: str
    severity: str = "info"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    user_id: Optional[str] = None
    role_code: Optional[str] = None

class MassActionRequest(BaseModel):
    entity_type: str
    entity_ids: list[str]
    action: str
    params: Optional[dict] = None


# ── CORE-008: Unified reference data ──────────────────────────────

REFERENCE_TYPES = {
    "locations": {
        "sql": "SELECT location_id AS id, location_code AS code, location_name AS name, location_subtype AS subtype FROM tms.locations WHERE is_active = TRUE ORDER BY location_name",
        "params": {}
    },
    "carriers": {
        "sql": "SELECT c.carrier_id AS id, p.party_code AS code, p.party_name AS name FROM tms.carriers c JOIN tms.parties p ON p.party_id = c.party_id ORDER BY p.party_name",
        "params": {}
    },
    "customers": {
        "sql": "SELECT p.party_id AS id, p.party_code AS code, p.party_name AS name FROM tms.parties p WHERE p.party_type_id IN (SELECT party_type_id FROM tms.party_types WHERE party_type_code = 'CUSTOMER') ORDER BY p.party_name",
        "params": {}
    },
    "suppliers": {
        "sql": "SELECT p.party_id AS id, p.party_code AS code, p.party_name AS name FROM tms.parties p WHERE p.party_type_id IN (SELECT party_type_id FROM tms.party_types WHERE party_type_code = 'SUPPLIER') ORDER BY p.party_name",
        "params": {}
    },
    "items": {
        "sql": "SELECT item_id AS id, item_number AS code, item_description AS name, freight_class FROM tms.items WHERE status = 'active' ORDER BY item_number",
        "params": {}
    },
    "charge_codes": {
        "sql": "SELECT charge_code_id AS id, charge_code AS code, charge_name AS name, charge_category, applies_to FROM tms.charge_code_master WHERE is_active = TRUE ORDER BY charge_category, charge_code",
        "params": {}
    },
    "service_levels": {
        "sql": "SELECT lookup_value_id AS id, lookup_code AS code, lookup_value AS name FROM tms.lookup_values WHERE lookup_type_id IN (SELECT lookup_type_id FROM tms.lookup_types WHERE lookup_type_code = 'SERVICE_LEVEL') AND is_active = TRUE ORDER BY lookup_value",
        "params": {}
    },
    "equipment_types": {
        "sql": "SELECT lookup_value_id AS id, lookup_code AS code, lookup_value AS name FROM tms.lookup_values WHERE lookup_type_id IN (SELECT lookup_type_id FROM tms.lookup_types WHERE lookup_type_code = 'EQUIPMENT_TYPE') AND is_active = TRUE ORDER BY lookup_value",
        "params": {}
    },
    "document_types": {
        "sql": "SELECT document_type_id AS id, type_code AS code, type_name AS name, category FROM tms.document_types WHERE is_active = TRUE ORDER BY category, type_name",
        "params": {}
    },
    "reason_codes": {
        "sql": "SELECT reason_code_id AS id, reason_code AS code, description AS name, category FROM tms.adjustment_reason_codes WHERE is_active = TRUE ORDER BY category, reason_code",
        "params": {}
    },
    "uom": {
        "sql": "SELECT uom_id AS id, uom_code AS code, uom_name AS name FROM tms.unit_of_measures WHERE is_active = TRUE ORDER BY uom_name",
        "params": {}
    },
    "countries": {
        "sql": "SELECT country_id AS id, country_code AS code, country_name AS name FROM tms.countries ORDER BY country_name",
        "params": {}
    },
    "transport_modes": {
        "sql": "SELECT lookup_value_id AS id, lookup_code AS code, lookup_value AS name FROM tms.lookup_values WHERE lookup_type_id IN (SELECT lookup_type_id FROM tms.lookup_types WHERE lookup_type_code = 'TRANSPORT_MODE') AND is_active = TRUE ORDER BY lookup_value",
        "params": {}
    },
    "gl_accounts": {
        "sql": "SELECT DISTINCT gl_account_code AS id, gl_account_code AS code, billing_category AS name FROM tms.charge_code_master WHERE gl_account_code IS NOT NULL ORDER BY gl_account_code",
        "params": {}
    },
}


@router.get("/reference-data/{ref_type}")
async def get_reference_data(
    ref_type: str,
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
    user=Depends(get_current_user),
):
    """
    CORE-008: Unified reference data endpoint.
    Supports: locations, carriers, customers, suppliers, items,
    charge_codes, service_levels, equipment_types, document_types,
    reason_codes, uom, countries, transport_modes, gl_accounts
    """
    if ref_type not in REFERENCE_TYPES:
        raise HTTPException(400, f"Unknown reference type: {ref_type}. Available: {', '.join(REFERENCE_TYPES.keys())}")

    config = REFERENCE_TYPES[ref_type]
    sql = config["sql"]
    params: dict[str, Any] = {**config["params"], "limit": limit}

    # Add search filter if provided
    if search:
        # Wrap in a subquery to filter on name/code
        sql = f"SELECT * FROM ({sql}) ref WHERE (CAST(ref.code AS TEXT) ILIKE :search OR CAST(ref.name AS TEXT) ILIKE :search) LIMIT :limit"
        params["search"] = f"%{search}%"
    else:
        sql = f"{sql} LIMIT :limit"

    try:
        result = await db.execute(text(sql), params)
        rows = [dict(r) for r in result.mappings().all()]
        return {
            "ref_type": ref_type,
            "count":    len(rows),
            "data":     rows,
        }
    except Exception as e:
        # Graceful fallback for missing tables
        return {"ref_type": ref_type, "count": 0, "data": [], "note": str(e)[:100]}


@router.get("/reference-data")
async def list_reference_types(user=Depends(get_current_user)):
    """List all available reference data types."""
    return {"available_types": list(REFERENCE_TYPES.keys()), "count": len(REFERENCE_TYPES)}


# ── CORE-009: Global audit trail ──────────────────────────────────

@router.get("/audit-trail")
async def get_audit_trail(
    db: AsyncSession = Depends(get_db),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    performed_by: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    """
    CORE-009: Complete transaction history and auditability.
    Aggregates audit events from all sources:
    - Master data changes (master_data_audit)
    - Re-rating events (rerate_log)
    - Lifecycle stage changes (process_lifecycle)
    - Exception events (lifecycle_exceptions)
    """
    events = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    # ── Master data audit ──
    md_conditions = ["1=1"]
    if entity_type:
        md_conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    if entity_id:
        md_conditions.append("entity_id = CAST(:entity_id AS uuid)")
        params["entity_id"] = entity_id
    if action:
        md_conditions.append("action = :action")
        params["action"] = action
    if performed_by:
        md_conditions.append("performed_by ILIKE :performed_by")
        params["performed_by"] = f"%{performed_by}%"
    if from_date:
        md_conditions.append("performed_at >= CAST(:from_date AS date)")
        params["from_date"] = from_date
    if to_date:
        md_conditions.append("performed_at <= CAST(:to_date AS date)")
        params["to_date"] = to_date

    md_result = await db.execute(text(f"""
        SELECT 'master_data' AS source, entity_type, CAST(entity_id AS TEXT) AS entity_id,
               action, version_before, version_after,
               changed_fields, performed_by, performed_at AS event_at, notes
        FROM tms.master_data_audit
        WHERE {' AND '.join(md_conditions)}
        ORDER BY performed_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    events.extend([dict(r) for r in md_result.mappings().all()])

    # ── Rerate events (operational/financial) ──
    if not entity_type or entity_type == "shipment":
        rr_params: dict[str, Any] = {"limit": min(limit, 50)}
        rr_conditions = ["1=1"]
        if entity_id:
            rr_conditions.append("shipment_id = CAST(:entity_id AS uuid)")
            rr_params["entity_id"] = entity_id
        if from_date:
            rr_conditions.append("completed_at >= CAST(:from_date AS date)")
            rr_params["from_date"] = from_date
        rr_result = await db.execute(text(f"""
            SELECT 'rerate' AS source, 'shipment' AS entity_type,
                   CAST(shipment_id AS TEXT) AS entity_id,
                   trigger_reason AS action, NULL AS version_before, NULL AS version_after,
                   changed_fields, triggered_by AS performed_by,
                   completed_at AS event_at, notes
            FROM tms.rerate_log
            WHERE {' AND '.join(rr_conditions)}
            ORDER BY completed_at DESC
            LIMIT :limit
        """), rr_params)
        events.extend([dict(r) for r in rr_result.mappings().all()])

    # ── Lifecycle changes ──
    if not entity_type or entity_type == "shipment":
        lc_params: dict[str, Any] = {"limit": min(limit, 50)}
        lc_conditions = ["1=1"]
        if entity_id:
            lc_conditions.append("shipment_id = CAST(:entity_id AS uuid)")
            lc_params["entity_id"] = entity_id
        lc_result = await db.execute(text(f"""
            SELECT 'lifecycle' AS source, 'shipment' AS entity_type,
                   CAST(shipment_id AS TEXT) AS entity_id,
                   current_stage AS action, NULL AS version_before, NULL AS version_after,
                   NULL AS changed_fields, NULL AS performed_by,
                   updated_at AS event_at, NULL AS notes
            FROM tms.process_lifecycle
            WHERE {' AND '.join(lc_conditions)}
            ORDER BY updated_at DESC
            LIMIT :limit
        """), lc_params)
        events.extend([dict(r) for r in lc_result.mappings().all()])

    # Sort all events by event_at descending
    events.sort(key=lambda x: str(x.get("event_at") or ""), reverse=True)

    # Summary by source
    summary = {}
    for e in events:
        src = e["source"]
        summary[src] = summary.get(src, 0) + 1

    return {
        "total_events": len(events),
        "source_summary": summary,
        "filters": {
            "entity_type": entity_type,
            "entity_id":   entity_id,
            "action":      action,
            "from_date":   from_date,
            "to_date":     to_date,
        },
        "events": events[:limit],
    }


# ── CORE-010: Dashboard ───────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CORE-010: Role-based dashboard with KPIs, work queue summary,
    active alerts, and exception counts.
    """
    user_email = user.get("email", "")

    # Shipment KPIs
    shp_result = await db.execute(text("""
        SELECT
            COUNT(*) AS total_shipments,
            COUNT(*) FILTER (WHERE pl.current_stage = 'planned') AS planned,
            COUNT(*) FILTER (WHERE pl.current_stage = 'in_transit') AS in_transit,
            COUNT(*) FILTER (WHERE pl.current_stage = 'delivered') AS delivered,
            COUNT(*) FILTER (WHERE pl.current_stage = 'costed') AS costed,
            COUNT(*) FILTER (WHERE pl.has_exceptions = TRUE) AS with_exceptions
        FROM tms.shipments s
        LEFT JOIN tms.process_lifecycle pl ON pl.shipment_id = s.shipment_id
    """))
    shp_kpis = dict(shp_result.mappings().one())

    # Financial KPIs
    try:
        fin_result = await db.execute(text("""
            SELECT
                COALESCE((SELECT SUM(amount) FROM tms.shipment_costs), 0) AS total_carrier_cost,
                COALESCE((SELECT SUM(amount) FROM tms.client_charges), 0) AS total_client_charges,
                (SELECT COUNT(DISTINCT shipment_id) FROM tms.shipment_costs) AS rated_shipments
        """))
        fin_kpis = dict(fin_result.mappings().one())
    except Exception:
        fin_kpis = {"total_carrier_cost": 0, "total_client_charges": 0, "rated_shipments": 0}

    # Document KPIs
    doc_result = await db.execute(text("""
        SELECT
            COUNT(*) AS total_documents,
            COUNT(*) FILTER (WHERE status = 'generated') AS generated,
            COUNT(*) FILTER (WHERE status = 'sent') AS sent,
            COUNT(*) FILTER (WHERE ocr_status = 'pending') AS ocr_pending
        FROM tms.documents
        WHERE is_current_version = TRUE
    """))
    doc_kpis = dict(doc_result.mappings().one())

    # Open exceptions by severity
    exc_result = await db.execute(text("""
        SELECT severity, COUNT(*) AS count
        FROM tms.lifecycle_exceptions WHERE is_resolved = FALSE
        GROUP BY severity ORDER BY severity
    """))
    exceptions = {r["severity"]: int(r["count"]) for r in exc_result.mappings().all()}

    # Master data counts (safe fallbacks)
    try:
        md_result = await db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM tms.locations) AS active_locations,
                (SELECT COUNT(*) FROM tms.items) AS active_items,
                (SELECT COUNT(*) FROM tms.charge_code_master) AS active_charge_codes,
                (SELECT COUNT(*) FROM tms.carriers) AS total_carriers
        """))
        md_kpis = dict(md_result.mappings().one())
    except Exception:
        md_kpis = {"active_locations": 0, "active_items": 0, "active_charge_codes": 0, "total_carriers": 0}

    # Recent activity (last 5 events)
    activity_result = await db.execute(text("""
        SELECT entity_type, action, performed_by, performed_at AS event_at, notes
        FROM tms.master_data_audit
        ORDER BY performed_at DESC LIMIT 5
    """))
    recent_activity = [dict(r) for r in activity_result.mappings().all()]

    return {
        "user":  user_email,
        "kpis": {
            "shipments":    {k: int(v) if v else 0 for k, v in shp_kpis.items()},
            "financials": {
                "total_carrier_cost":   float(fin_kpis.get("total_carrier_cost") or 0),
                "total_client_charges": float(fin_kpis.get("total_client_charges") or 0),
                "rated_shipments":      int(fin_kpis.get("rated_shipments") or 0),
                "gross_margin":         float(fin_kpis.get("total_client_charges") or 0) - float(fin_kpis.get("total_carrier_cost") or 0),
            },
            "documents":    {k: int(v) if v else 0 for k, v in doc_kpis.items()},
            "master_data":  {k: int(v) if v else 0 for k, v in md_kpis.items()},
        },
        "exceptions": {
            "by_severity": exceptions,
            "total_open":  sum(exceptions.values()),
        },
        "recent_activity": recent_activity,
    }


# ── CORE-010: Work queue ──────────────────────────────────────────

@router.get("/work-queue")
async def get_work_queue(
    db: AsyncSession = Depends(get_db),
    role: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """
    CORE-010: Role-based work queue showing items requiring action.
    """
    queue = []

    # Shipments needing costing
    uncosted = await db.execute(text("""
        SELECT s.shipment_id, s.shipment_number, 'Rate shipment' AS action_required,
               'rating' AS queue_type, 'high' AS priority
        FROM tms.shipments s
        LEFT JOIN tms.process_lifecycle pl ON pl.shipment_id = s.shipment_id
        WHERE (pl.costed = FALSE OR pl.lifecycle_id IS NULL)
        LIMIT 10
    """))
    for r in uncosted.mappings().all():
        queue.append({**dict(r), "category": "Costing"})

    # Documents missing POD before billing
    missing_pod = await db.execute(text("""
        SELECT s.shipment_id, s.shipment_number,
               'Missing POD - required before billing' AS action_required,
               'documents' AS queue_type, 'high' AS priority
        FROM tms.shipments s
        WHERE NOT EXISTS (
            SELECT 1 FROM tms.document_links dl
            JOIN tms.documents d ON d.document_id = dl.document_id
            JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
            WHERE dl.related_entity_type = 'shipment'
              AND dl.related_entity_id = s.shipment_id
              AND dt.type_code = 'POD'
        )
        LIMIT 10
    """))
    for r in missing_pod.mappings().all():
        queue.append({**dict(r), "category": "Documents"})

    # Open exceptions needing resolution
    open_exc = await db.execute(text("""
        SELECT e.exception_id AS shipment_id, s.shipment_number,
               e.description AS action_required,
               'exceptions' AS queue_type,
               CASE e.severity WHEN 'critical' THEN 'critical' WHEN 'error' THEN 'high' ELSE 'medium' END AS priority
        FROM tms.lifecycle_exceptions e
        LEFT JOIN tms.shipments s ON s.shipment_id = e.shipment_id
        WHERE e.is_resolved = FALSE
        ORDER BY e.severity, e.created_at DESC
        LIMIT 10
    """))
    for r in open_exc.mappings().all():
        queue.append({**dict(r), "category": "Exceptions"})

    # Shipments with client charges not yet approved
    unapproved = await db.execute(text("""
        SELECT DISTINCT s.shipment_id, s.shipment_number,
               'Client charges pending approval' AS action_required,
               'billing' AS queue_type, 'medium' AS priority
        FROM tms.client_charges cc
        JOIN tms.shipments s ON s.shipment_id = cc.shipment_id
        WHERE cc.approved_at IS NULL AND cc.billed_flag = FALSE
        LIMIT 10
    """))
    for r in unapproved.mappings().all():
        queue.append({**dict(r), "category": "Billing"})

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    queue.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

    summary = {}
    for item in queue:
        cat = item["category"]
        summary[cat] = summary.get(cat, 0) + 1

    return {
        "role":          role,
        "total_items":   len(queue),
        "by_category":   summary,
        "work_items":    queue,
    }


# ── CORE-010: Alerts ──────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    severity: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """CORE-010: Active alerts for current user."""
    # For now, surface lifecycle exceptions as alerts
    conditions = ["is_resolved = FALSE"]
    params: dict[str, Any] = {"limit": limit}
    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity

    result = await db.execute(text(f"""
        SELECT e.exception_id AS alert_id,
               e.exception_type AS alert_type,
               e.description AS message,
               e.severity,
               e.lifecycle_stage,
               s.shipment_number,
               e.created_at
        FROM tms.lifecycle_exceptions e
        LEFT JOIN tms.shipments s ON s.shipment_id = e.shipment_id
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE e.severity WHEN 'critical' THEN 1 WHEN 'error' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,
                 e.created_at DESC
        LIMIT :limit
    """), params)
    alerts = [dict(r) for r in result.mappings().all()]

    return {
        "total_alerts": len(alerts),
        "alerts":       alerts,
    }


# ── CORE-010: Saved searches ──────────────────────────────────────

@router.post("/saved-searches", status_code=201)
async def create_saved_search(
    payload: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CORE-010: Save a search configuration for reuse."""
    user_id = user.get("sub") or user.get("email", "system")
    result = await db.execute(text("""
        INSERT INTO tms.saved_searches
            (search_name, entity_type, filters, sort_by, sort_dir, is_shared, created_by)
        VALUES
            (:search_name, :entity_type, CAST(:filters AS jsonb),
             :sort_by, :sort_dir, :is_shared, :created_by)
        RETURNING search_id
    """), {
        **payload.model_dump(),
        "filters": _json.dumps(payload.filters),
        "created_by": user_id,
    })
    await db.commit()
    return {"search_id": str(result.scalar()), **payload.model_dump()}


@router.get("/saved-searches")
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    entity_type: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """CORE-010: Get saved searches for current user."""
    user_id = user.get("sub") or user.get("email", "system")
    conditions = ["(created_by = :user_id OR is_shared = TRUE)"]
    params: dict[str, Any] = {"user_id": user_id}
    if entity_type:
        conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    result = await db.execute(text(f"""
        SELECT * FROM tms.saved_searches
        WHERE {' AND '.join(conditions)}
        ORDER BY search_name
    """), params)
    return [dict(r) for r in result.mappings().all()]


# ── CORE-010: Mass actions ────────────────────────────────────────

@router.post("/mass-actions")
async def execute_mass_action(
    payload: MassActionRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CORE-010: Execute a mass action on multiple entities.
    Supported actions: approve_charges, advance_lifecycle_stage,
    resolve_exceptions, mark_documents_sent
    """
    user_id = user.get("email", "system")
    results = {"total": len(payload.entity_ids), "succeeded": 0, "failed": 0, "errors": []}

    for entity_id in payload.entity_ids:
        try:
            if payload.action == "approve_charges" and payload.entity_type == "shipment":
                await db.execute(text("""
                    UPDATE tms.client_charges
                    SET approved_by = :user, approved_at = NOW(), updated_at = NOW()
                    WHERE shipment_id = CAST(:id AS uuid) AND approved_at IS NULL
                """), {"user": user_id, "id": entity_id})
                results["succeeded"] += 1

            elif payload.action == "advance_lifecycle_stage" and payload.entity_type == "shipment":
                stage = (payload.params or {}).get("stage", "delivered")
                col = f"{stage}_at" if not stage.endswith("_at") else stage
                flag_col = stage if not stage.endswith("_at") else stage[:-3]
                await db.execute(text(f"""
                    INSERT INTO tms.process_lifecycle (shipment_id, {flag_col}, {flag_col}_at, current_stage)
                    VALUES (CAST(:id AS uuid), TRUE, NOW(), :stage)
                    ON CONFLICT (shipment_id) DO UPDATE SET
                        {flag_col} = TRUE, {flag_col}_at = NOW(),
                        current_stage = :stage, updated_at = NOW()
                """), {"id": entity_id, "stage": stage})
                results["succeeded"] += 1

            elif payload.action == "resolve_exceptions":
                notes = (payload.params or {}).get("notes", "Mass resolved")
                await db.execute(text("""
                    UPDATE tms.lifecycle_exceptions
                    SET is_resolved = TRUE, resolved_by = :user,
                        resolved_at = NOW(), resolution_notes = :notes
                    WHERE shipment_id = CAST(:id AS uuid) AND is_resolved = FALSE
                """), {"user": user_id, "notes": notes, "id": entity_id})
                results["succeeded"] += 1

            else:
                results["failed"] += 1
                results["errors"].append(f"{entity_id}: Unknown action '{payload.action}' for entity type '{payload.entity_type}'")
                continue

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{entity_id}: {str(e)[:100]}")

    await db.commit()
    return {"action": payload.action, "entity_type": payload.entity_type, **results}
