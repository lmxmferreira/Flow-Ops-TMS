"""
routers/master_data.py
TMS-MD-001 through TMS-MD-010: Master Data Management
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

class LocationMasterUpdate(BaseModel):
    location_subtype: Optional[str] = None
    operating_hours_start: Optional[str] = None
    operating_hours_end: Optional[str] = None
    operating_days: Optional[list[str]] = None
    appointment_required: Optional[bool] = None
    appointment_lead_hrs: Optional[int] = None
    dock_count: Optional[int] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    equipment_restrictions: Optional[list[str]] = None
    accessorial_rules: Optional[dict] = None
    special_instructions: Optional[str] = None
    is_active: Optional[bool] = None

class LocationCreate(BaseModel):
    location_code: str
    location_name: str
    location_subtype: str = "warehouse"
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    time_zone: Optional[str] = None
    operating_hours_start: Optional[str] = None
    operating_hours_end: Optional[str] = None
    operating_days: Optional[list[str]] = None
    appointment_required: bool = False
    dock_count: Optional[int] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    special_instructions: Optional[str] = None

class AliasCreate(BaseModel):
    alias_type: str = "alias"
    alias_value: str
    source_system: Optional[str] = None
    party_id: Optional[str] = None

class ItemCreate(BaseModel):
    item_number: str
    description: str
    weight_kg: Optional[float] = None
    weight_lb: Optional[float] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    freight_class: Optional[str] = None
    nmfc_code: Optional[str] = None
    commodity_code: Optional[str] = None
    commodity_desc: Optional[str] = None
    is_hazmat: bool = False
    hazmat_class: Optional[str] = None
    hazmat_un_number: Optional[str] = None
    requires_temp_ctrl: bool = False
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    packaging_type: Optional[str] = None
    units_per_pallet: Optional[int] = None
    is_stackable: bool = True
    base_uom: str = "EA"
    effective_date: Optional[str] = None

class ItemUpdate(BaseModel):
    description: Optional[str] = None
    weight_kg: Optional[float] = None
    freight_class: Optional[str] = None
    is_hazmat: Optional[bool] = None
    requires_temp_ctrl: Optional[bool] = None
    packaging_type: Optional[str] = None
    is_stackable: Optional[bool] = None
    is_active: Optional[bool] = None

class ChargeCodeCreate(BaseModel):
    charge_code: str
    charge_name: str
    charge_category: str = "freight"
    applies_to: str = "both"
    gl_account_code: Optional[str] = None
    billing_category: Optional[str] = None
    audit_rule_code: Optional[str] = None
    allocation_rule: Optional[str] = None
    tax_rule_code: Optional[str] = None
    external_code_edi: Optional[str] = None
    external_code_erp: Optional[str] = None
    effective_date: Optional[str] = None

class BulkImportRequest(BaseModel):
    entity_type: str  # location | item | charge_code
    records: list[dict]
    validate_only: bool = False
    update_existing: bool = False

class ApproveRequest(BaseModel):
    notes: Optional[str] = None


# ── MD-001/002: Locations ─────────────────────────────────────────

@router.get("/locations")
async def list_locations(
    db: AsyncSession = Depends(get_db),
    location_subtype: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    country_id: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if location_subtype:
        conditions.append("l.location_subtype = :subtype")
        params["subtype"] = location_subtype
    if city:
        conditions.append("l.city ILIKE :city")
        params["city"] = f"%{city}%"
    if country_id:
        conditions.append("l.country_id = CAST(:country_id AS uuid)")
        params["country_id"] = country_id
    result = await db.execute(text(f"""
        SELECT l.*,
               p.party_name, p.party_code
        FROM tms.locations l
        LEFT JOIN tms.parties p ON p.party_id = l.party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY l.location_name
        LIMIT :limit OFFSET :offset
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/locations", status_code=201)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        INSERT INTO tms.locations
            (location_code, location_name, location_subtype,
             address_line1, address_line2, city, state_province,
             postal_code, country_id, latitude, longitude, time_zone,
             operating_hours_start, operating_hours_end, operating_days,
             appointment_required, dock_count,
             contact_name, contact_phone, contact_email, special_instructions)
        VALUES
            (:location_code, :location_name, :location_subtype,
             :address_line1, :address_line2, :city, :state_province,
             :postal_code, CAST(:country_id AS uuid),
             CAST(:latitude AS numeric), CAST(:longitude AS numeric), :time_zone,
             CAST(:operating_hours_start AS time), CAST(:operating_hours_end AS time),
             :operating_days, :appointment_required, :dock_count,
             :contact_name, :contact_phone, :contact_email, :special_instructions)
        RETURNING location_id, location_code, location_name
    """), {**payload.model_dump(), "operating_days": payload.operating_days or []})
    await db.commit()
    row = dict(result.mappings().one())
    # Log audit
    await _audit_log(db, "location", str(row["location_id"]), "created", None, 1, user_id=user_id)
    await db.commit()
    return row


@router.get("/locations/{location_id}")
async def get_location(
    location_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT l.*, p.party_name, p.party_code
        FROM tms.locations l
        LEFT JOIN tms.parties p ON p.party_id = l.party_id
        WHERE l.location_id = CAST(:id AS uuid)
    """), {"id": location_id})
    loc = result.mappings().one_or_none()
    if not loc:
        raise HTTPException(404, "Location not found.")
    loc = dict(loc)

    aliases_result = await db.execute(text("""
        SELECT * FROM tms.location_aliases WHERE location_id = CAST(:id AS uuid) AND is_active = TRUE
    """), {"id": location_id})
    loc["aliases"] = [dict(r) for r in aliases_result.mappings().all()]

    audit_result = await db.execute(text("""
        SELECT * FROM tms.master_data_audit
        WHERE entity_type='location' AND entity_id=CAST(:id AS uuid)
        ORDER BY performed_at DESC LIMIT 10
    """), {"id": location_id})
    loc["audit_history"] = [dict(r) for r in audit_result.mappings().all()]
    return loc


