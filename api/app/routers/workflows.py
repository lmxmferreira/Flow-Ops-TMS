from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel
import json

router = APIRouter()

# ── Models ────────────────────────────────────────────────────
class RuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    rule_description: Optional[str] = None
    trigger_entity: str
    trigger_event: str
    trigger_status_from: Optional[str] = None
    trigger_status_to: Optional[str] = None
    filter_business_unit_id: Optional[str] = None
    filter_customer_party_id: Optional[str] = None
    filter_supplier_party_id: Optional[str] = None
    filter_carrier_id: Optional[str] = None
    filter_transport_mode_id: Optional[str] = None
    filter_country: Optional[str] = None
    filter_shipment_type: Optional[str] = None
    filter_priority: Optional[str] = None
    conditions: dict = {}
    action_type: str = 'NOTIFY'
    action_recipients: list = []
    notification_template: Optional[str] = None
    priority_order: int = 100
    status: str = 'ACTIVE'

class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    rule_description: Optional[str] = None
    trigger_status_from: Optional[str] = None
    trigger_status_to: Optional[str] = None
    filter_business_unit_id: Optional[str] = None
    filter_customer_party_id: Optional[str] = None
    filter_supplier_party_id: Optional[str] = None
    filter_carrier_id: Optional[str] = None
    filter_transport_mode_id: Optional[str] = None
    filter_country: Optional[str] = None
    filter_shipment_type: Optional[str] = None
    filter_priority: Optional[str] = None
    conditions: Optional[dict] = None
    action_recipients: Optional[list] = None
    notification_template: Optional[str] = None
    priority_order: Optional[int] = None
    status: Optional[str] = None

