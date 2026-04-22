"""
CRUD layer — replaces in-memory er_queue with PostgreSQL-backed storage.
In-memory list is kept as a fast cache; DB is source of truth on restart.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from database import PatientRecord, AuditLog, ShiftReport, SessionLocal


# ── Patient helpers ────────────────────────────────────────────────────────────

def upsert_patient(db: Session, record: dict) -> PatientRecord:
    existing = db.query(PatientRecord).filter_by(patient_id=record["patient_id"]).first()
    if existing:
        for k, v in record.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
    else:
        existing = PatientRecord(
            patient_id=record["patient_id"],
            name=record.get("name"),
            age=record.get("age"),
            phone=record.get("phone"),
            chief_complaint=record.get("chief_complaint"),
            esi_level=record.get("esi_level", 5),
            priority=record.get("priority"),
            risk_flags=record.get("risk_flags", []),
            ai_summary=record.get("ai_summary"),
            routing_destination=record.get("routing_destination"),
            room_assignment=record.get("room_assignment"),
            wristband_code=record.get("wristband_code"),
            wait_time_estimate=record.get("wait_time_estimate"),
            care_pre_staged=record.get("care_pre_staged", []),
            insurance=record.get("insurance", {}),
            sensor_data=record.get("sensor_data", {}),
            ehr_summary=record.get("ehr_summary", {}),
            triage_detail=record.get("triage_detail", {}),
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def load_active_patients(db: Session) -> List[dict]:
    rows = db.query(PatientRecord).filter_by(status="active").order_by(PatientRecord.esi_level).all()
    return [_row_to_dict(r) for r in rows]


def discharge_patient_db(db: Session, patient_id: str) -> bool:
    row = db.query(PatientRecord).filter_by(patient_id=patient_id, status="active").first()
    if not row:
        return False
    row.status = "discharged"
    row.discharged_at = datetime.utcnow()
    db.commit()
    return True


def clear_all_active(db: Session) -> int:
    rows = db.query(PatientRecord).filter_by(status="active").all()
    count = len(rows)
    for r in rows:
        r.status = "discharged"
        r.discharged_at = datetime.utcnow()
    db.commit()
    return count


def _row_to_dict(r: PatientRecord) -> dict:
    return {
        "patient_id": r.patient_id,
        "name": r.name,
        "age": r.age,
        "phone": r.phone,
        "chief_complaint": r.chief_complaint,
        "esi_level": r.esi_level,
        "priority": r.priority,
        "risk_flags": r.risk_flags or [],
        "ai_summary": r.ai_summary,
        "routing_destination": r.routing_destination,
        "room_assignment": r.room_assignment,
        "wristband_code": r.wristband_code,
        "wait_time_estimate": r.wait_time_estimate,
        "care_pre_staged": r.care_pre_staged or [],
        "insurance": r.insurance or {},
        "sensor_data": r.sensor_data or {},
        "ehr_summary": r.ehr_summary or {},
        "triage_detail": r.triage_detail or {},
        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        "status": r.status,
    }


# ── Audit helpers ──────────────────────────────────────────────────────────────

def write_audit(
    db: Session,
    username: str,
    role: str,
    action: str,
    patient_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict] = None,
    success: bool = True,
):
    entry = AuditLog(
        username=username,
        role=role,
        action=action,
        patient_id=patient_id,
        ip_address=ip_address,
        details=details or {},
        success=success,
    )
    db.add(entry)
    db.commit()


def get_audit_logs(db: Session, limit: int = 500) -> List[dict]:
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "username": r.username,
            "role": r.role,
            "action": r.action,
            "patient_id": r.patient_id,
            "ip_address": r.ip_address,
            "details": r.details,
            "success": r.success,
        }
        for r in rows
    ]


# ── Shift report helpers ───────────────────────────────────────────────────────

def save_shift_report(db: Session, report: dict) -> ShiftReport:
    row = ShiftReport(
        shift_start=report["shift_start"],
        shift_end=report.get("shift_end", datetime.utcnow()),
        generated_by=report["generated_by"],
        total_patients=report.get("total_patients", 0),
        esi_breakdown=report.get("esi_breakdown", {}),
        avg_wait_minutes=report.get("avg_wait_minutes", 0),
        sepsis_count=report.get("sepsis_count", 0),
        bh_count=report.get("bh_count", 0),
        lwbs_high_risk_count=report.get("lwbs_high_risk_count", 0),
        admissions_predicted=report.get("admissions_predicted", 0),
        report_data=report.get("report_data", {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_beds(db: Session) -> List[dict]:
    from database import Bed
    rows = db.query(Bed).order_by(Bed.unit, Bed.room).all()
    return [_bed_to_dict(r) for r in rows]


def update_bed(db: Session, room: str, status: str, patient_id: str = None, updated_by: str = None) -> dict | None:
    from database import Bed
    from datetime import datetime
    row = db.query(Bed).filter_by(room=room).first()
    if not row:
        return None
    row.status = status
    row.patient_id = patient_id
    row.updated_at = datetime.utcnow()
    row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    return _bed_to_dict(row)


def _bed_to_dict(r) -> dict:
    return {
        "id": r.id,
        "unit": r.unit,
        "room": r.room,
        "status": r.status,
        "patient_id": r.patient_id,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "updated_by": r.updated_by,
    }


def get_bed_summary(db: Session) -> dict:
    from database import Bed
    beds = db.query(Bed).all()
    total = len(beds)
    occupied = sum(1 for b in beds if b.status == "occupied")
    boarding = sum(1 for b in beds if b.status == "boarding")
    available = sum(1 for b in beds if b.status == "available")
    cleaning = sum(1 for b in beds if b.status == "cleaning")
    return {
        "total_beds": total,
        "occupied_beds": occupied + boarding,
        "available_beds": available,
        "boarding_patients": boarding,
        "cleaning_beds": cleaning,
        "occupancy_percent": round((occupied + boarding) / total * 100, 1) if total else 0,
    }


def get_shift_reports(db: Session, limit: int = 20) -> List[dict]:
    rows = (
        db.query(ShiftReport)
        .order_by(ShiftReport.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "shift_start": r.shift_start.isoformat() if r.shift_start else None,
            "shift_end": r.shift_end.isoformat() if r.shift_end else None,
            "generated_by": r.generated_by,
            "total_patients": r.total_patients,
            "esi_breakdown": r.esi_breakdown,
            "avg_wait_minutes": r.avg_wait_minutes,
            "sepsis_count": r.sepsis_count,
            "bh_count": r.bh_count,
            "lwbs_high_risk_count": r.lwbs_high_risk_count,
            "admissions_predicted": r.admissions_predicted,
            "report_data": r.report_data,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