@router.patch("/locations/{location_id}")
async def update_location(
    location_id: str,
    payload: LocationMasterUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    user_id = user.get("email", "system")

    # Get current version
    ver_result = await db.execute(text("""
        SELECT version_number FROM tms.locations WHERE location_id = CAST(:id AS uuid)
    """), {"id": location_id})
    ver_row = ver_result.mappings().one_or_none()
    if not ver_row:
        raise HTTPException(404, "Location not found.")
    current_ver = ver_row["version_number"]

    set_parts = []
    params: dict[str, Any] = {"id": location_id}
    for k, v in updates.items():
        if k == "accessorial_rules":
            set_parts.append(f"{k} = CAST(:{k} AS jsonb)")
            params[k] = _json.dumps(v)
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v
    set_parts.append("version_number = version_number + 1")
    set_parts.append("updated_at = NOW()")

    result = await db.execute(text(f"""
        UPDATE tms.locations SET {', '.join(set_parts)}
        WHERE location_id = CAST(:id AS uuid)
        RETURNING location_id, version_number
    """), params)
    await db.commit()
    row = dict(result.mappings().one())

    await _audit_log(db, "location", location_id, "updated",
                     current_ver, row["version_number"],
                     changed_fields=list(updates.keys()), user_id=user_id)
    await db.commit()
    return row


# ── MD-003: Location aliases ──────────────────────────────────────

@router.post("/locations/{location_id}/aliases", status_code=201)
async def add_location_alias(
    location_id: str,
    payload: AliasCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.location_aliases
            (location_id, alias_type, alias_value, source_system, party_id)
        VALUES
            (CAST(:location_id AS uuid), :alias_type, :alias_value,
             :source_system, CAST(:party_id AS uuid))
        RETURNING alias_id
    """), {"location_id": location_id, **payload.model_dump()})
    await db.commit()
    return {"alias_id": str(result.scalar()), "location_id": location_id, **payload.model_dump()}


@router.get("/locations/search/by-alias")
async def find_location_by_alias(
    alias_value: str,
    source_system: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    conditions = ["la.alias_value = :alias_value", "la.is_active = TRUE"]
    params: dict[str, Any] = {"alias_value": alias_value}
    if source_system:
        conditions.append("la.source_system = :source_system")
        params["source_system"] = source_system
    result = await db.execute(text(f"""
        SELECT l.*, la.alias_type, la.alias_value, la.source_system
        FROM tms.location_aliases la
        JOIN tms.locations l ON l.location_id = la.location_id
        WHERE {' AND '.join(conditions)}
    """), params)
    rows = [dict(r) for r in result.mappings().all()]
    return {"alias_value": alias_value, "matches": rows, "count": len(rows)}


# ── MD-004: Item master ───────────────────────────────────────────

@router.get("/items")
async def list_items(
    db: AsyncSession = Depends(get_db),
    freight_class: Optional[str] = Query(None),
    is_hazmat: Optional[bool] = Query(None),
    requires_temp_ctrl: Optional[bool] = Query(None),
    status: Optional[str] = Query("active"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if freight_class:
        conditions.append("freight_class = :freight_class")
        params["freight_class"] = freight_class
    if is_hazmat is not None:
        conditions.append("is_hazmat = :is_hazmat")
        params["is_hazmat"] = is_hazmat
    if requires_temp_ctrl is not None:
        conditions.append("requires_temp_ctrl = :requires_temp_ctrl")
        params["requires_temp_ctrl"] = requires_temp_ctrl
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if search:
        conditions.append("(item_number ILIKE :search OR description ILIKE :search)")
        params["search"] = f"%{search}%"
    result = await db.execute(text(f"""
        SELECT * FROM tms.items
        WHERE {' AND '.join(conditions)}
        ORDER BY item_number
        LIMIT :limit OFFSET :offset
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/items", status_code=201)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user.get("email", "system")
    from datetime import date as _date
    eff = _date.fromisoformat(payload.effective_date) if payload.effective_date else _date.today()
    data = payload.model_dump()
    data.pop("effective_date")

    result = await db.execute(text("""
        INSERT INTO tms.items
            (item_number, item_description, weight_value, weight_value,
             length_value, width_value, height_value,
             freight_class, nmfc_code, commodity_code, commodity_desc,
             hazardous_flag, hazmat_class, hazmat_un_number,
             hazardous_flag, temp_min_c, temp_max_c,
             packaging_type_id, units_per_pallet, stackable_flag, base_uom,
             effective_date, created_by)
        VALUES
            (:item_number, :description, CAST(:weight_kg AS numeric), CAST(:weight_kg AS numeric),
             CAST(:length_cm AS numeric), CAST(:width_cm AS numeric), CAST(:height_cm AS numeric),
             :freight_class, :nmfc_code, :commodity_code, :commodity_desc,
             :is_hazmat, :hazmat_class, :hazmat_un_number,
             :is_hazmat, CAST(:temp_min_c AS numeric), CAST(:temp_max_c AS numeric),
             :packaging_type, :units_per_pallet, :is_stackable, :base_uom,
             :effective_date, :created_by)
        RETURNING item_id, item_number, description, status, version_number
    """), {**data, "effective_date": eff, "created_by": user_id})
    await db.commit()
    row = dict(result.mappings().one())
    await _audit_log(db, "item", str(row["item_id"]), "created", None, 1, user_id=user_id)
    await db.commit()
    return row


@router.get("/items/{item_id}")
async def get_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.items WHERE item_id = CAST(:id AS uuid)
    """), {"id": item_id})
    item = result.mappings().one_or_none()
    if not item:
        raise HTTPException(404, "Item not found.")
    item = dict(item)

    aliases_result = await db.execute(text("""
        SELECT * FROM tms.item_aliases WHERE item_id = CAST(:id AS uuid) AND is_active = TRUE
    """), {"id": item_id})
    item["aliases"] = [dict(r) for r in aliases_result.mappings().all()]

    audit_result = await db.execute(text("""
        SELECT * FROM tms.master_data_audit
        WHERE entity_type='item' AND entity_id=CAST(:id AS uuid)
        ORDER BY performed_at DESC LIMIT 10
    """), {"id": item_id})
    item["audit_history"] = [dict(r) for r in audit_result.mappings().all()]
    return item


@router.patch("/items/{item_id}")
async def update_item(
    item_id: str,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    user_id = user.get("email", "system")

    ver_result = await db.execute(text("""
        SELECT version_number FROM tms.items WHERE item_id = CAST(:id AS uuid)
    """), {"id": item_id})
    ver_row = ver_result.mappings().one_or_none()
    if not ver_row:
        raise HTTPException(404, "Item not found.")
    current_ver = ver_row["version_number"]

    set_parts = [f"{k} = :{k}" for k in updates] + ["version_number = version_number + 1", "updated_at = NOW()"]
    result = await db.execute(text(f"""
        UPDATE tms.items SET {', '.join(set_parts)}
        WHERE item_id = CAST(:id AS uuid)
        RETURNING item_id, version_number, status
    """), {**updates, "id": item_id})
    await db.commit()
    row = dict(result.mappings().one())
    await _audit_log(db, "item", item_id, "updated", current_ver, row["version_number"],
                     changed_fields=list(updates.keys()), user_id=user_id)
    await db.commit()
    return row


# ── MD-005: Item aliases ──────────────────────────────────────────

@router.post("/items/{item_id}/aliases", status_code=201)
async def add_item_alias(
    item_id: str,
    payload: AliasCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.item_aliases
            (item_id, alias_type, alias_value, source_system, party_id)
        VALUES
            (CAST(:item_id AS uuid), :alias_type, :alias_value,
             :source_system, CAST(:party_id AS uuid))
        RETURNING item_alias_id
    """), {"item_id": item_id, **payload.model_dump()})
    await db.commit()
    return {"item_alias_id": str(result.scalar()), "item_id": item_id, **payload.model_dump()}


