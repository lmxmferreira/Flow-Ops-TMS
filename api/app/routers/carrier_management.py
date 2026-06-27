"""
routers/carrier_management.py
TMS-CAR-001 through TMS-CAR-015: Carrier Management & Tendering
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, date as _date_type

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class CarrierUpdate(BaseModel):
    tax_id: Optional[str] = None
    insurance_expiry: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_amount: Optional[float] = None
    supported_modes: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None

class CarrierStatusUpdate(BaseModel):
    status_code: str  # active | inactive | pending_approval | suspended | non_compliant | blocked | terminated
    reason: Optional[str] = None

class TenderCreate(BaseModel):
    shipment_id: str
    carrier_id: str
    offered_amount: float
    currency: str = "USD"
    tender_method: str = "manual"
    service_level: Optional[str] = None
    expiration_minutes: int = 120
    notes: Optional[str] = None

class TenderResponse(BaseModel):
    response: str  # accept | reject | counter | withdraw
    reason: Optional[str] = None
    counteroffer_amount: Optional[float] = None

class TenderRuleCreate(BaseModel):
    rule_name: str
    tender_method: str = "sequential"
    expiration_minutes: int = 120
    max_retenders: int = 3
    retender_on_reject: bool = True
    retender_on_expire: bool = True
    escalate_after_hrs: Optional[int] = None
    applies_to_modes: list[str] = ["FTL", "LTL"]

class CapacityCreate(BaseModel):
    carrier_id: str
    origin_region: Optional[str] = None
    dest_region: Optional[str] = None
    transport_mode: Optional[str] = None
    equipment_type: Optional[str] = None
    committed_loads_wk: Optional[int] = None
    committed_loads_mo: Optional[int] = None
    blackout_start: Optional[str] = None
    blackout_end: Optional[str] = None
    blackout_reason: Optional[str] = None
    effective_date: Optional[str] = None

class OnboardingUpdate(BaseModel):
    status: str
    reviewed_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

class ScorecardCreate(BaseModel):
    carrier_id: str
    period_start_date: str
    period_end_date: str
    tender_acceptance_pct: Optional[float] = None
    avg_response_minutes: Optional[float] = None
    on_time_pickup_pct: Optional[float] = None
    on_time_delivery_pct: Optional[float] = None
    tracking_compliance_pct: Optional[float] = None
    invoice_accuracy_pct: Optional[float] = None
    claims_count: int = 0
    service_failures_count: int = 0


# ── CAR-001/002/003: Carrier master data ──────────────────────────

@router.get("/")
async def list_carriers(
    db: AsyncSession = Depends(get_db),
    status_code: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    compliant_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    """CAR-001: List carrier master records with compliance status."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if search:
        conditions.append("(p.party_name ILIKE :search OR c.scac ILIKE :search OR c.mc_number ILIKE :search)")
        params["search"] = f"%{search}%"
    if compliant_only:
        conditions.append("c.is_compliant = TRUE")
    if mode:
        conditions.append(":mode = ANY(c.supported_modes)")
        params["mode"] = mode

    result = await db.execute(text(f"""
        SELECT
            c.*,
            p.party_name AS carrier_name,
            p.party_code AS carrier_code,
            lv_status.display_name AS status,
            lv_safety.display_name AS safety_rating,
            -- CAR-004: Compliance summary
            (SELECT COUNT(*) FROM tms.carrier_compliance_records cr
             WHERE cr.carrier_id = c.carrier_id
               AND cr.expiration_date < CURRENT_DATE) AS expired_compliance_count,
            (SELECT MIN(cr.expiration_date) FROM tms.carrier_compliance_records cr
             WHERE cr.carrier_id = c.carrier_id
               AND cr.expiration_date >= CURRENT_DATE) AS next_expiry_date,
            -- Scorecard summary
            (SELECT ROUND(AVG(cs.total_score),1) FROM tms.carrier_scorecards cs
             WHERE cs.carrier_id = c.carrier_id) AS avg_score,
            -- Active tenders
            (SELECT COUNT(*) FROM tms.tenders t
             WHERE t.carrier_id = c.carrier_id
               AND t.tender_status_id IN (
                   SELECT lookup_value_id FROM tms.lookup_values
                   WHERE lookup_code = 'OFFERED')) AS active_tenders
        FROM tms.carriers c
        JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = c.status_id
        LEFT JOIN tms.lookup_values lv_safety ON lv_safety.lookup_value_id = c.safety_rating_id
        WHERE {' AND '.join(conditions)}
        ORDER BY p.party_name
        LIMIT :limit OFFSET :offset
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/{carrier_id}")
async def get_carrier(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-002: Get full carrier profile with attributes and compliance."""
    result = await db.execute(text("""
        SELECT c.*, p.party_name AS carrier_name, p.party_code AS carrier_code,
               lv_status.display_name AS status,
               lv_safety.display_name AS safety_rating
        FROM tms.carriers c
        JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = c.status_id
        LEFT JOIN tms.lookup_values lv_safety ON lv_safety.lookup_value_id = c.safety_rating_id
        WHERE c.carrier_id = CAST(:id AS uuid)
    """), {"id": carrier_id})
    carrier = result.mappings().one_or_none()
    if not carrier:
        raise HTTPException(404, "Carrier not found.")
    carrier = dict(carrier)

    # Compliance records
    comp_result = await db.execute(text("""
        SELECT ccr.*, lv.display_name AS compliance_type
        FROM tms.carrier_compliance_records ccr
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = ccr.compliance_type_id
        WHERE ccr.carrier_id = CAST(:id AS uuid)
        ORDER BY ccr.expiration_date
    """), {"id": carrier_id})
    carrier["compliance_records"] = [dict(r) for r in comp_result.mappings().all()]

    # Latest scorecard
    sc_result = await db.execute(text("""
        SELECT * FROM tms.carrier_scorecards
        WHERE carrier_id = CAST(:id AS uuid)
        ORDER BY period_end_date DESC LIMIT 1
    """), {"id": carrier_id})
    sc = sc_result.mappings().one_or_none()
    carrier["latest_scorecard"] = dict(sc) if sc else None

    # Capacity commitments
    cap_result = await db.execute(text("""
        SELECT * FROM tms.carrier_capacity
        WHERE carrier_id = CAST(:id AS uuid) AND is_active = TRUE
        ORDER BY effective_date
    """), {"id": carrier_id})
    carrier["capacity"] = [dict(r) for r in cap_result.mappings().all()]

    # Onboarding status
    ob_result = await db.execute(text("""
        SELECT * FROM tms.carrier_onboarding WHERE carrier_id = CAST(:id AS uuid)
    """), {"id": carrier_id})
    ob = ob_result.mappings().one_or_none()
    carrier["onboarding"] = dict(ob) if ob else None

    return carrier


@router.patch("/{carrier_id}")
async def update_carrier(
    carrier_id: str,
    payload: CarrierUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-002: Update carrier attributes."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update.")

    set_parts = []
    params: dict[str, Any] = {"id": carrier_id}
    for k, v in updates.items():
        if k == "insurance_expiry" and v:
            set_parts.append(f"{k} = CAST(:{k} AS date)")
        else:
            set_parts.append(f"{k} = :{k}")
        params[k] = v
    set_parts.append("updated_at = NOW()")

    result = await db.execute(text(f"""
        UPDATE tms.carriers SET {', '.join(set_parts)}
        WHERE carrier_id = CAST(:id AS uuid)
        RETURNING carrier_id, updated_at
    """), params)
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Carrier not found.")
    return dict(row)


# ── CAR-003/005: Carrier status management ────────────────────────

@router.patch("/{carrier_id}/status")
async def update_carrier_status(
    carrier_id: str,
    payload: CarrierStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-003/005: Update carrier status with reason."""
    user_id = user.get("email", "system")

    # Get status_id from lookup
    status_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values
        WHERE UPPER(lookup_code) = UPPER(:code)
        LIMIT 1
    """), {"code": payload.status_code})
    status_row = status_result.mappings().one_or_none()
    status_id = str(status_row["lookup_value_id"]) if status_row else None

    # Update status and compliance flag
    is_compliant = payload.status_code.lower() in ("active",)
    blocked_reason = payload.reason if payload.status_code.lower() == "blocked" else None

    result = await db.execute(text("""
        UPDATE tms.carriers
        SET status_id       = CAST(:status_id AS uuid),
            is_compliant    = :is_compliant,
            blocked_reason  = :blocked_reason,
            updated_at      = NOW()
        WHERE carrier_id = CAST(:id AS uuid)
        RETURNING carrier_id, status_id, is_compliant
    """), {
        "status_id":    status_id,
        "is_compliant": is_compliant,
        "blocked_reason": blocked_reason,
        "id":           carrier_id,
    })
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Carrier not found.")
    return {"carrier_id": str(row["carrier_id"]),
            "status": payload.status_code, "is_compliant": is_compliant,
            "updated_by": user_id}


# ── CAR-004/005: Compliance check ────────────────────────────────

@router.get("/{carrier_id}/compliance-check")
async def check_carrier_compliance(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CAR-004/005: Check if a carrier is eligible for tendering.
    Returns compliance status and any blocking issues.
    """
    carrier_result = await db.execute(text("""
        SELECT c.carrier_id, p.party_name AS carrier_name,
               lv.display_name AS status, c.is_compliant,
               c.blocked_reason, c.insurance_expiry
        FROM tms.carriers c
        JOIN tms.parties p ON p.party_id = c.party_id
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = c.status_id
        WHERE c.carrier_id = CAST(:id AS uuid)
    """), {"id": carrier_id})
    carrier = carrier_result.mappings().one_or_none()
    if not carrier:
        raise HTTPException(404, "Carrier not found.")
    carrier = dict(carrier)

    issues = []
    blocking = []

    # Check status
    status = (carrier.get("status") or "").lower()
    if status in ("inactive", "blocked", "terminated", "suspended"):
        blocking.append(f"Carrier status is '{status}'")
    if status == "non_compliant":
        blocking.append("Carrier is marked non-compliant")
    if carrier.get("blocked_reason"):
        blocking.append(f"Blocked: {carrier['blocked_reason']}")

    # Check insurance expiry
    if carrier.get("insurance_expiry"):
        ins_exp = carrier["insurance_expiry"]
        from datetime import date as _d
        if isinstance(ins_exp, str):
            ins_exp = _d.fromisoformat(ins_exp)
        if ins_exp < _d.today():
            blocking.append(f"Insurance expired on {ins_exp}")

    # Check compliance records
    comp_result = await db.execute(text("""
        SELECT lv.display_name AS compliance_type, ccr.expiration_date, ccr.certificate_number
        FROM tms.carrier_compliance_records ccr
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = ccr.compliance_type_id
        WHERE ccr.carrier_id = CAST(:id AS uuid)
          AND ccr.expiration_date < CURRENT_DATE
    """), {"id": carrier_id})
    expired = [dict(r) for r in comp_result.mappings().all()]
    for exp in expired:
        issues.append(f"{exp.get('compliance_type', 'Record')} expired: {exp.get('expiration_date')}")

    can_tender = len(blocking) == 0

    # Auto-update compliance flag if needed
    if not can_tender and carrier.get("is_compliant"):
        await db.execute(text("""
            UPDATE tms.carriers SET is_compliant = FALSE,
            compliance_checked_at = NOW() WHERE carrier_id = CAST(:id AS uuid)
        """), {"id": carrier_id})
        await db.commit()

    return {
        "carrier_id":    carrier_id,
        "carrier_name":  carrier.get("carrier_name"),
        "status":        carrier.get("status"),
        "can_tender":    can_tender,
        "is_compliant":  carrier.get("is_compliant"),
        "blocking_issues": blocking,
        "warnings":      issues,
        "expired_records": expired,
    }


# ── CAR-006: Scorecards ───────────────────────────────────────────

@router.get("/{carrier_id}/scorecard")
async def get_carrier_scorecard(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-006: Get carrier scorecard with all KPIs."""
    result = await db.execute(text("""
        SELECT * FROM tms.carrier_scorecards
        WHERE carrier_id = CAST(:id AS uuid)
        ORDER BY period_end_date DESC
        LIMIT 12
    """), {"id": carrier_id})
    scorecards = [dict(r) for r in result.mappings().all()]
    if not scorecards:
        return {"carrier_id": carrier_id, "scorecards": [], "latest": None}

    latest = scorecards[0]
    return {
        "carrier_id": carrier_id,
        "latest": latest,
        "history": scorecards,
        "trend": {
            "on_time_delivery_trend": [s.get("on_time_delivery_pct") for s in scorecards[:6]],
            "acceptance_trend":       [s.get("tender_acceptance_pct") for s in scorecards[:6]],
        }
    }


@router.post("/{carrier_id}/scorecard", status_code=201)
async def create_scorecard(
    carrier_id: str,
    payload: ScorecardCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-006: Record carrier scorecard for a period."""
    # Calculate composite score
    scores = [
        payload.tender_acceptance_pct or 0,
        payload.on_time_pickup_pct or 0,
        payload.on_time_delivery_pct or 0,
        payload.tracking_compliance_pct or 0,
        payload.invoice_accuracy_pct or 0,
    ]
    # Deduct for claims and failures
    base_score = sum(s for s in scores) / len(scores) if scores else 0
    deductions = (payload.claims_count * 2) + (payload.service_failures_count * 3)
    total_score = max(0, round(base_score - deductions, 1))

    result = await db.execute(text("""
        INSERT INTO tms.carrier_scorecards
            (carrier_id, period_start_date, period_end_date,
             tender_acceptance_pct, avg_response_minutes,
             on_time_pickup_pct, on_time_delivery_pct,
             tracking_compliance_pct, invoice_accuracy_pct,
             claims_count, service_failures_count, total_score)
        VALUES
            (CAST(:carrier_id AS uuid),
             CAST(:period_start_date AS date), CAST(:period_end_date AS date),
             CAST(:tender_acceptance_pct AS numeric), CAST(:avg_response_minutes AS numeric),
             CAST(:on_time_pickup_pct AS numeric), CAST(:on_time_delivery_pct AS numeric),
             CAST(:tracking_compliance_pct AS numeric), CAST(:invoice_accuracy_pct AS numeric),
             :claims_count, :service_failures_count, :total_score)
        RETURNING carrier_scorecard_id, total_score
    """), {**payload.model_dump(), "total_score": total_score})
    await db.commit()
    row = dict(result.mappings().one())
    return {"scorecard_id": str(row["carrier_scorecard_id"]), "total_score": float(row["total_score"])}


# ── CAR-007/008/009/010/011/012: Tendering ───────────────────────

@router.post("/tenders", status_code=201)
async def create_tender(
    payload: TenderCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CAR-007/008: Create and send a tender to a carrier.
    Checks carrier eligibility before tendering (CAR-005).
    """
    user_id = user.get("email", "system")

    # CAR-005: Compliance check
    comp_result = await db.execute(text("""
        SELECT c.is_compliant, lv.display_name AS status, c.blocked_reason
        FROM tms.carriers c
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = c.status_id
        WHERE c.carrier_id = CAST(:id AS uuid)
    """), {"id": payload.carrier_id})
    carrier = comp_result.mappings().one_or_none()
    if not carrier:
        raise HTTPException(404, "Carrier not found.")

    status = (carrier.get("status") or "").lower()
    if status in ("inactive", "blocked", "terminated", "suspended") and not payload.notes:
        raise HTTPException(422, f"Cannot tender to carrier with status '{status}'. Provide override notes to proceed.")

    # Get OFFERED status lookup id
    status_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values
        WHERE UPPER(lookup_code) = 'SENT' LIMIT 1
    """))
    offered_status = status_result.scalar()

    # Get currency lookup id
    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :code LIMIT 1
    """), {"code": payload.currency})
    currency_id = curr_result.scalar()

    from datetime import datetime, timedelta
    expires_at = datetime.utcnow() + timedelta(minutes=payload.expiration_minutes)

    # Generate tender number
    tender_number = f"TND-{datetime.utcnow().strftime('%Y%m%d')}-{str(payload.shipment_id)[:8].upper()}"

    result = await db.execute(text("""
        INSERT INTO tms.tenders
            (tender_number, shipment_id, carrier_id, tender_method,
             tender_status_id, offered_amount, currency_id,
             service_level, sent_at, expires_at, override_reason,
             created_by_user_id)
        VALUES
            (:tender_number, CAST(:shipment_id AS uuid), CAST(:carrier_id AS uuid),
             :tender_method, CAST(:tender_status_id AS uuid),
             :offered_amount, CAST(:currency_id AS uuid),
             :service_level, NOW(), :expires_at, :override_reason,
             CAST(:created_by AS uuid))
        RETURNING tender_id, tender_number
    """), {
        "tender_number":   tender_number,
        "shipment_id":     payload.shipment_id,
        "carrier_id":      payload.carrier_id,
        "tender_method":   payload.tender_method,
        "tender_status_id":str(offered_status) if offered_status else None,
        "offered_amount":  payload.offered_amount,
        "currency_id":     str(currency_id) if currency_id else None,
        "service_level":   payload.service_level,
        "expires_at":      expires_at,
        "override_reason": payload.notes,
        "created_by":      None,  # user UUID not available
    })
    await db.commit()
    row = dict(result.mappings().one())

    # Update lifecycle
    await db.execute(text("""
        INSERT INTO tms.process_lifecycle (shipment_id, tendered, tendered_at, current_stage)
        VALUES (CAST(:id AS uuid), TRUE, NOW(), 'tendered')
        ON CONFLICT (shipment_id) DO UPDATE SET
            tendered = TRUE, tendered_at = NOW(),
            current_stage = 'tendered', updated_at = NOW()
    """), {"id": payload.shipment_id})
    await db.commit()

    return {
        "tender_id":     str(row["tender_id"]),
        "tender_number": row["tender_number"],
        "shipment_id":   payload.shipment_id,
        "carrier_id":    payload.carrier_id,
        "offered_amount":payload.offered_amount,
        "status":        "offered",
        "expires_at":    str(expires_at),
        "sent_via":      "system",
    }


@router.patch("/tenders/{tender_id}/respond")
async def respond_to_tender(
    tender_id: str,
    payload: TenderResponse,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-009: Carrier accepts, rejects, counters, or lets tender expire."""
    user_id = user.get("email", "system")

    # Load tender
    tender_result = await db.execute(text("""
        SELECT t.*, lv.lookup_value AS current_status
        FROM tms.tenders t
        LEFT JOIN tms.lookup_values lv ON lv.lookup_value_id = t.tender_status_id
        WHERE t.tender_id = CAST(:id AS uuid)
    """), {"id": tender_id})
    tender = tender_result.mappings().one_or_none()
    if not tender:
        raise HTTPException(404, "Tender not found.")
    tender = dict(tender)

    # Get new status lookup
    status_map = {
        "accept":   "ACCEPTED",
        "reject":   "REJECTED",
        "counter":  "COUNTERED",
        "withdraw": "WITHDRAWN",
    }
    if payload.response not in status_map:
        raise HTTPException(400, f"Invalid response. Use: {', '.join(status_map.keys())}")

    new_status_code = status_map[payload.response]
    status_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values
        WHERE UPPER(lookup_code) = :code LIMIT 1
    """), {"code": new_status_code})
    new_status_id = status_result.scalar()

    update_params: dict[str, Any] = {
        "status_id":    str(new_status_id) if new_status_id else None,
        "responded_at": datetime.utcnow(),
        "id":           tender_id,
        "counteroffer": payload.counteroffer_amount,
    }

    await db.execute(text("""
        UPDATE tms.tenders
        SET tender_status_id   = CAST(:status_id AS uuid),
            responded_at       = :responded_at,
            counteroffer_amount= :counteroffer,
            updated_at         = NOW()
        WHERE tender_id = CAST(:id AS uuid)
    """), update_params)

    # Log tender event (CAR-011)
    await db.execute(text("""
        INSERT INTO tms.tender_events (tender_id, event_type, performed_by, notes)
        VALUES (CAST(:tender_id AS uuid), :event_type, :performed_by, :notes)
    """), {
        "tender_id":    tender_id,
        "event_type":   payload.response,
        "performed_by": user_id,
        "notes":        payload.reason,
    })

    # Update lifecycle if accepted
    if payload.response == "accept":
        await db.execute(text("""
            INSERT INTO tms.process_lifecycle (shipment_id, tender_accepted, tender_accepted_at, current_stage)
            VALUES (CAST(:id AS uuid), TRUE, NOW(), 'accepted')
            ON CONFLICT (shipment_id) DO UPDATE SET
                tender_accepted = TRUE, tender_accepted_at = NOW(),
                current_stage = 'accepted', updated_at = NOW()
        """), {"id": str(tender.get("shipment_id"))})

    await db.commit()

    return {
        "tender_id":       tender_id,
        "response":        payload.response,
        "new_status":      new_status_code,
        "counteroffer":    payload.counteroffer_amount,
        "reason":          payload.reason,
        "responded_by":    user_id,
    }


