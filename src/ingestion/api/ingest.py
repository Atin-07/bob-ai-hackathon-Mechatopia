"""Mock government camera catalogue endpoint.

In production this contract would be served by an external government system.
For this hackathon we simulate it locally by aggregating the JSON files under
``cctv-platform/ingestion/departments/`` and serving them over real HTTP, so
that ``catalogue/catalog_client.py`` (and any other consumer) can poll it
exactly as it would poll the real thing.

This module is a read-only, consume-only mock: no POST/PUT/DELETE, no auth.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("ingest_api")

router = APIRouter(tags=["catalogue"])

# Resolved relative to this file, so it works regardless of CWD.
_DEPARTMENTS_DIR = Path(__file__).resolve().parent.parent / "departments"


def _load_all_cameras() -> list[dict]:
    """Load and merge cameras from every department JSON file.

    Malformed or unreadable files are skipped with a logged warning rather
    than failing the whole catalogue.
    """

    all_cameras: list[dict] = []

    if not _DEPARTMENTS_DIR.exists():
        logger.warning("Departments directory not found: %s", _DEPARTMENTS_DIR)
        return all_cameras

    for file_path in sorted(_DEPARTMENTS_DIR.glob("*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            organization_name = data.get("organization_name", "Unknown")
            cameras = data.get("cameras", [])

            for camera in cameras:
                camera_with_department = dict(camera)
                camera_with_department["department"] = organization_name
                all_cameras.append(camera_with_department)

        except (json.JSONDecodeError, OSError, KeyError, TypeError) as error:
            logger.warning(
                "Skipping malformed department file %s: %s",
                file_path.name,
                error,
            )
            continue

    return all_cameras


@router.get("/api/ingest")
async def get_catalogue() -> dict:
    """Return the full merged camera catalogue.

    Response shape:
        {
            "cameras": [ ... ],
            "total": <int>,
            "generated_at": "<UTC ISO-8601 timestamp>"
        }
    """

    cameras = _load_all_cameras()

    return {
        "cameras": cameras,
        "total": len(cameras),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/ingest/{camera_id}")
async def get_camera(camera_id: str) -> dict:
    """Return a single camera by id, or 404 if it does not exist."""

    cameras = _load_all_cameras()

    for camera in cameras:
        if camera.get("camera_id") == camera_id:
            return camera

    raise HTTPException(status_code=404, detail=f"Camera not found: {camera_id}")