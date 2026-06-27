"""
routers/billing.py
TMS-BILL-001 through TMS-BILL-020: Client Billing & Receivables
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, date as _date, timedelta
import json as _json

router = APIRouter()

BILL_STATUSES = [
    'draft','pending_approval','approved','sent','disputed',
    'partially_paid','paid','canceled','credited','rebilled','closed'
]


# ── Pydantic Models ───────────────────────────────────────────────

class BillCreate(BaseModel):
    customer_party_id: str
    bill_level: str = "shipment"
    shipment_ids: Optional[list[str]] = None
    po_ids: Optional[list[str]] = None
    billing_period_start: Optional[str] = None
    billing_period_end: Optional[str] = None
    bill_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: str = "USD"
    notes: Optional[str] = None
    apply_billing_rules: bool = True

class BillLineAdd(BaseModel):
    shipment_id: Optional[str] = None
    order_release_id: Optional[str] = None
    purchase_order_id: Optional[str] = None
    purchase_order_line_id: Optional[str] = None
    charge_code: str
    description: str
    quantity: float = 1.0
    rate_amount: float
    cost_amount: Optional[float] = None
    markup_pct: Optional[float] = None
    tax_amount: float = 0.0
    is_taxable: bool = False
    notes: Optional[str] = None

class BillStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    sent_channel: Optional[str] = None

class HoldUpdate(BaseModel):
    on_hold: bool
    hold_reason: Optional[str] = None

class AdjustmentCreate(BaseModel):
    adjustment_type: str  # credit | debit | rebill | correction | write_off
    amount: float
    reason: str
    notes: Optional[str] = None

class PaymentReceive(BaseModel):
    received_amount: float
    payment_reference: Optional[str] = None
    received_date: Optional[str] = None
    payment_status: str = "paid"
    erp_payment_id: Optional[str] = None
    notes: Optional[str] = None

class BillingRuleCreate(BaseModel):
    customer_party_id: Optional[str] = None
    rule_name: str
    rule_type: str
    # pass_through | markup | margin | fixed_fee | management_fee | discount
    applies_to_modes: Optional[list[str]] = None
    applies_to_charges: Optional[list[str]] = None
    rule_params: dict = {}
    priority: int = 0
    effective_date: Optional[str] = None

class BillingDisputeCreate(BaseModel):
    dispute_reason: str
    disputed_amount: float
    notes: Optional[str] = None

class BillExportRequest(BaseModel):
    target_system: str = "erp"
    format: str = "standard"
    include_supporting_docs: bool = False


# ── BILL-001/002/003/004: Create client bill ──────────────────────

@router.post("/", status_code=201)
async def create_bill(
    payload: BillCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    BILL-001/002/003/004: Create client bill from shipments, POs, or billing events.
    Supports all billing levels: shipment, order, PO, customer, cycle.
    """
    user_id = user.get("email", "system")

    bill_date = _date.fromisoformat(payload.bill_date) if payload.bill_date else _date.today()
    due_date = _date.fromisoformat(payload.due_date) if payload.due_date else bill_date + timedelta(days=30)
    period_start = _date.fromisoformat(payload.billing_period_start) if payload.billing_period_start else bill_date
    period_end = _date.fromisoformat(payload.billing_period_end) if payload.billing_period_end else bill_date

    # Get currency lookup id
    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :code LIMIT 1
    """), {"code": payload.currency})
    currency_id = curr_result.scalar()

    # Generate bill number
    bill_number = f"BILL-{datetime.utcnow().strftime('%Y%m%d')}-{payload.customer_party_id[:8].upper()}"

    # BILL-010: Duplicate check
    dup_result = await db.execute(text("""
        SELECT COUNT(*) FROM tms.client_bills
        WHERE customer_party_id = CAST(:cust_id AS uuid)
          AND status NOT IN ('canceled','credited')
          AND billing_period_start = :period_start
          AND billing_period_end   = :period_end
          AND bill_level           = :bill_level
    """), {
        "cust_id":     payload.customer_party_id,
        "period_start":period_start,
        "period_end":  period_end,
        "bill_level":  payload.bill_level,
    })
    if int(dup_result.scalar() or 0) > 0:
        raise HTTPException(409, "Potential duplicate bill detected for this customer/period/level.")

    bill_result = await db.execute(text("""
        INSERT INTO tms.client_bills
            (client_bill_number, customer_party_id, bill_level,
             bill_date, due_date, billing_period_start, billing_period_end,
             currency_id, total_bill_amount, total_tax_amount,
             status, payment_status, notes, created_by)
        VALUES
            (:bill_number, CAST(:customer_id AS uuid), :bill_level,
             :bill_date, :due_date, :period_start, :period_end,
             CAST(:currency_id AS uuid), 0, 0,
             'draft', 'unpaid', :notes, :created_by)
        RETURNING client_bill_id, client_bill_number
    """), {
        "bill_number": bill_number,
        "customer_id": payload.customer_party_id,
        "bill_level":  payload.bill_level,
        "bill_date":   bill_date,
        "due_date":    due_date,
        "period_start":period_start,
        "period_end":  period_end,
        "currency_id": str(currency_id) if currency_id else None,
        "notes":       payload.notes,
        "created_by":  user_id,
    })
    bill = dict(bill_result.mappings().one())
    bill_id = str(bill["client_bill_id"])

    # Auto-generate lines from shipments (BILL-005/006)
    total_amount = 0.0
    total_tax = 0.0
    line_count = 0

    if payload.shipment_ids:
        for shp_id in payload.shipment_ids:
            # BILL-009: Validate billing eligibility
            validation = await _validate_billing_eligibility(db, shp_id)
            if not validation["eligible"]:
                # Place on hold (BILL-008)
                await db.execute(text("""
                    UPDATE tms.client_bills SET on_hold = TRUE,
                        hold_reason = :reason WHERE client_bill_id = CAST(:id AS uuid)
                """), {"reason": "; ".join(validation["issues"]), "id": bill_id})
                continue

            # Load client charges for this shipment (from rating module)
            charges_result = await db.execute(text("""
                SELECT cc.*, sc.amount AS carrier_cost
                FROM tms.client_charges cc
                LEFT JOIN tms.shipment_costs sc ON sc.cost_id = cc.carrier_cost_id
                WHERE cc.shipment_id = CAST(:id AS uuid) AND cc.billed_flag = FALSE
            """), {"id": shp_id})
            charges = [dict(r) for r in charges_result.mappings().all()]

            # Apply billing rules if requested (BILL-006)
            if payload.apply_billing_rules:
                billing_rules = await _get_billing_rules(db, payload.customer_party_id)
            else:
                billing_rules = []

            for i, charge in enumerate(charges, 1):
                line_amount = float(charge.get("amount") or 0)
                carrier_cost = float(charge.get("carrier_cost") or line_amount)
                markup_amt = line_amount - carrier_cost
                markup_pct = (markup_amt / carrier_cost * 100) if carrier_cost > 0 else 0
                margin_pct = (markup_amt / line_amount * 100) if line_amount > 0 else 0

                await db.execute(text("""
                    INSERT INTO tms.client_bill_lines
                        (client_bill_id, line_number, shipment_id,
                         charge_code, description, quantity,
                         rate_amount, cost_amount, markup_amount,
                         markup_pct, margin_amount, margin_pct,
                         line_amount, tax_amount)
                    VALUES
                        (CAST(:bill_id AS uuid), :line_num, CAST(:shp_id AS uuid),
                         :charge_code, :description, 1,
                         :rate, :cost, :markup_amt,
                         :markup_pct, :margin_amt, :margin_pct,
                         :amount, 0)
                """), {
                    "bill_id":     bill_id,
                    "line_num":    str(line_count + i),
                    "shp_id":      shp_id,
                    "charge_code": charge.get("charge_code"),
                    "description": charge.get("charge_code", "Freight Charge"),
                    "rate":        line_amount,
                    "cost":        carrier_cost,
                    "markup_amt":  markup_amt,
                    "markup_pct":  markup_pct,
                    "margin_amt":  markup_amt,
                    "margin_pct":  margin_pct,
                    "amount":      line_amount,
                })
                total_amount += line_amount

                # Mark charge as billed
                await db.execute(text("""
                    UPDATE tms.client_charges SET billed_flag = TRUE, billed_at = NOW()
                    WHERE client_charge_id = CAST(:id AS uuid)
                """), {"id": str(charge["client_charge_id"])})

            line_count += len(charges)

    # Update bill totals
    await db.execute(text("""
        UPDATE tms.client_bills
        SET total_bill_amount = :total, outstanding_amount = :total
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"total": total_amount, "id": bill_id})

    await _bill_audit(db, bill_id, "created", None, "draft", user_id,
                      f"Bill created: ${total_amount:.2f}, {line_count} lines")
    await db.commit()

    return {
        "client_bill_id":    bill_id,
        "client_bill_number":bill["client_bill_number"],
        "status":            "draft",
        "total_amount":      total_amount,
        "line_count":        line_count,
        "bill_level":        payload.bill_level,
    }


