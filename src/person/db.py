from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

from config import settings

# Normalize the DSN so SQLAlchemy uses the asyncpg driver
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("postgresql://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgres://"):
    _async_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    _async_url = _raw_url

engine = create_async_engine(_async_url, pool_pre_ping=True, echo=False)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session():
    """Shared async session context manager. Usage: `async with get_session() as session:`"""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# --- Idempotent schema safety net -----------------------------------------
# We assume these tables already exist in the shared DB, but this is a
# harmless safety net in case this service is the first to touch the DB
# (e.g. in local/dev/demo environments).

_DDL_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS person_missing (
        person_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name                 TEXT NOT NULL,
        age                  INT,
        description          TEXT,
        reference_embedding  VECTOR(512) NOT NULL,
        reference_image_path TEXT,
        reported_by          TEXT,
        status               TEXT DEFAULT 'active',
        created_at           TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS person_wanted (
        person_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name                 TEXT NOT NULL,
        age                  INT,
        crime_description    TEXT,
        reference_embedding  VECTOR(512) NOT NULL,
        reference_image_path TEXT,
        reported_by          TEXT,
        status               TEXT DEFAULT 'active',
        created_at           TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS person_events (
        event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        camera_id            TEXT NOT NULL,
        organization_id      TEXT NOT NULL,
        pts_ms               DOUBLE PRECISION NOT NULL,
        detected_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        bbox                 JSONB NOT NULL,
        embedding             VECTOR(512) NOT NULL,
        crop_image_path       TEXT,
        matched_missing_id    UUID REFERENCES person_missing(person_id),
        matched_wanted_id     UUID REFERENCES person_wanted(person_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS person_alerts (
        alert_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        event_id             UUID REFERENCES person_events(event_id),
        missing_id            UUID REFERENCES person_missing(person_id),
        wanted_id              UUID REFERENCES person_wanted(person_id),
        category                TEXT NOT NULL CHECK (category IN ('missing', 'wanted')),
        camera_id                 TEXT NOT NULL,
        similarity_score           FLOAT NOT NULL,
        created_at                    TIMESTAMPTZ DEFAULT now(),
        status                           TEXT DEFAULT 'pending'
    )
    """,
    # ivfflat indexes for fast approximate nearest-neighbor search.
    # ivfflat requires some rows to build well, so wrap in DO blocks that
    # won't fail startup on an empty table / already-existing index.
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = 'ix_person_events_embedding'
        ) THEN
            CREATE INDEX ix_person_events_embedding
            ON person_events USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        END IF;
    EXCEPTION WHEN OTHERS THEN
        -- ivfflat can fail to build on an empty table in some pgvector
        -- versions; safe to skip, it'll still work as a seq scan.
        NULL;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = 'ix_person_missing_embedding'
        ) THEN
            CREATE INDEX ix_person_missing_embedding
            ON person_missing USING ivfflat (reference_embedding vector_cosine_ops)
            WITH (lists = 100);
        END IF;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = 'ix_person_wanted_embedding'
        ) THEN
            CREATE INDEX ix_person_wanted_embedding
            ON person_wanted USING ivfflat (reference_embedding vector_cosine_ops)
            WITH (lists = 100);
        END IF;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END $$;
    """,
]


async def init_db():
    """Run idempotent extension/table/index setup. Safe to call on every startup."""
    async with engine.begin() as conn:
        for stmt in _DDL_STATEMENTS:
            await conn.execute(text(stmt))


async def close_db():
    await engine.dispose()