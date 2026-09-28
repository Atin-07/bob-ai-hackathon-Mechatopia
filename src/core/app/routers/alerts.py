import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from fastapi import Depends

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ---------------- WebSocket Connection Manager ----------------
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict):
        payload = json.dumps(message, default=str)
        for connection in list(self.active):
            try:
                await connection.send_text(payload)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


# ---------------- Ingest endpoint — person service posts here ----------------
@router.post("", status_code=201)
async def receive_person_alert(payload: schemas.PersonAlertPush):
    """The person service writes the person_alerts row itself, then calls
    this endpoint ONLY to push the alert live over the WebSocket.
    No DB insert happens here."""
    await manager.broadcast({"source": "person", **payload.model_dump()})
    return {"received": True}


# ---------------- WebSocket — ws://localhost:8000/alerts/ws ----------------
@router.websocket("/ws")
async def alerts_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)


# ---------------- REST: history ----------------
@router.get("/person", response_model=List[schemas.PersonAlertResponse])
def list_person_alerts(db: Session = Depends(get_db)):
    return (
        db.query(models.PersonAlert)
        .order_by(desc(models.PersonAlert.created_at))
        .limit(200)
        .all()
    )


@router.get("/feed")
def list_alerts_feed(db: Session = Depends(get_db)):
    """Person alerts feed, newest first. The dashboard loads this once on
    mount, then the WebSocket takes over for new arrivals."""
    def _utc(dt: Optional[datetime]) -> datetime:
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    person_alerts = (
        db.query(models.PersonAlert)
        .order_by(desc(models.PersonAlert.created_at))
        .limit(200)
        .all()
    )

    feed = [
        {
            "source": "person",
            "id": str(p.alert_id),
            "camera_id": p.camera_id,
            "category": p.category,
            "similarity_score": p.similarity_score,
            "headline": f"{p.category} person match ({p.similarity_score:.2f} similarity)",
            "severity": "HIGH" if p.category == "wanted" else "MEDIUM",
            "status": p.status,
            "timestamp": _utc(p.created_at),
        }
        for p in person_alerts
    ]
    return feed