# ── Workflow Rules ────────────────────────────────────────────
@router.get("/rules")
async def list_rules(
    entity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    filters = ["1=1"]
    params = {}
    if entity:
        filters.append("wr.trigger_entity = :entity")
        params["entity"] = entity
    if status:
        filters.append("wr.status = :status")
        params["status"] = status

    sql = text(f"""
        SELECT
            wr.*,
            COALESCE(bu.business_unit_name, '') AS filter_bu_name,
            COALESCE(cp.party_name, '')          AS filter_customer_name,
            COALESCE(sp.party_name, '')          AS filter_supplier_name,
            COALESCE(tm.mode_code, '')           AS filter_mode_code
        FROM tms.workflow_rules wr
        LEFT JOIN tms.business_units  bu ON bu.business_unit_id      = wr.filter_business_unit_id
        LEFT JOIN tms.parties         cp ON cp.party_id              = wr.filter_customer_party_id
        LEFT JOIN tms.parties         sp ON sp.party_id              = wr.filter_supplier_party_id
        LEFT JOIN tms.transport_modes tm ON tm.transport_mode_id     = wr.filter_transport_mode_id
        WHERE {' AND '.join(filters)}
        ORDER BY wr.priority_order, wr.trigger_entity, wr.rule_name
    """)
    rows = (await db.execute(sql, params)).mappings().all()
    return {"data": [dict(r) for r in rows]}


@router.post("/rules")
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    exists = (await db.execute(
        text("SELECT 1 FROM tms.workflow_rules WHERE rule_code = :code"),
        {"code": body.rule_code}
    )).first()
    if exists:
        raise HTTPException(400, f"Rule code '{body.rule_code}' already exists")

    sql = text("""
        INSERT INTO tms.workflow_rules (
            rule_code, rule_name, rule_description,
            trigger_entity, trigger_event, trigger_status_from, trigger_status_to,
            filter_business_unit_id, filter_customer_party_id, filter_supplier_party_id,
            filter_carrier_id, filter_transport_mode_id, filter_country,
            filter_shipment_type, filter_priority,
            conditions, action_type, action_recipients, notification_template,
            priority_order, status
        ) VALUES (
            :rule_code, :rule_name, :rule_description,
            :trigger_entity, :trigger_event, :trigger_status_from, :trigger_status_to,
            :filter_bu, :filter_customer, :filter_supplier,
            :filter_carrier, :filter_mode, :filter_country,
            :filter_shipment_type, :filter_priority,
            :conditions::jsonb, :action_type, :action_recipients::jsonb, :notification_template,
            :priority_order, :status
        ) RETURNING rule_id, rule_code, rule_name, created_at
    """)
    row = (await db.execute(sql, {
        "rule_code": body.rule_code,
        "rule_name": body.rule_name,
        "rule_description": body.rule_description,
        "trigger_entity": body.trigger_entity,
        "trigger_event": body.trigger_event,
        "trigger_status_from": body.trigger_status_from,
        "trigger_status_to": body.trigger_status_to,
        "filter_bu": body.filter_business_unit_id,
        "filter_customer": body.filter_customer_party_id,
        "filter_supplier": body.filter_supplier_party_id,
        "filter_carrier": body.filter_carrier_id,
        "filter_mode": body.filter_transport_mode_id,
        "filter_country": body.filter_country,
        "filter_shipment_type": body.filter_shipment_type,
        "filter_priority": body.filter_priority,
        "conditions": json.dumps(body.conditions),
        "action_type": body.action_type,
        "action_recipients": json.dumps(body.action_recipients),
        "notification_template": body.notification_template,
        "priority_order": body.priority_order,
        "status": body.status,
    })).mappings().first()
    await db.commit()
    return dict(row)


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = ["updated_at = now()"]
    params = {"rule_id": rule_id}
    if body.rule_name is not None:
        sets.append("rule_name = :rule_name"); params["rule_name"] = body.rule_name
    if body.rule_description is not None:
        sets.append("rule_description = :desc"); params["desc"] = body.rule_description
    if body.status is not None:
        sets.append("status = :status"); params["status"] = body.status
    if body.trigger_status_from is not None:
        sets.append("trigger_status_from = :tsf"); params["tsf"] = body.trigger_status_from
    if body.trigger_status_to is not None:
        sets.append("trigger_status_to = :tst"); params["tst"] = body.trigger_status_to
    if body.notification_template is not None:
        sets.append("notification_template = :tmpl"); params["tmpl"] = body.notification_template
    if body.action_recipients is not None:
        sets.append("action_recipients = :recipients::jsonb")
        params["recipients"] = json.dumps(body.action_recipients)
    if body.priority_order is not None:
        sets.append("priority_order = :prio"); params["prio"] = body.priority_order
    if body.filter_country is not None:
        sets.append("filter_country = :country"); params["country"] = body.filter_country
    if body.filter_priority is not None:
        sets.append("filter_priority = :fpri"); params["fpri"] = body.filter_priority
    if body.conditions is not None:
        sets.append("conditions = :conditions::jsonb")
        params["conditions"] = json.dumps(body.conditions)

    await db.execute(
        text(f"UPDATE tms.workflow_rules SET {', '.join(sets)} WHERE rule_id = :rule_id"),
        params
    )
    await db.commit()
    return {"ok": True}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await db.execute(
        text("DELETE FROM tms.workflow_rules WHERE rule_id = :id"),
        {"id": rule_id}
    )
    await db.commit()
    return {"ok": True}


# ── Notification Engine ───────────────────────────────────────
@router.post("/trigger")
async def trigger_workflow(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Called internally whenever an entity status changes.
    body: { entity_type, entity_id, entity_number, event, status_from, status_to }
    Evaluates matching rules and creates notifications.
    """
    entity_type   = body.get("entity_type")
    entity_id     = body.get("entity_id")
    entity_number = body.get("entity_number", "")
    event         = body.get("event", "STATUS_CHANGE")
    status_from   = body.get("status_from")
    status_to     = body.get("status_to")

    # Find matching active rules
    rules_sql = text("""
        SELECT rule_id, rule_name, trigger_status_from, trigger_status_to,
               action_recipients, notification_template, action_type
        FROM tms.workflow_rules
        WHERE trigger_entity = :entity
          AND trigger_event  = :event
          AND status = 'ACTIVE'
          AND (trigger_status_from IS NULL OR trigger_status_from = :status_from)
          AND (trigger_status_to   IS NULL OR trigger_status_to   = :status_to)
        ORDER BY priority_order
    """)
    rules = (await db.execute(rules_sql, {
        "entity": entity_type,
        "event": event,
        "status_from": status_from,
        "status_to": status_to,
    })).mappings().all()

    notifications_created = 0
    for rule in rules:
        # Build message from template
        template = rule["notification_template"] or f"{entity_type} {entity_number} — {event}"
        message = template.replace("{{entity_number}}", entity_number)

        # Determine title
        title = rule["rule_name"]
        if status_to:
            title = f"{rule['rule_name']}: {entity_number}"

        # Parse recipients
        recipients = rule["action_recipients"] or []
        if isinstance(recipients, str):
            import json as _json
            recipients = _json.loads(recipients)

        # Create one notification per recipient type
        if not recipients:
            recipients = ["role:ALL"]

        for recipient in recipients:
            role = None
            user_id = None
            email = None
            if recipient.startswith("role:"):
                role = recipient[5:]
            elif recipient.startswith("user:"):
                user_id = recipient[5:]
            elif recipient.startswith("email:"):
                email = recipient[6:]

            await db.execute(text("""
                INSERT INTO tms.workflow_notifications (
                    rule_id, entity_type, entity_id, entity_number,
                    trigger_event, trigger_status_from, trigger_status_to,
                    title, message,
                    recipient_user_id, recipient_role, recipient_email,
                    delivery_status
                ) VALUES (
                    :rule_id, :entity_type, :entity_id::uuid, :entity_number,
                    :event, :status_from, :status_to,
                    :title, :message,
                    :user_id::uuid, :role, :email,
                    'SENT'
                )
            """), {
                "rule_id": rule["rule_id"],
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_number": entity_number,
                "event": event,
                "status_from": status_from,
                "status_to": status_to,
                "title": title,
                "message": message,
                "user_id": user_id,
                "role": role,
                "email": email,
            })
            notifications_created += 1

    await db.commit()
    return {"notifications_created": notifications_created, "rules_matched": len(rules)}


# ── Notifications (read) ──────────────────────────────────────
@router.get("/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    filters = ["1=1"]
    params = {"limit": limit}
    if unread_only:
        filters.append("n.is_read = false")

    sql = text(f"""
        SELECT
            n.notification_id, n.entity_type, n.entity_id, n.entity_number,
            n.trigger_event, n.trigger_status_from, n.trigger_status_to,
            n.title, n.message, n.is_read, n.read_at,
            n.recipient_role, n.delivery_status, n.created_at,
            wr.rule_name, wr.trigger_entity
        FROM tms.workflow_notifications n
        JOIN tms.workflow_rules wr ON wr.rule_id = n.rule_id
        WHERE {' AND '.join(filters)}
        ORDER BY n.created_at DESC
        LIMIT :limit
    """)
    rows = (await db.execute(sql, params)).mappings().all()

    unread_count = (await db.execute(
        text("SELECT COUNT(*) FROM tms.workflow_notifications WHERE is_read = false")
    )).scalar()

    return {"data": [dict(r) for r in rows], "unread_count": unread_count}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await db.execute(
        text("UPDATE tms.workflow_notifications SET is_read = true, read_at = now() WHERE notification_id = :id"),
        {"id": notification_id}
    )
    await db.commit()
    return {"ok": True}


@router.patch("/notifications/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await db.execute(
        text("UPDATE tms.workflow_notifications SET is_read = true, read_at = now() WHERE is_read = false")
    )
    await db.commit()
    return {"ok": True}
