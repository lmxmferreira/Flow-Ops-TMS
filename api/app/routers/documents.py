"""
routers/documents.py
TMS-DOC-001 through TMS-DOC-010: Document Management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
import json as _json
import hashlib
import uuid as _uuid

router = APIRouter()


# ── Pydantic Models ───────────────────────────────────────────────

class DocumentTypeCreate(BaseModel):
    type_code: str
    type_name: str
    category: str = "transport"
    description: Optional[str] = None
    requires_signature: bool = False
    is_transmittable: bool = True

class TemplateCreate(BaseModel):
    document_type_id: str
    template_name: str
    template_format: str = "pdf"
    template_body: Optional[str] = None
    customer_party_id: Optional[str] = None
    carrier_id: Optional[str] = None
    country_code: Optional[str] = None
    transport_mode: Optional[str] = None
    shipment_type: Optional[str] = None
    is_default: bool = False

class DocumentCreate(BaseModel):
    document_type_id: str
    document_name: str
    document_format: str = "pdf"
    content_text: Optional[str] = None
    generated_by: str = "system"
    doc_template_id: Optional[str] = None
    expires_at: Optional[str] = None

class AssociateRequest(BaseModel):
    document_id: str
    related_entity_type: str
    related_entity_id: str
    required_flag: bool = False

class GenerateDocumentRequest(BaseModel):
    document_type_code: str
    entity_type: str
    entity_id: str
    doc_template_id: Optional[str] = None
    transmission_method: Optional[str] = None
    transmitted_to: Optional[str] = None
    context_data: Optional[dict] = None

class TransmitRequest(BaseModel):
    method: str  # email | edi | api | portal | print
    recipient: str
    notes: Optional[str] = None

class RequiredRuleCreate(BaseModel):
    rule_name: str
    document_type_id: str
    trigger_event: str
    related_entity_type: str = "shipment"
    transport_mode: Optional[str] = None
    country_code: Optional[str] = None
    customer_party_id: Optional[str] = None
    is_blocking: bool = True

class OCRRequest(BaseModel):
    extraction_fields: list[str] = []
    # e.g. ["invoice_number","total_amount","carrier_name"]


# ── Document Types ────────────────────────────────────────────────

@router.get("/types")
async def list_document_types(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conditions = ["is_active = TRUE"]
    params: dict[str, Any] = {}
    if category:
        conditions.append("category = :category")
        params["category"] = category
    result = await db.execute(text(f"""
        SELECT dt.*, COUNT(d.document_id) AS document_count
        FROM tms.document_types dt
        LEFT JOIN tms.documents d ON d.document_type_id = dt.document_type_id
        WHERE {' AND '.join(conditions)}
        GROUP BY dt.document_type_id
        ORDER BY dt.category, dt.type_name
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/types", status_code=201)
async def create_document_type(
    payload: DocumentTypeCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.document_types
            (type_code, type_name, category, description,
             requires_signature, is_transmittable)
        VALUES (:type_code, :type_name, :category, :description,
                :requires_signature, :is_transmittable)
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


# ── Templates (DOC-003) ───────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    document_type_id: Optional[str] = Query(None),
    customer_party_id: Optional[str] = Query(None),
    transport_mode: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conditions = ["t.is_active = TRUE"]
    params: dict[str, Any] = {}
    if document_type_id:
        conditions.append("t.document_type_id = CAST(:dtid AS uuid)")
        params["dtid"] = document_type_id
    if customer_party_id:
        conditions.append("(t.customer_party_id = CAST(:cid AS uuid) OR t.customer_party_id IS NULL)")
        params["cid"] = customer_party_id
    if transport_mode:
        conditions.append("(t.transport_mode = :mode OR t.transport_mode IS NULL)")
        params["mode"] = transport_mode
    result = await db.execute(text(f"""
        SELECT t.*, dt.type_name, dt.type_code
        FROM tms.doc_templates t
        JOIN tms.document_types dt ON dt.document_type_id = t.document_type_id
        WHERE {' AND '.join(conditions)}
        ORDER BY t.is_default DESC, t.template_name
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/templates", status_code=201)
async def create_template(
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.doc_templates
            (document_type_id, template_name, template_format, template_body,
             customer_party_id, carrier_id, country_code, transport_mode,
             shipment_type, is_default, created_by)
        VALUES
            (CAST(:document_type_id AS uuid), :template_name, :template_format, :template_body,
             CAST(:customer_party_id AS uuid), CAST(:carrier_id AS uuid),
             :country_code, :transport_mode,
             :shipment_type, :is_default, :created_by)
        RETURNING *
    """), {**payload.model_dump(), "created_by": user.get("email","system")})
    await db.commit()
    return dict(result.mappings().one())


# ── Documents (DOC-001/007/008) ────────────────────────────────────

@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    related_entity_type: Optional[str] = Query(None),
    related_entity_id: Optional[str] = Query(None),
    document_type_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(get_current_user),
):
    conditions = ["d.is_current_version = TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if related_entity_type and related_entity_id:
        conditions.append("""d.document_id IN (
            SELECT document_id FROM tms.document_links
            WHERE related_entity_type = :related_entity_type AND related_entity_id = CAST(:related_entity_id AS uuid)
        )""")
        params["related_entity_type"] = related_entity_type
        params["related_entity_id"]   = related_entity_id
    if document_type_code:
        conditions.append("dt.type_code = :type_code")
        params["type_code"] = document_type_code
    if status:
        conditions.append("d.status = :status")
        params["status"] = status

    result = await db.execute(text(f"""
        SELECT d.*, dt.type_name, dt.type_code, dt.category
        FROM tms.documents d
        JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE {' AND '.join(conditions)}
        ORDER BY d.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/generate", status_code=201)
async def generate_document(
    payload: GenerateDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    DOC-001/004: Generate a document for an entity.
    Looks up the best matching template, renders content,
    stores the document, and creates the association.
    """
    user_id = user.get("email", "system")

    # Get document type
    dt_result = await db.execute(text("""
        SELECT * FROM tms.document_types WHERE type_code = :code AND is_active = TRUE
    """), {"code": payload.document_type_code})
    dt = dt_result.mappings().one_or_none()
    if not dt:
        raise HTTPException(400, f"Unknown document type: {payload.document_type_code}")
    dt = dict(dt)

    # Find best template (DOC-003 precedence)
    doc_template_id = payload.doc_template_id
    if not doc_template_id:
        tmpl_result = await db.execute(text("""
            SELECT doc_template_id FROM tms.doc_templates
            WHERE document_type_id = CAST(:dtid AS uuid) AND is_active = TRUE
            ORDER BY is_default DESC, created_at DESC
            LIMIT 1
        """), {"dtid": str(dt["document_type_id"])})
        tmpl_row = tmpl_result.mappings().one_or_none()
        if tmpl_row:
            doc_template_id = str(tmpl_row["doc_template_id"])

    # Generate document number
    doc_number = f"{payload.document_type_code}-{str(_uuid.uuid4())[:8].upper()}"

    # Generate simple content if context_data provided
    content_text = None
    if payload.context_data:
        lines = [f"Document: {dt['type_name']}", f"Number: {doc_number}", ""]
        for k, v in payload.context_data.items():
            lines.append(f"{k.replace('_', ' ').title()}: {v}")
        content_text = "\n".join(lines)

    # Store document
    doc_result = await db.execute(text("""
        INSERT INTO tms.documents
            (tms_document_type_id, template_id, document_number, document_name,
             document_format, content_text, status,
             generated_by, transmission_method, transmitted_to,
             created_by)
        VALUES
            (CAST(:document_type_id AS uuid), CAST(:doc_template_id AS uuid),
             :document_number, :document_name,
             'pdf', :content_text, 'generated',
             :generated_by, :transmission_method, :transmitted_to,
             :created_by)
        RETURNING document_id
    """), {
        "document_type_id":    str(dt["document_type_id"]),
        "doc_template_id":         doc_template_id,
        "document_number":     doc_number,
        "document_name":       f"{dt['type_name']} - {doc_number}",
        "content_text":        content_text,
        "generated_by":        "system",
        "transmission_method": payload.transmission_method,
        "transmitted_to":      payload.transmitted_to,
        "created_by":          user_id,
    })
    doc_id = str(doc_result.scalar())

    # Associate with entity
    await db.execute(text("""
        INSERT INTO tms.document_links
            (document_id, related_entity_type, related_entity_id)
        VALUES
            (CAST(:doc_id AS uuid), :entity_type, CAST(:entity_id AS uuid))
    """), {"doc_id": doc_id, "entity_type": payload.entity_type, "entity_id": payload.entity_id})

    await db.commit()

    return {
        "document_id":    doc_id,
        "document_number":doc_number,
        "document_type":  dt["type_code"],
        "type_name":      dt["type_name"],
        "status":         "generated",
            "related_entity_type": payload.entity_type,
            "related_entity_id":   payload.entity_id,
        "doc_template_id":    doc_template_id,
        "generated_by":   user_id,
    }


@router.post("/upload", status_code=201)
async def upload_document(
    document_type_code: str,
    related_entity_type: str,
    related_entity_id: str,
    upload_source: str = "user",
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """DOC-007: Upload a document from any source."""
    user_id = user.get("email", "system")

    dt_result = await db.execute(text("""
        SELECT * FROM tms.document_types WHERE type_code = :code AND is_active = TRUE
    """), {"code": document_type_code})
    dt = dt_result.mappings().one_or_none()
    if not dt:
        raise HTTPException(400, f"Unknown document type: {document_type_code}")
    dt = dict(dt)

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    doc_number = f"{document_type_code}-UP-{str(_uuid.uuid4())[:8].upper()}"

    doc_result = await db.execute(text("""
        INSERT INTO tms.documents
            (document_type_id, document_number, document_name, document_format,
             content_data, file_size_bytes, file_hash, status,
             generated_by, upload_source, created_by)
        VALUES
            (CAST(:document_type_id AS uuid), :document_number, :document_name,
             :document_format, :content_data, :file_size, :file_hash, 'generated',
             :generated_by, :upload_source, :created_by)
        RETURNING document_id
    """), {
        "document_type_id": str(dt["document_type_id"]),
        "document_number":  doc_number,
        "document_name":    file.filename or doc_number,
        "document_format":  file.filename.split(".")[-1] if file.filename and "." in file.filename else "bin",
        "content_data":     content,
        "file_size":        len(content),
        "file_hash":        file_hash,
        "generated_by":     upload_source,
        "upload_source":    upload_source,
        "created_by":       user_id,
    })
    doc_id = str(doc_result.scalar())

    await db.execute(text("""
        INSERT INTO tms.document_links (document_id, related_entity_type, related_entity_id, required_flag)
        VALUES (CAST(:doc_id AS uuid), :related_entity_type, CAST(:related_entity_id AS uuid), TRUE)
    """), {"doc_id": doc_id, "related_entity_type": related_entity_type, "related_entity_id": related_entity_id})

    await db.commit()

    return {
        "document_id":    doc_id,
        "document_number":doc_number,
        "document_type":  document_type_code,
        "file_name":      file.filename,
        "file_size":      len(content),
        "file_hash":      file_hash,
        "upload_source":  upload_source,
        "related_entity_type":    related_entity_type,
        "related_entity_id":      related_entity_id,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT d.*, dt.type_name, dt.type_code, dt.category,
               dt.requires_signature, dt.is_transmittable
        FROM tms.documents d
        JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE d.document_id = CAST(:id AS uuid)
    """), {"id": document_id})
    doc = result.mappings().one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found.")
    doc = dict(doc)
    # Don't return binary content in list view
    doc.pop("content_data", None)

    # Get associations
    assoc_result = await db.execute(text("""
        SELECT * FROM tms.document_links WHERE document_id = CAST(:id AS uuid)
    """), {"id": document_id})
    doc["associations"] = [dict(r) for r in assoc_result.mappings().all()]

    # Get version history
    ver_result = await db.execute(text("""
        SELECT document_id, document_number, version_number, status, created_at, created_by
        FROM tms.documents
        WHERE parent_document_id = CAST(:id AS uuid) OR document_id = CAST(:id AS uuid)
        ORDER BY version_number
    """), {"id": document_id})
    doc["versions"] = [dict(r) for r in ver_result.mappings().all()]

    return doc


@router.patch("/{document_id}/status")
async def update_document_status(
    document_id: str,
    status: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    valid = ["draft","generated","sent","delivered","signed","archived","voided"]
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(valid)}")
    result = await db.execute(text("""
        UPDATE tms.documents SET status = :status, updated_at = NOW()
        WHERE document_id = CAST(:id AS uuid) RETURNING document_id, status
    """), {"status": status, "id": document_id})
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Document not found.")
    return dict(row)


@router.post("/{document_id}/transmit")
async def transmit_document(
    document_id: str,
    payload: TransmitRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """DOC-001: Transmit a document via email, EDI, API, portal, or print."""
    from datetime import datetime, timezone
    result = await db.execute(text("""
        UPDATE tms.documents
        SET status              = 'sent',
            transmitted_at      = NOW(),
            transmitted_to      = :recipient,
            transmission_method = :method,
            updated_at          = NOW()
        WHERE document_id = CAST(:id AS uuid)
        RETURNING document_id, document_number, status, transmitted_at
    """), {"recipient": payload.recipient, "method": payload.method, "id": document_id})
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Document not found.")
    return {
        "document_id":   str(row["document_id"]),
        "status":        row["status"],
        "transmitted_to":payload.recipient,
        "method":        payload.method,
        "transmitted_at":str(row["transmitted_at"]),
    }


@router.post("/{document_id}/new-version", status_code=201)
async def create_document_version(
    document_id: str,
    payload: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """DOC-008: Create a new version of an existing document."""
    user_id = user.get("email", "system")

    # Load current doc
    curr = await db.execute(text("""
        SELECT * FROM tms.documents WHERE document_id = CAST(:id AS uuid)
    """), {"id": document_id})
    curr = curr.mappings().one_or_none()
    if not curr:
        raise HTTPException(404, "Document not found.")
    curr = dict(curr)

    next_ver = curr["version_number"] + 1
    doc_number = f"{curr['document_number']}-v{next_ver}"

    # Mark old version as not current
    await db.execute(text("""
        UPDATE tms.documents SET is_current_version = FALSE, updated_at = NOW()
        WHERE document_id = CAST(:id AS uuid)
    """), {"id": document_id})

    # Create new version
    new_result = await db.execute(text("""
        INSERT INTO tms.documents
            (document_type_id, document_number, document_name, document_format,
             content_text, version_number, parent_document_id,
             is_current_version, status, generated_by, created_by)
        VALUES
            (CAST(:dtid AS uuid), :doc_number, :doc_name, :fmt,
             :content, :ver, CAST(:parent_id AS uuid),
             TRUE, 'draft', :gen_by, :created_by)
        RETURNING document_id, version_number
    """), {
        "dtid":       str(curr["document_type_id"]),
        "doc_number": doc_number,
        "doc_name":   payload.document_name,
        "fmt":        payload.document_format,
        "content":    payload.content_text,
        "ver":        next_ver,
        "parent_id":  str(curr.get("parent_document_id") or document_id),
        "gen_by":     payload.generated_by,
        "created_by": user_id,
    })
    await db.commit()
    row = dict(new_result.mappings().one())
    return {"message": f"Version {next_ver} created.", **row}


# ── Document Associations (DOC-005) ───────────────────────────────

@router.post("/associate", status_code=201)
async def associate_document(
    payload: AssociateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.document_links
            (document_id, related_entity_type, related_entity_id, required_flag)
        VALUES
            (CAST(:document_id AS uuid), :related_entity_type, CAST(:related_entity_id AS uuid), :required_flag)
        RETURNING document_link_id
    """), payload.model_dump())
    await db.commit()
    return {"document_link_id": str(result.scalar()), **payload.model_dump()}


@router.get("/for/{related_entity_type}/{related_entity_id}")
async def get_documents_for_entity(
    related_entity_type: str,
    related_entity_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT d.document_id, d.document_number, d.document_name,
               d.document_format, d.status, d.version_number,
               d.generated_by, d.transmitted_at, d.transmission_method,
               d.file_size_bytes, d.created_at,
               dt.type_code, dt.type_name, dt.category,
               da.required_flag
        FROM tms.document_links da
        JOIN tms.documents      d  ON d.document_id       = da.document_id
        JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE da.related_entity_type = :related_entity_type
          AND da.related_entity_id   = CAST(:related_entity_id AS uuid)
          AND d.is_current_version = TRUE
        ORDER BY da.required_flag DESC, d.created_at DESC
    """), {"related_entity_type": related_entity_type, "related_entity_id": related_entity_id})
    docs = [dict(r) for r in result.mappings().all()]
    return {
        "related_entity_type": related_entity_type,
        "related_entity_id":   related_entity_id,
        "documents":   docs,
        "count":       len(docs),
    }


# ── Required Document Rules (DOC-006) ─────────────────────────────

@router.get("/required-rules")
async def list_required_rules(
    db: AsyncSession = Depends(get_db),
    trigger_event: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    conditions = ["r.is_active = TRUE"]
    params: dict[str, Any] = {}
    if trigger_event:
        conditions.append("r.trigger_event = :trigger_event")
        params["trigger_event"] = trigger_event
    result = await db.execute(text(f"""
        SELECT r.*, dt.type_name, dt.type_code
        FROM tms.document_required_rules r
        JOIN tms.document_types dt ON dt.document_type_id = r.document_type_id
        WHERE {' AND '.join(conditions)}
        ORDER BY r.trigger_event, dt.type_name
    """), params)
    return [dict(r) for r in result.mappings().all()]


@router.post("/required-rules", status_code=201)
async def create_required_rule(
    payload: RequiredRuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        INSERT INTO tms.document_required_rules
            (rule_name, document_type_id, trigger_event, related_entity_type,
             transport_mode, country_code, customer_party_id, is_blocking)
        VALUES
            (:rule_name, CAST(:document_type_id AS uuid), :trigger_event, :related_entity_type,
             :transport_mode, :country_code, CAST(:customer_party_id AS uuid), :is_blocking)
        RETURNING *
    """), payload.model_dump())
    await db.commit()
    return dict(result.mappings().one())


@router.post("/check-required/{related_entity_type}/{related_entity_id}")
async def check_required_documents(
    related_entity_type: str,
    related_entity_id: str,
    trigger_event: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """DOC-006: Check if all required documents exist before a trigger event."""
    # Get required document types for this event
    rules_result = await db.execute(text("""
        SELECT r.rule_id, r.rule_name, r.is_blocking,
               dt.type_code, dt.type_name
        FROM tms.document_required_rules r
        JOIN tms.document_types dt ON dt.document_type_id = r.document_type_id
        WHERE r.trigger_event = :event AND r.is_active = TRUE
          AND (r.entity_type = :entity_type OR r.entity_type IS NULL)
    """), {"event": trigger_event, "entity_type": related_entity_type})
    rules = [dict(r) for r in rules_result.mappings().all()]

    # Get existing documents for this entity
    docs_result = await db.execute(text("""
        SELECT dt.type_code
        FROM tms.document_links da
        JOIN tms.documents d ON d.document_id = da.document_id
        JOIN tms.document_types dt ON dt.document_type_id = d.tms_document_type_id
        WHERE da.related_entity_type = :related_entity_type
          AND da.related_entity_id   = CAST(:related_entity_id AS uuid)
          AND d.status NOT IN ('voided','archived')
          AND d.is_current_version = TRUE
    """), {"related_entity_type": related_entity_type, "related_entity_id": related_entity_id})
    existing_codes = {r["type_code"] for r in docs_result.mappings().all()}

    missing = []
    blocking = []
    for rule in rules:
        if rule["type_code"] not in existing_codes:
            missing.append({
                "rule_name":    rule["rule_name"],
                "document_type":rule["type_code"],
                "type_name":    rule["type_name"],
                "is_blocking":  rule["is_blocking"],
            })
            if rule["is_blocking"]:
                blocking.append(rule["type_code"])

    return {
        "related_entity_type":     related_entity_type,
        "related_entity_id":       related_entity_id,
        "trigger_event":   trigger_event,
        "can_proceed":     len(blocking) == 0,
        "missing_count":   len(missing),
        "blocking_count":  len(blocking),
        "missing_documents": missing,
        "existing_documents": list(existing_codes),
    }


# ── OCR / Data Extraction (DOC-010) ──────────────────────────────

@router.post("/{document_id}/request-ocr")
async def request_ocr(
    document_id: str,
    payload: OCRRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    DOC-010: Request OCR/data extraction from a document.
    Marks document for OCR processing; in production this would
    trigger an async job to an OCR service (AWS Textract, Azure Form Recognizer, etc.)
    """
    # Check document exists and has content
    doc_result = await db.execute(text("""
        SELECT document_id, document_format, file_size_bytes, ocr_status
        FROM tms.documents WHERE document_id = CAST(:id AS uuid)
    """), {"id": document_id})
    doc = doc_result.mappings().one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found.")

    await db.execute(text("""
        UPDATE tms.documents
        SET ocr_status  = 'pending',
            updated_at  = NOW()
        WHERE document_id = CAST(:id AS uuid)
    """), {"id": document_id})
    await db.commit()

    return {
        "document_id":       document_id,
        "ocr_status":        "pending",
        "extraction_fields": payload.extraction_fields,
        "message":           "OCR extraction queued. Results will be available via GET /{document_id} once complete.",
        "note":              "In production, this triggers an async OCR job (AWS Textract / Azure Form Recognizer).",
    }


@router.patch("/{document_id}/ocr-result")
async def save_ocr_result(
    document_id: str,
    extracted_data: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Save OCR extraction results (called by OCR service webhook)."""
    result = await db.execute(text("""
        UPDATE tms.documents
        SET ocr_status         = 'completed',
            ocr_extracted_data = CAST(:data AS jsonb),
            updated_at         = NOW()
        WHERE document_id = CAST(:id AS uuid)
        RETURNING document_id, ocr_status
    """), {"data": _json.dumps(extracted_data), "id": document_id})
    await db.commit()
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Document not found.")
    return {"document_id": str(row["document_id"]), "ocr_status": "completed", "fields_extracted": len(extracted_data)}
