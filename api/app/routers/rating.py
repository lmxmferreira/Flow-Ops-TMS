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
            s.shipment_id, s.carrier_id,
            NULL::text              AS mode,
            NULL::text              AS status,
            s.total_weight          AS total_weight_kg,
            s.total_weight          AS total_weight_lb,
            s.pallet_count          AS total_pallets,
            s.carton_count          AS total_cartons,
            NULL::numeric           AS total_pieces,
            s.distance_value        AS distance_km,
            s.distance_value        AS distance_miles,
            0                       AS declared_value,
            NULL::text              AS origin_country,
            o.state_province        AS origin_state,
            o.postal_code           AS origin_zip,
            NULL::text              AS dest_country,
            d.state_province        AS dest_state,
            d.postal_code           AS dest_zip,
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

# ================================================================== #
# TMS-RATE-009: Detailed Rating Breakdown
# Append this to the end of rating.py
# ================================================================== #

class TaxInput(BaseModel):
    charge_code: str
    tax_rate: float    # percentage e.g. 8.5 = 8.5%

class ApplyTaxRequest(BaseModel):
    shipment_id: str
    taxes: list[TaxInput]


@router.get("/shipment-costs/{shipment_id}/breakdown")
async def get_rating_breakdown(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-009: Return detailed rating breakdown for a shipment.
    Includes charge code, source rate, calculation basis, quantity,
    rate, amount, currency, and tax amount for each cost line.
    """
    # Load shipment header
    shp_result = await db.execute(text("""
        SELECT
            s.shipment_id, s.shipment_number,
            s.total_weight, s.pallet_count, s.carton_count, s.unit_count,
            s.distance_value,
            p_carrier.party_name AS carrier_name,
            o.city AS origin_city, o.state_province AS origin_state,
            d.city AS dest_city, d.state_province AS dest_state
        FROM tms.shipments s
        LEFT JOIN tms.carriers  c          ON c.carrier_id    = s.carrier_id
        LEFT JOIN tms.parties   p_carrier  ON p_carrier.party_id = c.party_id
        LEFT JOIN tms.locations o          ON o.location_id   = s.origin_location_id
        LEFT JOIN tms.locations d          ON d.location_id   = s.destination_location_id
        WHERE s.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    shp = shp_result.mappings().one_or_none()
    if not shp:
        raise HTTPException(404, "Shipment not found.")
    shp = dict(shp)

    # Load cost lines with full detail
    costs_result = await db.execute(text("""
        SELECT
            sc.cost_id,
            sc.charge_code,
            sc.charge_type,
            sc.description,
            sc.calculation_basis,
            sc.quantity,
            sc.rate_amount,
            sc.amount,
            sc.tax_rate,
            sc.tax_amount,
            sc.currency,
            sc.is_override,
            sc.override_reason,
            sc.rated_at,
            sc.rated_by,
            sc.updated_at,
            sc.fsc_fuel_price,
            sc.fsc_base_price,
            sc.fsc_index_code,
            rc.name          AS rate_card_name,
            rc.rate_type     AS rate_card_type,
            rc.version_number AS rate_card_version,
            rc.effective_date AS rate_card_effective,
            rc.contract_reference,
            l.lane_name,
            l.origin_type,
            l.origin_value,
            l.destination_type,
            l.destination_value
        FROM tms.shipment_costs sc
        LEFT JOIN tms.carrier_rate_cards rc ON rc.rate_card_id = sc.rate_card_id
        LEFT JOIN tms.carrier_rate_lanes l  ON l.lane_id       = sc.lane_id
        WHERE sc.shipment_id = CAST(:id AS uuid)
        ORDER BY
            CASE sc.charge_type
                WHEN 'base_flat'    THEN 1
                WHEN 'per_mile'     THEN 2
                WHEN 'per_km'       THEN 2
                WHEN 'per_lb'       THEN 3
                WHEN 'per_kg'       THEN 3
                WHEN 'per_cwt'      THEN 3
                WHEN 'per_pallet'   THEN 4
                WHEN 'per_carton'   THEN 4
                WHEN 'per_unit'     THEN 4
                WHEN 'per_stop'     THEN 5
                WHEN 'minimum'      THEN 8
                WHEN 'maximum'      THEN 9
                WHEN 'fuel_surcharge' THEN 10
                WHEN 'accessorial'  THEN 11
                ELSE 6
            END,
            sc.charge_code
    """), {"id": shipment_id})
    costs = [dict(r) for r in costs_result.mappings().all()]

    if not costs:
        return {
            "shipment_id":    shipment_id,
            "shipment_number":shp.get("shipment_number"),
            "breakdown":      [],
            "summary":        {"total_charges": 0, "total_tax": 0, "grand_total": 0, "currency": "USD"},
        }

    # Group by charge category
    linehaul   = [c for c in costs if c["charge_type"] not in ("fuel_surcharge","accessorial")]
    fsc        = [c for c in costs if c["charge_type"] == "fuel_surcharge"]
    accessorials = [c for c in costs if c["charge_type"] == "accessorial"]

    def fmt_line(c: dict) -> dict:
        return {
            "cost_id":          str(c["cost_id"]),
            "charge_code":      c["charge_code"],
            "charge_type":      c["charge_type"],
            "description":      c["description"],
            # Source rate info
            "source_rate_card": c.get("rate_card_name"),
            "rate_card_type":   c.get("rate_card_type"),
            "rate_card_version":c.get("rate_card_version"),
            "rate_effective":   str(c["rate_card_effective"]) if c.get("rate_card_effective") else None,
            "contract_ref":     c.get("contract_reference"),
            "lane":             c.get("lane_name"),
            # Calculation detail
            "calculation_basis":c.get("calculation_basis") or c.get("charge_type"),
            "quantity":         float(c["quantity"]) if c.get("quantity") is not None else None,
            "rate_amount":      float(c["rate_amount"]) if c.get("rate_amount") is not None else None,
            # Amounts
            "amount":           float(c["amount"]),
            "tax_rate":         float(c["tax_rate"] or 0),
            "tax_amount":       float(c["tax_amount"] or 0),
            "total_with_tax":   float(c["amount"]) + float(c["tax_amount"] or 0),
            "currency":         c["currency"] or "USD",
            # Override info
            "is_override":      c["is_override"],
            "override_reason":  c.get("override_reason"),
            # FSC detail
            "fsc_fuel_price":   float(c["fsc_fuel_price"]) if c.get("fsc_fuel_price") else None,
            "fsc_base_price":   float(c["fsc_base_price"]) if c.get("fsc_base_price") else None,
            "fsc_index_code":   c.get("fsc_index_code"),
            # Audit
            "rated_at":         str(c["rated_at"]) if c.get("rated_at") else None,
            "rated_by":         c.get("rated_by"),
        }

    linehaul_total   = sum(float(c["amount"]) for c in linehaul)
    fsc_total        = sum(float(c["amount"]) for c in fsc)
    accessorial_total= sum(float(c["amount"]) for c in accessorials)
    total_charges    = linehaul_total + fsc_total + accessorial_total
    total_tax        = sum(float(c.get("tax_amount") or 0) for c in costs)
    grand_total      = total_charges + total_tax

    return {
        "shipment_id":     shipment_id,
        "shipment_number": shp.get("shipment_number"),
        "mode":            None,
        "carrier":         shp.get("carrier_name"),
        "origin":          ", ".join(filter(None, [shp.get("origin_city"), shp.get("origin_state")])),
        "destination":     ", ".join(filter(None, [shp.get("dest_city"), shp.get("dest_state")])),
        "weight_kg":       float(shp["total_weight"]) if shp.get("total_weight") else None,
        "distance_km":     float(shp["distance_value"]) if shp.get("distance_value") else None,
        "breakdown": {
            "linehaul":    [fmt_line(c) for c in linehaul],
            "fuel_surcharge": [fmt_line(c) for c in fsc],
            "accessorials":[fmt_line(c) for c in accessorials],
        },
        "all_lines": [fmt_line(c) for c in costs],
        "summary": {
            "linehaul_total":    round(linehaul_total, 2),
            "fsc_total":         round(fsc_total, 2),
            "accessorial_total": round(accessorial_total, 2),
            "total_charges":     round(total_charges, 2),
            "total_tax":         round(total_tax, 2),
            "grand_total":       round(grand_total, 2),
            "currency":          costs[0]["currency"] if costs else "USD",
            "line_count":        len(costs),
            "has_overrides":     any(c["is_override"] for c in costs),
        },
    }


@router.post("/shipment-costs/{shipment_id}/apply-tax")
async def apply_tax_to_costs(
    shipment_id: str,
    payload: ApplyTaxRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Apply tax rates to specific charge codes on a shipment's costs.
    Updates tax_rate and tax_amount on matching cost lines.
    """
    updated = []
    for tax in payload.taxes:
        result = await db.execute(text("""
            UPDATE tms.shipment_costs
            SET tax_rate   = :tax_rate,
                tax_amount = ROUND(amount * :tax_rate / 100, 4),
                updated_at = NOW()
            WHERE shipment_id = CAST(:shipment_id AS uuid)
              AND charge_code = :charge_code
            RETURNING cost_id, charge_code, amount, tax_rate, tax_amount
        """), {
            "shipment_id": shipment_id,
            "charge_code": tax.charge_code,
            "tax_rate":    tax.tax_rate,
        })
        rows = [dict(r) for r in result.mappings().all()]
        updated.extend(rows)

    await db.commit()
    total_tax = sum(float(r["tax_amount"]) for r in updated)
    return {
        "shipment_id": shipment_id,
        "lines_updated": len(updated),
        "updated": updated,
        "total_tax_applied": round(total_tax, 2),
    }

# ================================================================== #
# TMS-RATE-010: Client Charges (Sell Side) vs Carrier Costs (Buy Side)
# Append this to the end of rating.py
# ================================================================== #

class ClientChargeLineInput(BaseModel):
    charge_code: str
    charge_type: str
    description: Optional[str] = None
    calculation_basis: Optional[str] = None
    quantity: Optional[float] = None
    rate_amount: float
    currency: str = "USD"
    markup_type: str = "none"   # none | fixed | percentage
    markup_value: float = 0.0
    carrier_cost_id: Optional[str] = None
    tax_rate: float = 0.0

class ClientChargesFromCarrierRequest(BaseModel):
    """Generate client charges from carrier costs with markup rules."""
    shipment_id: str
    markup_type: str = "percentage"   # none | fixed | percentage
    markup_value: float = 15.0        # default 15% margin
    # Per-charge-type overrides
    markup_overrides: Optional[dict] = None
    # e.g. {"fuel_surcharge": {"markup_type": "percentage", "markup_value": 0}}
    currency: str = "USD"
    tax_rate: float = 0.0
    replace_existing: bool = True

class ManualClientChargesRequest(BaseModel):
    shipment_id: str
    charges: list[ClientChargeLineInput]
    replace_existing: bool = False


@router.post("/client-charges/from-carrier", status_code=201)
async def create_client_charges_from_carrier(
    payload: ClientChargesFromCarrierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-010: Generate client charges by applying markup to carrier costs.
    Each carrier cost line becomes a client charge line with the markup applied.
    """
    user_id = current_user.get("email", "system")

    # Load carrier costs
    costs_result = await db.execute(text("""
        SELECT * FROM tms.shipment_costs
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY charge_type, charge_code
    """), {"id": payload.shipment_id})
    carrier_costs = costs_result.mappings().all()

    if not carrier_costs:
        raise HTTPException(422, "No carrier costs found for this shipment. Rate the shipment first.")

    # Clear existing client charges if requested
    if payload.replace_existing:
        await db.execute(text("""
            DELETE FROM tms.client_charges
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": payload.shipment_id})

    lines = []
    for cost in carrier_costs:
        cost = dict(cost)
        carrier_amount = Decimal(str(cost["amount"]))

        # Get markup for this charge type
        override = (payload.markup_overrides or {}).get(cost["charge_type"])
        if override:
            mtype  = override.get("markup_type",  payload.markup_type)
            mvalue = Decimal(str(override.get("markup_value", payload.markup_value)))
        else:
            mtype  = payload.markup_type
            mvalue = Decimal(str(payload.markup_value))

        # Calculate markup amount
        if mtype == "percentage":
            markup_amount = (carrier_amount * mvalue / Decimal("100")).quantize(Decimal("0.01"))
        elif mtype == "fixed":
            markup_amount = mvalue
        else:
            markup_amount = Decimal("0")

        client_amount = carrier_amount + markup_amount

        # Calculate tax
        tax_rate   = Decimal(str(payload.tax_rate))
        tax_amount = (client_amount * tax_rate / Decimal("100")).quantize(Decimal("0.01"))

        result = await db.execute(text("""
            INSERT INTO tms.client_charges
                (shipment_id, carrier_cost_id, charge_code, charge_type, description,
                 calculation_basis, quantity, rate_amount, amount, currency,
                 markup_type, markup_value, markup_amount,
                 tax_rate, tax_amount, created_by)
            VALUES
                (CAST(:shipment_id AS uuid), CAST(:carrier_cost_id AS uuid),
                 :charge_code, :charge_type, :description,
                 :calculation_basis, :quantity, :rate_amount, :amount, :currency,
                 :markup_type, :markup_value, :markup_amount,
                 :tax_rate, :tax_amount, :created_by)
            RETURNING client_charge_id
        """), {
            "shipment_id":      payload.shipment_id,
            "carrier_cost_id":  str(cost["cost_id"]),
            "charge_code":      cost["charge_code"],
            "charge_type":      cost["charge_type"],
            "description":      cost["description"],
            "calculation_basis":cost.get("calculation_basis") or cost["charge_type"],
            "quantity":         float(cost["quantity"]) if cost.get("quantity") else None,
            "rate_amount":      float(client_amount),
            "amount":           float(client_amount),
            "currency":         payload.currency,
            "markup_type":      mtype,
            "markup_value":     float(mvalue),
            "markup_amount":    float(markup_amount),
            "tax_rate":         float(tax_rate),
            "tax_amount":       float(tax_amount),
            "created_by":       user_id,
        })
        charge_id = result.scalar()

        lines.append({
            "client_charge_id":  str(charge_id),
            "charge_code":       cost["charge_code"],
            "charge_type":       cost["charge_type"],
            "description":       cost["description"],
            "carrier_amount":    float(carrier_amount),
            "markup_type":       mtype,
            "markup_value":      float(mvalue),
            "markup_amount":     float(markup_amount),
            "client_amount":     float(client_amount),
            "tax_rate":          float(tax_rate),
            "tax_amount":        float(tax_amount),
            "total_with_tax":    float(client_amount + tax_amount),
            "currency":          payload.currency,
        })

    await db.commit()

    carrier_total = sum(float(c["amount"]) for c in carrier_costs)
    client_total  = sum(l["client_amount"] for l in lines)
    margin        = client_total - carrier_total
    margin_pct    = (margin / carrier_total * 100) if carrier_total > 0 else 0

    return {
        "shipment_id":   payload.shipment_id,
        "lines":         lines,
        "summary": {
            "carrier_total":  round(carrier_total, 2),
            "client_total":   round(client_total, 2),
            "total_markup":   round(margin, 2),
            "margin_pct":     round(margin_pct, 2),
            "total_tax":      round(sum(l["tax_amount"] for l in lines), 2),
            "grand_total":    round(sum(l["total_with_tax"] for l in lines), 2),
            "currency":       payload.currency,
            "line_count":     len(lines),
        },
    }


@router.post("/client-charges/manual", status_code=201)
async def create_manual_client_charges(
    payload: ManualClientChargesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create client charges manually (not derived from carrier costs)."""
    user_id = current_user.get("email", "system")

    if payload.replace_existing:
        await db.execute(text("""
            DELETE FROM tms.client_charges WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": payload.shipment_id})

    lines = []
    for ch in payload.charges:
        amount     = Decimal(str(ch.rate_amount)) * Decimal(str(ch.quantity or 1))
        mvalue     = Decimal(str(ch.markup_value))
        if ch.markup_type == "percentage":
            markup = (amount * mvalue / Decimal("100")).quantize(Decimal("0.01"))
        elif ch.markup_type == "fixed":
            markup = mvalue
        else:
            markup = Decimal("0")
        client_amount = amount + markup
        tax_amount    = (client_amount * Decimal(str(ch.tax_rate)) / Decimal("100")).quantize(Decimal("0.01"))

        result = await db.execute(text("""
            INSERT INTO tms.client_charges
                (shipment_id, charge_code, charge_type, description,
                 calculation_basis, quantity, rate_amount, amount, currency,
                 markup_type, markup_value, markup_amount,
                 tax_rate, tax_amount, created_by)
            VALUES
                (CAST(:shipment_id AS uuid), :charge_code, :charge_type, :description,
                 :calculation_basis, :quantity, :rate_amount, :amount, :currency,
                 :markup_type, :markup_value, :markup_amount,
                 :tax_rate, :tax_amount, :created_by)
            RETURNING client_charge_id
        """), {
            "shipment_id":      payload.shipment_id,
            "charge_code":      ch.charge_code,
            "charge_type":      ch.charge_type,
            "description":      ch.description or ch.charge_type,
            "calculation_basis":ch.calculation_basis or ch.charge_type,
            "quantity":         ch.quantity,
            "rate_amount":      float(Decimal(str(ch.rate_amount))),
            "amount":           float(client_amount),
            "currency":         ch.currency,
            "markup_type":      ch.markup_type,
            "markup_value":     float(mvalue),
            "markup_amount":    float(markup),
            "tax_rate":         ch.tax_rate,
            "tax_amount":       float(tax_amount),
            "created_by":       user_id,
        })
        lines.append({"client_charge_id": str(result.scalar()), **ch.model_dump(), "amount": float(client_amount)})

    await db.commit()
    return {"shipment_id": payload.shipment_id, "lines": lines, "line_count": len(lines)}


@router.get("/client-charges/{shipment_id}")
async def get_client_charges(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all client charges for a shipment."""
    result = await db.execute(text("""
        SELECT cc.*, sc.amount AS carrier_amount, sc.charge_code AS carrier_charge_code
        FROM tms.client_charges cc
        LEFT JOIN tms.shipment_costs sc ON sc.cost_id = cc.carrier_cost_id
        WHERE cc.shipment_id = CAST(:id AS uuid)
        ORDER BY cc.charge_type, cc.charge_code
    """), {"id": shipment_id})
    rows = [dict(r) for r in result.mappings().all()]
    total = sum(float(r["amount"]) for r in rows)
    tax   = sum(float(r["tax_amount"]) for r in rows)
    return {
        "shipment_id": shipment_id,
        "charges":     rows,
        "summary": {
            "total_charges": round(total, 2),
            "total_tax":     round(tax, 2),
            "grand_total":   round(total + tax, 2),
            "currency":      rows[0]["currency"] if rows else "USD",
            "line_count":    len(rows),
            "billed_count":  sum(1 for r in rows if r["billed_flag"]),
        },
    }


@router.get("/client-charges/{shipment_id}/margin")
async def get_shipment_margin(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-010: Buy vs Sell margin analysis for a shipment.
    Shows carrier costs (buy side) vs client charges (sell side) with margin breakdown.
    """
    # Carrier costs (buy side)
    carrier_result = await db.execute(text("""
        SELECT charge_code, charge_type, description, amount, currency
        FROM tms.shipment_costs
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY charge_type, charge_code
    """), {"id": shipment_id})
    carrier_costs = [dict(r) for r in carrier_result.mappings().all()]

    # Client charges (sell side)
    client_result = await db.execute(text("""
        SELECT charge_code, charge_type, description, amount,
               markup_type, markup_value, markup_amount,
               tax_amount, currency, billed_flag
        FROM tms.client_charges
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY charge_type, charge_code
    """), {"id": shipment_id})
    client_charges = [dict(r) for r in client_result.mappings().all()]

    buy_total  = sum(float(c["amount"]) for c in carrier_costs)
    sell_total = sum(float(c["amount"]) for c in client_charges)
    margin     = sell_total - buy_total
    margin_pct = (margin / buy_total * 100) if buy_total > 0 else 0

    # Line-by-line comparison
    carrier_by_code = {}
    for c in carrier_costs:
        key = (c["charge_code"], c["charge_type"])
        carrier_by_code[key] = carrier_by_code.get(key, 0) + float(c["amount"])

    comparison = []
    for cc in client_charges:
        key = (cc["charge_code"], cc["charge_type"])
        buy = carrier_by_code.get(key, 0)
        sell = float(cc["amount"])
        comparison.append({
            "charge_code":    cc["charge_code"],
            "charge_type":    cc["charge_type"],
            "description":    cc["description"],
            "buy_amount":     buy,
            "sell_amount":    sell,
            "markup_type":    cc["markup_type"],
            "markup_value":   float(cc["markup_value"]),
            "markup_amount":  float(cc["markup_amount"]),
            "line_margin":    round(sell - buy, 2),
            "line_margin_pct":round((sell - buy) / buy * 100, 2) if buy > 0 else None,
            "currency":       cc["currency"],
            "billed":         cc["billed_flag"],
        })

    return {
        "shipment_id":    shipment_id,
        "buy_side": {
            "total":  round(buy_total, 2),
            "lines":  len(carrier_costs),
            "label":  "Carrier Cost",
        },
        "sell_side": {
            "total":  round(sell_total, 2),
            "lines":  len(client_charges),
            "label":  "Client Charge",
        },
        "margin": {
            "amount":     round(margin, 2),
            "percentage": round(margin_pct, 2),
            "currency":   "USD",
        },
        "comparison": comparison,
    }

# ================================================================== #
# TMS-RATE-011: Client-Specific Billing Rules Engine
# Append this to the end of rating.py
# ================================================================== #

import json as _json

class BillingRuleCreate(BaseModel):
    customer_party_id: str
    rule_name: str
    rule_type: str   # markup|margin|pass_through|management_fee|fixed_fee|minimum_billing|fsc_billing
    applies_to_modes: list[str] = ["FTL","LTL","Parcel"]
    applies_to_charges: list[str] = ["all"]
    rule_params: dict = {}
    priority: int = 0
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = None

class BillingRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    applies_to_modes: Optional[list[str]] = None
    applies_to_charges: Optional[list[str]] = None
    rule_params: Optional[dict] = None
    priority: Optional[int] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class ApplyBillingRulesRequest(BaseModel):
    shipment_id: str
    customer_party_id: str
    mode: str = "FTL"
    replace_existing: bool = True
    as_of_date: Optional[str] = None


# ── CRUD for billing rules ────────────────────────────────────────

@router.get("/billing-rules")
async def list_billing_rules(
    db: AsyncSession = Depends(get_db),
    customer_party_id: Optional[str] = Query(None),
    rule_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if customer_party_id:
        conditions.append("r.customer_party_id = CAST(:cid AS uuid)")
        params["cid"] = customer_party_id
    if rule_type:
        conditions.append("r.rule_type = :rule_type")
        params["rule_type"] = rule_type
    if active_only:
        conditions.append("r.is_active = TRUE")
        conditions.append("r.effective_date <= CURRENT_DATE")
        conditions.append("(r.expiry_date IS NULL OR r.expiry_date >= CURRENT_DATE)")

    where = " AND ".join(conditions)
    result = await db.execute(text(f"""
        SELECT r.*, p.party_name AS customer_name, p.party_code AS customer_code
        FROM tms.client_billing_rules r
        JOIN tms.parties p ON p.party_id = r.customer_party_id
        WHERE {where}
        ORDER BY r.priority, r.rule_type
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/billing-rules", status_code=201)
async def create_billing_rule(
    payload: BillingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from datetime import date as _date
    eff = _date.fromisoformat(payload.effective_date) if payload.effective_date else _date.today()
    exp = _date.fromisoformat(payload.expiry_date) if payload.expiry_date else None
    result = await db.execute(text("""
        INSERT INTO tms.client_billing_rules
            (customer_party_id, rule_name, rule_type, applies_to_modes,
             applies_to_charges, rule_params, priority, effective_date,
             expiry_date, notes, created_by)
        VALUES
            (CAST(:customer_party_id AS uuid), :rule_name, :rule_type,
             :applies_to_modes, :applies_to_charges,
             CAST(:rule_params AS jsonb), :priority,
             :effective_date, :expiry_date, :notes, :created_by)
        RETURNING *
    """), {
        "customer_party_id": payload.customer_party_id,
        "rule_name":         payload.rule_name,
        "rule_type":         payload.rule_type,
        "applies_to_modes":  payload.applies_to_modes,
        "applies_to_charges":payload.applies_to_charges,
        "rule_params":       _json.dumps(payload.rule_params),
        "priority":          payload.priority,
        "effective_date":    eff,
        "expiry_date":       exp,
        "notes":             payload.notes,
        "created_by":        current_user.get("email", "system"),
    })
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/billing-rules/{rule_id}")
async def update_billing_rule(
    rule_id: str,
    payload: BillingRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")
    set_parts = []
    params: dict[str, Any] = {"id": rule_id}
    for k, v in updates.items():
        if k == "rule_params":
            set_parts.append("rule_params = CAST(:rule_params AS jsonb)")
            params["rule_params"] = _json.dumps(v)
        elif k in ("effective_date","expiry_date") and v:
            from datetime import date as _date
            set_parts.append(f"{k} = :{k}")
            params[k] = _date.fromisoformat(v)
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v
    result = await db.execute(
        text(f"UPDATE tms.client_billing_rules SET {', '.join(set_parts)}, updated_at=NOW() WHERE rule_id=CAST(:id AS uuid) RETURNING *"),
        params
    )
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Billing rule not found.")
    return dict(row)


@router.delete("/billing-rules/{rule_id}", status_code=204)
async def delete_billing_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await db.execute(text("DELETE FROM tms.client_billing_rules WHERE rule_id=CAST(:id AS uuid)"), {"id": rule_id})
    await db.commit()


# ── Apply billing rules to a shipment ────────────────────────────

@router.post("/client-charges/apply-rules", status_code=201)
async def apply_billing_rules(
    payload: ApplyBillingRulesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-011: Apply stored billing rules for a customer to a shipment.
    Rules are evaluated in priority order and produce client charge lines.
    """
    from datetime import date as _date
    user_id  = current_user.get("email", "system")
    as_of    = _date.fromisoformat(payload.as_of_date) if payload.as_of_date else _date.today()

    # Load carrier costs
    costs_result = await db.execute(text("""
        SELECT * FROM tms.shipment_costs
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY charge_type, charge_code
    """), {"id": payload.shipment_id})
    carrier_costs = [dict(r) for r in costs_result.mappings().all()]

    if not carrier_costs:
        raise HTTPException(422, "No carrier costs found. Rate the shipment first.")

    # Load active billing rules for this customer + mode
    rules_result = await db.execute(text("""
        SELECT * FROM tms.client_billing_rules
        WHERE customer_party_id = CAST(:cid AS uuid)
          AND is_active = TRUE
          AND effective_date <= :as_of
          AND (expiry_date IS NULL OR expiry_date >= :as_of)
          AND (:mode = ANY(applies_to_modes))
        ORDER BY priority
    """), {"cid": payload.customer_party_id, "as_of": as_of, "mode": payload.mode})
    rules = [dict(r) for r in rules_result.mappings().all()]

    if not rules:
        raise HTTPException(422, f"No active billing rules found for this customer and mode {payload.mode}.")

    # Clear existing client charges
    if payload.replace_existing:
        await db.execute(text("DELETE FROM tms.client_charges WHERE shipment_id = CAST(:id AS uuid)"), {"id": payload.shipment_id})

    client_lines = []
    carrier_total = sum(Decimal(str(c["amount"])) for c in carrier_costs)

    # Track which costs have been billed
    billed_costs: set = set()

    for rule in rules:
        params_j = rule["rule_params"] if isinstance(rule["rule_params"], dict) else {}
        applies_charges = rule["applies_to_charges"]  # list of charge types or ['all']

        def charge_matches(cost: dict) -> bool:
            if "all" in applies_charges:
                return True
            return cost["charge_type"] in applies_charges or cost["charge_code"] in applies_charges

        applicable_costs = [c for c in carrier_costs if charge_matches(c)]

        if rule["rule_type"] == "markup":
            mtype  = params_j.get("markup_type", "percentage")
            mvalue = Decimal(str(params_j.get("markup_value", 0)))
            for cost in applicable_costs:
                carrier_amount = Decimal(str(cost["amount"]))
                if mtype == "percentage":
                    markup = (carrier_amount * mvalue / 100).quantize(Decimal("0.01"))
                elif mtype == "fixed":
                    markup = mvalue
                else:
                    markup = Decimal("0")
                client_amount = carrier_amount + markup
                client_lines.append(("markup", cost, client_amount, markup, mtype, float(mvalue)))
                billed_costs.add(str(cost["cost_id"]))

        elif rule["rule_type"] == "pass_through":
            for cost in applicable_costs:
                client_amount = Decimal(str(cost["amount"]))
                client_lines.append(("pass_through", cost, client_amount, Decimal("0"), "none", 0.0))
                billed_costs.add(str(cost["cost_id"]))

        elif rule["rule_type"] == "management_fee":
            fee_type  = params_j.get("fee_type", "percentage")
            fee_value = Decimal(str(params_j.get("fee_value", 0)))
            basis     = params_j.get("basis", "carrier_total")
            desc      = params_j.get("description", "Management Fee")
            basis_amt = carrier_total if basis == "carrier_total" else Decimal(str(sum(Decimal(str(c["amount"])) for c in applicable_costs)))
            if fee_type == "percentage":
                fee_amount = (basis_amt * fee_value / 100).quantize(Decimal("0.01"))
            else:
                fee_amount = fee_value
            # Add as a standalone line
            synthetic_cost = {"cost_id": None, "charge_code": "MGMT_FEE", "charge_type": "management_fee",
                               "description": desc, "amount": 0, "calculation_basis": fee_type}
            client_lines.append(("management_fee", synthetic_cost, fee_amount, fee_amount, fee_type, float(fee_value)))

        elif rule["rule_type"] == "fixed_fee":
            fee_amount = Decimal(str(params_j.get("amount", 0)))
            desc       = params_j.get("description", "Fixed Fee")
            synthetic_cost = {"cost_id": None, "charge_code": "FIXED_FEE", "charge_type": "fixed_fee",
                               "description": desc, "amount": 0, "calculation_basis": "flat"}
            client_lines.append(("fixed_fee", synthetic_cost, fee_amount, fee_amount, "fixed", float(fee_amount)))

        elif rule["rule_type"] == "fsc_billing":
            billing_method = params_j.get("billing_method", "pass_through")
            fsc_costs = [c for c in carrier_costs if c["charge_type"] == "fuel_surcharge"]
            markup_pct = Decimal(str(params_j.get("markup_pct", 0)))
            for cost in fsc_costs:
                carrier_amount = Decimal(str(cost["amount"]))
                markup = (carrier_amount * markup_pct / 100).quantize(Decimal("0.01")) if billing_method == "markup" else Decimal("0")
                client_amount = carrier_amount + markup
                client_lines.append(("fsc_billing", cost, client_amount, markup, "percentage", float(markup_pct)))
                billed_costs.add(str(cost["cost_id"]))

    # Apply minimum billing check
    total_client = sum(line[2] for line in client_lines)
    min_rule = next((r for r in rules if r["rule_type"] == "minimum_billing"), None)
    if min_rule:
        min_amount = Decimal(str(min_rule["rule_params"].get("minimum_amount", 0)))
        if total_client < min_amount:
            adj = min_amount - total_client
            synthetic_cost = {"cost_id": None, "charge_code": "MIN_CHARGE", "charge_type": "minimum_billing",
                               "description": "Minimum Billing Adjustment", "amount": 0, "calculation_basis": "flat"}
            client_lines.append(("minimum_billing", synthetic_cost, adj, adj, "fixed", float(min_amount)))
            total_client = min_amount

    # Persist client charges
    saved_lines = []
    for rule_type_applied, cost, client_amount, markup_amount, markup_type, markup_value in client_lines:
        result = await db.execute(text("""
            INSERT INTO tms.client_charges
                (shipment_id, carrier_cost_id, charge_code, charge_type, description,
                 calculation_basis, quantity, rate_amount, amount, currency,
                 markup_type, markup_value, markup_amount, created_by)
            VALUES
                (CAST(:shipment_id AS uuid), CAST(:carrier_cost_id AS uuid),
                 :charge_code, :charge_type, :description,
                 :calculation_basis, :quantity, :rate_amount, :amount, 'USD',
                 :markup_type, :markup_value, :markup_amount, :created_by)
            RETURNING client_charge_id
        """), {
            "shipment_id":     payload.shipment_id,
            "carrier_cost_id": str(cost["cost_id"]) if cost.get("cost_id") else None,
            "charge_code":     cost["charge_code"],
            "charge_type":     cost["charge_type"],
            "description":     cost.get("description") or cost["charge_type"],
            "calculation_basis":cost.get("calculation_basis") or cost["charge_type"],
            "quantity":        float(cost["amount"]) if cost.get("amount") else None,
            "rate_amount":     float(client_amount),
            "amount":          float(client_amount),
            "markup_type":     markup_type,
            "markup_value":    markup_value,
            "markup_amount":   float(markup_amount),
            "created_by":      user_id,
        })
        saved_lines.append({
            "client_charge_id":  str(result.scalar()),
            "rule_type":         rule_type_applied,
            "charge_code":       cost["charge_code"],
            "charge_type":       cost["charge_type"],
            "description":       cost.get("description"),
            "carrier_amount":    float(cost["amount"]) if cost.get("amount") else 0,
            "markup_type":       markup_type,
            "markup_value":      markup_value,
            "markup_amount":     float(markup_amount),
            "client_amount":     float(client_amount),
            "currency":          "USD",
        })

    await db.commit()

    sell_total   = sum(l["client_amount"] for l in saved_lines)
    buy_total    = float(carrier_total)
    margin       = sell_total - buy_total
    margin_pct   = (margin / buy_total * 100) if buy_total > 0 else 0
    rules_applied = list({l["rule_type"] for l in saved_lines})

    return {
        "shipment_id":      payload.shipment_id,
        "customer_party_id":payload.customer_party_id,
        "rules_applied":    rules_applied,
        "lines":            saved_lines,
        "summary": {
            "carrier_total": round(buy_total, 2),
            "client_total":  round(sell_total, 2),
            "margin":        round(margin, 2),
            "margin_pct":    round(margin_pct, 2),
            "line_count":    len(saved_lines),
            "currency":      "USD",
        },
    }

# ================================================================== #
# TMS-RATE-012: Billing Rate Allocation Across Multiple Levels
# Append this to the end of rating.py
# ================================================================== #

class AllocationLineInput(BaseModel):
    allocation_type: str   # shipment|stop|order_release|po_header|po_line|customer|project|cost_center
    entity_id: str         # UUID of the entity at that level
    allocation_pct: Optional[float] = None    # manual override
    allocation_amount: Optional[float] = None # manual override

class AllocateChargesRequest(BaseModel):
    shipment_id: str
    allocation_basis: str = "equal"   # equal|weight|value|volume|manual
    levels: list[str] = ["shipment"]  # which levels to allocate to
    # e.g. ["stop","po_header","po_line"]
    manual_allocations: Optional[list[AllocationLineInput]] = None
    use_client_charges: bool = True   # if False, use carrier costs


@router.post("/allocations", status_code=201)
async def allocate_charges(
    payload: AllocateChargesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-012: Allocate charges across multiple levels.
    Supports shipment, stop, order_release, PO header, PO line,
    customer, project, and cost center allocation.
    """
    user_id = current_user.get("email", "system")

    # Load charges to allocate
    if payload.use_client_charges:
        charges_result = await db.execute(text("""
            SELECT client_charge_id AS charge_id, charge_code, charge_type,
                   description, amount, currency
            FROM tms.client_charges
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": payload.shipment_id})
    else:
        charges_result = await db.execute(text("""
            SELECT cost_id AS charge_id, charge_code, charge_type,
                   description, amount, currency
            FROM tms.shipment_costs
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": payload.shipment_id})

    charges = [dict(r) for r in charges_result.mappings().all()]
    if not charges:
        raise HTTPException(422, "No charges found to allocate.")

    total_amount = sum(Decimal(str(c["amount"])) for c in charges)
    saved = []

    # ── Manual allocations ─────────────────────────────────────────
    if payload.allocation_basis == "manual" and payload.manual_allocations:
        for alloc in payload.manual_allocations:
            for charge in charges:
                amount = charge["amount"]
                if alloc.allocation_amount is not None:
                    alloc_amount = Decimal(str(alloc.allocation_amount))
                    alloc_pct    = (alloc_amount / Decimal(str(amount)) * 100).quantize(Decimal("0.01")) if amount else Decimal("0")
                elif alloc.allocation_pct is not None:
                    alloc_pct    = Decimal(str(alloc.allocation_pct))
                    alloc_amount = (Decimal(str(amount)) * alloc_pct / 100).quantize(Decimal("0.01"))
                else:
                    continue

                entity_col = _get_entity_col(alloc.allocation_type)
                result = await db.execute(text(f"""
                    INSERT INTO tms.charge_allocations
                        ({_charge_col(payload.use_client_charges)}, allocation_type, {entity_col + chr(44) + " shipment_id" if entity_col != "shipment_id" else "shipment_id"}, allocation_basis, allocation_pct, allocation_amount,
                         currency, created_by)
                    VALUES
                        (CAST(:charge_id AS uuid), :alloc_type, {("CAST(:entity_id AS uuid), " if entity_col != "shipment_id" else "") + "CAST(:shipment_id AS uuid)"}, :basis, :pct, :amount,
                         :currency, :created_by)
                    RETURNING allocation_id
                """), {
                    "charge_id":   str(charge["charge_id"]),
                    "alloc_type":  alloc.allocation_type,
                    "entity_id":   alloc.entity_id,
                    "shipment_id": payload.shipment_id,
                    "basis":       "manual",
                    "pct":         float(alloc_pct),
                    "amount":      float(alloc_amount),
                    "currency":    charge["currency"],
                    "created_by":  user_id,
                })
                saved.append({"allocation_id": str(result.scalar()), "charge_id": str(charge["charge_id"]),
                               "type": alloc.allocation_type, "entity_id": alloc.entity_id,
                               "amount": float(alloc_amount), "pct": float(alloc_pct)})
        await db.commit()
        return {"shipment_id": payload.shipment_id, "allocations": saved, "total": len(saved)}

    # ── Auto allocations by level ──────────────────────────────────
    for level in payload.levels:
        entities = await _get_entities_for_level(db, payload.shipment_id, level)
        if not entities:
            # No entities found for this level, skip
            continue

        n = len(entities)
        entity_col = _get_entity_col(level)

        for charge in charges:
            charge_amount = Decimal(str(charge["amount"]))

            for i, entity in enumerate(entities):
                # Calculate allocation split
                if payload.allocation_basis == "equal":
                    alloc_pct    = Decimal("100") / n
                    alloc_amount = (charge_amount / n).quantize(Decimal("0.01"))
                    # Last entity gets rounding remainder
                    if i == n - 1:
                        alloc_amount = charge_amount - sum(
                            (charge_amount / n).quantize(Decimal("0.01")) for _ in range(n-1)
                        )
                elif payload.allocation_basis == "weight":
                    total_w  = sum(Decimal(str(e.get("weight", 1) or 1)) for e in entities)
                    w        = Decimal(str(entity.get("weight", 1) or 1))
                    alloc_pct = (w / total_w * 100).quantize(Decimal("0.01"))
                    alloc_amount = (charge_amount * w / total_w).quantize(Decimal("0.01"))
                elif payload.allocation_basis == "value":
                    total_v  = sum(Decimal(str(e.get("value", 1) or 1)) for e in entities)
                    v        = Decimal(str(entity.get("value", 1) or 1))
                    alloc_pct = (v / total_v * 100).quantize(Decimal("0.01"))
                    alloc_amount = (charge_amount * v / total_v).quantize(Decimal("0.01"))
                else:
                    alloc_pct    = Decimal("100") / n
                    alloc_amount = (charge_amount / n).quantize(Decimal("0.01"))

                result = await db.execute(text(f"""
                    INSERT INTO tms.charge_allocations
                        ({_charge_col(payload.use_client_charges)}, allocation_type, {entity_col + chr(44) + " shipment_id" if entity_col != "shipment_id" else "shipment_id"}, allocation_basis, allocation_pct, allocation_amount,
                         currency, created_by)
                    VALUES
                        (CAST(:charge_id AS uuid), :alloc_type, {("CAST(:entity_id AS uuid), " if entity_col != "shipment_id" else "") + "CAST(:shipment_id AS uuid)"}, :basis, :pct, :amount,
                         :currency, :created_by)
                    RETURNING allocation_id
                """), {
                    "charge_id":   str(charge["charge_id"]),
                    "alloc_type":  level,
                    "entity_id":   entity["id"],
                    "shipment_id": payload.shipment_id,
                    "basis":       payload.allocation_basis,
                    "pct":         float(alloc_pct),
                    "amount":      float(alloc_amount),
                    "currency":    charge["currency"],
                    "created_by":  user_id,
                })
                saved.append({
                    "allocation_id": str(result.scalar()),
                    "charge_id":     str(charge["charge_id"]),
                    "charge_code":   charge["charge_code"],
                    "level":         level,
                    "entity_id":     entity["id"],
                    "allocation_pct":float(alloc_pct),
                    "allocation_amount": float(alloc_amount),
                    "currency":      charge["currency"],
                })

    await db.commit()

    level_summary = {}
    for a in saved:
        level_summary.setdefault(a["level"], {"count": 0, "total": 0})
        level_summary[a["level"]]["count"] += 1
        level_summary[a["level"]]["total"] += a["allocation_amount"]

    return {
        "shipment_id":      payload.shipment_id,
        "allocation_basis": payload.allocation_basis,
        "levels":           payload.levels,
        "total_charges":    float(total_amount),
        "allocations":      saved,
        "level_summary":    level_summary,
        "total_allocations":len(saved),
    }


def _charge_col(use_client: bool) -> str:
    return "client_charge_id" if use_client else "shipment_cost_id"

def _get_entity_col(level: str) -> str:
    mapping = {
        "shipment":      "shipment_id",
        "stop":          "stop_id",
        "order_release": "release_id",
        "po_header":     "purchase_order_id",
        "po_line":       "po_line_id",
        "customer":      "customer_party_id",
        "project":       "project_id",
        "cost_center":   "cost_center_id",
    }
    return mapping.get(level, "shipment_id")

async def _get_entities_for_level(db, shipment_id: str, level: str) -> list[dict]:
    """Get entities linked to a shipment at the requested allocation level."""
    if level == "stop":
        result = await db.execute(text("""
            SELECT shipment_stop_id AS id,
                   1 AS weight,
                   1 AS value
            FROM tms.shipment_stops
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        return [dict(r) for r in result.mappings().all()]

    elif level == "po_header":
        result = await db.execute(text("""
            SELECT DISTINCT pol.purchase_order_id AS id,
                   COALESCE(SUM(pol.ordered_quantity), 1) AS weight,
                   COALESCE(SUM(pol.line_value), 1) AS value
            FROM tms.order_release_lines orl
            JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
            JOIN tms.order_releases ore ON ore.release_id = orl.release_id
            WHERE ore.shipment_id = CAST(:id AS uuid)
            GROUP BY pol.purchase_order_id
        """), {"id": shipment_id})
        rows = [dict(r) for r in result.mappings().all()]
        return rows if rows else []

    elif level == "po_line":
        result = await db.execute(text("""
            SELECT pol.purchase_order_line_id AS id,
                   COALESCE(pol.ordered_quantity, 1) AS weight,
                   COALESCE(pol.line_value, 1) AS value
            FROM tms.order_release_lines orl
            JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
            JOIN tms.order_releases ore ON ore.release_id = orl.release_id
            WHERE ore.shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        rows = [dict(r) for r in result.mappings().all()]
        return rows if rows else []

    elif level == "customer":
        result = await db.execute(text("""
            SELECT customer_party_id AS id, 1 AS weight, 1 AS value
            FROM tms.shipments WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        row = result.mappings().one_or_none()
        return [dict(row)] if row and row["id"] else []

    elif level == "cost_center":
        result = await db.execute(text("""
            SELECT DISTINCT pol.purchase_order_id AS id, 1 AS weight, 1 AS value
            FROM tms.order_release_lines orl
            JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
            JOIN tms.order_releases ore ON ore.release_id = orl.release_id
            WHERE ore.shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        return [dict(r) for r in result.mappings().all()]

    # Default: shipment level
    return [{"id": shipment_id, "weight": 1, "value": 1}]


@router.get("/allocations/{shipment_id}")
async def get_allocations(
    shipment_id: str,
    level: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all charge allocations for a shipment, optionally filtered by level."""
    conditions = ["ca.shipment_id = CAST(:id AS uuid)"]
    params: dict[str, Any] = {"id": shipment_id}
    if level:
        conditions.append("ca.allocation_type = :level")
        params["level"] = level

    result = await db.execute(text(f"""
        SELECT
            ca.*,
            COALESCE(cc.charge_code, sc.charge_code)  AS charge_code,
            COALESCE(cc.charge_type, sc.charge_type)  AS charge_type,
            COALESCE(cc.description, sc.description)  AS description,
            COALESCE(cc.amount,      sc.amount)        AS source_amount
        FROM tms.charge_allocations ca
        LEFT JOIN tms.client_charges  cc ON cc.client_charge_id = ca.client_charge_id
        LEFT JOIN tms.shipment_costs  sc ON sc.cost_id          = ca.shipment_cost_id
        WHERE {' AND '.join(conditions)}
        ORDER BY ca.allocation_type, ca.charge_code
    """), params)
    rows = [dict(r) for r in result.mappings().all()]
    total = sum(float(r["allocation_amount"]) for r in rows)

    by_level: dict = {}
    for r in rows:
        lvl = r["allocation_type"]
        by_level.setdefault(lvl, {"lines": [], "total": 0})
        by_level[lvl]["lines"].append(r)
        by_level[lvl]["total"] += float(r["allocation_amount"])

    return {
        "shipment_id":    shipment_id,
        "total_allocated":round(total, 2),
        "by_level":       by_level,
        "all_allocations":rows,
    }


@router.get("/allocations/by-entity/{entity_type}/{entity_id}")
async def get_allocations_by_entity(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all charge allocations attributed to a specific entity.
    entity_type: po_header | po_line | cost_center | project | customer | stop
    """
    col = _get_entity_col(entity_type)
    result = await db.execute(text(f"""
        SELECT
            ca.*,
            COALESCE(cc.charge_code, sc.charge_code)  AS charge_code,
            COALESCE(cc.charge_type, sc.charge_type)  AS charge_type,
            COALESCE(cc.description, sc.description)  AS description,
            COALESCE(cc.amount,      sc.amount)        AS source_amount,
            s.shipment_number
        FROM tms.charge_allocations ca
        LEFT JOIN tms.client_charges cc ON cc.client_charge_id = ca.client_charge_id
        LEFT JOIN tms.shipment_costs sc ON sc.cost_id          = ca.shipment_cost_id
        LEFT JOIN tms.shipments      s  ON s.shipment_id       = ca.shipment_id
        WHERE ca.{col} = CAST(:entity_id AS uuid)
          AND ca.allocation_type = :entity_type
        ORDER BY ca.created_at DESC
    """), {"entity_id": entity_id, "entity_type": entity_type})
    rows = [dict(r) for r in result.mappings().all()]
    total = sum(float(r["allocation_amount"]) for r in rows)

    return {
        "entity_type":    entity_type,
        "entity_id":      entity_id,
        "total_allocated":round(total, 2),
        "allocations":    rows,
        "shipment_count": len({r["shipment_id"] for r in rows}),
    }

# ================================================================== #
# TMS-RATE-013: Shipment Financial Views
# Append this to the end of rating.py
# ================================================================== #

class ApproveFinancialRequest(BaseModel):
    approved_amount: float
    approval_notes: Optional[str] = None
    target: str = "both"   # carrier | client | both


@router.get("/financials/{shipment_id}")
async def get_shipment_financials(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-013: Full financial view for a shipment.
    Returns estimated cost, actual cost, billable amount,
    gross margin, variance, and approved financial amount.
    """
    # Main financial summary
    fin_result = await db.execute(text("""
        SELECT * FROM tms.v_shipment_financials
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    fin = fin_result.mappings().one_or_none()
    if not fin:
        raise HTTPException(404, "Shipment not found.")
    fin = dict(fin)

    # Carrier cost line detail
    carrier_result = await db.execute(text("""
        SELECT
            sc.cost_id, sc.charge_code, sc.charge_type, sc.description,
            sc.quantity, sc.rate_amount, sc.amount,
            sc.approved_amount, sc.approved_by, sc.approved_at,
            sc.is_override, sc.is_estimated, sc.override_reason,
            sc.currency, sc.rated_at, sc.rated_by
        FROM tms.shipment_costs sc
        WHERE sc.shipment_id = CAST(:id AS uuid)
        ORDER BY sc.charge_type, sc.charge_code
    """), {"id": shipment_id})
    carrier_lines = [dict(r) for r in carrier_result.mappings().all()]

    # Client charge line detail
    client_result = await db.execute(text("""
        SELECT
            cc.client_charge_id, cc.charge_code, cc.charge_type, cc.description,
            cc.amount, cc.markup_type, cc.markup_value, cc.markup_amount,
            cc.approved_amount, cc.approved_by, cc.approved_at,
            cc.tax_rate, cc.tax_amount, cc.currency, cc.billed_flag
        FROM tms.client_charges cc
        WHERE cc.shipment_id = CAST(:id AS uuid)
        ORDER BY cc.charge_type, cc.charge_code
    """), {"id": shipment_id})
    client_lines = [dict(r) for r in client_result.mappings().all()]

    # Build per-charge comparison
    carrier_by_code: dict = {}
    for c in carrier_lines:
        key = c["charge_code"]
        carrier_by_code.setdefault(key, 0)
        carrier_by_code[key] += float(c.get("approved_amount") or c["amount"])

    charge_comparison = []
    for cl in client_lines:
        key = cl["charge_code"]
        buy  = carrier_by_code.get(key, 0)
        sell = float(cl["amount"])
        charge_comparison.append({
            "charge_code":   key,
            "charge_type":   cl["charge_type"],
            "description":   cl["description"],
            "carrier_cost":  buy,
            "client_charge": sell,
            "markup":        round(sell - buy, 2),
            "markup_pct":    round((sell - buy) / buy * 100, 2) if buy > 0 else None,
            "approved":      float(cl["approved_amount"]) if cl.get("approved_amount") else None,
            "billed":        cl["billed_flag"],
        })

    return {
        "shipment_id":     shipment_id,
        "shipment_number": fin.get("shipment_number"),
        "currency":        fin.get("currency", "USD"),
        "financials": {
            "estimated_carrier_cost":    float(fin.get("estimated_carrier_cost") or 0),
            "actual_carrier_cost":       float(fin.get("actual_carrier_cost") or 0),
            "total_carrier_cost":        float(fin.get("total_carrier_cost") or 0),
            "client_billable_amount":    float(fin.get("client_billable_amount") or 0),
            "approved_financial_amount": float(fin.get("approved_financial_amount") or 0),
            "gross_margin":              float(fin.get("gross_margin") or 0),
            "gross_margin_pct":          float(fin.get("gross_margin_pct") or 0),
            "variance":                  float(fin.get("variance") or 0),
        },
        "flags": {
            "has_overrides":  fin.get("has_overrides", False),
            "has_approvals":  fin.get("has_approvals", False),
            "carrier_lines":  fin.get("carrier_cost_lines", 0),
            "client_lines":   fin.get("client_charge_lines", 0),
            "last_rated_at":  str(fin["last_rated_at"]) if fin.get("last_rated_at") else None,
            "last_billed_at": str(fin["last_billed_at"]) if fin.get("last_billed_at") else None,
        },
        "carrier_costs":       carrier_lines,
        "client_charges":      client_lines,
        "charge_comparison":   charge_comparison,
    }


@router.get("/financials")
async def get_financials_summary(
    db: AsyncSession = Depends(get_db),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    """
    TMS-RATE-013: Aggregated financial report across shipments.
    Shows estimated vs actual cost, billable, margin, and variance per shipment.
    """
    from datetime import date as _date
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if from_date:
        conditions.append("s.created_at >= CAST(:from_date AS date)")
        params["from_date"] = _date.fromisoformat(from_date)
    if to_date:
        conditions.append("s.created_at <= CAST(:to_date AS date)")
        params["to_date"] = _date.fromisoformat(to_date)

    where = " AND ".join(conditions)

    result = await db.execute(text(f"""
        SELECT vf.*
        FROM tms.v_shipment_financials vf
        JOIN tms.shipments s ON s.shipment_id = vf.shipment_id
        WHERE {where}
        ORDER BY vf.last_rated_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)
    rows = [dict(r) for r in result.mappings().all()]

    # Aggregate totals
    total_carrier  = sum(float(r.get("total_carrier_cost") or 0) for r in rows)
    total_billable = sum(float(r.get("client_billable_amount") or 0) for r in rows)
    total_margin   = sum(float(r.get("gross_margin") or 0) for r in rows)
    total_variance = sum(float(r.get("variance") or 0) for r in rows)

    return {
        "shipments":        rows,
        "count":            len(rows),
        "totals": {
            "total_carrier_cost":      round(total_carrier, 2),
            "total_billable_amount":   round(total_billable, 2),
            "total_gross_margin":      round(total_margin, 2),
            "total_variance":          round(total_variance, 2),
            "avg_margin_pct":          round(total_margin / total_billable * 100, 2) if total_billable > 0 else 0,
            "currency":                "USD",
        },
    }


@router.patch("/financials/{shipment_id}/approve")
async def approve_shipment_financials(
    shipment_id: str,
    payload: ApproveFinancialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Approve the financial amount for a shipment.
    Sets approved_amount on carrier costs and/or client charges.
    """
    user_id = current_user.get("email", "system")
    updated = {"carrier": 0, "client": 0}

    if payload.target in ("carrier", "both"):
        result = await db.execute(text("""
            UPDATE tms.shipment_costs
            SET approved_amount = :amount,
                approved_by     = :user,
                approved_at     = NOW(),
                updated_at      = NOW()
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"amount": payload.approved_amount, "user": user_id, "id": shipment_id})
        updated["carrier"] = result.rowcount

    if payload.target in ("client", "both"):
        result = await db.execute(text("""
            UPDATE tms.client_charges
            SET approved_amount = :amount,
                approved_by     = :user,
                approved_at     = NOW(),
                updated_at      = NOW()
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"amount": payload.approved_amount, "user": user_id, "id": shipment_id})
        updated["client"] = result.rowcount

    await db.commit()

    # Return updated financials
    fin_result = await db.execute(text("""
        SELECT * FROM tms.v_shipment_financials WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    fin = dict(fin_result.mappings().one())

    return {
        "shipment_id":       shipment_id,
        "approved_by":       user_id,
        "approved_amount":   payload.approved_amount,
        "lines_updated":     updated,
        "financials": {
            "estimated_carrier_cost":    float(fin.get("estimated_carrier_cost") or 0),
            "actual_carrier_cost":       float(fin.get("actual_carrier_cost") or 0),
            "client_billable_amount":    float(fin.get("client_billable_amount") or 0),
            "approved_financial_amount": float(fin.get("approved_financial_amount") or 0),
            "gross_margin":              float(fin.get("gross_margin") or 0),
            "gross_margin_pct":          float(fin.get("gross_margin_pct") or 0),
            "variance":                  float(fin.get("variance") or 0),
        },
    }
