from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional
from pydantic import BaseModel
import json

router = APIRouter()

ENTITY_TYPES = [
    'SHIPMENT', 'PURCHASE_ORDER', 'ORDER_RELEASE', 'LOAD', 'STOP',
    'CARRIER_INVOICE', 'CLIENT_BILL', 'VOUCHER', 'DISPUTE', 'PAYMENT'
]

class StatusValueUpdate(BaseModel):
    status_name: Optional[str] = None
    status_color: Optional[str] = None
    description: Optional[str] = None
    is_initial: Optional[bool] = None
    is_terminal: Optional[bool] = None
    requires_reason: Optional[bool] = None
    requires_approval: Optional[bool] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None

class TransitionUpdate(BaseModel):
    transition_name: Optional[str] = None
    allowed_roles: Optional[list] = None
    requires_reason: Optional[bool] = None
    requires_approval: Optional[bool] = None
    trigger_workflow: Optional[bool] = None
    is_active: Optional[bool] = None

# ── List all status models with their values ─────────────────
@router.get("/")
async def list_status_models(
    entity_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    filters = ["1=1"]
    params = {}
    if entity_type:
        filters.append("sm.applies_to_entity = :entity_type")
        params["entity_type"] = entity_type

    sql = text(f"""
        SELECT
            sm.status_model_id,
            sm.model_code,
            sm.model_name,
            sm.applies_to_entity AS entity_type,
            sm.description,
            sm.status AS model_status,
            json_agg(
                json_build_object(
                    'status_value_id', sv.status_value_id,
                    'status_code',     sv.status_code,
                    'status_name',     sv.status_name,
                    'status_color',    COALESCE(sv.status_color, '#9CA3AF'),
                    'description',     sv.description,
                    'is_initial',      sv.is_initial,
                    'is_terminal',     sv.is_terminal,
                    'requires_reason', COALESCE(sv.requires_reason, false),
                    'requires_approval',COALESCE(sv.requires_approval, false),
                    'sort_order',      sv.sort_order,
                    'status',          sv.status
                ) ORDER BY sv.sort_order, sv.status_code
            ) AS statuses,
            COUNT(sv.status_value_id) AS status_count
        FROM tms.status_models sm
        LEFT JOIN tms.status_values sv ON sv.status_model_id = sm.status_model_id
        WHERE {' AND '.join(filters)}
        GROUP BY sm.status_model_id, sm.model_code, sm.model_name,
                 sm.applies_to_entity, sm.description, sm.status
        ORDER BY sm.applies_to_entity
    """)
    rows = (await db.execute(sql, params)).mappings().all()
    return {"data": [dict(r) for r in rows], "entity_types": ENTITY_TYPES}


# ── Update a status value ─────────────────────────────────────
@router.patch("/values/{status_value_id}")
async def update_status_value(
    status_value_id: str,
    body: StatusValueUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = []
    params = {"id": status_value_id}
    field_map = {
        "status_name": "status_name", "status_color": "status_color",
        "description": "description", "is_initial": "is_initial",
        "is_terminal": "is_terminal", "requires_reason": "requires_reason",
        "requires_approval": "requires_approval", "sort_order": "sort_order",
        "status": "status",
    }
    for field, col in field_map.items():
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{col} = :{field}")
            params[field] = val
    if not sets:
        raise HTTPException(400, "Nothing to update")
    await db.execute(
        text(f"UPDATE tms.status_values SET {', '.join(sets)} WHERE status_value_id = :id"),
        params
    )
    await db.commit()
    return {"ok": True}


# ── List transitions ──────────────────────────────────────────
@router.get("/transitions")
async def list_transitions(
    entity_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    filters = ["1=1"]
    params = {}
    if entity_type:
        filters.append("sm.applies_to_entity = :entity_type")
        params["entity_type"] = entity_type

    sql = text(f"""
        SELECT
            st.transition_id,
            sm.applies_to_entity AS entity_type,
            st.from_status_code,
            st.to_status_code,
            st.transition_name,
            st.allowed_roles,
            st.requires_reason,
            st.requires_approval,
            st.trigger_workflow,
            st.is_active,
            st.sort_order
        FROM tms.status_transitions st
        JOIN tms.status_models sm ON sm.status_model_id = st.status_model_id
        WHERE {' AND '.join(filters)}
        ORDER BY sm.applies_to_entity, st.sort_order, st.from_status_code, st.to_status_code
    """)
    rows = (await db.execute(sql, params)).mappings().all()
    return {"data": [dict(r) for r in rows]}


# ── Update a transition ───────────────────────────────────────
@router.patch("/transitions/{transition_id}")
async def update_transition(
    transition_id: str,
    body: TransitionUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sets = []
    params = {"id": transition_id}
    if body.transition_name is not None:
        sets.append("transition_name = :tn"); params["tn"] = body.transition_name
    if body.allowed_roles is not None:
        sets.append("allowed_roles = :roles::jsonb"); params["roles"] = json.dumps(body.allowed_roles)
    if body.requires_reason is not None:
        sets.append("requires_reason = :rr"); params["rr"] = body.requires_reason
    if body.requires_approval is not None:
        sets.append("requires_approval = :ra"); params["ra"] = body.requires_approval
    if body.trigger_workflow is not None:
        sets.append("trigger_workflow = :tw"); params["tw"] = body.trigger_workflow
    if body.is_active is not None:
        sets.append("is_active = :ia"); params["ia"] = body.is_active
    if not sets:
        raise HTTPException(400, "Nothing to update")
    await db.execute(
        text(f"UPDATE tms.status_transitions SET {', '.join(sets)} WHERE transition_id = :id"),
        params
    )
    await db.commit()
    return {"ok": True}


# ── Validate transition ───────────────────────────────────────
@router.post("/validate")
async def validate_transition(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    sql = text("""
        SELECT st.transition_id, st.transition_name, st.allowed_roles,
               st.requires_reason, st.requires_approval, st.trigger_workflow
        FROM tms.status_transitions st
        JOIN tms.status_models sm ON sm.status_model_id = st.status_model_id
        WHERE sm.applies_to_entity = :entity_type
          AND (st.from_status_code = :from_status OR st.from_status_code IS NULL)
          AND st.to_status_code = :to_status
          AND st.is_active = true
        LIMIT 1
    """)
    row = (await db.execute(sql, {
        "entity_type": body.get("entity_type"),
        "from_status": body.get("from_status"),
        "to_status":   body.get("to_status"),
    })).mappings().first()

    if not row:
        return {"allowed": False, "reason": "No transition rule found"}

    roles = row["allowed_roles"] if isinstance(row["allowed_roles"], list) else json.loads(row["allowed_roles"])
    user_role = body.get("user_role", "")
    if roles and user_role not in roles:
        return {"allowed": False, "reason": f"Role '{user_role}' is not permitted for this transition"}

    return {
        "allowed": True,
        "transition_name": row["transition_name"],
        "requires_reason": row["requires_reason"],
        "requires_approval": row["requires_approval"],
        "trigger_workflow": row["trigger_workflow"],
    }
