import os
import uuid
import json
import logging

from sqlalchemy import text

from config import settings

logger = logging.getLogger("person_service.event_store")


def _embedding_to_pgvector_literal(embedding: list[float]) -> str:
    """Convert a plain float list into the string form pgvector expects
    when bound as a raw-SQL parameter, e.g. "[0.1,0.2,...]"."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


async def store_event(session, detection: dict, matched_missing_id, matched_wanted_id):
    """
    Inserts one row into person_events for a single detected face.
    Always called, regardless of whether it matched anything.

    detection is one entry from process_frame()'s output:
      {
        "camera_id": str,
        "organization_id": str,
        "pts_ms": float,
        "bbox": {"x": int, "y": int, "w": int, "h": int},
        "embedding": list[float],   # length 512
        "crop_bytes": bytes,
      }

    Returns (event_id, crop_image_path) so the caller can forward the
    crop path in an alert payload without a second DB round-trip.
    """

    event_id = str(uuid.uuid4())

    # Save the face crop to disk, never the full frame.
    crop_image_path = None
    crop_bytes = detection.get("crop_bytes")
    if crop_bytes:
        crop_image_path = os.path.join(settings.CROP_STORAGE_DIR, f"{event_id}.jpg")
        try:
            with open(crop_image_path, "wb") as f:
                f.write(crop_bytes)
        except OSError:
            logger.exception(f"Failed to write crop for event={event_id}, continuing without it")
            crop_image_path = None

    embedding_literal = _embedding_to_pgvector_literal(detection["embedding"])

    def _to_native(value):
        """Convert numpy scalar types (e.g. numpy.int64 from cv2/YOLO bbox
        coordinates) into plain Python int/float so json.dumps() can
        serialize them. Leaves already-native values untouched."""
        if hasattr(value, "item"):
            return value.item()
        return value

    bbox_native = {k: _to_native(v) for k, v in detection["bbox"].items()}

    await session.execute(
        text("""
            INSERT INTO person_events (
                event_id, camera_id, organization_id, pts_ms,
                bbox, embedding, crop_image_path,
                matched_missing_id, matched_wanted_id
            )
            VALUES (
                :event_id, :camera_id, :organization_id, :pts_ms,
                CAST(:bbox AS JSONB), CAST(:embedding AS VECTOR), :crop_image_path,
                :matched_missing_id, :matched_wanted_id
            )
        """),
        {
            "event_id": event_id,
            "camera_id": detection["camera_id"],
            "organization_id": detection["organization_id"],
            "pts_ms": detection["pts_ms"],
            "bbox": json.dumps(bbox_native),
            "embedding": embedding_literal,
            "crop_image_path": crop_image_path,
            "matched_missing_id": matched_missing_id,
            "matched_wanted_id": matched_wanted_id,
        },
    )

    return event_id, crop_image_path