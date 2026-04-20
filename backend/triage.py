import os
import json
import anthropic
from models import SensorReadings, EHRRecord, TriageResult

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def run_ai_triage(
    patient_id: str,
    name: str,
    age: int,
    chief_complaint: str,
    sensors: SensorReadings,
    ehr: EHRRecord,
) -> dict:
    """
    Zone 3: AI Diagnostic Engine using Claude claude-sonnet-4-6 with extended thinking.
    Performs sensor fusion + LLM triage + ESI scoring in < 8 seconds.
    """

    prompt = f"""You are a hospital AI triage engine operating inside a MedScan Gateway walk-through scanner portal.
A patient has just completed a full-body multi-sensor scan. You must perform sensor fusion,
clinical assessment, and assign an ESI (Emergency Severity Index) level 1-5.

## PATIENT
- ID: {patient_id}
- Name: {name}
- Age: {age}
- Chief Complaint: {chief_complaint}

## ZONE 1 SENSOR DATA

**mmWave Radar (non-contact vitals):**
- Heart Rate: {sensors.heart_rate} bpm
- Respiratory Rate: {sensors.respiratory_rate} breaths/min
- Gait Speed: {sensors.gait_speed} m/s
- Gait Symmetry Score: {sensors.gait_symmetry} (1.0 = perfect)

**Thermal IR Camera:**
- Skin Temperature: {sensors.skin_temp}°C
- Fever Flag: {sensors.fever_flag}
- Inflammation Zones: {', '.join(sensors.inflammation_zones) if sensors.inflammation_zones else 'None'}

**LiDAR Depth Sensor:**
- Posture Score: {sensors.posture_score}/100
- Limb Asymmetry: {sensors.limb_asymmetry or 'None detected'}
- Injury Indicators: {', '.join(sensors.injury_indicators) if sensors.injury_indicators else 'None'}

**Spectral X-ray:**
- Bone Density Flag: {sensors.bone_density_flag}
- Dense Tissue Alerts: {', '.join(sensors.dense_tissue_alerts) if sensors.dense_tissue_alerts else 'None'}

## ZONE 2 EHR DATA (pulled from Epic/Cerner)
- Medical History: {', '.join(ehr.history) if ehr.history else 'No prior history'}
- Current Medications: {', '.join(ehr.current_medications) if ehr.current_medications else 'None'}
- Known Allergies: {', '.join(ehr.allergies) if ehr.allergies else 'NKDA'}
- Blood Type: {ehr.blood_type}
- Last Visit: {ehr.last_visit or 'First visit'}

## YOUR TASK
Analyze ALL sensor modalities together (sensor fusion). Cross-reference with EHR history.
Assess risk for: heart attack, stroke, sepsis, respiratory failure, major trauma, psychiatric crisis.

Return ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "esi_level": <1-5>,
  "priority_label": "<CRITICAL|HIGH ACUITY|URGENT|LESS URGENT|NON-URGENT>",
  "risk_flags": ["<up to 4 specific clinical flags>"],
  "primary_concern": "<one sentence clinical summary>",
  "ai_summary": "<2-3 sentence clinical narrative for the MD>",
  "routing_destination": "<Trauma Bay|Immediate Bed|Fast Track|Self-Serve Kiosk|Crisis Suite>",
  "room_assignment": "<e.g. Trauma 1, Room 4B, Fast Track 2>",
  "wait_time_minutes": <0-120>,
  "care_pre_staged": ["<ordered interventions, e.g. 'IV access', '12-lead ECG', 'CBC BMP', 'Chest X-ray'>"],
  "md_alert_message": "<brief message sent to on-call physician's mobile>"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            thinking={
                "type": "enabled",
                "budget_tokens": 800,
            },
            messages=[{"role": "user", "content": prompt}],
        )

        text_block = next(
            (b.text for b in response.content if hasattr(b, "text")), None
        )

        if not text_block:
            raise ValueError("No text in response")

        # Strip any accidental markdown fences
        text_block = text_block.strip()
        if text_block.startswith("```"):
            text_block = text_block.split("```")[1]
            if text_block.startswith("json"):
                text_block = text_block[4:]

        return json.loads(text_block.strip())

    except Exception as e:
        print(f"Claude triage error: {e}")
        return _fallback_triage(age, chief_complaint, sensors)


def _fallback_triage(age: int, complaint: str, sensors: SensorReadings) -> dict:
    """Rule-based fallback if Claude is unavailable."""
    c = complaint.lower()

    if (sensors.heart_rate > 130 or sensors.respiratory_rate > 30
            or any(k in c for k in ["chest pain", "stroke", "unresponsive", "unconscious"])):
        esi = 1
        routing = "Trauma Bay"
        room = "Trauma 1"
        wait = 0
        care = ["Immediate physician", "Crash cart on standby", "IV access x2", "12-lead ECG"]
        flags = ["Critical vitals", "Immediate life threat"]
    elif (sensors.heart_rate > 110 or sensors.fever_flag
          or any(k in c for k in ["sepsis", "difficulty breathing", "stroke symptoms"])):
        esi = 2
        routing = "Immediate Bed"
        room = "Room 2A"
        wait = 5
        care = ["IV access", "CBC BMP Lactate", "Blood cultures", "O2 monitoring"]
        flags = ["High acuity", "Potential sepsis/cardiac event"]
    elif sensors.heart_rate > 100 or sensors.skin_temp > 38.5:
        esi = 3
        routing = "Fast Track"
        room = "Fast Track 3"
        wait = 20
        care = ["CBC BMP", "Urinalysis", "Chest X-ray if indicated"]
        flags = ["Elevated vitals", "Urgent evaluation needed"]
    elif any(k in c for k in ["pain", "injury", "cut", "nausea"]):
        esi = 4
        routing = "Fast Track"
        room = "Fast Track 5"
        wait = 45
        care = ["Vital signs monitoring", "Pain assessment"]
        flags = ["Non-critical pain complaint"]
    else:
        esi = 5
        routing = "Self-Serve Kiosk"
        room = "Kiosk B"
        wait = 90
        care = ["Nurse triage on arrival"]
        flags = []

    priority_map = {1: "CRITICAL", 2: "HIGH ACUITY", 3: "URGENT", 4: "LESS URGENT", 5: "NON-URGENT"}

    return {
        "esi_level": esi,
        "priority_label": priority_map[esi],
        "risk_flags": flags,
        "primary_concern": complaint,
        "ai_summary": f"Patient presents with {complaint}. ESI {esi} assigned by rule-based fallback.",
        "routing_destination": routing,
        "room_assignment": room,
        "wait_time_minutes": wait,
        "care_pre_staged": care,
        "md_alert_message": f"New ESI {esi} patient: {complaint}",
    }