@router.post("/tenders/{tender_id}/retender")
async def retender(
    tender_id: str,
    carrier_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-010/012: Re-tender a rejected or expired tender to same or new carrier."""
    # Load original tender
    orig_result = await db.execute(text("""
        SELECT * FROM tms.tenders WHERE tender_id = CAST(:id AS uuid)
    """), {"id": tender_id})
    orig = orig_result.mappings().one_or_none()
    if not orig:
        raise HTTPException(404, "Tender not found.")
    orig = dict(orig)

    new_carrier_id = carrier_id or str(orig["carrier_id"])
    from datetime import datetime, timedelta
    expires_at = datetime.utcnow() + timedelta(hours=2)
    tender_number = f"TND-{datetime.utcnow().strftime('%Y%m%d')}-R{(orig.get('retender_count') or 0)+1}"

    status_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE UPPER(lookup_code) = 'SENT' LIMIT 1
    """))
    offered_status = status_result.scalar()

    result = await db.execute(text("""
        INSERT INTO tms.tenders
            (tender_number, shipment_id, carrier_id, tender_method,
             tender_status_id, offered_amount, currency_id,
             parent_tender_id, retender_count, sent_at, expires_at)
        VALUES
            (:tender_number, CAST(:shipment_id AS uuid), CAST(:carrier_id AS uuid),
             :tender_method, CAST(:status_id AS uuid),
             :offered_amount, CAST(:currency_id AS uuid),
             CAST(:parent_id AS uuid), :retender_count, NOW(), :expires_at)
        RETURNING tender_id, tender_number
    """), {
        "tender_number":  tender_number,
        "shipment_id":    str(orig["shipment_id"]),
        "carrier_id":     new_carrier_id,
        "tender_method":  orig.get("tender_method") or "manual",
        "status_id":      str(offered_status) if offered_status else None,
        "offered_amount": float(orig["offered_amount"]),
        "currency_id":    str(orig["currency_id"]) if orig.get("currency_id") else None,
        "parent_id":      tender_id,
        "retender_count": (orig.get("retender_count") or 0) + 1,
        "expires_at":     expires_at,
    })
    await db.commit()
    row = dict(result.mappings().one())
    return {
        "new_tender_id":    str(row["tender_id"]),
        "tender_number":    row["tender_number"],
        "parent_tender_id": tender_id,
        "carrier_id":       new_carrier_id,
        "retender_count":   (orig.get("retender_count") or 0) + 1,
    }


