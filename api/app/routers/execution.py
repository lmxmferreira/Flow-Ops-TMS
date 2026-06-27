"""
routers/execution.py
TMS-EXEC-001 through TMS-EXEC-015: Execution, Tracking & Visibility
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter()

MILESTONE_SEQUENCE = [
    "tendered", "accepted", "dispatched", "arrived_pickup", "picked_up",
    "departed_pickup", "in_transit", "arrived_delivery", "delivered",
    "departed_delivery", "completed", "closed"
]


# ── Pydantic Models ───────────────────────────────────────────────

class DispatchRequest(BaseModel):
    carrier_id: Optional[str] = None
    driver_name: Optional[str] = None
    trailer_number: Optional[str] = None
    pro_number: Optional[str] = None
    bol_number: Optional[str] = None
    dispatch_notes: Optional[str] = None

class TrackingEventCreate(BaseModel):
    event_code: str
    event_datetime: Optional[str] = None
    event_source: str = "manual"
    shipment_stop_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    eta_datetime: Optional[str] = None
    notes: Optional[str] = None

class TrackingEventCorrection(BaseModel):
    corrected_event_id: str
    event_code: str
    event_datetime: str
    override_reason: str
    notes: Optional[str] = None

class ProofCreate(BaseModel):
    proof_type: str = "pod"
    shipment_stop_id: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None
    signature_data: Optional[str] = None
    photo_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capture_source: str = "manual"
    notes: Optional[str] = None

class AssetAssign(BaseModel):
    asset_type: str
    asset_value: str
    notes: Optional[str] = None

class ETAUpdate(BaseModel):
    shipment_stop_id: Optional[str] = None
    calculated_eta: str
    planned_arrival: Optional[str] = None
    calculation_source: str = "manual"
    confidence_pct: Optional[float] = None

class GeofenceEventCreate(BaseModel):
    shipment_stop_id: Optional[str] = None
    event_type: str  # arrival | departure
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_radius_m: int = 500
    auto_milestone: Optional[str] = None

class AlertCreate(BaseModel):
    alert_type: str
    severity: str = "warning"
    title: str
    message: Optional[str] = None
    delivery_channels: list[str] = ["portal"]
    recipient_emails: Optional[list[str]] = None
    webhook_url: Optional[str] = None

class SubscriptionCreate(BaseModel):
    entity_type: str = "shipment"
    entity_id: str
    subscriber_type: str
    subscriber_name: str
    delivery_channel: str = "email"
    endpoint: Optional[str] = None
    milestone_codes: Optional[list[str]] = None


# ── EXEC-001: Dispatch ────────────────────────────────────────────

@router.post("/{shipment_id}/dispatch", status_code=201)
async def dispatch_shipment(
    shipment_id: str,
    payload: DispatchRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-001: Dispatch a shipment to carrier/driver/broker."""
    user_id = user.get("email", "system")

    # Record dispatch event
    event_result = await db.execute(text("""
        INSERT INTO tms.tracking_events
            (shipment_id, event_code, event_datetime, event_source, performed_by, notes)
        VALUES
            (CAST(:id AS uuid), 'dispatched', NOW(), 'manual', :user, :notes)
        RETURNING tracking_event_id
    """), {"id": shipment_id, "user": user_id, "notes": payload.dispatch_notes})
    event_id = str(event_result.scalar())

    # Assign assets
    asset_ids = []
    assets = [
        ("trailer", payload.trailer_number),
        ("pro_number", payload.pro_number),
        ("bol_number", payload.bol_number),
        ("driver", payload.driver_name),
    ]
    for asset_type, asset_value in assets:
        if asset_value:
            ar = await db.execute(text("""
                INSERT INTO tms.exec_assets (shipment_id, asset_type, asset_value, assigned_by)
                VALUES (CAST(:id AS uuid), :type, :value, :user)
                RETURNING asset_id
            """), {"id": shipment_id, "type": asset_type, "value": asset_value, "user": user_id})
            asset_ids.append(str(ar.scalar()))

    # Update lifecycle
    await db.execute(text("""
        INSERT INTO tms.process_lifecycle (shipment_id, current_stage)
        VALUES (CAST(:id AS uuid), 'dispatched')
        ON CONFLICT (shipment_id) DO UPDATE SET
            current_stage = 'dispatched', updated_at = NOW()
    """), {"id": shipment_id})

    await db.commit()
    return {
        "shipment_id":    shipment_id,
        "status":         "dispatched",
        "dispatch_event": event_id,
        "assets_assigned":len(asset_ids),
        "dispatched_by":  user_id,
    }


