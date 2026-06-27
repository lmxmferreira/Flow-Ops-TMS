"""
routers/allocation.py
TMS-ALLOC-001 through TMS-ALLOC-015: Cost Allocation Engine
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from decimal import Decimal
import json as _json

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class AllocationRuleCreate(BaseModel):
    rule_name: str
    charge_category: Optional[str] = None
    charge_code: Optional[str] = None
    customer_party_id: Optional[str] = None
    carrier_id: Optional[str] = None
    transport_mode: Optional[str] = None
    allocation_method: str = "equal"
    allocation_level: str = "po_line"
    responsible_type: Optional[str] = None
    gl_account_code: Optional[str] = None
    priority: int = 0

class CalculateRequest(BaseModel):
    allocation_basis: str = "rule_based"
    # rule_based | weight | volume | value | equal | pallet_count | quantity
    allocation_levels: list[str] = ["po_line"]
    charge_categories: Optional[list[str]] = None
    # if None, allocate all charge types
    replace_existing: bool = True
    gl_account_mapping: Optional[dict] = None
    # {"LINEHAUL": "5010", "FSC": "5020"}

class ManualAdjustRequest(BaseModel):
    allocation_id: str
    new_amount: float
    reason_code: str
    notes: Optional[str] = None

class RecalcRequest(BaseModel):
    trigger_reason: str = "cost_change"
    # cost_change | quantity_change | rule_change | manual
    allocation_basis: Optional[str] = None
    preserve_manual_adjustments: bool = True


# ── ALLOC-004: Allocation rules CRUD ─────────────────────────────

@router.get("/rules")
async def list_allocation_rules(
    db: AsyncSession = Depends(get_db),
    charge_category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    user=Depends(get_current_user),
):
    """ALLOC-004: List configurable allocation rules."""
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if charge_category:
        conditions.append("(charge_category = :cat OR charge_category IS NULL)")
        params["cat"] = charge_category
    if active_only:
        conditions.append("is_active = TRUE")
    result = await db.execute(text(f"""
        SELECT r.*, p.party_name AS customer_name
        FROM tms.alloc_rules r
        LEFT JOIN tms.parties p ON p.party_id = r.customer_party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY r.priority DESC, r.charge_category NULLS LAST
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/rules", status_code=201)
async def create_allocation_rule(
    payload: AllocationRuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """ALLOC-004: Create a new allocation rule."""
    result = await db.execute(text("""
        INSERT INTO tms.alloc_rules
            (rule_name, charge_category, charge_code, customer_party_id,
             carrier_id, transport_mode, allocation_method, allocation_level,
             responsible_type, gl_account_code, priority, created_by)
        VALUES
            (:rule_name, :charge_category, :charge_code, CAST(:customer_party_id AS uuid),
             CAST(:carrier_id AS uuid), :transport_mode, :allocation_method, :allocation_level,
             :responsible_type, :gl_account_code, :priority, :created_by)
        RETURNING rule_id
    """), {**payload.model_dump(), "created_by": user.get("email","system")})
    await db.commit()
    return {"rule_id": str(result.scalar()), **payload.model_dump()}


# ── ALLOC-001/002/003: Allocation engine ──────────────────────────

@router.post("/calculate/{shipment_id}", status_code=201)
async def calculate_allocation(
    shipment_id: str,
    payload: CalculateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    ALLOC-001/002/003: Full allocation engine.
    Allocates shipment costs across PO lines, stops, customers, projects, cost centers.
    Supports: weight, volume, value, equal, pallet_count, quantity methods.
    """
    user_id = user.get("email", "system")

    # Get current version number
    ver_result = await db.execute(text("""
        SELECT COALESCE(MAX(version_number), 0) AS max_ver
        FROM tms.allocation_versions WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    max_ver = ver_result.scalar() or 0
    new_version = max_ver + 1

    # Load charges to allocate (ALLOC-005: by category)
    cost_conditions = ["sc.shipment_id = CAST(:id AS uuid)"]
    if payload.charge_categories:
        cost_conditions.append("sc.charge_type = ANY(:categories)")
    cost_params: dict[str, Any] = {"id": shipment_id}
    if payload.charge_categories:
        cost_params["categories"] = payload.charge_categories

    costs_result = await db.execute(text(f"""
        SELECT sc.cost_id, sc.charge_code, sc.charge_type, sc.amount,
               sc.currency, sc.override_reason,
               ccm.charge_category, ccm.gl_account_code AS default_gl
        FROM tms.shipment_costs sc
        LEFT JOIN tms.charge_code_master ccm ON ccm.charge_code = sc.charge_code
        WHERE {' AND '.join(cost_conditions)}
        ORDER BY sc.charge_type, sc.charge_code
    """), cost_params)
    costs = [dict(r) for r in costs_result.mappings().all()]

    if not costs:
        raise HTTPException(422, "No charges found to allocate.")

    # Clear existing allocations if requested
    if payload.replace_existing:
        await db.execute(text("""
            UPDATE tms.charge_allocations
            SET is_current_version = FALSE
            WHERE shipment_id = CAST(:id AS uuid) AND is_current_version = TRUE
              AND is_manual_adjustment = FALSE
        """), {"id": shipment_id})

    total_source = sum(Decimal(str(c["amount"])) for c in costs)
    saved_allocations = []

    for cost in costs:
        charge_amount = Decimal(str(cost["amount"]))
        charge_cat = cost.get("charge_category") or cost.get("charge_type", "freight")
        gl_code = (payload.gl_account_mapping or {}).get(cost["charge_code"]) or cost.get("default_gl")

        # Find applicable rule (ALLOC-004)
        rule_result = await db.execute(text("""
            SELECT * FROM tms.alloc_rules
            WHERE is_active = TRUE
              AND (charge_category = :cat OR charge_category IS NULL)
              AND (charge_code = :code OR charge_code IS NULL)
            ORDER BY priority DESC, charge_category NULLS LAST
            LIMIT 1
        """), {"cat": charge_cat, "code": cost["charge_code"]})
        rule = rule_result.mappings().one_or_none()
        method = rule["allocation_method"] if rule else payload.allocation_basis
        level = rule["allocation_level"] if rule else (payload.allocation_levels[0] if payload.allocation_levels else "shipment")
        resp_type = rule["responsible_type"] if rule else "customer"

        # Get entities at the allocation level
        entities = await _get_alloc_entities(db, shipment_id, level, method)

        if not entities:
            # Fallback to shipment level
            entities = [{"id": shipment_id, "type": "shipment", "weight": 1, "value": 1, "quantity": 1}]
            level = "shipment"

        # Calculate split (ALLOC-003/009: rounding)
        n = len(entities)
        total_weight = sum(Decimal(str(e.get(method, 1) or 1)) for e in entities)
        running_total = Decimal("0")

        for idx, entity in enumerate(entities):
            is_last = idx == n - 1
            entity_weight = Decimal(str(entity.get(method, 1) or 1))

            if method == "equal":
                alloc_pct = Decimal("100") / n
                if is_last:
                    alloc_amount = charge_amount - running_total
                else:
                    alloc_amount = (charge_amount / n).quantize(Decimal("0.01"))
            elif method in ("weight", "volume", "value", "quantity", "pallet_count", "carton_count"):
                if total_weight == 0:
                    alloc_pct = Decimal("100") / n
                    alloc_amount = (charge_amount / n).quantize(Decimal("0.01"))
                else:
                    alloc_pct = (entity_weight / total_weight * 100).quantize(Decimal("0.0001"))
                    if is_last:
                        alloc_amount = charge_amount - running_total
                    else:
                        alloc_amount = (charge_amount * entity_weight / total_weight).quantize(Decimal("0.01"))
            elif method == "percentage":
                alloc_pct = entity_weight  # entity weight IS the percentage
                alloc_amount = (charge_amount * alloc_pct / 100).quantize(Decimal("0.01"))
            elif method == "fixed":
                alloc_amount = entity_weight  # entity weight IS the fixed amount
                alloc_pct = (alloc_amount / charge_amount * 100).quantize(Decimal("0.0001")) if charge_amount > 0 else Decimal("0")
            else:
                alloc_pct = Decimal("100") / n
                alloc_amount = (charge_amount / n).quantize(Decimal("0.01"))

            running_total += alloc_amount

            # Get entity column
            entity_col = _entity_col(entity["type"])

            # avoid duplicate shipment_id column when entity IS the shipment
            extra_col = f", {entity_col}" if entity_col != "shipment_id" else ""
            extra_val = ", CAST(:entity_id AS uuid)" if entity_col != "shipment_id" else ""
            result = await db.execute(text(f"""
                INSERT INTO tms.charge_allocations
                    (shipment_cost_id, allocation_type{extra_col},
                     shipment_id, allocation_basis, allocation_pct, allocation_amount,
                     currency, charge_category, gl_account_code,
                     responsible_party_type, allocation_version, is_current_version,
                     notes)
                VALUES
                    (CAST(:cost_id AS uuid), :alloc_type{extra_val},
                     CAST(:shipment_id AS uuid), :method, :pct, :amount,
                     :currency, :charge_cat, :gl_code,
                     :resp_type, :version, TRUE,
                     :notes)
                RETURNING allocation_id
            """), {
                "cost_id":    str(cost["cost_id"]),
                "alloc_type": entity["type"],
                "entity_id":  entity["id"],
                "shipment_id":shipment_id,
                "method":     method,
                "pct":        float(alloc_pct),
                "amount":     float(alloc_amount),
                "currency":   cost.get("currency","USD"),
                "charge_cat": charge_cat,
                "gl_code":    gl_code,
                "resp_type":  resp_type,
                "version":    new_version,
                "notes":      f"Auto-allocated v{new_version}: {method} method",
            })
            saved_allocations.append({
                "allocation_id":  str(result.scalar()),
                "charge_code":    cost["charge_code"],
                "charge_category":charge_cat,
                "entity_type":    entity["type"],
                "entity_id":      entity["id"],
                "method":         method,
                "pct":            float(alloc_pct),
                "amount":         float(alloc_amount),
                "gl_account":     gl_code,
                "responsible":    resp_type,
            })

    # ALLOC-009: Verify balance
    total_allocated = sum(Decimal(str(a["amount"])) for a in saved_allocations)
    is_balanced = abs(total_allocated - total_source) < Decimal("0.02")  # penny tolerance

    # Save version snapshot (ALLOC-013)
    await db.execute(text("""
        INSERT INTO tms.allocation_versions
            (shipment_id, version_number, allocation_method,
             total_allocated, total_source, is_balanced,
             triggered_by, snapshot, created_by)
        VALUES
            (CAST(:id AS uuid), :ver, :method,
             :allocated, :source, :balanced,
             :trigger, CAST(:snapshot AS jsonb), :created_by)
    """), {
        "id":          shipment_id,
        "ver":         new_version,
        "method":      payload.allocation_basis,
        "allocated":   float(total_allocated),
        "source":      float(total_source),
        "balanced":    is_balanced,
        "trigger":     "manual",
        "snapshot":    _json.dumps({"allocation_count": len(saved_allocations)}),
        "created_by":  user_id,
    })

    await db.commit()

    return {
        "shipment_id":      shipment_id,
        "version":          new_version,
        "allocation_basis": payload.allocation_basis,
        "total_source":     float(total_source),
        "total_allocated":  float(total_allocated),
        "is_balanced":      is_balanced,
        "variance":         float(total_allocated - total_source),
        "allocation_count": len(saved_allocations),
        "allocations":      saved_allocations,
    }


# ── ALLOC-010: View by entity ─────────────────────────────────────

@router.get("/by-entity/{entity_type}/{entity_id}")
async def get_allocations_by_entity(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    charge_category: Optional[str] = Query(None),
    current_only: bool = Query(True),
    user=Depends(get_current_user),
):
    """
    ALLOC-010: View allocated costs by any entity:
    shipment, order, order_line, po, po_line, customer, supplier,
    department, project, cost_center, GL account.
    """
    col = _entity_col(entity_type)
    conditions = [f"ca.{col} = CAST(:entity_id AS uuid)"]
    params: dict[str, Any] = {"entity_id": entity_id}
    if current_only:
        conditions.append("ca.is_current_version = TRUE")
    if charge_category:
        conditions.append("ca.charge_category = :cat")
        params["cat"] = charge_category

    result = await db.execute(text(f"""
        SELECT ca.*,
               sc.charge_code, sc.charge_type, sc.amount AS source_amount,
               s.shipment_number
        FROM tms.charge_allocations ca
        LEFT JOIN tms.shipment_costs sc ON sc.cost_id = ca.shipment_cost_id
        LEFT JOIN tms.shipments s ON s.shipment_id = ca.shipment_id
        WHERE {' AND '.join(conditions)}
        ORDER BY ca.charge_category, sc.charge_code
    """), params)
    rows = [dict(r) for r in result.mappings().all()]

    # Summary by charge category
    by_cat: dict = {}
    for r in rows:
        cat = r.get("charge_category") or "unknown"
        by_cat.setdefault(cat, {"count": 0, "total": 0})
        by_cat[cat]["count"] += 1
        by_cat[cat]["total"] += float(r["allocation_amount"])

    total = sum(float(r["allocation_amount"]) for r in rows)
    return {
        "entity_type": entity_type,
        "entity_id":   entity_id,
        "total":       round(total, 2),
        "by_category": by_cat,
        "allocations": rows,
    }


@router.get("/summary/{shipment_id}")
async def get_allocation_summary(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """ALLOC-010: Full allocation summary for a shipment."""
    result = await db.execute(text("""
        SELECT ca.allocation_type, ca.charge_category, ca.allocation_basis,
               ca.gl_account_code, ca.responsible_party_type,
               COUNT(*) AS line_count,
               SUM(ca.allocation_amount) AS total_allocated,
               MIN(ca.allocation_amount) AS min_alloc,
               MAX(ca.allocation_amount) AS max_alloc
        FROM tms.charge_allocations ca
        WHERE ca.shipment_id = CAST(:id AS uuid) AND ca.is_current_version = TRUE
        GROUP BY ca.allocation_type, ca.charge_category, ca.allocation_basis,
                 ca.gl_account_code, ca.responsible_party_type
        ORDER BY ca.charge_category, ca.allocation_type
    """), {"id": shipment_id})
    summary = [dict(r) for r in result.mappings().all()]

    # Source total
    source_result = await db.execute(text("""
        SELECT COALESCE(SUM(amount),0) AS total FROM tms.shipment_costs
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    source_total = float(source_result.scalar() or 0)

    alloc_total = sum(float(r["total_allocated"]) for r in summary)

    return {
        "shipment_id":    shipment_id,
        "source_total":   round(source_total, 2),
        "allocated_total":round(alloc_total, 2),
        "variance":       round(alloc_total - source_total, 2),
        "is_balanced":    abs(alloc_total - source_total) < 0.02,
        "summary":        summary,
    }


# ── ALLOC-011: Manual adjustment ──────────────────────────────────

@router.post("/adjust", status_code=201)
async def manual_adjust(
    payload: ManualAdjustRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """ALLOC-011: Manual allocation adjustment with reason code and audit."""
    user_id = user.get("email", "system")

    # Validate reason code
    rc_result = await db.execute(text("""
        SELECT description FROM tms.adjustment_reason_codes
        WHERE reason_code = :code AND is_active = TRUE
    """), {"code": payload.reason_code})
    rc = rc_result.mappings().one_or_none()
    if not rc:
        raise HTTPException(400, f"Invalid reason code: {payload.reason_code}")

    # Load current allocation
    curr_result = await db.execute(text("""
        SELECT * FROM tms.charge_allocations WHERE allocation_id = CAST(:id AS uuid)
    """), {"id": payload.allocation_id})
    curr = curr_result.mappings().one_or_none()
    if not curr:
        raise HTTPException(404, "Allocation not found.")
    curr = dict(curr)

    old_amount = float(curr["allocation_amount"])

    # Mark old as not current
    await db.execute(text("""
        UPDATE tms.charge_allocations SET is_current_version = FALSE
        WHERE allocation_id = CAST(:id AS uuid)
    """), {"id": payload.allocation_id})

    # Create new adjusted version
    entity_col = _entity_col(curr["allocation_type"])
    entity_id = curr.get(entity_col) or curr.get("shipment_id")

    new_pct = float(Decimal(str(payload.new_amount)) / Decimal(str(curr["allocation_amount"])) * Decimal(str(curr["allocation_pct"]))) if float(curr["allocation_amount"]) > 0 else float(curr["allocation_pct"])

    result = await db.execute(text(f"""
        INSERT INTO tms.charge_allocations
            (shipment_cost_id, allocation_type, {entity_col},
             shipment_id, allocation_basis, allocation_pct, allocation_amount,
             currency, charge_category, gl_account_code,
             responsible_party_type, allocation_version,
             is_current_version, is_manual_adjustment,
             adjustment_reason, adjusted_by, adjusted_at, notes)
        VALUES
            (CAST(:cost_id AS uuid), :alloc_type, CAST(:entity_id AS uuid),
             CAST(:shipment_id AS uuid), :method, :pct, :amount,
             :currency, :charge_cat, :gl_code,
             :resp_type, :version,
             TRUE, TRUE,
             :reason, :adjusted_by, NOW(), :notes)
        RETURNING allocation_id
    """), {
        "cost_id":     str(curr["shipment_cost_id"]) if curr.get("shipment_cost_id") else None,
        "alloc_type":  curr["allocation_type"],
        "entity_id":   str(entity_id),
        "shipment_id": str(curr["shipment_id"]),
        "method":      curr["allocation_basis"],
        "pct":         new_pct,
        "amount":      payload.new_amount,
        "currency":    curr.get("currency","USD"),
        "charge_cat":  curr.get("charge_category"),
        "gl_code":     curr.get("gl_account_code"),
        "resp_type":   curr.get("responsible_party_type"),
        "version":     (curr.get("allocation_version") or 1) + 1,
        "reason":      f"{payload.reason_code}: {payload.notes or ''}".strip(": "),
        "adjusted_by": user_id,
        "notes":       payload.notes,
    })
    await db.commit()
    new_id = str(result.scalar())

    return {
        "new_allocation_id": new_id,
        "old_allocation_id": payload.allocation_id,
        "old_amount":        old_amount,
        "new_amount":        payload.new_amount,
        "delta":             round(payload.new_amount - old_amount, 2),
        "reason_code":       payload.reason_code,
        "adjusted_by":       user_id,
    }


# ── ALLOC-012: Recalculation ──────────────────────────────────────

@router.post("/recalculate/{shipment_id}", status_code=201)
async def recalculate_allocation(
    shipment_id: str,
    payload: RecalcRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """ALLOC-012: Recalculate when costs, quantities, or rules change."""
    user_id = user.get("email", "system")

    # Preserve manual adjustments if requested
    manual_adjustments = []
    if payload.preserve_manual_adjustments:
        ma_result = await db.execute(text("""
            SELECT * FROM tms.charge_allocations
            WHERE shipment_id = CAST(:id AS uuid)
              AND is_manual_adjustment = TRUE
              AND is_current_version = TRUE
        """), {"id": shipment_id})
        manual_adjustments = [dict(r) for r in ma_result.mappings().all()]

    # Trigger new calculation
    calc_request = CalculateRequest(
        allocation_basis=payload.allocation_basis or "rule_based",
        replace_existing=True,
    )
    result = await calculate_allocation(shipment_id, calc_request, db, {"email": user_id})

    return {
        **result,
        "trigger_reason":              payload.trigger_reason,
        "preserved_manual_adjustments":len(manual_adjustments),
    }


# ── ALLOC-013: Version history ────────────────────────────────────

@router.get("/versions/{shipment_id}")
async def get_allocation_versions(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """ALLOC-013: Allocation version history for audit and reconciliation."""
    result = await db.execute(text("""
        SELECT * FROM tms.allocation_versions
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY version_number DESC
    """), {"id": shipment_id})
    versions = [dict(r) for r in result.mappings().all()]
    return {"shipment_id": shipment_id, "versions": versions, "version_count": len(versions)}


# ── ALLOC-014: ERP export ─────────────────────────────────────────

@router.get("/export/{shipment_id}")
async def export_allocations(
    shipment_id: str,
    format: str = Query("erp"),
    # erp | accounting | billing | procurement
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """ALLOC-014: Export allocation distributions to ERP/accounting systems."""
    result = await db.execute(text("""
        SELECT
            ca.allocation_id,
            s.shipment_number,
            ca.allocation_type,
            ca.charge_category,
            sc.charge_code,
            sc.description AS charge_description,
            ca.allocation_amount,
            ca.allocation_pct,
            ca.currency,
            ca.gl_account_code,
            ca.responsible_party_type,
            p.party_name AS responsible_party,
            p.party_code AS responsible_party_code,
            pol.purchase_order_line_id,
            po.purchase_order_number,
            pol.line_number AS po_line_number,
            ca.allocation_version,
            ca.updated_at AS as_of
        FROM tms.charge_allocations ca
        JOIN tms.shipments s ON s.shipment_id = ca.shipment_id
        LEFT JOIN tms.shipment_costs sc ON sc.cost_id = ca.shipment_cost_id
        LEFT JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = ca.po_line_id
        LEFT JOIN tms.purchase_orders po ON po.purchase_order_id = pol.purchase_order_id
        LEFT JOIN tms.parties p ON p.party_id = ca.responsible_party_id
        WHERE ca.shipment_id = CAST(:id AS uuid) AND ca.is_current_version = TRUE
        ORDER BY ca.charge_category, ca.allocation_type
    """), {"id": shipment_id})
    rows = [dict(r) for r in result.mappings().all()]

    total = sum(float(r["allocation_amount"]) for r in rows)

    return {
        "export_format":  format,
        "shipment_id":    shipment_id,
        "export_date":    str(__import__('datetime').date.today()),
        "total_exported": round(total, 2),
        "record_count":   len(rows),
        "records":        rows,
    }


# ── ALLOC-015: Validation / balance check ────────────────────────

@router.get("/validate/{shipment_id}")
async def validate_allocation(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    ALLOC-015: Validate allocation completeness and balance.
    Used to prevent invoice approval, payment, or billing when
    allocation is incomplete, invalid, or out of balance.
    """
    # Source total
    src_result = await db.execute(text("""
        SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS count
        FROM tms.shipment_costs WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    src = dict(src_result.mappings().one())

    # Allocated total (current version)
    alloc_result = await db.execute(text("""
        SELECT COALESCE(SUM(allocation_amount),0) AS total, COUNT(*) AS count
        FROM tms.charge_allocations
        WHERE shipment_id = CAST(:id AS uuid) AND is_current_version = TRUE
    """), {"id": shipment_id})
    alloc = dict(alloc_result.mappings().one())

    source_total = float(src["total"])
    alloc_total  = float(alloc["total"])
    variance     = alloc_total - source_total
    is_balanced  = abs(variance) < 0.02

    # Check for unallocated costs
    unalloc_result = await db.execute(text("""
        SELECT sc.cost_id, sc.charge_code, sc.amount
        FROM tms.shipment_costs sc
        WHERE sc.shipment_id = CAST(:id AS uuid)
          AND NOT EXISTS (
              SELECT 1 FROM tms.charge_allocations ca
              WHERE ca.shipment_cost_id = sc.cost_id
                AND ca.is_current_version = TRUE
          )
    """), {"id": shipment_id})
    unallocated = [dict(r) for r in unalloc_result.mappings().all()]

    issues = []
    if not is_balanced:
        issues.append(f"Allocation out of balance by ${abs(variance):.2f}")
    if unallocated:
        issues.append(f"{len(unallocated)} cost line(s) have no allocation")
    if int(alloc["count"]) == 0:
        issues.append("No allocations exist for this shipment")

    return {
        "shipment_id":       shipment_id,
        "is_valid":          len(issues) == 0,
        "can_approve":       len(issues) == 0,
        "source_total":      round(source_total, 2),
        "allocated_total":   round(alloc_total, 2),
        "variance":          round(variance, 2),
        "is_balanced":       is_balanced,
        "unallocated_costs": unallocated,
        "issues":            issues,
        "cost_line_count":   int(src["count"]),
        "allocation_count":  int(alloc["count"]),
    }


# ── Helpers ───────────────────────────────────────────────────────

def _entity_col(entity_type: str) -> str:
    return {
        "shipment":      "shipment_id",
        "stop":          "stop_id",
        "order_release": "release_id",
        "po_header":     "purchase_order_id",
        "po_line":       "po_line_id",
        "customer":      "customer_party_id",
        "project":       "project_id",
        "cost_center":   "cost_center_id",
    }.get(entity_type, "shipment_id")


async def _get_alloc_entities(db, shipment_id: str, level: str, method: str) -> list[dict]:
    """Get entities + allocation weights at the requested level."""
    if level == "po_line":
        result = await db.execute(text("""
            SELECT DISTINCT
                pol.purchase_order_line_id AS id,
                'po_line' AS type,
                COALESCE(pol.ordered_quantity, 1) AS quantity,
                COALESCE(pol.ordered_quantity, 1) AS weight,
                COALESCE(pol.ordered_quantity, 1) AS volume,
                COALESCE(pol.line_value, 1)        AS value,
                1                                  AS pallet_count,
                1                                  AS carton_count
            FROM tms.shipment_order_releases sor
            JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
            JOIN tms.order_release_lines orl ON orl.order_release_id = ore.order_release_id
            JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
            WHERE sor.shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        return [dict(r) for r in result.mappings().all()]

    elif level == "po":
        result = await db.execute(text("""
            SELECT DISTINCT
                pol.purchase_order_id AS id,
                'po_header' AS type,
                COALESCE(SUM(pol.ordered_quantity), 1) AS quantity,
                COALESCE(SUM(pol.ordered_quantity), 1) AS weight,
                COALESCE(SUM(pol.line_value), 1)       AS value,
                1 AS volume, 1 AS pallet_count, 1 AS carton_count
            FROM tms.shipment_order_releases sor
            JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
            JOIN tms.order_release_lines orl ON orl.order_release_id = ore.order_release_id
            JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
            WHERE sor.shipment_id = CAST(:id AS uuid)
            GROUP BY pol.purchase_order_id
        """), {"id": shipment_id})
        return [dict(r) for r in result.mappings().all()]

    elif level == "stop":
        result = await db.execute(text("""
            SELECT shipment_stop_id AS id, 'stop' AS type,
                   1 AS weight, 1 AS value, 1 AS quantity,
                   1 AS volume, 1 AS pallet_count, 1 AS carton_count
            FROM tms.shipment_stops WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        return [dict(r) for r in result.mappings().all()]

    elif level == "customer":
        result = await db.execute(text("""
            SELECT customer_party_id AS id, 'customer' AS type,
                   1 AS weight, 1 AS value, 1 AS quantity,
                   1 AS volume, 1 AS pallet_count, 1 AS carton_count
            FROM tms.shipments WHERE shipment_id = CAST(:id AS uuid)
              AND customer_party_id IS NOT NULL
        """), {"id": shipment_id})
        row = result.mappings().one_or_none()
        return [dict(row)] if row else []

    else:
        return [{"id": shipment_id, "type": "shipment",
                 "weight": 1, "value": 1, "quantity": 1,
                 "volume": 1, "pallet_count": 1, "carton_count": 1}]
