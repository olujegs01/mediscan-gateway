import random
import numpy as np
from models import SensorReadings


def run_sensor_suite(age: int, chief_complaint: str) -> SensorReadings:
    """
    Simulates all Zone 1 sensors firing simultaneously as patient walks through the portal.
    In production: mmWave radar, Thermal IR camera, LiDAR depth sensor, Spectral X-ray.
    """
    complaint = chief_complaint.lower()

    # --- mmWave Radar: non-contact vitals + gait ---
    hr_base = 75
    rr_base = 16

    if any(k in complaint for k in ["chest", "heart", "cardiac"]):
        hr_base = random.randint(105, 145)
        rr_base = random.randint(22, 30)
    elif any(k in complaint for k in ["breath", "asthma", "respiratory"]):
        hr_base = random.randint(90, 120)
        rr_base = random.randint(24, 32)
    elif any(k in complaint for k in ["fall", "dizzy", "faint"]):
        hr_base = random.randint(50, 65)
        rr_base = random.randint(10, 14)
    elif any(k in complaint for k in ["fever", "infection", "sepsis"]):
        hr_base = random.randint(100, 130)
        rr_base = random.randint(20, 26)
    else:
        hr_base = random.randint(65, 95)
        rr_base = random.randint(14, 20)

    heart_rate = hr_base + random.randint(-5, 5)
    respiratory_rate = rr_base + random.randint(-2, 2)

    gait_speed = round(random.uniform(0.6, 1.4), 2)
    gait_symmetry = round(random.uniform(0.7, 1.0), 2)

    if any(k in complaint for k in ["fall", "limp", "hip", "knee", "ankle", "leg"]):
        gait_speed = round(random.uniform(0.3, 0.7), 2)
        gait_symmetry = round(random.uniform(0.4, 0.75), 2)

    # --- Thermal IR: skin temp map, fever, inflammation ---
    skin_temp = round(random.uniform(36.1, 37.2), 1)
    fever_flag = False
    inflammation_zones = []

    if any(k in complaint for k in ["fever", "infection", "sepsis", "flu"]):
        skin_temp = round(random.uniform(38.5, 40.2), 1)
        fever_flag = True
        inflammation_zones = random.sample(["forehead", "neck", "torso"], k=random.randint(1, 2))
    elif any(k in complaint for k in ["pain", "swelling", "inflam"]):
        skin_temp = round(random.uniform(37.3, 38.0), 1)
        inflammation_zones = random.sample(["left arm", "right knee", "lower back", "abdomen"], k=1)

    # --- LiDAR Depth: posture, asymmetry, injury indicators ---
    posture_score = round(random.uniform(60, 95), 1)
    limb_asymmetry = None
    injury_indicators = []

    if any(k in complaint for k in ["back", "spine", "posture"]):
        posture_score = round(random.uniform(30, 55), 1)
        injury_indicators.append("spinal curvature detected")
    if any(k in complaint for k in ["arm", "shoulder", "wrist"]):
        limb_asymmetry = "upper left limb guarding posture"
        injury_indicators.append("upper extremity movement restriction")
    if any(k in complaint for k in ["fall", "hip", "leg", "knee"]):
        limb_asymmetry = "lower limb asymmetric weight bearing"
        injury_indicators.append("possible lower extremity injury")
        posture_score = round(random.uniform(40, 65), 1)

    # --- Spectral X-ray: bone density, dense tissue flags ---
    bone_density_flag = False
    dense_tissue_alerts = []

    if age > 60 or any(k in complaint for k in ["fracture", "bone", "break", "fall"]):
        bone_density_flag = random.random() > 0.4
        if bone_density_flag:
            dense_tissue_alerts = random.sample(
                ["reduced trabecular density L2-L4", "cortical thinning distal radius",
                 "hip cortical irregularity", "compression pattern T12"],
                k=1
            )

    if any(k in complaint for k in ["chest", "lung", "breath"]):
        dense_tissue_alerts.append("pulmonary opacity flag — possible consolidation")

    return SensorReadings(
        heart_rate=heart_rate,
        respiratory_rate=respiratory_rate,
        gait_speed=gait_speed,
        gait_symmetry=gait_symmetry,
        skin_temp=skin_temp,
        fever_flag=fever_flag,
        inflammation_zones=inflammation_zones,
        posture_score=posture_score,
        limb_asymmetry=limb_asymmetry,
        injury_indicators=injury_indicators,
        bone_density_flag=bone_density_flag,
        dense_tissue_alerts=dense_tissue_alerts,
    )
