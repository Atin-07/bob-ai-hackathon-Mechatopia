from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.routers.alerts import broadcast_vehicle_alert

router = APIRouter(prefix="/vehicle_events", tags=["Vehicle Events"])

from app.auth import SERVICE_KEY


# ---------------- Receive Events (ingestion) ----------------
@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.VehicleEventResponse)
def receive_vehicle_event(
    event_data: schemas.VehicleEventCreate,
    background_tasks: BackgroundTasks,
    x_service_key: str = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db),
):
    if x_service_key != SERVICE_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Service Key")

    new_event = models.VehicleEvent(**event_data.model_dump())
    db.add(new_event)
    db.flush()

    plate = event_data.plate_number
    created_alerts: List[models.Alert] = []

    if plate:
        wanted = db.query(models.WantedVehicle).filter(models.WantedVehicle.plate_number == plate).first()
        if wanted:
            alert = models.Alert(
                event_id=new_event.id,
                plate_number=plate,
                camera_id=event_data.camera_id,
                alert_type="WANTED",
                severity=wanted.severity,
                details=f"Wanted FIR: {wanted.fir_number} - {wanted.crime_description}",
            )
            db.add(alert)
            created_alerts.append(alert)

        missing = db.query(models.MissingVehicle).filter(models.MissingVehicle.plate_number == plate).first()
        if missing:
            alert = models.Alert(
                event_id=new_event.id,
                plate_number=plate,
                camera_id=event_data.camera_id,
                alert_type="MISSING",
                severity="HIGH",
                details=f"Missing Report: {missing.report_number} | Owner: {missing.owner_name} ({missing.vehicle_model})",
            )
            db.add(alert)
            created_alerts.append(alert)

    # Overspeed violation — guarded on the actual numbers too, not just the
    # event_type label (worker_pool.py already only sends event_type="speed"
    # when it's over the limit, but this makes the endpoint correct on its own).
    if (
        event_data.event_type == "speed"
        and event_data.speed_kmph is not None
        and event_data.speed_limit_kmph is not None
        and event_data.speed_kmph > event_data.speed_limit_kmph
    ):
        alert = models.Alert(
            event_id=new_event.id,
            plate_number=plate or "UNKNOWN",
            camera_id=event_data.camera_id,
            alert_type="SPEED",
            severity="MEDIUM",
            details=f"Overspeeding: {event_data.speed_kmph} km/h (Limit: {event_data.speed_limit_kmph} km/h)",
        )
        db.add(alert)
        created_alerts.append(alert)

    db.commit()
    db.refresh(new_event)

    # Push every alert created by this event to the live dashboard.
    for alert in created_alerts:
        db.refresh(alert)
        background_tasks.add_task(broadcast_vehicle_alert, alert)

    return new_event


# ---------------- Query Endpoints ----------------
@router.get("", response_model=List[schemas.VehicleEventResponse])
def list_vehicle_events(
    camera_id: Optional[str] = None,
    plate_number: Optional[str] = None,
    organization_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.VehicleEvent)
    if camera_id:
        query = query.filter(models.VehicleEvent.camera_id == camera_id)
    if plate_number:
        query = query.filter(models.VehicleEvent.plate_number == plate_number)
    if organization_id:
        query = query.filter(models.VehicleEvent.organization_id == organization_id)
    return query.order_by(models.VehicleEvent.created_at.desc()).limit(500).all()


@router.get("/track/{plate_number}", response_model=schemas.VehicleTrackResponse)
def track_vehicle(plate_number: str, db: Session = Depends(get_db)):
    """Full sighting history for one plate: every camera it was seen at, in
    chronological order, each point already carrying that camera's name and
    lat/long so the frontend doesn't need a second round of camera lookups.
    Also surfaces the most recent sighting on its own so the frontend can
    drop a single 'last known location' marker."""
    rows = (
        db.query(models.VehicleEvent, models.Camera)
        .outerjoin(models.Camera, models.Camera.camera_id == models.VehicleEvent.camera_id)
        .filter(models.VehicleEvent.plate_number == plate_number)
        .order_by(models.VehicleEvent.created_at.asc())
        .all()
    )

    points = [
        schemas.VehicleTrackPoint(
            id=event.id,
            camera_id=event.camera_id,
            camera_name=camera.name if camera else None,
            latitude=camera.latitude if camera else None,
            longitude=camera.longitude if camera else None,
            event_type=event.event_type,
            plate_number=event.plate_number,
            confidence=float(event.confidence),
            speed_kmph=float(event.speed_kmph) if event.speed_kmph is not None else None,
            speed_limit_kmph=float(event.speed_limit_kmph) if event.speed_limit_kmph is not None else None,
            helmet_status=event.helmet_status,
            snapshot_url=event.snapshot_url,
            created_at=event.created_at,
        )
        for event, camera in rows
    ]

    last = points[-1] if points else None

    return schemas.VehicleTrackResponse(
        plate_number=plate_number,
        total_detections=len(points),
        first_seen=points[0].created_at if points else None,
        last_seen=last.created_at if last else None,
        last_camera_id=last.camera_id if last else None,
        last_latitude=last.latitude if last else None,
        last_longitude=last.longitude if last else None,
        points=points,
    )