"""
Zone 1 hardware sensor integration layer.

Each function tries the real SDK/API first, falls back to sensors.py simulation
if hardware is unavailable (dev mode, sensor offline, etc.).

Swap in real SDKs by setting env vars:
  MMWAVE_HOST     — IP/hostname of mmWave radar module (e.g. TI IWR6843)
  THERMAL_HOST    — IP of thermal camera (e.g. FLIR A50)
  LIDAR_HOST      — IP of LiDAR unit (e.g. Ouster OS1)
  SPECTRAL_HOST   — IP of spectral X-ray panel
"""

import os
import httpx
from sensors import run_sensor_suite
from models import SensorReadings

MMWAVE_HOST   = os.getenv("MMWAVE_HOST")
THERMAL_HOST  = os.getenv("THERMAL_HOST")
LIDAR_HOST    = os.getenv("LIDAR_HOST")
SPECTRAL_HOST = os.getenv("SPECTRAL_HOST")

HARDWARE_TIMEOUT = 3.0  # seconds per sensor call


def _get(url: str, params: dict = None) -> dict:
    r = httpx.get(url, params=params, timeout=HARDWARE_TIMEOUT)
    r.raise_for_status()
    return r.json()


def read_mmwave(age: int, complaint: str) -> dict:
    """
    TI IWR6843 / Acconeer XM125 REST API.
    Expected response: { heart_rate, respiratory_rate, gait_speed, gait_symmetry }
    """
    if not MMWAVE_HOST:
        return None
    try:
        return _get(f"http://{MMWAVE_HOST}/api/vitals")
    except Exception as e:
        print(f"[mmWave] hardware unavailable ({e}), using simulation")
        return None


def read_thermal(age: int, complaint: str) -> dict:
    """
    FLIR A50 / Lepton REST API.
    Expected response: { skin_temp, fever_flag, inflammation_zones }
    """
    if not THERMAL_HOST:
        return None
    try:
        return _get(f"http://{THERMAL_HOST}/api/scan")
    except Exception as e:
        print(f"[Thermal] hardware unavailable ({e}), using simulation")
        return None


def read_lidar(age: int, complaint: str) -> dict:
    """
    Ouster OS1 / Intel RealSense REST API.
    Expected response: { posture_score, limb_asymmetry, injury_indicators }
    """
    if not LIDAR_HOST:
        return None
    try:
        return _get(f"http://{LIDAR_HOST}/api/depth")
    except Exception as e:
        print(f"[LiDAR] hardware unavailable ({e}), using simulation")
        return None


def read_spectral(age: int, complaint: str) -> dict:
    """
    Spectral X-ray panel REST API.
    Expected response: { bone_density_flag, dense_tissue_alerts }
    """
    if not SPECTRAL_HOST:
        return None
    try:
        return _get(f"http://{SPECTRAL_HOST}/api/scan")
    except Exception as e:
        print(f"[Spectral] hardware unavailable ({e}), using simulation")
        return None


def run_full_scan(age: int, chief_complaint: str) -> SensorReadings:
    """
    Tries each hardware sensor independently.
    Any sensor that fails or is unconfigured falls back to simulation for that modality only.
    All four modalities are always returned in the unified SensorReadings model.
    """
    # Get simulation baseline (used as fallback per-modality)
    sim = run_sensor_suite(age, chief_complaint)

    mmwave   = read_mmwave(age, chief_complaint)
    thermal  = read_thermal(age, chief_complaint)
    lidar    = read_lidar(age, chief_complaint)
    spectral = read_spectral(age, chief_complaint)

    return SensorReadings(
        # mmWave — real or sim
        heart_rate        = mmwave.get("heart_rate", sim.heart_rate)       if mmwave   else sim.heart_rate,
        respiratory_rate  = mmwave.get("respiratory_rate", sim.respiratory_rate) if mmwave else sim.respiratory_rate,
        gait_speed        = mmwave.get("gait_speed", sim.gait_speed)       if mmwave   else sim.gait_speed,
        gait_symmetry     = mmwave.get("gait_symmetry", sim.gait_symmetry) if mmwave   else sim.gait_symmetry,

        # Thermal — real or sim
        skin_temp          = thermal.get("skin_temp", sim.skin_temp)           if thermal else sim.skin_temp,
        fever_flag         = thermal.get("fever_flag", sim.fever_flag)         if thermal else sim.fever_flag,
        inflammation_zones = thermal.get("inflammation_zones", sim.inflammation_zones) if thermal else sim.inflammation_zones,

        # LiDAR — real or sim
        posture_score    = lidar.get("posture_score", sim.posture_score)       if lidar else sim.posture_score,
        limb_asymmetry   = lidar.get("limb_asymmetry", sim.limb_asymmetry)    if lidar else sim.limb_asymmetry,
        injury_indicators= lidar.get("injury_indicators", sim.injury_indicators) if lidar else sim.injury_indicators,

        # Spectral — real or sim
        bone_density_flag   = spectral.get("bone_density_flag", sim.bone_density_flag)   if spectral else sim.bone_density_flag,
        dense_tissue_alerts = spectral.get("dense_tissue_alerts", sim.dense_tissue_alerts) if spectral else sim.dense_tissue_alerts,
    )
