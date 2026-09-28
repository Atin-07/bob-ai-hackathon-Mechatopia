from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Incoming batch request (POST /person/batch)
# ---------------------------------------------------------------------------

class FrameIn(BaseModel):
    camera_id: str
    organization_id: str
    pts_ms: float
    width: int
    height: int
    format: str = "jpeg"
    frame: str  # base64-encoded JPEG bytes


class BatchIn(BaseModel):
    frames: list[FrameIn]


class BatchAcceptedOut(BaseModel):
    status: str = "accepted"


# ---------------------------------------------------------------------------
# Shape returned by teammate's process_frame() — for reference/type hints
# only, not strictly enforced at runtime since it's a plain dict.
# ---------------------------------------------------------------------------

class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class DetectionResult(BaseModel):
    camera_id: str
    organization_id: str
    pts_ms: float
    bbox: BBox
    embedding: list[float]
    # crop_bytes intentionally excluded — raw bytes aren't JSON-serializable
    # here, this model is just for documentation/type-checking purposes.


# ---------------------------------------------------------------------------
# /person/search response
# ---------------------------------------------------------------------------

class SearchMatchOut(BaseModel):
    event_id: str
    camera_id: str
    detected_at: str
    similarity_score: float
    crop_image_path: Optional[str] = None


class SearchResponseOut(BaseModel):
    matches: list[SearchMatchOut]