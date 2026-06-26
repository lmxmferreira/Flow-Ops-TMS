from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

ENTITY_TYPES = [
    'SHIPMENT', 'PURCHASE_ORDER', 'ORDER_RELEASE', 'LOAD', 'STOP',
    'CARRIER_INVOICE', 'CLIENT_BILL', 'VOUCHER', 'CLAIM', 'DISPUTE'
]

class SchemeUpdate(BaseModel):
    scheme_name: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    separator: Optional[str] = None
    padding: Optional[int] = None
    include_year: Optional[bool] = None
    include_month: Optional[bool] = None
    reset_period: Optional[str] = None
    next_value: Optional[int] = None
    is_active: Optional[bool] = None

# ── List all schemes ──────────────────────────────────────────
@router.get("/")
async def list_schemes(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sql = text("""
        SELECT
            scheme_id, entity_type, scheme_name,
            prefix, suffix, separator, padding,
            include_year, include_month, reset_period,
            next_value, last_reset_at, is_active,
            created_at, updated_at,
            tms.preview_number(entity_type) AS preview
        FROM tms.numbering_schemes
        ORDER BY entity_type
    """)
    rows = (await db.execute(sql)).mappings().all()
    return {"data": [dict(r) for r in rows]}

# ── Generate next number ──────────────────────────────────────
@router.post("/generate/{entity_type}")
async def generate_number(
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"Invalid entity_type. Must be one of: {ENTITY_TYPES}")
    try:
        result = (await db.execute(
            text("SELECT tms.generate_number(:entity_type) AS number"),
            {"entity_type": entity_type}
        )).scalar()
        await db.commit()
        return {"number": result, "entity_type": entity_type}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Preview next number (no increment) ───────────────────────
@router.get("/preview/{entity_type}")
async def preview_number(
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = (await db.execute(
        text("SELECT tms.preview_number(:entity_type) AS number"),
        {"entity_type": entity_type}
    )).scalar()
    return {"preview": result, "entity_type": entity_type}

# ── Update scheme ─────────────────────────────────────────────
@router.patch("/{entity_type}")
async def update_scheme(
    entity_type: str,
    body: SchemeUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = ["updated_at = now()"]
    params = {"entity_type": entity_type}

    field_map = {
        "scheme_name": "scheme_name", "prefix": "prefix", "suffix": "suffix",
        "separator": "separator", "padding": "padding", "include_year": "include_year",
        "include_month": "include_month", "reset_period": "reset_period",
        "next_value": "next_value", "is_active": "is_active",
    }
    for field, col in field_map.items():
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{col} = :{field}")
            params[field] = val

    if len(sets) == 1:
        raise HTTPException(400, "Nothing to update")

    await db.execute(
        text(f"UPDATE tms.numbering_schemes SET {', '.join(sets)} WHERE entity_type = :entity_type"),
        params
    )
    # Update preview
    await db.execute(
        text("UPDATE tms.numbering_schemes SET preview = tms.preview_number(entity_type) WHERE entity_type = :entity_type"),
        {"entity_type": entity_type}
    )
    await db.commit()
    return {"ok": True}

# ── Reset counter ─────────────────────────────────────────────
@router.post("/{entity_type}/reset")
async def reset_counter(
    entity_type: str,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    start_from = body.get("start_from", 1)
    await db.execute(
        text("UPDATE tms.numbering_schemes SET next_value = :v, last_reset_at = now() WHERE entity_type = :et"),
        {"v": start_from, "et": entity_type}
    )
    await db.commit()
    return {"ok": True, "reset_to": start_from}
