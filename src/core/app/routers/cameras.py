import csv
import io
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

import app.models as models
import app.schemas as schemas
import app.auth as auth
from app.database import get_db
import random

# ---------- Gujarat bounding box (approx) — used only to give GLS-synced
# cameras a plottable position, since gls-sync's payload has no lat/long
# field at all (only a free-text "location" string, stored as address). ----------
GUJARAT_LAT_RANGE = (20.1, 24.7)
GUJARAT_LNG_RANGE = (68.2, 74.5)


def _random_gujarat_coords():
    lat = round(random.uniform(*GUJARAT_LAT_RANGE), 6)
    lng = round(random.uniform(*GUJARAT_LNG_RANGE), 6)
    return lat, lng

router = APIRouter(prefix="/cameras", tags=["cameras"])


# ---------- helpers: flat DB row <-> nested contract shape ----------

def _camera_to_out(cam: models.Camera) -> dict:
    return {
        "camera_id": cam.camera_id,
        "organization_id": cam.organization_id,
        "organization_name": cam.organization_name,
        "name": cam.name,
        "status": cam.status,
        "location": {
            "latitude": cam.latitude,
            "longitude": cam.longitude,
            "address": cam.address,
        },
        "camera_type": cam.camera_type,
        "properties": {
            "codec": cam.codec,
            "width": cam.width,
            "height": cam.height,
        },
        "stream": {
            "rtsp": cam.rtsp_url,
            "webrtc": cam.webrtc_url,
            "hls": cam.hls_url,
        },
        "department": cam.department,
        "district": cam.district,
        "vms_vendor": cam.vms_vendor,
        "storage_type": cam.storage_type,
        "retention_days": cam.retention_days,
        "install_date": cam.install_date,
        "last_health_check": cam.last_health_check,
    }


def _build_camera_row(payload: schemas.CameraCreate) -> models.Camera:
    props = payload.properties or schemas.PropertiesIn()
    stream = payload.stream or schemas.StreamIn()
    return models.Camera(
        camera_id=payload.camera_id,
        organization_id=payload.organization_id,
        organization_name=payload.organization_name,
        name=payload.name,
        status=payload.status,
        latitude=payload.location.latitude,
        longitude=payload.location.longitude,
        address=payload.location.address,
        camera_type=payload.camera_type,
        codec=props.codec,
        width=props.width,
        height=props.height,
        rtsp_url=stream.rtsp,
        webrtc_url=stream.webrtc,
        hls_url=stream.hls,
        department=payload.department or payload.organization_name,
        district=payload.district,
        vms_vendor=payload.vms_vendor,
        storage_type=payload.storage_type,
        retention_days=payload.retention_days,
    )


# ---------- CRUD ----------

@router.post("", response_model=schemas.CameraOut)
def create_camera(
    camera: schemas.CameraCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    existing = db.query(models.Camera).filter(models.Camera.camera_id == camera.camera_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="camera_id already exists")
    db_camera = _build_camera_row(camera)
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return _camera_to_out(db_camera)


@router.get("", response_model=List[schemas.CameraOut])
def list_cameras(
    department: Optional[str] = None,
    district: Optional[str] = None,
    status: Optional[str] = None,
    organization_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.Camera)

    # Access control: a non-admin user only ever sees their own department's
    # cameras, no matter what "department" filter they pass in — admins see
    # everything and can filter by any department they like.
    # Scope by organization_id, not the free-text "department" field — the
    # ingestion squad's real catalogue tags cameras with organization_id
    # values (ORG-POLICE, ORG-TRANSPORT, ORG-MUNICIPAL); department names
    # aren't guaranteed to match a user's department string exactly. A
    # user's "department" column stores an organization_id value.
    if current_user.role != "admin":
        query = query.filter(models.Camera.organization_id == current_user.department)
    elif department:
        query = query.filter(models.Camera.department == department)

    if district:
        query = query.filter(models.Camera.district == district)
    if status:
        query = query.filter(models.Camera.status == status)
    if organization_id:
        query = query.filter(models.Camera.organization_id == organization_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.Camera.camera_id.ilike(like)) | (models.Camera.name.ilike(like))
        )
    return [_camera_to_out(c) for c in query.all()]


