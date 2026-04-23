"""
Clinical Journeys™ — post-discharge follow-up engine.
Sends automated SMS check-ins at 24h / 72h / 7d post-discharge.
If symptoms worsen, escalates via WebSocket alert to staff.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import Callable
from sqlalchemy.orm import Session
from database import ClinicalJourney, SessionLocal
from symptom_check import run_assessment

_JOURNEY_SCHEDULE_HOURS = {
    1: [24, 48],         # ESI 1 — critical, 2 follow-ups
    2: [24, 72],         # ESI 2 — high acuity
    3: [72, 168],        # ESI 3 — urgent, 72h + 7d
    4: [168],            # ESI 4 — less urgent, 7d
    5: [168],            # ESI 5 — non-urgent, 7d
}

MONITOR_INTERVAL = int(os.getenv("JOURNEY_INTERVAL", "300"))  # 5 min default

_SMS_QUESTIONS = {
    1: "Hi {name}, MediScan follow-up: How are you feeling? Reply 1=Much better, 2=Same, 3=Worse, or describe symptoms.",
    2: "Hi {name}, MediScan 72hr check: Any changes since discharge? Reply 1=Improved, 2=Same, 3=Worsening, or describe.",
}


def trigger_journey(db: Session, patient_id: str, name: str, phone: str, esi_level: int) -> dict:
    """Create a new Clinical Journey record after discharge."""
    schedule = _JOURNEY_SCHEDULE_HOURS.get(esi_level, [168])
    now = datetime.utcnow()
    next_checkin = now + timedelta(hours=schedule[0])

    existing = db.query(ClinicalJourney).filter_by(patient_id=patient_id).first()
    if existing:
        return {"journey_id": existing.id, "already_active": True}

    portal_token = str(uuid.uuid4())
    journey = ClinicalJourney(
        patient_id=patient_id,
        name=name,
        phone=phone or "",
        esi_level=esi_level,
        discharge_at=now,
        journey_status="active",
        checkins_total=len(schedule),
        next_checkin_at=next_checkin,
        checkin_log=[],
        portal_token=portal_token,
    )
    db.add(journey)
    db.commit()
    base_url = os.getenv("FRONTEND_URL", "https://mediscan-gateway.vercel.app")
    return {
        "journey_id": journey.id,
        "next_checkin_at": next_checkin.isoformat(),
        "checkins_planned": len(schedule),
        "portal_url": f"{base_url}/patient?token={portal_token}",
    }


def get_journeys(db: Session, status: str = None) -> list:
    q = db.query(ClinicalJourney)
    if status:
        q = q.filter_by(journey_status=status)
    rows = q.order_by(ClinicalJourney.discharge_at.desc()).limit(200).all()
    return [_journey_to_dict(r) for r in rows]


def get_journey(db: Session, patient_id: str) -> dict | None:
    row = db.query(ClinicalJourney).filter_by(patient_id=patient_id).first()
    return _journey_to_dict(row) if row else None


def send_checkin_sms(journey: ClinicalJourney, checkin_num: int) -> bool:
    """Send an SMS check-in message. Returns True if sent."""
    from notifications import _sms
    if not journey.phone:
        return False
    template = _SMS_QUESTIONS.get(checkin_num, _SMS_QUESTIONS[1])
    msg = template.format(name=journey.name.split()[0])
    return _sms(journey.phone, msg)


def process_sms_response(db: Session, from_phone: str, message: str) -> dict | None:
    """
    Called by Twilio webhook. Returns escalation dict if this phone belongs to
    an active journey AND response suggests worsening, else None.
    """
    journey = db.query(ClinicalJourney).filter_by(phone=from_phone, journey_status="active").first()
    if not journey:
        return None

    msg_lower = message.strip().lower()
    worsening = (
        msg_lower in ("3", "worse", "worsening", "bad", "worse than before") or
        any(w in msg_lower for w in ["chest pain", "can't breathe", "worse", "emergency", "help", "911", "severe"])
    )

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "message": message,
        "worsening": worsening,
        "checkin_num": journey.checkins_completed + 1,
    }

    existing_log = journey.checkin_log or []
    journey.checkin_log = existing_log + [log_entry]
    journey.last_response = message
    journey.last_checkin_at = datetime.utcnow()
    journey.checkins_completed = (journey.checkins_completed or 0) + 1

    schedule = _JOURNEY_SCHEDULE_HOURS.get(journey.esi_level, [168])
    next_idx = journey.checkins_completed
    if next_idx < len(schedule):
        journey.next_checkin_at = journey.discharge_at + timedelta(hours=schedule[next_idx])
    else:
        journey.journey_status = "completed"
        journey.completed_at = datetime.utcnow()

    if worsening:
        journey.journey_status = "escalated"
        journey.escalated_reason = f"Patient reported worsening symptoms: '{message[:200]}'"

    db.commit()

    if worsening:
        try:
            from email_service import notify_journey_escalation
            notify_journey_escalation(
                patient_name=journey.name,
                esi_level=journey.esi_level,
                phone=journey.phone,
                reason=journey.escalated_reason,
                portal_token=journey.portal_token,
            )
        except Exception as e:
            print(f"[Email] Escalation notification failed: {e}")
        return {
            "journey_id": journey.id,
            "patient_id": journey.patient_id,
            "name": journey.name,
            "phone": journey.phone,
            "esi_level": journey.esi_level,
            "message": message,
            "escalated": True,
        }
    return {"journey_id": journey.id, "escalated": False}


def manual_checkin(db: Session, journey_id: str) -> dict:
    journey = db.query(ClinicalJourney).filter_by(id=journey_id).first()
    if not journey:
        return {"success": False, "error": "Journey not found"}
    checkin_num = (journey.checkins_completed or 0) + 1
    sent = send_checkin_sms(journey, checkin_num)
    return {"success": True, "sms_sent": sent, "journey_id": journey_id}


async def journey_monitor_loop(get_db_fn: Callable, broadcast_fn: Callable):
    """Background task — sends due check-ins and escalates worsening patients."""
    while True:
        await asyncio.sleep(MONITOR_INTERVAL)
        try:
            db: Session = next(get_db_fn())
            now = datetime.utcnow()
            due = (
                db.query(ClinicalJourney)
                .filter(
                    ClinicalJourney.journey_status == "active",
                    ClinicalJourney.next_checkin_at <= now,
                    ClinicalJourney.phone != "",
                )
                .all()
            )
            for journey in due:
                checkin_num = (journey.checkins_completed or 0) + 1
                sent = send_checkin_sms(journey, checkin_num)
                log_entry = {
                    "timestamp": now.isoformat(),
                    "type": "checkin_sent",
                    "sms_sent": sent,
                    "checkin_num": checkin_num,
                }
                journey.checkin_log = (journey.checkin_log or []) + [log_entry]

                schedule = _JOURNEY_SCHEDULE_HOURS.get(journey.esi_level, [168])
                next_idx = checkin_num
                if next_idx < len(schedule):
                    journey.next_checkin_at = journey.discharge_at + timedelta(hours=schedule[next_idx])
                else:
                    journey.next_checkin_at = None

            db.commit()
            db.close()
        except Exception as e:
            print(f"Journey monitor error: {e}")


def _journey_to_dict(j: ClinicalJourney) -> dict:
    return {
        "journey_id": j.id,
        "patient_id": j.patient_id,
        "name": j.name,
        "phone": j.phone,
        "esi_level": j.esi_level,
        "journey_status": j.journey_status,
        "discharge_at": j.discharge_at.isoformat() if j.discharge_at else None,
        "checkins_completed": j.checkins_completed or 0,
        "checkins_total": j.checkins_total or 2,
        "last_response": j.last_response,
        "last_checkin_at": j.last_checkin_at.isoformat() if j.last_checkin_at else None,
        "next_checkin_at": j.next_checkin_at.isoformat() if j.next_checkin_at else None,
        "escalated_reason": j.escalated_reason,
        "checkin_log": j.checkin_log or [],
        "portal_token": j.portal_token,
    }
