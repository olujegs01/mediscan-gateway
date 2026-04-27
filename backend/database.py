"""
PostgreSQL via SQLAlchemy — persists queue, audit logs, shift reports.
Falls back to SQLite for local dev when DATABASE_URL is not set.
"""
import os
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mediscan.db")

# Render gives postgres:// — SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs = {"poolclass": StaticPool}
else:
    # Production PostgreSQL: connection pool tuned for FastAPI concurrency
    engine_kwargs = {
        "pool_pre_ping": True,      # detects stale connections before use
        "pool_size": 10,            # keep 10 connections warm
        "max_overflow": 20,         # up to 30 total under load
        "pool_timeout": 30,         # wait up to 30s for a connection
        "pool_recycle": 1800,       # recycle connections every 30 min
    }

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Hospital(Base):
    __tablename__ = "hospitals"

    id     = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug   = Column(String, unique=True, index=True)   # e.g. "general-hospital"
    name   = Column(String)
    city   = Column(String, nullable=True)
    state  = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    bed_count     = Column(Integer, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def _default_hospital():
    return "default"


class PatientRecord(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, unique=True, index=True)
    hospital_id = Column(String, index=True, default=_default_hospital)
    name = Column(String)
    age = Column(Integer)
    phone = Column(String, nullable=True)
    chief_complaint = Column(Text)
    esi_level = Column(Integer)
    priority = Column(String)
    risk_flags = Column(JSON, default=list)
    ai_summary = Column(Text)
    routing_destination = Column(String)
    room_assignment = Column(String)
    wristband_code = Column(String)
    wait_time_estimate = Column(Integer)
    care_pre_staged = Column(JSON, default=list)
    insurance = Column(JSON, default=dict)
    sensor_data = Column(JSON, default=dict)
    ehr_summary = Column(JSON, default=dict)
    triage_detail = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")   # active | discharged
    discharged_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    timestamp = Column(DateTime, default=datetime.utcnow)
    username = Column(String)
    role = Column(String)
    action = Column(String)       # login | scan | view_queue | discharge | view_analytics | view_patient
    patient_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    success = Column(Boolean, default=True)


class ShiftReport(Base):
    __tablename__ = "shift_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    shift_start = Column(DateTime)
    shift_end = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String)
    total_patients = Column(Integer, default=0)
    esi_breakdown = Column(JSON, default=dict)
    avg_wait_minutes = Column(Float, default=0)
    sepsis_count = Column(Integer, default=0)
    bh_count = Column(Integer, default=0)
    lwbs_high_risk_count = Column(Integer, default=0)
    admissions_predicted = Column(Integer, default=0)
    report_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Bed(Base):
    __tablename__ = "beds"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    unit = Column(String)           # Trauma Bay | Resuscitation | ED Main | Fast Track
    room = Column(String, unique=True)
    status = Column(String, default="available")  # available | occupied | boarding | cleaning
    patient_id = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, nullable=True)


# Seed 42 beds on first run
_BED_LAYOUT = [
    # unit,             room,        count, prefix
    ("Trauma Bay",      "Trauma",    4,     "T"),
    ("Resuscitation",   "Resus",     4,     "R"),
    ("ED Main",         "Room",      24,    ""),
    ("Fast Track",      "FT",        6,     "FT-"),
    ("Behavioral Health","BH-Suite", 4,     "BH-"),
]


class ClinicalJourney(Base):
    __tablename__ = "clinical_journeys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    patient_id = Column(String, index=True)
    name = Column(String)
    phone = Column(String, nullable=True)
    esi_level = Column(Integer)
    discharge_at = Column(DateTime, default=datetime.utcnow)
    journey_status = Column(String, default="active")   # active | escalated | completed
    checkins_completed = Column(Integer, default=0)
    checkins_total = Column(Integer, default=2)
    last_response = Column(Text, nullable=True)
    last_checkin_at = Column(DateTime, nullable=True)
    next_checkin_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    escalated_reason = Column(Text, nullable=True)
    checkin_log = Column(JSON, default=list)
    portal_token = Column(String, unique=True, nullable=True, index=True)


class AppointmentSlot(Base):
    __tablename__ = "appointment_slots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slot_id = Column(String, unique=True, index=True)
    provider_name = Column(String)
    provider_type = Column(String)   # primary_care | urgent_care | telehealth
    specialty = Column(String, nullable=True)
    location = Column(String)
    address = Column(String, nullable=True)
    slot_date = Column(String)       # ISO date string
    slot_time = Column(String)       # HH:MM
    duration_min = Column(Integer, default=20)
    available = Column(Boolean, default=True)
    booked_by = Column(String, nullable=True)
    booked_at = Column(DateTime, nullable=True)


class SOAPNote(Base):
    __tablename__ = "soap_notes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    patient_id = Column(String, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String, default="AI")
    subjective = Column(Text)
    objective = Column(Text)
    assessment = Column(Text)
    plan = Column(Text)
    full_text = Column(Text)
    finalized = Column(Boolean, default=False)
    finalized_by = Column(String, nullable=True)
    finalized_at = Column(DateTime, nullable=True)


class EscalationRule(Base):
    __tablename__ = "escalation_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_name = Column(String, unique=True)
    condition_field = Column(String)   # esi_level | sepsis_probability | wait_time_minutes
    condition_op = Column(String)      # eq | lte | gte | in
    condition_value = Column(String)
    action = Column(String)            # notify_attending | page_charge_nurse | activate_rapid_response
    response_time_minutes = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    tier = Column(String)              # starter | growth | enterprise
    stripe_session_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    hospital_name = Column(String, nullable=True)
    status = Column(String, default="active")   # active | cancelled | past_due | trialing
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DemoRequest(Base):
    __tablename__ = "demo_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    hospital = Column(String)
    role = Column(String)
    email = Column(String)
    bed_count = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PatientNote(Base):
    __tablename__ = "patient_notes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, index=True)
    hospital_id = Column(String, index=True, default=_default_hospital)
    note_text = Column(Text)
    note_type = Column(String, default="general")  # general | allergy | alert | lab | interpreter
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class PatientFeedback(Base):
    __tablename__ = "patient_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    journey_id = Column(String, index=True, nullable=True)
    patient_id = Column(String, index=True, nullable=True)
    rating = Column(Integer)           # 1–5
    comment = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # wait_time | staff | communication | overall
    submitted_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="portal")   # portal | sms | kiosk


class StaffUser(Base):
    __tablename__ = "staff_users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String, index=True, default=_default_hospital)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)           # admin | nurse | physician
    name = Column(String)
    email = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    mfa_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)


def seed_beds(db):
    from sqlalchemy import func
    count = db.query(func.count(Bed.id)).scalar()
    if count > 0:
        return
    beds = []
    for unit, room_base, total, prefix in _BED_LAYOUT:
        for i in range(1, total + 1):
            room_name = f"{room_base} {i}" if not prefix else f"{prefix}{i}"
            beds.append(Bed(id=str(uuid.uuid4()), unit=unit, room=room_name))
    db.add_all(beds)
    db.commit()


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
