import asyncio
import logging
import os

from sqlalchemy import text

from db import get_session

logger = logging.getLogger("person_service.retention_cleanup")

CLEANUP_INTERVAL_SECONDS = 60 * 60  # run every hour
RETENTION_HOURS = 48


async def retention_cleanup_loop():
    """
    Background loop: every hour, deletes unmatched person_events older than
    48 hours, and removes their crop files from disk.
    """
    logger.info("retention_cleanup_loop started")
    while True:
        try:
            await _run_cleanup_once()
        except asyncio.CancelledError:
            logger.info("retention_cleanup_loop cancelled, exiting")
            raise
        except Exception:
            logger.exception("Error during retention cleanup")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def _run_cleanup_once():
    async with get_session() as session:
        # Grab paths first so we can delete the files after the DB delete succeeds
        rows = await session.execute(
            text(
                f"""
                SELECT event_id, crop_image_path
                FROM person_events
                WHERE detected_at < now() - interval '{RETENTION_HOURS} hours'
                  AND matched_missing_id IS NULL
                  AND matched_wanted_id IS NULL
                """
            )
        )
        to_delete = rows.fetchall()

        if not to_delete:
            return

        result = await session.execute(
            text(
                f"""
                DELETE FROM person_events
                WHERE detected_at < now() - interval '{RETENTION_HOURS} hours'
                  AND matched_missing_id IS NULL
                  AND matched_wanted_id IS NULL
                """
            )
        )
        await session.commit()

        logger.info(f"Retention cleanup: deleted {result.rowcount} unmatched events")

        for row in to_delete:
            crop_path = row.crop_image_path
            if crop_path and os.path.exists(crop_path):
                try:
                    os.remove(crop_path)
                except OSError:
                    logger.warning(f"Failed to delete crop file {crop_path}")