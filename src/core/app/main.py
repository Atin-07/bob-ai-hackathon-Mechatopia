from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
import app.models as models
from app.routers import (
    cameras,
    admin,
    person_events,
    alerts,
    watchlist,
)

# 1. Enable pgvector extension inside the database first
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

# 2. Auto-create all tables in Postgres/PostGIS/pgvector
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Netra CCTV Core Backend", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(cameras.router)
app.include_router(admin.router)
app.include_router(person_events.router)
app.include_router(alerts.router)
app.include_router(watchlist.router)


@app.get("/api/ingest")
def get_ingest_catalogue(db: Session = Depends(get_db)):
    """Exposes online cameras for the ingestion service's CatalogClient."""
    db_cameras = db.query(models.Camera).filter(models.Camera.status == "online").all()
    catalogue = []
    for cam in db_cameras:
        catalogue.append({
            "camera_id": cam.camera_id,
            "organization_id": cam.organization_id or "ORG-01",
            "name": cam.name or "Camera Stream",
            "location": cam.location_name or cam.address or "Gandhinagar Lab",
            "codec": cam.codec or "H264",
            "live": str(cam.status) == "online",
            "stream_properties": {
                "width": cam.width or 1920,
                "height": cam.height or 1080,
                "fps": 30,
                "bitrate_kbps": 4000,
            },
            "rtsp_url": cam.rtsp_url or "",
            "webrtc_url": cam.webrtc_url or "",
            "hls_url": cam.hls_url or "",
        })
    return {"cameras": catalogue}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "core_backend"}


@app.get("/")
def root():
    return {"status": "CCTV Platform API running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)