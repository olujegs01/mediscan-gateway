from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SensorReadings(BaseModel):
    # mmWave radar
    heart_rate: int
    respiratory_rate: int
    gait_speed: float
    gait_symmetry: float  # 0-1 score
    # Thermal IR
    skin_temp: float
    fever_flag: bool
    inflammation_zones: List[str]
    # LiDAR depth
    posture_score: float  # 0-100
    limb_asymmetry: Optional[str]
    injury_indicators: List[str]
    # Spectral X-ray
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
    wait_time_estimate: int  # minutes
    care_pre_staged: List[str]
    timestamp: str
    sensor_data: Optional[SensorReadings] = None
