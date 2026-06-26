from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

# ── Currencies ────────────────────────────────────────────────
@router.get("/currencies")
async def list_currencies(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rows = (await db.execute(text(
        "SELECT * FROM tms.currencies ORDER BY currency_code"
    ))).mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.patch("/currencies/{currency_code}")
async def update_currency(currency_code: str, body: dict,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if "is_active" in body:
        await db.execute(text(
            "UPDATE tms.currencies SET is_active = :v WHERE currency_code = :c"
        ), {"v": body["is_active"], "c": currency_code})
        await db.commit()
    return {"ok": True}

# ── Languages ─────────────────────────────────────────────────
@router.get("/languages")
async def list_languages(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rows = (await db.execute(text(
        "SELECT * FROM tms.languages ORDER BY language_name"
    ))).mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.patch("/languages/{language_code}")
async def update_language(language_code: str, body: dict,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sets, params = [], {"c": language_code}
    if "is_active"  in body: sets.append("is_active = :ia");  params["ia"] = body["is_active"]
    if "is_default" in body: sets.append("is_default = :id"); params["id"] = body["is_default"]
    if sets:
        await db.execute(text(f"UPDATE tms.languages SET {', '.join(sets)} WHERE language_code = :c"), params)
        await db.commit()
    return {"ok": True}

# ── Date Formats ──────────────────────────────────────────────
@router.get("/date-formats")
async def list_date_formats(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    rows = (await db.execute(text(
        "SELECT * FROM tms.date_formats ORDER BY is_default DESC, format_code"
    ))).mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.patch("/date-formats/{format_code}")
async def update_date_format(format_code: str, body: dict,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sets, params = [], {"c": format_code}
    if "is_active"  in body: sets.append("is_active = :ia");  params["ia"] = body["is_active"]
    if "is_default" in body:
        # Clear existing default first
        await db.execute(text("UPDATE tms.date_formats SET is_default = false"))
        sets.append("is_default = :id"); params["id"] = body["is_default"]
    if sets:
        await db.execute(text(f"UPDATE tms.date_formats SET {', '.join(sets)} WHERE format_code = :c"), params)
        await db.commit()
    return {"ok": True}

# ── Time Zones ────────────────────────────────────────────────
@router.get("/time-zones")
async def list_time_zones(
    region: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    where = "WHERE region = :region" if region else ""
    params = {"region": region} if region else {}
    rows = (await db.execute(text(
        f"SELECT * FROM tms.time_zones {where} ORDER BY utc_offset_minutes, tz_name"
    ), params)).mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.patch("/time-zones/{tz_code}")
async def update_time_zone(tz_code: str, body: dict,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sets, params = [], {"c": tz_code}
    if "is_active"  in body: sets.append("is_active = :ia");  params["ia"] = body["is_active"]
    if "is_default" in body:
        await db.execute(text("UPDATE tms.time_zones SET is_default = false"))
        sets.append("is_default = :id"); params["id"] = body["is_default"]
    if sets:
        await db.execute(text(f"UPDATE tms.time_zones SET {', '.join(sets)} WHERE tz_code = :c"), params)
        await db.commit()
    return {"ok": True}

# ── Tax Jurisdictions ─────────────────────────────────────────
@router.get("/tax-jurisdictions")
async def list_tax_jurisdictions(
    country: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    where = "WHERE country_code = :country" if country else ""
    params = {"country": country} if country else {}
    rows = (await db.execute(text(
        f"SELECT * FROM tms.tax_jurisdictions {where} ORDER BY country_code, jurisdiction_name"
    ), params)).mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.patch("/tax-jurisdictions/{jurisdiction_code}")
async def update_tax_jurisdiction(jurisdiction_code: str, body: dict,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sets, params = ["updated_at = now()"], {"c": jurisdiction_code}
    for f in ["is_active","standard_rate","reduced_rate","notes"]:
        if f in body: sets.append(f"{f} = :{f}"); params[f] = body[f]
    await db.execute(text(f"UPDATE tms.tax_jurisdictions SET {', '.join(sets)} WHERE jurisdiction_code = :c"), params)
    await db.commit()
    return {"ok": True}

# ── Unit of Measures ──────────────────────────────────────────
@router.get("/uoms")
async def list_uoms(
    uom_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    where = "WHERE uom_type = :uom_type" if uom_type else ""
    params = {"uom_type": uom_type} if uom_type else {}
    rows = (await db.execute(text(
        f"SELECT * FROM tms.unit_of_measures {where} ORDER BY uom_type, uom_code"
    ), params)).mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.patch("/uoms/{uom_code}")
async def update_uom(uom_code: str, body: dict,
    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    sets, params = [], {"c": uom_code}
    if "is_active" in body: sets.append("is_active = :ia"); params["ia"] = body["is_active"]
    if sets:
        await db.execute(text(f"UPDATE tms.unit_of_measures SET {', '.join(sets)} WHERE uom_code = :c"), params)
        await db.commit()
    return {"ok": True}
