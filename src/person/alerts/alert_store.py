import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def store_alert(
    session: AsyncSession,
    event_id: str,
    category: str,
    missing_id: str | None,
    wanted_id: str | None,
    camera_id: str,
    similarity_score: float,
) -> str:
    """Inserts into person_alerts. Only one of missing_id/wanted_id will be non-null."""
    alert_id = str(uuid.uuid4())

    await session.execute(
        text(
            """
            INSERT INTO person_alerts (
                alert_id, event_id, missing_id, wanted_id,
                category, camera_id, similarity_score, status
            )
            VALUES (
                :alert_id, :event_id, :missing_id, :wanted_id,
                :category, :camera_id, :similarity_score, 'pending'
            )
            """
        ),
        {
            "alert_id": alert_id,
            "event_id": event_id,
            "missing_id": missing_id,
            "wanted_id": wanted_id,
            "category": category,
            "camera_id": camera_id,
            "similarity_score": similarity_score,
        },
    )

    return alert_id