@router.get("/{camera_id}", response_model=schemas.CameraOut)
def get_camera(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    cam = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    if current_user.role != "admin" and cam.organization_id != current_user.department:
        raise HTTPException(status_code=403, detail="Not authorized to view this camera")
    return _camera_to_out(cam)


@router.patch("/{camera_id}/status")
def update_status(
    camera_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    cam = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    cam.status = status
    db.commit()
    return {"camera_id": camera_id, "status": status}


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    cam = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    db.delete(cam)
    db.commit()
    return {"deleted": camera_id}


@router.delete("")
def reset_all_cameras(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    count = db.query(models.Camera).delete()
    db.commit()
    return {"deleted_count": count}


# ---------- Bulk import: JSON, matching the exact { "cameras": [...] } contract ----------

@router.post("/bulk-import-json")
def bulk_import_json(
    payload: schemas.CamerasBulkImport,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    created, skipped = 0, 0
    for camera in payload.cameras:
        exists = db.query(models.Camera).filter(models.Camera.camera_id == camera.camera_id).first()
        if exists:
            skipped += 1
            continue
        db.add(_build_camera_row(camera))
        created += 1
    db.commit()
    return {"created": created, "skipped_existing": skipped}


# ---------- Bulk import: CSV, for quick hackathon dataset loading ----------

@router.post("/bulk-import")
async def bulk_import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    content = await file.read()
    decoded = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    created, skipped = 0, 0
    for row in reader:
        exists = db.query(models.Camera).filter(models.Camera.camera_id == row["camera_id"]).first()
        if exists:
            skipped += 1
            continue
        cam = models.Camera(
            camera_id=row["camera_id"],
            organization_id=row.get("organization_id", "ORG-UNKNOWN"),
            organization_name=row.get("organization_name") or None,
            name=row["name"],
            status=row.get("status", "online"),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            address=row.get("address") or None,
            camera_type=row.get("camera_type", "IP"),
            codec=row.get("codec") or None,
            width=int(row["width"]) if row.get("width") else None,
            height=int(row["height"]) if row.get("height") else None,
            rtsp_url=row.get("rtsp_url") or None,
            webrtc_url=row.get("webrtc_url") or None,
            hls_url=row.get("hls_url") or None,
            department=row.get("department") or None,
            district=row.get("district") or None,
            vms_vendor=row.get("vms_vendor") or None,
            storage_type=row.get("storage_type", "cloud"),
            retention_days=int(row.get("retention_days", 7)),
        )
        db.add(cam)
        created += 1
    db.commit()
    return {"created": created, "skipped_existing": skipped}


@router.get("/export/csv")
def export_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    cameras = db.query(models.Camera).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["camera_id", "organization_id", "organization_name", "name", "status",
                      "latitude", "longitude", "address", "camera_type", "codec", "width",
                      "height", "rtsp_url", "webrtc_url", "hls_url", "department", "district",
                      "vms_vendor", "storage_type", "retention_days"])
    for c in cameras:
        writer.writerow([c.camera_id, c.organization_id, c.organization_name, c.name, c.status,
                          c.latitude, c.longitude, c.address, c.camera_type, c.codec, c.width,
                          c.height, c.rtsp_url, c.webrtc_url, c.hls_url, c.department, c.district,
                          c.vms_vendor, c.storage_type, c.retention_days])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cameras_export.csv"},
    )


# ---------- Gap analysis ----------

@router.get("/reports/gap-analysis")
def gap_analysis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    by_district = (
        db.query(models.Camera.district, func.count(models.Camera.id))
        .group_by(models.Camera.district)
        .all()
    )
    by_department = (
        db.query(models.Camera.department, func.count(models.Camera.id))
        .group_by(models.Camera.department)
        .all()
    )
    flagged = (
        db.query(models.Camera)
        .filter(models.Camera.status.in_(["inactive", "offline", "maintenance"]))
        .all()
    )
    return {
        "cameras_per_district": [{"district": d, "count": c} for d, c in by_district],
        "cameras_per_department": [{"department": d, "count": c} for d, c in by_department],
        "flagged_for_attention": [
            {"camera_id": c.camera_id, "name": c.name, "district": c.district, "status": c.status}
            for c in flagged
        ],
        "total_cameras": db.query(models.Camera).count(),
    }



# ---------- GLS sync: accepts ingestion/catalogue/gls_sync.py's real payload ----------

@router.post("/gls-sync", dependencies=[Depends(auth.verify_service_key)])
def gls_sync(
    payload: schemas.GLSSyncBatch,
    db: Session = Depends(get_db),
):
    """The ingestion squad's GLSSync class calls this on a repeating timer,
    full catalogue each time — including offline cameras. Unlike
    bulk-import-json, this UPSERTS: an existing camera_id gets its status/
    name/stream URLs updated in place, since a camera going offline needs
    to actually update the record, not be silently skipped as a
    'duplicate'. Coordinates aren't provided by this payload (only a
    free-text "location" string) — stored as address; latitude/longitude
    stay null until another source provides them."""
    created, updated = 0, 0
    for camera in payload.cameras:
        props = camera.camera_properties or schemas.GLSCameraProperties()
        existing = db.query(models.Camera).filter(models.Camera.camera_id == camera.camera_id).first()

        if existing:
            existing.organization_id = camera.organization_id
            existing.name = camera.name
            existing.address = camera.location
            existing.status = camera.status
            existing.codec = props.codec
            existing.width = props.width
            existing.height = props.height
            existing.rtsp_url = camera.rtsp_url
            existing.webrtc_url = camera.webrtc_url
            existing.hls_url = camera.hls_url
            if not existing.department:
                existing.department = camera.organization_id
            # Backfill only if still unset — never overwrite real coordinates
            # that a CSV/JSON import or manual edit already gave this camera.
            if existing.latitude is None or existing.longitude is None:
                existing.latitude, existing.longitude = _random_gujarat_coords()
            updated += 1
        else:
            lat, lng = _random_gujarat_coords()
            db.add(models.Camera(
                camera_id=camera.camera_id,
                organization_id=camera.organization_id,
                organization_name=None,
                name=camera.name,
                status=camera.status,
                latitude=lat,
                longitude=lng,
                address=camera.location,
                camera_type="IP",
                codec=props.codec,
                width=props.width,
                height=props.height,
                rtsp_url=camera.rtsp_url,
                webrtc_url=camera.webrtc_url,
                hls_url=camera.hls_url,
                department=camera.organization_id,
                district=None,
            ))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}