from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional

router = APIRouter()

# ── List order releases ──────────────────────────────────────
@router.get("/")
async def list_order_releases(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    filters = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}

    if search:
        filters.append(
            "(orr.order_release_number ILIKE :search "
            "OR po.purchase_order_number ILIKE :search "
            "OR customer.party_name ILIKE :search "
            "OR supplier.party_name ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    if status:
        filters.append("lv_status.lookup_code = :status")
        params["status"] = status

    where = " AND ".join(filters)

    sql = text(f"""
        SELECT
            orr.order_release_id,
            orr.order_release_number,
            orr.requested_ship_date,
            orr.requested_delivery_date,
            orr.created_at,
            orr.updated_at,
            -- status
            COALESCE(lv_status.lookup_code,  'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name, 'Unknown') AS status_name,
            -- source type
            COALESCE(lv_src.display_name,    '')        AS release_source_type,
            -- PO linkage
            COALESCE(po.purchase_order_number, '')      AS po_number,
            COALESCE(po.purchase_order_id::text, '')    AS po_id,
            -- parties
            COALESCE(customer.party_name,  '')          AS customer_name,
            COALESCE(supplier.party_name,  '')          AS supplier_name,
            COALESCE(responsible.party_name, '')        AS responsible_party,
            -- locations
            COALESCE(shipper.location_name,   '')       AS shipper_name,
            COALESCE(shipper.city,            '')       AS shipper_city,
            COALESCE(shipper.state_province,  '')       AS shipper_state,
            COALESCE(consignee.location_name, '')       AS consignee_name,
            COALESCE(consignee.city,          '')       AS consignee_city,
            COALESCE(consignee.state_province,'')       AS consignee_state,
            -- transport
            COALESCE(tm.mode_code,            '')       AS transport_mode,
            COALESCE(sl.service_level_name,   '')       AS service_level,
            COALESCE(eq.equipment_name,       '')       AS equipment_type,
            COALESCE(lv_frt.display_name,     '')       AS freight_terms,
            COALESCE(lv_pri.display_name,     '')       AS priority,
            -- created by
            COALESCE(u.email,                 '')       AS created_by,
            -- line count
            (SELECT COUNT(*) FROM tms.order_release_lines orl
             WHERE orl.order_release_id = orr.order_release_id) AS line_count
        FROM tms.order_releases orr
        LEFT JOIN tms.lookup_values    lv_status  ON lv_status.lookup_value_id  = orr.status_id
        LEFT JOIN tms.lookup_values    lv_src     ON lv_src.lookup_value_id     = orr.release_source_type_id
        LEFT JOIN tms.purchase_orders  po         ON po.purchase_order_id       = orr.source_purchase_order_id
        LEFT JOIN tms.parties          customer   ON customer.party_id          = orr.customer_party_id
        LEFT JOIN tms.parties          supplier   ON supplier.party_id          = orr.supplier_party_id
        LEFT JOIN tms.parties          responsible ON responsible.party_id      = orr.responsible_party_id
        LEFT JOIN tms.locations        shipper    ON shipper.location_id        = orr.shipper_location_id
        LEFT JOIN tms.locations        consignee  ON consignee.location_id      = orr.consignee_location_id
        LEFT JOIN tms.transport_modes  tm         ON tm.transport_mode_id       = orr.transport_mode_id
        LEFT JOIN tms.service_levels   sl         ON sl.service_level_id        = orr.service_level_id
        LEFT JOIN tms.equipment_types  eq         ON eq.equipment_type_id       = orr.equipment_type_id
        LEFT JOIN tms.lookup_values    lv_frt     ON lv_frt.lookup_value_id     = orr.freight_terms_id
        LEFT JOIN tms.lookup_values    lv_pri     ON lv_pri.lookup_value_id     = orr.priority_id
        LEFT JOIN tms.app_users        u          ON u.user_id                  = orr.created_by_user_id
        WHERE {where}
        ORDER BY orr.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    count_sql = text(f"""
        SELECT COUNT(*) FROM tms.order_releases orr
        LEFT JOIN tms.lookup_values   lv_status ON lv_status.lookup_value_id = orr.status_id
        LEFT JOIN tms.purchase_orders po        ON po.purchase_order_id      = orr.source_purchase_order_id
        LEFT JOIN tms.parties         customer  ON customer.party_id         = orr.customer_party_id
        LEFT JOIN tms.parties         supplier  ON supplier.party_id         = orr.supplier_party_id
        WHERE {where}
    """)

    rows  = (await db.execute(sql, params)).mappings().all()
    total = (await db.execute(count_sql, params)).scalar()
    return {"data": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


# ── Order release detail ─────────────────────────────────────
@router.get("/{release_id}")
async def get_order_release(
    release_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sql = text("""
        SELECT
            orr.order_release_id,
            orr.order_release_number,
            orr.requested_ship_date,
            orr.requested_delivery_date,
            orr.created_at,
            orr.updated_at,
            COALESCE(lv_status.lookup_code,   'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name,  'Unknown') AS status_name,
            COALESCE(lv_src.display_name,     '')        AS release_source_type,
            COALESCE(lv_override.display_name,'')        AS override_reason,
            -- PO
            COALESCE(po.purchase_order_number,'')        AS po_number,
            COALESCE(po.purchase_order_id::text,'')      AS po_id,
            -- parties
            COALESCE(customer.party_name,    '')         AS customer_name,
            COALESCE(customer.party_code,    '')         AS customer_code,
            COALESCE(supplier.party_name,    '')         AS supplier_name,
            COALESCE(supplier.party_code,    '')         AS supplier_code,
            COALESCE(responsible.party_name, '')         AS responsible_party,
            -- locations
            COALESCE(shipper.location_name,   '')        AS shipper_name,
            COALESCE(shipper.address_line1,   '')        AS shipper_address,
            COALESCE(shipper.city,            '')        AS shipper_city,
            COALESCE(shipper.state_province,  '')        AS shipper_state,
            COALESCE(shipper.postal_code,     '')        AS shipper_zip,
            COALESCE(consignee.location_name, '')        AS consignee_name,
            COALESCE(consignee.address_line1, '')        AS consignee_address,
            COALESCE(consignee.city,          '')        AS consignee_city,
            COALESCE(consignee.state_province,'')        AS consignee_state,
            COALESCE(consignee.postal_code,   '')        AS consignee_zip,
            -- transport
            COALESCE(tm.mode_code,            '')        AS transport_mode,
            COALESCE(sl.service_level_name,   '')        AS service_level,
            COALESCE(eq.equipment_name,       '')        AS equipment_type,
            COALESCE(lv_frt.display_name,     '')        AS freight_terms,
            COALESCE(lv_pri.display_name,     '')        AS priority,
            COALESCE(lv_rule.release_rule_name,'')       AS release_rule,
            -- created by
            COALESCE(u.email,                 '')        AS created_by
        FROM tms.order_releases orr
        LEFT JOIN tms.lookup_values    lv_status   ON lv_status.lookup_value_id   = orr.status_id
        LEFT JOIN tms.lookup_values    lv_src      ON lv_src.lookup_value_id      = orr.release_source_type_id
        LEFT JOIN tms.lookup_values    lv_override ON lv_override.lookup_value_id = orr.override_reason_id
        LEFT JOIN tms.purchase_orders  po          ON po.purchase_order_id        = orr.source_purchase_order_id
        LEFT JOIN tms.parties          customer    ON customer.party_id           = orr.customer_party_id
        LEFT JOIN tms.parties          supplier    ON supplier.party_id           = orr.supplier_party_id
        LEFT JOIN tms.parties          responsible ON responsible.party_id        = orr.responsible_party_id
        LEFT JOIN tms.locations        shipper     ON shipper.location_id         = orr.shipper_location_id
        LEFT JOIN tms.locations        consignee   ON consignee.location_id       = orr.consignee_location_id
        LEFT JOIN tms.transport_modes  tm          ON tm.transport_mode_id        = orr.transport_mode_id
        LEFT JOIN tms.service_levels   sl          ON sl.service_level_id         = orr.service_level_id
        LEFT JOIN tms.equipment_types  eq          ON eq.equipment_type_id        = orr.equipment_type_id
        LEFT JOIN tms.lookup_values    lv_frt      ON lv_frt.lookup_value_id      = orr.freight_terms_id
        LEFT JOIN tms.lookup_values    lv_pri      ON lv_pri.lookup_value_id      = orr.priority_id
        LEFT JOIN tms.release_rules    lv_rule     ON lv_rule.release_rule_id     = orr.release_rule_id
        LEFT JOIN tms.app_users        u           ON u.user_id                   = orr.created_by_user_id
        WHERE orr.order_release_id = :release_id
    """)

    lines_sql = text("""
        SELECT
            orl.order_release_line_id,
            orl.line_number,
            orl.quantity,
            orl.weight_value,
            orl.cube_value,
            orl.line_value,
            orl.hazardous_flag,
            orl.temperature_requirement,
            orl.handling_instructions,
            orl.created_at,
            COALESCE(lv_status.lookup_code,  'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name, 'Unknown') AS status_name,
            COALESCE(i.item_number,          '')        AS item_number,
            COALESCE(i.item_description,     '')        AS item_description,
            COALESCE(uom.uom_code,           'EA')      AS quantity_uom,
            COALESCE(wuom.uom_code,          'KG')      AS weight_uom,
            COALESCE(cuom.uom_code,          'M3')      AS cube_uom,
            COALESCE(lv_curr.lookup_code,    'USD')     AS currency,
            COALESCE(lv_pkg.display_name,    '')        AS packaging_type,
            -- PO line linkage
            COALESCE(pol.line_number,        '')        AS po_line_number
        FROM tms.order_release_lines orl
        LEFT JOIN tms.items            i        ON i.item_id              = orl.item_id
        LEFT JOIN tms.unit_of_measures uom      ON uom.uom_id             = orl.quantity_uom_id
        LEFT JOIN tms.unit_of_measures wuom     ON wuom.uom_id            = orl.weight_uom_id
        LEFT JOIN tms.unit_of_measures cuom     ON cuom.uom_id            = orl.cube_uom_id
        LEFT JOIN tms.lookup_values    lv_curr  ON lv_curr.lookup_value_id = orl.currency_id
        LEFT JOIN tms.lookup_values    lv_status ON lv_status.lookup_value_id = orl.status_id
        LEFT JOIN tms.lookup_values    lv_pkg   ON lv_pkg.lookup_value_id  = orl.packaging_type_id
        LEFT JOIN tms.purchase_order_lines pol  ON pol.purchase_order_line_id = orl.purchase_order_line_id
        WHERE orl.order_release_id = :release_id
        ORDER BY orl.line_number::integer
    """)

    events_sql = text("""
        SELECT
            re.release_event_id,
            re.event_timestamp,
            re.quantity,
            re.notes,
            re.metadata_json,
            COALESCE(lv_type.display_name,   'Event')  AS event_type,
            COALESCE(lv_ch.display_name,     '')        AS source_channel,
            COALESCE(u.email,                '')        AS created_by
        FROM tms.release_events re
        LEFT JOIN tms.lookup_values lv_type ON lv_type.lookup_value_id = re.event_type_id
        LEFT JOIN tms.lookup_values lv_ch   ON lv_ch.lookup_value_id   = re.source_channel_id
        LEFT JOIN tms.app_users     u       ON u.user_id                = re.created_by_user_id
        WHERE re.order_release_id = :release_id
        ORDER BY re.event_timestamp DESC
    """)

    # linked shipments
    shipments_sql = text("""
        SELECT
            s.shipment_id,
            s.shipment_number,
            COALESCE(lv.lookup_code,  'UNKNOWN') AS status_code,
            COALESCE(lv.display_name, 'Unknown') AS status_name,
            s.planned_pickup_datetime,
            s.planned_delivery_datetime
        FROM tms.shipment_order_releases sor
        JOIN tms.shipments s ON s.shipment_id = sor.shipment_id
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = s.shipment_status_id
        WHERE sor.order_release_id = :release_id
        ORDER BY s.created_at DESC
    """)

    row = (await db.execute(sql, {"release_id": release_id})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Order release not found")

    lines     = (await db.execute(lines_sql,     {"release_id": release_id})).mappings().all()
    events    = (await db.execute(events_sql,    {"release_id": release_id})).mappings().all()
    shipments = (await db.execute(shipments_sql, {"release_id": release_id})).mappings().all()

    return {
        "order_release": dict(row),
        "lines":     [dict(r) for r in lines],
        "events":    [dict(r) for r in events],
        "shipments": [dict(r) for r in shipments],
    }


from pydantic import BaseModel
from typing import Optional

class OrderReleaseCreate(BaseModel):
    source_purchase_order_id: Optional[str] = None
    customer_party_id: Optional[str] = None
    supplier_party_id: Optional[str] = None
    shipper_location_id: Optional[str] = None
    consignee_location_id: Optional[str] = None
    requested_ship_date: Optional[str] = None
    requested_delivery_date: Optional[str] = None
    transport_mode_id: Optional[str] = None
    service_level_id: Optional[str] = None
    freight_terms_id: Optional[str] = None
    priority: Optional[str] = "Medium"
    notes: Optional[str] = None

class OrderReleaseUpdate(BaseModel):
    requested_ship_date: Optional[str] = None
    requested_delivery_date: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    override_reason: Optional[str] = None

@router.post("/", status_code=201)
async def create_order_release(
    payload: OrderReleaseCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new order release."""
    from datetime import datetime
    user_id = user.get("email", "system")
    # Generate release number
    result = await db.execute(text("""
        SELECT COUNT(*) FROM tms.order_releases
    """))
    count = result.scalar() or 0
    release_number = f"REL-{datetime.utcnow().strftime('%Y')}-{str(count + 1).zfill(4)}"

    # Get DRAFT status
    status_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values
        WHERE UPPER(lookup_code) = 'DRAFT' LIMIT 1
    """))
    status_id = status_result.scalar()

    rel_result = await db.execute(text("""
        INSERT INTO tms.order_releases
            (order_release_number, source_purchase_order_id,
             customer_party_id, supplier_party_id,
             shipper_location_id, consignee_location_id,
             requested_ship_date, requested_delivery_date,
             transport_mode_id, service_level_id,
             freight_terms_id, release_status_id)
        VALUES
            (:release_number, CAST(:po_id AS uuid),
             CAST(:customer_id AS uuid), CAST(:supplier_id AS uuid),
             CAST(:shipper_id AS uuid), CAST(:consignee_id AS uuid),
             CAST(:ship_date AS date), CAST(:delivery_date AS date),
             CAST(:mode_id AS uuid), CAST(:service_id AS uuid),
             CAST(:terms_id AS uuid), CAST(:status_id AS uuid))
        RETURNING order_release_id, order_release_number
    """), {
        "release_number":  release_number,
        "po_id":           payload.source_purchase_order_id,
        "customer_id":     payload.customer_party_id,
        "supplier_id":     payload.supplier_party_id,
        "shipper_id":      payload.shipper_location_id,
        "consignee_id":    payload.consignee_location_id,
        "ship_date":       payload.requested_ship_date,
        "delivery_date":   payload.requested_delivery_date,
        "mode_id":         payload.transport_mode_id,
        "service_id":      payload.service_level_id,
        "terms_id":        payload.freight_terms_id,
        "status_id":       str(status_id) if status_id else None,
    })
    await db.commit()
    row = dict(rel_result.mappings().one())
    return {"order_release_id": str(row["order_release_id"]),
            "order_release_number": row["order_release_number"],
            "status": "DRAFT"}


@router.patch("/{release_id}")
async def update_order_release(
    release_id: str,
    payload: OrderReleaseUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update an order release."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        from fastapi import HTTPException
        raise HTTPException(400, "No fields to update.")
    set_parts = []
    params: dict = {"id": release_id}
    for k, v in updates.items():
        if k in ("requested_ship_date", "requested_delivery_date") and v:
            set_parts.append(f"{k} = CAST(:{k} AS date)")
        else:
            set_parts.append(f"{k} = :{k}")
        params[k] = v
    set_parts.append("updated_at = NOW()")
    result = await db.execute(text(f"""
        UPDATE tms.order_releases SET {', '.join(set_parts)}
        WHERE order_release_id = CAST(:id AS uuid)
        RETURNING order_release_id, updated_at
    """), params)
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Release not found.")
    return dict(row)