@router.get("/tenders/{shipment_id}/history")
async def get_tender_history(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-011: Full tender history for a shipment."""
    result = await db.execute(text("""
        SELECT t.*, p.party_name AS carrier_name, c.scac,
               lv_status.display_name AS status,
               lv_reason.display_name AS response_reason
        FROM tms.tenders t
        JOIN tms.carriers c ON c.carrier_id = t.carrier_id
        JOIN tms.parties p  ON p.party_id   = c.party_id
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = t.tender_status_id
        LEFT JOIN tms.lookup_values lv_reason ON lv_reason.lookup_value_id = t.response_reason_id
        WHERE t.shipment_id = CAST(:id AS uuid)
        ORDER BY t.created_at
    """), {"id": shipment_id})
    tenders = [dict(r) for r in result.mappings().all()]

    # Get events for each tender
    for tender in tenders:
        ev_result = await db.execute(text("""
            SELECT * FROM tms.tender_events
            WHERE tender_id = CAST(:id AS uuid)
            ORDER BY created_at
        """), {"id": str(tender["tender_id"])})
        tender["events"] = [dict(r) for r in ev_result.mappings().all()]

    return {
        "shipment_id":   shipment_id,
        "tender_count":  len(tenders),
        "tenders":       tenders,
    }


# ── CAR-010: Tender rules ─────────────────────────────────────────

@router.get("/tender-rules")
async def list_tender_rules(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.tender_rules WHERE is_active = TRUE ORDER BY tender_method
    """))
    return [dict(r) for r in result.mappings().all()]


