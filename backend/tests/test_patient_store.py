"""
Unit tests for patient_store.py CRUD helpers.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, PatientRecord, AuditLog, Bed
from patient_store import (
    upsert_patient,
    load_active_patients,
    discharge_patient_db,
    clear_all_active,
    write_audit,
    get_audit_logs,
    save_shift_report,
    get_shift_reports,
    get_beds,
    update_bed,
    get_bed_summary,
)


@pytest.fixture(scope="module")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_upsert_patient_create(db):
    record = {
        "patient_id": "PT-STORE-001",
        "name": "Alice Smith",
        "age": 35,
        "chief_complaint": "headache",
        "esi_level": 3,
        "priority": "moderate",
        "risk_flags": ["hypertension"],
        "ai_summary": "Moderate headache",
        "routing_destination": "ED Main",
        "room_assignment": "Room 5",
        "wristband_code": "WB-001",
        "wait_time_estimate": 20,
        "care_pre_staged": [],
        "insurance": {"provider": "BlueCross"},
        "sensor_data": {},
        "ehr_summary": {},
        "triage_detail": {"sepsis_probability": "low"},
    }
    row = upsert_patient(db, record)
    assert row.patient_id == "PT-STORE-001"
    assert row.name == "Alice Smith"


def test_upsert_patient_update(db):
    # Update the same patient
    record = {
        "patient_id": "PT-STORE-001",
        "name": "Alice Smith Updated",
        "age": 35,
        "chief_complaint": "headache",
        "esi_level": 2,
        "priority": "urgent",
        "risk_flags": [],
        "ai_summary": "Updated summary",
        "routing_destination": "ED Main",
        "room_assignment": "Room 5",
        "wristband_code": "WB-001",
        "wait_time_estimate": 10,
        "care_pre_staged": [],
        "insurance": {},
        "sensor_data": {},
        "ehr_summary": {},
        "triage_detail": {},
    }
    row = upsert_patient(db, record)
    assert row.name == "Alice Smith Updated"
    assert row.esi_level == 2


def test_load_active_patients(db):
    # Insert a fresh active patient
    db.add(PatientRecord(
        patient_id="PT-ACTIVE-001",
        name="Bob Jones",
        age=50,
        chief_complaint="chest pain",
        esi_level=2,
        status="active",
        hospital_id="default",
    ))
    db.commit()

    patients = load_active_patients(db, hospital_id="default")
    ids = [p["patient_id"] for p in patients]
    assert "PT-ACTIVE-001" in ids


def test_load_active_patients_excludes_discharged(db):
    db.add(PatientRecord(
        patient_id="PT-DISCH-001",
        name="Charlie Brown",
        age=60,
        chief_complaint="cough",
        esi_level=4,
        status="discharged",
        hospital_id="default",
    ))
    db.commit()

    patients = load_active_patients(db, hospital_id="default")
    ids = [p["patient_id"] for p in patients]
    assert "PT-DISCH-001" not in ids


def test_discharge_patient_db(db):
    db.add(PatientRecord(
        patient_id="PT-DISC-002",
        name="Diana Prince",
        age=30,
        chief_complaint="fever",
        esi_level=3,
        status="active",
        hospital_id="default",
    ))
    db.commit()

    result = discharge_patient_db(db, "PT-DISC-002")
    assert result is True

    row = db.query(PatientRecord).filter_by(patient_id="PT-DISC-002").first()
    assert row.status == "discharged"
    assert row.discharged_at is not None


def test_discharge_patient_not_found(db):
    result = discharge_patient_db(db, "NO-SUCH-PATIENT")
    assert result is False


def test_clear_all_active(db):
    # Add two active patients
    for i in range(3, 5):
        db.add(PatientRecord(
            patient_id=f"PT-CLEAR-{i:03d}",
            name=f"Patient {i}",
            age=40,
            chief_complaint="back pain",
            esi_level=4,
            status="active",
            hospital_id="default",
        ))
    db.commit()

    count = clear_all_active(db)
    assert count >= 2

    active_remaining = db.query(PatientRecord).filter_by(status="active").count()
    assert active_remaining == 0


def test_write_audit(db):
    write_audit(db, "admin", "admin", "test_action",
                patient_id="PT-001", ip_address="10.0.0.1",
                details={"info": "test"}, hospital_id="default")
    logs = db.query(AuditLog).filter_by(action="test_action").all()
    assert len(logs) >= 1
    assert logs[-1].username == "admin"


def test_get_audit_logs(db):
    write_audit(db, "nurse", "nurse", "view_queue", hospital_id="default")
    logs = get_audit_logs(db, limit=50, hospital_id="default")
    assert isinstance(logs, list)
    actions = [log["action"] for log in logs]
    assert "view_queue" in actions


def test_save_and_get_shift_reports(db):
    report = {
        "shift_start": datetime(2026, 5, 1, 7, 0),
        "shift_end": datetime(2026, 5, 1, 19, 0),
        "generated_by": "admin",
        "total_patients": 42,
        "esi_breakdown": {"1": 2, "2": 8, "3": 20, "4": 10, "5": 2},
        "avg_wait_minutes": 18.5,
        "sepsis_count": 3,
        "bh_count": 1,
        "lwbs_high_risk_count": 2,
        "admissions_predicted": 10,
        "report_data": {"active_patients": []},
    }
    row = save_shift_report(db, report)
    assert row.id is not None
    assert row.total_patients == 42

    reports = get_shift_reports(db)
    assert len(reports) >= 1
    assert reports[0]["generated_by"] == "admin"


def test_get_beds_empty(db):
    beds = get_beds(db)
    assert isinstance(beds, list)


def test_get_beds_with_data(db):
    db.add(Bed(unit="ED Main", room="PSTEST-1"))
    db.commit()
    beds = get_beds(db)
    rooms = [b["room"] for b in beds]
    assert "PSTEST-1" in rooms


def test_update_bed(db):
    db.add(Bed(unit="Fast Track", room="FT-TEST-1"))
    db.commit()

    result = update_bed(db, "FT-TEST-1", "occupied", patient_id="PT-001", updated_by="nurse")
    assert result is not None
    assert result["status"] == "occupied"
    assert result["patient_id"] == "PT-001"


def test_update_bed_not_found(db):
    result = update_bed(db, "ROOM-NOPE", "available")
    assert result is None


def test_get_bed_summary(db):
    # Ensure at least one bed exists
    db.add(Bed(unit="ED Main", room="SUMMARY-TEST-1", status="available"))
    db.add(Bed(unit="ED Main", room="SUMMARY-TEST-2", status="occupied"))
    db.commit()

    summary = get_bed_summary(db)
    assert "total_beds" in summary
    assert "occupied_beds" in summary
    assert "available_beds" in summary
    assert "occupancy_percent" in summary
    assert summary["total_beds"] > 0