# ── MD-006/007/008: Charge codes ──────────────────────────────────

@router.get("/charge-codes")
async def list_charge_codes(
    db: AsyncSession = Depends(get_db),
    charge_category: Optional[str] = Query(None),
    applies_to: Optional[str] = Query(None),
    active_only: bool = Query(True),
    user=Depends(get_current_user),
):
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if charge_category:
        conditions.append("charge_category = :charge_category")
        params["charge_category"] = charge_category
    if applies_to:
        conditions.append("(applies_to = :applies_to OR applies_to = 'both')")
        params["applies_to"] = applies_to
    if active_only:
        conditions.append("is_active = TRUE")
        conditions.append("effective_date <= CURRENT_DATE")
        conditions.append("(expiry_date IS NULL OR expiry_date >= CURRENT_DATE)")
    result = await db.execute(text(f"""
        SELECT * FROM tms.charge_code_master
        WHERE {' AND '.join(conditions)}
        ORDER BY charge_category, charge_code
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/charge-codes", status_code=201)
async def create_charge_code(
    payload: ChargeCodeCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user.get("email", "system")
    from datetime import date as _date
    eff = _date.fromisoformat(payload.effective_date) if payload.effective_date else _date.today()
    data = payload.model_dump(); data.pop("effective_date")
    result = await db.execute(text("""
        INSERT INTO tms.charge_code_master
            (charge_code, charge_name, charge_category, applies_to,
             gl_account_code, billing_category, audit_rule_code,
             allocation_rule, tax_rule_code,
             external_code_edi, external_code_erp, effective_date, created_by)
        VALUES
            (:charge_code, :charge_name, :charge_category, :applies_to,
             :gl_account_code, :billing_category, :audit_rule_code,
             :allocation_rule, :tax_rule_code,
             :external_code_edi, :external_code_erp, :effective_date, :created_by)
        RETURNING charge_code_id, charge_code, charge_name, charge_category
    """), {**data, "effective_date": eff, "created_by": user_id})
    await db.commit()
    row = dict(result.mappings().one())
    await _audit_log(db, "charge_code", str(row["charge_code_id"]), "created", None, 1, user_id=user_id)
    await db.commit()
    return row


@router.patch("/charge-codes/{charge_code_id}/approve")
async def approve_charge_code(
    charge_code_id: str,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """MD-009: Approve a charge code record."""
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        UPDATE tms.charge_code_master
        SET approved_by = :user, approved_at = NOW(), updated_at = NOW()
        WHERE charge_code_id = CAST(:id AS uuid)
        RETURNING charge_code_id, charge_code, approved_by, approved_at
    """), {"user": user_id, "id": charge_code_id})
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Charge code not found.")
    await _audit_log(db, "charge_code", charge_code_id, "approved", None, None, user_id=user_id, notes=payload.notes)
    await db.commit()
    return dict(row)


