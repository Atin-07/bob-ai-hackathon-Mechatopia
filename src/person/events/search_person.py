import logging

import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Query
from sqlalchemy import text

from db import get_session
from schemas import SearchResponseOut, SearchMatchOut
from events.event_store import _embedding_to_pgvector_literal

from matching.embed_reference import embed_reference_photo

logger = logging.getLogger("person_service.search_person")

router = APIRouter()


@router.post("/person/search", response_model=SearchResponseOut)
async def search_person(
    file: UploadFile = File(...),
    top_k: int = Query(10, ge=1, le=100),
):
    """
    Accepts an uploaded reference photo, embeds it, and runs a pgvector
    nearest-neighbor search directly against person_events. This is a
    standalone search feature — separate from watchlist alerting, so it
    does NOT call match_watchlist().
    """
    raw_bytes = await file.read()
    np_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        return SearchResponseOut(matches=[])

    query_embedding = embed_reference_photo(image)
    embedding_literal = _embedding_to_pgvector_literal(query_embedding)

    async with get_session() as session:
        rows = await session.execute(
            text(
                """
                SELECT
                    event_id,
                    camera_id,
                    detected_at,
                    crop_image_path,
                    1 - (embedding <=> :query_embedding) AS similarity_score
                FROM person_events
                ORDER BY embedding <=> :query_embedding
                LIMIT :top_k
                """
            ),
            {"query_embedding": embedding_literal, "top_k": top_k},
        )

        matches = [
            SearchMatchOut(
                event_id=str(row.event_id),
                camera_id=row.camera_id,
                detected_at=row.detected_at.isoformat(),
                similarity_score=float(row.similarity_score),
                crop_image_path=row.crop_image_path,
            )
            for row in rows
        ]

    return SearchResponseOut(matches=matches)