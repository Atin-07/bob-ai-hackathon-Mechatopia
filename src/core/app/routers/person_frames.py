import base64
from fastapi import APIRouter

import app.schemas as schemas
from app.frame_worker import FrameWorkerPool

router = APIRouter(prefix="/person-frames", tags=["face-ai"])

pool = FrameWorkerPool(name="face-ai-worker")


def process_person_frame(frame: schemas.FrameIn) -> dict:
    """TODO (facial-recognition squad): replace this stub with real
    processing — face detection + recognition/matching — then POST any
    identified person to /person-events, which already checks the
    watchlist and raises an alert automatically."""
    try:
        raw_bytes = base64.b64decode(frame.frame)
    except Exception:
        raw_bytes = b""
    return {
        "camera_id": frame.camera_id,
        "organization_id": frame.organization_id,
        "pts_ms": frame.pts_ms,
        "bytes_received": len(raw_bytes),
        "processed": True,
    }


@router.post("/ingest", response_model=schemas.FrameBatchStatus)
def ingest_person_frames(batch: schemas.FrameBatchIn):
    pool.process_batch(batch.frames, process_person_frame)
    return {"status": "Completed"}


@router.get("/worker-info")
def worker_info():
    return {"pool": pool.name, "max_workers": pool.max_workers}
