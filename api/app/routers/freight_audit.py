"""
routers/freight_audit.py
TMS-AUDIT-001 through TMS-AUDIT-020: Freight Audit, Dispute & Pay
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, date as _date

router = APIRouter()

EXCEPTION_TYPES = [
    "overcharge","undercharge","missing_charge","duplicate","invalid",
    "incorrect_fuel","unauthorized_accessorial","incorrect_tax",
    "incorrect_currency","incorrect_distance","incorrect_reference",
]
DISPUTE_REASONS = [
    "rate_mismatch","duplicate_invoice","missing_pod","unauthorized_accessorial",
    "incorrect_fuel","incorrect_shipment","tax_issue","service_failure",
    "damage","shortage","overcharge",
]


# ── Pydantic Models ───────────────────────────────────────────────

class AuditRunRequest(BaseModel):
    invoice_id: str
    tolerance_id: Optional[str] = None
    audit_type: str = "auto"

class AuditLineOverride(BaseModel):
    audit_result_id: str
    disposition: str
    reason_code: str
    comments: str

class DisputeCreate(BaseModel):
    carrier_invoice_id: str
    carrier_invoice_line_id: Optional[str] = None
    dispute_reason: str
    disputed_amount: float
    expected_amount: Optional[float] = None
    notes: Optional[str] = None

class DisputeResponse(BaseModel):
    dispute_id: str
    carrier_response: str
    response_channel: str = "portal"
    resolution_code: Optional[str] = None

class VoucherCreate(BaseModel):
    carrier_invoice_id: str
    include_disputed: bool = False

class PaymentUpdate(BaseModel):
    payment_status: str
    payment_amount: Optional[float] = None
    payment_reference: Optional[str] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    erp_voucher_id: Optional[str] = None
    notes: Optional[str] = None

class ToleranceCreate(BaseModel):
    tolerance_name: str
    carrier_id: Optional[str] = None
    transport_mode: Optional[str] = None
    charge_code: Optional[str] = None
    variance_pct: float = 5.0
    variance_amount: float = 10.0
    use_pct: bool = True
    auto_approve: bool = True


# ── AUDIT-001/002/003: Run freight audit ─────────────────────────

@router.post("/run", status_code=201)
async def run_freight_audit(
    payload: AuditRunRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    AUDIT-001/002/003: Automated freight audit.
    Compares invoice lines against contracted rates, estimates, tolerances.
    Identifies overcharges, duplicates, unauthorized charges, etc.
    """
    user_id = user.get("email", "system")

    # Load invoice
    inv_result = await db.execute(text("""
        SELECT ci.*, p.party_name AS carrier_name
        FROM tms.carrier_invoices ci
        JOIN tms.carriers c ON c.carrier_id = ci.carrier_id
        JOIN tms.parties  p ON p.party_id   = c.party_id
        WHERE ci.carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": payload.invoice_id})
    inv = inv_result.mappings().one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found.")
    inv = dict(inv)

    # Load invoice lines
    lines_result = await db.execute(text("""
        SELECT * FROM tms.carrier_invoice_lines
        WHERE carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY line_number
    """), {"id": payload.invoice_id})
    lines = [dict(r) for r in lines_result.mappings().all()]

    # Load shipment costs (expected amounts)
    costs_by_code: dict = {}
    if inv.get("shipment_id"):
        costs_result = await db.execute(text("""
            SELECT charge_code, SUM(amount) AS total
            FROM tms.shipment_costs WHERE shipment_id = CAST(:id AS uuid)
            GROUP BY charge_code
        """), {"id": str(inv["shipment_id"])})
        costs_by_code = {r["charge_code"]: float(r["total"]) for r in costs_result.mappings().all()}

    # Load tolerance
    tol: dict = {"variance_pct": 5.0, "variance_amount": 10.0,
                 "use_pct": True, "auto_approve": True}
    if payload.tolerance_id:
        tr = await db.execute(text("""
            SELECT * FROM tms.audit_tolerances WHERE tolerance_id = CAST(:id AS uuid)
        """), {"id": payload.tolerance_id})
        t = tr.mappings().one_or_none()
        if t:
            tol = dict(t)
    else:
        # Get carrier-specific or default tolerance
        tr = await db.execute(text("""
            SELECT * FROM tms.audit_tolerances
            WHERE is_active = TRUE
              AND (carrier_id = CAST(:carrier_id AS uuid) OR carrier_id IS NULL)
            ORDER BY carrier_id NULLS LAST, variance_pct ASC LIMIT 1
        """), {"carrier_id": str(inv["carrier_id"])})
        t = tr.mappings().one_or_none()
        if t:
            tol = dict(t)

    audit_results = []
    auto_approved = 0
    exceptions = 0

    # AUDIT-003: Check for duplicate invoice
    dup_result = await db.execute(text("""
        SELECT COUNT(*) AS cnt FROM tms.carrier_invoices
        WHERE carrier_id = CAST(:carrier_id AS uuid)
          AND carrier_invoice_number = :inv_num
          AND carrier_invoice_id != CAST(:id AS uuid)
          AND status NOT IN ('canceled','reversed')
    """), {
        "carrier_id": str(inv["carrier_id"]),
        "inv_num": inv["carrier_invoice_number"],
        "id": payload.invoice_id,
    })
    if int(dup_result.scalar() or 0) > 0:
        # Record duplicate exception at header level
        r_id = await _save_audit_result(db, {
            "carrier_invoice_id": payload.invoice_id,
            "carrier_invoice_line_id": None,
            "expected_amount": 0,
            "invoiced_amount": float(inv["invoice_total_amount"]),
            "variance_amount": float(inv["invoice_total_amount"]),
            "tolerance_amount": 0,
            "tolerance_percent": 0,
            "exception_type": "duplicate",
            "disposition": "pending",
            "audit_type": payload.audit_type,
            "shipment_id": str(inv["shipment_id"]) if inv.get("shipment_id") else None,
            "charge_code": None,
            "audit_rule_name": "Duplicate Invoice Check",
        })
        audit_results.append({"audit_result_id": r_id, "exception_type": "duplicate",
                               "disposition": "pending"})
        exceptions += 1

    # AUDIT-002/007: Line-level audit
    for line in lines:
        charge_code = line.get("charge_code")
        invoiced = float(line.get("line_amount") or 0)
        expected = costs_by_code.get(charge_code, invoiced)  # default to invoiced if no estimate
        variance = invoiced - expected

        # Calculate tolerance
        tol_pct = float(tol.get("variance_pct", 5.0))
        tol_amt = float(tol.get("variance_amount", 10.0))
        use_pct = bool(tol.get("use_pct", True))

        if expected > 0:
            variance_pct = abs(variance / expected * 100)
        else:
            variance_pct = 0

        within_tolerance = (variance_pct <= tol_pct) if use_pct else (abs(variance) <= tol_amt)

        # Determine exception type
        exc_type = None
        if not within_tolerance:
            exc_type = "overcharge" if variance > 0 else "undercharge"

        disposition = "approved" if within_tolerance and tol.get("auto_approve") else "pending"
        if not within_tolerance:
            disposition = "pending"
            exceptions += 1
        else:
            auto_approved += 1

        r_id = await _save_audit_result(db, {
            "carrier_invoice_id": payload.invoice_id,
            "carrier_invoice_line_id": str(line["carrier_invoice_line_id"]),
            "expected_amount": expected,
            "invoiced_amount": invoiced,
            "variance_amount": variance,
            "tolerance_amount": tol_amt,
            "tolerance_percent": tol_pct,
            "exception_type": exc_type,
            "disposition": disposition,
            "audit_type": payload.audit_type,
            "shipment_id": str(inv["shipment_id"]) if inv.get("shipment_id") else None,
            "charge_code": charge_code,
            "audit_rule_name": "Auto Rate Check",
        })
        audit_results.append({
            "audit_result_id": r_id,
            "charge_code":     charge_code,
            "invoiced":        invoiced,
            "expected":        expected,
            "variance":        round(variance, 2),
            "within_tolerance":within_tolerance,
            "exception_type":  exc_type,
            "disposition":     disposition,
        })

    # Update invoice status (AUDIT-005/006)
    new_status = "matched" if exceptions == 0 else "exception"
    await db.execute(text("""
        UPDATE tms.carrier_invoices SET status = :status, updated_at = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"status": new_status, "id": payload.invoice_id})

    # Record audit history (AUDIT-019)
    await _audit_history(db, payload.invoice_id, "audit_started", inv.get("status"),
                         new_status, user_id,
                         f"Auto audit: {auto_approved} approved, {exceptions} exceptions")
    await db.commit()

    return {
        "invoice_id":       payload.invoice_id,
        "carrier":          inv.get("carrier_name"),
        "invoice_number":   inv.get("carrier_invoice_number"),
        "audit_type":       payload.audit_type,
        "new_status":       new_status,
        "lines_audited":    len(lines),
        "auto_approved":    auto_approved,
        "exceptions":       exceptions,
        "tolerance_used":   tol,
        "audit_results":    audit_results,
    }


