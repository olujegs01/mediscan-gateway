"""
Pre-baked demo patients for the public kiosk/investor demo stream.
No real patient data — fully synthetic, no AI calls needed.
"""
import random
import uuid

DEMO_PATIENTS = [
    {
        "name": "James Okonkwo",
        "age": 58,
        "chief_complaint": "chest pain, shortness of breath",
        "esi_level": 2,
        "priority_label": "HIGH ACUITY",
        "routing_destination": "Immediate Bed",
        "room_assignment": "Room 2A",
        "wait_time_minutes": 5,
        "risk_flags": ["Elevated HR 118 bpm", "CAD history", "SIRS 2/4"],
        "ai_summary": "58-year-old male with CAD history presenting with chest pain and dyspnea. Elevated HR and thermal asymmetry suggest acute cardiac etiology. HEART score elevated — ECG and troponin ordered stat.",
        "care_pre_staged": ["12-lead ECG", "Troponin I + II stat", "IV access x2", "Aspirin 325mg", "O2 via nasal cannula", "Cardiac monitor"],
        "sepsis_probability": "low",
        "qsofa_score": 1,
        "admission_probability": 78,
        "disposition_prediction": "admit",
        "sensors": {"heart_rate": 118, "respiratory_rate": 22, "skin_temp": 37.8, "fever_flag": False, "gait_symmetry": 0.88, "posture_score": 72},
        "face_confidence": 96.4,
        "insurance": "BlueCross BlueShield PPO — Co-pay $150",
    },
    {
        "name": "Maria Santos",
        "age": 34,
        "chief_complaint": "anxiety / panic, difficulty breathing",
        "esi_level": 3,
        "priority_label": "URGENT",
        "routing_destination": "Fast Track",
        "room_assignment": "Fast Track 3",
        "wait_time_minutes": 20,
        "risk_flags": ["Behavioral health flag", "Asthma history", "SpO2 borderline"],
        "ai_summary": "34-year-old female with asthma and anxiety disorder presenting with acute panic attack and respiratory symptoms. Behavioral health early routing triggered. Peak flow and psych consult ordered.",
        "care_pre_staged": ["Albuterol nebulizer", "SpO2 monitoring", "Psychiatric evaluation consult", "Anxiolytic PRN"],
        "sepsis_probability": "low",
        "qsofa_score": 0,
        "admission_probability": 35,
        "disposition_prediction": "discharge",
        "sensors": {"heart_rate": 104, "respiratory_rate": 24, "skin_temp": 37.2, "fever_flag": False, "gait_symmetry": 0.94, "posture_score": 85},
        "face_confidence": 94.1,
        "insurance": "Aetna HMO — Co-pay $75",
    },
    {
        "name": "Derek Williams",
        "age": 72,
        "chief_complaint": "fever & chills, difficulty breathing",
        "esi_level": 2,
        "priority_label": "HIGH ACUITY",
        "routing_destination": "Immediate Bed",
        "room_assignment": "Room 3B",
        "wait_time_minutes": 5,
        "risk_flags": ["SEPSIS ALERT — qSOFA 2", "SIRS 3/4", "COPD + CHF", "Temp 38.9°C"],
        "ai_summary": "72-year-old male with COPD, CHF, and AFib presenting with fever and respiratory distress. qSOFA 2 + SIRS 3 — Surviving Sepsis Campaign bundle triggered. Sepsis workup and broad-spectrum antibiotics initiated.",
        "care_pre_staged": ["Blood cultures x2", "Lactate level", "CBC BMP CMP", "1L NS bolus", "Piperacillin-tazobactam IV", "O2 via NRB mask", "Repeat vitals q15min"],
        "sepsis_probability": "high",
        "qsofa_score": 2,
        "admission_probability": 92,
        "disposition_prediction": "ICU",
        "sensors": {"heart_rate": 112, "respiratory_rate": 26, "skin_temp": 38.9, "fever_flag": True, "gait_symmetry": 0.71, "posture_score": 55},
        "face_confidence": 91.7,
        "insurance": "Medicare Advantage — Co-pay $0",
    },
    {
        "name": "Aisha Patel",
        "age": 26,
        "chief_complaint": "urinary symptoms, fever & chills",
        "esi_level": 4,
        "priority_label": "LESS URGENT",
        "routing_destination": "Vertical Flow",
        "room_assignment": "VF-2",
        "wait_time_minutes": 45,
        "risk_flags": ["Low-grade fever 38.1°C", "Vertical flow eligible"],
        "ai_summary": "26-year-old female with no significant history presenting with dysuria and low-grade fever. Presentation consistent with uncomplicated UTI. Urinalysis and urine culture ordered. Vertical flow eligible — 30% LOS reduction.",
        "care_pre_staged": ["Urinalysis + urine culture", "CBC", "Nitrofurantoin 100mg if UA positive"],
        "sepsis_probability": "low",
        "qsofa_score": 0,
        "admission_probability": 8,
        "disposition_prediction": "discharge",
        "sensors": {"heart_rate": 88, "respiratory_rate": 16, "skin_temp": 38.1, "fever_flag": True, "gait_symmetry": 0.97, "posture_score": 95},
        "face_confidence": 98.2,
        "insurance": "UnitedHealthcare HDHP — Co-pay $200",
    },
]


def get_demo_patient(index: int) -> dict:
    p = DEMO_PATIENTS[index % len(DEMO_PATIENTS)]
    patient_id = f"DEMO-{uuid.uuid4().hex[:6].upper()}"
    return {**p, "patient_id": patient_id}
