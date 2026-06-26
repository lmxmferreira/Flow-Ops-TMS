"""
routers/rating.py
TMS-RATE-001 + TMS-RATE-002 + TMS-RATE-003:
Carrier freight cost calculation with full rate structure support.
Rate types: flat, per_mile, per_km, per_lb, per_kg, per_cwt, per_pallet,
            per_carton, per_unit, per_stop, per_zone, per_lane,
            per_container, percentage_of_value, custom_formula,
            minimum, maximum
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
import json
from decimal import Decimal

router = APIRouter()

RATE_TYPE_PRIORITY = {
    "spot":              6,
    "route_guide":       5,
    "customer_specific": 4,
    "contract":          3,
    "tariff":            2,
    "carrier_specific":  1,
}

RATE_TYPES = ["contract", "tariff", "spot", "route_guide", "customer_specific", "carrier_specific"]

ALL_CHARGE_TYPES = [
    "base_flat", "per_mile", "per_km", "per_lb", "per_kg", "per_cwt",
    "per_pallet", "per_carton", "per_unit", "per_stop", "per_zone",
    "per_lane", "per_container", "percentage_of_value", "custom_formula",
    "minimum", "maximum",
]


# ================================================================== #
# Pydantic Models
# ================================================================== #

class RateCardCreate(BaseModel):
    carrier_id: str
    name: str
    mode: str
    currency: str = "USD"
    effective_date: str
    expiry_date: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    rate_type: str = "contract"
    customer_party_id: Optional[str] = None
    contract_reference: Optional[str] = None
    route_priority: int = 0

class RateCardUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    currency: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    rate_type: Optional[str] = None
    customer_party_id: Optional[str] = None
    contract_reference: Optional[str] = None
    route_priority: Optional[int] = None

class LaneCreate(BaseModel):
    rate_card_id: str
    lane_name: str
    origin_type: str = "any"
    origin_value: Optional[str] = None
    destination_type: str = "any"
    destination_value: Optional[str] = None
    min_weight_kg: Optional[float] = None
    max_weight_kg: Optional[float] = None
    min_distance_km: Optional[float] = None
    max_distance_km: Optional[float] = None
    priority: int = 0
    is_active: bool = True

class LaneUpdate(BaseModel):
    lane_name: Optional[str] = None
    origin_type: Optional[str] = None
    origin_value: Optional[str] = None
    destination_type: Optional[str] = None
    destination_value: Optional[str] = None
    min_weight_kg: Optional[float] = None
    max_weight_kg: Optional[float] = None
    min_distance_km: Optional[float] = None
    max_distance_km: Optional[float] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class RateLineCreate(BaseModel):
    lane_id: str
    charge_type: str
    charge_code: str = "LINEHAUL"
    description: Optional[str] = None
    rate_amount: float
    currency: str = "USD"
    uom: Optional[str] = None
    min_charge: Optional[float] = None
    max_charge: Optional[float] = None
    formula_text: Optional[str] = None
    zone_value: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

class RateLineUpdate(BaseModel):
    charge_type: Optional[str] = None
    charge_code: Optional[str] = None
    description: Optional[str] = None
    rate_amount: Optional[float] = None
    uom: Optional[str] = None
    min_charge: Optional[float] = None
    max_charge: Optional[float] = None
    formula_text: Optional[str] = None
    zone_value: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class FuelSurchargeCreate(BaseModel):
    carrier_id: str
    name: str
    mode: Optional[str] = None
    effective_date: str
    expiry_date: Optional[str] = None
    rate_type: str = "percentage"
    rate_value: float
    basis: str = "linehaul"
    is_active: bool = True

class FuelSurchargeUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    rate_type: Optional[str] = None
    rate_value: Optional[float] = None
    basis: Optional[str] = None
    is_active: Optional[bool] = None

class AccessorialCreate(BaseModel):
    carrier_id: str
    charge_code: str
    description: str
    charge_type: str = "flat"
    rate_amount: float
    currency: str = "USD"
    applies_to_modes: list[str] = ["FTL", "LTL", "Parcel"]
    is_active: bool = True

class AccessorialUpdate(BaseModel):
    charge_code: Optional[str] = None
    description: Optional[str] = None
    charge_type: Optional[str] = None
    rate_amount: Optional[float] = None
    applies_to_modes: Optional[list[str]] = None
    is_active: Optional[bool] = None

class CostOverride(BaseModel):
    cost_id: str
    amount: float
    override_reason: str


# ================================================================== #
# Rate Cards
# ================================================================== #

@router.get("/rate-cards")
async def list_rate_cards(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    rate_type: Optional[str] = Query(None),
    customer_party_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if carrier_id:
        conditions.append("rc.carrier_id = CAST(:carrier_id AS uuid)")
        params["carrier_id"] = carrier_id
    if mode:
        conditions.append("rc.mode = :mode")
        params["mode"] = mode
    if status:
        conditions.append("rc.status = :status")
        params["status"] = status
    if rate_type:
        conditions.append("rc.rate_type = :rate_type")
        params["rate_type"] = rate_type
    if customer_party_id:
        conditions.append("rc.customer_party_id = CAST(:customer_party_id AS uuid)")
        params["customer_party_id"] = customer_party_id
    where = " AND ".join(conditions)

    result = await db.execute(text(f"""
        SELECT
            rc.rate_card_id, rc.name, rc.mode, rc.currency,
            rc.effective_date, rc.expiry_date, rc.status, rc.notes,
            rc.rate_type, rc.contract_reference, rc.route_priority,
            rc.created_at, rc.updated_at,
            p.party_name  AS carrier_name,
            cp.party_name AS customer_name,
            COUNT(DISTINCT l.lane_id) AS lane_count
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carriers  c  ON c.carrier_id   = rc.carrier_id
        LEFT JOIN tms.parties   p  ON p.party_id     = c.party_id
        LEFT JOIN tms.parties   cp ON cp.party_id    = rc.customer_party_id
        LEFT JOIN tms.carrier_rate_lanes l ON l.rate_card_id = rc.rate_card_id
        WHERE {where}
        GROUP BY rc.rate_card_id, p.party_name, cp.party_name
        ORDER BY rc.rate_type, rc.mode, rc.effective_date DESC
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/rate-cards", status_code=201)
async def create_rate_card(
    payload: RateCardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    data = payload.model_dump()
    result = await db.execute(text("""
        INSERT INTO tms.carrier_rate_cards
            (carrier_id, name, mode, currency, effective_date, expiry_date,
             status, notes, rate_type, customer_party_id, contract_reference, route_priority)
        VALUES
            (CAST(:carrier_id AS uuid), :name, :mode, :currency,
             CAST(:effective_date AS date), CAST(:expiry_date AS date),
             :status, :notes, :rate_type,
             CAST(:customer_party_id AS uuid), :contract_reference, :route_priority)
        RETURNING *
    """), data)
    await db.commit()
    return dict(result.mappings().one())


@router.get("/rate-cards/{card_id}")
async def get_rate_card(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT rc.*,
            p.party_name  AS carrier_name,
            cp.party_name AS customer_name
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carriers  c  ON c.carrier_id = rc.carrier_id
        LEFT JOIN tms.parties   p  ON p.party_id   = c.party_id
        LEFT JOIN tms.parties   cp ON cp.party_id  = rc.customer_party_id
        WHERE rc.rate_card_id = CAST(:id AS uuid)
    """), {"id": card_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Rate card not found.")
    return dict(row)


@router.patch("/rate-cards/{card_id}")
async def update_rate_card(
    card_id: str,
    payload: RateCardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    set_parts = []
    params: dict[str, Any] = {"id": card_id}
    for k, v in updates.items():
        if k == "customer_party_id" and v is not None:
            set_parts.append(f"{k} = CAST(:{k} AS uuid)")
        elif k in ("effective_date", "expiry_date") and v is not None:
            set_parts.append(f"{k} = CAST(:{k} AS date)")
        else:
            set_parts.append(f"{k} = :{k}")
        params[k] = v
    set_clause = ", ".join(set_parts)
    result = await db.execute(
        text(f"UPDATE tms.carrier_rate_cards SET {set_clause}, updated_at=NOW() WHERE rate_card_id=CAST(:id AS uuid) RETURNING *"),
        params
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Rate card not found.")
    return dict(row)


@router.delete("/rate-cards/{card_id}", status_code=204)
async def delete_rate_card(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(text("DELETE FROM tms.carrier_rate_cards WHERE rate_card_id=CAST(:id AS uuid)"), {"id": card_id})
    await db.commit()


# ================================================================== #
# Lanes
# ================================================================== #

@router.get("/rate-cards/{card_id}/lanes")
async def list_lanes(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT l.*, COUNT(rl.rate_line_id) AS rate_line_count
        FROM tms.carrier_rate_lanes l
        LEFT JOIN tms.carrier_rate_lines rl ON rl.lane_id = l.lane_id
        WHERE l.rate_card_id = CAST(:card_id AS uuid)
        GROUP BY l.lane_id
        ORDER BY l.priority DESC, l.lane_name
    """), {"card_id": card_id})
    return [dict(r) for r in result.mappings().all()]


