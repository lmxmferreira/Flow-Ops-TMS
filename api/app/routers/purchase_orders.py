from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional

router = APIRouter()

# ── List POs ─────────────────────────────────────────────────
@router.get("/")
async def list_purchase_orders(
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
            "(po.purchase_order_number ILIKE :search "
            "OR supplier.party_name ILIKE :search "
            "OR buyer.party_name ILIKE :search "
            "OR po.source_reference ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    if status:
        filters.append("lv_status.lookup_code = :status")
        params["status"] = status

    where = " AND ".join(filters)

    sql = text(f"""
        SELECT
            po.purchase_order_id,
            po.purchase_order_number,
            po.source_reference,
            po.requested_ship_date,
            po.requested_delivery_date,
            po.hold_flag,
            po.version_number,
            po.created_at,
            po.updated_at,
            -- status
            COALESCE(lv_status.lookup_code,  'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name, 'Unknown') AS status_name,
            -- po type
            COALESCE(lv_type.display_name, '') AS po_type,
            -- parties
            COALESCE(supplier.party_name, '') AS supplier_name,
            COALESCE(buyer.party_name,    '') AS buyer_name,
            -- locations
            COALESCE(ship_from.location_name, '') AS ship_from_name,
            COALESCE(ship_from.city,          '') AS ship_from_city,
            COALESCE(ship_from.state_province,'') AS ship_from_state,
            COALESCE(ship_to.location_name,   '') AS ship_to_name,
            COALESCE(ship_to.city,            '') AS ship_to_city,
            COALESCE(ship_to.state_province,  '') AS ship_to_state,
            -- terms & finance
            COALESCE(lv_inco.display_name,   '') AS incoterm,
            COALESCE(lv_frt.display_name,    '') AS freight_terms,
            COALESCE(lv_curr.lookup_code,    'USD') AS currency,
            COALESCE(lv_pay.display_name,    '') AS payment_terms,
            COALESCE(lv_pri.display_name,    '') AS priority,
            COALESCE(lv_hold.display_name,   '') AS hold_reason,
            -- org
            COALESCE(bu.business_unit_name,  '') AS business_unit,
            COALESCE(proj.project_name,      '') AS project,
            COALESCE(cc.cost_center_name,    '') AS cost_center,
            COALESCE(ext.system_name,        '') AS source_system,
            -- line count
            (SELECT COUNT(*) FROM tms.purchase_order_lines pol
             WHERE pol.purchase_order_id = po.purchase_order_id) AS line_count
        FROM tms.purchase_orders po
        LEFT JOIN tms.lookup_values  lv_status ON lv_status.lookup_value_id = po.status_id
        LEFT JOIN tms.lookup_values  lv_type   ON lv_type.lookup_value_id   = po.purchase_order_type_id
        LEFT JOIN tms.parties        supplier  ON supplier.party_id          = po.supplier_party_id
        LEFT JOIN tms.parties        buyer     ON buyer.party_id             = po.buyer_party_id
        LEFT JOIN tms.locations      ship_from ON ship_from.location_id      = po.ship_from_location_id
        LEFT JOIN tms.locations      ship_to   ON ship_to.location_id        = po.ship_to_location_id
        LEFT JOIN tms.lookup_values  lv_inco   ON lv_inco.lookup_value_id   = po.incoterm_id
        LEFT JOIN tms.lookup_values  lv_frt    ON lv_frt.lookup_value_id    = po.freight_terms_id
        LEFT JOIN tms.lookup_values  lv_curr   ON lv_curr.lookup_value_id   = po.currency_id
        LEFT JOIN tms.lookup_values  lv_pay    ON lv_pay.lookup_value_id    = po.payment_terms_id
        LEFT JOIN tms.lookup_values  lv_pri    ON lv_pri.lookup_value_id    = po.priority_id
        LEFT JOIN tms.lookup_values  lv_hold   ON lv_hold.lookup_value_id   = po.hold_reason_id
        LEFT JOIN tms.business_units bu        ON bu.business_unit_id       = po.owning_business_unit_id
        LEFT JOIN tms.projects       proj      ON proj.project_id           = po.project_id
        LEFT JOIN tms.cost_centers   cc        ON cc.cost_center_id         = po.cost_center_id
        LEFT JOIN tms.external_systems ext     ON ext.external_system_id    = po.source_system_id
        WHERE {where}
        ORDER BY po.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    count_sql = text(f"""
        SELECT COUNT(*) FROM tms.purchase_orders po
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = po.status_id
        LEFT JOIN tms.parties supplier ON supplier.party_id = po.supplier_party_id
        LEFT JOIN tms.parties buyer    ON buyer.party_id    = po.buyer_party_id
        WHERE {where}
    """)

    rows  = (await db.execute(sql, params)).mappings().all()
    total = (await db.execute(count_sql, params)).scalar()
    return {"data": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


# ── PO Detail ────────────────────────────────────────────────
@router.get("/{po_id}")
async def get_purchase_order(
    po_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    po_sql = text("""
        SELECT
            po.purchase_order_id,
            po.purchase_order_number,
            po.source_reference,
            po.requested_ship_date,
            po.requested_delivery_date,
            po.hold_flag,
            po.version_number,
            po.created_at,
            po.updated_at,
            COALESCE(lv_status.lookup_code,  'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name, 'Unknown') AS status_name,
            COALESCE(lv_type.display_name,   '')        AS po_type,
            COALESCE(supplier.party_name,    '')        AS supplier_name,
            COALESCE(supplier.party_code,    '')        AS supplier_code,
            COALESCE(supplier.tax_identifier,'')        AS supplier_tax_id,
            COALESCE(buyer.party_name,       '')        AS buyer_name,
            COALESCE(buyer.party_code,       '')        AS buyer_code,
            COALESCE(ship_from.location_name,'')        AS ship_from_name,
            COALESCE(ship_from.address_line1,'')        AS ship_from_address,
            COALESCE(ship_from.city,         '')        AS ship_from_city,
            COALESCE(ship_from.state_province,'')       AS ship_from_state,
            COALESCE(ship_from.postal_code,  '')        AS ship_from_zip,
            COALESCE(ship_from.country_id::text,'')     AS ship_from_country,
            COALESCE(ship_to.location_name,  '')        AS ship_to_name,
            COALESCE(ship_to.address_line1,  '')        AS ship_to_address,
            COALESCE(ship_to.city,           '')        AS ship_to_city,
            COALESCE(ship_to.state_province, '')        AS ship_to_state,
            COALESCE(ship_to.postal_code,    '')        AS ship_to_zip,
            COALESCE(ship_to.country_id::text,'')       AS ship_to_country,
            COALESCE(lv_inco.display_name,   '')        AS incoterm,
            COALESCE(lv_frt.display_name,    '')        AS freight_terms,
            COALESCE(lv_curr.lookup_code,    'USD')     AS currency,
            COALESCE(lv_pay.display_name,    '')        AS payment_terms,
            COALESCE(lv_pri.display_name,    '')        AS priority,
            COALESCE(lv_hold.display_name,   '')        AS hold_reason,
            COALESCE(bu.business_unit_name,  '')        AS business_unit,
            COALESCE(proj.project_name,      '')        AS project,
            COALESCE(cc.cost_center_name,    '')        AS cost_center,
            COALESCE(ext.system_name,        '')        AS source_system
        FROM tms.purchase_orders po
        LEFT JOIN tms.lookup_values   lv_status ON lv_status.lookup_value_id = po.status_id
        LEFT JOIN tms.lookup_values   lv_type   ON lv_type.lookup_value_id   = po.purchase_order_type_id
        LEFT JOIN tms.parties         supplier  ON supplier.party_id          = po.supplier_party_id
        LEFT JOIN tms.parties         buyer     ON buyer.party_id             = po.buyer_party_id
        LEFT JOIN tms.locations       ship_from ON ship_from.location_id      = po.ship_from_location_id
        LEFT JOIN tms.locations       ship_to   ON ship_to.location_id        = po.ship_to_location_id
        LEFT JOIN tms.lookup_values   lv_inco   ON lv_inco.lookup_value_id   = po.incoterm_id
        LEFT JOIN tms.lookup_values   lv_frt    ON lv_frt.lookup_value_id    = po.freight_terms_id
        LEFT JOIN tms.lookup_values   lv_curr   ON lv_curr.lookup_value_id   = po.currency_id
        LEFT JOIN tms.lookup_values   lv_pay    ON lv_pay.lookup_value_id    = po.payment_terms_id
        LEFT JOIN tms.lookup_values   lv_pri    ON lv_pri.lookup_value_id    = po.priority_id
        LEFT JOIN tms.lookup_values   lv_hold   ON lv_hold.lookup_value_id   = po.hold_reason_id
        LEFT JOIN tms.business_units  bu        ON bu.business_unit_id       = po.owning_business_unit_id
        LEFT JOIN tms.projects        proj      ON proj.project_id           = po.project_id
        LEFT JOIN tms.cost_centers    cc        ON cc.cost_center_id         = po.cost_center_id
        LEFT JOIN tms.external_systems ext      ON ext.external_system_id    = po.source_system_id
        WHERE po.purchase_order_id = :po_id
    """)

    lines_sql = text("""
        SELECT
            pol.purchase_order_line_id,
            pol.line_number,
            pol.item_description,
            pol.ordered_quantity,
            pol.releasable_quantity,
            pol.released_quantity,
            pol.planned_quantity,
            pol.shipped_quantity,
            pol.delivered_quantity,
            pol.received_quantity,
            pol.canceled_quantity,
            pol.remaining_quantity,
            pol.weight_value,
            pol.volume_value,
            pol.line_value,
            pol.hazardous_flag,
            pol.temperature_requirement,
            pol.requested_ship_date,
            pol.requested_delivery_date,
            pol.hold_flag,
            COALESCE(i.item_number,          '')    AS item_number,
            COALESCE(i.item_description,     '')    AS item_name,
            COALESCE(lv_uom.uom_code, 'EA')  AS quantity_uom,
            COALESCE(lv_wuom.uom_code, 'KG')  AS weight_uom,
            COALESCE(lv_vuom.uom_code, 'M3')  AS volume_uom,
            COALESCE(lv_curr.lookup_code,    'USD') AS currency,
            COALESCE(lv_status.lookup_code,  'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name, 'Unknown') AS status_name,
            COALESCE(lv_fc.display_name,     '')    AS freight_class,
            COALESCE(lv_pkg.display_name,    '')    AS packaging_type,
            COALESCE(lv_hold.display_name,   '')    AS hold_reason
        FROM tms.purchase_order_lines pol
        LEFT JOIN tms.items           i         ON i.item_id             = pol.item_id
        LEFT JOIN tms.unit_of_measures lv_uom   ON lv_uom.uom_id        = pol.quantity_uom_id
        LEFT JOIN tms.unit_of_measures lv_wuom  ON lv_wuom.uom_id       = pol.weight_uom_id
        LEFT JOIN tms.unit_of_measures lv_vuom  ON lv_vuom.uom_id       = pol.volume_uom_id
        LEFT JOIN tms.lookup_values   lv_curr   ON lv_curr.lookup_value_id = pol.currency_id
        LEFT JOIN tms.lookup_values   lv_status ON lv_status.lookup_value_id = pol.status_id
        LEFT JOIN tms.lookup_values   lv_fc     ON lv_fc.lookup_value_id  = pol.freight_class_id
        LEFT JOIN tms.lookup_values   lv_pkg    ON lv_pkg.lookup_value_id = pol.packaging_type_id
        LEFT JOIN tms.lookup_values   lv_hold   ON lv_hold.lookup_value_id = pol.hold_reason_id
        WHERE pol.purchase_order_id = :po_id
        ORDER BY pol.line_number::integer
    """)

    versions_sql = text("""
        SELECT
            pov.purchase_order_version_id,
            pov.version_number,
            pov.created_at,
            COALESCE(lv.display_name, '') AS change_reason,
            COALESCE(u.email, '')         AS created_by
        FROM tms.purchase_order_versions pov
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = pov.change_reason_id
        LEFT JOIN tms.app_users     u  ON u.user_id          = pov.created_by_user_id
        WHERE pov.purchase_order_id = :po_id
        ORDER BY pov.version_number DESC
    """)

    po = (await db.execute(po_sql, {"po_id": po_id})).mappings().first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    lines    = (await db.execute(lines_sql,    {"po_id": po_id})).mappings().all()
    versions = (await db.execute(versions_sql, {"po_id": po_id})).mappings().all()

    return {
        "purchase_order": dict(po),
        "lines":    [dict(r) for r in lines],
        "versions": [dict(r) for r in versions],
    }


from pydantic import BaseModel

# ── Update PO ─────────────────────────────────────────────────
class POUpdate(BaseModel):
    requested_ship_date:     str | None = None
    requested_delivery_date: str | None = None
    source_reference:        str | None = None
    hold_flag:               bool | None = None

@router.patch("/{po_id}")
async def update_purchase_order(
    po_id: str,
    payload: POUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    set_parts = []
    params: dict = {"po_id": po_id}
    for k, v in updates.items():
        if k in ("requested_ship_date", "requested_delivery_date") and v is not None:
            set_parts.append(f"{k} = :{k}::date")
        else:
            set_parts.append(f"{k} = :{k}")
        params[k] = v
    set_clause = ", ".join(set_parts)
    result = await db.execute(
        text(f"""
            UPDATE tms.purchase_orders
            SET {set_clause}, updated_at = NOW()
            WHERE purchase_order_id = :po_id::uuid
            RETURNING purchase_order_id, purchase_order_number, updated_at
        """),
        params
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return dict(row)
