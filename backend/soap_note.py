"""
SOAP note generator — uses Claude Haiku for speed.
Produces chart-ready clinical documentation from triage data.
"""
import os
import json
from datetime import datetime
import anthropic
from sqlalchemy.orm import Session
from database import SOAPNote

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_soap_note(patient: dict) -> dict:
    """Generate a structured SOAP note from a patient record."""
    triage = patient.get("triage_detail", {})
    sensors = patient.get("sensor_data", {})
    ehr = patient.get("ehr_summary", {})

    prompt = f"""You are a clinical documentation specialist. Generate a complete, chart-ready SOAP note for this emergency department patient.

PATIENT DATA:
Name: {patient.get("name", "Unknown")}
Age: {patient.get("age", "?")} years old
Chief Complaint: {patient.get("chief_complaint", "")}
ESI Level: {patient.get("esi_level", "?")} — {patient.get("priority", "")}
AI Summary: {patient.get("ai_summary", "")}
Risk Flags: {", ".join(patient.get("risk_flags", [])) or "None"}

SENSOR / VITALS:
Heart Rate: {sensors.get("heart_rate", "Not recorded")}
Respiratory Rate: {sensors.get("respiratory_rate", "Not recorded")}
Skin Temp: {sensors.get("skin_temp", "Not recorded")}
Fever Flag: {sensors.get("fever_flag", False)}
O2 Sat: {sensors.get("o2_sat", "Not recorded")}
Gait Symmetry: {sensors.get("gait_symmetry", "Not recorded")}

EHR / HISTORY:
PMH: {", ".join(ehr.get("history", [])) or "None documented"}
Current Medications: {", ".join(ehr.get("medications", [])) or "None documented"}
Allergies: {", ".join(ehr.get("allergies", [])) or "NKDA"}

TRIAGE DETAIL:
qSOFA Score: {triage.get("qsofa_score", 0)}
Sepsis Probability: {triage.get("sepsis_probability", "low")}
Admission Probability: {triage.get("admission_probability", 0)}%
Differential Diagnoses: {", ".join(triage.get("differential_diagnoses", [])) or "Pending evaluation"}
Time-Sensitive Interventions: {", ".join(triage.get("time_sensitive_interventions", [])) or "None pre-staged"}
Room Assignment: {patient.get("room_assignment", "Pending")}
Care Pre-Staged: {", ".join(patient.get("care_pre_staged", [])) or "None"}

OUTPUT FORMAT — Return ONLY valid JSON, no markdown:
{{
  "subjective": "Complete S section — chief complaint in patient's words, HPI (onset, location, quality, severity, timing, modifying factors, associated symptoms), relevant ROS, pertinent social/family history",
  "objective": "Complete O section — vitals, physical exam findings from sensor data, ESI level, relevant lab/imaging ordered",
  "assessment": "Complete A section — primary working diagnosis with reasoning, risk stratification, differential diagnoses ranked by likelihood, relevant clinical scores (HEART, qSOFA, etc.)",
  "plan": "Complete P section — numbered action items: immediate interventions, orders placed, disposition, follow-up instructions, patient education points"
}}"""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        note = json.loads(raw.strip())
    except Exception as e:
        print(f"SOAP note generation error: {e}")
        note = _fallback_soap(patient)

    full_text = (
        f"SUBJECTIVE:\n{note['subjective']}\n\n"
        f"OBJECTIVE:\n{note['objective']}\n\n"
        f"ASSESSMENT:\n{note['assessment']}\n\n"
        f"PLAN:\n{note['plan']}"
    )

    return {
        "subjective": note["subjective"],
        "objective": note["objective"],
        "assessment": note["assessment"],
        "plan": note["plan"],
        "full_text": full_text,
        "generated_at": datetime.utcnow().isoformat(),
        "patient_id": patient.get("patient_id"),
        "patient_name": patient.get("name"),
        "esi_level": patient.get("esi_level"),
    }


def save_soap_note(db: Session, patient_id: str, note: dict, generated_by: str = "AI") -> SOAPNote:
    existing = db.query(SOAPNote).filter_by(patient_id=patient_id).first()
    if existing:
        existing.subjective = note["subjective"]
        existing.objective = note["objective"]
        existing.assessment = note["assessment"]
        existing.plan = note["plan"]
        existing.full_text = note["full_text"]
        existing.generated_at = datetime.utcnow()
        existing.generated_by = generated_by
        db.commit()
        return existing

    row = SOAPNote(
        patient_id=patient_id,
        generated_by=generated_by,
        subjective=note["subjective"],
        objective=note["objective"],
        assessment=note["assessment"],
        plan=note["plan"],
        full_text=note["full_text"],
    )
    db.add(row)
    db.commit()
    return row


def get_soap_note(db: Session, patient_id: str) -> dict | None:
    row = db.query(SOAPNote).filter_by(patient_id=patient_id).first()
    if not row:
        return None
    return {
        "patient_id": row.patient_id,
        "subjective": row.subjective,
        "objective": row.objective,
        "assessment": row.assessment,
        "plan": row.plan,
        "full_text": row.full_text,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "generated_by": row.generated_by,
        "finalized": row.finalized,
        "finalized_by": row.finalized_by,
    }


def finalize_note(db: Session, patient_id: str, physician: str) -> bool:
    row = db.query(SOAPNote).filter_by(patient_id=patient_id).first()
    if not row:
        return False
    row.finalized = True
    row.finalized_by = physician
    row.finalized_at = datetime.utcnow()
    db.commit()
    return True


def _fallback_soap(patient: dict) -> dict:
    name = patient.get("name", "Patient")
    age = patient.get("age", "?")
    cc = patient.get("chief_complaint", "presenting complaint")
    esi = patient.get("esi_level", "?")
    return {
        "subjective": f"{name} is a {age}-year-old presenting with {cc}. Onset and full HPI to be obtained by treating clinician. Patient able to provide history.",
        "objective": f"Vitals recorded via MediScan sensor portal at triage. ESI {esi} assigned by AI triage engine. Full physical exam deferred to bedside clinician.",
        "assessment": f"ESI {esi} — {patient.get('priority', 'see triage data')}. {patient.get('ai_summary', '')} Differential: {', '.join(patient.get('triage_detail', {}).get('differential_diagnoses', ['to be determined']))}.",
        "plan": "1. Bedside evaluation by treating clinician\n2. Review pre-staged orders\n3. Disposition per clinical assessment",
    }
