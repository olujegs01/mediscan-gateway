import random
import uuid
from models import BiometricResult, EHRRecord, InsuranceResult

SAMPLE_EHR_DB = {
    "P001": {
        "name": "James Okonkwo",
        "age": 58,
        "history": ["Type 2 Diabetes", "Hypertension", "Coronary Artery Disease"],
        "medications": ["Metformin 500mg", "Lisinopril 10mg", "Aspirin 81mg", "Atorvastatin 40mg"],
        "allergies": ["Penicillin", "Sulfa drugs"],
        "last_visit": "2026-02-14",
        "blood_type": "O+",
    },
    "P002": {
        "name": "Maria Santos",
        "age": 34,
        "history": ["Asthma", "Anxiety disorder"],
        "medications": ["Albuterol inhaler", "Sertraline 50mg"],
        "allergies": ["Latex", "Ibuprofen"],
        "last_visit": "2025-11-03",
        "blood_type": "A+",
    },
    "P003": {
        "name": "Derek Williams",
        "age": 72,
        "history": ["COPD", "Atrial Fibrillation", "Osteoporosis", "CHF"],
        "medications": ["Warfarin 5mg", "Metoprolol 50mg", "Furosemide 40mg", "Tiotropium"],
        "allergies": ["Codeine"],
        "last_visit": "2026-03-28",
        "blood_type": "B-",
    },
    "P004": {
        "name": "Aisha Patel",
        "age": 26,
        "history": ["No significant history"],
        "medications": [],
        "allergies": [],
        "last_visit": None,
        "blood_type": "AB+",
    },
}

INSURANCE_DB = {
    "P001": {"provider": "BlueCross BlueShield", "eligible": True, "copay": 150.0, "plan_type": "PPO"},
    "P002": {"provider": "Aetna", "eligible": True, "copay": 75.0, "plan_type": "HMO"},
    "P003": {"provider": "Medicare Advantage", "eligible": True, "copay": 0.0, "plan_type": "Medicare"},
    "P004": {"provider": "UnitedHealthcare", "eligible": True, "copay": 200.0, "plan_type": "HDHP"},
}


def identify_patient(name: str, wristband_id: str = None) -> BiometricResult:
    """Simulates face recognition + NFC wristband scan."""
    matched_id = None

    # Match by name (simulating face recognition lookup)
    for pid, record in SAMPLE_EHR_DB.items():
        if name.lower() in record["name"].lower() or record["name"].lower() in name.lower():
            matched_id = pid
            break

    if not matched_id:
        matched_id = f"NEW-{uuid.uuid4().hex[:6].upper()}"
        return BiometricResult(
            patient_id=matched_id,
            name=name,
            age=0,
            face_match_confidence=0.0,
            wristband_nfc=wristband_id,
        )

    record = SAMPLE_EHR_DB[matched_id]
    return BiometricResult(
        patient_id=matched_id,
        name=record["name"],
        age=record["age"],
        face_match_confidence=round(random.uniform(0.91, 0.99), 3),
        wristband_nfc=wristband_id or f"NFC-{matched_id}",
    )


def pull_ehr(patient_id: str, name: str, age: int) -> EHRRecord:
    """Pulls EHR from Epic/Cerner simulation."""
    if patient_id in SAMPLE_EHR_DB:
        r = SAMPLE_EHR_DB[patient_id]
        return EHRRecord(
            patient_id=patient_id,
            history=r["history"],
            current_medications=r["medications"],
            allergies=r["allergies"],
            last_visit=r["last_visit"],
            blood_type=r["blood_type"],
        )
    return EHRRecord(
        patient_id=patient_id,
        history=[],
        current_medications=[],
        allergies=[],
        last_visit=None,
        blood_type="Unknown",
    )


def verify_insurance(patient_id: str) -> InsuranceResult:
    """Real-time insurance eligibility check simulation."""
    if patient_id in INSURANCE_DB:
        d = INSURANCE_DB[patient_id]
        return InsuranceResult(**d)
    return InsuranceResult(
        provider="Self-Pay",
        eligible=False,
        copay=0.0,
        plan_type="None",
    )
