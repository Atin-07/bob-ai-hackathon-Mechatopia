import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Numeric,
    DateTime, Text, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .database import Base

# ============================================================
# CAMERA REGISTRY
# ============================================================
class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(50), unique=True, index=True, nullable=False)
    organization_id = Column(String(50), index=True)
    organization_name = Column(String, nullable=True)
    name = Column(String(100))
    status = Column(String, default="online")  # online/offline/maintenance

    # location
        # location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(255), nullable=True)
    location_name = Column(String(255), nullable=True)

    camera_type = Column(String, default="IP")  # IP/PTZ/analog

    # properties
    codec = Column(String(20), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # stream URLs
    rtsp_url = Column(Text, nullable=True)
    webrtc_url = Column(Text, nullable=True)
    hls_url = Column(Text, nullable=True)

    # extra fields
    department = Column(String, index=True, nullable=True)
    district = Column(String, index=True, nullable=True)
    vms_vendor = Column(String, nullable=True)
    storage_type = Column(String, default="cloud")
    retention_days = Column(Integer, default=7)

    created_at = Column(DateTime, default=datetime.utcnow)
    install_date = Column(DateTime, default=datetime.utcnow)
    last_health_check = Column(DateTime, default=datetime.utcnow)

    vehicle_events = relationship("VehicleEvent", back_populates="camera", cascade="all, delete-orphan")
    person_events = relationship("PersonEvent", back_populates="camera", cascade="all, delete-orphan")


# ============================================================
# USER + WATCHLIST
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    department = Column(String, nullable=True)
    role = Column(String, default="viewer")   # admin/operator/viewer
    created_at = Column(DateTime, default=datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    entry_type = Column(String, index=True)   # "vehicle" or "person"
    value = Column(String, index=True)        # plate number or person label
    reason = Column(String)
    added_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# VEHICLE SUBSYSTEM
# ============================================================
class VehicleEvent(Base):
    __tablename__ = "vehicle_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    camera_id = Column(String(50), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(50), nullable=False)
    event_type = Column(String(20), nullable=False, default="anpr")
    plate_number = Column(String(20), index=True, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=False)
    pts_ms = Column(Float, nullable=True)
    speed_kmph = Column(Numeric(5, 2), nullable=True)
    speed_limit_kmph = Column(Numeric(5, 2), nullable=True)
    helmet_status = Column(String, nullable=True)   # worn/not_worn/None
    snapshot_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    camera = relationship("Camera", back_populates="vehicle_events")
    alerts = relationship("Alert", back_populates="event", cascade="all, delete-orphan")


class WantedVehicle(Base):
    __tablename__ = "wanted_vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(20), unique=True, nullable=False, index=True)
    fir_number = Column(String(100), nullable=True)
    crime_description = Column(Text, nullable=False)
    severity = Column(String(20), default="HIGH")
    issuing_authority = Column(String(100), default="Gujarat Police")
    registered_at = Column(DateTime, default=datetime.utcnow)


class MissingVehicle(Base):
    __tablename__ = "missing_vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(20), unique=True, nullable=False, index=True)
    owner_name = Column(String(100))
    vehicle_model = Column(String(100))
    report_number = Column(String(100))
    contact_number = Column(String(20))
    reported_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# ALERTS (VEHICLE)
# ============================================================
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(BigInteger, ForeignKey("vehicle_events.id", ondelete="CASCADE"), nullable=False)
    plate_number = Column(String(20), nullable=True, index=True)
    camera_id = Column(String(50), nullable=False)
    alert_type = Column(String(20), nullable=False)
    severity = Column(String(20), nullable=False)
    details = Column(Text, nullable=True)
    status = Column(String(20), default="ACTIVE", index=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("VehicleEvent", back_populates="alerts")


# ============================================================
# PERSON SUBSYSTEM
# ============================================================
class PersonMissing(Base):
    __tablename__ = "person_missing"

    person_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    age = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    reference_embedding = Column(Vector(512), nullable=False)
    reference_image_path = Column(Text, nullable=True)
    reported_by = Column(Text, nullable=True)
    status = Column(Text, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    matched_events = relationship(
        "PersonEvent", 
        back_populates="missing_person", 
        foreign_keys="PersonEvent.matched_missing_id"
    )
    alerts = relationship("PersonAlert", back_populates="missing_person")


class PersonWanted(Base):
    __tablename__ = "person_wanted"

    person_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    age = Column(Integer, nullable=True)
    crime_description = Column(Text, nullable=True)
    reference_embedding = Column(Vector(512), nullable=False)
    reference_image_path = Column(Text, nullable=True)
    reported_by = Column(Text, nullable=True)
    status = Column(Text, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    matched_events = relationship(
        "PersonEvent", 
        back_populates="wanted_person", 
        foreign_keys="PersonEvent.matched_wanted_id"
    )
    alerts = relationship("PersonAlert", back_populates="wanted_person")


class PersonEvent(Base):
    __tablename__ = "person_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(String(50), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Text, nullable=False)
    pts_ms = Column(Float, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    bbox = Column(JSONB, nullable=False)
    embedding = Column(Vector(512), nullable=False)
    crop_image_path = Column(Text, nullable=True)

    matched_missing_id = Column(UUID(as_uuid=True), ForeignKey("person_missing.person_id"), nullable=True)
    matched_wanted_id = Column(UUID(as_uuid=True), ForeignKey("person_wanted.person_id"), nullable=True)

    camera = relationship("Camera", back_populates="person_events")
    missing_person = relationship("PersonMissing", back_populates="matched_events", foreign_keys=[matched_missing_id])
    wanted_person = relationship("PersonWanted", back_populates="matched_events", foreign_keys=[matched_wanted_id])
    alerts = relationship("PersonAlert", back_populates="event", cascade="all, delete-orphan")


class PersonAlert(Base):
    __tablename__ = "person_alerts"
    __table_args__ = (
        CheckConstraint("category IN ('missing', 'wanted')", name="check_person_alert_category"),
    )

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("person_events.event_id", ondelete="CASCADE"), nullable=True)
    missing_id = Column(UUID(as_uuid=True), ForeignKey("person_missing.person_id", ondelete="SET NULL"), nullable=True)
    wanted_id = Column(UUID(as_uuid=True), ForeignKey("person_wanted.person_id", ondelete="SET NULL"), nullable=True)
    category = Column(Text, nullable=False)
    camera_id = Column(String(50), nullable=False)
    similarity_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    status = Column(Text, default="pending", index=True)

    # Relationships mapped to back_populates
    event = relationship("PersonEvent", back_populates="alerts")
    missing_person = relationship("PersonMissing", back_populates="alerts")
    wanted_person = relationship("PersonWanted", back_populates="alerts")