# ── MD-009: Audit history ─────────────────────────────────────────

@router.get("/audit/{entity_type}/{entity_id}")
async def get_audit_history(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.master_data_audit
        WHERE entity_type = :entity_type AND entity_id = CAST(:entity_id AS uuid)
        ORDER BY performed_at DESC
    """), {"entity_type": entity_type, "entity_id": entity_id})
    rows = [dict(r) for r in result.mappings().all()]
    return {"entity_type": entity_type, "entity_id": entity_id, "history": rows, "count": len(rows)}


# ── MD-010: Bulk import / export / duplicate detection ────────────

@router.post("/bulk-import", status_code=201)
async def bulk_import(
    payload: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    MD-010: Bulk import master data records with validation
    and duplicate detection. Set validate_only=true for dry run.
    """
    user_id = user.get("email", "system")
    results = {"total": len(payload.records), "valid": 0, "invalid": 0,
               "duplicates": 0, "imported": 0, "errors": [], "warnings": []}

    for i, rec in enumerate(payload.records):
        row_label = f"Row {i+1}"
        try:
            if payload.entity_type == "item":
                # Validate required fields
                if not rec.get("item_number") or not rec.get("description"):
                    results["invalid"] += 1
                    results["errors"].append(f"{row_label}: item_number and description required")
                    continue
                # Duplicate check
                dup = await db.execute(text("""
                    SELECT item_id FROM tms.items WHERE item_number = :item_number
                """), {"item_number": rec["item_number"]})
                if dup.scalar():
                    results["duplicates"] += 1
                    if not payload.update_existing:
                        results["warnings"].append(f"{row_label}: Duplicate item_number {rec['item_number']} — skipped")
                        continue
                results["valid"] += 1
                if not payload.validate_only:
                    await db.execute(text("""
                        INSERT INTO tms.items (item_number, item_description, freight_class,
                            weight_value, hazardous_flag, base_uom, created_by)
                        VALUES (:item_number, :description, :freight_class,
                            CAST(:weight_kg AS numeric), :is_hazmat, :base_uom, :created_by)
                        ON CONFLICT (item_number) DO UPDATE SET
                            item_description = EXCLUDED.item_description, updated_at = NOW()
                    """), {
                        "item_number":   rec.get("item_number"),
                        "description":   rec.get("description"),
                        "freight_class": rec.get("freight_class"),
                        "weight_kg":     rec.get("weight_kg"),
                        "is_hazmat":     rec.get("is_hazmat", False),
                        "base_uom":      rec.get("base_uom", "EA"),
                        "created_by":    user_id,
                    })
                    results["imported"] += 1

            elif payload.entity_type == "charge_code":
                if not rec.get("charge_code") or not rec.get("charge_name"):
                    results["invalid"] += 1
                    results["errors"].append(f"{row_label}: charge_code and charge_name required")
                    continue
                dup = await db.execute(text("""
                    SELECT charge_code_id FROM tms.charge_code_master WHERE charge_code = :code
                """), {"code": rec["charge_code"]})
                if dup.scalar():
                    results["duplicates"] += 1
                    if not payload.update_existing:
                        results["warnings"].append(f"{row_label}: Duplicate charge_code {rec['charge_code']} — skipped")
                        continue
                results["valid"] += 1
                if not payload.validate_only:
                    await db.execute(text("""
                        INSERT INTO tms.charge_code_master
                            (charge_code, charge_name, charge_category, applies_to, gl_account_code, created_by)
                        VALUES (:charge_code, :charge_name, :charge_category, :applies_to, :gl_account_code, :created_by)
                        ON CONFLICT (charge_code) DO UPDATE SET
                            charge_name = EXCLUDED.charge_name, updated_at = NOW()
                    """), {
                        "charge_code":     rec.get("charge_code"),
                        "charge_name":     rec.get("charge_name"),
                        "charge_category": rec.get("charge_category", "freight"),
                        "applies_to":      rec.get("applies_to", "both"),
                        "gl_account_code": rec.get("gl_account_code"),
                        "created_by":      user_id,
                    })
                    results["imported"] += 1
            else:
                results["errors"].append(f"Unsupported entity_type: {payload.entity_type}")
                break

        except Exception as e:
            results["invalid"] += 1
            results["errors"].append(f"{row_label}: {str(e)}")

    if not payload.validate_only:
        await db.commit()
        await _audit_log(db, payload.entity_type, "bulk", "bulk_import", None, None,
                         user_id=user_id, notes=f"Imported {results['imported']} records")
        await db.commit()

    results["dry_run"] = payload.validate_only
    return results


@router.get("/export/{entity_type}")
async def export_master_data(
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(True),
    user=Depends(get_current_user),
):
    """MD-010: Export master data records."""
    if entity_type == "items":
        conditions = ["status = 'active'"] if active_only else ["1=1"]
        result = await db.execute(text(f"""
            SELECT * FROM tms.items WHERE {' AND '.join(conditions)} ORDER BY item_number
        """))
    elif entity_type == "charge_codes":
        conditions = ["is_active = TRUE"] if active_only else ["1=1"]
        result = await db.execute(text(f"""
            SELECT * FROM tms.charge_code_master WHERE {' AND '.join(conditions)} ORDER BY charge_code
        """))
    elif entity_type == "locations":
        conditions = ["is_active = TRUE"] if active_only else ["1=1"]
        result = await db.execute(text(f"""
            SELECT l.*, p.party_name FROM tms.locations l
            LEFT JOIN tms.parties p ON p.party_id = l.party_id
            WHERE {' AND '.join(conditions)} ORDER BY l.location_name
        """))
    else:
        raise HTTPException(400, f"Unsupported entity_type: {entity_type}. Use: items, charge_codes, locations")

    rows = [dict(r) for r in result.mappings().all()]
    return {"entity_type": entity_type, "count": len(rows), "records": rows}


# ── Helper ────────────────────────────────────────────────────────

async def _audit_log(db, entity_type: str, entity_id: str, action: str,
                      ver_before, ver_after, changed_fields=None,
                      new_values=None, user_id="system", notes=None):
    try:
        await db.execute(text("""
            INSERT INTO tms.master_data_audit
                (entity_type, entity_id, action, version_before, version_after,
                 changed_fields, new_values, performed_by, notes)
            VALUES
                (:entity_type, CAST(:entity_id AS uuid), :action,
                 :version_before, :version_after, :changed_fields,
                 CAST(:new_values AS jsonb), :performed_by, :notes)
        """), {
            "entity_type":   entity_type,
            "entity_id":     entity_id if entity_id != "bulk" else "00000000-0000-0000-0000-000000000000",
            "action":        action,
            "version_before":ver_before,
            "version_after": ver_after,
            "changed_fields":changed_fields or [],
            "new_values":    _json.dumps(new_values) if new_values else None,
            "performed_by":  user_id,
            "notes":         notes,
        })
    except Exception:
        pass  # Audit log failures should never break main flow

# ── RATE REGIONS ──────────────────────────────────────────────

@router.get("/rate-regions")
async def list_rate_regions(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(text("""
        SELECT r.*, COUNT(m.member_id) AS member_count
        FROM tms.rate_regions r
        LEFT JOIN tms.rate_region_members m ON m.region_id = r.region_id
        WHERE r.is_active = TRUE
        GROUP BY r.region_id
        ORDER BY r.region_name
    """))
    return {"regions": [dict(row) for row in result.mappings().all()]}

@router.get("/rate-regions/{region_id}")
async def get_rate_region(region_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    r = await db.execute(text("SELECT * FROM tms.rate_regions WHERE region_id = CAST(:id AS uuid)"), {"id": region_id})
    region = r.mappings().first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    m = await db.execute(text("SELECT * FROM tms.rate_region_members WHERE region_id = CAST(:id AS uuid) ORDER BY member_type, member_value"), {"id": region_id})
    return {"region": dict(region), "members": [dict(row) for row in m.mappings().all()]}

@router.post("/rate-regions", status_code=201)
async def create_rate_region(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    from sqlalchemy import text as t
    result = await db.execute(text("""
        INSERT INTO tms.rate_regions (region_code, region_name, region_type, description, created_by)
        VALUES (:code, :name, :type, :desc, :by)
        RETURNING region_id
    """), {"code": payload["region_code"], "name": payload["region_name"],
           "type": payload.get("region_type","custom"), "desc": payload.get("description",""),
           "by": str(user.user_id)})
    await db.commit()
    return {"region_id": str(result.scalar())}

@router.post("/rate-regions/{region_id}/members", status_code=201)
async def add_region_member(region_id: str, payload: dict, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(text("""
        INSERT INTO tms.rate_region_members (region_id, member_type, member_value, member_value_to, country_code)
        VALUES (CAST(:rid AS uuid), :mtype, :mval, :mval_to, :country)
        RETURNING member_id
    """), {"rid": region_id, "mtype": payload["member_type"], "mval": payload["member_value"],
           "mval_to": payload.get("member_value_to"), "country": payload.get("country_code","US")})
    await db.commit()
    return {"member_id": str(result.scalar())}

@router.delete("/rate-regions/{region_id}/members/{member_id}", status_code=204)
async def remove_region_member(region_id: str, member_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await db.execute(text("DELETE FROM tms.rate_region_members WHERE member_id = CAST(:id AS uuid)"), {"id": member_id})
    await db.commit()

# ── RATE CARDS ────────────────────────────────────────────────

@router.get("/rate-cards")
async def list_rate_cards(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(text("""
        SELECT rc.*, p.party_name AS carrier_name,
               COUNT(DISTINCT rl.lane_id) AS lane_count,
               COUNT(DISTINCT rli.rate_line_id) AS line_count
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carriers c ON c.carrier_id = rc.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.carrier_rate_lanes rl ON rl.rate_card_id = rc.rate_card_id
        LEFT JOIN tms.carrier_rate_lines rli ON rli.lane_id = rl.lane_id
        GROUP BY rc.rate_card_id, p.party_name
        ORDER BY rc.effective_date DESC NULLS LAST
    """))
    return {"rate_cards": [dict(row) for row in result.mappings().all()]}

@router.get("/rate-cards/{rate_card_id}")
async def get_rate_card(rate_card_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rc = await db.execute(text("""
        SELECT rc.*, p.party_name AS carrier_name
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carriers c ON c.carrier_id = rc.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = c.party_id
        WHERE rc.rate_card_id = CAST(:id AS uuid)
    """), {"id": rate_card_id})
    card = rc.mappings().first()
    if not card:
        raise HTTPException(status_code=404, detail="Rate card not found")
    lanes = await db.execute(text("""
        SELECT rl.*, COUNT(rli.rate_line_id) AS line_count
        FROM tms.carrier_rate_lanes rl
        LEFT JOIN tms.carrier_rate_lines rli ON rli.lane_id = rl.lane_id
        WHERE rl.rate_card_id = CAST(:id AS uuid)
        GROUP BY rl.lane_id ORDER BY rl.priority
    """), {"id": rate_card_id})
    return {"rate_card": dict(card), "lanes": [dict(r) for r in lanes.mappings().all()]}

@router.get("/rate-cards/{rate_card_id}/lanes/{lane_id}/lines")
async def get_lane_lines(rate_card_id: str, lane_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(text("""
        SELECT * FROM tms.carrier_rate_lines
        WHERE lane_id = CAST(:id AS uuid) AND is_active = TRUE
        ORDER BY sort_order, charge_code
    """), {"id": lane_id})
    return {"lines": [dict(r) for r in result.mappings().all()]}

@router.post("/locations", status_code=201)
async def create_location(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(text("""
        INSERT INTO tms.locations (location_code, location_name, address_line1, address_line2,
            city, state_province, postal_code, latitude, longitude, time_zone, created_at, updated_at)
        VALUES (:location_code, :location_name, :address_line1, :address_line2,
            :city, :state_province, :postal_code, :latitude, :longitude, :time_zone, NOW(), NOW())
        RETURNING location_id
    """), {
        "location_code": payload.get("location_code"),
        "location_name": payload.get("location_name"),
        "address_line1": payload.get("address_line1"),
        "address_line2": payload.get("address_line2"),
        "city": payload.get("city"),
        "state_province": payload.get("state_province"),
        "postal_code": payload.get("postal_code"),
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "time_zone": payload.get("time_zone"),
    })
    await db.commit()
    return {"location_id": str(result.scalar())}

@router.patch("/locations/{location_id}")
async def update_location(location_id: str, payload: dict, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await db.execute(text("""
        UPDATE tms.locations SET
            location_code = COALESCE(:location_code, location_code),
            location_name = COALESCE(:location_name, location_name),
            address_line1 = :address_line1,
            address_line2 = :address_line2,
            city = :city,
            state_province = :state_province,
            postal_code = :postal_code,
            latitude = :latitude,
            longitude = :longitude,
            time_zone = :time_zone,
            updated_at = NOW()
        WHERE location_id = CAST(:id AS uuid)
    """), {
        "id": location_id,
        "location_code": payload.get("location_code"),
        "location_name": payload.get("location_name"),
        "address_line1": payload.get("address_line1"),
        "address_line2": payload.get("address_line2"),
        "city": payload.get("city"),
        "state_province": payload.get("state_province"),
        "postal_code": payload.get("postal_code"),
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "time_zone": payload.get("time_zone"),
    })
    await db.commit()
    return {"location_id": location_id}