# ── EXEC-002/003: Tracking events ────────────────────────────────

@router.post("/{shipment_id}/events", status_code=201)
async def record_tracking_event(
    shipment_id: str,
    payload: TrackingEventCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-002/003: Record execution milestone from any source."""
    user_id = user.get("email", "system")

    if payload.event_code not in MILESTONE_SEQUENCE + ["exception", "refused", "damaged", "short", "over"]:
        raise HTTPException(400, f"Invalid event_code. Valid: {', '.join(MILESTONE_SEQUENCE)}")

    evt_dt = datetime.fromisoformat(payload.event_datetime) if payload.event_datetime else datetime.utcnow()
    eta_dt = datetime.fromisoformat(payload.eta_datetime) if payload.eta_datetime else None

    result = await db.execute(text("""
        INSERT INTO tms.tracking_events
            (shipment_id, shipment_stop_id, event_code, event_datetime,
             event_source, performed_by, latitude, longitude, city,
             state_province, eta_datetime, notes)
        VALUES
            (CAST(:shipment_id AS uuid), CAST(:stop_id AS uuid), :event_code,
             :event_dt, :source, :user,
             CAST(:lat AS numeric), CAST(:lng AS numeric), :city,
             :state, :eta_dt, :notes)
        RETURNING tracking_event_id
    """), {
        "shipment_id": shipment_id,
        "stop_id":     payload.shipment_stop_id,
        "event_code":  payload.event_code,
        "event_dt":    evt_dt,
        "source":      payload.event_source,
        "user":        user_id,
        "lat":         payload.latitude,
        "lng":         payload.longitude,
        "city":        payload.city,
        "state":       payload.state_province,
        "eta_dt":      eta_dt,
        "notes":       payload.notes,
    })
    event_id = str(result.scalar())

    # Update lifecycle stage
    stage_map = {
        "dispatched":       "dispatched",
        "arrived_pickup":   "in_transit",
        "picked_up":        "in_transit",
        "departed_pickup":  "in_transit",
        "in_transit":       "in_transit",
        "arrived_delivery": "in_transit",
        "delivered":        "delivered",
        "completed":        "delivered",
        "closed":           "closed",
    }
    if payload.event_code in stage_map:
        lc_stage = stage_map[payload.event_code]
        delivered_flag = payload.event_code in ("delivered", "completed", "closed")
        await db.execute(text(f"""
            INSERT INTO tms.process_lifecycle
                (shipment_id, in_transit, in_transit_at, delivered, delivered_at, current_stage)
            VALUES
                (CAST(:id AS uuid),
                 :in_transit, CASE WHEN :in_transit THEN NOW() ELSE NULL END,
                 :delivered, CASE WHEN :delivered THEN NOW() ELSE NULL END,
                 :stage)
            ON CONFLICT (shipment_id) DO UPDATE SET
                in_transit   = CASE WHEN :in_transit THEN TRUE ELSE tms.process_lifecycle.in_transit END,
                in_transit_at= CASE WHEN :in_transit AND tms.process_lifecycle.in_transit = FALSE THEN NOW() ELSE tms.process_lifecycle.in_transit_at END,
                delivered    = CASE WHEN :delivered THEN TRUE ELSE tms.process_lifecycle.delivered END,
                delivered_at = CASE WHEN :delivered AND tms.process_lifecycle.delivered = FALSE THEN NOW() ELSE tms.process_lifecycle.delivered_at END,
                current_stage= :stage,
                updated_at   = NOW()
        """), {
            "id":         shipment_id,
            "in_transit": lc_stage == "in_transit",
            "delivered":  delivered_flag,
            "stage":      lc_stage,
        })

    # Auto-trigger alerts for exceptions
    if payload.event_code in ("exception", "refused", "damaged"):
        await db.execute(text("""
            INSERT INTO tms.exec_alerts
                (shipment_id, alert_type, severity, title, message, delivery_channels)
            VALUES
                (CAST(:id AS uuid), :alert_type, 'error', :title, :msg, ARRAY['portal'])
        """), {
            "id":         shipment_id,
            "alert_type": payload.event_code,
            "title":      f"Shipment Exception: {payload.event_code.replace('_',' ').title()}",
            "msg":        payload.notes or f"{payload.event_code} reported at {evt_dt}",
        })

    await db.commit()
    return {
        "tracking_event_id": event_id,
        "shipment_id":       shipment_id,
        "event_code":        payload.event_code,
        "event_datetime":    str(evt_dt),
        "source":            payload.event_source,
    }


@router.get("/{shipment_id}/events")
async def get_tracking_events(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """EXEC-002/013: Full milestone history for a shipment."""
    result = await db.execute(text("""
        SELECT te.*, lv_type.display_name AS event_type_name,
               lv_status.display_name AS event_status_name,
               ss.stop_sequence, ss.stop_type_id
        FROM tms.tracking_events te
        LEFT JOIN tms.lookup_values lv_type   ON lv_type.lookup_value_id   = te.event_type_id
        LEFT JOIN tms.lookup_values lv_status ON lv_status.lookup_value_id = te.event_status_id
        LEFT JOIN tms.shipment_stops ss       ON ss.shipment_stop_id       = te.shipment_stop_id
        WHERE te.shipment_id = CAST(:id AS uuid)
          AND te.correction_flag = FALSE
        ORDER BY te.event_datetime DESC
        LIMIT :limit
    """), {"id": shipment_id, "limit": limit})
    events = [dict(r) for r in result.mappings().all()]

    # Current milestone
    current = events[0]["event_code"] if events else None
    next_milestone = None
    if current and current in MILESTONE_SEQUENCE:
        idx = MILESTONE_SEQUENCE.index(current)
        if idx < len(MILESTONE_SEQUENCE) - 1:
            next_milestone = MILESTONE_SEQUENCE[idx + 1]

    return {
        "shipment_id":    shipment_id,
        "event_count":    len(events),
        "current_milestone": current,
        "next_milestone":    next_milestone,
        "events":         events,
    }


# ── EXEC-004: Proof of delivery/pickup ───────────────────────────

@router.post("/{shipment_id}/proof", status_code=201)
async def capture_proof(
    shipment_id: str,
    payload: ProofCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-004: Capture POD/POP with signature, photo, timestamp, location."""
    user_id = user.get("email", "system")
    result = await db.execute(text("""
        INSERT INTO tms.proof_of_execution
            (shipment_id, shipment_stop_id, proof_type,
             captured_by, capture_source,
             latitude, longitude, signatory_name, signatory_title,
             signature_data, photo_url, notes)
        VALUES
            (CAST(:shipment_id AS uuid), CAST(:stop_id AS uuid), :proof_type,
             :captured_by, :source,
             CAST(:lat AS numeric), CAST(:lng AS numeric),
             :signatory_name, :signatory_title,
             :signature_data, :photo_url, :notes)
        RETURNING proof_id, captured_at
    """), {
        "shipment_id":    shipment_id,
        "stop_id":        payload.shipment_stop_id,
        "proof_type":     payload.proof_type,
        "captured_by":    user_id,
        "source":         payload.capture_source,
        "lat":            payload.latitude,
        "lng":            payload.longitude,
        "signatory_name": payload.signatory_name,
        "signatory_title":payload.signatory_title,
        "signature_data": payload.signature_data,
        "photo_url":      payload.photo_url,
        "notes":          payload.notes,
    })
    row = dict(result.mappings().one())
    await db.commit()
    return {"proof_id": str(row["proof_id"]), "captured_at": str(row["captured_at"]),
            "proof_type": payload.proof_type, "shipment_id": shipment_id}


@router.get("/{shipment_id}/proof")
async def get_proof(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.proof_of_execution
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY captured_at DESC
    """), {"id": shipment_id})
    return [dict(r) for r in result.mappings().all()]


# ── EXEC-005: Asset assignment ────────────────────────────────────

@router.post("/{shipment_id}/assets", status_code=201)
async def assign_asset(
    shipment_id: str,
    payload: AssetAssign,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-005: Assign trailer, tractor, container, PRO, BOL, etc."""
    valid_types = ["trailer","tractor","container","chassis","driver","seal",
                   "tracking_number","pro_number","bol_number","container_number"]
    if payload.asset_type not in valid_types:
        raise HTTPException(400, f"Invalid asset_type. Valid: {', '.join(valid_types)}")
    result = await db.execute(text("""
        INSERT INTO tms.exec_assets (shipment_id, asset_type, asset_value, assigned_by, notes)
        VALUES (CAST(:id AS uuid), :type, :value, :user, :notes)
        RETURNING asset_id
    """), {
        "id": shipment_id, "type": payload.asset_type,
        "value": payload.asset_value, "user": user.get("email","system"),
        "notes": payload.notes
    })
    await db.commit()

    # Add to reference index for EXEC-006
    try:
        await db.execute(text("""
            INSERT INTO tms.reference_index (ref_number, ref_type, entity_type, entity_id, parent_ref, parent_type)
            VALUES (:ref, :ref_type, 'shipment', CAST(:entity_id AS uuid), NULL, NULL)
            ON CONFLICT DO NOTHING
        """), {"ref": payload.asset_value, "ref_type": payload.asset_type, "entity_id": shipment_id})
        await db.commit()
    except Exception:
        pass

    return {"asset_id": str(result.scalar()), "asset_type": payload.asset_type,
            "asset_value": payload.asset_value, "shipment_id": shipment_id}


@router.get("/{shipment_id}/assets")
async def get_assets(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT * FROM tms.exec_assets WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY asset_type, assigned_at
    """), {"id": shipment_id})
    return [dict(r) for r in result.mappings().all()]


# ── EXEC-006: Visibility search ───────────────────────────────────

@router.get("/visibility/search")
async def search_visibility(
    ref: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-006: Find shipment by any reference — PO, BOL, PRO, tracking #, container."""
    # Search reference index
    ref_result = await db.execute(text("""
        SELECT ri.*, s.shipment_number
        FROM tms.reference_index ri
        LEFT JOIN tms.shipments s ON s.shipment_id = ri.entity_id
            AND ri.entity_type = 'shipment'
        WHERE ri.ref_number ILIKE :ref AND ri.is_active = TRUE
        LIMIT 10
    """), {"ref": f"%{ref}%"})
    refs = [dict(r) for r in ref_result.mappings().all()]

    # Also search assets
    asset_result = await db.execute(text("""
        SELECT sa.*, s.shipment_number,
               te.event_code AS last_event, te.event_datetime AS last_event_at,
               te.city, te.state_province
        FROM tms.exec_assets sa
        JOIN tms.shipments s ON s.shipment_id = sa.shipment_id
        LEFT JOIN tms.tracking_events te ON te.shipment_id = sa.shipment_id
            AND te.tracking_event_id = (
                SELECT tracking_event_id FROM tms.tracking_events
                WHERE shipment_id = sa.shipment_id
                ORDER BY event_datetime DESC LIMIT 1)
        WHERE sa.asset_value ILIKE :ref
        LIMIT 5
    """), {"ref": f"%{ref}%"})
    assets = [dict(r) for r in asset_result.mappings().all()]

    return {
        "query":            ref,
        "reference_matches":refs,
        "asset_matches":    assets,
        "total_matches":    len(refs) + len(assets),
    }


# ── EXEC-007: Map/location ────────────────────────────────────────

@router.get("/{shipment_id}/location")
async def get_shipment_location(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-007: Latest GPS location for map display."""
    result = await db.execute(text("""
        SELECT te.tracking_event_id, te.event_code, te.event_datetime,
               te.latitude, te.longitude, te.city, te.state_province,
               te.eta_datetime, te.event_source
        FROM tms.tracking_events te
        WHERE te.shipment_id = CAST(:id AS uuid)
          AND te.latitude IS NOT NULL
          AND te.correction_flag = FALSE
        ORDER BY te.event_datetime DESC
        LIMIT 1
    """), {"id": shipment_id})
    loc = result.mappings().one_or_none()
    if not loc:
        return {"shipment_id": shipment_id, "location": None,
                "message": "No location data available."}
    return {"shipment_id": shipment_id, "location": dict(loc)}


# ── EXEC-008: ETA ─────────────────────────────────────────────────

@router.post("/{shipment_id}/eta", status_code=201)
async def update_eta(
    shipment_id: str,
    payload: ETAUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-008: Update ETA with at-risk / late flags."""
    eta_dt = datetime.fromisoformat(payload.calculated_eta)
    planned = datetime.fromisoformat(payload.planned_arrival) if payload.planned_arrival else None

    variance_min = None
    is_at_risk = False
    is_late = False
    if planned:
        variance_min = int((eta_dt - planned).total_seconds() / 60)
        is_late = variance_min > 0
        is_at_risk = variance_min > -60  # at risk if within 60 min of late

    result = await db.execute(text("""
        INSERT INTO tms.shipment_etas
            (shipment_id, shipment_stop_id, calculated_eta, planned_arrival,
             variance_minutes, is_at_risk, is_late,
             confidence_pct, calculation_source)
        VALUES
            (CAST(:shipment_id AS uuid), CAST(:stop_id AS uuid),
             :eta, :planned, :variance, :at_risk, :late,
             CAST(:confidence AS numeric), :source)
        RETURNING eta_id, is_late, variance_minutes
    """), {
        "shipment_id":shipment_id,
        "stop_id":    payload.shipment_stop_id,
        "eta":        eta_dt,
        "planned":    planned,
        "variance":   variance_min,
        "at_risk":    is_at_risk,
        "late":       is_late,
        "confidence": payload.confidence_pct,
        "source":     payload.calculation_source,
    })
    row = dict(result.mappings().one())

    # Auto-alert if late
    if is_late:
        await db.execute(text("""
            INSERT INTO tms.exec_alerts
                (shipment_id, alert_type, severity, title, message, delivery_channels)
            VALUES
                (CAST(:id AS uuid), 'late_delivery', 'warning',
                 'Late Delivery Alert',
                 :msg, ARRAY['portal'])
            ON CONFLICT DO NOTHING
        """), {
            "id":  shipment_id,
            "msg": f"ETA is {abs(variance_min)} minutes late. Calculated: {eta_dt}",
        })

    await db.commit()
    return {
        "eta_id":         str(row["eta_id"]),
        "calculated_eta": str(eta_dt),
        "is_late":        is_late,
        "is_at_risk":     is_at_risk,
        "variance_minutes":variance_min,
    }


# ── EXEC-009: Geofence events ─────────────────────────────────────

@router.post("/{shipment_id}/geofence", status_code=201)
async def trigger_geofence(
    shipment_id: str,
    payload: GeofenceEventCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-009: Record geofence-based arrival or departure event."""
    result = await db.execute(text("""
        INSERT INTO tms.geofence_events
            (shipment_id, shipment_stop_id, event_type, location_name,
             geofence_radius_m, latitude, longitude, auto_milestone)
        VALUES
            (CAST(:shipment_id AS uuid), CAST(:stop_id AS uuid),
             :event_type, :location,
             :radius, CAST(:lat AS numeric), CAST(:lng AS numeric), :auto_ms)
        RETURNING geofence_event_id, triggered_at
    """), {
        "shipment_id": shipment_id,
        "stop_id":     payload.shipment_stop_id,
        "event_type":  payload.event_type,
        "location":    payload.location_name,
        "radius":      payload.geofence_radius_m,
        "lat":         payload.latitude,
        "lng":         payload.longitude,
        "auto_ms":     payload.auto_milestone,
    })
    row = dict(result.mappings().one())

    # Auto-create tracking event if configured
    if payload.auto_milestone:
        await db.execute(text("""
            INSERT INTO tms.tracking_events
                (shipment_id, shipment_stop_id, event_code, event_datetime,
                 event_source, latitude, longitude, notes)
            VALUES
                (CAST(:shipment_id AS uuid), CAST(:stop_id AS uuid),
                 :code, NOW(), 'geofence',
                 CAST(:lat AS numeric), CAST(:lng AS numeric),
                 :notes)
        """), {
            "shipment_id": shipment_id,
            "stop_id":     payload.shipment_stop_id,
            "code":        payload.auto_milestone,
            "lat":         payload.latitude,
            "lng":         payload.longitude,
            "notes":       f"Auto-triggered by {payload.event_type} geofence at {payload.location_name}",
        })

    await db.commit()
    return {
        "geofence_event_id": str(row["geofence_event_id"]),
        "triggered_at":      str(row["triggered_at"]),
        "event_type":        payload.event_type,
        "auto_milestone":    payload.auto_milestone,
    }


# ── EXEC-010/014: Customer tracking & alerts ──────────────────────

@router.get("/{shipment_id}/tracking-page")
async def get_customer_tracking(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-010: Customer-facing tracking page data."""
    shp_result = await db.execute(text("""
        SELECT s.shipment_number, s.planned_pickup_date, s.planned_delivery_date,
               p.party_name AS carrier_name, c.scac
        FROM tms.shipments s
        LEFT JOIN tms.carriers c ON c.carrier_id = s.carrier_id
        LEFT JOIN tms.parties  p ON p.party_id   = c.party_id
        WHERE s.shipment_id = CAST(:id AS uuid)
    """), {"id": shipment_id})
    shp = shp_result.mappings().one_or_none()
    if not shp:
        raise HTTPException(404, "Shipment not found.")
    shp = dict(shp)

    # Latest milestone
    latest_result = await db.execute(text("""
        SELECT event_code, event_datetime, city, state_province, eta_datetime
        FROM tms.tracking_events
        WHERE shipment_id = CAST(:id AS uuid) AND correction_flag = FALSE
        ORDER BY event_datetime DESC LIMIT 1
    """), {"id": shipment_id})
    latest = latest_result.mappings().one_or_none()

    # Stops
    stops_result = await db.execute(text("""
        SELECT ss.stop_sequence, ss.stop_type_id,
               l.location_name, l.city, l.state_province,
               ss.planned_arrival_datetime, ss.actual_arrival_datetime
        FROM tms.shipment_stops ss
        LEFT JOIN tms.locations l ON l.location_id = ss.location_id
        WHERE ss.shipment_id = CAST(:id AS uuid)
        ORDER BY ss.stop_sequence
    """), {"id": shipment_id})
    stops = [dict(r) for r in stops_result.mappings().all()]

    # Latest ETA
    eta_result = await db.execute(text("""
        SELECT calculated_eta, is_late, variance_minutes
        FROM tms.shipment_etas
        WHERE shipment_id = CAST(:id AS uuid)
        ORDER BY calculated_at DESC LIMIT 1
    """), {"id": shipment_id})
    eta = eta_result.mappings().one_or_none()

    return {
        "shipment_number":  shp.get("shipment_number"),
        "carrier":          shp.get("carrier_name"),
        "current_status":   dict(latest) if latest else None,
        "planned_pickup":   str(shp.get("planned_pickup_date") or ""),
        "planned_delivery": str(shp.get("planned_delivery_date") or ""),
        "eta":              dict(eta) if eta else None,
        "stops":            stops,
        "tracking_url":     f"/track/{shipment_id}",
    }


@router.post("/{shipment_id}/alerts", status_code=201)
async def create_alert(
    shipment_id: str,
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-011/014: Create shipment alert with configurable delivery channels."""
    result = await db.execute(text("""
        INSERT INTO tms.exec_alerts
            (shipment_id, alert_type, severity, title, message,
             delivery_channels, recipient_emails, webhook_url)
        VALUES
            (CAST(:id AS uuid), :alert_type, :severity, :title, :message,
             :channels, :emails, :webhook)
        RETURNING alert_id
    """), {
        "id":         shipment_id,
        "alert_type": payload.alert_type,
        "severity":   payload.severity,
        "title":      payload.title,
        "message":    payload.message,
        "channels":   payload.delivery_channels,
        "emails":     payload.recipient_emails,
        "webhook":    payload.webhook_url,
    })
    await db.commit()
    return {"alert_id": str(result.scalar()), **payload.model_dump()}


@router.get("/alerts/dashboard")
async def exception_dashboard(
    db: AsyncSession = Depends(get_db),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """EXEC-011: Exception dashboard for delayed/missing/failed shipments."""
    conditions = ["ea.is_resolved = FALSE"]
    params: dict[str, Any] = {}
    if severity:
        conditions.append("ea.severity = :severity")
        params["severity"] = severity
    if alert_type:
        conditions.append("ea.alert_type = :alert_type")
        params["alert_type"] = alert_type

    result = await db.execute(text(f"""
        SELECT ea.*, s.shipment_number,
               p.party_name AS carrier_name
        FROM tms.exec_alerts ea
        JOIN tms.shipments s ON s.shipment_id = ea.shipment_id
        LEFT JOIN tms.carriers c ON c.carrier_id = s.carrier_id
        LEFT JOIN tms.parties p  ON p.party_id   = c.party_id
        WHERE {' AND '.join(conditions)}
        ORDER BY CASE ea.severity WHEN 'critical' THEN 1 WHEN 'error' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,
                 ea.created_at DESC
        LIMIT 100
    """), params)
    alerts = [dict(r) for r in result.mappings().all()]

    summary_result = await db.execute(text("""
        SELECT alert_type, COUNT(*) AS count
        FROM tms.exec_alerts WHERE is_resolved = FALSE
        GROUP BY alert_type ORDER BY count DESC
    """))
    by_type = {r["alert_type"]: int(r["count"]) for r in summary_result.mappings().all()}

    return {
        "total_open": len(alerts),
        "by_type":    by_type,
        "alerts":     alerts,
    }


# ── EXEC-012: Status subscriptions ───────────────────────────────

@router.post("/subscriptions", status_code=201)
async def create_subscription(
    payload: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-012: Subscribe to status updates for a shipment."""
    result = await db.execute(text("""
        INSERT INTO tms.status_subscriptions
            (entity_type, entity_id, subscriber_type, subscriber_name,
             delivery_channel, endpoint, milestone_codes)
        VALUES
            (:entity_type, CAST(:entity_id AS uuid), :subscriber_type,
             :subscriber_name, :delivery_channel, :endpoint, :milestones)
        RETURNING subscription_id
    """), {**payload.model_dump(), "milestones": payload.milestone_codes})
    await db.commit()
    return {"subscription_id": str(result.scalar()), **payload.model_dump()}


# ── EXEC-015: Event correction ────────────────────────────────────

@router.post("/{shipment_id}/events/correct", status_code=201)
async def correct_event(
    shipment_id: str,
    payload: TrackingEventCorrection,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """EXEC-015: Correct/reverse a tracking event with audit trail."""
    user_id = user.get("email", "system")

    # Mark original as corrected
    await db.execute(text("""
        UPDATE tms.tracking_events
        SET correction_flag = TRUE, corrected_tracking_event_id = CAST(:new_id AS uuid)
        WHERE tracking_event_id = CAST(:old_id AS uuid)
    """), {"new_id": payload.corrected_event_id, "old_id": payload.corrected_event_id})

    # Insert corrected event
    result = await db.execute(text("""
        INSERT INTO tms.tracking_events
            (shipment_id, event_code, event_datetime, event_source,
             performed_by, notes, is_correction, override_reason,
             corrected_tracking_event_id)
        VALUES
            (CAST(:shipment_id AS uuid), :event_code,
             CAST(:event_dt AS timestamptz), 'manual',
             :user, :notes, TRUE, :reason,
             CAST(:orig_id AS uuid))
        RETURNING tracking_event_id
    """), {
        "shipment_id": shipment_id,
        "event_code":  payload.event_code,
        "event_dt":    payload.event_datetime,
        "user":        user_id,
        "notes":       payload.notes,
        "reason":      payload.override_reason,
        "orig_id":     payload.corrected_event_id,
    })
    await db.commit()
    return {
        "new_event_id":      str(result.scalar()),
        "corrected_event_id":payload.corrected_event_id,
        "event_code":        payload.event_code,
        "override_reason":   payload.override_reason,
    }
