from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

# ── Models ───────────────────────────────────────────────────
class OrgCreate(BaseModel):
    organization_code: str
    organization_name: str
    organization_type: Optional[str] = None
    parent_organization_id: Optional[str] = None
    default_currency: Optional[str] = 'USD'
    country: Optional[str] = None
    status: Optional[str] = 'ACTIVE'

class OrgUpdate(BaseModel):
    organization_name: Optional[str] = None
    organization_type: Optional[str] = None
    parent_organization_id: Optional[str] = None
    default_currency: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None

class BUCreate(BaseModel):
    organization_id: str
    business_unit_code: str
    business_unit_name: str
    parent_business_unit_id: Optional[str] = None
    status: Optional[str] = 'ACTIVE'

class BUUpdate(BaseModel):
    business_unit_name: Optional[str] = None
    parent_business_unit_id: Optional[str] = None
    status: Optional[str] = None

# ── Organizations ─────────────────────────────────────────────
@router.get("/")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sql = text("""
        SELECT
            o.organization_id,
            o.organization_code,
            o.organization_name,
            COALESCE(lv_type.display_name, '')    AS organization_type,
            COALESCE(lv_curr.lookup_code, 'USD')  AS default_currency,
            COALESCE(lv_country.display_name, '') AS country,
            COALESCE(lv_status.lookup_code, 'ACTIVE') AS status,
            COALESCE(parent.organization_name, '') AS parent_name,
            o.parent_organization_id,
            o.created_at,
            o.updated_at,
            (SELECT COUNT(*) FROM tms.business_units bu
             WHERE bu.organization_id = o.organization_id) AS bu_count
        FROM tms.organizations o
        LEFT JOIN tms.lookup_values lv_type    ON lv_type.lookup_value_id   = o.organization_type_id
        LEFT JOIN tms.lookup_values lv_curr    ON lv_curr.lookup_value_id   = o.default_currency_id
        LEFT JOIN tms.lookup_values lv_country ON lv_country.lookup_value_id = o.country_id
        LEFT JOIN tms.lookup_values lv_status  ON lv_status.lookup_value_id  = o.status_id
        LEFT JOIN tms.organizations parent     ON parent.organization_id     = o.parent_organization_id
        ORDER BY o.organization_name
    """)
    rows = (await db.execute(sql)).mappings().all()
    return {"data": [dict(r) for r in rows]}


@router.post("/")
async def create_organization(
    body: OrgCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # check duplicate code
    exists = (await db.execute(
        text("SELECT 1 FROM tms.organizations WHERE organization_code = :code"),
        {"code": body.organization_code}
    )).first()
    if exists:
        raise HTTPException(400, f"Organization code '{body.organization_code}' already exists")

    sql = text("""
        INSERT INTO tms.organizations
            (organization_code, organization_name, parent_organization_id, created_at, updated_at)
        VALUES
            (:code, :name, :parent_id, now(), now())
        RETURNING organization_id, organization_code, organization_name, created_at
    """)
    row = (await db.execute(sql, {
        "code": body.organization_code,
        "name": body.organization_name,
        "parent_id": body.parent_organization_id or None,
    })).mappings().first()
    await db.commit()
    return dict(row)


@router.patch("/{org_id}")
async def update_organization(
    org_id: str,
    body: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = []
    params: dict = {"org_id": org_id}
    if body.organization_name is not None:
        sets.append("organization_name = :name"); params["name"] = body.organization_name
    if body.status is not None:
        sets.append("status_id = (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :status LIMIT 1)")
        params["status"] = body.status
    if body.parent_organization_id is not None:
        sets.append("parent_organization_id = :parent_id"); params["parent_id"] = body.parent_organization_id
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets.append("updated_at = now()")
    await db.execute(
        text(f"UPDATE tms.organizations SET {', '.join(sets)} WHERE organization_id = :org_id"),
        params
    )
    await db.commit()
    return {"ok": True}


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    bu_count = (await db.execute(
        text("SELECT COUNT(*) FROM tms.business_units WHERE organization_id = :id"),
        {"id": org_id}
    )).scalar()
    if bu_count:
        raise HTTPException(400, f"Cannot delete: {bu_count} business unit(s) still linked to this organization")
    await db.execute(
        text("DELETE FROM tms.organizations WHERE organization_id = :id"),
        {"id": org_id}
    )
    await db.commit()
    return {"ok": True}


# ── Business Units ────────────────────────────────────────────
@router.get("/{org_id}/business-units")
async def list_business_units(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sql = text("""
        SELECT
            bu.business_unit_id,
            bu.business_unit_code,
            bu.business_unit_name,
            bu.organization_id,
            bu.parent_business_unit_id,
            COALESCE(parent.business_unit_name, '') AS parent_name,
            COALESCE(lv.lookup_code, 'ACTIVE')      AS status,
            bu.created_at,
            bu.updated_at
        FROM tms.business_units bu
        LEFT JOIN tms.lookup_values  lv     ON lv.lookup_value_id      = bu.status_id
        LEFT JOIN tms.business_units parent ON parent.business_unit_id  = bu.parent_business_unit_id
        WHERE bu.organization_id = :org_id
        ORDER BY bu.business_unit_name
    """)
    rows = (await db.execute(sql, {"org_id": org_id})).mappings().all()
    return {"data": [dict(r) for r in rows]}


@router.post("/{org_id}/business-units")
async def create_business_unit(
    org_id: str,
    body: BUCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    exists = (await db.execute(
        text("SELECT 1 FROM tms.business_units WHERE organization_id = :org_id AND business_unit_code = :code"),
        {"org_id": org_id, "code": body.business_unit_code}
    )).first()
    if exists:
        raise HTTPException(400, f"Business unit code '{body.business_unit_code}' already exists in this organization")

    sql = text("""
        INSERT INTO tms.business_units
            (organization_id, business_unit_code, business_unit_name, parent_business_unit_id, created_at, updated_at)
        VALUES
            (:org_id, :code, :name, :parent_id, now(), now())
        RETURNING business_unit_id, business_unit_code, business_unit_name, created_at
    """)
    row = (await db.execute(sql, {
        "org_id": org_id,
        "code": body.business_unit_code,
        "name": body.business_unit_name,
        "parent_id": body.parent_business_unit_id or None,
    })).mappings().first()
    await db.commit()
    return dict(row)


@router.patch("/{org_id}/business-units/{bu_id}")
async def update_business_unit(
    org_id: str,
    bu_id: str,
    body: BUUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = []
    params: dict = {"bu_id": bu_id}
    if body.business_unit_name is not None:
        sets.append("business_unit_name = :name"); params["name"] = body.business_unit_name
    if body.parent_business_unit_id is not None:
        sets.append("parent_business_unit_id = :parent_id"); params["parent_id"] = body.parent_business_unit_id
    if body.status is not None:
        sets.append("status_id = (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :status LIMIT 1)")
        params["status"] = body.status
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets.append("updated_at = now()")
    await db.execute(
        text(f"UPDATE tms.business_units SET {', '.join(sets)} WHERE business_unit_id = :bu_id"),
        params
    )
    await db.commit()
    return {"ok": True}


@router.delete("/{org_id}/business-units/{bu_id}")
async def delete_business_unit(
    org_id: str,
    bu_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await db.execute(
        text("DELETE FROM tms.business_units WHERE business_unit_id = :id AND organization_id = :org_id"),
        {"id": bu_id, "org_id": org_id}
    )
    await db.commit()
    return {"ok": True}
