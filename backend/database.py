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
engine_kwargs = {"poolclass": StaticPool} if DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True}

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PatientRecord(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, unique=True, index=True)
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


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
