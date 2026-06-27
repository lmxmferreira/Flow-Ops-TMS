"""
routers/e2e.py
TMS-E2E-001 through TMS-E2E-010: End-to-End Process & Traceability
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class LifecycleStageUpdate(BaseModel):
    stage: str
    notes: Optional[str] = None

class ExceptionCreate(BaseModel):
    shipment_id: Optional[str] = None
    entity_type: str
    entity_id: Optional[str] = None
    exception_type: str
    severity: str = "warning"
    description: str
    lifecycle_stage: Optional[str] = None

class ExceptionResolve(BaseModel):
    resolution_notes: str

class TraceabilityLinkCreate(BaseModel):
    shipment_cost_id: Optional[str] = None
    client_charge_id: Optional[str] = None
    rate_card_id: Optional[str] = None
    contract_reference: Optional[str] = None
    carrier_invoice_ref: Optional[str] = None
    client_bill_ref: Optional[str] = None
    voucher_ref: Optional[str] = None
    payment_ref: Optional[str] = None
    is_manual_adjustment: bool = False
    adjustment_reason: Optional[str] = None

class RefIndexCreate(BaseModel):
    ref_number: str
    ref_type: str
    entity_type: str
    entity_id: str
    parent_ref: Optional[str] = None
    parent_type: Optional[str] = None

class QuantityEventUpdate(BaseModel):
    event_type: str
    # released | planned | shipped | delivered | received | canceled
    quantity: float
    uom: Optional[str] = None


# ── E2E-001: Full lifecycle view ──────────────────────────────────

@router.get("/lifecycle/{shipment_id}")
async def get_shipment_lifecycle(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    TMS-E2E-001: Full end-to-end lifecycle view for a shipment.
    Shows all stages from PO through closure with timestamps and status.
    """
    # Get or create lifecycle record
    lc_result = await db.execute(text("""
        SELECT * FROM tms.process_lifecycle
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    lc = lc_result.mappings().one_or_none()

    if not lc:
        # Auto-create
        await db.execute(text("""
            INSERT INTO tms.process_lifecycle (shipment_id, current_stage)
            VALUES (CAST(:id AS uuid), 'planned')
            ON CONFLICT DO NOTHING
        """), {"id": shipment_id})
        await db.commit()
        lc_result = await db.execute(text("""
            SELECT * FROM tms.process_lifecycle WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": shipment_id})
        lc = lc_result.mappings().one_or_none()

    lc = dict(lc)

    # Shipment header
    shp_result = await db.execute(text("""
        SELECT s.shipment_id, s.shipment_number,
               p.party_name AS carrier_name,
               s.customer_party_id,
               pc.party_name AS customer_name
        FROM tms.shipments s
        LEFT JOIN tms.carriers c ON c.carrier_id = s.carrier_id
        LEFT JOIN tms.parties p  ON p.party_id   = c.party_id
        LEFT JOIN tms.parties pc ON pc.party_id  = s.customer_party_id
        WHERE s.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    shp = shp_result.mappings().one_or_none()
    if not shp:
        raise HTTPException(404, "Shipment not found.")
    shp = dict(shp)

    # Linked POs via order releases
    po_result = await db.execute(text("""
        SELECT DISTINCT po.purchase_order_id, po.purchase_order_number, NULL AS po_status
        FROM tms.shipment_order_releases sor
        JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
        JOIN tms.order_release_lines orl ON orl.order_release_id = ore.order_release_id
        JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
        JOIN tms.purchase_orders po ON po.purchase_order_id = pol.purchase_order_id
        WHERE sor.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    linked_pos = [dict(r) for r in po_result.mappings().all()]

    # Costs summary
    cost_result = await db.execute(text("""
        SELECT COUNT(*) AS cost_lines, COALESCE(SUM(amount),0) AS carrier_total
        FROM tms.shipment_costs WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    cost_row = dict(cost_result.mappings().one())

    # Client charges summary
    cc_result = await db.execute(text("""
        SELECT COUNT(*) AS charge_lines, COALESCE(SUM(amount),0) AS client_total
        FROM tms.client_charges WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    cc_row = dict(cc_result.mappings().one())

    # Documents
    doc_result = await db.execute(text("""
        SELECT dt.type_code, d.status, d.created_at
        FROM tms.document_links dl
        JOIN tms.documents d ON d.document_id = dl.document_id
        JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE dl.related_entity_type = 'shipment'
          AND dl.related_entity_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    documents = [dict(r) for r in doc_result.mappings().all()]

    # Allocations
    alloc_result = await db.execute(text("""
        SELECT allocation_type, COUNT(*) AS count, SUM(allocation_amount) AS total
        FROM tms.charge_allocations WHERE shipment_id = CAST(:id AS uuid)
        GROUP BY allocation_type
    """), {"id": shipment_id})
    allocations = [dict(r) for r in alloc_result.mappings().all()]

    # Exceptions
    exc_result = await db.execute(text("""
        SELECT exception_type, severity, description, is_resolved, created_at
        FROM tms.lifecycle_exceptions
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY created_at DESC
    """), {"id": shipment_id})
    exceptions = [dict(r) for r in exc_result.mappings().all()]

    # Build stage timeline
    stages = [
        {"stage": "po_linked",        "label": "PO Linked",          "done": lc.get("po_linked"),          "at": str(lc.get("po_linked_at") or "")},
        {"stage": "released",         "label": "Order Released",      "done": lc.get("released"),           "at": str(lc.get("released_at") or "")},
        {"stage": "shipment_planned", "label": "Shipment Planned",    "done": lc.get("shipment_planned"),   "at": str(lc.get("shipment_planned_at") or "")},
        {"stage": "tendered",         "label": "Tendered to Carrier", "done": lc.get("tendered"),           "at": str(lc.get("tendered_at") or "")},
        {"stage": "tender_accepted",  "label": "Tender Accepted",     "done": lc.get("tender_accepted"),    "at": str(lc.get("tender_accepted_at") or "")},
        {"stage": "in_transit",       "label": "In Transit",          "done": lc.get("in_transit"),         "at": str(lc.get("in_transit_at") or "")},
        {"stage": "delivered",        "label": "Delivered",           "done": lc.get("delivered"),          "at": str(lc.get("delivered_at") or "")},
        {"stage": "costed",           "label": "Costed",              "done": lc.get("costed"),             "at": str(lc.get("costed_at") or "")},
        {"stage": "allocated",        "label": "Costs Allocated",     "done": lc.get("allocated"),          "at": str(lc.get("allocated_at") or "")},
        {"stage": "carrier_invoiced", "label": "Carrier Invoiced",    "done": lc.get("carrier_invoiced"),   "at": str(lc.get("carrier_invoiced_at") or "")},
        {"stage": "audited",          "label": "Audited",             "done": lc.get("audited"),            "at": str(lc.get("audited_at") or "")},
        {"stage": "payment_approved", "label": "Payment Approved",    "done": lc.get("payment_approved"),   "at": str(lc.get("payment_approved_at") or "")},
        {"stage": "client_billed",    "label": "Client Billed",       "done": lc.get("client_billed"),      "at": str(lc.get("client_billed_at") or "")},
        {"stage": "closed",           "label": "Closed",              "done": lc.get("closed"),             "at": str(lc.get("closed_at") or "")},
    ]
    stages_done = sum(1 for s in stages if s["done"])
    pct_complete = round(stages_done / len(stages) * 100, 1)

    return {
        "shipment_id":     shipment_id,
        "shipment_number": shp.get("shipment_number"),
        "carrier":         shp.get("carrier_name"),
        "customer":        shp.get("customer_name"),
        "current_stage":   lc.get("current_stage"),
        "has_exceptions":  lc.get("has_exceptions"),
        "pct_complete":    pct_complete,
        "stages_done":     stages_done,
        "total_stages":    len(stages),
        "stage_timeline":  stages,
        "linked_pos":      linked_pos,
        "financials": {
            "carrier_cost_lines": int(cost_row["cost_lines"]),
            "carrier_total":      float(cost_row["carrier_total"]),
            "client_charge_lines":int(cc_row["charge_lines"]),
            "client_total":       float(cc_row["client_total"]),
        },
        "documents":   documents,
        "allocations": allocations,
        "exceptions":  exceptions,
    }


@router.patch("/lifecycle/{shipment_id}/stage")
async def advance_lifecycle_stage(
    shipment_id: str,
    payload: LifecycleStageUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Advance a shipment's lifecycle stage."""
    stage_map = {
        "po_linked":        ("po_linked", "po_linked_at"),
        "released":         ("released", "released_at"),
        "shipment_planned": ("shipment_planned", "shipment_planned_at"),
        "tendered":         ("tendered", "tendered_at"),
        "tender_accepted":  ("tender_accepted", "tender_accepted_at"),
        "in_transit":       ("in_transit", "in_transit_at"),
        "delivered":        ("delivered", "delivered_at"),
        "costed":           ("costed", "costed_at"),
        "allocated":        ("allocated", "allocated_at"),
        "carrier_invoiced": ("carrier_invoiced", "carrier_invoiced_at"),
        "audited":          ("audited", "audited_at"),
        "payment_approved": ("payment_approved", "payment_approved_at"),
        "client_billed":    ("client_billed", "client_billed_at"),
        "closed":           ("closed", "closed_at"),
    }
    if payload.stage not in stage_map:
        raise HTTPException(400, f"Invalid stage: {payload.stage}")

    flag_col, time_col = stage_map[payload.stage]
    result = await db.execute(text(f"""
        INSERT INTO tms.process_lifecycle
            (shipment_id, {flag_col}, {time_col}, current_stage)
        VALUES (CAST(:id AS uuid), TRUE, NOW(), :stage)
        ON CONFLICT (shipment_id) DO UPDATE SET
            {flag_col}     = TRUE,
            {time_col}     = NOW(),
            current_stage  = :stage,
            updated_at     = NOW()
        RETURNING lifecycle_id, current_stage, updated_at
    """), {"id": shipment_id, "stage": payload.stage})
    await db.commit()
    return dict(result.mappings().one())


# ── E2E-008: Universal reference search ──────────────────────────

@router.get("/search")
async def search_by_reference(
    ref: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    TMS-E2E-008: Search any major reference number and view the complete
    transaction chain. Searches shipment numbers, PO numbers, BOL numbers,
    invoice numbers, tracking numbers, etc.
    """
    # Search reference index
    idx_result = await db.execute(text("""
        SELECT * FROM tms.reference_index
        WHERE ref_number ILIKE :ref AND is_active = TRUE
        ORDER BY ref_type, created_at DESC
    """), {"ref": f"%{ref}%"})
    refs = [dict(r) for r in idx_result.mappings().all()]

    # Also search directly in key tables
    results: dict[str, Any] = {"query": ref, "matches": [], "transaction_chain": {}}

    # Search shipments
    shp_result = await db.execute(text("""
        SELECT shipment_id, shipment_number, 'shipment' AS entity_type
        FROM tms.shipments WHERE shipment_number ILIKE :ref
    """), {"ref": f"%{ref}%"})
    for r in shp_result.mappings().all():
        results["matches"].append(dict(r))

    # Search POs
    po_result = await db.execute(text("""
        SELECT purchase_order_id AS entity_id, purchase_order_number AS ref_number, 'purchase_order' AS entity_type
        FROM tms.purchase_orders WHERE purchase_order_number ILIKE :ref
    """), {"ref": f"%{ref}%"})
    for r in po_result.mappings().all():
        results["matches"].append(dict(r))

    # Search documents (BOL numbers)
    doc_result = await db.execute(text("""
        SELECT d.document_id AS entity_id, d.document_number AS ref_number,
               dt.type_code, 'document' AS entity_type
        FROM tms.documents d
        JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE d.document_number ILIKE :ref
    """), {"ref": f"%{ref}%"})
    for r in doc_result.mappings().all():
        results["matches"].append(dict(r))

    # Add reference index matches
    for r in refs:
        if not any(m.get("entity_id") == str(r["entity_id"]) for m in results["matches"]):
            results["matches"].append(r)

    # Build transaction chain for first shipment match
    shp_match = next((m for m in results["matches"] if m.get("entity_type") == "shipment"), None)
    if shp_match:
        shp_id = str(shp_match.get("shipment_id") or shp_match.get("entity_id", ""))
        if shp_id:
            results["transaction_chain"] = await _build_transaction_chain(db, shp_id)

    results["total_matches"] = len(results["matches"])
    return results


async def _build_transaction_chain(db, shipment_id: str) -> dict:
    """Build the full transaction chain for a shipment."""
    chain: dict = {}

    # POs
    po_r = await db.execute(text("""
        SELECT DISTINCT po.purchase_order_id, po.purchase_order_number
        FROM tms.shipment_order_releases sor
        JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
        JOIN tms.order_release_lines orl ON orl.order_release_id = ore.order_release_id
        JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
        JOIN tms.purchase_orders po ON po.purchase_order_id = pol.purchase_order_id
        WHERE sor.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    chain["purchase_orders"] = [dict(r) for r in po_r.mappings().all()]

    # Releases
    rel_r = await db.execute(text("""
        SELECT sor.order_release_id AS release_id, ore.order_release_number AS release_number
        FROM tms.shipment_order_releases sor
        JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
        WHERE sor.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    chain["order_releases"] = [dict(r) for r in rel_r.mappings().all()]

    # Carrier costs
    cost_r = await db.execute(text("""
        SELECT cost_id, charge_code, amount, currency FROM tms.shipment_costs
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    chain["carrier_costs"] = [dict(r) for r in cost_r.mappings().all()]

    # Client charges
    cc_r = await db.execute(text("""
        SELECT client_charge_id, charge_code, amount, currency FROM tms.client_charges
        WHERE shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    chain["client_charges"] = [dict(r) for r in cc_r.mappings().all()]

    # Documents
    doc_r = await db.execute(text("""
        SELECT d.document_number, dt.type_code, d.status
        FROM tms.document_links dl
        JOIN tms.documents d ON d.document_id = dl.document_id
        LEFT JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE dl.related_entity_type='shipment' AND dl.related_entity_id=CAST(:id AS uuid)
    """), {"id": shipment_id})
    chain["documents"] = [dict(r) for r in doc_r.mappings().all()]

    # Allocations
    alloc_r = await db.execute(text("""
        SELECT allocation_type, SUM(allocation_amount) AS total
        FROM tms.charge_allocations WHERE shipment_id = CAST(:id AS uuid)
        GROUP BY allocation_type
    """), {"id": shipment_id})
    chain["allocations"] = [dict(r) for r in alloc_r.mappings().all()]

    return chain


# ── E2E-007: Charge traceability ──────────────────────────────────

@router.get("/trace/charge/{cost_id}")
async def trace_charge(
    cost_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    TMS-E2E-007: Full traceability from a charge to its source contract,
    rate, accessorial event, adjustment, allocation, invoice, bill, and payment.
    """
    # Load cost line
    cost_result = await db.execute(text("""
        SELECT sc.*, rc.name AS rate_card_name, rc.contract_reference,
               rc.rate_type, rc.version_number AS rate_version,
               l.lane_name
        FROM tms.shipment_costs sc
        LEFT JOIN tms.carrier_rate_cards rc ON rc.rate_card_id = sc.rate_card_id
        LEFT JOIN tms.carrier_rate_lanes l  ON l.lane_id = sc.lane_id
        WHERE sc.cost_id = CAST(:id AS uuid)
    """), {"id": cost_id})
    cost = cost_result.mappings().one_or_none()
    if not cost:
        raise HTTPException(404, "Cost line not found.")
    cost = dict(cost)

    # Client charge linked to this cost
    cc_result = await db.execute(text("""
        SELECT * FROM tms.client_charges WHERE carrier_cost_id = CAST(:id AS uuid)
    """), {"id": cost_id})
    client_charges = [dict(r) for r in cc_result.mappings().all()]

    # Allocations
    alloc_result = await db.execute(text("""
        SELECT * FROM tms.charge_allocations WHERE shipment_cost_id = CAST(:id AS uuid)
    """), {"id": cost_id})
    allocations = [dict(r) for r in alloc_result.mappings().all()]

    # Traceability link
    tl_result = await db.execute(text("""
        SELECT * FROM tms.traceability_links WHERE shipment_cost_id = CAST(:id AS uuid)
    """), {"id": cost_id})
    trace_links = [dict(r) for r in tl_result.mappings().all()]

    return {
        "cost_id":          cost_id,
        "charge_code":      cost.get("charge_code"),
        "charge_type":      cost.get("charge_type"),
        "amount":           float(cost.get("amount", 0)),
        "currency":         cost.get("currency"),
        "is_override":      cost.get("is_override"),
        "source_rate": {
            "rate_card_id":      str(cost.get("rate_card_id")) if cost.get("rate_card_id") else None,
            "rate_card_name":    cost.get("rate_card_name"),
            "contract_ref":      cost.get("contract_reference"),
            "rate_type":         cost.get("rate_type"),
            "rate_version":      cost.get("rate_version"),
            "lane":              cost.get("lane_name"),
        },
        "client_charges":    client_charges,
        "allocations":       allocations,
        "traceability_links":trace_links,
        "audit_trail": {
            "rated_at":     str(cost.get("rated_at")) if cost.get("rated_at") else None,
            "rated_by":     cost.get("rated_by"),
            "override_reason": cost.get("override_reason"),
        },
    }


@router.post("/trace/link", status_code=201)
async def create_traceability_link(
    payload: TraceabilityLinkCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a traceability link connecting a charge to invoice/bill/payment."""
    result = await db.execute(text("""
        INSERT INTO tms.traceability_links
            (shipment_cost_id, client_charge_id, rate_card_id,
             contract_reference, carrier_invoice_ref, client_bill_ref,
             voucher_ref, payment_ref, is_manual_adjustment, adjustment_reason)
        VALUES
            (CAST(:shipment_cost_id AS uuid), CAST(:client_charge_id AS uuid),
             CAST(:rate_card_id AS uuid),
             :contract_reference, :carrier_invoice_ref, :client_bill_ref,
             :voucher_ref, :payment_ref, :is_manual_adjustment, :adjustment_reason)
        RETURNING link_id
    """), payload.model_dump())
    await db.commit()
    return {"link_id": str(result.scalar()), **payload.model_dump()}


# ── E2E-002: PO reference preservation check ─────────────────────

@router.get("/po-references/{shipment_id}")
async def get_po_references(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    TMS-E2E-002: Verify PO and PO line references are preserved
    on every release line and shipment line.
    """
    result = await db.execute(text("""
        SELECT
            po.purchase_order_id,
            po.purchase_order_number,
            pol.purchase_order_line_id,
            pol.line_number        AS po_line_number,
            pol.item_description,
            ore.order_release_id,
            ore.order_release_number,
            orl.order_release_line_id,
            orl.quantity           AS release_qty,
            orl.uom
        FROM tms.shipment_order_releases sor
        JOIN tms.order_releases ore ON ore.order_release_id = sor.order_release_id
        JOIN tms.order_release_lines orl ON orl.order_release_id = ore.order_release_id
        JOIN tms.purchase_order_lines pol ON pol.purchase_order_line_id = orl.purchase_order_line_id
        JOIN tms.purchase_orders po ON po.purchase_order_id = pol.purchase_order_id
        WHERE sor.shipment_id = CAST(:id AS uuid)
        ORDER BY po.purchase_order_number, pol.line_number
    """), {"id": shipment_id})
    lines = [dict(r) for r in result.mappings().all()]

    return {
        "shipment_id":   shipment_id,
        "po_references": lines,
        "po_count":      len({l["purchase_order_id"] for l in lines}),
        "line_count":    len(lines),
        "all_referenced": all(l.get("purchase_order_id") and l.get("purchase_order_line_id") for l in lines),
    }


# ── E2E-003: PO line quantity tracking ───────────────────────────

@router.get("/po-line-quantities/{po_line_id}")
async def get_po_line_quantities(
    po_line_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """TMS-E2E-003: Get quantity status for a PO line across all downstream events."""
    # Try ledger first
    ledger_result = await db.execute(text("""
        SELECT * FROM tms.po_line_quantity_ledger
        WHERE purchase_order_line_id = CAST(:id AS uuid)
    """), {"id": po_line_id})
    ledger = ledger_result.mappings().one_or_none()

    # Get PO line details
    pol_result = await db.execute(text("""
        SELECT pol.*, po.purchase_order_number FROM tms.purchase_order_lines pol
        JOIN tms.purchase_orders po ON po.purchase_order_id = pol.purchase_order_id
        WHERE pol.purchase_order_line_id = CAST(:id AS uuid)
    """), {"id": po_line_id})
    pol = pol_result.mappings().one_or_none()
    if not pol:
        raise HTTPException(404, "PO line not found.")
    pol = dict(pol)

    # Compute from releases if no ledger
    released_result = await db.execute(text("""
        SELECT COALESCE(SUM(orl.quantity),0) AS released_qty
        FROM tms.order_release_lines orl
        WHERE orl.purchase_order_line_id = CAST(:id AS uuid)
    """), {"id": po_line_id})
    released_qty = float(released_result.scalar() or 0)

    ordered_qty = float(pol.get("ordered_quantity") or 0)

    if ledger:
        qty = dict(ledger)
    else:
        qty = {
            "ordered_qty":   ordered_qty,
            "released_qty":  released_qty,
            "planned_qty":   0,
            "shipped_qty":   0,
            "delivered_qty": 0,
            "received_qty":  0,
            "canceled_qty":  0,
            "remaining_qty": max(0, ordered_qty - released_qty),
        }

    return {
        "po_line_id":     po_line_id,
        "po_number":      pol.get("purchase_order_number"),
        "line_number":    pol.get("line_number"),
        "item_description": pol.get("item_description"),
        "quantities":     qty,
        "pct_released":   round(released_qty / ordered_qty * 100, 1) if ordered_qty > 0 else 0,
        "is_fully_released": released_qty >= ordered_qty,
    }


@router.post("/po-line-quantities/{po_line_id}/event")
async def record_quantity_event(
    po_line_id: str,
    payload: QuantityEventUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """TMS-E2E-003: Record a quantity event (shipped, delivered, received, etc.)"""
    col_map = {
        "released":  "released_qty",
        "planned":   "planned_qty",
        "shipped":   "shipped_qty",
        "delivered": "delivered_qty",
        "received":  "received_qty",
        "canceled":  "canceled_qty",
    }
    if payload.event_type not in col_map:
        raise HTTPException(400, f"Invalid event_type. Use: {', '.join(col_map.keys())}")

    col = col_map[payload.event_type]

    # Get ordered qty for ledger init
    pol_r = await db.execute(text("""
        SELECT ordered_quantity FROM tms.purchase_order_lines
        WHERE purchase_order_line_id = CAST(:id AS uuid)
    """), {"id": po_line_id})
    pol_row = pol_r.mappings().one_or_none()
    if not pol_row:
        raise HTTPException(404, "PO line not found.")

    await db.execute(text(f"""
        INSERT INTO tms.po_line_quantity_ledger
            (purchase_order_line_id, ordered_qty, {col}, uom, last_event, last_event_at)
        VALUES
            (CAST(:id AS uuid), :ordered_qty, :qty, :uom, :event, NOW())
        ON CONFLICT (purchase_order_line_id) DO UPDATE SET
            {col}          = tms.po_line_quantity_ledger.{col} + :qty,
            last_event     = :event,
            last_event_at  = NOW(),
            updated_at     = NOW()
    """), {
        "id":          po_line_id,
        "ordered_qty": float(pol_row["ordered_quantity"] or 0),
        "qty":         payload.quantity,
        "uom":         payload.uom or "EA",
        "event":       payload.event_type,
    })
    await db.commit()
    return {"po_line_id": po_line_id, "event": payload.event_type, "quantity": payload.quantity}


# ── E2E-010: Exceptions ───────────────────────────────────────────

@router.get("/exceptions")
async def list_exceptions(
    db: AsyncSession = Depends(get_db),
    severity: Optional[str] = Query(None),
    exception_type: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(False),
    shipment_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """TMS-E2E-010: Exception visibility across the complete transportation lifecycle."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity
    if exception_type:
        conditions.append("exception_type = :exception_type")
        params["exception_type"] = exception_type
    if resolved is not None:
        conditions.append("is_resolved = :resolved")
        params["resolved"] = resolved
    if shipment_id:
        conditions.append("shipment_id = CAST(:shipment_id AS uuid)")
        params["shipment_id"] = shipment_id

    result = await db.execute(text(f"""
        SELECT e.*, s.shipment_number
        FROM tms.lifecycle_exceptions e
        LEFT JOIN tms.shipments s ON s.shipment_id = e.shipment_id
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'error' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,
                 e.created_at DESC
        LIMIT :limit
    """), params)
    rows = [dict(r) for r in result.mappings().all()]

    # Summary counts
    summary_result = await db.execute(text("""
        SELECT severity, COUNT(*) AS count
        FROM tms.lifecycle_exceptions WHERE is_resolved = FALSE
        GROUP BY severity
    """))
    summary = {r["severity"]: int(r["count"]) for r in summary_result.mappings().all()}

    return {
        "exceptions":     rows,
        "count":          len(rows),
        "open_summary":   summary,
        "total_open":     sum(summary.values()),
    }


@router.post("/exceptions", status_code=201)
async def create_exception(
    payload: ExceptionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.lifecycle_exceptions
            (shipment_id, entity_type, entity_id, exception_type,
             severity, description, lifecycle_stage)
        VALUES
            (CAST(:shipment_id AS uuid), :entity_type, CAST(:entity_id AS uuid),
             :exception_type, :severity, :description, :lifecycle_stage)
        RETURNING exception_id
    """), {
        "shipment_id":    payload.shipment_id,
        "entity_type":    payload.entity_type,
        "entity_id":      payload.entity_id,
        "exception_type": payload.exception_type,
        "severity":       payload.severity,
        "description":    payload.description,
        "lifecycle_stage":payload.lifecycle_stage,
    })
    exc_id = str(result.scalar())

    # Update lifecycle exception flag
    if payload.shipment_id:
        await db.execute(text("""
            UPDATE tms.process_lifecycle
            SET has_exceptions  = TRUE,
                exception_count = exception_count + 1,
                updated_at      = NOW()
            WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": payload.shipment_id})

    await db.commit()
    return {"exception_id": exc_id, **payload.model_dump()}


@router.patch("/exceptions/{exception_id}/resolve")
async def resolve_exception(
    exception_id: str,
    payload: ExceptionResolve,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        UPDATE tms.lifecycle_exceptions
        SET is_resolved      = TRUE,
            resolved_by      = :user,
            resolved_at      = NOW(),
            resolution_notes = :notes
        WHERE exception_id = CAST(:id AS uuid)
        RETURNING exception_id, shipment_id, is_resolved
    """), {"user": user_id, "notes": payload.resolution_notes, "id": exception_id})
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Exception not found.")
    return dict(row)


# ── E2E-008: Reference index management ──────────────────────────

@router.post("/references", status_code=201)
async def add_reference(
    payload: RefIndexCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.reference_index
            (ref_number, ref_type, entity_type, entity_id, parent_ref, parent_type)
        VALUES
            (:ref_number, :ref_type, :entity_type, CAST(:entity_id AS uuid),
             :parent_ref, :parent_type)
        RETURNING ref_index_id
    """), payload.model_dump())
    await db.commit()
    return {"ref_index_id": str(result.scalar()), **payload.model_dump()}


# ── E2E-009: History ──────────────────────────────────────────────

@router.get("/history/{entity_type}/{entity_id}")
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    TMS-E2E-009: Historical versions and audit trail for any entity.
    Aggregates from master_data_audit, rerate_log, and lifecycle events.
    """
    history = []

    # Master data audit
    md_result = await db.execute(text("""
        SELECT 'master_data' AS source, action, version_before, version_after,
               changed_fields, performed_by, performed_at AS event_at, notes
        FROM tms.master_data_audit
        WHERE entity_type = :entity_type AND entity_id = CAST(:id AS uuid)
        ORDER BY performed_at DESC
    """), {"entity_type": entity_type, "id": entity_id})
    history.extend([dict(r) for r in md_result.mappings().all()])

    # Rerate log (for shipments)
    if entity_type == "shipment":
        rr_result = await db.execute(text("""
            SELECT 'rerate' AS source, trigger_reason AS action,
                   NULL AS version_before, NULL AS version_after,
                   changed_fields, triggered_by AS performed_by,
                   completed_at AS event_at, notes
            FROM tms.rerate_log WHERE shipment_id = CAST(:id AS uuid)
            ORDER BY completed_at DESC
        """), {"id": entity_id})
        history.extend([dict(r) for r in rr_result.mappings().all()])

        # Lifecycle events
        lc_result = await db.execute(text("""
            SELECT 'lifecycle' AS source, current_stage AS action,
                   NULL AS version_before, NULL AS version_after,
                   NULL AS changed_fields, NULL AS performed_by,
                   updated_at AS event_at, NULL AS notes
            FROM tms.process_lifecycle WHERE shipment_id = CAST(:id AS uuid)
        """), {"id": entity_id})
        history.extend([dict(r) for r in lc_result.mappings().all()])

    # Sort by event_at descending
    history.sort(key=lambda x: str(x.get("event_at") or ""), reverse=True)

    return {
        "entity_type": entity_type,
        "entity_id":   entity_id,
        "history":     history,
        "event_count": len(history),
    }
