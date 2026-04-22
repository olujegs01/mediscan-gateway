"""
Appointment scheduling engine.
Uses mock slot inventory for demo; swap NEXHEALTH_API_KEY or EPIC_SCHEDULING_URL
env vars to go live against a real scheduling system.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database import AppointmentSlot

_NEXHEALTH_KEY = os.getenv("NEXHEALTH_API_KEY")

MOCK_PROVIDERS = [
    {
        "provider_name": "Dr. Sarah Chen, MD",
        "provider_type": "primary_care",
        "specialty": "Internal Medicine",
        "location": "MediScan Primary Care Clinic",
        "address": "1200 Health Blvd, Suite 300",
    },
    {
        "provider_name": "Dr. James Okafor, DO",
        "provider_type": "primary_care",
        "specialty": "Family Medicine",
        "location": "Riverside Medical Group",
        "address": "455 Riverside Drive",
    },
    {
        "provider_name": "CityUrgent Care — Main St",
        "provider_type": "urgent_care",
        "specialty": "Urgent Care",
        "location": "CityUrgent Main Street",
        "address": "800 Main Street",
    },
    {
        "provider_name": "QuickCare Express",
        "provider_type": "urgent_care",
        "specialty": "Urgent Care",
        "location": "QuickCare Express — West End",
        "address": "2050 West End Ave",
    },
    {
        "provider_name": "MediScan Telehealth — Dr. Patel",
        "provider_type": "telehealth",
        "specialty": "Telehealth / General Medicine",
        "location": "Virtual Visit",
        "address": "Video call link sent on booking",
    },
    {
        "provider_name": "MediScan Telehealth — Dr. Torres",
        "provider_type": "telehealth",
        "specialty": "Telehealth / Urgent",
        "location": "Virtual Visit",
        "address": "Video call link sent on booking",
    },
]

_TIME_SLOTS = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
               "11:00", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
               "16:00", "16:30"]


def seed_slots(db: Session) -> None:
    """Populate ~30 appointment slots for the next 2 days if the table is empty."""
    from sqlalchemy import func
    if db.query(func.count(AppointmentSlot.id)).scalar() > 0:
        return

    today = datetime.utcnow().date()
    slots = []
    for day_offset in range(2):
        d = today + timedelta(days=day_offset)
        date_str = d.isoformat()
        for provider in MOCK_PROVIDERS:
            # Assign 3–4 time slots per provider per day
            import random
            chosen_times = random.sample(_TIME_SLOTS, k=4)
            for t in chosen_times:
                slots.append(AppointmentSlot(
                    slot_id=f"SLOT-{uuid.uuid4().hex[:8].upper()}",
                    slot_date=date_str,
                    slot_time=t,
                    duration_min=20 if "telehealth" in provider["provider_type"] else 30,
                    **provider,
                ))
    db.add_all(slots)
    db.commit()


def get_available_slots(db: Session, care_type: str, limit: int = 8) -> list:
    """Return next available slots for a given care type."""
    today = datetime.utcnow().date().isoformat()

    # If live NexHealth key, call their API instead (stub)
    if _NEXHEALTH_KEY:
        return _nexhealth_slots(care_type, limit)

    rows = (
        db.query(AppointmentSlot)
        .filter(
            AppointmentSlot.provider_type == care_type,
            AppointmentSlot.available == True,
            AppointmentSlot.slot_date >= today,
        )
        .order_by(AppointmentSlot.slot_date, AppointmentSlot.slot_time)
        .limit(limit)
        .all()
    )
    return [_slot_to_dict(r) for r in rows]


def book_slot(
    db: Session,
    slot_id: str,
    patient_name: str,
    patient_age: int,
    phone: str,
    symptoms: str,
) -> dict:
    slot = db.query(AppointmentSlot).filter_by(slot_id=slot_id, available=True).first()
    if not slot:
        return {"success": False, "error": "Slot no longer available"}

    slot.available = False
    slot.booked_by = patient_name
    slot.booked_at = datetime.utcnow()
    db.commit()

    confirmation_id = f"APT-{uuid.uuid4().hex[:6].upper()}"
    return {
        "success": True,
        "confirmation_id": confirmation_id,
        "provider_name": slot.provider_name,
        "provider_type": slot.provider_type,
        "location": slot.location,
        "address": slot.address,
        "slot_date": slot.slot_date,
        "slot_time": slot.slot_time,
        "duration_min": slot.duration_min,
        "patient_name": patient_name,
        "instructions": _booking_instructions(slot.provider_type),
        "calendar_event": _ical_event(slot, patient_name, confirmation_id),
    }


def _slot_to_dict(slot: AppointmentSlot) -> dict:
    return {
        "slot_id": slot.slot_id,
        "provider_name": slot.provider_name,
        "provider_type": slot.provider_type,
        "specialty": slot.specialty,
        "location": slot.location,
        "address": slot.address,
        "slot_date": slot.slot_date,
        "slot_time": slot.slot_time,
        "duration_min": slot.duration_min,
    }


def _booking_instructions(care_type: str) -> str:
    if care_type == "telehealth":
        return "A video call link will be texted/emailed to you 15 minutes before your appointment. Have your insurance card ready."
    if care_type == "urgent_care":
        return "Walk in at your scheduled time. Bring a photo ID and insurance card. No additional check-in required."
    return "Arrive 10 minutes early for paperwork. Bring photo ID, insurance card, and a list of current medications."


def _ical_event(slot: AppointmentSlot, patient_name: str, confirmation_id: str) -> str:
    """Returns minimal iCal event string for calendar download."""
    dt_str = f"{slot.slot_date}T{slot.slot_time}:00"
    start = datetime.fromisoformat(dt_str)
    end = start + timedelta(minutes=slot.duration_min)
    fmt = "%Y%m%dT%H%M%S"
    return (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        f"SUMMARY:Appointment with {slot.provider_name}\n"
        f"DTSTART:{start.strftime(fmt)}\nDTEND:{end.strftime(fmt)}\n"
        f"LOCATION:{slot.location} — {slot.address}\n"
        f"DESCRIPTION:Confirmation {confirmation_id} for {patient_name}\n"
        "END:VEVENT\nEND:VCALENDAR"
    )


def _nexhealth_slots(care_type: str, limit: int) -> list:
    """Stub for NexHealth API integration."""
    import httpx
    try:
        r = httpx.get(
            "https://nexhealth.info/slots",
            params={"care_type": care_type, "limit": limit},
            headers={"Authorization": f"Bearer {_NEXHEALTH_KEY}"},
            timeout=5,
        )
        r.raise_for_status()
        return r.json().get("slots", [])
    except Exception as e:
        print(f"NexHealth API error: {e}")
        return []