@router.post("/tender-rules", status_code=201)
async def create_tender_rule(
    payload: TenderRuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.tender_rules
            (rule_name, tender_method, expiration_minutes, max_retenders,
             retender_on_reject, retender_on_expire, escalate_after_hrs, applies_to_modes)
        VALUES
            (:rule_name, :tender_method, :expiration_minutes, :max_retenders,
             :retender_on_reject, :retender_on_expire, :escalate_after_hrs, :applies_to_modes)
        RETURNING rule_id
    """), payload.model_dump())
    await db.commit()
    return {"rule_id": str(result.scalar()), **payload.model_dump()}


# ── CAR-014: Carrier capacity ─────────────────────────────────────

@router.get("/{carrier_id}/capacity")
async def get_carrier_capacity(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.carrier_capacity
        WHERE carrier_id = CAST(:id AS uuid) AND is_active = TRUE
        ORDER BY effective_date
    """), {"id": carrier_id})
    rows = [dict(r) for r in result.mappings().all()]

    # Check for active blackouts
    blackouts = [r for r in rows if r.get("blackout_start") and r.get("blackout_end")]
    return {"carrier_id": carrier_id, "capacity": rows, "active_blackouts": blackouts}


@router.post("/capacity", status_code=201)
async def create_capacity(
    payload: CapacityCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-014: Record carrier capacity commitment or blackout."""
    eff = _date_type.fromisoformat(payload.effective_date) if payload.effective_date else _date_type.today()
    data = payload.model_dump(); data.pop("effective_date")
    result = await db.execute(text("""
        INSERT INTO tms.carrier_capacity
            (carrier_id, origin_region, dest_region, transport_mode, equipment_type,
             committed_loads_wk, committed_loads_mo,
             blackout_start, blackout_end, blackout_reason, effective_date)
        VALUES
            (CAST(:carrier_id AS uuid), :origin_region, :dest_region,
             :transport_mode, :equipment_type,
             :committed_loads_wk, :committed_loads_mo,
             CAST(:blackout_start AS date), CAST(:blackout_end AS date),
             :blackout_reason, :effective_date)
        RETURNING capacity_id
    """), {**data, "effective_date": eff})
    await db.commit()
    return {"capacity_id": str(result.scalar()), **payload.model_dump()}


# ── CAR-015: Carrier onboarding ───────────────────────────────────

@router.get("/{carrier_id}/onboarding")
async def get_onboarding(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT co.*, p.party_name AS carrier_name, c.scac
        FROM tms.carrier_onboarding co
        JOIN tms.carriers c ON c.carrier_id = co.carrier_id
        JOIN tms.parties p  ON p.party_id   = c.party_id
        WHERE co.carrier_id = CAST(:id AS uuid)
    """), {"id": carrier_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "No onboarding record found. Create one first.")
    return dict(row)


