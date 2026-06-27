from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

# ── Edit model ────────────────────────────────────────────────
class ShipmentUpdate(BaseModel):
    shipment_status_id: Optional[str] = None
    carrier_id: Optional[str] = None
    transport_mode_id: Optional[str] = None
    service_level_id: Optional[str] = None
    equipment_type_id: Optional[str] = None
    origin_location_id: Optional[str] = None
    destination_location_id: Optional[str] = None
    customer_party_id: Optional[str] = None
    supplier_party_id: Optional[str] = None
    financial_owner_party_id: Optional[str] = None
    freight_terms_id: Optional[str] = None
    planned_pickup_datetime: Optional[str] = None
    planned_delivery_datetime: Optional[str] = None
    actual_pickup_datetime: Optional[str] = None
    actual_delivery_datetime: Optional[str] = None
    total_weight: Optional[float] = None
    total_volume: Optional[float] = None
    pallet_count: Optional[float] = None
    carton_count: Optional[float] = None
    unit_count: Optional[float] = None
    linear_feet: Optional[float] = None
    distance_value: Optional[float] = None
    chargeable_weight: Optional[float] = None
    closeout_completed_flag: Optional[bool] = None

# ── List shipments ────────────────────────────────────────────
@router.get("/")
async def list_shipments(
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
        filters.append("(s.shipment_number ILIKE :search OR origin.city ILIKE :search OR dest.city ILIKE :search OR cp_carrier.party_name ILIKE :search OR po.purchase_order_number ILIKE :search)")
        params["search"] = f"%{search}%"
    if status:
        filters.append("lv_status.lookup_code = :status")
        params["status"] = status

    where = " AND ".join(filters)
    sql = text(f"""
        SELECT
            s.shipment_id, s.shipment_number, s.total_weight, s.pallet_count, s.carton_count, s.created_at,
            COALESCE(lv_status.lookup_code,'UNKNOWN')    AS status_code,
            COALESCE(lv_status.display_name,'Unknown')   AS status_name,
            COALESCE(cp_carrier.party_name,'Unassigned') AS carrier_name,
            COALESCE(origin.location_name,'')  AS origin_name,
            COALESCE(origin.city,'')           AS origin_city,
            COALESCE(origin.state_province,'') AS origin_state,
            COALESCE(dest.location_name,'')    AS destination_name,
            COALESCE(dest.city,'')             AS destination_city,
            COALESCE(dest.state_province,'')   AS destination_state,
            COALESCE(tm.mode_code,'')          AS transport_mode,
            s.planned_pickup_datetime, s.planned_delivery_datetime,
            MIN(po.purchase_order_number)      AS po_number,
            MIN(po.purchase_order_id::text)    AS po_id,
            COUNT(DISTINCT po.purchase_order_id) AS po_count
        FROM tms.shipments s
        LEFT JOIN tms.lookup_values   lv_status  ON lv_status.lookup_value_id  = s.shipment_status_id
        LEFT JOIN tms.carriers        c          ON c.carrier_id               = s.carrier_id
        LEFT JOIN tms.parties         cp_carrier ON cp_carrier.party_id        = c.party_id
        LEFT JOIN tms.locations       origin     ON origin.location_id         = s.origin_location_id
        LEFT JOIN tms.locations       dest       ON dest.location_id           = s.destination_location_id
        LEFT JOIN tms.transport_modes tm         ON tm.transport_mode_id       = s.transport_mode_id
        LEFT JOIN tms.shipment_order_releases sor ON sor.shipment_id           = s.shipment_id
        LEFT JOIN tms.order_releases  orr        ON orr.order_release_id       = sor.order_release_id
        LEFT JOIN tms.purchase_orders po         ON po.purchase_order_id       = orr.source_purchase_order_id
        WHERE {where}
        GROUP BY s.shipment_id, s.shipment_number, s.total_weight, s.pallet_count, s.carton_count, s.created_at,
                 lv_status.lookup_code, lv_status.display_name, cp_carrier.party_name,
                 origin.location_name, origin.city, origin.state_province,
                 dest.location_name, dest.city, dest.state_province, tm.mode_code,
                 s.planned_pickup_datetime, s.planned_delivery_datetime
        ORDER BY s.created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    count_sql = text(f"""
        SELECT COUNT(DISTINCT s.shipment_id) FROM tms.shipments s
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = s.shipment_status_id
        LEFT JOIN tms.carriers c ON c.carrier_id = s.carrier_id
        LEFT JOIN tms.parties cp_carrier ON cp_carrier.party_id = c.party_id
        LEFT JOIN tms.locations origin ON origin.location_id = s.origin_location_id
        LEFT JOIN tms.locations dest ON dest.location_id = s.destination_location_id
        LEFT JOIN tms.shipment_order_releases sor ON sor.shipment_id = s.shipment_id
        LEFT JOIN tms.order_releases orr ON orr.order_release_id = sor.order_release_id
        LEFT JOIN tms.purchase_orders po ON po.purchase_order_id = orr.source_purchase_order_id
        WHERE {where}
    """)
    rows  = (await db.execute(sql, params)).mappings().all()
    total = (await db.execute(count_sql, params)).scalar()
    return {"data": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}

# ── Status filter options ─────────────────────────────────────
@router.get("/statuses")
async def list_statuses(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sql = text("""
        SELECT DISTINCT COALESCE(lv.lookup_code,'UNKNOWN') AS status_code,
               COALESCE(lv.display_name,'Unknown') AS status_name
        FROM tms.shipments s
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = s.shipment_status_id
        ORDER BY status_name
    """)
    rows = (await db.execute(sql)).mappings().all()
    return {"data": [dict(r) for r in rows]}

# ── Shipment detail — ALL columns ────────────────────────────
@router.get("/{shipment_id}")
async def get_shipment(shipment_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sql = text("""
        SELECT
            s.shipment_id, s.shipment_number, s.closeout_completed_flag,
            s.total_weight, s.total_volume, s.pallet_count, s.carton_count,
            s.unit_count, s.linear_feet, s.distance_value, s.chargeable_weight,
            s.planned_pickup_datetime, s.planned_delivery_datetime,
            s.actual_pickup_datetime, s.actual_delivery_datetime,
            s.created_at, s.updated_at,
            -- FK raw IDs (for edit form)
            s.shipment_status_id, s.shipment_type_id, s.carrier_id,
            s.transport_mode_id, s.service_level_id, s.equipment_type_id,
            s.origin_location_id, s.destination_location_id,
            s.customer_party_id, s.supplier_party_id, s.financial_owner_party_id,
            s.freight_terms_id, s.currency_id, s.distance_uom_id,
            -- Resolved display values
            COALESCE(lv_status.lookup_code,'UNKNOWN')    AS status_code,
            COALESCE(lv_status.display_name,'Unknown')   AS status_name,
            COALESCE(lv_type.display_name,'')            AS shipment_type,
            COALESCE(cp_carrier.party_name,'Unassigned') AS carrier_name,
            COALESCE(tm.mode_code,'')                    AS transport_mode,
            COALESCE(sl.service_level_name,'')           AS service_level,
            COALESCE(eq.equipment_name,'')               AS equipment_type,
            COALESCE(lv_frt.display_name,'')             AS freight_terms,
            COALESCE(lv_curr.lookup_code,'USD')          AS currency,
            COALESCE(lv_duom.lookup_code,'')             AS distance_uom,
            COALESCE(origin.location_name,'')            AS origin_name,
            COALESCE(origin.location_code,'')            AS origin_code,
            COALESCE(origin.address_line1,'')            AS origin_address,
            COALESCE(origin.city,'')                     AS origin_city,
            COALESCE(origin.state_province,'')           AS origin_state,
            COALESCE(origin.postal_code,'')              AS origin_zip,
            COALESCE(dest.location_name,'')              AS destination_name,
            COALESCE(dest.location_code,'')              AS destination_code,
            COALESCE(dest.address_line1,'')              AS destination_address,
            COALESCE(dest.city,'')                       AS destination_city,
            COALESCE(dest.state_province,'')             AS destination_state,
            COALESCE(dest.postal_code,'')                AS destination_zip,
            COALESCE(cust.party_name,'')                 AS customer_name,
            COALESCE(supp.party_name,'')                 AS supplier_name,
            COALESCE(fin.party_name,'')                  AS financial_owner_name
        FROM tms.shipments s
        LEFT JOIN tms.lookup_values   lv_status ON lv_status.lookup_value_id  = s.shipment_status_id
        LEFT JOIN tms.lookup_values   lv_type   ON lv_type.lookup_value_id    = s.shipment_type_id
        LEFT JOIN tms.lookup_values   lv_frt    ON lv_frt.lookup_value_id     = s.freight_terms_id
        LEFT JOIN tms.lookup_values   lv_curr   ON lv_curr.lookup_value_id    = s.currency_id
        LEFT JOIN tms.lookup_values   lv_duom   ON lv_duom.lookup_value_id    = s.distance_uom_id
        LEFT JOIN tms.carriers        c         ON c.carrier_id               = s.carrier_id
        LEFT JOIN tms.parties         cp_carrier ON cp_carrier.party_id       = c.party_id
        LEFT JOIN tms.transport_modes tm        ON tm.transport_mode_id       = s.transport_mode_id
        LEFT JOIN tms.service_levels  sl        ON sl.service_level_id        = s.service_level_id
        LEFT JOIN tms.equipment_types eq        ON eq.equipment_type_id       = s.equipment_type_id
        LEFT JOIN tms.locations       origin    ON origin.location_id         = s.origin_location_id
        LEFT JOIN tms.locations       dest      ON dest.location_id           = s.destination_location_id
        LEFT JOIN tms.parties         cust      ON cust.party_id              = s.customer_party_id
        LEFT JOIN tms.parties         supp      ON supp.party_id              = s.supplier_party_id
        LEFT JOIN tms.parties         fin       ON fin.party_id               = s.financial_owner_party_id
        WHERE s.shipment_id = :id
    """)
    po_sql = text("""
        SELECT po.purchase_order_id, po.purchase_order_number, po.hold_flag,
               COALESCE(lv.display_name,'Unknown') AS status_name,
               COALESCE(lv.lookup_code,'UNKNOWN')  AS status_code,
               COALESCE(sup.party_name,'')          AS supplier_name,
               po.requested_ship_date, po.requested_delivery_date,
               orr.order_release_number
        FROM tms.shipment_order_releases sor
        JOIN tms.order_releases  orr ON orr.order_release_id    = sor.order_release_id
        JOIN tms.purchase_orders po  ON po.purchase_order_id    = orr.source_purchase_order_id
        LEFT JOIN tms.lookup_values lv  ON lv.lookup_value_id  = po.status_id
        LEFT JOIN tms.parties       sup ON sup.party_id         = po.supplier_party_id
        WHERE sor.shipment_id = :id ORDER BY po.purchase_order_number
    """)
    row = (await db.execute(sql, {"id": shipment_id})).mappings().first()
    if not row:
        raise HTTPException(404, "Shipment not found")
    pos = (await db.execute(po_sql, {"id": shipment_id})).mappings().all()
    return {"shipment": dict(row), "purchase_orders": [dict(p) for p in pos]}

# ── Edit shipment ─────────────────────────────────────────────
@router.patch("/{shipment_id}")
async def update_shipment(
    shipment_id: str,
    body: ShipmentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = ["updated_at = now()"]
    params: dict = {"id": shipment_id}
    uuid_fields = [
        "shipment_status_id","carrier_id","transport_mode_id","service_level_id",
        "equipment_type_id","origin_location_id","destination_location_id",
        "customer_party_id","supplier_party_id","financial_owner_party_id","freight_terms_id",
    ]
    scalar_fields = [
        "planned_pickup_datetime","planned_delivery_datetime",
        "actual_pickup_datetime","actual_delivery_datetime",
        "total_weight","total_volume","pallet_count","carton_count",
        "unit_count","linear_feet","distance_value","chargeable_weight","closeout_completed_flag",
    ]
    for f in uuid_fields:
        v = getattr(body, f)
        if v is not None:
            sets.append(f"{f} = :{f}::uuid"); params[f] = v
    for f in scalar_fields:
        v = getattr(body, f)
        if v is not None:
            sets.append(f"{f} = :{f}"); params[f] = v

    if len(sets) == 1:
        raise HTTPException(400, "Nothing to update")

    await db.execute(
        text(f"UPDATE tms.shipments SET {', '.join(sets)} WHERE shipment_id = :id"),
        params
    )
    await db.commit()
    return {"ok": True}

@router.get("/{shipment_id}/stops")
async def get_shipment_stops(shipment_id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    from sqlalchemy import text
    sql = text("""
        SELECT
            ss.shipment_stop_id, ss.stop_sequence, ss.stop_type_id,
            ss.planned_arrival_datetime, ss.actual_arrival_datetime,
            ss.planned_departure_datetime, ss.actual_departure_datetime,
            ss.appointment_datetime, ss.instructions, ss.stop_status_id,
            ss.dwell_minutes, ss.detention_minutes, ss.late_minutes,
            l.location_name, l.location_code, l.address_line1,
            l.city, l.state_province, l.postal_code,
            l.latitude, l.longitude,
            COALESCE(lv_type.display_name, 'Stop') AS stop_type,
            COALESCE(lv_status.display_name, 'Pending') AS stop_status
        FROM tms.shipment_stops ss
        LEFT JOIN tms.locations l ON l.location_id = ss.location_id
        LEFT JOIN tms.lookup_values lv_type ON lv_type.lookup_value_id = ss.stop_type_id
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = ss.stop_status_id
        WHERE ss.shipment_id = CAST(:id AS uuid)
        ORDER BY ss.stop_sequence
    """)
    result = await db.execute(sql, {"id": shipment_id})
    return {"stops": [dict(r) for r in result.mappings().all()]}
