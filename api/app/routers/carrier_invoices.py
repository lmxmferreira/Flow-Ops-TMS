"""
routers/carrier_invoices.py
TMS-CINV-001 through TMS-CINV-015: Carrier Invoice Management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import date as _date_type, datetime
import json as _json

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    carrier_id: str
    carrier_invoice_number: str
    invoice_date: str
    due_date: Optional[str] = None
    invoice_total_amount: float
    tax_total_amount: float = 0.0
    currency: str = "USD"
    invoice_type: str = "standard"
    source_channel: str = "manual"
    shipment_id: Optional[str] = None
    notes: Optional[str] = None

class InvoiceLine(BaseModel):
    shipment_id: Optional[str] = None
    charge_code: Optional[str] = None
    description: str
    quantity: float = 1.0
    rate_amount: float
    line_amount: float
    tax_amount: float = 0.0

class InvoiceCreateWithLines(InvoiceCreate):
    lines: list[InvoiceLine] = []

class InvoiceStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    payment_reference: Optional[str] = None
    paid_amount: Optional[float] = None

class HoldRequest(BaseModel):
    on_hold: bool
    reason: Optional[str] = None

class DisputeRequest(BaseModel):
    reason: str
    disputed_amount: Optional[float] = None
    line_ids: Optional[list[str]] = None

class MatchRequest(BaseModel):
    shipment_id: str
    auto_match_lines: bool = True
    tolerance_pct: float = 5.0


# ── CINV-001/002/003: Invoice creation ───────────────────────────

@router.post("/", status_code=201)
async def create_invoice(
    payload: InvoiceCreateWithLines,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CINV-001/002/003: Create a carrier invoice with header and line details.
    Supports manual entry, all source channels, and multiple invoice types.
    """
    user_id = user.get("email", "system")

    # CINV-007: Duplicate detection
    dup_result = await db.execute(text("""
        SELECT carrier_invoice_id, carrier_invoice_number
        FROM tms.carrier_invoices
        WHERE carrier_id = CAST(:carrier_id AS uuid)
          AND carrier_invoice_number = :inv_number
          AND status NOT IN ('canceled','reversed')
        LIMIT 1
    """), {"carrier_id": payload.carrier_id, "inv_number": payload.carrier_invoice_number})
    dup = dup_result.mappings().one_or_none()
    if dup:
        raise HTTPException(409, f"Duplicate invoice detected: {payload.carrier_invoice_number} already exists (ID: {dup['carrier_invoice_id']})")

    # Get currency lookup id
    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :code LIMIT 1
    """), {"code": payload.currency})
    currency_id = curr_result.scalar()

    inv_date = _date_type.fromisoformat(payload.invoice_date)
    due_date = _date_type.fromisoformat(payload.due_date) if payload.due_date else None

    # Insert header
    inv_result = await db.execute(text("""
        INSERT INTO tms.carrier_invoices
            (carrier_id, carrier_invoice_number, invoice_date, due_date,
             currency_id, invoice_total_amount, tax_total_amount,
             invoice_type, source_channel, shipment_id, status, notes, created_by)
        VALUES
            (CAST(:carrier_id AS uuid), :inv_number, :inv_date, :due_date,
             CAST(:currency_id AS uuid), :total, :tax,
             :inv_type, :source, CAST(:shipment_id AS uuid),
             'received', :notes, :created_by)
        RETURNING carrier_invoice_id, carrier_invoice_number, status
    """), {
        "carrier_id":  payload.carrier_id,
        "inv_number":  payload.carrier_invoice_number,
        "inv_date":    inv_date,
        "due_date":    due_date,
        "currency_id": str(currency_id) if currency_id else None,
        "total":       payload.invoice_total_amount,
        "tax":         payload.tax_total_amount,
        "inv_type":    payload.invoice_type,
        "source":      payload.source_channel,
        "shipment_id": payload.shipment_id,
        "notes":       payload.notes,
        "created_by":  user_id,
    })
    inv = dict(inv_result.mappings().one())
    invoice_id = str(inv["carrier_invoice_id"])

    # Insert lines (CINV-004)
    line_ids = []
    for i, line in enumerate(payload.lines, 1):
        line_result = await db.execute(text("""
            INSERT INTO tms.carrier_invoice_lines
                (carrier_invoice_id, line_number, shipment_id,
                 charge_code, description, quantity, rate_amount, line_amount, tax_amount)
            VALUES
                (CAST(:invoice_id AS uuid), CAST(:line_num AS text), CAST(:shipment_id AS uuid),
                 :charge_code, :description, :quantity, :rate, :amount, :tax)
            RETURNING carrier_invoice_line_id
        """), {
            "invoice_id":  invoice_id,
            "line_num":    str(i),
            "shipment_id": line.shipment_id or payload.shipment_id,
            "charge_code": line.charge_code,
            "description": line.description,
            "quantity":    line.quantity,
            "rate":        line.rate_amount,
            "amount":      line.line_amount,
            "tax":         line.tax_amount,
        })
        line_ids.append(str(line_result.scalar()))

    # Audit log
    await _audit(db, invoice_id, "created", None, "received", user_id,
                 f"Invoice {payload.carrier_invoice_number} created via {payload.source_channel}")
    await db.commit()

    # Add to reference index
    try:
        await db.execute(text("""
            INSERT INTO tms.reference_index (ref_number, ref_type, entity_type, entity_id)
            VALUES (:ref, 'invoice_number', 'carrier_invoice', CAST(:id AS uuid))
            ON CONFLICT DO NOTHING
        """), {"ref": payload.carrier_invoice_number, "id": invoice_id})
        await db.commit()
    except Exception:
        pass

    return {
        "carrier_invoice_id":    invoice_id,
        "carrier_invoice_number":inv["carrier_invoice_number"],
        "status":                inv["status"],
        "line_count":            len(line_ids),
        "line_ids":              line_ids,
    }


# ── CINV-003: Invoice header detail ──────────────────────────────

@router.get("/")
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    shipment_id: Optional[str] = Query(None),
    on_hold: Optional[bool] = Query(None),
    overdue_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    """CINV-010/015: List invoices with aging and status filtering."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if carrier_id:
        conditions.append("ci.carrier_id = CAST(:carrier_id AS uuid)")
        params["carrier_id"] = carrier_id
    if status:
        conditions.append("ci.status = :status")
        params["status"] = status
    if shipment_id:
        conditions.append("ci.shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id
    if on_hold is not None:
        conditions.append("ci.on_hold = :on_hold")
        params["on_hold"] = on_hold
    if overdue_only:
        conditions.append("ci.due_date < CURRENT_DATE AND ci.status NOT IN ('paid','closed','canceled','reversed')")

    result = await db.execute(text(f"""
        SELECT ci.*,
               p.party_name AS carrier_name, c.scac,
               -- CINV-015: Aging
               CASE
                   WHEN ci.due_date IS NULL THEN NULL
                   WHEN ci.status IN ('paid','closed','canceled') THEN 0
                   ELSE (CURRENT_DATE - ci.due_date)
               END AS days_overdue,
               COUNT(cil.carrier_invoice_line_id) AS line_count
        FROM tms.carrier_invoices ci
        JOIN tms.carriers c  ON c.carrier_id  = ci.carrier_id
        JOIN tms.parties p   ON p.party_id    = c.party_id
        LEFT JOIN tms.carrier_invoice_lines cil ON cil.carrier_invoice_id = ci.carrier_invoice_id
        WHERE {' AND '.join(conditions)}
        GROUP BY ci.carrier_invoice_id, p.party_name, c.scac
        ORDER BY ci.invoice_date DESC, ci.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CINV-003/004/013: Full invoice detail with lines and audit trail."""
    result = await db.execute(text("""
        SELECT ci.*, p.party_name AS carrier_name, c.scac,
               (CURRENT_DATE - ci.due_date) AS days_overdue
        FROM tms.carrier_invoices ci
        JOIN tms.carriers c ON c.carrier_id = ci.carrier_id
        JOIN tms.parties  p ON p.party_id   = c.party_id
        WHERE ci.carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    inv = result.mappings().one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found.")
    inv = dict(inv)

    # Lines (CINV-004)
    lines_result = await db.execute(text("""
        SELECT cil.*, sc.charge_code AS matched_charge_code,
               sc.amount AS estimated_amount
        FROM tms.carrier_invoice_lines cil
        LEFT JOIN tms.shipment_costs sc ON sc.cost_id = cil.matched_cost_id
        WHERE cil.carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY cil.line_number
    """), {"id": invoice_id})
    inv["lines"] = [dict(r) for r in lines_result.mappings().all()]

    # Audit trail (CINV-013)
    audit_result = await db.execute(text("""
        SELECT * FROM tms.carrier_invoice_audit
        WHERE carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY performed_at DESC
    """), {"id": invoice_id})
    inv["audit_trail"] = [dict(r) for r in audit_result.mappings().all()]

    # Documents (CINV-009)
    doc_result = await db.execute(text("""
        SELECT d.document_id, d.document_number, d.document_name,
               dt.type_code, dt.type_name, d.status
        FROM tms.document_links dl
        JOIN tms.documents d ON d.document_id = dl.document_id
        LEFT JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE dl.related_entity_type = 'carrier_invoice'
          AND dl.related_entity_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    inv["documents"] = [dict(r) for r in doc_result.mappings().all()]

    return inv


# ── CINV-005: Invoice matching ────────────────────────────────────

@router.post("/{invoice_id}/match")
async def match_invoice(
    invoice_id: str,
    payload: MatchRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CINV-005: Match carrier invoice against shipment costs.
    Compares invoice lines against estimated costs and flags variances.
    """
    user_id = user.get("email", "system")

    # Load invoice
    inv_result = await db.execute(text("""
        SELECT * FROM tms.carrier_invoices WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    inv = inv_result.mappings().one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found.")
    inv = dict(inv)

    # Load shipment costs
    costs_result = await db.execute(text("""
        SELECT * FROM tms.shipment_costs WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": payload.shipment_id})
    costs = [dict(r) for r in costs_result.mappings().all()]
    total_estimated = sum(float(c["amount"]) for c in costs)

    # Load invoice lines
    lines_result = await db.execute(text("""
        SELECT * FROM tms.carrier_invoice_lines WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    lines = [dict(r) for r in lines_result.mappings().all()]
    total_invoiced = float(inv.get("invoice_total_amount") or 0)

    # Calculate variance
    variance = total_invoiced - total_estimated
    variance_pct = abs(variance / total_estimated * 100) if total_estimated > 0 else 0

    # Determine match status
    if variance_pct <= payload.tolerance_pct:
        new_status = "matched"
        match_result = "matched"
    else:
        new_status = "exception"
        match_result = "variance_exceeded"

    # Auto-match lines if requested
    if payload.auto_match_lines:
        costs_by_code = {c["charge_code"]: c for c in costs}
        for line in lines:
            charge_code = line.get("charge_code")
            matched_cost = costs_by_code.get(charge_code)
            if matched_cost:
                line_var = float(line["line_amount"]) - float(matched_cost["amount"])
                await db.execute(text("""
                    UPDATE tms.carrier_invoice_lines
                    SET matched_cost_id  = CAST(:cost_id AS uuid),
                        match_status     = :status,
                        variance_amount  = :variance
                    WHERE carrier_invoice_line_id = CAST(:line_id AS uuid)
                """), {
                    "cost_id":  str(matched_cost["cost_id"]),
                    "status":   "matched" if float(matched_cost["amount"]) == 0 or abs(line_var) / float(matched_cost["amount"]) * 100 <= payload.tolerance_pct else "variance",
                    "variance": line_var,
                    "line_id":  str(line["carrier_invoice_line_id"]),
                })

    # Update invoice status and variance
    await db.execute(text("""
        UPDATE tms.carrier_invoices
        SET status          = :status,
            shipment_id     = CAST(:shipment_id AS uuid),
            matched_amount  = :matched,
            variance_amount = :variance,
            variance_pct    = :variance_pct,
            updated_at      = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {
        "status":      new_status,
        "shipment_id": payload.shipment_id,
        "matched":     total_estimated,
        "variance":    variance,
        "variance_pct":variance_pct,
        "id":          invoice_id,
    })

    await _audit(db, invoice_id, "matched", inv.get("status"), new_status, user_id,
                 f"Matched against shipment. Variance: ${variance:.2f} ({variance_pct:.1f}%)")
    await db.commit()

    return {
        "invoice_id":      invoice_id,
        "match_result":    match_result,
        "new_status":      new_status,
        "total_invoiced":  total_invoiced,
        "total_estimated": total_estimated,
        "variance":        round(variance, 2),
        "variance_pct":    round(variance_pct, 2),
        "tolerance_pct":   payload.tolerance_pct,
        "within_tolerance":variance_pct <= payload.tolerance_pct,
    }


# ── CINV-010/012: Status management ──────────────────────────────

@router.patch("/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: str,
    payload: InvoiceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CINV-010/012: Update invoice status with full audit trail."""
    user_id = user.get("email", "system")
    valid_statuses = [
        'received','pending_validation','matched','exception','disputed',
        'approved','rejected','exported','paid','partially_paid',
        'canceled','reversed','closed'
    ]
    if payload.status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Valid: {', '.join(valid_statuses)}")

    # Load current
    curr_result = await db.execute(text("""
        SELECT status, invoice_total_amount FROM tms.carrier_invoices
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    curr = curr_result.mappings().one_or_none()
    if not curr:
        raise HTTPException(404, "Invoice not found.")

    update_params: dict[str, Any] = {
        "status": payload.status, "id": invoice_id,
        "approved_by": None, "approved_at": None,
        "exported_at": None, "paid_amount": None,
        "paid_at": None, "payment_ref": None, "closed_at": None,
    }
    if payload.status == "approved":
        update_params.update({"approved_by": user_id, "approved_at": datetime.utcnow()})
    elif payload.status == "exported":
        update_params["exported_at"] = datetime.utcnow()
    elif payload.status in ("paid", "partially_paid"):
        update_params.update({
            "paid_amount": payload.paid_amount or float(curr["invoice_total_amount"]),
            "paid_at": datetime.utcnow(),
            "payment_ref": payload.payment_reference,
        })
    elif payload.status == "closed":
        update_params["closed_at"] = datetime.utcnow()

    await db.execute(text("""
        UPDATE tms.carrier_invoices
        SET status            = :status,
            approved_by       = :approved_by,
            approved_at       = :approved_at,
            exported_at       = :exported_at,
            paid_amount       = CAST(:paid_amount AS numeric),
            paid_at           = :paid_at,
            payment_reference = :payment_ref,
            closed_at         = :closed_at,
            updated_at        = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), update_params)

    await _audit(db, invoice_id, "status_changed", curr["status"], payload.status,
                 user_id, payload.notes)
    await db.commit()

    return {
        "carrier_invoice_id": invoice_id,
        "from_status": curr["status"],
        "to_status":   payload.status,
        "updated_by":  user_id,
    }


# ── CINV-011: Hold management ─────────────────────────────────────

@router.patch("/{invoice_id}/hold")
async def set_invoice_hold(
    invoice_id: str,
    payload: HoldRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CINV-011: Place or release a hold on a carrier invoice."""
    user_id = user.get("email", "system")
    await db.execute(text("""
        UPDATE tms.carrier_invoices
        SET on_hold     = :on_hold,
            hold_reason = :reason,
            held_by     = :held_by,
            held_at     = CASE WHEN :on_hold THEN NOW() ELSE NULL END,
            updated_at  = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {
        "on_hold": payload.on_hold,
        "reason":  payload.reason,
        "held_by": user_id if payload.on_hold else None,
        "id":      invoice_id,
    })
    await _audit(db, invoice_id, "hold", None, None, user_id,
                 f"Hold {'placed' if payload.on_hold else 'released'}: {payload.reason or ''}")
    await db.commit()
    return {"carrier_invoice_id": invoice_id, "on_hold": payload.on_hold,
            "held_by": user_id if payload.on_hold else None}


@router.patch("/lines/{line_id}/hold")
async def set_line_hold(
    line_id: str,
    payload: HoldRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CINV-011: Hold a specific invoice line."""
    await db.execute(text("""
        UPDATE tms.carrier_invoice_lines
        SET on_hold = :on_hold, hold_reason = :reason
        WHERE carrier_invoice_line_id = CAST(:id AS uuid)
    """), {"on_hold": payload.on_hold, "reason": payload.reason, "id": line_id})
    await db.commit()
    return {"line_id": line_id, "on_hold": payload.on_hold}


# ── CINV-008: Credit/debit memos, reversals ───────────────────────

@router.post("/{invoice_id}/reverse", status_code=201)
async def reverse_invoice(
    invoice_id: str,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CINV-008: Create a reversal/credit memo for an existing invoice."""
    user_id = user.get("email", "system")
    orig_result = await db.execute(text("""
        SELECT * FROM tms.carrier_invoices WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    orig = orig_result.mappings().one_or_none()
    if not orig:
        raise HTTPException(404, "Invoice not found.")
    orig = dict(orig)

    # Create reversal invoice
    rev_number = f"REV-{orig['carrier_invoice_number']}"
    rev_result = await db.execute(text("""
        INSERT INTO tms.carrier_invoices
            (carrier_id, carrier_invoice_number, invoice_date, due_date,
             currency_id, invoice_total_amount, tax_total_amount,
             invoice_type, source_channel, shipment_id, status,
             parent_invoice_id, notes, created_by)
        VALUES
            (CAST(:carrier_id AS uuid), :rev_number, CURRENT_DATE, CURRENT_DATE,
             CAST(:currency_id AS uuid), :neg_total, :neg_tax,
             'reversal', 'manual', CAST(:shipment_id AS uuid), 'received',
             CAST(:parent_id AS uuid), :notes, :created_by)
        RETURNING carrier_invoice_id
    """), {
        "carrier_id": str(orig["carrier_id"]),
        "rev_number": rev_number,
        "currency_id": str(orig["currency_id"]) if orig.get("currency_id") else None,
        "neg_total":  -float(orig["invoice_total_amount"]),
        "neg_tax":    -float(orig.get("tax_total_amount") or 0),
        "shipment_id": str(orig["shipment_id"]) if orig.get("shipment_id") else None,
        "parent_id":  invoice_id,
        "notes":      notes or f"Reversal of {orig['carrier_invoice_number']}",
        "created_by": user_id,
    })
    rev_id = str(rev_result.scalar())

    # Mark original as reversed
    await db.execute(text("""
        UPDATE tms.carrier_invoices SET status = 'reversed', updated_at = NOW()
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})

    await _audit(db, invoice_id, "status_changed", orig["status"], "reversed", user_id, f"Reversed: {rev_id}")
    await db.commit()
    return {"reversal_invoice_id": rev_id, "reversal_number": rev_number,
            "original_id": invoice_id, "amount": -float(orig["invoice_total_amount"])}


# ── CINV-007: Duplicate check ─────────────────────────────────────

@router.post("/check-duplicate")
async def check_duplicate(
    carrier_id: str,
    invoice_number: str,
    invoice_date: Optional[str] = None,
    total_amount: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """CINV-007: Check if an invoice is a duplicate before creating."""
    conditions = [
        "carrier_id = CAST(:carrier_id AS uuid)",
        "carrier_invoice_number = :inv_number",
        "status NOT IN ('canceled','reversed')"
    ]
    params: dict[str, Any] = {"carrier_id": carrier_id, "inv_number": invoice_number}

    result = await db.execute(text(f"""
        SELECT carrier_invoice_id, carrier_invoice_number, invoice_date,
               invoice_total_amount, status
        FROM tms.carrier_invoices
        WHERE {' AND '.join(conditions)}
    """), params)
    exact_matches = [dict(r) for r in result.mappings().all()]

    return {
        "is_duplicate":   len(exact_matches) > 0,
        "exact_matches":  exact_matches,
        "match_count":    len(exact_matches),
    }


# ── CINV-015: Aging report ────────────────────────────────────────

@router.get("/reports/aging")
async def invoice_aging_report(
    db: AsyncSession = Depends(get_db),
    carrier_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """CINV-015: Invoice aging and payment due-date report."""
    conditions = ["ci.status NOT IN ('paid','closed','canceled','reversed')"]
    params: dict[str, Any] = {}
    if carrier_id:
        conditions.append("ci.carrier_id = CAST(:carrier_id AS uuid)")
        params["carrier_id"] = carrier_id

    result = await db.execute(text(f"""
        SELECT
            p.party_name AS carrier_name, c.scac,
            ci.carrier_invoice_number, ci.invoice_date, ci.due_date,
            ci.invoice_total_amount, ci.status, ci.on_hold,
            (CURRENT_DATE - ci.due_date) AS days_overdue,
            CASE
                WHEN ci.due_date IS NULL THEN 'no_due_date'
                WHEN CURRENT_DATE <= ci.due_date THEN 'current'
                WHEN (CURRENT_DATE - ci.due_date) <= 30 THEN '1_30_days'
                WHEN (CURRENT_DATE - ci.due_date) <= 60 THEN '31_60_days'
                WHEN (CURRENT_DATE - ci.due_date) <= 90 THEN '61_90_days'
                ELSE 'over_90_days'
            END AS aging_bucket
        FROM tms.carrier_invoices ci
        JOIN tms.carriers c ON c.carrier_id = ci.carrier_id
        JOIN tms.parties  p ON p.party_id   = c.party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY ci.due_date NULLS LAST
    """), params)
    rows = [dict(r) for r in result.mappings().all()]

    # Summarize by bucket
    buckets: dict[str, dict] = {}
    for r in rows:
        b = r["aging_bucket"]
        if b not in buckets:
            buckets[b] = {"count": 0, "total": 0}
        buckets[b]["count"] += 1
        buckets[b]["total"] += float(r["invoice_total_amount"] or 0)

    total_outstanding = sum(float(r["invoice_total_amount"] or 0) for r in rows)

    return {
        "total_outstanding": round(total_outstanding, 2),
        "invoice_count":     len(rows),
        "aging_summary":     buckets,
        "invoices":          rows,
    }


# ── CINV-013: Audit trail ─────────────────────────────────────────

@router.get("/{invoice_id}/audit")
async def get_invoice_audit(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.carrier_invoice_audit
        WHERE carrier_invoice_id = CAST(:id AS uuid)
        ORDER BY performed_at DESC
    """), {"id": invoice_id})
    return [dict(r) for r in result.mappings().all()]


# ── Helper ────────────────────────────────────────────────────────

async def _audit(db, invoice_id: str, event_type: str, from_status, to_status,
                  performed_by: str, notes: str = None):
    try:
        await db.execute(text("""
            INSERT INTO tms.carrier_invoice_audit
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
