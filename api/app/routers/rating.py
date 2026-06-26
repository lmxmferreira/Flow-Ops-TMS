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