@router.post("/{carrier_id}/onboarding", status_code=201)
async def start_onboarding(
    carrier_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-015: Start carrier onboarding workflow."""
    result = await db.execute(text("""
        INSERT INTO tms.carrier_onboarding (carrier_id, status, submitted_at)
        VALUES (CAST(:id AS uuid), 'pending', NOW())
        ON CONFLICT (carrier_id) DO UPDATE SET status = 'pending', updated_at = NOW()
        RETURNING onboarding_id, status
    """), {"id": carrier_id})
    await db.commit()
    return dict(result.mappings().one())


@router.patch("/{carrier_id}/onboarding")
async def update_onboarding(
    carrier_id: str,
    payload: OnboardingUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CAR-015: Update onboarding status (approve, reject, request docs)."""
    user_id = user.get("email", "system")
    extra_params: dict[str, Any] = {}
    if payload.status == "approved":
        extra_params["approved_by"] = user_id
        extra_params["approved_at"] = datetime.utcnow()
    elif payload.status == "in_review":
        extra_params["reviewed_by"] = user_id
        extra_params["reviewed_at"] = datetime.utcnow()

    result = await db.execute(text("""
        UPDATE tms.carrier_onboarding
        SET status           = :status,
            reviewed_by      = :reviewed_by,
            reviewed_at      = :reviewed_at,
            approved_by      = :approved_by,
            approved_at      = :approved_at,
            rejection_reason = :rejection_reason,
            notes            = :notes,
            updated_at       = NOW()
        WHERE carrier_id = CAST(:id AS uuid)
        RETURNING onboarding_id, status
    """), {
        "status":           payload.status,
        "reviewed_by":      extra_params.get("reviewed_by"),
        "reviewed_at":      extra_params.get("reviewed_at"),
        "approved_by":      extra_params.get("approved_by"),
        "approved_at":      extra_params.get("approved_at"),
        "rejection_reason": payload.rejection_reason,
        "notes":            payload.notes,
        "id":               carrier_id,
    })
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "No onboarding record found.")
    return dict(row)
