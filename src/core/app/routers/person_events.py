from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.database import get_db

router = APIRouter(prefix="/person-events", tags=["person-events"])

# NOTE: In your real pipeline, cctv-platform/person/ writes person_events and
# person_alerts DIRECTLY into this same Postgres database via raw SQL
# (person/events/event_store.py, person/alerts/alert_store.py) and only
# calls core's POST /alerts to push the match live to the frontend — it does
# NOT call this endpoint. This is kept around for manual testing / any tool
# that wants to insert a person_event over HTTP instead of raw SQL.


@router.post("", response_model=schemas.PersonEventResponse, status_code=201)
def create_person_event(event: schemas.PersonEventCreate, db: Session = Depends(get_db)):
    db_event = models.PersonEvent(**event.model_dump(exclude_unset=True))
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.get("", response_model=List[schemas.PersonEventResponse])
def list_person_events(
    camera_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.PersonEvent)
    if camera_id:
        query = query.filter(models.PersonEvent.camera_id == camera_id)
    if organization_id:
        query = query.filter(models.PersonEvent.organization_id == organization_id)
    return query.order_by(models.PersonEvent.detected_at.desc()).limit(500).all()