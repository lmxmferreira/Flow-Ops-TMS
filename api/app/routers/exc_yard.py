"""
routers/exc_yard.py
TMS-EXC-001-010: Exceptions, Claims & Recovery
TMS-YARD-001-010: Appointment, Yard, Dock & Gate
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, date as _date, timedelta

router = APIRouter()

EXCEPTION_TYPES = [
    "delay","missed_pickup","missed_delivery","damage","shortage","overage",
    "refusal","temp_excursion","customs_hold","compliance","carrier_no_show",
    "rate_failure","invoice_variance","missing_document","integration_failure",
]
CLAIM_TYPES = ["loss","damage","shortage","delay","temp_failure","service_failure","overcharge"]


# ── Pydantic Models ───────────────────────────────────────────────

class ExceptionCreate(BaseModel):
    exception_type: str
    related_entity_type: str
    related_entity_id: str
    shipment_id: Optional[str] = None
    severity: str = "warning"
    queue_name: Optional[str] = None
    comments: Optional[str] = None
    is_blocking: bool = False
    source: str = "manual"
    due_hours: Optional[int] = None
    sla_minutes: Optional[int] = None

class ExceptionResolve(BaseModel):
    resolution_notes: str
    root_cause: Optional[str] = None
    override_reason: Optional[str] = None

class ClaimCreate(BaseModel):
    shipment_id: str
    claim_type: str = "damage"
    carrier_id: Optional[str] = None
    claimed_amount: float
    claimed_quantity: Optional[float] = None
    damaged_quantity: Optional[float] = None
    notes: Optional[str] = None
    exception_id: Optional[str] = None
    shipment_stop_id: Optional[str] = None

class ClaimUpdate(BaseModel):
    status: str
    carrier_response: Optional[str] = None
    approved_amount: Optional[float] = None
    settlement_amount: Optional[float] = None
    notes: Optional[str] = None

class AppointmentCreate(BaseModel):
    shipment_stop_id: str
    location_id: str
    appointment_type: str = "delivery"
    start_datetime: str
    duration_minutes: int = 60
    dock_door_id: Optional[str] = None
    carrier_id: Optional[str] = None
    scheduled_by_type: str = "internal"
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: str  # confirmed|cancelled|no_show|completed
    actual_arrival: Optional[str] = None
    actual_departure: Optional[str] = None
    cancel_reason: Optional[str] = None
    notes: Optional[str] = None

class GateTransaction(BaseModel):
    location_id: str
    transaction_type: str = "check_in"
    appointment_id: Optional[str] = None
    shipment_id: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    carrier_id: Optional[str] = None
    tractor_number: Optional[str] = None
    trailer_number: Optional[str] = None
    container_number: Optional[str] = None
    seal_number: Optional[str] = None
    chassis_number: Optional[str] = None
    is_empty: bool = False
    notes: Optional[str] = None

class YardMove(BaseModel):
    asset_type: str  # trailer|container|chassis
    asset_id: str
    from_location_id: Optional[str] = None
    to_location_id: str
    is_empty: bool = True
    notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# TMS-EXC: Exceptions, Claims & Recovery
# ══════════════════════════════════════════════════════════════════

# ── EXC-001/002/003/004: Exception CRUD ──────────────────────────

@router.post("/exceptions", status_code=201)
async def create_exception(
    payload: ExceptionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXC-001/002/003/004: Create exception with full metadata."""
    user_id = user.get("email", "system")
    if payload.exception_type not in EXCEPTION_TYPES:
        raise HTTPException(400, f"Invalid type. Valid: {', '.join(EXCEPTION_TYPES)}")

    due_at = datetime.utcnow() + timedelta(hours=payload.due_hours) if payload.due_hours else None
    exc_number = f"EXC-{datetime.utcnow().strftime('%Y%m%d')}-{payload.related_entity_id[:8].upper()}"

    result = await db.execute(text("""
        INSERT INTO tms.exceptions
            (exception_number, exception_type, related_entity_type, related_entity_id,
             shipment_id, severity, status, queue_name, comments,
             is_blocking, source, due_at, sla_minutes, created_by)
        VALUES
            (:exc_number, :exc_type, :entity_type, CAST(:entity_id AS uuid),
             CAST(:shipment_id AS uuid), :severity, 'open', :queue, :comments,
             :is_blocking, :source, :due_at, :sla_min, :created_by)
        RETURNING exception_id, exception_number
    """), {
        "exc_number":  exc_number,
        "exc_type":    payload.exception_type,
        "entity_type": payload.related_entity_type,
        "entity_id":   payload.related_entity_id,
        "shipment_id": payload.shipment_id,
        "severity":    payload.severity,
        "queue":       payload.queue_name,
        "comments":    payload.comments,
        "is_blocking": payload.is_blocking,
        "source":      payload.source,
        "due_at":      due_at,
        "sla_min":     payload.sla_minutes,
        "created_by":  user_id,
    })
    row = dict(result.mappings().one())

    # Update lifecycle if shipment-linked
    if payload.shipment_id:
        await db.execute(text("""
            INSERT INTO tms.process_lifecycle (shipment_id, has_exceptions, exception_count, current_stage)
            VALUES (CAST(:id AS uuid), TRUE, 1, 'exception')
            ON CONFLICT (shipment_id) DO UPDATE SET
                has_exceptions  = TRUE,
                exception_count = tms.process_lifecycle.exception_count + 1,
                updated_at      = NOW()
        """), {"id": payload.shipment_id})

    await db.commit()
    return {
        "exception_id":    str(row["exception_id"]),
        "exception_number":row["exception_number"],
        "exception_type":  payload.exception_type,
        "is_blocking":     payload.is_blocking,
        "severity":        payload.severity,
    }


