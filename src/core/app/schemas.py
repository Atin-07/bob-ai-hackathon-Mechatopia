from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel


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
    webrtc: Optional[str] = None
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
# ORGANIZATIONS
# ============================================================
VALID_ORGANIZATIONS = [
    {"id": "ORG-POLICE", "label": "Police Department"},
    {"id": "ORG-TRANSPORT", "label": "Transport Department"},
    {"id": "ORG-MUNICIPAL", "label": "Municipal Corporation"},
]


# ============================================================
# PERSON SCHEMAS
# ============================================================
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
# ALERT PUSH (person service → core → websocket)
# ============================================================
class PersonAlertPush(BaseModel):
    alert_id: str
    event_id: str
    person_id: str
    camera_id: str
    category: str
    similarity_score: float
    crop_image_path: Optional[str] = None


# ============================================================
# GLS SYNC (ingestion → core cameras)
# ============================================================
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
