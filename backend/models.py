from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SensorReadings(BaseModel):
    heart_rate: int
    respiratory_rate: int
    gait_speed: float
    gait_symmetry: float
    skin_temp: float
    fever_flag: bool
    inflammation_zones: List[str]
    posture_score: float
    limb_asymmetry: Optional[str]
    injury_indicators: List[str]
    bone_density_flag: bool
    dense_tissue_alerts: List[str]


class BiometricResult(BaseModel):
    patient_id: str
    name: str
    age: int
    face_match_confidence: float
    wristband_nfc: Optional[str]


class EHRRecord(BaseModel):
    patient_id: str
    history: List[str]
    current_medications: List[str]
    allergies: List[str]
    last_visit: Optional[str]
    blood_type: str


class InsuranceResult(BaseModel):
    provider: str
    eligible: bool
    copay: float
    plan_type: str


class PatientScanRequest(BaseModel):
    name: str
    age: int
    chief_complaint: str
    wristband_id: Optional[str] = None


class ClinicalScores(BaseModel):
    qsofa_score: int              # 0-3 (>=2 = high sepsis risk)
    sirs_criteria_met: int        # 0-4
    sepsis_probability: str       # low / moderate / high / critical
    admission_probability: int    # 0-100 %
    lwbs_risk: str                # low / moderate / high
    deterioration_risk: str       # stable / watch / high
    vertical_flow_eligible: bool  # can be assessed standing/seated
    fast_track_eligible: bool     # ESI 3 candidates for fast track
    behavioral_health_flag: bool  # mental health / psych crisis
    sepsis_bundle_triggered: bool


class TriageResult(BaseModel):
    patient_id: str
    name: str
    age: int
    esi_level: int
    priority: str
    risk_flags: List[str]
    ai_summary: str
    routing_destination: str
    room_assignment: Optional[str]
    wristband_code: str
    wait_time_estimate: int
    care_pre_staged: List[str]
    timestamp: str
    sensor_data: Optional[SensorReadings] = None
    clinical_scores: Optional[ClinicalScores] = None
