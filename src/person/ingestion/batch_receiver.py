import base64
import logging

import cv2
import numpy as np
from fastapi import APIRouter, status

from schemas import BatchIn, BatchAcceptedOut

logger = logging.getLogger("person_service.batch_receiver")

router = APIRouter()


@router.post("/person/batch", status_code=status.HTTP_202_ACCEPTED, response_model=BatchAcceptedOut)
async def receive_batch(batch: BatchIn):
    """
    Fast-path endpoint: decode frames and push onto the shared queue, then
    return immediately. NO detection/matching/DB work happens here — the
    ingestion service is waiting synchronously for this response, so any
    heavy work here would stall its next batch.
    """
    # Imported lazily to avoid a circular import with main.py (main.py
    # imports this router; this module needs main's shared queue).
    from main import frame_queue

    for f in batch.frames:
        try:
            jpeg_bytes = base64.b64decode(f.frame)
            np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            # Skip malformed frames rather than failing the whole batch
            logger.warning(f"Failed to decode frame from camera={f.camera_id}: {e}")
            continue

        if frame is None:
            logger.warning(f"cv2.imdecode returned None for camera={f.camera_id}")
            continue

        # Push (frame, camera_id, organization_id, pts_ms) — worker consumes this shape
        frame_queue.put_nowait((frame, f.camera_id, f.organization_id, f.pts_ms))

    return BatchAcceptedOut(status="accepted")