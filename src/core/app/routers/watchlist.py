from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
import app.auth as auth
from app.database import get_db

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


# ---------------- Wanted vehicles ----------------

@router.post("/wanted", response_model=schemas.WantedVehicleResponse)
def add_wanted_vehicle(
    entry: schemas.WantedVehicleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    existing = db.query(models.WantedVehicle).filter(
        models.WantedVehicle.plate_number == entry.plate_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plate already on the wanted list")
    db_entry = models.WantedVehicle(**entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.get("/wanted", response_model=List[schemas.WantedVehicleResponse])
def list_wanted_vehicles(db: Session = Depends(get_db)):
    return db.query(models.WantedVehicle).order_by(models.WantedVehicle.registered_at.desc()).all()


@router.delete("/wanted/{plate_number}")
def remove_wanted_vehicle(
    plate_number: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    entry = db.query(models.WantedVehicle).filter(models.WantedVehicle.plate_number == plate_number).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
    return {"deleted": plate_number}


# ---------------- Missing vehicles ----------------

@router.post("/missing", response_model=schemas.MissingVehicleResponse)
def add_missing_vehicle(
    entry: schemas.MissingVehicleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    existing = db.query(models.MissingVehicle).filter(
        models.MissingVehicle.plate_number == entry.plate_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plate already reported missing")
    db_entry = models.MissingVehicle(**entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.get("/missing", response_model=List[schemas.MissingVehicleResponse])
def list_missing_vehicles(db: Session = Depends(get_db)):
    return db.query(models.MissingVehicle).order_by(models.MissingVehicle.reported_at.desc()).all()


@router.delete("/missing/{plate_number}")
def remove_missing_vehicle(
    plate_number: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    entry = db.query(models.MissingVehicle).filter(models.MissingVehicle.plate_number == plate_number).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
    return {"deleted": plate_number}