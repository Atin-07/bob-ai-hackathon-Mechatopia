"""
watchlist_api.py  (NEW FILE -> src/person/watchlist/watchlist_api.py)

HTTP endpoints so the frontend can manage the missing / wanted list instead
of using the add_person.py command-line script.

  POST   /person/watchlist                        add a person (multipart form + photo)
  GET    /person/watchlist                        list people (optional filters)
  DELETE /person/watchlist/{category}/{person_id} deactivate a person

The frame worker reloads the active watchlist from the DB on every frame, so
a newly added person starts matching immediately - no restart needed.
"""

import logging
import os
import uuid
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from db import get_session
from matching.embed_reference import embed_reference_photo

logger = logging.getLogger("person_service.watchlist_api")

router = APIRouter()

# Reference photos are saved here and served by main.py at /reference/<file>
REFERENCE_DIR = os.environ.get("REFERENCE_PHOTO_DIR", "./reference_photos")
os.makedirs(REFERENCE_DIR, exist_ok=True)

VALID_CATEGORIES = ("missing", "wanted")


def _embedding_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _photo_url(person_id: str, has_photo: bool) -> Optional[str]:
    return f"/reference/{person_id}.jpg" if has_photo else None


@router.post("/person/watchlist", status_code=201)
async def add_watchlist_person(
    category: str = Form(...),                 # "missing" or "wanted"
    name: str = Form(...),
    age: Optional[int] = Form(None),
    details: Optional[str] = Form(None),       # description (missing) / crime description (wanted)
    reported_by: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    category = category.strip().lower()
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="category must be 'missing' or 'wanted'")
    if not name.strip():
        raise HTTPException(status_code=400, detail="name is required")

    raw = await file.read()
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Could not read the uploaded image")

    try:
        # Heavy CPU work -> thread pool so the event loop (frame worker) is not blocked
        embedding = await run_in_threadpool(embed_reference_photo, image)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))          # e.g. no face found
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Face model error: {e}")

    person_id = str(uuid.uuid4())

    # Save a re-encoded JPEG (never the raw upload bytes)
    ok, buf = cv2.imencode(".jpg", image)
    photo_saved = False
    if ok:
        with open(os.path.join(REFERENCE_DIR, f"{person_id}.jpg"), "wb") as f:
            f.write(buf.tobytes())
        photo_saved = True
    photo_path = os.path.join(REFERENCE_DIR, f"{person_id}.jpg") if photo_saved else None

    table = "person_missing" if category == "missing" else "person_wanted"
    details_col = "description" if category == "missing" else "crime_description"

    async with get_session() as session:
        row = await session.execute(
            text(
                f"""
                INSERT INTO {table}
                    (person_id, name, age, {details_col}, reference_embedding,
                     reference_image_path, reported_by, status)
                VALUES
                    (CAST(:person_id AS UUID), :name, :age, :details,
                     CAST(:embedding AS VECTOR), :photo_path, :reported_by, 'active')
                RETURNING created_at
                """
            ),
            {
                "person_id": person_id,
                "name": name.strip(),
                "age": age,
                "details": details,
                "embedding": _embedding_literal(embedding),
                "photo_path": photo_path,
                "reported_by": reported_by,
            },
        )
        created_at = row.scalar_one()
        await session.commit()

    logger.info(f"Added {category} person '{name}' id={person_id}")

    return {
        "person_id": person_id,
        "category": category,
        "name": name.strip(),
        "age": age,
        "details": details,
        "reported_by": reported_by,
        "status": "active",
        "photo_url": _photo_url(person_id, photo_saved),
        "created_at": created_at.isoformat(),
    }


@router.get("/person/watchlist")
async def list_watchlist(
    category: Optional[str] = Query(None, description="missing | wanted (omit for both)"),
    status: Optional[str] = Query("active", description="active | inactive | all"),
):
    if category is not None and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="category must be 'missing' or 'wanted'")

    categories = [category] if category else list(VALID_CATEGORIES)
    people: list[dict] = []

    async with get_session() as session:
        for cat in categories:
            table = "person_missing" if cat == "missing" else "person_wanted"
            details_col = "description" if cat == "missing" else "crime_description"

            where = "" if status in (None, "all") else "WHERE status = :status"
            params = {} if status in (None, "all") else {"status": status}

            rows = await session.execute(
                text(
                    f"""
                    SELECT person_id, name, age, {details_col} AS details,
                           reported_by, status, reference_image_path, created_at
                    FROM {table}
                    {where}
                    """
                ),
                params,
            )
            for r in rows:
                pid = str(r.person_id)
                people.append({
                    "person_id": pid,
                    "category": cat,
                    "name": r.name,
                    "age": r.age,
                    "details": r.details,
                    "reported_by": r.reported_by,
                    "status": r.status,
                    "photo_url": _photo_url(pid, bool(r.reference_image_path)),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })

    people.sort(key=lambda p: p["created_at"] or "", reverse=True)
    return {"people": people}


@router.delete("/person/watchlist/{category}/{person_id}")
async def deactivate_watchlist_person(category: str, person_id: str):
    """Soft delete: sets status='inactive' so the person stops matching, but
    past events and alerts that reference them stay intact (hard deleting
    would break those foreign keys)."""
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="category must be 'missing' or 'wanted'")
    try:
        uuid.UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="person_id is not a valid UUID")

    table = "person_missing" if category == "missing" else "person_wanted"

    async with get_session() as session:
        result = await session.execute(
            text(
                f"""
                UPDATE {table} SET status = 'inactive'
                WHERE person_id = CAST(:person_id AS UUID)
                RETURNING person_id
                """
            ),
            {"person_id": person_id},
        )
        found = result.first()
        await session.commit()

    if not found:
        raise HTTPException(status_code=404, detail="Person not found")

    return {"person_id": person_id, "category": category, "status": "inactive"}