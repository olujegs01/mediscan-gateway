"""
Seeds 30 days of realistic demo data on a fresh environment.
Called at startup when the audit log has fewer than 50 records.
"""
import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import AuditLog, PatientRecord, ClinicalJourney

DEMO_PATIENTS = [
    {"name": "James Okonkwo",   "age": 58, "complaint": "chest pain, shortness of breath",      "esi": 2},
    {"name": "Maria Santos",    "age": 34, "complaint": "abdominal pain, nausea",                "esi": 3},
    {"name": "Derek Williams",  "age": 72, "complaint": "altered consciousness, fever 104°F",    "esi": 1},
    {"name": "Aisha Patel",     "age": 26, "complaint": "anxiety, palpitations",                 "esi": 3},
    {"name": "Robert Chen",     "age": 65, "complaint": "stroke symptoms, left arm weakness",    "esi": 1},
    {"name": "Linda Foster",    "age": 45, "complaint": "back pain, difficulty walking",         "esi": 3},
    {"name": "Michael Torres",  "age": 52, "complaint": "sepsis symptoms, fever 103°F, hypotension", "esi": 2},
    {"name": "Sarah Johnson",   "age": 29, "complaint": "lacerations from fall injury",          "esi": 4},
    {"name": "David Kim",       "age": 78, "complaint": "respiratory distress, COPD exacerbation","esi": 2},
    {"name": "Emma Wilson",     "age": 19, "complaint": "allergic reaction, hives, facial swelling","esi": 3},
    {"name": "Charles Brown",   "age": 61, "complaint": "hypertensive urgency, severe headache", "esi": 2},
    {"name": "Patricia Moore",  "age": 44, "complaint": "urinary symptoms, right flank pain",    "esi": 4},
    {"name": "Anthony Davis",   "age": 33, "complaint": "suicidal ideation, mental health crisis","esi": 2},
    {"name": "Karen White",     "age": 55, "complaint": "syncope, dizziness, pre-syncope",       "esi": 2},
    {"name": "Mark Garcia",     "age": 41, "complaint": "eye pain, foreign body in eye",         "esi": 4},
]

_HOUR_WEIGHTS = [3,2,2,1,1,2,3,5,8,10,12,13,12,11,10,9,10,11,13,12,10,8,6,4]
_USERS = ["nurse1", "admin", "physician1", "nurse2"]


def seed_demo_data(db: Session):
    """No-op if DB already has meaningful data."""
    existing = db.query(AuditLog).count()
    if existing >= 50:
        return

    rng = random.Random(42)
    now = datetime.utcnow()
    scanned: list[tuple[str, dict, datetime]] = []

    # ── 30 days of scan audit logs ──────────────────────────────
    for day in range(30, 0, -1):
        base = now - timedelta(days=day)
        daily = rng.randint(45, 115)
        for _ in range(daily):
            hour = rng.choices(range(24), weights=_HOUR_WEIGHTS)[0]
            ts = base.replace(
                hour=hour,
                minute=rng.randint(0, 59),
                second=rng.randint(0, 59),
                microsecond=0,
            )
            pat = rng.choice(DEMO_PATIENTS)
            pid = f"PT-{str(uuid.uuid4())[:8].upper()}"
            scanned.append((pid, pat, ts))
            db.add(AuditLog(
                username=rng.choice(_USERS),
                role=rng.choice(["nurse", "admin", "physician"]),
                action="scan",
                patient_id=pid,
                ip_address="10.0.0.1",
                success=True,
                timestamp=ts,
                details={"complaint": pat["complaint"], "esi": pat["esi"]},
            ))
    db.commit()

    # ── 60 discharged patient records ──────────────────────────
    for pid, pat, ts in scanned[-60:]:
        db.add(PatientRecord(
            patient_id=pid,
            name=pat["name"],
            age=pat["age"],
            chief_complaint=pat["complaint"],
            esi_level=pat["esi"],
            status="discharged",
            timestamp=ts,
            discharged_at=ts + timedelta(hours=rng.randint(1, 6)),
        ))
    db.commit()

    # ── Clinical Journeys for ~70% of recent patients ──────────
    _schedule = {1: [24, 48], 2: [24, 72], 3: [72, 168], 4: [168], 5: [168]}
    _statuses = ["completed"] * 16 + ["escalated"] * 3 + ["active"] * 6

    for pid, pat, ts in scanned[-40:]:
        status = rng.choice(_statuses)
        sched = _schedule.get(pat["esi"], [168])
        completed = rng.randint(1, len(sched)) if status in ("completed", "escalated") else rng.randint(0, 1)
        db.add(ClinicalJourney(
            patient_id=pid,
            name=pat["name"],
            phone=f"+1312555{rng.randint(1000, 9999)}",
            esi_level=pat["esi"],
            discharge_at=ts + timedelta(hours=2),
            journey_status=status,
            checkins_completed=completed,
            checkins_total=len(sched),
            portal_token=str(uuid.uuid4()),
            last_response=(
                "Feeling much better, pain is a 2/10. Thank you for checking in."
                if status == "completed"
                else "Symptoms much worse, having trouble breathing. Please advise."
                if status == "escalated"
                else None
            ),
            escalated_reason="Patient reported worsening symptoms via SMS" if status == "escalated" else None,
        ))
    db.commit()
    print("[MediScan] ✅ Demo data seeded — 30d audit logs + 60 patients + 40 journeys")
