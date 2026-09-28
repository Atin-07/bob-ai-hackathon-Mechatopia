from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.database import get_db
from app.routers.cameras import normalize_status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/summary")
def platform_summary(db: Session = Depends(get_db)):
    statuses = [normalize_status(c.status) for (c,) in db.query(models.Camera.status).all()]
    missing = db.query(models.PersonMissing).filter(models.PersonMissing.status == "active").count()
    wanted = db.query(models.PersonWanted).filter(models.PersonWanted.status == "active").count()

    return {
        # cameras
        "total_cameras": len(statuses),
        "cameras_online": statuses.count("online"),
        "cameras_offline": statuses.count("offline"),
        "cameras_maintenance": statuses.count("maintenance"),
        # events / alerts (names match what the dashboard reads)
        "total_person_events": db.query(models.PersonEvent).count(),
        "total_vehicle_events": 0,  # vehicle service is not part of this build
        "total_alerts": db.query(models.PersonAlert).count(),
        "total_person_alerts": db.query(models.PersonAlert).count(),
        "total_users": db.query(models.User).count(),
        # watchlist
        "watchlist_missing": missing,
        "watchlist_wanted": wanted,
        "watchlist_entries": missing + wanted,
    }


@router.get("/organizations")
def list_organizations():
    return schemas.VALID_ORGANIZATIONS