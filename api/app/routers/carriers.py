from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────

class CarrierCreate(BaseModel):
    party_name: str
    party_code: str
    scac: Optional[str] = None
    mc_number: Optional[str] = None
    dot_number: Optional[str] = None
    tax_identifier: Optional[str] = None
    status_id: Optional[str] = None
    payment_terms_id: Optional[str] = None
    onboarding_status_id: Optional[str] = None
    safety_rating_id: Optional[str] = None
    remittance_party_id: Optional[str] = None


class CarrierUpdate(BaseModel):
    scac: Optional[str] = None
    mc_number: Optional[str] = None
    dot_number: Optional[str] = None
    status_id: Optional[str] = None
    payment_terms_id: Optional[str] = None
    onboarding_status_id: Optional[str] = None
    safety_rating_id: Optional[str] = None
    remittance_party_id: Optional[str] = None


# ── List Carriers ─────────────────────────────────────────────

@router.get("/")
async def list_carriers(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    filters = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}

    if search:
        filters.append(
            "(p.party_name ILIKE :search OR p.party_code ILIKE :search "
            "OR c.scac ILIKE :search OR c.mc_number ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    if status:
        filters.append("lv_status.lookup_code = :status")
        params["status"] = status

    where = " AND ".join(filters)

    result = await db.execute(text(f"""
        SELECT
            c.carrier_id,
            c.scac,
            c.mc_number,
            c.dot_number,
            c.created_at,
            c.updated_at,
            p.party_name      AS carrier_name,
            p.party_code      AS carrier_code,
            p.tax_identifier,
            COALESCE(lv_status.lookup_code,    'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name,   'Unknown') AS status_name,
            COALESCE(lv_onboard.display_name,  '')        AS onboarding_status,
            COALESCE(lv_safety.display_name,   '')        AS safety_rating,
            COALESCE(lv_pay.display_name,      '')        AS payment_terms,
            COALESCE(rp.party_name,            '')        AS remittance_party,
            (SELECT COUNT(*) FROM tms.carrier_rate_cards rc
             WHERE rc.carrier_id = c.carrier_id AND rc.status = 'active') AS active_rate_cards
        FROM tms.carriers c
        JOIN  tms.parties       p         ON p.party_id          = c.party_id
        LEFT JOIN tms.lookup_values lv_status  ON lv_status.lookup_value_id  = c.status_id
        LEFT JOIN tms.lookup_values lv_onboard ON lv_onboard.lookup_value_id = c.onboarding_status_id
        LEFT JOIN tms.lookup_values lv_safety  ON lv_safety.lookup_value_id  = c.safety_rating_id
        LEFT JOIN tms.lookup_values lv_pay     ON lv_pay.lookup_value_id     = c.payment_terms_id
        LEFT JOIN tms.parties       rp         ON rp.party_id               = c.remittance_party_id
        WHERE {where}
        ORDER BY p.party_name
        LIMIT :limit OFFSET :offset
    """), params)

    count_result = await db.execute(text(f"""
        SELECT COUNT(*) FROM tms.carriers c
        JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = c.status_id
        WHERE {where}
    """), params)

    rows  = [dict(r) for r in result.mappings().all()]
    total = count_result.scalar()
    return {"data": rows, "total": total, "limit": limit, "offset": offset}


# ── Create Carrier ────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_carrier(
    payload: CarrierCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Create party first
    party_result = await db.execute(text("""
        INSERT INTO tms.parties (party_name, party_code, tax_identifier)
        VALUES (:party_name, :party_code, :tax_identifier)
        RETURNING party_id
    """), {
        "party_name":     payload.party_name,
        "party_code":     payload.party_code,
        "tax_identifier": payload.tax_identifier,
    })
    party_id = party_result.scalar()

    # Create carrier
    carrier_result = await db.execute(text("""
        INSERT INTO tms.carriers
            (party_id, scac, mc_number, dot_number,
             status_id, payment_terms_id, onboarding_status_id,
             safety_rating_id, remittance_party_id)
        VALUES
            (CAST(:party_id AS uuid), :scac, :mc_number, :dot_number,
             CAST(:status_id AS uuid), CAST(:payment_terms_id AS uuid),
             CAST(:onboarding_status_id AS uuid), CAST(:safety_rating_id AS uuid),
             CAST(:remittance_party_id AS uuid))
        RETURNING carrier_id
    """), {
        "party_id":             str(party_id),
        "scac":                 payload.scac,
        "mc_number":            payload.mc_number,
        "dot_number":           payload.dot_number,
        "status_id":            payload.status_id,
        "payment_terms_id":     payload.payment_terms_id,
        "onboarding_status_id": payload.onboarding_status_id,
        "safety_rating_id":     payload.safety_rating_id,
        "remittance_party_id":  payload.remittance_party_id,
    })
    carrier_id = carrier_result.scalar()
    await db.commit()
    return {"carrier_id": str(carrier_id), "party_id": str(party_id)}


# ── Get Carrier ───────────────────────────────────────────────

@router.get("/lookups")
async def get_carrier_lookups(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return all lookup values needed for carrier forms."""
    result = await db.execute(text("""
        SELECT lt.lookup_type_code, lv.lookup_value_id, lv.lookup_code, lv.display_name
        FROM tms.lookup_values lv
        JOIN tms.lookup_types lt ON lt.lookup_type_id = lv.lookup_type_id
        WHERE lt.lookup_type_code IN ('CARRIER_STATUS','PAYMENT_TERMS','ONBOARDING_STATUS','SAFETY_RATING')
        ORDER BY lt.lookup_type_code, lv.sort_order
    """))
    rows = result.mappings().all()
    grouped: dict = {}
    for r in rows:
        key = r["lookup_type_code"]
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({"id": str(r["lookup_value_id"]), "code": r["lookup_code"], "label": r["display_name"]})
    return grouped


@router.get("/{carrier_id}")
async def get_carrier(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT
            c.carrier_id,
            c.scac, c.mc_number, c.dot_number,
            c.status_id, c.payment_terms_id, c.onboarding_status_id,
            c.safety_rating_id, c.remittance_party_id,
            c.created_at, c.updated_at,
            p.party_id, p.party_name AS carrier_name,
            p.party_code AS carrier_code, p.tax_identifier,
            COALESCE(lv_status.lookup_code,   'UNKNOWN') AS status_code,
            COALESCE(lv_status.display_name,  'Unknown') AS status_name,
            COALESCE(lv_onboard.display_name, '')        AS onboarding_status,
            COALESCE(lv_safety.display_name,  '')        AS safety_rating,
            COALESCE(lv_pay.display_name,     '')        AS payment_terms,
            COALESCE(rp.party_name,           '')        AS remittance_party
        FROM tms.carriers c
        JOIN  tms.parties       p         ON p.party_id          = c.party_id
        LEFT JOIN tms.lookup_values lv_status  ON lv_status.lookup_value_id  = c.status_id
        LEFT JOIN tms.lookup_values lv_onboard ON lv_onboard.lookup_value_id = c.onboarding_status_id
        LEFT JOIN tms.lookup_values lv_safety  ON lv_safety.lookup_value_id  = c.safety_rating_id
        LEFT JOIN tms.lookup_values lv_pay     ON lv_pay.lookup_value_id     = c.payment_terms_id
        LEFT JOIN tms.parties       rp         ON rp.party_id               = c.remittance_party_id
        WHERE c.carrier_id = CAST(:id AS uuid)
    """), {"id": carrier_id})

    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Carrier not found.")

    rc_result = await db.execute(text("""
        SELECT rc.rate_card_id, rc.name, rc.mode, rc.rate_type,
               rc.effective_date, rc.expiry_date, rc.status,
               rc.contract_reference, rc.route_priority,
               COUNT(l.lane_id) AS lane_count
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carrier_rate_lanes l ON l.rate_card_id = rc.rate_card_id
        WHERE rc.carrier_id = CAST(:id AS uuid)
        GROUP BY rc.rate_card_id
        ORDER BY rc.mode, rc.effective_date DESC
    """), {"id": carrier_id})

    return {
        "carrier":    dict(row),
        "rate_cards": [dict(r) for r in rc_result.mappings().all()],
    }


# ── Update Carrier ────────────────────────────────────────────

@router.patch("/{carrier_id}")
async def update_carrier(
    carrier_id: str,
    payload: CarrierUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")

    set_parts = []
    params: dict = {"id": carrier_id}
    uuid_fields = {"status_id", "payment_terms_id", "onboarding_status_id",
                   "safety_rating_id", "remittance_party_id"}

    for k, v in updates.items():
        if k in uuid_fields:
            set_parts.append(f"{k} = CAST(:{k} AS uuid)")
        else:
            set_parts.append(f"{k} = :{k}")
        params[k] = v

    set_clause = ", ".join(set_parts)
    result = await db.execute(
        text(f"UPDATE tms.carriers SET {set_clause}, updated_at=NOW() WHERE carrier_id=CAST(:id AS uuid) RETURNING carrier_id"),
        params
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Carrier not found.")
    return {"carrier_id": str(row["carrier_id"])}