@router.get("/exceptions")
async def list_exceptions(
    db: AsyncSession = Depends(get_db),
    exception_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    shipment_id: Optional[str] = Query(None),
    is_blocking: Optional[bool] = Query(None),
    queue_name: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """EXC-004/006: List exceptions with work queue filtering."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if exception_type:
        conditions.append("e.exception_type = :exc_type")
        params["exc_type"] = exception_type
    if severity:
        conditions.append("e.severity = :severity")
        params["severity"] = severity
    if status:
        conditions.append("e.status = :status")
        params["status"] = status
    if shipment_id:
        conditions.append("e.shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id
    if is_blocking is not None:
        conditions.append("e.is_blocking = :is_blocking")
        params["is_blocking"] = is_blocking
    if queue_name:
        conditions.append("e.queue_name = :queue_name")
        params["queue_name"] = queue_name

    result = await db.execute(text(f"""
        SELECT e.*, s.shipment_number,
               CASE WHEN e.due_at < NOW() AND e.status = 'open' THEN TRUE ELSE FALSE END AS is_overdue
        FROM tms.exceptions e
        LEFT JOIN tms.shipments s ON s.shipment_id = e.shipment_id
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE e.severity WHEN 'critical' THEN 1 WHEN 'error' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,
                 e.created_at DESC
        LIMIT :limit
    """), params)
    rows = [dict(r) for r in result.mappings().all()]

    summary = {}
    for r in rows:
        t = r.get("exception_type","unknown")
        summary[t] = summary.get(t, 0) + 1

    return {"total": len(rows), "by_type": summary, "exceptions": rows}


@router.patch("/exceptions/{exception_id}/resolve")
async def resolve_exception(
    exception_id: str,
    payload: ExceptionResolve,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXC-004/007: Resolve exception with root cause and resolution notes."""
    user_id = user.get("email", "system")
    new_status = "overridden" if payload.override_reason else "resolved"

    result = await db.execute(text("""
        UPDATE tms.exceptions
        SET status           = :status,
            resolution_notes = :notes,
            root_cause       = :root_cause,
            override_reason  = :override,
            overridden_by    = CASE WHEN :override IS NOT NULL THEN :user ELSE NULL END,
            overridden_at    = CASE WHEN :override IS NOT NULL THEN NOW() ELSE NULL END,
            resolved_at      = NOW(),
            updated_at       = NOW()
        WHERE exception_id = CAST(:id AS uuid)
        RETURNING exception_id, status, shipment_id
    """), {
        "status":     new_status,
        "notes":      payload.resolution_notes,
        "root_cause": payload.root_cause,
        "override":   payload.override_reason,
        "user":       user_id,
        "id":         exception_id,
    })
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Exception not found.")
    await db.commit()
    return dict(row)


@router.patch("/exceptions/{exception_id}/escalate")
async def escalate_exception(
    exception_id: str,
    queue_name: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXC-006: Escalate exception to a different queue."""
    await db.execute(text("""
        UPDATE tms.exceptions
        SET status = 'escalated', queue_name = :queue, escalated_at = NOW(), updated_at = NOW()
        WHERE exception_id = CAST(:id AS uuid)
    """), {"queue": queue_name, "id": exception_id})
    await db.commit()
    return {"exception_id": exception_id, "escalated_to": queue_name}


# ── EXC-007: Blocking check ───────────────────────────────────────

@router.get("/exceptions/blocking-check/{entity_type}/{entity_id}")
async def check_blocking_exceptions(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXC-007: Check if blocking exceptions prevent completion/approval."""
    result = await db.execute(text("""
        SELECT exception_id, exception_number, exception_type, severity, comments
        FROM tms.exceptions
        WHERE related_entity_type = :entity_type
          AND related_entity_id = CAST(:entity_id AS uuid)
          AND is_blocking = TRUE
          AND status NOT IN ('resolved','closed','overridden')
    """), {"entity_type": entity_type, "entity_id": entity_id})
    blocking = [dict(r) for r in result.mappings().all()]
    return {
        "entity_type":         entity_type,
        "entity_id":           entity_id,
        "has_blocking":        len(blocking) > 0,
        "blocking_count":      len(blocking),
        "blocking_exceptions": blocking,
    }


# ── EXC-008/009/010: Claims ───────────────────────────────────────

@router.post("/claims", status_code=201)
async def create_claim(
    payload: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXC-008/009: Create freight claim for loss/damage/shortage/etc."""
    user_id = user.get("email", "system")
    if payload.claim_type not in CLAIM_TYPES:
        raise HTTPException(400, f"Invalid claim_type. Valid: {', '.join(CLAIM_TYPES)}")

    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = 'USD' LIMIT 1
    """))
    currency_id = curr_result.scalar()

    claim_number = f"CLM-{datetime.utcnow().strftime('%Y%m%d')}-{payload.shipment_id[:8].upper()}"

    result = await db.execute(text("""
        INSERT INTO tms.claims
            (claim_number, claim_type, shipment_id, carrier_id,
             claimed_amount, claimed_quantity, damaged_quantity,
             currency_id, status, exception_id, shipment_stop_id,
             notes, created_by)
        VALUES
            (:claim_number, :claim_type, CAST(:shipment_id AS uuid),
             CAST(:carrier_id AS uuid),
             :claimed_amount, CAST(:claimed_qty AS numeric),
             CAST(:damaged_qty AS numeric),
             CAST(:currency_id AS uuid), 'draft',
             CAST(:exception_id AS uuid), CAST(:stop_id AS uuid),
             :notes, :created_by)
        RETURNING claim_id, claim_number
    """), {
        "claim_number":  claim_number,
        "claim_type":    payload.claim_type,
        "shipment_id":   payload.shipment_id,
        "carrier_id":    payload.carrier_id,
        "claimed_amount":payload.claimed_amount,
        "claimed_qty":   payload.claimed_quantity,
        "damaged_qty":   payload.damaged_quantity,
        "currency_id":   str(currency_id) if currency_id else None,
        "exception_id":  payload.exception_id,
        "stop_id":       payload.shipment_stop_id,
        "notes":         payload.notes,
        "created_by":    user_id,
    })
    row = dict(result.mappings().one())
    await db.commit()
    return {"claim_id": str(row["claim_id"]), "claim_number": row["claim_number"],
            "claim_type": payload.claim_type, "claimed_amount": payload.claimed_amount}


@router.get("/claims")
async def list_claims(
    db: AsyncSession = Depends(get_db),
    shipment_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    claim_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """EXC-010: List claims with status tracking."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if shipment_id:
        conditions.append("c.shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id
    if status:
        conditions.append("c.status = :status")
        params["status"] = status
    if claim_type:
        conditions.append("c.claim_type = :claim_type")
        params["claim_type"] = claim_type

    result = await db.execute(text(f"""
        SELECT c.*, s.shipment_number, p.party_name AS carrier_name
        FROM tms.claims c
        LEFT JOIN tms.shipments s ON s.shipment_id = c.shipment_id
        LEFT JOIN tms.carriers car ON car.carrier_id = c.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = car.party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY c.created_at DESC
        LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.patch("/claims/{claim_id}")
async def update_claim(
    claim_id: str,
    payload: ClaimUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXC-010: Update claim status, carrier response, settlement."""
    valid = ["draft","submitted","under_review","approved","rejected","settled","closed","withdrawn"]
    if payload.status not in valid:
        raise HTTPException(400, f"Invalid status. Valid: {', '.join(valid)}")

    user_id = user.get("email", "system")
    submitted_at = datetime.utcnow() if payload.status == "submitted" else None
    settled_at = datetime.utcnow() if payload.status == "settled" else None

    # Create credit if settled
    create_credit = payload.status == "settled" and payload.settlement_amount

    await db.execute(text("""
        UPDATE tms.claims
        SET status              = :status,
            carrier_response    = :carrier_response,
            carrier_responded_at= CASE WHEN :carrier_response IS NOT NULL THEN NOW() ELSE carrier_responded_at END,
            approved_amount     = CAST(:approved_amount AS numeric),
            settlement_amount   = CAST(:settlement_amount AS numeric),
            recovery_amount     = CAST(:settlement_amount AS numeric),
            submitted_at        = COALESCE(:submitted_at, submitted_at),
            settled_at          = COALESCE(:settled_at, settled_at),
            credit_created      = :credit_created,
            credit_amount       = CAST(:settlement_amount AS numeric),
            notes               = COALESCE(:notes, notes),
            updated_at          = NOW()
        WHERE claim_id = CAST(:id AS uuid)
    """), {
        "status":           payload.status,
        "carrier_response": payload.carrier_response,
        "approved_amount":  payload.approved_amount,
        "settlement_amount":payload.settlement_amount,
        "submitted_at":     submitted_at,
        "settled_at":       settled_at,
        "credit_created":   create_credit,
        "notes":            payload.notes,
        "id":               claim_id,
    })
    await db.commit()
    return {"claim_id": claim_id, "status": payload.status,
            "settlement_amount": payload.settlement_amount}


# ══════════════════════════════════════════════════════════════════
# TMS-YARD: Appointment, Yard, Dock & Gate
# ══════════════════════════════════════════════════════════════════

# ── YARD-001/002/003/004: Appointments ───────────────────────────

@router.post("/appointments", status_code=201)
async def create_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """YARD-001/002/003/004: Schedule appointment with conflict check."""
    user_id = user.get("email", "system")
    start_dt = datetime.fromisoformat(payload.start_datetime)
    end_dt = start_dt + timedelta(minutes=payload.duration_minutes)

    # YARD-004: Conflict check
    conflict_result = await db.execute(text("""
        SELECT COUNT(*) FROM tms.appointments
        WHERE location_id = CAST(:loc_id AS uuid)
          AND dock_door_id = CAST(:dock_id AS uuid)
          AND appointment_status_id IS NOT NULL
          AND appointment_start_datetime < :end_dt
          AND appointment_end_datetime > :start_dt
          AND cancelled_at IS NULL
    """), {
        "loc_id":   payload.location_id,
        "dock_id":  payload.dock_door_id,
        "start_dt": start_dt,
        "end_dt":   end_dt,
    })
    if payload.dock_door_id and int(conflict_result.scalar() or 0) > 0:
        raise HTTPException(409, "Appointment conflict: dock door already booked for this time slot.")

    # YARD-002: Check facility hours
    dow = start_dt.weekday() + 1  # Mon=1..Sun=7 → adjust
    schedule_result = await db.execute(text("""
        SELECT is_closed, open_time, close_time FROM tms.facility_schedules
        WHERE location_id = CAST(:loc_id AS uuid)
          AND (day_of_week = :dow OR specific_date = CAST(:appt_date AS date))
        ORDER BY specific_date NULLS LAST LIMIT 1
    """), {"loc_id": payload.location_id, "dow": dow, "appt_date": start_dt.date()})
    schedule = schedule_result.mappings().one_or_none()
    if schedule and schedule.get("is_closed"):
        raise HTTPException(422, "Facility is closed on this date.")

    apt_number = f"APT-{start_dt.strftime('%Y%m%d')}-{payload.location_id[:6].upper()}"

    result = await db.execute(text("""
        INSERT INTO tms.appointments
            (appointment_number, shipment_stop_id, location_id, dock_door_id,
             carrier_id, appointment_type, appointment_start_datetime,
             appointment_end_datetime, duration_minutes,
             scheduled_by, scheduled_by_type, notes)
        VALUES
            (:apt_number, CAST(:stop_id AS uuid), CAST(:loc_id AS uuid),
             CAST(:dock_id AS uuid), CAST(:carrier_id AS uuid),
             :apt_type, :start_dt, :end_dt, :duration,
             :scheduled_by, :scheduled_by_type, :notes)
        RETURNING appointment_id, appointment_number
    """), {
        "apt_number":        apt_number,
        "stop_id":           payload.shipment_stop_id,
        "loc_id":            payload.location_id,
        "dock_id":           payload.dock_door_id,
        "carrier_id":        payload.carrier_id,
        "apt_type":          payload.appointment_type,
        "start_dt":          start_dt,
        "end_dt":            end_dt,
        "duration":          payload.duration_minutes,
        "scheduled_by":      user_id,
        "scheduled_by_type": payload.scheduled_by_type,
        "notes":             payload.notes,
    })
    row = dict(result.mappings().one())
    await db.commit()
    return {
        "appointment_id":    str(row["appointment_id"]),
        "appointment_number":row["appointment_number"],
        "start":             str(start_dt),
        "end":               str(end_dt),
        "type":              payload.appointment_type,
    }


@router.get("/appointments")
async def list_appointments(
    db: AsyncSession = Depends(get_db),
    location_id: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """YARD-001/005: List appointments with status."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if location_id:
        conditions.append("a.location_id = CAST(:loc_id AS uuid)")
        params["loc_id"] = location_id
    if date:
        conditions.append("DATE(a.appointment_start_datetime) = CAST(:appt_date AS date)")
        params["appt_date"] = date

    result = await db.execute(text(f"""
        SELECT a.*, l.location_name, l.city, l.state_province,
               dd.dock_door_code, dd.dock_door_name,
               p.party_name AS carrier_name
        FROM tms.appointments a
        LEFT JOIN tms.locations l ON l.location_id = a.location_id
        LEFT JOIN tms.dock_doors dd ON dd.dock_door_id = a.dock_door_id
        LEFT JOIN tms.carriers c ON c.carrier_id = a.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = c.party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY a.appointment_start_datetime
        LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """YARD-005: Confirm, cancel, no-show, complete appointment."""
    valid = ["confirmed","cancelled","no_show","completed","rescheduled"]
    if payload.status not in valid:
        raise HTTPException(400, f"Status must be: {', '.join(valid)}")

    arr_dt = datetime.fromisoformat(payload.actual_arrival) if payload.actual_arrival else None
    dep_dt = datetime.fromisoformat(payload.actual_departure) if payload.actual_departure else None

    # YARD-010: Calculate detention
    detention_min = None
    if arr_dt and dep_dt:
        appt_result = await db.execute(text("""
            SELECT appointment_end_datetime FROM tms.appointments
            WHERE appointment_id = CAST(:id AS uuid)
        """), {"id": appointment_id})
        appt = appt_result.mappings().one_or_none()
        if appt and appt.get("appointment_end_datetime"):
            scheduled_end = appt["appointment_end_datetime"]
            if dep_dt > scheduled_end:
                detention_min = int((dep_dt - scheduled_end).total_seconds() / 60)

    await db.execute(text("""
        UPDATE tms.appointments
        SET actual_arrival   = :arr_dt,
            actual_departure = :dep_dt,
            detention_minutes= :detention,
            no_show          = :no_show,
            confirmed_at     = CASE WHEN :status = 'confirmed' THEN NOW() ELSE confirmed_at END,
            cancelled_at     = CASE WHEN :status = 'cancelled' THEN NOW() ELSE cancelled_at END,
            cancel_reason    = COALESCE(:cancel_reason, cancel_reason),
            notes            = COALESCE(:notes, notes),
            updated_at       = NOW()
        WHERE appointment_id = CAST(:id AS uuid)
    """), {
        "arr_dt":       arr_dt,
        "dep_dt":       dep_dt,
        "detention":    detention_min,
        "no_show":      payload.status == "no_show",
        "status":       payload.status,
        "cancel_reason":payload.cancel_reason,
        "notes":        payload.notes,
        "id":           appointment_id,
    })
    await db.commit()
    return {"appointment_id": appointment_id, "status": payload.status,
            "detention_minutes": detention_min}


# ── YARD-006/007: Gate ────────────────────────────────────────────

@router.post("/gate", status_code=201)
async def record_gate_transaction(
    payload: GateTransaction,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """YARD-006/007: Gate check-in or check-out with full details."""
    user_id = user.get("email", "system")
    txn_number = f"GATE-{payload.transaction_type.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    result = await db.execute(text("""
        INSERT INTO tms.gate_transactions
            (gate_transaction_number, location_id, appointment_id, shipment_id,
             transaction_type, driver_name, driver_license, carrier_id,
             tractor_number, trailer_number, container_number, seal_number,
             chassis_number, is_empty, transaction_at, performed_by, notes)
        VALUES
            (:txn_number, CAST(:loc_id AS uuid), CAST(:appt_id AS uuid),
             CAST(:shipment_id AS uuid), :txn_type,
             :driver_name, :driver_license, CAST(:carrier_id AS uuid),
             :tractor, :trailer, :container, :seal, :chassis,
             :is_empty, NOW(), :performed_by, :notes)
        RETURNING gate_transaction_id, gate_transaction_number
    """), {
        "txn_number":   txn_number,
        "loc_id":       payload.location_id,
        "appt_id":      payload.appointment_id,
        "shipment_id":  payload.shipment_id,
        "txn_type":     payload.transaction_type,
        "driver_name":  payload.driver_name,
        "driver_license":payload.driver_license,
        "carrier_id":   payload.carrier_id,
        "tractor":      payload.tractor_number,
        "trailer":      payload.trailer_number,
        "container":    payload.container_number,
        "seal":         payload.seal_number,
        "chassis":      payload.chassis_number,
        "is_empty":     payload.is_empty,
        "performed_by": user_id,
        "notes":        payload.notes,
    })
    row = dict(result.mappings().one())
    await db.commit()
    return {"gate_transaction_id": str(row["gate_transaction_id"]),
            "transaction_number": row["gate_transaction_number"],
            "transaction_type": payload.transaction_type}


@router.get("/gate")
async def list_gate_transactions(
    db: AsyncSession = Depends(get_db),
    location_id: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """YARD-007: Gate transaction log."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if location_id:
        conditions.append("gt.location_id = CAST(:loc_id AS uuid)")
        params["loc_id"] = location_id
    if date:
        conditions.append("DATE(gt.transaction_at) = CAST(:date AS date)")
        params["date"] = date
    if transaction_type:
        conditions.append("gt.transaction_type = :txn_type")
        params["txn_type"] = transaction_type

    result = await db.execute(text(f"""
        SELECT gt.*, l.location_name, s.shipment_number
        FROM tms.gate_transactions gt
        LEFT JOIN tms.locations l ON l.location_id = gt.location_id
        LEFT JOIN tms.shipments s ON s.shipment_id = gt.shipment_id
        WHERE {' AND '.join(conditions)}
        ORDER BY gt.transaction_at DESC
        LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


# ── YARD-008/009: Yard management ────────────────────────────────

@router.post("/yard/move", status_code=201)
async def record_yard_move(
    payload: YardMove,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """YARD-008/009: Move asset between yard locations."""
    user_id = user.get("email", "system")

    # Clear from location
    if payload.from_location_id:
        await db.execute(text("""
            UPDATE tms.yard_locations
            SET is_occupied = FALSE, current_asset_type = NULL,
                current_asset_id = NULL, occupied_since = NULL, updated_at = NOW()
            WHERE yard_location_id = CAST(:id AS uuid)
        """), {"id": payload.from_location_id})

    # Set in to location
    await db.execute(text("""
        UPDATE tms.yard_locations
        SET is_occupied = TRUE, current_asset_type = :asset_type,
            current_asset_id = :asset_id, is_empty = :is_empty,
            occupied_since = NOW(), updated_at = NOW()
        WHERE yard_location_id = CAST(:id AS uuid)
    """), {
        "asset_type": payload.asset_type,
        "asset_id":   payload.asset_id,
        "is_empty":   payload.is_empty,
        "id":         payload.to_location_id,
    })

    # Record move in yard_moves if table exists
    try:
        await db.execute(text("""
            INSERT INTO tms.yard_moves
                (asset_type, asset_identifier, from_yard_location_id,
                 to_yard_location_id, moved_by_user_id, notes)
            VALUES
                (:asset_type, :asset_id, CAST(:from_id AS uuid),
                 CAST(:to_id AS uuid), NULL, :notes)
        """), {
            "asset_type": payload.asset_type,
            "asset_id":   payload.asset_id,
            "from_id":    payload.from_location_id,
            "to_id":      payload.to_location_id,
            "notes":      payload.notes,
        })
    except Exception:
        pass

    await db.commit()
    return {
        "asset_type": payload.asset_type,
        "asset_id":   payload.asset_id,
        "from":       payload.from_location_id,
        "to":         payload.to_location_id,
        "is_empty":   payload.is_empty,
    }


@router.get("/yard/inventory")
async def get_yard_inventory(
    location_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """YARD-008/009: Yard inventory and asset locations."""
    result = await db.execute(text("""
        SELECT yl.*, l.location_name
        FROM tms.yard_locations yl
        LEFT JOIN tms.locations l ON l.location_id = yl.location_id
        WHERE yl.location_id = CAST(:loc_id AS uuid)
        ORDER BY yl.zone_code, yl.yard_location_id
    """), {"loc_id": location_id})
    spots = [dict(r) for r in result.mappings().all()]

    occupied = [s for s in spots if s.get("is_occupied")]
    empty    = [s for s in spots if not s.get("is_occupied")]

    return {
        "location_id":    location_id,
        "total_spots":    len(spots),
        "occupied":       len(occupied),
        "empty":          len(empty),
        "utilization_pct":round(len(occupied)/len(spots)*100,1) if spots else 0,
        "inventory":      spots,
    }


# ── YARD-010: Detention & throughput ─────────────────────────────

@router.get("/yard/detention/{location_id}")
async def get_detention_report(
    location_id: str,
    date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """YARD-010: Detention, dwell, wait time, service time, throughput."""
    target_date = _date.fromisoformat(date) if date else _date.today()

    result = await db.execute(text("""
        SELECT
            a.appointment_number,
            a.appointment_type,
            a.appointment_start_datetime AS scheduled_start,
            a.appointment_end_datetime   AS scheduled_end,
            a.actual_arrival,
            a.actual_departure,
            a.detention_minutes,
            a.no_show,
            EXTRACT(EPOCH FROM (a.actual_arrival - a.appointment_start_datetime))/60 AS wait_minutes,
            EXTRACT(EPOCH FROM (a.actual_departure - a.actual_arrival))/60           AS service_minutes,
            dd.dock_door_code,
            p.party_name AS carrier_name
        FROM tms.appointments a
        LEFT JOIN tms.dock_doors dd ON dd.dock_door_id = a.dock_door_id
        LEFT JOIN tms.carriers c ON c.carrier_id = a.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = c.party_id
        WHERE a.location_id = CAST(:loc_id AS uuid)
          AND DATE(a.appointment_start_datetime) = :target_date
          AND a.actual_arrival IS NOT NULL
        ORDER BY a.actual_arrival
    """), {"loc_id": location_id, "target_date": target_date})
    rows = [dict(r) for r in result.mappings().all()]

    total_detention = sum(r.get("detention_minutes") or 0 for r in rows)
    avg_service = sum(r.get("service_minutes") or 0 for r in rows) / len(rows) if rows else 0

    return {
        "location_id":     location_id,
        "date":            str(target_date),
        "appointments":    len(rows),
        "total_detention": total_detention,
        "avg_service_min": round(avg_service, 1),
        "no_shows":        sum(1 for r in rows if r.get("no_show")),
        "detail":          rows,
    }