# ── AUDIT-007: Line audit results ────────────────────────────────

@router.get("/results/{invoice_id}")
async def get_audit_results(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-007: Line-level audit results with expected/invoiced/variance."""
    result = await db.execute(text("""
        SELECT far.*,
               cil.charge_code, cil.description AS line_description,
               cil.line_amount AS invoiced_line_amount
        FROM tms.freight_audit_results far
        LEFT JOIN tms.carrier_invoice_lines cil
               ON cil.carrier_invoice_line_id = far.carrier_invoice_line_id
        WHERE far.carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY far.created_at
    """), {"id": invoice_id})
    rows = [dict(r) for r in result.mappings().all()]

    summary = {"total": len(rows), "approved": 0, "pending": 0,
               "disputed": 0, "exceptions": 0}
    for r in rows:
        d = r.get("disposition", "pending")
        if d in summary:
            summary[d] += 1
        if r.get("exception_type"):
            summary["exceptions"] += 1

    return {"invoice_id": invoice_id, "summary": summary, "results": rows}


# ── AUDIT-008/009: Manual override / disposition ──────────────────

@router.patch("/results/{audit_result_id}/disposition")
async def set_disposition(
    audit_result_id: str,
    payload: AuditLineOverride,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-008/009: Approve, reject, dispute, short-pay, override, or escalate."""
    user_id = user.get("email", "system")
    valid = ["approved","rejected","disputed","short_pay","override","escalated","pending"]
    if payload.disposition not in valid:
        raise HTTPException(400, f"Invalid disposition. Valid: {', '.join(valid)}")

    # Require reason code and comment for manual overrides (AUDIT-009)
    if payload.disposition in ("override", "short_pay", "rejected"):
        if not payload.reason_code or not payload.comments:
            raise HTTPException(422, "reason_code and comments are required for this disposition.")

    await db.execute(text("""
        UPDATE tms.freight_audit_results
        SET disposition       = :disposition,
            comments          = :comments,
            override_reason   = :reason,
            overridden_by     = :user,
            overridden_at     = NOW(),
            approved_at       = CASE WHEN :disposition = 'approved' THEN NOW() ELSE approved_at END
        WHERE freight_audit_result_id = CAST(:id AS uuid)
    """), {
        "disposition": payload.disposition,
        "comments":    payload.comments,
        "reason":      payload.reason_code,
        "user":        user_id,
        "id":          audit_result_id,
    })
    await db.commit()
    return {"audit_result_id": audit_result_id, "disposition": payload.disposition,
            "updated_by": user_id}


# ── AUDIT-010/011: Disputes ───────────────────────────────────────

@router.post("/disputes", status_code=201)
async def create_dispute(
    payload: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-010/011: Create dispute against carrier invoice or invoice line."""
    user_id = user.get("email", "system")
    if payload.dispute_reason not in DISPUTE_REASONS:
        raise HTTPException(400, f"Invalid dispute_reason. Valid: {', '.join(DISPUTE_REASONS)}")

    # Get dispute_reason_id from lookup
    reason_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values
        WHERE UPPER(lookup_code) = UPPER(:code) LIMIT 1
    """), {"code": payload.dispute_reason})
    reason_id = reason_result.scalar()

    # Get currency_id
    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = 'USD' LIMIT 1
    """))
    currency_id = curr_result.scalar()

    # Generate dispute number
    dispute_number = f"DISP-{datetime.utcnow().strftime('%Y%m%d')}-{payload.carrier_invoice_id[:8].upper()}"

    result = await db.execute(text("""
        INSERT INTO tms.disputes
            (dispute_number, related_entity_type, related_entity_id,
             carrier_invoice_id, carrier_invoice_line_id,
             dispute_reason_id, dispute_reason_text,
             disputed_amount, expected_amount, currency_id,
             payment_blocked, opened_at, created_by, notes)
        VALUES
            (:number, 'carrier_invoice', CAST(:inv_id AS uuid),
             CAST(:inv_id AS uuid), CAST(:line_id AS uuid),
             CAST(:reason_id AS uuid), :reason_text,
             :disputed_amount, :expected_amount, CAST(:currency_id AS uuid),
             TRUE, NOW(), :created_by, :notes)
        RETURNING dispute_id, dispute_number
    """), {
        "number":           dispute_number,
        "inv_id":           payload.carrier_invoice_id,
        "line_id":          payload.carrier_invoice_line_id,
        "reason_id":        str(reason_id) if reason_id else None,
        "reason_text":      payload.dispute_reason,
        "disputed_amount":  payload.disputed_amount,
        "expected_amount":  payload.expected_amount,
        "currency_id":      str(currency_id) if currency_id else None,
        "created_by":       user_id,
        "notes":            payload.notes,
    })
    row = dict(result.mappings().one())

    # Update invoice to disputed status (AUDIT-013: block payment)
    await db.execute(text("""
        UPDATE tms.carrier_invoices SET status = 'disputed', updated_at = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": payload.carrier_invoice_id})

    await _audit_history(db, payload.carrier_invoice_id, "disputed", None, "disputed",
                         user_id, f"Dispute {dispute_number}: {payload.dispute_reason}")
    await db.commit()

    return {
        "dispute_id":    str(row["dispute_id"]),
        "dispute_number":row["dispute_number"],
        "payment_blocked":True,
        "reason":        payload.dispute_reason,
        "disputed_amount":payload.disputed_amount,
    }


