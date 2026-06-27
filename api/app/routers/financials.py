"""
routers/financials.py
TMS-FIN-001 through TMS-FIN-010: Accruals, Accounting & Financial Controls
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, date as _date
import json as _json
from decimal import Decimal

router = APIRouter()

ACCRUAL_MILESTONES = [
    "planned","tendered","accepted","picked_up","delivered","completed","closed"
]


# ── Pydantic Models ───────────────────────────────────────────────

class AccrualCreate(BaseModel):
    shipment_id: str
    accrual_milestone: str = "planned"
    accrual_level: str = "shipment"
    amount: Optional[float] = None
    charge_code: Optional[str] = None
    gl_account_code: Optional[str] = None
    cost_center_code: Optional[str] = None
    project_code: Optional[str] = None
    currency: str = "USD"

class AccrualRelieve(BaseModel):
    carrier_invoice_id: str
    reversal_reason: Optional[str] = None

class GLDistributionCreate(BaseModel):
    shipment_id: Optional[str] = None
    carrier_invoice_id: Optional[str] = None
    client_bill_id: Optional[str] = None
    gl_account_code: str
    business_unit_code: Optional[str] = None
    department_code: Optional[str] = None
    cost_center_code: Optional[str] = None
    project_code: Optional[str] = None
    charge_code: Optional[str] = None
    tax_code: Optional[str] = None
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    currency_code: str = "USD"
    accounting_date: Optional[str] = None

class ExchangeRateCreate(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    rate_date: str
    rate_type: str = "spot"
    source: str = "manual"

class TaxCalcRequest(BaseModel):
    shipment_id: Optional[str] = None
    carrier_invoice_id: Optional[str] = None
    client_bill_id: Optional[str] = None
    taxable_amount: float
    tax_code: Optional[str] = None
    jurisdiction: Optional[str] = None

class PeriodClose(BaseModel):
    status: str  # closing | closed | locked
    notes: Optional[str] = None

class ApprovalCreate(BaseModel):
    approval_type: str
    entity_type: str
    entity_id: str
    amount: Optional[float] = None
    notes: Optional[str] = None
    expires_hours: int = 48

class ApprovalAction(BaseModel):
    action: str  # approve | reject | withdraw
    reason: Optional[str] = None


# ── FIN-001/002/003: Accruals ─────────────────────────────────────

@router.post("/accruals", status_code=201)
async def create_accrual(
    payload: AccrualCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-001/003: Create freight cost accrual at a milestone."""
    user_id = user.get("email", "system")
    if payload.accrual_milestone not in ACCRUAL_MILESTONES:
        raise HTTPException(400, f"Invalid milestone. Valid: {', '.join(ACCRUAL_MILESTONES)}")

    # Auto-estimate amount from shipment costs if not provided
    accrual_amount = payload.amount
    if not accrual_amount:
        amt_result = await db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) AS total FROM tms.shipment_costs
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": payload.shipment_id})
        accrual_amount = float(amt_result.scalar() or 0)

    # Get active financial period
    period_result = await db.execute(text("""
        SELECT financial_period_id AS period_id FROM tms.financial_periods
        WHERE close_status_id IS NULL AND period_start_date <= CURRENT_DATE AND period_end_date >= CURRENT_DATE
        ORDER BY period_start_date DESC LIMIT 1
    """))
    period_id = period_result.scalar()

    # Get currency id
    curr_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :code LIMIT 1
    """), {"code": payload.currency})
    currency_id = curr_result.scalar()

    # Generate accrual number
    accrual_number = f"ACR-{datetime.utcnow().strftime('%Y%m%d')}-{payload.shipment_id[:8].upper()}"

    result = await db.execute(text("""
        INSERT INTO tms.accruals
            (accrual_number, accrual_source_type, accrual_source_id,
             shipment_id, accrual_milestone, accrual_level,
             financial_period_id, currency_id,
             accrual_amount, estimated_amount, status,
             gl_account_code, cost_center_code, project_code, charge_code,
             created_by)
        VALUES
            (:number, 'shipment', CAST(:shipment_id AS uuid),
             CAST(:shipment_id AS uuid), :milestone, :level,
             CAST(:period_id AS uuid), CAST(:currency_id AS uuid),
             :amount, :amount, 'open',
             :gl_code, :cc_code, :proj_code, :charge_code,
             :created_by)
        RETURNING accrual_id, accrual_number
    """), {
        "number":      accrual_number,
        "shipment_id": payload.shipment_id,
        "milestone":   payload.accrual_milestone,
        "level":       payload.accrual_level,
        "period_id":   str(period_id) if period_id else None,
        "currency_id": str(currency_id) if currency_id else None,
        "amount":      accrual_amount,
        "gl_code":     payload.gl_account_code,
        "cc_code":     payload.cost_center_code,
        "proj_code":   payload.project_code,
        "charge_code": payload.charge_code,
        "created_by":  user_id,
    })
    row = dict(result.mappings().one())
    await db.commit()

    return {
        "accrual_id":     str(row["accrual_id"]),
        "accrual_number": row["accrual_number"],
        "shipment_id":    payload.shipment_id,
        "milestone":      payload.accrual_milestone,
        "amount":         accrual_amount,
        "status":         "open",
    }


@router.get("/accruals")
async def list_accruals(
    db: AsyncSession = Depends(get_db),
    shipment_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    milestone: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """FIN-001: List accruals with filtering."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if shipment_id:
        conditions.append("a.shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id
    if status:
        conditions.append("a.status = :status")
        params["status"] = status
    if milestone:
        conditions.append("a.accrual_milestone = :milestone")
        params["milestone"] = milestone

    result = await db.execute(text(f"""
        SELECT a.*, s.shipment_number,
               fp.period_code AS financial_period
        FROM tms.accruals a
        LEFT JOIN tms.shipments s ON s.shipment_id = a.shipment_id
        LEFT JOIN tms.financial_periods fp ON fp.financial_period_id = a.financial_period_id
        WHERE {' AND '.join(conditions)}
        ORDER BY a.created_at DESC
        LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/accruals/{accrual_id}/reverse")
async def reverse_accrual(
    accrual_id: str,
    payload: AccrualRelieve,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-002: Reverse or relieve accrual when invoice approved/paid."""
    user_id = user.get("email", "system")

    result = await db.execute(text("""
        UPDATE tms.accruals
        SET status           = 'reversed',
            carrier_invoice_id = CAST(:inv_id AS uuid),
            reversal_reason  = :reason,
            reversed_at      = NOW(),
            reversed_by      = :user,
            relieved_amount  = accrual_amount,
            updated_at       = NOW()
        WHERE accrual_id = CAST(:id AS uuid) AND status = 'open'
        RETURNING accrual_id, accrual_amount, status
    """), {
        "inv_id": payload.carrier_invoice_id,
        "reason": payload.reversal_reason or "Invoice approved",
        "user":   user_id,
        "id":     accrual_id,
    })
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Accrual not found or already reversed.")
    await db.commit()
    return dict(row)


@router.post("/accruals/auto-relieve/{invoice_id}")
async def auto_relieve_accruals(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-002: Auto-relieve all open accruals when invoice is approved."""
    user_id = user.get("email", "system")

    # Get shipment for this invoice
    inv_result = await db.execute(text("""
        SELECT shipment_id FROM tms.carrier_invoices
        WHERE carrier_invoice_id = CAST(:id AS uuid)
    """), {"id": invoice_id})
    inv = inv_result.mappings().one_or_none()
    if not inv or not inv.get("shipment_id"):
        return {"relieved": 0, "message": "No shipment linked to invoice."}

    result = await db.execute(text("""
        UPDATE tms.accruals
        SET status           = 'relieved',
            carrier_invoice_id = CAST(:inv_id AS uuid),
            reversal_reason  = 'Invoice approved - auto relieved',
            reversed_at      = NOW(),
            reversed_by      = :user,
            relieved_amount  = accrual_amount,
            updated_at       = NOW()
        WHERE shipment_id = CAST(:shp_id AS uuid) AND status = 'open'
        RETURNING accrual_id
    """), {"inv_id": invoice_id, "user": user_id, "shp_id": str(inv["shipment_id"])})
    relieved = result.fetchall()
    await db.commit()
    return {"relieved": len(relieved), "shipment_id": str(inv["shipment_id"])}


# ── FIN-004/005: GL distributions ────────────────────────────────

@router.post("/gl-distributions", status_code=201)
async def create_gl_distribution(
    payload: GLDistributionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-004/005: Create GL accounting distribution."""
    user_id = user.get("email", "system")
    acc_date = _date.fromisoformat(payload.accounting_date) if payload.accounting_date else _date.today()

    # Get active fiscal period name
    period_result = await db.execute(text("""
        SELECT period_code AS period_name FROM tms.financial_periods
        WHERE :acc_date BETWEEN start_date AND end_date AND status != 'locked'
        ORDER BY period_start_date DESC LIMIT 1
    """), {"acc_date": acc_date})
    period_row = period_result.mappings().one_or_none()
    fiscal_period = period_row["period_name"] if period_row else None

    result = await db.execute(text("""
        INSERT INTO tms.gl_distributions
            (shipment_id, carrier_invoice_id, client_bill_id,
             gl_account_code, business_unit_code, department_code,
             cost_center_code, project_code, charge_code, tax_code,
             debit_amount, credit_amount, currency_code,
             accounting_date, fiscal_period, created_by)
        VALUES
            (CAST(:shipment_id AS uuid), CAST(:carrier_invoice_id AS uuid),
             CAST(:client_bill_id AS uuid),
             :gl_account_code, :business_unit_code, :department_code,
             :cost_center_code, :project_code, :charge_code, :tax_code,
             :debit_amount, :credit_amount, :currency_code,
             :accounting_date, :fiscal_period, :created_by)
        RETURNING distribution_id
    """), {
        **payload.model_dump(),
        "accounting_date": acc_date,
        "fiscal_period":   fiscal_period,
        "created_by":      user_id,
    })
    await db.commit()
    return {"distribution_id": str(result.scalar()), "fiscal_period": fiscal_period,
            **payload.model_dump()}


@router.post("/gl-distributions/auto-generate/{shipment_id}", status_code=201)
async def auto_generate_gl(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-004: Auto-generate GL distributions from allocation rules."""
    user_id = user.get("email", "system")

    # Get allocations with GL codes
    alloc_result = await db.execute(text("""
        SELECT ca.*, sc.charge_code, ccm.gl_account_code AS master_gl
        FROM tms.charge_allocations ca
        LEFT JOIN tms.shipment_costs sc ON sc.cost_id = ca.shipment_cost_id
        LEFT JOIN tms.charge_code_master ccm ON ccm.charge_code = sc.charge_code
        WHERE ca.shipment_id = CAST(:id AS uuid) AND ca.is_current_version = TRUE
    """), {"id": shipment_id})
    allocations = [dict(r) for r in alloc_result.mappings().all()]

    # Get active period
    period_result = await db.execute(text("""
        SELECT period_code AS period_name FROM tms.financial_periods
        WHERE close_status_id IS NULL AND period_start_date <= CURRENT_DATE AND period_end_date >= CURRENT_DATE
        ORDER BY period_number LIMIT 1
    """))
    period_name = period_result.scalar()

    created = []
    for alloc in allocations:
        gl_code = alloc.get("gl_account_code") or alloc.get("master_gl") or "5000"
        amount = float(alloc.get("allocation_amount") or 0)
        if amount <= 0:
            continue

        r = await db.execute(text("""
            INSERT INTO tms.gl_distributions
                (shipment_id, allocation_id, gl_account_code,
                 cost_center_code, charge_code,
                 debit_amount, credit_amount, currency_code,
                 accounting_date, fiscal_period, created_by)
            VALUES
                (CAST(:shp_id AS uuid), CAST(:alloc_id AS uuid), :gl_code,
                 :cc_code, :charge_code,
                 :debit, 0, :currency,
                 CURRENT_DATE, :period, :user)
            RETURNING distribution_id
        """), {
            "shp_id":      shipment_id,
            "alloc_id":    str(alloc["allocation_id"]),
            "gl_code":     gl_code,
            "cc_code":     alloc.get("cost_center_code"),
            "charge_code": alloc.get("charge_code"),
            "debit":       amount,
            "currency":    alloc.get("currency","USD"),
            "period":      period_name,
            "user":        user_id,
        })
        created.append(str(r.scalar()))

    await db.commit()
    return {"shipment_id": shipment_id, "distributions_created": len(created),
            "fiscal_period": period_name}


@router.get("/gl-distributions")
async def list_gl_distributions(
    db: AsyncSession = Depends(get_db),
    shipment_id: Optional[str] = Query(None),
    gl_account_code: Optional[str] = Query(None),
    fiscal_period: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """FIN-004/005: List GL distributions with filtering."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if shipment_id:
        conditions.append("gld.shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id
    if gl_account_code:
        conditions.append("gld.gl_account_code = :gl_code")
        params["gl_code"] = gl_account_code
    if fiscal_period:
        conditions.append("gld.fiscal_period = :period")
        params["period"] = fiscal_period
    if status:
        conditions.append("gld.status = :status")
        params["status"] = status

    result = await db.execute(text(f"""
        SELECT gld.*, s.shipment_number, ga.account_name
        FROM tms.gl_distributions gld
        LEFT JOIN tms.shipments s ON s.shipment_id = gld.shipment_id
        LEFT JOIN tms.gl_accounts ga ON ga.account_code = gld.gl_account_code
        WHERE {' AND '.join(conditions)}
        ORDER BY gld.accounting_date DESC, gld.created_at DESC
        LIMIT :limit
    """), params)
    return [dict(r) for r in result.mappings().all()]


# ── FIN-006: Financial periods ────────────────────────────────────

@router.get("/periods")
async def list_periods(
    db: AsyncSession = Depends(get_db),
    fiscal_year: Optional[int] = Query(None),
    user=Depends(get_current_user),
):
    """FIN-006: List financial periods and their status."""
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if fiscal_year:
        conditions.append("fiscal_year = :year")
        params["year"] = fiscal_year
    result = await db.execute(text(f"""
        SELECT *, period_code AS period_name, period_start_date AS start_date, period_end_date AS end_date FROM tms.financial_periods
        WHERE {' AND '.join(conditions)}
        ORDER BY period_start_date
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.patch("/periods/{period_id}/close")
async def close_period(
    period_id: str,
    payload: PeriodClose,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-006: Close or lock an accounting period."""
    user_id = user.get("email", "system")
    if payload.status not in ("closing","closed","locked"):
        raise HTTPException(400, "Status must be: closing, closed, or locked.")

    # Check for open accruals in this period
    open_accr = await db.execute(text("""
        SELECT COUNT(*) FROM tms.accruals
        WHERE financial_period_id = CAST(:id AS uuid) AND status = 'open'
    """), {"id": period_id})
    if int(open_accr.scalar() or 0) > 0 and payload.status == "locked":
        raise HTTPException(422, "Cannot lock period with open accruals.")

    result = await db.execute(text("""
        UPDATE tms.financial_periods
        SET close_status_id = (SELECT lookup_value_id FROM tms.lookup_values WHERE UPPER(lookup_code) = UPPER(:status) LIMIT 1), closed_by_user_id = :user, closed_at = NOW()
        WHERE financial_period_id = CAST(:id AS uuid)
        RETURNING financial_period_id AS period_id, period_code AS period_name, close_status_id
    """), {"status": payload.status, "user": user_id, "id": period_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Period not found.")
    await db.commit()
    return dict(row)


# ── FIN-007: Currency & exchange rates ───────────────────────────

@router.get("/exchange-rates")
async def list_exchange_rates(
    db: AsyncSession = Depends(get_db),
    from_currency: Optional[str] = Query(None),
    to_currency: Optional[str] = Query(None),
    rate_date: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """FIN-007: List exchange rates."""
    conditions = ["er.is_active = TRUE"]
    params: dict[str, Any] = {}
    if from_currency:
        conditions.append("lv_from.lookup_code = :from_curr")
        params["from_curr"] = from_currency
    if to_currency:
        conditions.append("lv_to.lookup_code = :to_curr")
        params["to_curr"] = to_currency
    if rate_date:
        conditions.append("er.rate_date = CAST(:rate_date AS date)")
        params["rate_date"] = rate_date

    result = await db.execute(text(f"""
        SELECT er.*,
               lv_from.lookup_code AS from_currency_code,
               lv_to.lookup_code   AS to_currency_code
        FROM tms.exchange_rates er
        LEFT JOIN tms.lookup_values lv_from ON lv_from.lookup_value_id = er.from_currency_id
        LEFT JOIN tms.lookup_values lv_to   ON lv_to.lookup_value_id   = er.to_currency_id
        WHERE {' AND '.join(conditions)}
        ORDER BY er.rate_date DESC
        LIMIT 50
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/exchange-rates", status_code=201)
async def create_exchange_rate(
    payload: ExchangeRateCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-007: Add or update exchange rate."""
    # Get currency lookup ids
    from_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :code LIMIT 1
    """), {"code": payload.from_currency})
    from_id = from_result.scalar()

    to_result = await db.execute(text("""
        SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code = :code LIMIT 1
    """), {"code": payload.to_currency})
    to_id = to_result.scalar()

    rate_date = _date.fromisoformat(payload.rate_date)
    result = await db.execute(text("""
        INSERT INTO tms.exchange_rates
            (from_currency_id, to_currency_id, rate_date, exchange_rate, rate_type, source)
        VALUES
            (CAST(:from_id AS uuid), CAST(:to_id AS uuid), :rate_date, :rate, :rate_type, :source)
        RETURNING exchange_rate_id
    """), {
        "from_id":   str(from_id) if from_id else None,
        "to_id":     str(to_id) if to_id else None,
        "rate_date": rate_date,
        "rate":      payload.rate,
        "rate_type": payload.rate_type,
        "source":    payload.source,
    })
    await db.commit()
    return {"exchange_rate_id": str(result.scalar()), **payload.model_dump()}


@router.post("/convert")
async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    rate_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-007: Convert amount between currencies using latest rate."""
    if from_currency == to_currency:
        return {"converted_amount": amount, "rate": 1.0, "from": from_currency, "to": to_currency}

    target_date = _date.fromisoformat(rate_date) if rate_date else _date.today()

    rate_result = await db.execute(text("""
        SELECT er.exchange_rate FROM tms.exchange_rates er
        JOIN tms.lookup_values lv_from ON lv_from.lookup_value_id = er.from_currency_id
        JOIN tms.lookup_values lv_to   ON lv_to.lookup_value_id   = er.to_currency_id
        WHERE lv_from.lookup_code = :from_curr AND lv_to.lookup_code = :to_curr
          AND er.rate_date <= :rate_date AND er.is_active = TRUE
        ORDER BY er.rate_date DESC LIMIT 1
    """), {"from_curr": from_currency, "to_curr": to_currency, "rate_date": target_date})
    rate_row = rate_result.mappings().one_or_none()

    if not rate_row:
        raise HTTPException(404, f"No exchange rate found for {from_currency}/{to_currency}")

    rate = float(rate_row["exchange_rate"])
    converted = round(amount * rate, 4)
    return {"original_amount": amount, "converted_amount": converted,
            "rate": rate, "from": from_currency, "to": to_currency}


# ── FIN-008: Tax calculations ─────────────────────────────────────

@router.post("/tax/calculate", status_code=201)
async def calculate_tax(
    payload: TaxCalcRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-008: Calculate tax based on jurisdiction rules."""
    # Find applicable tax rule
    rule_result = await db.execute(text("""
        SELECT tr.tax_rule_id, lv_type.lookup_code AS tax_type,
               tr.effective_rate, tr.jurisdiction_id
        FROM tms.tax_rules tr
        LEFT JOIN tms.lookup_values lv_type ON lv_type.lookup_value_id = tr.tax_type_id
        WHERE tr.is_active = TRUE
        ORDER BY tr.priority DESC LIMIT 1
    """))
    rule = rule_result.mappings().one_or_none()

    if not rule:
        return {"taxable_amount": payload.taxable_amount, "tax_amount": 0,
                "tax_rate": 0, "message": "No applicable tax rule found."}

    rule = dict(rule)
    tax_rate = float(rule.get("effective_rate") or 0)
    tax_amount = round(payload.taxable_amount * tax_rate / 100, 4)

    result = await db.execute(text("""
        INSERT INTO tms.tax_calculations
            (shipment_id, carrier_invoice_id, client_bill_id,
             tax_rule_id, taxable_amount, tax_rate, tax_amount,
             tax_code, jurisdiction)
        VALUES
            (CAST(:shipment_id AS uuid), CAST(:inv_id AS uuid), CAST(:bill_id AS uuid),
             CAST(:rule_id AS uuid), :taxable, :rate, :tax_amount,
             :tax_code, :jurisdiction)
        RETURNING tax_calc_id
    """), {
        "shipment_id": payload.shipment_id,
        "inv_id":      payload.carrier_invoice_id,
        "bill_id":     payload.client_bill_id,
        "rule_id":     str(rule["tax_rule_id"]),
        "taxable":     payload.taxable_amount,
        "rate":        tax_rate,
        "tax_amount":  tax_amount,
        "tax_code":    payload.tax_code,
        "jurisdiction":payload.jurisdiction,
    })
    await db.commit()
    return {
        "tax_calc_id":    str(result.scalar()),
        "taxable_amount": payload.taxable_amount,
        "tax_rate":       tax_rate,
        "tax_amount":     tax_amount,
        "tax_type":       rule.get("tax_type"),
    }


# ── FIN-009: Financial reconciliation ────────────────────────────

@router.post("/reconcile/{shipment_id}", status_code=201)
async def reconcile_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-009: Reconcile all financial dimensions for a shipment."""

    async def _scalar(sql, params=None):
        r = await db.execute(text(sql), params or {"id": shipment_id})
        return float(r.scalar() or 0)

    planned    = await _scalar("SELECT COALESCE(SUM(amount),0) FROM tms.shipment_costs WHERE shipment_id=CAST(:id AS uuid)")
    tendered   = await _scalar("SELECT COALESCE(SUM(offered_amount),0) FROM tms.tenders WHERE shipment_id=CAST(:id AS uuid) AND tender_status_id IN (SELECT lookup_value_id FROM tms.lookup_values WHERE lookup_code='SENT')")
    accrued    = await _scalar("SELECT COALESCE(SUM(accrual_amount),0) FROM tms.accruals WHERE shipment_id=CAST(:id AS uuid) AND status='open'")
    actual     = await _scalar("SELECT COALESCE(SUM(invoice_total_amount),0) FROM tms.carrier_invoices WHERE shipment_id=CAST(:id AS uuid) AND status NOT IN ('canceled','reversed')")
    approved   = await _scalar("SELECT COALESCE(SUM(voucher_total_amount),0) FROM tms.vouchers v JOIN tms.carrier_invoices ci ON ci.carrier_invoice_id=v.carrier_invoice_id WHERE ci.shipment_id=CAST(:id AS uuid)")
    paid_amt   = await _scalar("SELECT COALESCE(SUM(payment_amount),0) FROM tms.vouchers v JOIN tms.carrier_invoices ci ON ci.carrier_invoice_id=v.carrier_invoice_id WHERE ci.shipment_id=CAST(:id AS uuid) AND v.payment_status IN ('paid','confirmed')")
    billed     = await _scalar("SELECT COALESCE(SUM(total_bill_amount),0) FROM tms.client_bills cb JOIN tms.client_bill_lines cbl ON cbl.client_bill_id=cb.client_bill_id WHERE cbl.shipment_id=CAST(:id AS uuid) AND cb.status NOT IN ('canceled','credited')")
    received   = await _scalar("SELECT COALESCE(SUM(cbp.received_amount),0) FROM tms.client_bill_payments cbp JOIN tms.client_bills cb ON cb.client_bill_id=cbp.client_bill_id JOIN tms.client_bill_lines cbl ON cbl.client_bill_id=cb.client_bill_id WHERE cbl.shipment_id=CAST(:id AS uuid)")
    client_charges = await _scalar("SELECT COALESCE(SUM(amount),0) FROM tms.client_charges WHERE shipment_id=CAST(:id AS uuid)")

    gross_margin = client_charges - actual if client_charges > 0 else billed - actual
    margin_pct   = round(gross_margin / client_charges * 100, 2) if client_charges > 0 else 0

    variances = {}
    if abs(actual - planned) > 0.01:
        variances["cost_vs_planned"]   = round(actual - planned, 2)
    if abs(actual - accrued) > 0.01:
        variances["actual_vs_accrued"] = round(actual - accrued, 2)
    if abs(approved - actual) > 0.01:
        variances["approved_vs_actual"]= round(approved - actual, 2)
    if abs(received - billed) > 0.01:
        variances["received_vs_billed"]= round(received - billed, 2)

    is_reconciled = len(variances) == 0

    # Upsert reconciliation record
    await db.execute(text("""
        INSERT INTO tms.financial_reconciliation
            (shipment_id, planned_cost, tendered_cost, accrued_cost,
             actual_carrier_cost, approved_payable, paid_amount,
             client_bill_amount, received_amount,
             gross_margin, margin_pct, is_reconciled, variances, updated_at)
        VALUES
            (CAST(:id AS uuid), :planned, :tendered, :accrued,
             :actual, :approved, :paid_amt,
             :billed, :received,
             :margin, :margin_pct, :is_recon, CAST(:variances AS jsonb), NOW())
        ON CONFLICT (shipment_id) DO UPDATE SET
            planned_cost        = :planned,
            tendered_cost       = :tendered,
            accrued_cost        = :accrued,
            actual_carrier_cost = :actual,
            approved_payable    = :approved,
            paid_amount         = :paid_amt,
            client_bill_amount  = :billed,
            received_amount     = :received,
            gross_margin        = :margin,
            margin_pct          = :margin_pct,
            is_reconciled       = :is_recon,
            variances           = CAST(:variances AS jsonb),
            updated_at          = NOW()
    """), {
        "id":        shipment_id,
        "planned":   planned,  "tendered":  tendered,  "accrued":  accrued,
        "actual":    actual,   "approved":  approved,  "paid_amt": paid_amt,
        "billed":    billed,   "received":  received,
        "margin":    gross_margin, "margin_pct": margin_pct,
        "is_recon":  is_reconciled,
        "variances": _json.dumps(variances),
    })
    await db.commit()

    return {
        "shipment_id":        shipment_id,
        "is_reconciled":      is_reconciled,
        "planned_cost":       planned,
        "tendered_cost":      tendered,
        "accrued_cost":       accrued,
        "actual_carrier_cost":actual,
        "approved_payable":   approved,
        "paid_amount":        paid_amt,
        "client_bill_amount": billed,
        "received_amount":    received,
        "gross_margin":       round(gross_margin, 2),
        "margin_pct":         margin_pct,
        "variances":          variances,
    }


@router.get("/reconcile/{shipment_id}")
async def get_reconciliation(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.financial_reconciliation
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "No reconciliation found. Run POST /reconcile/{id} first.")
    return dict(row)


# ── FIN-010: Financial approvals & segregation of duties ─────────

@router.post("/approvals", status_code=201)
async def request_approval(
    payload: ApprovalCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-010: Request financial approval (rate override, invoice, billing, etc.)"""
    user_id = user.get("email", "system")
    valid_types = ["rate_override","invoice_approval","billing_adjustment",
                   "allocation_adjustment","payment_release","accounting_export"]
    if payload.approval_type not in valid_types:
        raise HTTPException(400, f"Invalid approval_type. Valid: {', '.join(valid_types)}")

    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(hours=payload.expires_hours)

    result = await db.execute(text("""
        INSERT INTO tms.financial_approvals
            (approval_type, entity_type, entity_id, requested_by,
             amount, notes, expires_at)
        VALUES
            (:approval_type, :entity_type, CAST(:entity_id AS uuid),
             :requested_by, CAST(:amount AS numeric), :notes, :expires_at)
        RETURNING approval_id
    """), {
        "approval_type": payload.approval_type,
        "entity_type":   payload.entity_type,
        "entity_id":     payload.entity_id,
        "requested_by":  user_id,
        "amount":        payload.amount,
        "notes":         payload.notes,
        "expires_at":    expires_at,
    })
    await db.commit()
    return {"approval_id": str(result.scalar()), **payload.model_dump(),
            "requested_by": user_id, "status": "pending"}


@router.patch("/approvals/{approval_id}")
async def action_approval(
    approval_id: str,
    payload: ApprovalAction,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """FIN-010: Approve, reject, or withdraw a financial approval request."""
    user_id = user.get("email", "system")
    if payload.action not in ("approve","reject","withdraw"):
        raise HTTPException(400, "Action must be: approve, reject, or withdraw.")

    # SOD check: approver cannot be the requester
    req_result = await db.execute(text("""
        SELECT requested_by, status FROM tms.financial_approvals
        WHERE approval_id = CAST(:id AS uuid)
    """), {"id": approval_id})
    req = req_result.mappings().one_or_none()
    if not req:
        raise HTTPException(404, "Approval not found.")
    if req["status"] != "pending":
        raise HTTPException(422, f"Approval is already '{req['status']}'.")
    if req["requested_by"] == user_id and payload.action == "approve":
        raise HTTPException(403, "Segregation of duties: cannot approve your own request.")

    status_map = {"approve": "approved", "reject": "rejected", "withdraw": "withdrawn"}
    new_status = status_map[payload.action]

    col = "approved" if payload.action == "approve" else "rejected"
    await db.execute(text(f"""
        UPDATE tms.financial_approvals
        SET status      = :status,
            {col}_by    = :user,
            {col}_at    = NOW(),
            rejection_reason = CASE WHEN :action = 'reject' THEN :reason ELSE rejection_reason END
        WHERE approval_id = CAST(:id AS uuid)
    """), {
        "status": new_status, "user": user_id,
        "action": payload.action, "reason": payload.reason, "id": approval_id
    })
    await db.commit()
    return {"approval_id": approval_id, "status": new_status, "actioned_by": user_id}


@router.get("/approvals")
async def list_approvals(
    db: AsyncSession = Depends(get_db),
    approval_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """FIN-010: List financial approvals with filtering."""
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if approval_type:
        conditions.append("approval_type = :approval_type")
        params["approval_type"] = approval_type
    if status:
        conditions.append("status = :status")
        params["status"] = status
    result = await db.execute(text(f"""
        SELECT * FROM tms.financial_approvals
        WHERE {' AND '.join(conditions)}
        ORDER BY requested_at DESC LIMIT 100
    """), params)
    return [dict(r) for r in result.mappings().all()]