@router.post("/lanes", status_code=201)
async def create_lane(
    payload: LaneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.carrier_rate_lanes
            (rate_card_id, lane_name, origin_type, origin_value,
             destination_type, destination_value, min_weight_kg, max_weight_kg,
             min_distance_km, max_distance_km, priority, is_active)
        VALUES
            (CAST(:rate_card_id AS uuid), :lane_name, :origin_type, :origin_value,
             :destination_type, :destination_value, :min_weight_kg, :max_weight_kg,
             :min_distance_km, :max_distance_km, :priority, :is_active)
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/lanes/{lane_id}")
async def update_lane(
    lane_id: str,
    payload: LaneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = lane_id
    result = await db.execute(
        text(f"UPDATE tms.carrier_rate_lanes SET {set_clauses}, updated_at=NOW() WHERE lane_id=CAST(:id AS uuid) RETURNING *"),
        updates
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Lane not found.")
    return dict(row)


@router.delete("/lanes/{lane_id}", status_code=204)
async def delete_lane(
    lane_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(text("DELETE FROM tms.carrier_rate_lanes WHERE lane_id=CAST(:id AS uuid)"), {"id": lane_id})
    await db.commit()


# ================================================================== #
# Rate Lines
# ================================================================== #

@router.get("/lanes/{lane_id}/rate-lines")
async def list_rate_lines(
    lane_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.carrier_rate_lines
        WHERE lane_id = CAST(:lane_id AS uuid)
        ORDER BY sort_order, rate_line_id
    """), {"lane_id": lane_id})
    return [dict(r) for r in result.mappings().all()]


@router.post("/rate-lines", status_code=201)
async def create_rate_line(
    payload: RateLineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.carrier_rate_lines
            (lane_id, charge_type, charge_code, description, rate_amount,
             currency, uom, min_charge, max_charge, formula_text, zone_value,
             is_active, sort_order)
        VALUES
            (CAST(:lane_id AS uuid), :charge_type, :charge_code, :description, :rate_amount,
             :currency, :uom, :min_charge, :max_charge, :formula_text, :zone_value,
             :is_active, :sort_order)
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/rate-lines/{line_id}")
async def update_rate_line(
    line_id: str,
    payload: RateLineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = line_id
    result = await db.execute(
        text(f"UPDATE tms.carrier_rate_lines SET {set_clauses}, updated_at=NOW() WHERE rate_line_id=CAST(:id AS uuid) RETURNING *"),
        updates
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Rate line not found.")
    return dict(row)


@router.delete("/rate-lines/{line_id}", status_code=204)
async def delete_rate_line(
    line_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(text("DELETE FROM tms.carrier_rate_lines WHERE rate_line_id=CAST(:id AS uuid)"), {"id": line_id})
    await db.commit()


# ================================================================== #
# Fuel Surcharges
# ================================================================== #

@router.get("/fuel-surcharges")
async def list_fuel_surcharges(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    params: dict[str, Any] = {}
    where = "1=1"
    if carrier_id:
        where += " AND carrier_id = CAST(:carrier_id AS uuid)"
        params["carrier_id"] = carrier_id
    result = await db.execute(
        text(f"SELECT * FROM tms.fuel_surcharge_schedules WHERE {where} ORDER BY effective_date DESC"),
        params
    )
    return [dict(r) for r in result.mappings().all()]


@router.post("/fuel-surcharges", status_code=201)
async def create_fuel_surcharge(
    payload: FuelSurchargeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import uuid as _uuid
    schedule_code = f"FSC-{payload.carrier_id[:8].upper()}-{payload.mode or 'ALL'}-{payload.effective_date[:7]}-{str(_uuid.uuid4())[:4]}"
    result = await db.execute(text("""
        INSERT INTO tms.fuel_surcharge_schedules
            (schedule_code, carrier_id, name, mode, effective_date, expiry_date,
             rate_type, rate_value, basis, is_active)
        VALUES
            (:schedule_code, CAST(:carrier_id AS uuid), :name, :mode,
             CAST(:effective_date AS date), CAST(:expiry_date AS date),
             :rate_type, :rate_value, :basis, :is_active)
        RETURNING *
    """), {**payload.model_dump(), "schedule_code": schedule_code})
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/fuel-surcharges/{fsc_id}")
async def update_fuel_surcharge(
    fsc_id: str,
    payload: FuelSurchargeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = fsc_id
    result = await db.execute(
        text(f"UPDATE tms.fuel_surcharge_schedules SET {set_clauses}, updated_at=NOW() WHERE fuel_surcharge_schedule_id=CAST(:id AS uuid) RETURNING *"),
        updates
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Fuel surcharge not found.")
    return dict(row)


@router.delete("/fuel-surcharges/{fsc_id}", status_code=204)
async def delete_fuel_surcharge(
    fsc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(text("DELETE FROM tms.fuel_surcharge_schedules WHERE fuel_surcharge_schedule_id=CAST(:id AS uuid)"), {"id": fsc_id})
    await db.commit()


# ================================================================== #
# Accessorials
# ================================================================== #

@router.get("/accessorials")
async def list_accessorials(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    params: dict[str, Any] = {}
    where = "1=1"
    if carrier_id:
        where += " AND carrier_id = CAST(:carrier_id AS uuid)"
        params["carrier_id"] = carrier_id
    result = await db.execute(
        text(f"SELECT * FROM tms.accessorial_charges WHERE {where} ORDER BY charge_code"),
        params
    )
    return [dict(r) for r in result.mappings().all()]


@router.post("/accessorials", status_code=201)
async def create_accessorial(
    payload: AccessorialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.accessorial_charges
            (carrier_id, charge_code, description, charge_type, rate_amount,
             currency, applies_to_modes, is_active)
        VALUES
            (CAST(:carrier_id AS uuid), :charge_code, :description, :charge_type, :rate_amount,
             :currency, :applies_to_modes, :is_active)
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/accessorials/{acc_id}")
async def update_accessorial(
    acc_id: str,
    payload: AccessorialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    set_parts = []
    params: dict[str, Any] = {"id": acc_id}
    for k, v in updates.items():
        set_parts.append(f"{k} = :{k}")
        params[k] = v
    result = await db.execute(
        text(f"UPDATE tms.accessorial_charges SET {', '.join(set_parts)}, updated_at=NOW() WHERE accessorial_id=CAST(:id AS uuid) RETURNING *"),
        params
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Accessorial not found.")
    return dict(row)


@router.delete("/accessorials/{acc_id}", status_code=204)
async def delete_accessorial(
    acc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(text("DELETE FROM tms.accessorial_charges WHERE accessorial_id=CAST(:id AS uuid)"), {"id": acc_id})
    await db.commit()


# ================================================================== #
# Rating Engine
# ================================================================== #

async def _find_best_lane(
    db: AsyncSession,
    carrier_id: str,
    mode: str,
    origin_country: Optional[str],
    origin_state: Optional[str],
    origin_zip: Optional[str],
    dest_country: Optional[str],
    dest_state: Optional[str],
    dest_zip: Optional[str],
    weight_kg: Optional[float],
    distance_km: Optional[float],
    customer_party_id: Optional[str] = None,
) -> Optional[dict]:
    result = await db.execute(text("""
        SELECT l.*, rc.currency AS card_currency, rc.rate_type,
               rc.route_priority, rc.customer_party_id
        FROM tms.carrier_rate_lanes l
        JOIN tms.carrier_rate_cards rc ON rc.rate_card_id = l.rate_card_id
        WHERE rc.carrier_id = CAST(:carrier_id AS uuid)
          AND rc.mode = :mode
          AND rc.status = 'active'
          AND rc.effective_date <= CURRENT_DATE
          AND (rc.expiry_date IS NULL OR rc.expiry_date >= CURRENT_DATE)
          AND l.is_active = TRUE
          AND (l.min_weight_kg IS NULL OR :weight_kg IS NULL OR :weight_kg >= l.min_weight_kg)
          AND (l.max_weight_kg IS NULL OR :weight_kg IS NULL OR :weight_kg <= l.max_weight_kg)
          AND (l.min_distance_km IS NULL OR :distance_km IS NULL OR :distance_km >= l.min_distance_km)
          AND (l.max_distance_km IS NULL OR :distance_km IS NULL OR :distance_km <= l.max_distance_km)
        ORDER BY l.priority DESC
        LIMIT 50
    """), {"carrier_id": carrier_id, "mode": mode, "weight_kg": weight_kg, "distance_km": distance_km})
    lanes = result.mappings().all()

    def loc_score(ltype: str, lval: Optional[str], val: Optional[str]) -> int:
        if ltype == "any": return 1
        if not val or not lval: return 0
        if ltype == "zip"     and val.startswith(lval): return 4
        if ltype == "state"   and val == lval:           return 3
        if ltype == "country" and val == lval:           return 2
        if ltype == "region":                            return 1
        return 0

    best = None
    best_score = -1
    for lane in lanes:
        o_score = loc_score(lane["origin_type"],      lane.get("origin_value"),      origin_zip or origin_state or origin_country)
        d_score = loc_score(lane["destination_type"], lane.get("destination_value"), dest_zip   or dest_state   or dest_country)
        if o_score == 0 and lane["origin_type"]      != "any": continue
        if d_score == 0 and lane["destination_type"] != "any": continue

        rate_type_score = RATE_TYPE_PRIORITY.get(lane["rate_type"], 0)
        customer_boost  = 0
        if lane["rate_type"] == "customer_specific" and customer_party_id:
            if str(lane.get("customer_party_id")) == customer_party_id:
                customer_boost = 10
            else:
                continue

        total = rate_type_score * 100 + customer_boost + o_score * 10 + d_score * 10 + (lane["route_priority"] or 0) + (lane["priority"] or 0)
        if total > best_score:
            best_score = total
            best = dict(lane)
    return best


def _calculate_charge(
    ct: str,
    rate: Decimal,
    weight_kg: float,
    weight_lb: float,
    pallets: float,
    cartons: float,
    units: float,
    stops: int,
    distance_km: float,
    distance_mi: float,
    shipment_value: float,
    lane_name: str,
    zone_value: Optional[str],
    formula_text: Optional[str],
    shipment_data: dict,
) -> tuple[Optional[Decimal], Decimal]:
    """
    Returns (quantity, amount) for a given charge type.
    Returns (None, Decimal(0)) for minimum/maximum (handled separately).
    """
    match ct:
        case "base_flat":
            return Decimal("1"), rate

        case "per_mile":
            qty = Decimal(str(distance_mi))
            return qty, qty * rate

        case "per_km":
            qty = Decimal(str(distance_km))
            return qty, qty * rate

        case "per_lb":
            qty = Decimal(str(weight_lb))
            return qty, qty * rate

        case "per_kg":
            qty = Decimal(str(weight_kg))
            return qty, qty * rate

        case "per_cwt":
            # per hundredweight = per 100 lbs
            qty = Decimal(str(weight_lb / 100))
            return qty, qty * rate

        case "per_pallet":
            qty = Decimal(str(pallets))
            return qty, qty * rate

        case "per_carton":
            qty = Decimal(str(cartons))
            return qty, qty * rate

        case "per_unit":
            qty = Decimal(str(units))
            return qty, qty * rate

        case "per_stop":
            qty = Decimal(str(stops))
            return qty, qty * rate

        case "per_zone":
            # rate per zone — quantity is always 1, rate is the zone rate
            return Decimal("1"), rate

        case "per_lane":
            # flat rate per lane — quantity 1
            return Decimal("1"), rate

        case "per_container":
            # treat containers same as cartons for now
            qty = Decimal(str(cartons))
            return qty, qty * rate

        case "percentage_of_value":
            if shipment_value > 0:
                amt = (Decimal(str(shipment_value)) * rate / Decimal("100")).quantize(Decimal("0.01"))
            else:
                amt = Decimal("0")
            return rate, amt

        case "custom_formula":
            if formula_text:
                try:
                    safe_vars = {
                        "weight_kg":     weight_kg,
                        "weight_lb":     weight_lb,
                        "pallets":       pallets,
                        "cartons":       cartons,
                        "units":         units,
                        "stops":         stops,
                        "distance_km":   distance_km,
                        "distance_mi":   distance_mi,
                        "shipment_value":shipment_value,
                        "rate":          float(rate),
                    }
                    result = eval(formula_text, {"__builtins__": {}}, safe_vars)  # noqa: S307
                    return None, Decimal(str(result)).quantize(Decimal("0.01"))
                except Exception:
                    return None, Decimal("0")
            return None, Decimal("0")

        case _:
            return None, Decimal("0")


@router.post("/rate-shipment/{shipment_id}")
async def rate_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # 1. Load shipment
    shp_result = await db.execute(text("""
        SELECT
            s.shipment_id, s.carrier_id, s.mode, s.status,
            s.total_weight_kg, s.total_weight_lb,
            s.total_pallets, s.total_cartons, s.total_pieces,
            s.distance_km, s.distance_miles,
            COALESCE(s.declared_value, 0) AS declared_value,
            o.country_code   AS origin_country,
            o.state_province AS origin_state,
            o.postal_code    AS origin_zip,
            d.country_code   AS dest_country,
            d.state_province AS dest_state,
            d.postal_code    AS dest_zip,
            (SELECT COUNT(*) FROM tms.shipment_stops ss WHERE ss.shipment_id = s.shipment_id) AS stop_count
        FROM tms.shipments s
        LEFT JOIN tms.locations o ON o.location_id = s.origin_location_id
        LEFT JOIN tms.locations d ON d.location_id = s.destination_location_id
        WHERE s.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    shp = shp_result.mappings().one_or_none()
    if not shp:
        raise HTTPException(404, "Shipment not found.")
    if not shp["carrier_id"]:
        raise HTTPException(422, "Shipment has no carrier assigned.")

    shp = dict(shp)
    weight_kg      = float(shp["total_weight_kg"]   or 0)
    weight_lb      = float(shp["total_weight_lb"]   or weight_kg * 2.20462)
    pallets        = float(shp["total_pallets"]      or 0)
    cartons        = float(shp["total_cartons"]      or 0)
    units          = float(shp["total_pieces"]       or 0)
    distance_km    = float(shp["distance_km"]        or 0)
    distance_mi    = float(shp["distance_miles"]     or distance_km * 0.621371)
    stop_count     = int(shp.get("stop_count")       or 1)
    declared_value = float(shp.get("declared_value") or 0)

    # 2. Find best lane
    lane = await _find_best_lane(
        db,
        carrier_id=str(shp["carrier_id"]),
        mode=shp["mode"] or "FTL",
        origin_country=shp.get("origin_country"),
        origin_state=shp.get("origin_state"),
        origin_zip=shp.get("origin_zip"),
        dest_country=shp.get("dest_country"),
        dest_state=shp.get("dest_state"),
        dest_zip=shp.get("dest_zip"),
        weight_kg=weight_kg or None,
        distance_km=distance_km or None,
    )
    if not lane:
        raise HTTPException(422, "No matching rate lane found.")

    # 3. Load rate lines
    rl_result = await db.execute(text("""
        SELECT * FROM tms.carrier_rate_lines
        WHERE lane_id = CAST(:lane_id AS uuid) AND is_active = TRUE
        ORDER BY sort_order
    """), {"lane_id": lane["lane_id"]})
    rate_lines = rl_result.mappings().all()

    # 4. Calculate charges
    cost_rows = []
    linehaul_total = Decimal("0")

    for rl in rate_lines:
        ct    = rl["charge_type"]
        rate  = Decimal(str(rl["rate_amount"]))
        min_c = Decimal(str(rl["min_charge"])) if rl["min_charge"] else None
        max_c = Decimal(str(rl["max_charge"])) if rl["max_charge"] else None

        if ct in ("minimum", "maximum"):
            continue

        qty, amount = _calculate_charge(
            ct=ct, rate=rate,
            weight_kg=weight_kg, weight_lb=weight_lb,
            pallets=pallets, cartons=cartons, units=units,
            stops=stop_count, distance_km=distance_km, distance_mi=distance_mi,
            shipment_value=declared_value,
            lane_name=lane["lane_name"],
            zone_value=rl.get("zone_value"),
            formula_text=rl.get("formula_text"),
            shipment_data=shp,
        )

        if min_c and amount < min_c: amount = min_c
        if max_c and amount > max_c: amount = max_c

        cost_rows.append({
            "shipment_id":  shipment_id,
            "rate_card_id": str(lane["rate_card_id"]),
            "lane_id":      str(lane["lane_id"]),
            "charge_code":  rl["charge_code"],
            "charge_type":  ct,
            "description":  rl["description"] or ct.replace("_", " ").title(),
            "quantity":     float(qty) if qty is not None else None,
            "rate_amount":  float(rate),
            "amount":       float(amount),
            "currency":     rl["currency"] or "USD",
        })
        linehaul_total += amount

    # Apply minimum/maximum
    for rl in rate_lines:
        ct   = rl["charge_type"]
        rate = Decimal(str(rl["rate_amount"]))
        if ct == "minimum" and linehaul_total < rate:
            adj = rate - linehaul_total
            cost_rows.append({
                "shipment_id": shipment_id, "rate_card_id": str(lane["rate_card_id"]),
                "lane_id": str(lane["lane_id"]), "charge_code": "MINIMUM",
                "charge_type": "minimum", "description": "Minimum Charge Adjustment",
                "quantity": 1, "rate_amount": float(rate), "amount": float(adj), "currency": "USD",
            })
            linehaul_total = rate
        elif ct == "maximum" and linehaul_total > rate:
            adj = linehaul_total - rate
            cost_rows.append({
                "shipment_id": shipment_id, "rate_card_id": str(lane["rate_card_id"]),
                "lane_id": str(lane["lane_id"]), "charge_code": "MAXIMUM",
                "charge_type": "maximum", "description": "Maximum Charge Cap",
                "quantity": 1, "rate_amount": float(rate), "amount": float(-adj), "currency": "USD",
            })
            linehaul_total = rate

    # 5. Fuel surcharge
    fsc_result = await db.execute(text("""
        SELECT * FROM tms.fuel_surcharge_schedules
        WHERE carrier_id = CAST(:carrier_id AS uuid)
          AND is_active = TRUE
          AND effective_date <= CURRENT_DATE
          AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
          AND (mode IS NULL OR mode = :mode)
        ORDER BY mode NULLS LAST LIMIT 1
    """), {"carrier_id": str(shp["carrier_id"]), "mode": shp["mode"] or "FTL"})
    fsc = fsc_result.mappings().one_or_none()

    if fsc:
        rate = Decimal(str(fsc["rate_value"]))
        fsc_amount = Decimal("0")
        if fsc["rate_type"] == "percentage":
            fsc_amount = (linehaul_total * rate / Decimal("100")).quantize(Decimal("0.01"))
        elif fsc["rate_type"] == "per_mile":
            fsc_amount = (Decimal(str(distance_mi)) * rate).quantize(Decimal("0.01"))
        elif fsc["rate_type"] == "per_km":
            fsc_amount = (Decimal(str(distance_km)) * rate).quantize(Decimal("0.01"))
        elif fsc["rate_type"] == "flat":
            fsc_amount = rate

        if fsc_amount > 0:
            cost_rows.append({
                "shipment_id": shipment_id, "rate_card_id": str(lane["rate_card_id"]),
                "lane_id": str(lane["lane_id"]), "charge_code": "FSC",
                "charge_type": "fuel_surcharge",
                "description": f"Fuel Surcharge ({fsc['rate_value']}{'%' if fsc['rate_type']=='percentage' else ''})",
                "quantity": float(rate), "rate_amount": float(rate),
                "amount": float(fsc_amount), "currency": "USD",
            })

    # 6. Persist
    await db.execute(
        text("DELETE FROM tms.shipment_costs WHERE shipment_id = CAST(:id AS uuid) AND is_override = FALSE"),
        {"id": shipment_id}
    )
    for row in cost_rows:
        await db.execute(text("""
            INSERT INTO tms.shipment_costs
                (shipment_id, rate_card_id, lane_id, charge_code, charge_type,
                 description, quantity, rate_amount, amount, currency, rated_by)
            VALUES
                (CAST(:shipment_id AS uuid), CAST(:rate_card_id AS uuid), CAST(:lane_id AS uuid),
                 :charge_code, :charge_type, :description, :quantity,
                 :rate_amount, :amount, :currency, 'system')
        """), row)
    await db.commit()

    total = sum(r["amount"] for r in cost_rows)
    return {
        "shipment_id":  shipment_id,
        "carrier_id":   str(shp["carrier_id"]),
        "mode":         shp["mode"],
        "rate_type":    lane.get("rate_type"),
        "lane_matched": {
            "lane_id":      str(lane["lane_id"]),
            "lane_name":    lane["lane_name"],
            "rate_card_id": str(lane["rate_card_id"]),
            "rate_type":    lane.get("rate_type"),
        },
        "cost_lines": cost_rows,
        "total_cost": round(total, 2),
        "currency":   "USD",
    }


@router.get("/shipment-costs/{shipment_id}")
async def get_shipment_costs(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT sc.*, l.lane_name, rc.name AS rate_card_name, rc.mode, rc.rate_type
        FROM tms.shipment_costs sc
        LEFT JOIN tms.carrier_rate_lanes l  ON l.lane_id      = sc.lane_id
        LEFT JOIN tms.carrier_rate_cards rc ON rc.rate_card_id = sc.rate_card_id
        WHERE sc.shipment_id = CAST(:id AS uuid)
        ORDER BY sc.charge_type, sc.rated_at
    """), {"id": shipment_id})
    rows  = [dict(r) for r in result.mappings().all()]
    total = sum(r["amount"] for r in rows)
    return {
        "shipment_id": shipment_id,
        "cost_lines":  rows,
        "total_cost":  round(float(total), 2),
        "currency":    rows[0]["currency"] if rows else "USD",
    }


@router.patch("/shipment-costs/{cost_id}/override")
async def override_shipment_cost(
    cost_id: str,
    payload: CostOverride,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "unknown")
    result = await db.execute(text("""
        UPDATE tms.shipment_costs
        SET amount = :amount, is_override = TRUE,
            override_reason = :reason, rated_by = :rated_by, updated_at = NOW()
        WHERE cost_id = CAST(:id AS uuid)
        RETURNING *
    """), {"amount": payload.amount, "reason": payload.override_reason,
           "rated_by": f"user:{user_id}", "id": cost_id})
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Cost line not found.")
    return dict(row)


# ================================================================== #
# Reference endpoints
# ================================================================== #

@router.get("/rate-types")
async def get_rate_types(current_user: dict = Depends(get_current_user)):
    return [
        {"value": "contract",          "label": "Contract Rate",          "description": "Negotiated contract rates with a carrier"},
        {"value": "tariff",            "label": "Tariff Rate",            "description": "Published carrier tariff / class rates"},
        {"value": "spot",              "label": "Spot Rate",              "description": "One-time spot market rates"},
        {"value": "route_guide",       "label": "Route Guide Rate",       "description": "Routing guide rates by lane priority"},
        {"value": "customer_specific", "label": "Customer-Specific Rate", "description": "Rates negotiated for a specific customer"},
        {"value": "carrier_specific",  "label": "Carrier-Specific Rate",  "description": "Default carrier-published rates"},
    ]


@router.get("/charge-types")
async def get_charge_types(current_user: dict = Depends(get_current_user)):
    """Return all supported rate structure types."""
    return [
        {"value": "base_flat",           "label": "Flat Charge",             "description": "Fixed charge per shipment"},
        {"value": "per_mile",            "label": "Per Mile",                "description": "Charge per mile of distance"},
        {"value": "per_km",              "label": "Per Kilometer",           "description": "Charge per kilometer of distance"},
        {"value": "per_lb",              "label": "Per Pound",               "description": "Charge per pound of weight"},
        {"value": "per_kg",              "label": "Per Kilogram",            "description": "Charge per kilogram of weight"},
        {"value": "per_cwt",             "label": "Per Hundredweight (CWT)", "description": "Charge per 100 lbs of weight"},
        {"value": "per_pallet",          "label": "Per Pallet",              "description": "Charge per pallet"},
        {"value": "per_carton",          "label": "Per Carton",              "description": "Charge per carton"},
        {"value": "per_unit",            "label": "Per Unit",                "description": "Charge per individual unit/piece"},
        {"value": "per_stop",            "label": "Per Stop",                "description": "Charge per delivery/pickup stop"},
        {"value": "per_zone",            "label": "Per Zone",                "description": "Flat rate based on zone"},
        {"value": "per_lane",            "label": "Per Lane",                "description": "Flat rate for the specific lane"},
        {"value": "per_container",       "label": "Per Container",           "description": "Charge per container (ocean/intermodal)"},
        {"value": "percentage_of_value", "label": "% of Declared Value",     "description": "Percentage of shipment declared value"},
        {"value": "custom_formula",      "label": "Custom Formula",          "description": "Arbitrary formula using shipment variables"},
        {"value": "minimum",             "label": "Minimum Charge",          "description": "Floor charge if total falls below threshold"},
        {"value": "maximum",             "label": "Maximum Charge",          "description": "Cap charge if total exceeds threshold"},
    ]
# ================================================================== #
# TMS-RATE-004: Rate Lookup by Shipment Attributes
# Append this to the end of rating.py
# ================================================================== #

class RateLookupRequest(BaseModel):
    mode: str
    carrier_id: Optional[str] = None
    origin_zip: Optional[str] = None
    origin_state: Optional[str] = None
    origin_country: Optional[str] = None
    dest_zip: Optional[str] = None
    dest_state: Optional[str] = None
    dest_country: Optional[str] = None
    weight_kg: Optional[float] = None
    weight_lb: Optional[float] = None
    distance_km: Optional[float] = None
    distance_miles: Optional[float] = None
    total_pallets: Optional[float] = None
    total_cartons: Optional[float] = None
    total_pieces: Optional[float] = None
    declared_value: Optional[float] = None
    stop_count: int = 1
    equipment_type: Optional[str] = None
    service_level: Optional[str] = None
    commodity: Optional[str] = None
    effective_date: Optional[str] = None
    customer_party_id: Optional[str] = None
    limit: int = 10


@router.post("/lookup")
async def lookup_rates(
    payload: RateLookupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-004: Look up applicable rates based on shipment attributes.
    Returns all matching rate cards/lanes ranked by priority with estimated charges.
    Does NOT persist any costs — purely a lookup/preview operation.
    """
    # Derive weights and distances
    weight_kg   = payload.weight_kg or 0.0
    weight_lb   = payload.weight_lb or weight_kg * 2.20462
    distance_km = payload.distance_km or 0.0
    distance_mi = payload.distance_miles or distance_km * 0.621371
    pallets     = payload.total_pallets or 0.0
    cartons     = payload.total_cartons or 0.0
    units       = payload.total_pieces  or 0.0
    stops       = payload.stop_count    or 1
    declared_value = payload.declared_value or 0.0
    eff_date    = payload.effective_date or "CURRENT_DATE"

    # Build carrier filter
    carrier_filter = ""
    params: dict[str, Any] = {
        "mode":        payload.mode,
        "weight_kg":   weight_kg or None,
        "distance_km": distance_km or None,
    }
    if payload.carrier_id:
        carrier_filter = "AND rc.carrier_id = CAST(:carrier_id AS uuid)"
        params["carrier_id"] = payload.carrier_id

    if payload.effective_date:
        from datetime import date as _date
        params["eff_date"] = _date.fromisoformat(payload.effective_date)
        date_expr = ":eff_date"
    else:
        date_expr = "CURRENT_DATE"

    # Query all matching lanes
    result = await db.execute(text(f"""
        SELECT
            l.lane_id, l.lane_name, l.priority AS lane_priority,
            l.origin_type, l.origin_value,
            l.destination_type, l.destination_value,
            rc.rate_card_id, rc.name AS rate_card_name,
            rc.mode, rc.rate_type, rc.currency,
            rc.effective_date, rc.expiry_date,
            rc.contract_reference, rc.route_priority,
            rc.customer_party_id,
            c.carrier_id,
            p.party_name AS carrier_name,
            p.party_code AS carrier_code,
            cp.party_name AS customer_name
        FROM tms.carrier_rate_lanes l
        JOIN tms.carrier_rate_cards rc ON rc.rate_card_id = l.rate_card_id
        JOIN tms.carriers  c  ON c.carrier_id  = rc.carrier_id
        JOIN tms.parties   p  ON p.party_id    = c.party_id
        LEFT JOIN tms.parties cp ON cp.party_id = rc.customer_party_id
        WHERE rc.mode = :mode
          AND rc.status = 'active'
          AND rc.effective_date <= {date_expr}
          AND (rc.expiry_date IS NULL OR rc.expiry_date >= {date_expr})
          AND l.is_active = TRUE
          AND (l.min_weight_kg IS NULL OR CAST(:weight_kg AS numeric) IS NULL OR CAST(:weight_kg AS numeric) >= l.min_weight_kg)
          AND (l.max_weight_kg IS NULL OR CAST(:weight_kg AS numeric) IS NULL OR CAST(:weight_kg AS numeric) <= l.max_weight_kg)
          AND (l.min_distance_km IS NULL OR CAST(:distance_km AS numeric) IS NULL OR CAST(:distance_km AS numeric) >= l.min_distance_km)
          AND (l.max_distance_km IS NULL OR CAST(:distance_km AS numeric) IS NULL OR CAST(:distance_km AS numeric) <= l.max_distance_km)
          {carrier_filter}
        ORDER BY rc.effective_date DESC
    """), params)

    all_lanes = result.mappings().all()

    # Score and filter lanes by location match
    def loc_score(ltype: str, lval: Optional[str], val: Optional[str]) -> int:
        if ltype == "any": return 1
        if not val or not lval: return 0
        if ltype == "zip"     and val.startswith(lval): return 4
        if ltype == "state"   and val == lval:           return 3
        if ltype == "country" and val == lval:           return 2
        if ltype == "region":                            return 1
        return 0

    scored = []
    for lane in all_lanes:
        o_score = loc_score(lane["origin_type"],      lane.get("origin_value"),
                            payload.origin_zip or payload.origin_state or payload.origin_country)
        d_score = loc_score(lane["destination_type"], lane.get("destination_value"),
                            payload.dest_zip or payload.dest_state or payload.dest_country)

        if o_score == 0 and lane["origin_type"]      != "any": continue
        if d_score == 0 and lane["destination_type"] != "any": continue

        # Skip customer-specific rates that don't match
        if lane["rate_type"] == "customer_specific":
            if not payload.customer_party_id:
                continue
            if str(lane.get("customer_party_id") or "") != payload.customer_party_id:
                continue

        rate_type_score = RATE_TYPE_PRIORITY.get(lane["rate_type"], 0)
        total_score = (
            rate_type_score * 100
            + o_score * 10
            + d_score * 10
            + (lane["route_priority"] or 0)
            + (lane["lane_priority"]  or 0)
        )
        scored.append((total_score, dict(lane)))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    top_lanes = scored[:payload.limit]

    if not top_lanes:
        return {
            "mode":    payload.mode,
            "matches": [],
            "message": "No matching rate lanes found for the given attributes.",
        }

    # For each matched lane, load rate lines and estimate charge
    matches = []
    for score, lane in top_lanes:
        rl_result = await db.execute(text("""
            SELECT * FROM tms.carrier_rate_lines
            WHERE lane_id = CAST(:lane_id AS uuid) AND is_active = TRUE
            ORDER BY sort_order
        """), {"lane_id": lane["lane_id"]})
        rate_lines = rl_result.mappings().all()

        line_estimates = []
        linehaul_total = Decimal("0")

        for rl in rate_lines:
            ct    = rl["charge_type"]
            rate  = Decimal(str(rl["rate_amount"]))
            min_c = Decimal(str(rl["min_charge"])) if rl["min_charge"] else None
            max_c = Decimal(str(rl["max_charge"])) if rl["max_charge"] else None

            if ct in ("minimum", "maximum"):
                continue

            qty, amount = _calculate_charge(
                ct=ct, rate=rate,
                weight_kg=weight_kg, weight_lb=weight_lb,
                pallets=pallets, cartons=cartons, units=units,
                stops=stops, distance_km=distance_km, distance_mi=distance_mi,
                shipment_value=declared_value,
                lane_name=lane["lane_name"],
                zone_value=rl.get("zone_value"),
                formula_text=rl.get("formula_text"),
                shipment_data={},
            )
            if min_c and amount < min_c: amount = min_c
            if max_c and amount > max_c: amount = max_c

            line_estimates.append({
                "charge_code":  rl["charge_code"],
                "charge_type":  ct,
                "description":  rl["description"] or ct.replace("_", " ").title(),
                "rate_amount":  float(rate),
                "uom":          rl["uom"],
                "quantity":     float(qty) if qty is not None else None,
                "estimated_amount": float(amount),
                "currency":     rl["currency"] or lane["currency"],
            })
            linehaul_total += amount

        # Apply minimum/maximum to total
        for rl in rate_lines:
            ct   = rl["charge_type"]
            rate = Decimal(str(rl["rate_amount"]))
            if ct == "minimum" and linehaul_total < rate:
                linehaul_total = rate
                line_estimates.append({
                    "charge_code": "MINIMUM", "charge_type": "minimum",
                    "description": "Minimum Charge", "rate_amount": float(rate),
                    "uom": None, "quantity": 1,
                    "estimated_amount": float(rate - linehaul_total + rate),
                    "currency": lane["currency"],
                })
            elif ct == "maximum" and linehaul_total > rate:
                linehaul_total = rate

        matches.append({
            "score":          score,
            "rank":           len(matches) + 1,
            "carrier_id":     str(lane["carrier_id"]),
            "carrier_name":   lane["carrier_name"],
            "carrier_code":   lane["carrier_code"],
            "rate_card_id":   str(lane["rate_card_id"]),
            "rate_card_name": lane["rate_card_name"],
            "rate_type":      lane["rate_type"],
            "lane_id":        str(lane["lane_id"]),
            "lane_name":      lane["lane_name"],
            "origin_type":    lane["origin_type"],
            "origin_value":   lane["origin_value"],
            "dest_type":      lane["destination_type"],
            "dest_value":     lane["destination_value"],
            "effective_date": str(lane["effective_date"]),
            "expiry_date":    str(lane["expiry_date"]) if lane["expiry_date"] else None,
            "contract_reference": lane["contract_reference"],
            "customer_name":  lane["customer_name"],
            "currency":       lane["currency"],
            "rate_lines":     line_estimates,
            "estimated_total": float(linehaul_total),
        })

    return {
        "mode":       payload.mode,
        "origin":     f"{payload.origin_zip or payload.origin_state or payload.origin_country or 'any'}",
        "destination":f"{payload.dest_zip or payload.dest_state or payload.dest_country or 'any'}",
        "weight_kg":  weight_kg,
        "weight_lb":  round(weight_lb, 2),
        "distance_km":distance_km,
        "distance_mi":round(distance_mi, 2),
        "effective_date": payload.effective_date or "today",
        "matches":    matches,
        "total_matches": len(matches),
    }

# ================================================================== #
# TMS-RATE-005: Multi-Carrier Rate Comparison & Best Rate Selection
# Append this to the end of rating.py
# ================================================================== #

class RateCompareRequest(BaseModel):
    mode: str
    origin_zip: Optional[str] = None
    origin_state: Optional[str] = None
    origin_country: Optional[str] = None
    dest_zip: Optional[str] = None
    dest_state: Optional[str] = None
    dest_country: Optional[str] = None
    weight_kg: Optional[float] = None
    weight_lb: Optional[float] = None
    distance_km: Optional[float] = None
    distance_miles: Optional[float] = None
    total_pallets: Optional[float] = None
    total_cartons: Optional[float] = None
    total_pieces: Optional[float] = None
    declared_value: Optional[float] = None
    stop_count: int = 1
    effective_date: Optional[str] = None
    customer_party_id: Optional[str] = None
    # Selection criteria: lowest_cost | route_guide | best_rate_type
    selection_criteria: str = "lowest_cost"
    # Optional: restrict to specific carriers
    carrier_ids: Optional[list[str]] = None


@router.post("/compare")
async def compare_rates(
    payload: RateCompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-005: Multi-carrier rate comparison and best rate selection.
    Queries all active carriers (or a specified subset), finds the best
    matching lane per carrier, calculates estimated charges, and returns
    a ranked comparison with the recommended best rate highlighted.
    """
    from datetime import date as _date

    weight_kg      = payload.weight_kg or 0.0
    weight_lb      = payload.weight_lb or weight_kg * 2.20462
    distance_km    = payload.distance_km or 0.0
    distance_mi    = payload.distance_miles or distance_km * 0.621371
    pallets        = payload.total_pallets or 0.0
    cartons        = payload.total_cartons or 0.0
    units          = payload.total_pieces  or 0.0
    stops          = payload.stop_count    or 1
    declared_value = payload.declared_value or 0.0
    eff_date       = _date.fromisoformat(payload.effective_date) if payload.effective_date else None

    # ── 1. Get all active carriers (or subset) ────────────────────
    if payload.carrier_ids:
        carrier_result = await db.execute(text("""
            SELECT c.carrier_id, p.party_name AS carrier_name, p.party_code AS carrier_code
            FROM tms.carriers c
            JOIN tms.parties p ON p.party_id = c.party_id
            WHERE c.carrier_id = ANY(CAST(:ids AS uuid[]))
        """), {"ids": payload.carrier_ids})
    else:
        carrier_result = await db.execute(text("""
            SELECT c.carrier_id, p.party_name AS carrier_name, p.party_code AS carrier_code
            FROM tms.carriers c
            JOIN tms.parties p ON p.party_id = c.party_id
            ORDER BY p.party_name
        """))
    carriers = carrier_result.mappings().all()

    if not carriers:
        return {
            "mode": payload.mode,
            "selection_criteria": payload.selection_criteria,
            "carriers_evaluated": 0,
            "results": [],
            "best_rate": None,
            "message": "No carriers found.",
        }

    # ── 2. For each carrier, find best lane + calculate charges ───
    results = []

    for carrier in carriers:
        carrier_id = str(carrier["carrier_id"])

        # Build date filter
        if eff_date:
            date_filter = "AND rc.effective_date <= :eff_date AND (rc.expiry_date IS NULL OR rc.expiry_date >= :eff_date)"
            date_params: dict[str, Any] = {"eff_date": eff_date}
        else:
            date_filter = "AND rc.effective_date <= CURRENT_DATE AND (rc.expiry_date IS NULL OR rc.expiry_date >= CURRENT_DATE)"
            date_params = {}

        lane_result = await db.execute(text(f"""
            SELECT
                l.lane_id, l.lane_name, l.priority AS lane_priority,
                l.origin_type, l.origin_value,
                l.destination_type, l.destination_value,
                rc.rate_card_id, rc.name AS rate_card_name,
                rc.rate_type, rc.currency, rc.route_priority,
                rc.customer_party_id, rc.contract_reference
            FROM tms.carrier_rate_lanes l
            JOIN tms.carrier_rate_cards rc ON rc.rate_card_id = l.rate_card_id
            WHERE rc.carrier_id = CAST(:carrier_id AS uuid)
              AND rc.mode = :mode
              AND rc.status = 'active'
              {date_filter}
              AND l.is_active = TRUE
              AND (l.min_weight_kg IS NULL OR CAST(:weight_kg AS numeric) IS NULL OR CAST(:weight_kg AS numeric) >= l.min_weight_kg)
              AND (l.max_weight_kg IS NULL OR CAST(:weight_kg AS numeric) IS NULL OR CAST(:weight_kg AS numeric) <= l.max_weight_kg)
              AND (l.min_distance_km IS NULL OR CAST(:distance_km AS numeric) IS NULL OR CAST(:distance_km AS numeric) >= l.min_distance_km)
              AND (l.max_distance_km IS NULL OR CAST(:distance_km AS numeric) IS NULL OR CAST(:distance_km AS numeric) <= l.max_distance_km)
            ORDER BY l.priority DESC
            LIMIT 20
        """), {
            "carrier_id":  carrier_id,
            "mode":        payload.mode,
            "weight_kg":   weight_kg or None,
            "distance_km": distance_km or None,
            **date_params,
        })
        lanes = lane_result.mappings().all()

        if not lanes:
            results.append({
                "carrier_id":    carrier_id,
                "carrier_name":  carrier["carrier_name"],
                "carrier_code":  carrier["carrier_code"],
                "status":        "no_rates",
                "message":       "No applicable rate lanes found.",
                "estimated_total": None,
                "rate_lines":    [],
            })
            continue

        # Score and pick best lane
        def loc_score(ltype: str, lval: Optional[str], val: Optional[str]) -> int:
            if ltype == "any": return 1
            if not val or not lval: return 0
            if ltype == "zip"     and val.startswith(lval): return 4
            if ltype == "state"   and val == lval:           return 3
            if ltype == "country" and val == lval:           return 2
            return 1

        best_lane = None
        best_score = -1
        for lane in lanes:
            o_score = loc_score(lane["origin_type"],      lane.get("origin_value"),      payload.origin_zip or payload.origin_state or payload.origin_country)
            d_score = loc_score(lane["destination_type"], lane.get("destination_value"), payload.dest_zip   or payload.dest_state   or payload.dest_country)
            if o_score == 0 and lane["origin_type"]      != "any": continue
            if d_score == 0 and lane["destination_type"] != "any": continue

            rate_type_score = RATE_TYPE_PRIORITY.get(lane["rate_type"], 0)
            customer_boost  = 0
            if lane["rate_type"] == "customer_specific" and payload.customer_party_id:
                if str(lane.get("customer_party_id") or "") == payload.customer_party_id:
                    customer_boost = 10
                else:
                    continue

            total = rate_type_score * 100 + customer_boost + o_score * 10 + d_score * 10 + (lane["route_priority"] or 0) + (lane["lane_priority"] or 0)
            if total > best_score:
                best_score = total
                best_lane  = dict(lane)

        if not best_lane:
            results.append({
                "carrier_id":    carrier_id,
                "carrier_name":  carrier["carrier_name"],
                "carrier_code":  carrier["carrier_code"],
                "status":        "no_rates",
                "message":       "No matching lane for origin/destination.",
                "estimated_total": None,
                "rate_lines":    [],
            })
            continue

        # Load rate lines
        rl_result = await db.execute(text("""
            SELECT * FROM tms.carrier_rate_lines
            WHERE lane_id = CAST(:lane_id AS uuid) AND is_active = TRUE
            ORDER BY sort_order
        """), {"lane_id": best_lane["lane_id"]})
        rate_lines = rl_result.mappings().all()

        line_estimates = []
        linehaul_total = Decimal("0")

        for rl in rate_lines:
            ct    = rl["charge_type"]
            rate  = Decimal(str(rl["rate_amount"]))
            min_c = Decimal(str(rl["min_charge"])) if rl["min_charge"] else None
            max_c = Decimal(str(rl["max_charge"])) if rl["max_charge"] else None

            if ct in ("minimum", "maximum"):
                continue

            qty, amount = _calculate_charge(
                ct=ct, rate=rate,
                weight_kg=weight_kg, weight_lb=weight_lb,
                pallets=pallets, cartons=cartons, units=units,
                stops=stops, distance_km=distance_km, distance_mi=distance_mi,
                shipment_value=declared_value,
                lane_name=best_lane["lane_name"],
                zone_value=rl.get("zone_value"),
                formula_text=rl.get("formula_text"),
                shipment_data={},
            )
            if min_c and amount < min_c: amount = min_c
            if max_c and amount > max_c: amount = max_c

            line_estimates.append({
                "charge_code":       rl["charge_code"],
                "charge_type":       ct,
                "description":       rl["description"] or ct.replace("_", " ").title(),
                "rate_amount":       float(rate),
                "uom":               rl["uom"],
                "quantity":          float(qty) if qty is not None else None,
                "estimated_amount":  float(amount),
                "currency":          rl["currency"] or best_lane["currency"],
            })
            linehaul_total += amount

        # Apply min/max
        for rl in rate_lines:
            ct   = rl["charge_type"]
            rate = Decimal(str(rl["rate_amount"]))
            if ct == "minimum" and linehaul_total < rate:
                linehaul_total = rate
            elif ct == "maximum" and linehaul_total > rate:
                linehaul_total = rate

        # Load FSC for this carrier
        fsc_params: dict[str, Any] = {"carrier_id": carrier_id, "mode": payload.mode}
        if eff_date:
            fsc_date_filter = "AND effective_date <= :eff_date AND (expiry_date IS NULL OR expiry_date >= :eff_date)"
            fsc_params["eff_date"] = eff_date
        else:
            fsc_date_filter = "AND effective_date <= CURRENT_DATE AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)"

        fsc_result = await db.execute(text(f"""
            SELECT * FROM tms.fuel_surcharge_schedules
            WHERE carrier_id = CAST(:carrier_id AS uuid)
              AND is_active = TRUE
              {fsc_date_filter}
              AND (mode IS NULL OR mode = :mode)
            ORDER BY mode NULLS LAST LIMIT 1
        """), fsc_params)
        fsc = fsc_result.mappings().one_or_none()

        fsc_amount = Decimal("0")
        if fsc:
            fsc_rate = Decimal(str(fsc["rate_value"]))
            if fsc["rate_type"] == "percentage":
                fsc_amount = (linehaul_total * fsc_rate / Decimal("100")).quantize(Decimal("0.01"))
            elif fsc["rate_type"] == "flat":
                fsc_amount = fsc_rate
            if fsc_amount > 0:
                line_estimates.append({
                    "charge_code":      "FSC",
                    "charge_type":      "fuel_surcharge",
                    "description":      f"Fuel Surcharge ({fsc['rate_value']}{'%' if fsc['rate_type']=='percentage' else ''})",
                    "rate_amount":      float(fsc_rate),
                    "uom":              None,
                    "quantity":         None,
                    "estimated_amount": float(fsc_amount),
                    "currency":         "USD",
                })

        grand_total = linehaul_total + fsc_amount

        results.append({
            "carrier_id":        carrier_id,
            "carrier_name":      carrier["carrier_name"],
            "carrier_code":      carrier["carrier_code"],
            "status":            "rated",
            "rate_card_id":      str(best_lane["rate_card_id"]),
            "rate_card_name":    best_lane["rate_card_name"],
            "rate_type":         best_lane["rate_type"],
            "lane_id":           str(best_lane["lane_id"]),
            "lane_name":         best_lane["lane_name"],
            "contract_reference":best_lane["contract_reference"],
            "currency":          best_lane["currency"],
            "linehaul_total":    float(linehaul_total),
            "fsc_amount":        float(fsc_amount),
            "estimated_total":   float(grand_total),
            "rate_lines":        line_estimates,
        })

    # ── 3. Filter to rated results and rank ───────────────────────
    rated = [r for r in results if r["status"] == "rated"]
    no_rates = [r for r in results if r["status"] == "no_rates"]

    if payload.selection_criteria == "lowest_cost":
        rated.sort(key=lambda x: x["estimated_total"])
    elif payload.selection_criteria == "route_guide":
        # route_guide prefers route_guide rate type, then lowest cost
        def rg_sort(r):
            type_priority = RATE_TYPE_PRIORITY.get(r["rate_type"], 0)
            return (-type_priority, r["estimated_total"])
        rated.sort(key=rg_sort)
    elif payload.selection_criteria == "best_rate_type":
        rated.sort(key=lambda x: (-RATE_TYPE_PRIORITY.get(x["rate_type"], 0), x["estimated_total"]))

    # Add rank
    for i, r in enumerate(rated):
        r["rank"] = i + 1

    best_rate = rated[0] if rated else None

    return {
        "mode":                  payload.mode,
        "selection_criteria":    payload.selection_criteria,
        "origin":                payload.origin_zip or payload.origin_state or payload.origin_country or "any",
        "destination":           payload.dest_zip or payload.dest_state or payload.dest_country or "any",
        "weight_kg":             weight_kg,
        "weight_lb":             round(weight_lb, 2),
        "distance_km":           distance_km,
        "distance_mi":           round(distance_mi, 2),
        "effective_date":        payload.effective_date or "today",
        "carriers_evaluated":    len(carriers),
        "carriers_with_rates":   len(rated),
        "carriers_without_rates":len(no_rates),
        "results":               rated + no_rates,
        "best_rate":             best_rate,
    }

# ================================================================== #
# TMS-RATE-006: Enhanced Fuel Surcharge Calculation
# Append this to the end of rating.py
# ================================================================== #

class FuelIndexCreate(BaseModel):
    index_code: str
    index_name: str
    description: Optional[str] = None
    unit: str = "USD_PER_GALLON"
    current_price: float

class FuelIndexPriceUpdate(BaseModel):
    current_price: float
    source: Optional[str] = None

class FuelSurchargeAdvancedCreate(BaseModel):
    carrier_id: str
    name: str
    mode: Optional[str] = None
    effective_date: str
    expiry_date: Optional[str] = None
    # Calculation method
    calc_method: str = "fixed"    # fixed | index_based | sliding_scale | distance_band
    # Fixed rate fields
    rate_type: str = "percentage"
    rate_value: float = 0
    basis: str = "linehaul"
    # Index-based fields
    fuel_index_id: Optional[str] = None
    base_fuel_price: Optional[float] = None
    price_increment: Optional[float] = None   # e.g. 0.05 = per $0.05 fuel change
    increment_rate: Optional[float] = None    # e.g. 0.5 = 0.5% FSC change per increment
    # Distance band fields
    distance_bands: Optional[list] = None     # [{min_km, max_km, rate}]
    # Carrier contract overrides
    contract_rules: Optional[dict] = None
    notes: Optional[str] = None
    is_active: bool = True


# ── Fuel Index CRUD ───────────────────────────────────────────────

@router.get("/fuel-indexes")
async def list_fuel_indexes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT fi.*,
               (SELECT price FROM tms.fuel_index_history
                WHERE fuel_index_id = fi.fuel_index_id
                ORDER BY effective_date DESC LIMIT 1) AS last_reported_price,
               (SELECT effective_date FROM tms.fuel_index_history
                WHERE fuel_index_id = fi.fuel_index_id
                ORDER BY effective_date DESC LIMIT 1) AS last_report_date
        FROM tms.fuel_indexes fi
        ORDER BY fi.index_code
    """))
    return [dict(r) for r in result.mappings().all()]


@router.post("/fuel-indexes", status_code=201)
async def create_fuel_index(
    payload: FuelIndexCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.fuel_indexes
            (index_code, index_name, description, unit, current_price, price_updated_at)
        VALUES
            (:index_code, :index_name, :description, :unit, :current_price, NOW())
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/fuel-indexes/{index_id}/price")
async def update_fuel_price(
    index_id: str,
    payload: FuelIndexPriceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update current fuel price and log to history."""
    # Update current price
    result = await db.execute(text("""
        UPDATE tms.fuel_indexes
        SET current_price = :price, price_updated_at = NOW(), updated_at = NOW()
        WHERE fuel_index_id = CAST(:id AS uuid)
        RETURNING *
    """), {"price": payload.current_price, "id": index_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Fuel index not found.")

    # Log to history
    await db.execute(text("""
        INSERT INTO tms.fuel_index_history
            (fuel_index_id, price, effective_date, source)
        VALUES
            (CAST(:id AS uuid), :price, CURRENT_DATE, :source)
    """), {"id": index_id, "price": payload.current_price, "source": payload.source or "manual"})

    await db.commit()
    return dict(row)


@router.get("/fuel-indexes/{index_id}/history")
async def get_fuel_index_history(
    index_id: str,
    limit: int = 52,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.fuel_index_history
        WHERE fuel_index_id = CAST(:id AS uuid)
        ORDER BY effective_date DESC
        LIMIT :limit
    """), {"id": index_id, "limit": limit})
    return [dict(r) for r in result.mappings().all()]


# ── Advanced FSC Calculation ──────────────────────────────────────

@router.post("/fuel-surcharges/advanced", status_code=201)
async def create_advanced_fuel_surcharge(
    payload: FuelSurchargeAdvancedCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a fuel surcharge with advanced calculation method."""
    import uuid as _uuid
    schedule_code = f"FSC-{payload.carrier_id[:8].upper()}-{payload.mode or 'ALL'}-{payload.effective_date[:7]}-{str(_uuid.uuid4())[:4]}"

    result = await db.execute(text("""
        INSERT INTO tms.fuel_surcharge_schedules
            (schedule_code, carrier_id, name, mode, effective_date, expiry_date,
             rate_type, rate_value, basis, calc_method, fuel_index_id,
             base_fuel_price, price_increment, increment_rate,
             distance_bands, contract_rules, notes, is_active)
        VALUES
            (:schedule_code, CAST(:carrier_id AS uuid), :name, :mode,
             CAST(:effective_date AS date), CAST(:expiry_date AS date),
             :rate_type, :rate_value, :basis, :calc_method,
             CAST(:fuel_index_id AS uuid), :base_fuel_price,
             :price_increment, :increment_rate,
             CAST(:distance_bands AS jsonb), CAST(:contract_rules AS jsonb),
             :notes, :is_active)
        RETURNING *
    """), {
        **payload.model_dump(),
        "schedule_code":  schedule_code,
        "distance_bands": json.dumps(payload.distance_bands) if payload.distance_bands else None,
        "contract_rules": json.dumps(payload.contract_rules) if payload.contract_rules else None,
    })
    await db.commit()
    return dict(result.mappings().one())


def _calculate_fsc_amount(
    fsc: dict,
    linehaul_total: Decimal,
    distance_km: float,
    distance_mi: float,
    current_fuel_price: Optional[float] = None,
) -> tuple[Decimal, dict]:
    """
    Calculate FSC amount based on calc_method.
    Returns (fsc_amount, metadata_dict)
    """
    rate     = Decimal(str(fsc.get("rate_value") or 0))
    method   = fsc.get("calc_method") or "fixed"
    metadata: dict = {"calc_method": method}

    if method == "fixed":
        if fsc.get("rate_type") == "percentage":
            basis_amount = linehaul_total if fsc.get("basis") == "linehaul" else linehaul_total
            amount = (basis_amount * rate / Decimal("100")).quantize(Decimal("0.01"))
        elif fsc.get("rate_type") == "per_mile":
            amount = (Decimal(str(distance_mi)) * rate).quantize(Decimal("0.01"))
        elif fsc.get("rate_type") == "per_km":
            amount = (Decimal(str(distance_km)) * rate).quantize(Decimal("0.01"))
        else:
            amount = rate
        metadata["rate_applied"] = float(rate)

    elif method == "index_based":
        # FSC = (current_price - base_price) / increment * increment_rate
        fuel_price = Decimal(str(current_fuel_price or fsc.get("current_price") or rate))
        base_price = Decimal(str(fsc.get("base_fuel_price") or fuel_price))
        increment  = Decimal(str(fsc.get("price_increment") or "0.05"))
        inc_rate   = Decimal(str(fsc.get("increment_rate")  or "0.5"))

        if increment > 0:
            price_diff  = fuel_price - base_price
            increments  = (price_diff / increment).quantize(Decimal("1"))
            fsc_pct     = (inc_rate * increments).quantize(Decimal("0.01"))
            # Minimum 0% FSC
            fsc_pct     = max(fsc_pct, Decimal("0"))
        else:
            fsc_pct = rate

        basis_amount = linehaul_total
        amount = (basis_amount * fsc_pct / Decimal("100")).quantize(Decimal("0.01"))
        metadata.update({
            "current_fuel_price": float(fuel_price),
            "base_fuel_price":    float(base_price),
            "fsc_pct_applied":    float(fsc_pct),
        })

    elif method == "sliding_scale":
        # Same as index_based but capped
        fuel_price = Decimal(str(current_fuel_price or fsc.get("current_price") or rate))
        base_price = Decimal(str(fsc.get("base_fuel_price") or fuel_price))
        increment  = Decimal(str(fsc.get("price_increment") or "0.05"))
        inc_rate   = Decimal(str(fsc.get("increment_rate")  or "0.5"))

        price_diff = max(fuel_price - base_price, Decimal("0"))
        fsc_pct    = (price_diff / increment * inc_rate).quantize(Decimal("0.01")) if increment > 0 else rate
        amount     = (linehaul_total * fsc_pct / Decimal("100")).quantize(Decimal("0.01"))
        metadata.update({
            "current_fuel_price": float(fuel_price),
            "base_fuel_price":    float(base_price),
            "fsc_pct_applied":    float(fsc_pct),
        })

    elif method == "distance_band":
        bands = fsc.get("distance_bands") or []
        matched_rate = rate  # fallback
        for band in bands:
            min_km = band.get("min_km", 0)
            max_km = band.get("max_km")  # None = no upper limit
            if distance_km >= min_km and (max_km is None or distance_km < max_km):
                matched_rate = Decimal(str(band.get("rate", 0)))
                metadata["band_matched"] = band
                break
        amount = (linehaul_total * matched_rate / Decimal("100")).quantize(Decimal("0.01"))
        metadata["rate_applied"] = float(matched_rate)

    else:
        amount = Decimal("0")

    return amount, metadata


@router.post("/calculate-fsc")
async def calculate_fsc_preview(
    db: AsyncSession = Depends(get_db),
    carrier_id: str = "",
    mode: str = "FTL",
    linehaul_amount: float = 0,
    distance_km: float = 0,
    distance_miles: float = 0,
    effective_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Preview FSC calculation for a carrier/mode without persisting.
    Shows which schedule would apply and the calculated amount.
    """
    from datetime import date as _date

    eff_date = _date.fromisoformat(effective_date) if effective_date else None
    date_filter = "AND fsc.effective_date <= :eff_date AND (fsc.expiry_date IS NULL OR fsc.expiry_date >= :eff_date)" if eff_date else "AND fsc.effective_date <= CURRENT_DATE AND (fsc.expiry_date IS NULL OR fsc.expiry_date >= CURRENT_DATE)"
    date_params = {"eff_date": eff_date} if eff_date else {}

    result = await db.execute(text(f"""
        SELECT fsc.*,
               fi.index_code, fi.index_name, fi.current_price AS index_current_price
        FROM tms.fuel_surcharge_schedules fsc
        LEFT JOIN tms.fuel_indexes fi ON fi.fuel_index_id = fsc.fuel_index_id
        WHERE fsc.carrier_id = CAST(:carrier_id AS uuid)
          AND fsc.is_active = TRUE
          {date_filter}
          AND (fsc.mode IS NULL OR fsc.mode = :mode)
        ORDER BY fsc.mode NULLS LAST
        LIMIT 1
    """), {"carrier_id": carrier_id, "mode": mode, **date_params})

    fsc = result.mappings().one_or_none()
    if not fsc:
        return {"message": "No active fuel surcharge schedule found.", "fsc_amount": 0}

    fsc_dict = dict(fsc)
    linehaul = Decimal(str(linehaul_amount))
    dist_mi  = distance_miles or distance_km * 0.621371

    fsc_amount, meta = _calculate_fsc_amount(
        fsc=fsc_dict,
        linehaul_total=linehaul,
        distance_km=distance_km,
        distance_mi=dist_mi,
        current_fuel_price=float(fsc_dict.get("index_current_price") or 0) or None,
    )

    return {
        "carrier_id":       carrier_id,
        "mode":             mode,
        "schedule_code":    fsc_dict["schedule_code"],
        "schedule_name":    fsc_dict["name"],
        "calc_method":      fsc_dict.get("calc_method", "fixed"),
        "fuel_index":       fsc_dict.get("index_code"),
        "linehaul_amount":  linehaul_amount,
        "fsc_amount":       float(fsc_amount),
        "fsc_pct":          float(fsc_amount / linehaul * 100) if linehaul > 0 else 0,
        "calculation_detail": meta,
    }

# ================================================================== #
# TMS-RATE-006: Enhanced Fuel Surcharge Calculation
# Append this to the end of rating.py
# ================================================================== #

class FuelIndexCreate(BaseModel):
    index_code: str
    index_name: str
    description: Optional[str] = None
    unit: str = "USD_PER_GALLON"
    current_price: float

class FuelIndexPriceUpdate(BaseModel):
    current_price: float
    source: Optional[str] = None

class FuelSurchargeAdvancedCreate(BaseModel):
    carrier_id: str
    name: str
    mode: Optional[str] = None
    effective_date: str
    expiry_date: Optional[str] = None
    # Calculation method
    calc_method: str = "fixed"    # fixed | index_based | sliding_scale | distance_band
    # Fixed rate fields
    rate_type: str = "percentage"
    rate_value: float = 0
    basis: str = "linehaul"
    # Index-based fields
    tms_fuel_index_id: Optional[str] = None
    base_fuel_price: Optional[float] = None
    price_increment: Optional[float] = None   # e.g. 0.05 = per $0.05 fuel change
    increment_rate: Optional[float] = None    # e.g. 0.5 = 0.5% FSC change per increment
    # Distance band fields
    distance_bands: Optional[list] = None     # [{min_km, max_km, rate}]
    # Carrier contract overrides
    contract_rules: Optional[dict] = None
    notes: Optional[str] = None
    is_active: bool = True


# ── Fuel Index CRUD ───────────────────────────────────────────────

@router.get("/fuel-indexes")
async def list_fuel_indexes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT fi.*,
               (SELECT price FROM tms.fuel_index_history
                WHERE tms_fuel_index_id = fi.tms_fuel_index_id
                ORDER BY effective_date DESC LIMIT 1) AS last_reported_price,
               (SELECT effective_date FROM tms.fuel_index_history
                WHERE tms_fuel_index_id = fi.tms_fuel_index_id
                ORDER BY effective_date DESC LIMIT 1) AS last_report_date
        FROM tms.fuel_indexes fi
        ORDER BY fi.index_code
    """))
    return [dict(r) for r in result.mappings().all()]


@router.post("/fuel-indexes", status_code=201)
async def create_fuel_index(
    payload: FuelIndexCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.fuel_indexes
            (index_code, index_name, description, unit, current_price, price_updated_at)
        VALUES
            (:index_code, :index_name, :description, :unit, :current_price, NOW())
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/fuel-indexes/{index_id}/price")
async def update_fuel_price(
    index_id: str,
    payload: FuelIndexPriceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update current fuel price and log to history."""
    # Update current price
    result = await db.execute(text("""
        UPDATE tms.fuel_indexes
        SET current_price = :price, price_updated_at = NOW(), updated_at = NOW()
        WHERE tms_fuel_index_id = CAST(:id AS uuid)
        RETURNING *
    """), {"price": payload.current_price, "id": index_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Fuel index not found.")

    # Log to history
    await db.execute(text("""
        INSERT INTO tms.fuel_index_history
            (tms_fuel_index_id, price, effective_date, source)
        VALUES
            (CAST(:id AS uuid), :price, CURRENT_DATE, :source)
    """), {"id": index_id, "price": payload.current_price, "source": payload.source or "manual"})

    await db.commit()
    return dict(row)


@router.get("/fuel-indexes/{index_id}/history")
async def get_fuel_index_history(
    index_id: str,
    limit: int = 52,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.fuel_index_history
        WHERE tms_fuel_index_id = CAST(:id AS uuid)
        ORDER BY effective_date DESC
        LIMIT :limit
    """), {"id": index_id, "limit": limit})
    return [dict(r) for r in result.mappings().all()]


# ── Advanced FSC Calculation ──────────────────────────────────────

@router.post("/fuel-surcharges/advanced", status_code=201)
async def create_advanced_fuel_surcharge(
    payload: FuelSurchargeAdvancedCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a fuel surcharge with advanced calculation method."""
    import uuid as _uuid
    schedule_code = f"FSC-{payload.carrier_id[:8].upper()}-{payload.mode or 'ALL'}-{payload.effective_date[:7]}-{str(_uuid.uuid4())[:4]}"

    result = await db.execute(text("""
        INSERT INTO tms.fuel_surcharge_schedules
            (schedule_code, carrier_id, name, mode, effective_date, expiry_date,
             rate_type, rate_value, basis, calc_method, tms_fuel_index_id,
             base_fuel_price, price_increment, increment_rate,
             distance_bands, contract_rules, notes, is_active)
        VALUES
            (:schedule_code, CAST(:carrier_id AS uuid), :name, :mode,
             CAST(:effective_date AS date), CAST(:expiry_date AS date),
             :rate_type, :rate_value, :basis, :calc_method,
             CAST(:tms_fuel_index_id AS uuid), :base_fuel_price,
             :price_increment, :increment_rate,
             CAST(:distance_bands AS jsonb), CAST(:contract_rules AS jsonb),
             :notes, :is_active)
        RETURNING *
    """), {
        **payload.model_dump(),
        "schedule_code":  schedule_code,
        "distance_bands": json.dumps(payload.distance_bands) if payload.distance_bands else None,
        "contract_rules": json.dumps(payload.contract_rules) if payload.contract_rules else None,
    })
    await db.commit()
    return dict(result.mappings().one())


def _calculate_fsc_amount(
    fsc: dict,
    linehaul_total: Decimal,
    distance_km: float,
    distance_mi: float,
    current_fuel_price: Optional[float] = None,
) -> tuple[Decimal, dict]:
    """
    Calculate FSC amount based on calc_method.
    Returns (fsc_amount, metadata_dict)
    """
    rate     = Decimal(str(fsc.get("rate_value") or 0))
    method   = fsc.get("calc_method") or "fixed"
    metadata: dict = {"calc_method": method}

    if method == "fixed":
        if fsc.get("rate_type") == "percentage":
            basis_amount = linehaul_total if fsc.get("basis") == "linehaul" else linehaul_total
            amount = (basis_amount * rate / Decimal("100")).quantize(Decimal("0.01"))
        elif fsc.get("rate_type") == "per_mile":
            amount = (Decimal(str(distance_mi)) * rate).quantize(Decimal("0.01"))
        elif fsc.get("rate_type") == "per_km":
            amount = (Decimal(str(distance_km)) * rate).quantize(Decimal("0.01"))
        else:
            amount = rate
        metadata["rate_applied"] = float(rate)

    elif method == "index_based":
        # FSC = (current_price - base_price) / increment * increment_rate
        fuel_price = Decimal(str(current_fuel_price or fsc.get("current_price") or rate))
        base_price = Decimal(str(fsc.get("base_fuel_price") or fuel_price))
        increment  = Decimal(str(fsc.get("price_increment") or "0.05"))
        inc_rate   = Decimal(str(fsc.get("increment_rate")  or "0.5"))

        if increment > 0:
            price_diff  = fuel_price - base_price
            increments  = (price_diff / increment).quantize(Decimal("1"))
            fsc_pct     = (inc_rate * increments).quantize(Decimal("0.01"))
            # Minimum 0% FSC
            fsc_pct     = max(fsc_pct, Decimal("0"))
        else:
            fsc_pct = rate

        basis_amount = linehaul_total
        amount = (basis_amount * fsc_pct / Decimal("100")).quantize(Decimal("0.01"))
        metadata.update({
            "current_fuel_price": float(fuel_price),
            "base_fuel_price":    float(base_price),
            "fsc_pct_applied":    float(fsc_pct),
        })

    elif method == "sliding_scale":
        # Same as index_based but capped
        fuel_price = Decimal(str(current_fuel_price or fsc.get("current_price") or rate))
        base_price = Decimal(str(fsc.get("base_fuel_price") or fuel_price))
        increment  = Decimal(str(fsc.get("price_increment") or "0.05"))
        inc_rate   = Decimal(str(fsc.get("increment_rate")  or "0.5"))

        price_diff = max(fuel_price - base_price, Decimal("0"))
        fsc_pct    = (price_diff / increment * inc_rate).quantize(Decimal("0.01")) if increment > 0 else rate
        amount     = (linehaul_total * fsc_pct / Decimal("100")).quantize(Decimal("0.01"))
        metadata.update({
            "current_fuel_price": float(fuel_price),
            "base_fuel_price":    float(base_price),
            "fsc_pct_applied":    float(fsc_pct),
        })

    elif method == "distance_band":
        bands = fsc.get("distance_bands") or []
        matched_rate = rate  # fallback
        for band in bands:
            min_km = band.get("min_km", 0)
            max_km = band.get("max_km")  # None = no upper limit
            if distance_km >= min_km and (max_km is None or distance_km < max_km):
                matched_rate = Decimal(str(band.get("rate", 0)))
                metadata["band_matched"] = band
                break
        amount = (linehaul_total * matched_rate / Decimal("100")).quantize(Decimal("0.01"))
        metadata["rate_applied"] = float(matched_rate)

    else:
        amount = Decimal("0")

    return amount, metadata


@router.post("/calculate-fsc")
async def calculate_fsc_preview(
    db: AsyncSession = Depends(get_db),
    carrier_id: str = "",
    mode: str = "FTL",
    linehaul_amount: float = 0,
    distance_km: float = 0,
    distance_miles: float = 0,
    effective_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Preview FSC calculation for a carrier/mode without persisting.
    Shows which schedule would apply and the calculated amount.
    """
    from datetime import date as _date

    eff_date = _date.fromisoformat(effective_date) if effective_date else None
    date_filter = "AND fsc.effective_date <= :eff_date AND (fsc.expiry_date IS NULL OR fsc.expiry_date >= :eff_date)" if eff_date else "AND fsc.effective_date <= CURRENT_DATE AND (fsc.expiry_date IS NULL OR fsc.expiry_date >= CURRENT_DATE)"
    date_params = {"eff_date": eff_date} if eff_date else {}

    result = await db.execute(text(f"""
        SELECT fsc.*,
               fi.index_code, fi.index_name, fi.current_price AS index_current_price
        FROM tms.fuel_surcharge_schedules fsc
        LEFT JOIN tms.fuel_indexes fi ON fi.tms_fuel_index_id = fsc.tms_fuel_index_id
        WHERE fsc.carrier_id = CAST(:carrier_id AS uuid)
          AND fsc.is_active = TRUE
          {date_filter}
          AND (fsc.mode IS NULL OR fsc.mode = :mode)
        ORDER BY fsc.mode NULLS LAST
        LIMIT 1
    """), {"carrier_id": carrier_id, "mode": mode, **date_params})

    fsc = result.mappings().one_or_none()
    if not fsc:
        return {"message": "No active fuel surcharge schedule found.", "fsc_amount": 0}

    fsc_dict = dict(fsc)
    linehaul = Decimal(str(linehaul_amount))
    dist_mi  = distance_miles or distance_km * 0.621371

    fsc_amount, meta = _calculate_fsc_amount(
        fsc=fsc_dict,
        linehaul_total=linehaul,
        distance_km=distance_km,
        distance_mi=dist_mi,
        current_fuel_price=float(fsc_dict.get("index_current_price") or 0) or None,
    )

    return {
        "carrier_id":       carrier_id,
        "mode":             mode,
        "schedule_code":    fsc_dict["schedule_code"],
        "schedule_name":    fsc_dict["name"],
        "calc_method":      fsc_dict.get("calc_method", "fixed"),
        "fuel_index":       fsc_dict.get("index_code"),
        "linehaul_amount":  linehaul_amount,
        "fsc_amount":       float(fsc_amount),
        "fsc_pct":          float(fsc_amount / linehaul * 100) if linehaul > 0 else 0,
        "calculation_detail": meta,
    }

# ================================================================== #
# TMS-RATE-007: Accessorial Charge Calculation
# Append this to the end of rating.py
# ================================================================== #

import json as _json

class AccessorialLineInput(BaseModel):
    charge_code: str
    quantity: Optional[float] = None   # hours, days, stops, etc.
    override_amount: Optional[float] = None  # manual override
    notes: Optional[str] = None

class AccessorialCalculateRequest(BaseModel):
    carrier_id: str
    mode: str
    shipment_id: Optional[str] = None
    declared_value: Optional[float] = None
    distance_km: Optional[float] = None
    distance_miles: Optional[float] = None
    accessorials: list[AccessorialLineInput]
    persist: bool = False   # if True, save to shipment_costs


@router.get("/accessorials/catalog")
async def get_accessorial_catalog(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Return all active accessorial charges with calculation details."""
    conditions = ["is_active = TRUE"]
    params: dict[str, Any] = {}

    if carrier_id:
        conditions.append("carrier_id = CAST(:carrier_id AS uuid)")
        params["carrier_id"] = carrier_id
    if mode:
        conditions.append(":mode = ANY(applies_to_modes)")
        params["mode"] = mode

    where = " AND ".join(conditions)
    result = await db.execute(text(f"""
        SELECT
            accessorial_id, charge_code, description, charge_type,
            calculation_basis, rate_amount, currency, applies_to_modes,
            input_label, free_units, min_units, max_units,
            calculation_notes, is_active
        FROM tms.accessorial_charges
        WHERE {where}
        ORDER BY charge_code
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/calculate-accessorials")
async def calculate_accessorials(
    payload: AccessorialCalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-007: Calculate accessorial charges for a shipment.
    Accepts a list of accessorial codes with quantities and returns
    calculated amounts. Optionally persists to shipment_costs.
    """
    if not payload.accessorials:
        return {"carrier_id": payload.carrier_id, "mode": payload.mode,
                "lines": [], "total": 0.0, "currency": "USD"}

    codes = [a.charge_code for a in payload.accessorials]

    # Load applicable accessorial definitions
    result = await db.execute(text("""
        SELECT *
        FROM tms.accessorial_charges
        WHERE carrier_id = CAST(:carrier_id AS uuid)
          AND charge_code = ANY(:codes)
          AND is_active = TRUE
    """), {"carrier_id": payload.carrier_id, "codes": codes})
    catalog = {r["charge_code"]: dict(r) for r in result.mappings().all()}

    distance_km = payload.distance_km or 0.0
    distance_mi = payload.distance_miles or distance_km * 0.621371
    declared_value = payload.declared_value or 0.0

    lines = []
    grand_total = Decimal("0")

    for item in payload.accessorials:
        code = item.charge_code
        acc  = catalog.get(code)

        if not acc:
            lines.append({
                "charge_code": code,
                "status": "not_found",
                "message": f"No active accessorial '{code}' found for this carrier/mode.",
                "amount": 0.0,
            })
            continue

        # Handle override
        if item.override_amount is not None:
            amount = Decimal(str(item.override_amount))
            lines.append({
                "charge_code":   code,
                "description":   acc["description"],
                "calc_basis":    acc["calculation_basis"],
                "rate":          float(Decimal(str(acc["rate_amount"]))),
                "quantity":      item.quantity,
                "free_units":    float(acc["free_units"] or 0),
                "billable_units":item.quantity,
                "amount":        float(amount),
                "currency":      acc["currency"],
                "is_override":   True,
                "notes":         item.notes,
            })
            grand_total += amount
            continue

        rate     = Decimal(str(acc["rate_amount"]))
        basis    = acc["calculation_basis"]
        free     = Decimal(str(acc["free_units"] or 0))
        qty      = Decimal(str(item.quantity or 1))
        amount   = Decimal("0")
        billable = qty

        if basis == "flat":
            amount   = rate
            billable = Decimal("1")

        elif basis in ("per_hour", "per_day", "per_unit"):
            billable = max(qty - free, Decimal("0"))
            if acc["min_units"]:
                billable = max(billable, Decimal(str(acc["min_units"])))
            if acc["max_units"]:
                billable = min(billable, Decimal(str(acc["max_units"])))
            amount = billable * rate

        elif basis == "per_mile":
            billable = Decimal(str(distance_mi))
            amount   = billable * rate

        elif basis == "per_km":
            billable = Decimal(str(distance_km))
            amount   = billable * rate

        elif basis == "percentage":
            # percentage of declared value
            if declared_value > 0:
                amount = (Decimal(str(declared_value)) * rate / Decimal("100")).quantize(Decimal("0.01"))
            billable = rate

        elif basis == "per_cwt":
            # assume qty is weight in lbs
            billable = (qty / Decimal("100")).quantize(Decimal("0.01"))
            amount   = billable * rate

        lines.append({
            "charge_code":   code,
            "description":   acc["description"],
            "calc_basis":    basis,
            "rate":          float(rate),
            "quantity":      float(qty),
            "free_units":    float(free),
            "billable_units":float(billable),
            "amount":        float(amount),
            "currency":      acc["currency"],
            "is_override":   False,
            "notes":         item.notes or acc.get("calculation_notes"),
        })
        grand_total += amount

    # Optionally persist to shipment_costs
    if payload.persist and payload.shipment_id:
        for line in lines:
            if line.get("status") == "not_found":
                continue
            await db.execute(text("""
                INSERT INTO tms.shipment_costs
                    (shipment_id, charge_code, charge_type, description,
                     quantity, rate_amount, amount, currency, rated_by)
                VALUES
                    (CAST(:shipment_id AS uuid), :charge_code, 'accessorial',
                     :description, :quantity, :rate_amount, :amount, :currency, 'system')
            """), {
                "shipment_id": payload.shipment_id,
                "charge_code": line["charge_code"],
                "description": line["description"],
                "quantity":    line["billable_units"],
                "rate_amount": line["rate"],
                "amount":      line["amount"],
                "currency":    line["currency"],
            })
        await db.commit()

    return {
        "carrier_id":   payload.carrier_id,
        "mode":         payload.mode,
        "shipment_id":  payload.shipment_id,
        "lines":        lines,
        "total":        float(grand_total),
        "currency":     "USD",
        "persisted":    payload.persist and payload.shipment_id is not None,
    }

# ================================================================== #
# TMS-RATE-008: Rate Card Version Control
# Append this to the end of rating.py
# ================================================================== #

class NewVersionRequest(BaseModel):
    effective_date: str
    expiry_date: Optional[str] = None
    change_reason: Optional[str] = None
    # Optional field overrides for new version
    name: Optional[str] = None
    currency: Optional[str] = None
    rate_type: Optional[str] = None
    notes: Optional[str] = None
    copy_lanes: bool = True   # copy all lanes + rate lines from parent


@router.post("/rate-cards/{card_id}/new-version", status_code=201)
async def create_new_version(
    card_id: str,
    payload: NewVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-008: Create a new version of a rate card.
    - Clones the existing card with a bumped version number
    - Sets expiry_date on the parent to the day before new effective_date
    - Marks parent as superseded
    - Optionally copies all lanes and rate lines
    """
    from datetime import date as _date, timedelta

    user_id = current_user.get("email", "system")

    # Load parent card
    parent_result = await db.execute(text("""
        SELECT * FROM tms.carrier_rate_cards
        WHERE rate_card_id = CAST(:id AS uuid)
    """), {"id": card_id})
    parent = parent_result.mappings().one_or_none()
    if not parent:
        raise HTTPException(404, "Rate card not found.")
    parent = dict(parent)

    # Find root card (for version family tracking)
    root_id = str(parent.get("parent_rate_card_id") or card_id)

    # Get next version number
    version_result = await db.execute(text("""
        SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
        FROM tms.carrier_rate_cards
        WHERE parent_rate_card_id = CAST(:root_id AS uuid)
           OR rate_card_id        = CAST(:root_id AS uuid)
    """), {"root_id": root_id})
    next_version = version_result.scalar() or 2

    # New card's effective date
    new_eff = _date.fromisoformat(payload.effective_date)
    # Parent expiry = day before new effective
    parent_expiry = new_eff - timedelta(days=1)

    # Create new version card
    new_card_result = await db.execute(text("""
        INSERT INTO tms.carrier_rate_cards
            (carrier_id, name, mode, currency, effective_date, expiry_date,
             status, notes, rate_type, customer_party_id, contract_reference,
             route_priority, version_number, parent_rate_card_id,
             change_reason, changed_by)
        VALUES
            (CAST(:carrier_id AS uuid),
             :name, :mode, :currency,
             CAST(:effective_date AS date), CAST(:expiry_date AS date),
             'active', :notes, :rate_type,
             CAST(:customer_party_id AS uuid), :contract_reference,
             :route_priority, :version_number, CAST(:parent_id AS uuid),
             :change_reason, :changed_by)
        RETURNING rate_card_id
    """), {
        "carrier_id":        parent["carrier_id"],
        "name":              payload.name or parent["name"],
        "mode":              parent["mode"],
        "currency":          payload.currency or parent["currency"],
        "effective_date":    new_eff,
        "expiry_date":       payload.expiry_date,
        "notes":             payload.notes or parent["notes"],
        "rate_type":         payload.rate_type or parent["rate_type"],
        "customer_party_id": parent.get("customer_party_id"),
        "contract_reference":parent.get("contract_reference"),
        "route_priority":    parent.get("route_priority", 0),
        "version_number":    next_version,
        "parent_id":         root_id,
        "change_reason":     payload.change_reason,
        "changed_by":        user_id,
    })
    new_card_id = str(new_card_result.scalar())

    # Supersede parent
    await db.execute(text("""
        UPDATE tms.carrier_rate_cards
        SET expiry_date     = CAST(:expiry AS date),
            status          = 'expired',
            superseded_by_id = CAST(:new_id AS uuid),
            superseded_at   = NOW(),
            updated_at      = NOW()
        WHERE rate_card_id = CAST(:old_id AS uuid)
    """), {"expiry": parent_expiry, "new_id": new_card_id, "old_id": card_id})

    # Log audit
    await db.execute(text("""
        INSERT INTO tms.rate_card_audit_log
            (rate_card_id, action, old_status, new_status,
             old_expiry_date, new_expiry_date, version_number,
             change_reason, changed_by)
        VALUES
            (CAST(:card_id AS uuid), 'versioned', 'active', 'expired',
             CAST(:old_expiry AS date), CAST(:new_expiry AS date),
             :version, :reason, :user)
    """), {
        "card_id":    card_id,
        "old_expiry": _date.fromisoformat(str(parent.get("expiry_date"))) if parent.get("expiry_date") else None,
        "new_expiry": parent_expiry,
        "version":    next_version,
        "reason":     payload.change_reason,
        "user":       user_id,
    })

    await db.execute(text("""
        INSERT INTO tms.rate_card_audit_log
            (rate_card_id, action, old_status, new_status,
             version_number, change_reason, changed_by)
        VALUES
            (CAST(:card_id AS uuid), 'created', NULL, 'active',
             :version, :reason, :user)
    """), {
        "card_id": new_card_id,
        "version": next_version,
        "reason":  payload.change_reason,
        "user":    user_id,
    })

    # Copy lanes + rate lines if requested
    if payload.copy_lanes:
        lanes_result = await db.execute(text("""
            SELECT * FROM tms.carrier_rate_lanes
            WHERE rate_card_id = CAST(:old_id AS uuid)
        """), {"old_id": card_id})
        lanes = lanes_result.mappings().all()

        for lane in lanes:
            new_lane_result = await db.execute(text("""
                INSERT INTO tms.carrier_rate_lanes
                    (rate_card_id, lane_name, origin_type, origin_value,
                     destination_type, destination_value, min_weight_kg,
                     max_weight_kg, min_distance_km, max_distance_km,
                     priority, is_active)
                VALUES
                    (CAST(:rate_card_id AS uuid), :lane_name, :origin_type,
                     :origin_value, :destination_type, :destination_value,
                     :min_weight_kg, :max_weight_kg, :min_distance_km,
                     :max_distance_km, :priority, :is_active)
                RETURNING lane_id
            """), {
                "rate_card_id":      new_card_id,
                "lane_name":         lane["lane_name"],
                "origin_type":       lane["origin_type"],
                "origin_value":      lane["origin_value"],
                "destination_type":  lane["destination_type"],
                "destination_value": lane["destination_value"],
                "min_weight_kg":     lane["min_weight_kg"],
                "max_weight_kg":     lane["max_weight_kg"],
                "min_distance_km":   lane["min_distance_km"],
                "max_distance_km":   lane["max_distance_km"],
                "priority":          lane["priority"],
                "is_active":         lane["is_active"],
            })
            new_lane_id = str(new_lane_result.scalar())

            # Copy rate lines for this lane
            rls_result = await db.execute(text("""
                SELECT * FROM tms.carrier_rate_lines
                WHERE lane_id = CAST(:lane_id AS uuid)
            """), {"lane_id": str(lane["lane_id"])})
            rate_lines = rls_result.mappings().all()

            for rl in rate_lines:
                await db.execute(text("""
                    INSERT INTO tms.carrier_rate_lines
                        (lane_id, charge_type, charge_code, description,
                         rate_amount, currency, uom, min_charge, max_charge,
                         formula_text, zone_value, is_active, sort_order)
                    VALUES
                        (CAST(:lane_id AS uuid), :charge_type, :charge_code,
                         :description, :rate_amount, :currency, :uom,
                         :min_charge, :max_charge, :formula_text, :zone_value,
                         :is_active, :sort_order)
                """), {
                    "lane_id":      new_lane_id,
                    "charge_type":  rl["charge_type"],
                    "charge_code":  rl["charge_code"],
                    "description":  rl["description"],
                    "rate_amount":  rl["rate_amount"],
                    "currency":     rl["currency"],
                    "uom":          rl["uom"],
                    "min_charge":   rl["min_charge"],
                    "max_charge":   rl["max_charge"],
                    "formula_text": rl.get("formula_text"),
                    "zone_value":   rl.get("zone_value"),
                    "is_active":    rl["is_active"],
                    "sort_order":   rl["sort_order"],
                })

    await db.commit()

    return {
        "message":          f"Version {next_version} created successfully.",
        "new_rate_card_id": new_card_id,
        "parent_rate_card_id": card_id,
        "version_number":   next_version,
        "effective_date":   payload.effective_date,
        "parent_expired_on":parent_expiry.isoformat(),
        "lanes_copied":     payload.copy_lanes,
    }


@router.get("/rate-cards/{card_id}/versions")
async def get_rate_card_versions(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the full version history for a rate card family."""
    # Find root
    root_result = await db.execute(text("""
        SELECT COALESCE(parent_rate_card_id, rate_card_id) AS root_id
        FROM tms.carrier_rate_cards
        WHERE rate_card_id = CAST(:id AS uuid)
    """), {"id": card_id})
    root_row = root_result.mappings().one_or_none()
    if not root_row:
        raise HTTPException(404, "Rate card not found.")
    root_id = str(root_row["root_id"])

    result = await db.execute(text("""
        SELECT
            rc.rate_card_id, rc.name, rc.mode, rc.rate_type,
            rc.effective_date, rc.expiry_date, rc.status,
            rc.version_number, rc.parent_rate_card_id,
            rc.superseded_by_id, rc.superseded_at,
            rc.change_reason, rc.changed_by,
            rc.created_at, rc.updated_at,
            p.party_name AS carrier_name,
            COUNT(l.lane_id) AS lane_count
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carriers c  ON c.carrier_id = rc.carrier_id
        LEFT JOIN tms.parties  p  ON p.party_id   = c.party_id
        LEFT JOIN tms.carrier_rate_lanes l ON l.rate_card_id = rc.rate_card_id
        WHERE rc.rate_card_id        = CAST(:root_id AS uuid)
           OR rc.parent_rate_card_id = CAST(:root_id AS uuid)
        GROUP BY rc.rate_card_id, p.party_name
        ORDER BY rc.version_number DESC
    """), {"root_id": root_id})

    versions = [dict(r) for r in result.mappings().all()]

    # Get audit log
    audit_result = await db.execute(text("""
        SELECT * FROM tms.rate_card_audit_log
        WHERE rate_card_id IN (
            SELECT rate_card_id FROM tms.carrier_rate_cards
            WHERE rate_card_id        = CAST(:root_id AS uuid)
               OR parent_rate_card_id = CAST(:root_id AS uuid)
        )
        ORDER BY changed_at DESC
    """), {"root_id": root_id})
    audit = [dict(r) for r in audit_result.mappings().all()]

    return {
        "root_rate_card_id": root_id,
        "total_versions":    len(versions),
        "versions":          versions,
        "audit_log":         audit,
    }


@router.get("/rate-cards/effective")
async def get_effective_rate_card(
    carrier_id: str = Query(...),
    mode: str = Query(...),
    effective_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-008: Return the rate card version active on a specific date.
    Defaults to today if no date provided.
    """
    from datetime import date as _date

    eff = _date.fromisoformat(effective_date) if effective_date else None
    params: dict[str, Any] = {"carrier_id": carrier_id, "mode": mode}

    if eff:
        date_filter = "AND rc.effective_date <= :eff_date AND (rc.expiry_date IS NULL OR rc.expiry_date >= :eff_date)"
        params["eff_date"] = eff
    else:
        date_filter = "AND rc.effective_date <= CURRENT_DATE AND (rc.expiry_date IS NULL OR rc.expiry_date >= CURRENT_DATE)"

    result = await db.execute(text(f"""
        SELECT
            rc.*,
            p.party_name AS carrier_name,
            COUNT(l.lane_id) AS lane_count
        FROM tms.carrier_rate_cards rc
        LEFT JOIN tms.carriers c ON c.carrier_id = rc.carrier_id
        LEFT JOIN tms.parties  p ON p.party_id   = c.party_id
        LEFT JOIN tms.carrier_rate_lanes l ON l.rate_card_id = rc.rate_card_id
        WHERE rc.carrier_id = CAST(:carrier_id AS uuid)
          AND rc.mode = :mode
          AND rc.status = 'active'
          {date_filter}
        GROUP BY rc.rate_card_id, p.party_name
        ORDER BY rc.version_number DESC
        LIMIT 1
    """), params)

    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, f"No active rate card found for carrier {carrier_id} mode {mode} on {effective_date or 'today'}.")
    return dict(row)


@router.get("/rate-cards/{card_id}/audit")
async def get_rate_card_audit(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return audit log for a specific rate card."""
    result = await db.execute(text("""
        SELECT * FROM tms.rate_card_audit_log
        WHERE rate_card_id = CAST(:id AS uuid)
        ORDER BY changed_at DESC
    """), {"id": card_id})
    return [dict(r) for r in result.mappings().all()]