@router.get("/disputes/{invoice_id}")
async def get_disputes(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT d.*, lv_status.display_name AS status,
               lv_reason.display_name AS reason
        FROM tms.disputes d
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = d.dispute_status_id
        LEFT JOIN tms.lookup_values lv_reason ON lv_reason.lookup_value_id = d.dispute_reason_id
        WHERE d.carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY d.opened_at DESC
    """), {"id": invoice_id})
    return [dict(r) for r in result.mappings().all()]


@router.patch("/disputes/{dispute_id}/respond")
async def carrier_dispute_response(
    dispute_id: str,
    payload: DisputeResponse,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-012: Carrier responds to dispute via portal/email/EDI/API."""
    user_id = user.get("email", "system")

    # Get resolved status id
    res_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values
        WHERE UPPER(lookup_code) = 'RESOLVED' LIMIT 1
    """))
    resolved_id = res_result.scalar()

    await db.execute(text("""
        UPDATE tms.disputes
        SET carrier_response       = :response,
            response_channel       = :channel,
            carrier_responded_at   = NOW(),
            resolved_at            = CASE WHEN :resolution IS NOT NULL THEN NOW() ELSE NULL END,
            resolved_by            = :user,
            dispute_status_id      = CASE WHEN :resolution IS NOT NULL
                                     THEN CAST(:resolved_id AS uuid)
                                     ELSE dispute_status_id END,
            payment_blocked        = CASE WHEN :resolution = 'accepted'
                                     THEN FALSE ELSE payment_blocked END,
            updated_at             = NOW()
        WHERE dispute_id = CAST(:id AS uuid)
    """), {
        "response":    payload.carrier_response,
        "channel":     payload.response_channel,
        "resolution":  payload.resolution_code,
        "user":        user_id,
        "resolved_id": str(resolved_id) if resolved_id else None,
        "id":          dispute_id,
    })
    await db.commit()
    return {"dispute_id": dispute_id, "carrier_response": payload.carrier_response,
            "resolved": payload.resolution_code is not None}


# ── AUDIT-014: Create payable voucher ────────────────────────────

@router.post("/vouchers", status_code=201)
async def create_voucher(
    payload: VoucherCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-014: Create payable voucher from approved invoice lines."""
    user_id = user.get("email", "system")

    # Load invoice
    inv_result = await db.execute(text("""
        SELECT ci.*, c.carrier_id, c.remittance_party_id,
               p.party_name AS carrier_name
        FROM tms.carrier_invoices ci
        JOIN tms.carriers c ON c.carrier_id = ci.carrier_id
        JOIN tms.parties p ON p.party_id = c.party_id
        WHERE ci.carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": payload.carrier_invoice_id})
    inv = inv_result.mappings().one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found.")
    inv = dict(inv)

    # AUDIT-013: Check no active disputes blocking payment
    if not payload.include_disputed:
        blocked_result = await db.execute(text("""
            SELECT COUNT(*) FROM tms.disputes
            WHERE carrier_invoice_id = CAST(:id AS uuid)
              AND payment_blocked = TRUE
              AND resolved_at IS NULL
        """), {"id": payload.carrier_invoice_id})
        blocked = int(blocked_result.scalar() or 0)
        if blocked > 0:
            raise HTTPException(422,
                f"{blocked} unresolved dispute(s) blocking payment. Resolve disputes or use include_disputed=true.")

    # Load approved audit lines to determine payable amount
    approved_result = await db.execute(text("""
        SELECT COALESCE(SUM(far.invoiced_amount), ci.invoice_total_amount) AS payable_amount
        FROM tms.carrier_invoices ci
        LEFT JOIN tms.freight_audit_results far ON far.carrier_invoice_id = ci.carrier_invoice_id
            AND far.disposition = 'approved'
        WHERE ci.carrier_invoice_id = CAST(:id AS uuid)
        GROUP BY ci.invoice_total_amount
    """), {"id": payload.carrier_invoice_id})
    payable_row = approved_result.mappings().one_or_none()
    payable_amount = float(payable_row["payable_amount"]) if payable_row else float(inv["invoice_total_amount"])

    # Get voucher status (pending)
    vstatus_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = 'PENDING' LIMIT 1
    """))
    vstatus_id = vstatus_result.scalar()

    voucher_number = f"VOU-{datetime.utcnow().strftime('%Y%m%d')}-{payload.carrier_invoice_id[:8].upper()}"
    payee_id = str(inv.get("remittance_party_id") or inv.get("carrier_id"))

    vou_result = await db.execute(text("""
        INSERT INTO tms.vouchers
            (voucher_number, carrier_invoice_id, payee_party_id,
             voucher_date, currency_id, voucher_total_amount,
             voucher_status_id, payment_status, created_by)
        VALUES
            (:number, CAST(:inv_id AS uuid), CAST(:payee_id AS uuid),
             CURRENT_DATE, CAST(:currency_id AS uuid), :amount,
             CAST(:status_id AS uuid), 'pending', :created_by)
        RETURNING voucher_id, voucher_number
    """), {
        "number":      voucher_number,
        "inv_id":      payload.carrier_invoice_id,
        "payee_id":    payee_id,
        "currency_id": str(inv["currency_id"]) if inv.get("currency_id") else None,
        "amount":      payable_amount,
        "status_id":   str(vstatus_id) if vstatus_id else None,
        "created_by":  user_id,
    })
    vou = dict(vou_result.mappings().one())
    voucher_id = str(vou["voucher_id"])

    # Create voucher lines from approved audit results
    lines_result = await db.execute(text("""
        SELECT far.carrier_invoice_line_id, far.invoiced_amount
        FROM tms.freight_audit_results far
        WHERE far.carrier_invoice_id = CAST(:id AS uuid)
          AND far.disposition = 'approved'
    """), {"id": payload.carrier_invoice_id})
    lines = [dict(r) for r in lines_result.mappings().all()]

    # If no audit results, create one voucher line for total
    if not lines:
        await db.execute(text("""
            INSERT INTO tms.voucher_lines
                (voucher_id, carrier_invoice_line_id, line_amount)
            VALUES (CAST(:vid AS uuid), NULL, :amount)
        """), {"vid": voucher_id, "amount": payable_amount})
    else:
        for line in lines:
            await db.execute(text("""
                INSERT INTO tms.voucher_lines
                    (voucher_id, carrier_invoice_line_id, line_amount)
                VALUES
                    (CAST(:vid AS uuid), CAST(:line_id AS uuid), :amount)
            """), {
                "vid":     voucher_id,
                "line_id": str(line["carrier_invoice_line_id"]) if line.get("carrier_invoice_line_id") else None,
                "amount":  float(line["invoiced_amount"]),
            })

    # Update invoice status
    await db.execute(text("""
        UPDATE tms.carrier_invoices SET status = 'approved', updated_at = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": payload.carrier_invoice_id})

    await _audit_history(db, payload.carrier_invoice_id, "voucher_created",
                         "approved", "approved", user_id,
                         f"Voucher {voucher_number} created: ${payable_amount:.2f}")
    await db.commit()

    return {
        "voucher_id":     voucher_id,
        "voucher_number": vou["voucher_number"],
        "payable_amount": payable_amount,
        "line_count":     max(len(lines), 1),
        "carrier":        inv.get("carrier_name"),
    }


# ── AUDIT-015: ERP export ─────────────────────────────────────────

@router.post("/vouchers/{voucher_id}/export")
async def export_voucher(
    voucher_id: str,
    target_system: str = "erp",
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-015: Export approved payables to ERP/AP/treasury/payment platforms."""
    vou_result = await db.execute(text("""
        SELECT v.*, ci.carrier_invoice_number, p.party_name AS payee_name,
               p.party_code AS payee_code
        FROM tms.vouchers v
        JOIN tms.carrier_invoices ci ON ci.carrier_invoice_id = v.carrier_invoice_id
        LEFT JOIN tms.parties p ON p.party_id = v.payee_party_id
        WHERE v.voucher_id = CAST(:id AS uuid)
    """), {"id": voucher_id})
    vou = vou_result.mappings().one_or_none()
    if not vou:
        raise HTTPException(404, "Voucher not found.")
    vou = dict(vou)

    # Lines
    lines_result = await db.execute(text("""
        SELECT vl.*, cil.charge_code, cil.description
        FROM tms.voucher_lines vl
        LEFT JOIN tms.carrier_invoice_lines cil ON cil.carrier_invoice_line_id = vl.carrier_invoice_line_id
        WHERE vl.voucher_id = CAST(:id AS uuid)
    """), {"id": voucher_id})
    lines = [dict(r) for r in lines_result.mappings().all()]

    # Mark as exported
    await db.execute(text("""
        UPDATE tms.vouchers
        SET payment_status = 'exported', exported_at = NOW(), updated_at = NOW()
        WHERE voucher_id = CAST(:id AS uuid)
    """), {"id": voucher_id})

    await db.execute(text("""
        UPDATE tms.carrier_invoices SET status = 'exported', exported_at = NOW(), updated_at = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": str(vou["carrier_invoice_id"])})

    await _audit_history(db, str(vou["carrier_invoice_id"]), "exported",
                         "approved", "exported", user.get("email","system"),
                         f"Exported to {target_system}")
    await db.commit()

    return {
        "voucher_id":       voucher_id,
        "voucher_number":   vou.get("voucher_number"),
        "target_system":    target_system,
        "exported_at":      str(datetime.utcnow()),
        "payee":            vou.get("payee_name"),
        "amount":           float(vou.get("voucher_total_amount") or 0),
        "invoice_number":   vou.get("carrier_invoice_number"),
        "lines":            lines,
        "erp_format": {
            "vendor_code":   vou.get("payee_code"),
            "voucher_number":vou.get("voucher_number"),
            "amount":        float(vou.get("voucher_total_amount") or 0),
            "currency":      "USD",
            "invoice_ref":   vou.get("carrier_invoice_number"),
            "lines":         [{"charge": l.get("charge_code"), "amount": float(l.get("line_amount") or 0)} for l in lines],
        },
    }


# ── AUDIT-016/017: Payment status ────────────────────────────────

@router.patch("/vouchers/{voucher_id}/payment")
async def update_payment(
    voucher_id: str,
    payload: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-016/017: Full, partial, short, hold, reversal, failed, confirmed."""
    user_id = user.get("email", "system")
    valid = ["pending","exported","paid","partial_paid","short_pay","held",
             "reversed","failed","confirmed"]
    if payload.payment_status not in valid:
        raise HTTPException(400, f"Invalid payment_status. Valid: {', '.join(valid)}")

    vou_result = await db.execute(text("""
        SELECT carrier_invoice_id FROM tms.vouchers WHERE voucher_id = CAST(:id AS uuid)
    """), {"id": voucher_id})
    vou = vou_result.mappings().one_or_none()
    if not vou:
        raise HTTPException(404, "Voucher not found.")

    pay_date = _date.fromisoformat(payload.payment_date) if payload.payment_date else None

    await db.execute(text("""
        UPDATE tms.vouchers
        SET payment_status    = :status,
            payment_amount    = CAST(:amount AS numeric),
            payment_reference = :ref,
            payment_date      = :pay_date,
            payment_method    = :method,
            erp_voucher_id    = :erp_id,
            updated_at        = NOW()
        WHERE voucher_id = CAST(:id AS uuid)
    """), {
        "status":   payload.payment_status,
        "amount":   payload.payment_amount,
        "ref":      payload.payment_reference,
        "pay_date": pay_date,
        "method":   payload.payment_method,
        "erp_id":   payload.erp_voucher_id,
        "id":       voucher_id,
    })

    # Update invoice status
    inv_status = {
        "paid": "paid", "partial_paid": "partially_paid",
        "confirmed": "paid", "failed": "approved",
    }.get(payload.payment_status)
    if inv_status:
        await db.execute(text("""
            UPDATE tms.carrier_invoices SET status = :status, updated_at = NOW()
            WHERE carrier_invoice_id = CAST(:id AS uuid)
        """), {"status": inv_status, "id": str(vou["carrier_invoice_id"])})

    await _audit_history(db, str(vou["carrier_invoice_id"]),
                         "payment_received", None, payload.payment_status,
                         user_id, payload.notes or f"Payment {payload.payment_status}")
    await db.commit()

    return {"voucher_id": voucher_id, "payment_status": payload.payment_status,
            "payment_amount": payload.payment_amount}


# ── AUDIT-018: Remittance advice ──────────────────────────────────

@router.get("/vouchers/{voucher_id}/remittance")
async def get_remittance(
    voucher_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-018: Generate remittance advice and carrier payment status."""
    vou_result = await db.execute(text("""
        SELECT v.*, ci.carrier_invoice_number, ci.invoice_date,
               p.party_name AS payee_name, p.party_code AS payee_code
        FROM tms.vouchers v
        JOIN tms.carrier_invoices ci ON ci.carrier_invoice_id = v.carrier_invoice_id
        LEFT JOIN tms.parties p ON p.party_id = v.payee_party_id
        WHERE v.voucher_id = CAST(:id AS uuid)
    """), {"id": voucher_id})
    vou = vou_result.mappings().one_or_none()
    if not vou:
        raise HTTPException(404, "Voucher not found.")
    vou = dict(vou)

    lines_result = await db.execute(text("""
        SELECT vl.*, cil.charge_code, cil.description
        FROM tms.voucher_lines vl
        LEFT JOIN tms.carrier_invoice_lines cil ON cil.carrier_invoice_line_id = vl.carrier_invoice_line_id
        WHERE vl.voucher_id = CAST(:id AS uuid)
    """), {"id": voucher_id})
    lines = [dict(r) for r in lines_result.mappings().all()]

    return {
        "remittance_advice": {
            "voucher_number":   vou.get("voucher_number"),
            "payee":            vou.get("payee_name"),
            "payee_code":       vou.get("payee_code"),
            "invoice_number":   vou.get("carrier_invoice_number"),
            "invoice_date":     str(vou.get("invoice_date") or ""),
            "voucher_date":     str(vou.get("voucher_date") or ""),
            "amount":           float(vou.get("voucher_total_amount") or 0),
            "payment_amount":   float(vou.get("payment_amount") or 0),
            "payment_status":   vou.get("payment_status"),
            "payment_date":     str(vou.get("payment_date") or ""),
            "payment_method":   vou.get("payment_method"),
            "payment_reference":vou.get("payment_reference"),
            "erp_voucher_id":   vou.get("erp_voucher_id"),
        },
        "line_details": lines,
        "generated_at":  str(datetime.utcnow()),
    }


# ── AUDIT-019: Audit history ──────────────────────────────────────

@router.get("/history/{invoice_id}")
async def get_audit_history(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """AUDIT-019: Full audit history across all lifecycle events."""
    result = await db.execute(text("""
        SELECT * FROM tms.audit_history
        WHERE carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY performed_at ASC
    """), {"id": invoice_id})
    events = [dict(r) for r in result.mappings().all()]
    return {"invoice_id": invoice_id, "event_count": len(events), "events": events}


# ── AUDIT-004: Tolerance CRUD ─────────────────────────────────────

@router.get("/tolerances")
async def list_tolerances(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT t.*, p.party_name AS carrier_name FROM tms.audit_tolerances t
        LEFT JOIN tms.carriers c ON c.carrier_id = t.carrier_id
        LEFT JOIN tms.parties p ON p.party_id = c.party_id
        WHERE t.is_active = TRUE ORDER BY t.variance_pct
    """))
    return [dict(r) for r in result.mappings().all()]


@router.post("/tolerances", status_code=201)
async def create_tolerance(
    payload: ToleranceCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.audit_tolerances
            (tolerance_name, carrier_id, transport_mode, charge_code,
             variance_pct, variance_amount, use_pct, auto_approve)
        VALUES
            (:tolerance_name, CAST(:carrier_id AS uuid), :transport_mode,
             :charge_code, :variance_pct, :variance_amount, :use_pct, :auto_approve)
        RETURNING tolerance_id
    """), payload.model_dump())
    await db.commit()
    return {"tolerance_id": str(result.scalar()), **payload.model_dump()}


# ── AUDIT-020: Reports ────────────────────────────────────────────

@router.get("/reports/summary")
async def audit_reports(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """AUDIT-020: Invoice aging, dispute aging, audit variance, payment status reports."""
    params: dict[str, Any] = {}

    # Aging
    aging_result = await db.execute(text("""
        SELECT
            CASE
                WHEN due_date IS NULL THEN 'no_due_date'
                WHEN CURRENT_DATE <= due_date THEN 'current'
                WHEN (CURRENT_DATE - due_date) <= 30 THEN '1_30_days'
                WHEN (CURRENT_DATE - due_date) <= 60 THEN '31_60_days'
                ELSE 'over_60_days'
            END AS bucket,
            COUNT(*) AS count,
            SUM(invoice_total_amount) AS total
        FROM tms.carrier_invoices
        WHERE status NOT IN ('paid','closed','canceled','reversed')
        GROUP BY bucket ORDER BY bucket
    """))
    aging = {r["bucket"]: {"count": int(r["count"]), "total": float(r["total"])}
             for r in aging_result.mappings().all()}

    # Dispute aging
    disp_result = await db.execute(text("""
        SELECT COUNT(*) AS open_disputes,
               SUM(disputed_amount) AS total_disputed
        FROM tms.disputes WHERE resolved_at IS NULL
    """))
    disp = dict(disp_result.mappings().one())

    # Variance summary
    var_result = await db.execute(text("""
        SELECT exception_type, COUNT(*) AS count, SUM(variance_amount) AS total_variance
        FROM tms.freight_audit_results
        WHERE exception_type IS NOT NULL AND disposition = 'pending'
        GROUP BY exception_type ORDER BY total_variance DESC
    """))
    variance = {r["exception_type"]: {"count": int(r["count"]),
                "total": float(r["total_variance"] or 0)} for r in var_result.mappings().all()}

    # Payment status
    pay_result = await db.execute(text("""
        SELECT payment_status, COUNT(*) AS count, SUM(voucher_total_amount) AS total
        FROM tms.vouchers GROUP BY payment_status ORDER BY payment_status
    """))
    payment = {r["payment_status"]: {"count": int(r["count"]), "total": float(r["total"] or 0)}
               for r in pay_result.mappings().all()}

    return {
        "invoice_aging":   aging,
        "dispute_summary": {
            "open_disputes":   int(disp.get("open_disputes") or 0),
            "total_disputed":  float(disp.get("total_disputed") or 0),
        },
        "variance_by_type": variance,
        "payment_status":   payment,
    }


# ── Helper ────────────────────────────────────────────────────────

async def _save_audit_result(db, data: dict) -> str:
    r = await db.execute(text("""
        INSERT INTO tms.freight_audit_results
            (carrier_invoice_id, carrier_invoice_line_id,
             expected_amount, invoiced_amount, variance_amount,
             tolerance_amount, tolerance_percent,
             exception_type, disposition, audit_type,
             shipment_id, charge_code, audit_rule_name)
        VALUES
            (CAST(:carrier_invoice_id AS uuid), CAST(:carrier_invoice_line_id AS uuid),
             CAST(:expected_amount AS numeric), CAST(:invoiced_amount AS numeric),
             CAST(:variance_amount AS numeric),
             CAST(:tolerance_amount AS numeric), CAST(:tolerance_percent AS numeric),
             :exception_type, :disposition, :audit_type,
             CAST(:shipment_id AS uuid), :charge_code, :audit_rule_name)
        RETURNING freight_audit_result_id
    """), data)
    return str(r.scalar())


async def _audit_history(db, invoice_id: str, event_type: str,
                          from_status, to_status, performed_by: str, notes: str = None):
    try:
        await db.execute(text("""
            INSERT INTO tms.audit_history
                (carrier_invoice_id, event_type, from_status, to_status, performed_by, notes)
            VALUES
                (CAST(:id AS uuid), :event_type, :from_status, :to_status, :performed_by, :notes)
        """), {
            "id": invoice_id, "event_type": event_type,
            "from_status": from_status, "to_status": to_status,
            "performed_by": performed_by, "notes": notes,
        })
    except Exception:
        pass
