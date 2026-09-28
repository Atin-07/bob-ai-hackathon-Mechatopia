from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/summary")
def platform_summary(db: Session = Depends(get_db)):
    return {
        "total_cameras": db.query(models.Camera).count(),
        "total_person_events": db.query(models.PersonEvent).count(),
        "total_person_alerts": db.query(models.PersonAlert).count(),
        "watchlist_missing": db.query(models.PersonMissing).filter(models.PersonMissing.status == "active").count(),
        "watchlist_wanted": db.query(models.PersonWanted).filter(models.PersonWanted.status == "active").count(),
    }


@router.get("/organizations")
def list_organizations():
    return schemas.VALID_ORGANIZATIONS
