import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, close_db
from ingestion.batch_receiver import router as batch_router
from events.search_person import router as search_router
from worker.frame_worker import frame_worker
from jobs.retention_cleanup import retention_cleanup_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("person_service")

# Shared queue: batch_receiver pushes (frame, camera_id, organization_id, pts_ms)
# tuples onto this, frame_worker drains it. Created once here and imported
# elsewhere so every module shares the same instance.
frame_queue: asyncio.Queue = asyncio.Queue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    await init_db()
    logger.info("DB initialized")

    worker_task = asyncio.create_task(frame_worker(frame_queue))
    cleanup_task = asyncio.create_task(retention_cleanup_loop())
    logger.info("Background worker + retention cleanup started")

    yield

    # --- shutdown ---
    worker_task.cancel()
    cleanup_task.cancel()
    for t in (worker_task, cleanup_task):
        try:
            await t
        except asyncio.CancelledError:
            pass

    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(title="Person Tracking Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],  # add other dev/prod origins as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batch_router)
app.include_router(search_router)


@app.get("/health")
async def health():
    return {"status": "ok"}