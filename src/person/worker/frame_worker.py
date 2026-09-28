import asyncio
import logging

from config import settings
from db import get_session
from watchlist.watchlist_store import load_combined_watchlist
from events.event_store import store_event
from alerts.cooldown import CooldownTracker
from alerts.alert_store import store_alert
from alerts.send_to_core import send_alert_to_core

from detection_recognition.extract_embedding import process_frame
from matching.match_watchlist import match_watchlist

logger = logging.getLogger("person_service.frame_worker")

# In-memory cooldown tracker shared across the worker's lifetime
cooldown_tracker = CooldownTracker(cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS)


async def frame_worker(queue: asyncio.Queue):
    """
    Background coroutine: drains the shared queue at its own pace and does
    all the real work — detection, matching, storage, alerting.
    """
    logger.info("frame_worker started")
    while True:
        try:
            frame, camera_id, organization_id, pts_ms = await queue.get()
        except asyncio.CancelledError:
            logger.info("frame_worker cancelled, exiting")
            raise

        try:
            await _process_one_frame(frame, camera_id, organization_id, pts_ms)
        except Exception:
            logger.exception(
                f"Error processing frame from camera={camera_id} org={organization_id}"
            )
        finally:
            queue.task_done()


async def _process_one_frame(frame, camera_id: str, organization_id: str, pts_ms: float):
    # 1. Detect + embed all faces in this frame (teammate's function, black box)
    detections = process_frame(frame, camera_id, organization_id, pts_ms)

    if not detections:
        return

    async with get_session() as session:
        # Load once per frame (not once per face) to keep DB round-trips down
        watchlist = await load_combined_watchlist(session)

        for detection in detections:
            matched_missing_id = None
            matched_wanted_id = None
            match_result = {"matched": False}

            if watchlist:
                match_result = match_watchlist(
                    detection["embedding"], watchlist, threshold=settings.MATCH_THRESHOLD
                )

            if match_result.get("matched"):
                if match_result["category"] == "missing":
                    matched_missing_id = match_result["person_id"]
                elif match_result["category"] == "wanted":
                    matched_wanted_id = match_result["person_id"]

            # Always store the event, matched or not.
            # store_event returns (event_id, crop_image_path) so the real
            # crop path can be forwarded to core in the alert payload below.
            event_id, crop_image_path = await store_event(
                session, detection, matched_missing_id, matched_wanted_id
            )
            await session.commit()

            # Only alert on a match, and only if not on cooldown
            if match_result.get("matched"):
                person_id = match_result["person_id"]
                category = match_result["category"]

                if not cooldown_tracker.is_on_cooldown(camera_id, person_id):
                    alert_id = await store_alert(
                        session,
                        event_id=event_id,
                        category=category,
                        missing_id=matched_missing_id,
                        wanted_id=matched_wanted_id,
                        camera_id=camera_id,
                        similarity_score=match_result["similarity_score"],
                    )
                    await session.commit()

                    await send_alert_to_core({
                        "alert_id": alert_id,
                        "event_id": event_id,
                        "person_id": person_id,
                        "camera_id": camera_id,
                        "category": category,
                        "similarity_score": match_result["similarity_score"],
                        "crop_image_path": crop_image_path,
                    })

                    cooldown_tracker.record_alert(camera_id, person_id)
                else:
                    logger.debug(
                        f"Skipping alert for person={person_id} camera={camera_id}: on cooldown"
                    )