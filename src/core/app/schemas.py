from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, model_validator

# ============================================================
# CAMERA SCHEMAS
# ============================================================
class LocationIn(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class PropertiesIn(BaseModel):
    codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class StreamIn(BaseModel):
    rtsp: Optional[str] = None
    webrtc: Optional[str] = None   # preferred protocol
    hls: Optional[str] = None


class CameraCreate(BaseModel):
    camera_id: str
    organization_id: str
    organization_name: Optional[str] = None
    name: str
    status: str = "online"
    location: LocationIn
    camera_type: str = "IP"
    properties: Optional[PropertiesIn] = None
    stream: Optional[StreamIn] = None

    department: Optional[str] = None
    district: Optional[str] = None
    vms_vendor: Optional[str] = None
    storage_type: str = "cloud"
    retention_days: int = 7


class CameraOut(CameraCreate):
    install_date: datetime
    last_health_check: datetime

    class Config:
        from_attributes = True


class CamerasBulkImport(BaseModel):
    cameras: List[CameraCreate]


# ============================================================
# AUTH + WATCHLIST
# ============================================================
# Real organization_id values from the ingestion catalogue (see
# ingestion/departments/*.json). A non-admin's `department` is compared
# directly against Camera.organization_id in cameras.py's access control.
VALID_ORGANIZATIONS = [
    {"id": "ORG-POLICE", "label": "Police Department"},
    {"id": "ORG-TRANSPORT", "label": "Transport Department"},
    {"id": "ORG-MUNICIPAL", "label": "Municipal Corporation"},
]
_VALID_ORG_IDS = {org["id"] for org in VALID_ORGANIZATIONS}


class UserCreate(BaseModel):
    username: str
    password: str
    department: Optional[str] = None
    role: str = "viewer"

    @model_validator(mode="after")
    def validate_department_for_non_admin(self):
        if self.role != "admin" and self.department not in _VALID_ORG_IDS:
            raise ValueError(
                f"department must be one of {sorted(_VALID_ORG_IDS)} for non-admin users"
            )
        return self


class UserOut(BaseModel):
    id: int
    username: str
    department: Optional[str]
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WatchlistCreate(BaseModel):
    entry_type: str   # "vehicle" or "person"
    value: str
    reason: str
    added_by: Optional[str] = None


class WatchlistOut(WatchlistCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# VEHICLE SCHEMAS
# ============================================================
class VehicleEventCreate(BaseModel):
    camera_id: str
    organization_id: str
    event_type: str
    plate_number: Optional[str] = None
    confidence: float
    pts_ms: float
    speed_kmph: Optional[float] = None
    speed_limit_kmph: Optional[float] = None
    snapshot_url: Optional[str] = None
    helmet_status: Optional[str] = None


class VehicleEventResponse(VehicleEventCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WantedVehicleCreate(BaseModel):
    plate_number: str
    fir_number: Optional[str] = None
    crime_description: str
    severity: Optional[str] = "HIGH"
    issuing_authority: Optional[str] = "Gujarat Police"


class WantedVehicleResponse(WantedVehicleCreate):
    id: int
    registered_at: datetime

    class Config:
        from_attributes = True


class MissingVehicleCreate(BaseModel):
    plate_number: str
    owner_name: Optional[str] = None
    vehicle_model: Optional[str] = None
    report_number: Optional[str] = None
    contact_number: Optional[str] = None


class MissingVehicleResponse(MissingVehicleCreate):
    id: int
    reported_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    event_id: int
    plate_number: str
    camera_id: str
    alert_type: str
    severity: str
    details: str
    status: str
    triggered_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# PERSON SCHEMAS
# ============================================================
class PersonMissingCreate(BaseModel):
    name: str
    age: Optional[int] = None
    description: Optional[str] = None
    reference_embedding: List[float]
    reference_image_path: Optional[str] = None
    reported_by: Optional[str] = None
    status: Optional[str] = "active"


class PersonMissingResponse(PersonMissingCreate):
    person_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class PersonWantedCreate(BaseModel):
    name: str
    age: Optional[int] = None
    crime_description: Optional[str] = None
    reference_embedding: List[float]
    reference_image_path: Optional[str] = None
    reported_by: Optional[str] = None
    status: Optional[str] = "active"


class PersonWantedResponse(PersonWantedCreate):
    person_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class PersonEventCreate(BaseModel):
    camera_id: str
    organization_id: str
    pts_ms: float
    bbox: Dict[str, Any]
    embedding: List[float]
    crop_image_path: Optional[str] = None
    matched_missing_id: Optional[UUID] = None
    matched_wanted_id: Optional[UUID] = None


class PersonEventResponse(PersonEventCreate):
    event_id: UUID
    detected_at: datetime

    class Config:
        from_attributes = True


class PersonAlertResponse(BaseModel):
    alert_id: UUID
    event_id: Optional[UUID] = None
    missing_id: Optional[UUID] = None
    wanted_id: Optional[UUID] = None
    category: str
    camera_id: str
    similarity_score: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# FRAME BATCH (AI PIPELINE INPUT)
# ============================================================
class FrameIn(BaseModel):
    camera_id: str
    organization_id: str
    pts_ms: int
    width: int
    height: int
    format: str = "jpeg"
    frame: str   # base64-encoded JPEG


class FrameBatchIn(BaseModel):
    frames: List[FrameIn]


class FrameBatchStatus(BaseModel):
    status: str = "Completed"

# ============================================================
# VEHICLE TRACKING (map + full history view)
# ============================================================
class VehicleTrackPoint(BaseModel):
    id: int
    camera_id: str
    camera_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_type: str
    plate_number: Optional[str] = None
    confidence: float
    speed_kmph: Optional[float] = None
    speed_limit_kmph: Optional[float] = None
    helmet_status: Optional[str] = None
    snapshot_url: Optional[str] = None
    created_at: datetime


class VehicleTrackResponse(BaseModel):
    plate_number: str
    total_detections: int
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_camera_id: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    points: List[VehicleTrackPoint]


# ============================================================
# ALERT PUSH (from person microservice → core → websocket)
# ============================================================
class PersonAlertPush(BaseModel):
    alert_id: str
    event_id: str
    person_id: str
    camera_id: str
    category: str
    similarity_score: float
    crop_image_path: Optional[str] = None

class GLSCameraProperties(BaseModel):
    codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    bitrate_kbps: Optional[int] = None


class GLSCameraSync(BaseModel):
    camera_id: str
    organization_id: str
    name: str
    location: Optional[str] = None
    status: str = "online"
    camera_properties: Optional[GLSCameraProperties] = None
    webrtc_url: Optional[str] = None
    hls_url: Optional[str] = None
    rtsp_url: Optional[str] = None


class GLSSyncBatch(BaseModel):
    cameras: List[GLSCameraSync]