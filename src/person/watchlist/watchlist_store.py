from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def load_combined_watchlist(session: AsyncSession) -> list[dict]:
    """
    Queries both person_missing and person_wanted (only 'active' status)
    and returns a single combined list shaped exactly as match_watchlist()
    expects:
      {"person_id": str, "name": str, "category": "missing"|"wanted",
       "reference_embedding": list[float]}
    """
    missing_rows = await session.execute(
        text(
            """
            SELECT person_id, name, reference_embedding
            FROM person_missing
            WHERE status = 'active'
            """
        )
    )
    wanted_rows = await session.execute(
        text(
            """
            SELECT person_id, name, reference_embedding
            FROM person_wanted
            WHERE status = 'active'
            """
        )
    )

    watchlist: list[dict] = []

    for row in missing_rows:
        watchlist.append({
            "person_id": str(row.person_id),
            "name": row.name,
            "category": "missing",
            "reference_embedding": _to_float_list(row.reference_embedding),
        })

    for row in wanted_rows:
        watchlist.append({
            "person_id": str(row.person_id),
            "name": row.name,
            "category": "wanted",
            "reference_embedding": _to_float_list(row.reference_embedding),
        })

    return watchlist


def _to_float_list(embedding) -> list[float]:
    """
    pgvector's asyncpg codec typically returns a list/array already, but
    guard against it coming back as a string like "[0.1,0.2,...]" depending
    on driver/version.
    """
    if isinstance(embedding, str):
        return [float(x) for x in embedding.strip("[]").split(",") if x]
    return list(embedding)