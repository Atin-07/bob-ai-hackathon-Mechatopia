from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
import app.auth as auth
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/summary")
def platform_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    return {
        "total_cameras": db.query(models.Camera).count(),
        "total_users": db.query(models.User).count(),
        "total_vehicle_events": db.query(models.VehicleEvent).count(),
        "total_person_events": db.query(models.PersonEvent).count(),
        "total_alerts": db.query(models.Alert).count(),
        "watchlist_entries": db.query(models.Watchlist).count(),
    }


# ---------- User management (admin only) ----------

@router.get("/users", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    return db.query(models.User).all()


@router.post("/users", response_model=schemas.UserOut)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    existing = db.query(models.User).filter(models.User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    db_user = models.User(
        username=user.username,
        hashed_password=auth.hash_password(user.password),
        department=user.department,
        role=user.role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.delete("/users/{username}")
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account while logged in as it")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"deleted": username}

@router.get("/organizations")
def list_organizations(current_user: models.User = Depends(auth.require_admin)):
    return schemas.VALID_ORGANIZATIONS