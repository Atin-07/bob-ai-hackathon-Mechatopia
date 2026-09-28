import base64
from fastapi import APIRouter

import app.schemas as schemas
from app.frame_worker import FrameWorkerPool

router = APIRouter(prefix="/vehicle-frames", tags=["vehicle-ai"])

# One pool per AI pipeline, created once at import time (not per-request) so
# workers stay warm and ready across batches instead of being spun up fresh
# each time — this is what keeps "at least 2 workers" always available.
pool = FrameWorkerPool(name="vehicle-ai-worker")


def process_vehicle_frame(frame: schemas.FrameIn) -> dict:
    """TODO (vehicle/ANPR squad): replace this stub with real processing:
      1. Decode the frame (already done below — `raw_bytes` is the JPEG).
      2. Run plate detection (e.g. YOLOv8) + OCR (EasyOCR/PaddleOCR).
      3. Optionally estimate speed and detect helmet status.
      4. If a plate is found, POST it to /vehicle-events — that endpoint
         already checks it against the watchlist and raises an alert
         automatically, so you don't need to duplicate that logic here.
    This stub currently just decodes the frame and confirms it was received,
    so the ingestion pipeline itself is fully working end to end already.
    """
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
def ingest_vehicle_frames(batch: schemas.FrameBatchIn):
    """Accepts a batch of frames (the { "frames": [...] } shape), processes
    every frame concurrently across the worker pool, and only responds once
    the entire batch has finished — matching the { "status": "Completed" }
    contract."""
    pool.process_batch(batch.frames, process_vehicle_frame)
    return {"status": "Completed"}


@router.get("/worker-info")
def worker_info():
    """Handy to sanity-check how many workers are actually running."""
    return {"pool": pool.name, "max_workers": pool.max_workers}