# ── BILL-004: Bill detail ─────────────────────────────────────────

@router.get("/")
async def list_bills(
    db: AsyncSession = Depends(get_db),
    customer_party_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    on_hold: Optional[bool] = Query(None),
    overdue_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    """BILL-013/018: List client bills with status and aging."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if customer_party_id:
        conditions.append("cb.customer_party_id = CAST(:cust_id AS uuid)")
        params["cust_id"] = customer_party_id
    if status:
        conditions.append("cb.status = :status")
        params["status"] = status
    if on_hold is not None:
        conditions.append("cb.on_hold = :on_hold")
        params["on_hold"] = on_hold
    if overdue_only:
        conditions.append("cb.due_date < CURRENT_DATE AND cb.status NOT IN ('paid','closed','canceled')")

    result = await db.execute(text(f"""
        SELECT cb.*, p.party_name AS customer_name,
               (CURRENT_DATE - cb.due_date) AS days_overdue,
               (SELECT COUNT(*) FROM tms.client_bill_lines cbl
                WHERE cbl.client_bill_id = cb.client_bill_id) AS line_count
        FROM tms.client_bills cb
        JOIN tms.parties p ON p.party_id = cb.customer_party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY cb.bill_date DESC, cb.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/{bill_id}")
async def get_bill(
    bill_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-004/005: Full bill detail with lines, payments, disputes, audit."""
    result = await db.execute(text("""
        SELECT cb.*, p.party_name AS customer_name
        FROM tms.client_bills cb
        JOIN tms.parties p ON p.party_id = cb.customer_party_id
        WHERE cb.client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    bill = result.mappings().one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found.")
    bill = dict(bill)

    # Lines (BILL-005)
    lines_result = await db.execute(text("""
        SELECT cbl.*, s.shipment_number
        FROM tms.client_bill_lines cbl
        LEFT JOIN tms.shipments s ON s.shipment_id = cbl.shipment_id
        WHERE cbl.client_bill_id = CAST(:id AS uuid)
        ORDER BY cbl.line_number
    """), {"id": bill_id})
    bill["lines"] = [dict(r) for r in lines_result.mappings().all()]

    # Payments (BILL-016)
    pay_result = await db.execute(text("""
        SELECT * FROM tms.client_bill_payments
        WHERE client_bill_id = CAST(:id AS uuid)
        ORDER BY received_date DESC
    """), {"id": bill_id})
    bill["payments"] = [dict(r) for r in pay_result.mappings().all()]

    # Disputes (BILL-012)
    disp_result = await db.execute(text("""
        SELECT * FROM tms.billing_disputes
        WHERE client_bill_id = CAST(:id AS uuid)
        ORDER BY opened_at DESC
    """), {"id": bill_id})
    bill["disputes"] = [dict(r) for r in disp_result.mappings().all()]

    # Audit trail (BILL-020)
    audit_result = await db.execute(text("""
        SELECT * FROM tms.bill_audit_history
        WHERE client_bill_id = CAST(:id AS uuid)
        ORDER BY performed_at DESC
    """), {"id": bill_id})
    bill["audit_trail"] = [dict(r) for r in audit_result.mappings().all()]

    return bill


# ── BILL-005: Add manual line ─────────────────────────────────────

@router.post("/{bill_id}/lines", status_code=201)
async def add_bill_line(
    bill_id: str,
    payload: BillLineAdd,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-005/006: Add charge line to bill with markup/margin calculation."""
    line_amount = payload.rate_amount * payload.quantity
    cost = payload.cost_amount or line_amount
    markup_amt = line_amount - cost
    markup_pct = payload.markup_pct or ((markup_amt / cost * 100) if cost > 0 else 0)
    margin_pct = (markup_amt / line_amount * 100) if line_amount > 0 else 0

    # Get next line number
    ln_result = await db.execute(text("""
        SELECT COALESCE(MAX(CAST(line_number AS INTEGER)), 0) + 1 AS next_line
        FROM tms.client_bill_lines WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    next_line = int(ln_result.scalar() or 1)

    result = await db.execute(text("""
        INSERT INTO tms.client_bill_lines
            (client_bill_id, line_number, shipment_id, order_release_id,
             purchase_order_id, purchase_order_line_id,
             charge_code, description, quantity, rate_amount,
             cost_amount, markup_amount, markup_pct,
             margin_amount, margin_pct, line_amount, tax_amount,
             is_taxable, notes)
        VALUES
            (CAST(:bill_id AS uuid), :line_num,
             CAST(:shipment_id AS uuid), CAST(:release_id AS uuid),
             CAST(:po_id AS uuid), CAST(:pol_id AS uuid),
             :charge_code, :description, :qty, :rate,
             :cost, :markup_amt, :markup_pct,
             :markup_amt, :margin_pct, :amount, :tax,
             :is_taxable, :notes)
        RETURNING client_bill_line_id
    """), {
        "bill_id":    bill_id,
        "line_num":   str(next_line),
        "shipment_id":payload.shipment_id,
        "release_id": payload.order_release_id,
        "po_id":      payload.purchase_order_id,
        "pol_id":     payload.purchase_order_line_id,
        "charge_code":payload.charge_code,
        "description":payload.description,
        "qty":        payload.quantity,
        "rate":       payload.rate_amount,
        "cost":       cost,
        "markup_amt": markup_amt,
        "markup_pct": markup_pct,
        "margin_pct": margin_pct,
        "amount":     line_amount,
        "tax":        payload.tax_amount,
        "is_taxable": payload.is_taxable,
        "notes":      payload.notes,
    })

    # Recalculate bill total
    await db.execute(text("""
        UPDATE tms.client_bills
        SET total_bill_amount = (
            SELECT COALESCE(SUM(line_amount + tax_amount), 0)
            FROM tms.client_bill_lines WHERE client_bill_id = CAST(:id AS uuid)
        ),
        outstanding_amount = (
            SELECT COALESCE(SUM(line_amount + tax_amount), 0)
            FROM tms.client_bill_lines WHERE client_bill_id = CAST(:id AS uuid)
        ) - paid_amount
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    await db.commit()

    return {"line_id": str(result.scalar()), "line_amount": line_amount,
            "markup_pct": markup_pct, "margin_pct": margin_pct}


# ── BILL-008/009: Hold management & validation ────────────────────

@router.patch("/{bill_id}/hold")
async def set_bill_hold(
    bill_id: str,
    payload: HoldUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-008: Place or release billing hold."""
    user_id = user.get("email", "system")
    await db.execute(text("""
        UPDATE tms.client_bills
        SET on_hold = :on_hold, hold_reason = :reason, updated_at = NOW()
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"on_hold": payload.on_hold, "reason": payload.hold_reason, "id": bill_id})
    await _bill_audit(db, bill_id, "hold_changed", None, None, user_id,
                      f"Hold {'placed' if payload.on_hold else 'released'}: {payload.hold_reason or ''}")
    await db.commit()
    return {"client_bill_id": bill_id, "on_hold": payload.on_hold}


@router.get("/{bill_id}/validate")
async def validate_billing(
    bill_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-009: Validate billing eligibility before approval/send."""
    bill_result = await db.execute(text("""
        SELECT cb.*, p.party_name AS customer_name
        FROM tms.client_bills cb JOIN tms.parties p ON p.party_id = cb.customer_party_id
        WHERE cb.client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    bill = bill_result.mappings().one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found.")
    bill = dict(bill)

    issues = []
    warnings = []

    # Check lines exist
    ln_result = await db.execute(text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(line_amount),0) AS total
        FROM tms.client_bill_lines WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    ln = dict(ln_result.mappings().one())
    if int(ln["cnt"]) == 0:
        issues.append("Bill has no lines.")

    # Check total matches
    if abs(float(ln["total"]) - float(bill.get("total_bill_amount") or 0)) > 0.01:
        warnings.append("Bill total doesn't match sum of lines.")

    # Check disputes
    open_disp = await db.execute(text("""
        SELECT COUNT(*) FROM tms.billing_disputes
        WHERE client_bill_id = CAST(:id AS uuid) AND status NOT IN ('resolved','closed')
    """), {"id": bill_id})
    if int(open_disp.scalar() or 0) > 0:
        issues.append("Bill has unresolved disputes.")

    # Check on hold
    if bill.get("on_hold"):
        issues.append(f"Bill is on hold: {bill.get('hold_reason')}")

    is_valid = len(issues) == 0
    return {
        "client_bill_id": bill_id,
        "is_valid":       is_valid,
        "can_approve":    is_valid,
        "line_count":     int(ln["cnt"]),
        "total_amount":   float(ln["total"]),
        "issues":         issues,
        "warnings":       warnings,
    }


# ── BILL-011: Adjustments (credit/debit/rebill) ───────────────────

@router.post("/{bill_id}/adjust", status_code=201)
async def create_adjustment(
    bill_id: str,
    payload: AdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-011: Credit memo, debit memo, rebill, correction, write-off."""
    user_id = user.get("email", "system")
    valid_types = ["credit","debit","rebill","correction","write_off"]
    if payload.adjustment_type not in valid_types:
        raise HTTPException(400, f"Invalid adjustment_type. Valid: {', '.join(valid_types)}")

    # Load original bill
    orig_result = await db.execute(text("""
        SELECT * FROM tms.client_bills WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    orig = orig_result.mappings().one_or_none()
    if not orig:
        raise HTTPException(404, "Bill not found.")
    orig = dict(orig)

    adj_number = f"ADJ-{payload.adjustment_type.upper()}-{datetime.utcnow().strftime('%Y%m%d')}-{bill_id[:8].upper()}"
    adj_amount = -payload.amount if payload.adjustment_type in ("credit","write_off") else payload.amount

    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = 'USD' LIMIT 1
    """))
    currency_id = curr_result.scalar()

    adj_result = await db.execute(text("""
        INSERT INTO tms.client_bills
            (client_bill_number, customer_party_id, bill_level,
             bill_date, due_date, currency_id, total_bill_amount,
             outstanding_amount, status, payment_status,
             parent_bill_id, notes, created_by)
        VALUES
            (:number, CAST(:cust_id AS uuid), :level,
             CURRENT_DATE, CURRENT_DATE, CAST(:currency_id AS uuid), :amount,
             :amount, 'approved', 'unpaid',
             CAST(:parent_id AS uuid), :notes, :created_by)
        RETURNING client_bill_id, client_bill_number
    """), {
        "number":      adj_number,
        "cust_id":     str(orig["customer_party_id"]),
        "level":       orig.get("bill_level","shipment"),
        "currency_id": str(currency_id) if currency_id else None,
        "amount":      adj_amount,
        "parent_id":   bill_id,
        "notes":       f"{payload.adjustment_type}: {payload.reason}. {payload.notes or ''}".strip(),
        "created_by":  user_id,
    })
    adj = dict(adj_result.mappings().one())

    # Update original bill status for credit/rebill
    if payload.adjustment_type == "credit":
        await db.execute(text("""
            UPDATE tms.client_bills SET status = 'credited', updated_at = NOW()
            WHERE client_bill_id = CAST(:id AS uuid)
        """), {"id": bill_id})
    elif payload.adjustment_type == "rebill":
        await db.execute(text("""
            UPDATE tms.client_bills SET status = 'rebilled', updated_at = NOW()
            WHERE client_bill_id = CAST(:id AS uuid)
        """), {"id": bill_id})

    await _bill_audit(db, bill_id, payload.adjustment_type, orig.get("status"),
                      payload.adjustment_type, user_id,
                      f"{payload.adjustment_type} ${abs(payload.amount):.2f}: {payload.reason}")
    await db.commit()

    return {
        "adjustment_bill_id":    str(adj["client_bill_id"]),
        "adjustment_bill_number":adj["client_bill_number"],
        "adjustment_type":       payload.adjustment_type,
        "amount":                adj_amount,
        "original_bill_id":      bill_id,
    }


# ── BILL-012: Status management & disputes ────────────────────────

@router.patch("/{bill_id}/status")
async def update_bill_status(
    bill_id: str,
    payload: BillStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-013: Update bill status through lifecycle."""
    user_id = user.get("email", "system")
    if payload.status not in BILL_STATUSES:
        raise HTTPException(400, f"Invalid status.")

    curr_result = await db.execute(text("""
        SELECT status FROM tms.client_bills WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    curr = curr_result.mappings().one_or_none()
    if not curr:
        raise HTTPException(404, "Bill not found.")

    update_params: dict[str, Any] = {
        "status": payload.status, "id": bill_id,
        "approved_by": None, "approved_at": None,
        "sent_at": None, "sent_channel": None,
    }
    if payload.status == "approved":
        update_params.update({"approved_by": user_id, "approved_at": datetime.utcnow()})
    elif payload.status == "sent":
        update_params.update({
            "sent_at": datetime.utcnow(),
            "sent_channel": payload.sent_channel or "portal",
        })

    await db.execute(text("""
        UPDATE tms.client_bills
        SET status       = :status,
            approved_by  = :approved_by,
            approved_at  = :approved_at,
            sent_at      = :sent_at,
            sent_channel = :sent_channel,
            updated_at   = NOW()
        WHERE client_bill_id = CAST(:id AS uuid)
    """), update_params)

    await _bill_audit(db, bill_id, "status_changed", curr["status"],
                      payload.status, user_id, payload.notes)
    await db.commit()

    return {"client_bill_id": bill_id, "from_status": curr["status"],
            "to_status": payload.status, "updated_by": user_id}


@router.post("/{bill_id}/disputes", status_code=201)
async def create_billing_dispute(
    bill_id: str,
    payload: BillingDisputeCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-012: Customer billing dispute."""
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        INSERT INTO tms.billing_disputes
            (client_bill_id, dispute_reason, disputed_amount, notes, opened_by)
        VALUES (CAST(:id AS uuid), :reason, :amount, :notes, :user)
        RETURNING dispute_id
    """), {
        "id": bill_id, "reason": payload.dispute_reason,
        "amount": payload.disputed_amount, "notes": payload.notes, "user": user_id
    })
    await db.execute(text("""
        UPDATE tms.client_bills SET status = 'disputed', updated_at = NOW()
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    await _bill_audit(db, bill_id, "disputed", None, "disputed", user_id,
                      f"Dispute: {payload.dispute_reason} ${payload.disputed_amount:.2f}")
    await db.commit()
    return {"dispute_id": str(result.scalar()), "dispute_reason": payload.dispute_reason}


# ── BILL-014/015: Delivery & export ──────────────────────────────

@router.post("/{bill_id}/send")
async def send_bill(
    bill_id: str,
    channel: str = "portal",
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-014: Deliver bill by email, portal, EDI, API, print, accounting export."""
    user_id = user.get("email", "system")
    valid_channels = ["email","portal","edi","api","print","accounting_export"]
    if channel not in valid_channels:
        raise HTTPException(400, f"Invalid channel. Valid: {', '.join(valid_channels)}")

    bill_result = await db.execute(text("""
        SELECT cb.*, p.party_name AS customer_name, p.party_code
        FROM tms.client_bills cb JOIN tms.parties p ON p.party_id = cb.customer_party_id
        WHERE cb.client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    bill = bill_result.mappings().one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found.")
    bill = dict(bill)

    if bill.get("status") not in ("approved","draft"):
        raise HTTPException(422, f"Cannot send bill with status '{bill.get('status')}'. Approve first.")

    await db.execute(text("""
        UPDATE tms.client_bills
        SET status = 'sent', sent_at = NOW(), sent_channel = :channel, updated_at = NOW()
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"channel": channel, "id": bill_id})

    await _bill_audit(db, bill_id, "sent", bill.get("status"), "sent",
                      user_id, f"Sent via {channel}")
    await db.commit()

    return {
        "client_bill_id":    bill_id,
        "bill_number":       bill.get("client_bill_number"),
        "customer":          bill.get("customer_name"),
        "channel":           channel,
        "sent_at":           str(datetime.utcnow()),
        "amount":            float(bill.get("total_bill_amount") or 0),
    }


@router.post("/{bill_id}/export")
async def export_bill(
    bill_id: str,
    payload: BillExportRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-015: Export to ERP, AR, accounting, customer portals."""
    user_id = user.get("email", "system")
    bill_result = await db.execute(text("""
        SELECT cb.*, p.party_name AS customer_name, p.party_code
        FROM tms.client_bills cb JOIN tms.parties p ON p.party_id = cb.customer_party_id
        WHERE cb.client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    bill = bill_result.mappings().one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found.")
    bill = dict(bill)

    lines_result = await db.execute(text("""
        SELECT cbl.*, s.shipment_number
        FROM tms.client_bill_lines cbl
        LEFT JOIN tms.shipments s ON s.shipment_id = cbl.shipment_id
        WHERE cbl.client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    lines = [dict(r) for r in lines_result.mappings().all()]

    await db.execute(text("""
        UPDATE tms.client_bills
        SET exported_at = NOW(), updated_at = NOW()
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    await _bill_audit(db, bill_id, "exported", None, None, user_id,
                      f"Exported to {payload.target_system}")
    await db.commit()

    return {
        "export_format":  payload.target_system,
        "bill_number":    bill.get("client_bill_number"),
        "customer_code":  bill.get("party_code"),
        "customer_name":  bill.get("customer_name"),
        "bill_date":      str(bill.get("bill_date") or ""),
        "due_date":       str(bill.get("due_date") or ""),
        "total_amount":   float(bill.get("total_bill_amount") or 0),
        "currency":       "USD",
        "line_count":     len(lines),
        "lines": [{
            "line_number":  l.get("line_number"),
            "shipment_ref": l.get("shipment_number"),
            "charge_code":  l.get("charge_code"),
            "description":  l.get("description"),
            "amount":       float(l.get("line_amount") or 0),
            "tax":          float(l.get("tax_amount") or 0),
        } for l in lines],
        "exported_at": str(datetime.utcnow()),
    }


# ── BILL-016: Receive payment ─────────────────────────────────────

@router.post("/{bill_id}/payments", status_code=201)
async def receive_payment(
    bill_id: str,
    payload: PaymentReceive,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """BILL-016/017: Receive full, partial payment or credit from ERP/AR."""
    user_id = user.get("email", "system")

    bill_result = await db.execute(text("""
        SELECT total_bill_amount, paid_amount, outstanding_amount
        FROM tms.client_bills WHERE client_bill_id = CAST(:id AS uuid)
    """), {"id": bill_id})
    bill = bill_result.mappings().one_or_none()
    if not bill:
        raise HTTPException(404, "Bill not found.")
    bill = dict(bill)

    total = float(bill.get("total_bill_amount") or 0)
    already_paid = float(bill.get("paid_amount") or 0)
    new_paid = already_paid + payload.received_amount
    outstanding = max(0, total - new_paid)

    pay_status = "paid" if outstanding <= 0.01 else "partially_paid"
    rec_date = _date.fromisoformat(payload.received_date) if payload.received_date else _date.today()

    # Record payment
    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = 'USD' LIMIT 1
    """))
    currency_id = curr_result.scalar()

    await db.execute(text("""
        INSERT INTO tms.client_bill_payments
            (client_bill_id, received_amount, currency_id, received_date)
        VALUES
            (CAST(:id AS uuid), :amount, CAST(:currency_id AS uuid), :rec_date)
    """), {
        "id":          bill_id,
        "amount":      payload.received_amount,
        "currency_id": str(currency_id) if currency_id else None,
        "rec_date":    rec_date,
    })

    await db.execute(text("""
        UPDATE tms.client_bills
        SET paid_amount       = :paid,
            outstanding_amount= :outstanding,
            payment_status    = :pay_status,
            status            = CASE WHEN :outstanding <= 0.01 THEN 'paid' ELSE status END,
            updated_at        = NOW()
        WHERE client_bill_id = CAST(:id AS uuid)
    """), {"paid": new_paid, "outstanding": outstanding,
           "pay_status": pay_status, "id": bill_id})

    await _bill_audit(db, bill_id, "payment_received", None, pay_status, user_id,
                      f"Received ${payload.received_amount:.2f}. Outstanding: ${outstanding:.2f}")
    await db.commit()

    return {
        "client_bill_id":   bill_id,
        "received_amount":  payload.received_amount,
        "total_paid":       new_paid,
        "outstanding":      outstanding,
        "payment_status":   pay_status,
    }


# ── BILL-006/017: Billing rules ───────────────────────────────────

@router.get("/rules")
async def list_billing_rules(
    db: AsyncSession = Depends(get_db),
    customer_party_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """BILL-006: List configurable billing rules."""
    conditions = ["is_active = TRUE"]
    params: dict[str, Any] = {}
    if customer_party_id:
        conditions.append("(customer_party_id = CAST(:cust_id AS uuid) OR customer_party_id IS NULL)")
        params["cust_id"] = customer_party_id
    result = await db.execute(text(f"""
        SELECT r.*, p.party_name AS customer_name FROM tms.client_billing_rules r
        LEFT JOIN tms.parties p ON p.party_id = r.customer_party_id
        WHERE {' AND '.join(conditions)} ORDER BY r.priority DESC
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/rules", status_code=201)
async def create_billing_rule(
    payload: BillingRuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user.get("email", "system")
    eff_date = _date.fromisoformat(payload.effective_date) if payload.effective_date else _date.today()
    result = await db.execute(text("""
        INSERT INTO tms.client_billing_rules
            (customer_party_id, rule_name, rule_type, applies_to_modes,
             applies_to_charges, rule_params, priority, effective_date, created_by)
        VALUES
            (CAST(:customer_party_id AS uuid), :rule_name, :rule_type,
             :applies_to_modes, :applies_to_charges,
             CAST(:rule_params AS jsonb), :priority, :effective_date, :created_by)
        RETURNING rule_id
    """), {
        **payload.model_dump(),
        "rule_params":       _json.dumps(payload.rule_params),
        "effective_date":    eff_date,
        "created_by":        user_id,
    })
    await db.commit()
    return {"rule_id": str(result.scalar()), **payload.model_dump()}


# ── BILL-018/019: Reports ─────────────────────────────────────────

@router.get("/reports/summary")
async def billing_reports(
    db: AsyncSession = Depends(get_db),
    customer_party_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """BILL-018/019: Revenue, margin, AR aging, unbilled, disputed, reconciliation."""
    # AR aging
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
            SUM(outstanding_amount) AS total
        FROM tms.client_bills
        WHERE status NOT IN ('paid','closed','canceled','credited')
        GROUP BY bucket ORDER BY bucket
    """))
    aging = {r["bucket"]: {"count": int(r["count"]), "total": float(r["total"] or 0)}
             for r in aging_result.mappings().all()}

    # Revenue summary
    rev_result = await db.execute(text("""
        SELECT
            SUM(total_bill_amount) AS total_billed,
            SUM(paid_amount) AS total_paid,
            SUM(outstanding_amount) AS total_outstanding,
            COUNT(*) FILTER (WHERE status = 'draft') AS draft_count,
            COUNT(*) FILTER (WHERE status = 'disputed') AS disputed_count
        FROM tms.client_bills
        WHERE status NOT IN ('canceled','credited')
    """))
    rev = dict(rev_result.mappings().one())

    # Margin summary (BILL-019 reconciliation)
    margin_result = await db.execute(text("""
        SELECT
            COALESCE(SUM(cbl.line_amount), 0) AS total_billed_lines,
            COALESCE(SUM(cbl.cost_amount), 0) AS total_cost,
            COALESCE(SUM(cbl.markup_amount), 0) AS total_markup
        FROM tms.client_bill_lines cbl
        JOIN tms.client_bills cb ON cb.client_bill_id = cbl.client_bill_id
        WHERE cb.status NOT IN ('canceled','credited')
    """))
    margin = dict(margin_result.mappings().one())
    total_billed = float(margin.get("total_billed_lines") or 0)
    total_cost = float(margin.get("total_cost") or 0)
    overall_margin = ((total_billed - total_cost) / total_billed * 100) if total_billed > 0 else 0

    # Unbilled shipments
    unbilled_result = await db.execute(text("""
        SELECT COUNT(*) AS unbilled_count
        FROM tms.client_charges cc
        WHERE cc.billed_flag = FALSE
    """))
    unbilled = dict(unbilled_result.mappings().one())

    return {
        "revenue": {
            "total_billed":      float(rev.get("total_billed") or 0),
            "total_paid":        float(rev.get("total_paid") or 0),
            "total_outstanding": float(rev.get("total_outstanding") or 0),
            "draft_bills":       int(rev.get("draft_count") or 0),
            "disputed_bills":    int(rev.get("disputed_count") or 0),
        },
        "margin": {
            "total_billed":   total_billed,
            "total_cost":     total_cost,
            "total_markup":   float(margin.get("total_markup") or 0),
            "overall_margin_pct": round(overall_margin, 2),
        },
        "ar_aging":          aging,
        "unbilled_charges":  int(unbilled.get("unbilled_count") or 0),
    }


# ── Helpers ───────────────────────────────────────────────────────

async def _bill_audit(db, bill_id: str, event_type: str, from_status,
                       to_status, performed_by: str, notes: str = None):
    try:
        await db.execute(text("""
            INSERT INTO tms.bill_audit_history
                (client_bill_id, event_type, from_status, to_status, performed_by, notes)
            VALUES (CAST(:id AS uuid), :et, :from_s, :to_s, :by, :notes)
        """), {"id": bill_id, "et": event_type, "from_s": from_status,
               "to_s": to_status, "by": performed_by, "notes": notes})
    except Exception:
        pass


async def _validate_billing_eligibility(db, shipment_id: str) -> dict:
    issues = []

    # Check lifecycle stage
    lc_result = await db.execute(text("""
        SELECT current_stage, delivered FROM tms.process_lifecycle
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    lc = lc_result.mappings().one_or_none()
    if not lc or not lc.get("delivered"):
        issues.append("INCOMPLETE_SHIPMENT")

    # Check POD
    pod_result = await db.execute(text("""
        SELECT COUNT(*) FROM tms.proof_of_execution
        WHERE shipment_id = CAST(:id AS uuid) AND proof_type = 'pod'
    """), {"id": shipment_id})
    if int(pod_result.scalar() or 0) == 0:
        issues.append("MISSING_POD")

    # Check allocation
    alloc_result = await db.execute(text("""
        SELECT COUNT(*) FROM tms.charge_allocations
        WHERE shipment_id = CAST(:id AS uuid) AND is_current_version = TRUE
    """), {"id": shipment_id})
    if int(alloc_result.scalar() or 0) == 0:
        issues.append("INCOMPLETE_ALLOCATION")

    return {"eligible": len(issues) == 0, "issues": issues}


async def _get_billing_rules(db, customer_party_id: str) -> list:
    result = await db.execute(text("""
        SELECT * FROM tms.client_billing_rules
        WHERE is_active = TRUE
          AND (customer_party_id = CAST(:id AS uuid) OR customer_party_id IS NULL)
        ORDER BY priority DESC
    """), {"id": customer_party_id})
    return [dict(r) for r in result.mappings().all()]
