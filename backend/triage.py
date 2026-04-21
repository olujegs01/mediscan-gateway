"""
MediScan AI Triage Engine — powered by Claude claude-sonnet-4-6 with extended thinking.

Clinical frameworks embedded (based on current ED research):
- ESI v4 (Emergency Severity Index)
- qSOFA (quick Sequential Organ Failure Assessment) — sepsis
- SIRS (Systemic Inflammatory Response Syndrome) — sepsis
- Surviving Sepsis Campaign bundle auto-trigger
- HEART score (chest pain — cardiac risk)
- Cincinnati Stroke Scale (stroke symptoms)
- Vertical Patient Flow eligibility (reduces LOS 30%)
- Behavioral Health fast-routing (avg 9-10hr wait without early intervention)
- LWBS (Left Without Being Seen) risk prediction
- Admission probability modeling
- Deterioration risk scoring
"""

import os
import json
import anthropic
from models import SensorReadings, EHRRecord, ClinicalScores

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def run_ai_triage(
    patient_id: str,
    name: str,
    age: int,
    chief_complaint: str,
    sensors: SensorReadings,
    ehr: EHRRecord,
) -> dict:

    prompt = f"""You are MediScan's clinical AI engine — the most advanced emergency triage system in the world.
A patient just walked through our multi-sensor portal. You have 8 seconds to prevent them from becoming
a statistic: 1 in 3 ED patients wait over 2 hours; LWBS rates have doubled; sepsis is missed 1 in 8 times.

Your job: sensor fusion + clinical scoring + ESI assignment + actionable routing. Lives depend on this.

═══════════════════════════════════════════════
PATIENT PROFILE
═══════════════════════════════════════════════
ID: {patient_id}
Name: {name}
Age: {age}
Chief Complaints: {chief_complaint}

═══════════════════════════════════════════════
ZONE 1 — SENSOR READINGS
═══════════════════════════════════════════════
mmWave Radar (non-contact vitals):
  Heart Rate:        {sensors.heart_rate} bpm
  Respiratory Rate:  {sensors.respiratory_rate} breaths/min
  Gait Speed:        {sensors.gait_speed} m/s
  Gait Symmetry:     {sensors.gait_symmetry} (1.0 = normal)

Thermal IR Camera:
  Skin Temperature:       {sensors.skin_temp}°C
  Fever Flag:             {sensors.fever_flag}
  Inflammation Zones:     {', '.join(sensors.inflammation_zones) if sensors.inflammation_zones else 'None'}

LiDAR Depth Sensor:
  Posture Score:          {sensors.posture_score}/100
  Limb Asymmetry:         {sensors.limb_asymmetry or 'None detected'}
  Injury Indicators:      {', '.join(sensors.injury_indicators) if sensors.injury_indicators else 'None'}

Spectral X-ray:
  Bone Density Flag:      {sensors.bone_density_flag}
  Dense Tissue Alerts:    {', '.join(sensors.dense_tissue_alerts) if sensors.dense_tissue_alerts else 'None'}

═══════════════════════════════════════════════
ZONE 2 — EHR (Epic/Cerner)
═══════════════════════════════════════════════
Medical History:    {', '.join(ehr.history) if ehr.history else 'No prior history'}
Medications:        {', '.join(ehr.current_medications) if ehr.current_medications else 'None'}
Allergies:          {', '.join(ehr.allergies) if ehr.allergies else 'NKDA'}
Blood Type:         {ehr.blood_type}
Last Visit:         {ehr.last_visit or 'First visit / Unknown'}

═══════════════════════════════════════════════
CLINICAL SCORING — APPLY ALL FRAMEWORKS
═══════════════════════════════════════════════

1. qSOFA (Sepsis) — score 1 point each:
   - RR >= 22: {1 if sensors.respiratory_rate >= 22 else 0}
   - Altered mentation (infer from gait/complaint)
   - SBP <= 100 (infer from HR pattern + gait)
   Score >= 2 = HIGH sepsis risk → trigger Surviving Sepsis Campaign bundle

2. SIRS Criteria — score 1 each:
   - Temp > 38°C or < 36°C: {1 if sensors.skin_temp > 38.0 or sensors.skin_temp < 36.0 else 0}
   - HR > 90: {1 if sensors.heart_rate > 90 else 0}
   - RR > 20: {1 if sensors.respiratory_rate > 20 else 0}
   - WBC (infer from fever + complaint pattern)
   >= 2 criteria = SIRS positive

3. Stroke Screen (if neurological complaint):
   - Sudden facial droop (infer from complaint)
   - Arm drift (infer from limb asymmetry: {sensors.limb_asymmetry})
   - Speech difficulty (infer from complaint)
   → FAST positive = ESI 1-2, CT head immediately

4. Cardiac Risk (if chest pain):
   - Age {age}, HR {sensors.heart_rate}, history: {', '.join(ehr.history[:3]) if ehr.history else 'none'}
   - Apply HEART score components

5. Behavioral Health Assessment:
   - Flag if: suicidal ideation / mental health crisis / altered behavior
   - BH patients avg 9-10hrs without early routing — intercept immediately

6. Vertical Flow Eligibility:
   - ESI 3-5 with low-acuity complaints (skin, urinary, eye, minor pain)
   - Can be assessed standing/seated → 30% LOS reduction
   - NOT eligible if: unstable vitals, fall risk (gait symmetry < 0.75), severe pain

7. Admission Probability (0-100%):
   - Based on: age, ESI, vitals, history (CHF, COPD, CAD, diabetes, cancer)
   - High admission risk → pre-notify bed management now

8. LWBS Risk:
   - High: ESI 4-5 + wait > 45min predicted + complaint allows self-care
   - Moderate: ESI 3 + long queue + no immediate interventions needed
   - Proactive messaging reduces LWBS by 60%

═══════════════════════════════════════════════
RESPOND WITH VALID JSON ONLY — NO MARKDOWN
═══════════════════════════════════════════════
{{
  "esi_level": <1-5>,
  "priority_label": "<CRITICAL|HIGH ACUITY|URGENT|LESS URGENT|NON-URGENT>",
  "risk_flags": ["<up to 5 specific clinical flags>"],
  "primary_concern": "<one-line clinical summary>",
  "ai_summary": "<2-3 sentence clinical narrative for the attending physician>",
  "routing_destination": "<Trauma Bay|Resuscitation|Immediate Bed|Fast Track|Vertical Flow|Behavioral Health Suite|Self-Serve Kiosk>",
  "room_assignment": "<specific room e.g. Trauma 1, Room 4B, VF-3, BH-Suite 2>",
  "wait_time_minutes": <0-180>,
  "care_pre_staged": ["<specific orders — labs, imaging, meds, IV, O2, monitors>"],
  "md_alert_message": "<urgent 1-line text to on-call physician mobile>",
  "qsofa_score": <0-3>,
  "sirs_criteria_met": <0-4>,
  "sepsis_probability": "<low|moderate|high|critical>",
  "sepsis_bundle_triggered": <true|false>,
  "admission_probability": <0-100>,
  "lwbs_risk": "<low|moderate|high>",
  "deterioration_risk": "<stable|watch|high>",
  "vertical_flow_eligible": <true|false>,
  "fast_track_eligible": <true|false>,
  "behavioral_health_flag": <true|false>,
  "differential_diagnoses": ["<top 3 differentials to rule out>"],
  "time_sensitive_interventions": ["<interventions that must happen in <30 min>"],
  "disposition_prediction": "<discharge|observation|admit|ICU|OR>"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            thinking={"type": "enabled", "budget_tokens": 1200},
            messages=[{"role": "user", "content": prompt}],
        )

        text_block = next(
            (b.text for b in response.content if hasattr(b, "text")), None
        )
        if not text_block:
            raise ValueError("No text in Claude response")

        text_block = text_block.strip()
        if text_block.startswith("```"):
            text_block = text_block.split("```")[1]
            if text_block.startswith("json"):
                text_block = text_block[4:]

        result = json.loads(text_block.strip())

        # Ensure all required fields exist
        result.setdefault("qsofa_score", 0)
        result.setdefault("sirs_criteria_met", 0)
        result.setdefault("sepsis_probability", "low")
        result.setdefault("sepsis_bundle_triggered", False)
        result.setdefault("admission_probability", 20)
        result.setdefault("lwbs_risk", "low")
        result.setdefault("deterioration_risk", "stable")
        result.setdefault("vertical_flow_eligible", False)
        result.setdefault("fast_track_eligible", False)
        result.setdefault("behavioral_health_flag", False)
        result.setdefault("differential_diagnoses", [])
        result.setdefault("time_sensitive_interventions", [])
        result.setdefault("disposition_prediction", "discharge")

        return result

    except Exception as e:
        print(f"Claude triage error: {e}")
        return _fallback_triage(age, chief_complaint, sensors)


def _fallback_triage(age: int, complaint: str, sensors: SensorReadings) -> dict:
    c = complaint.lower()

    # qSOFA
    qsofa = 0
    if sensors.respiratory_rate >= 22:
        qsofa += 1
    if sensors.heart_rate > 120:
        qsofa += 1
    if sensors.gait_symmetry < 0.6:
        qsofa += 1

    # SIRS
    sirs = 0
    if sensors.skin_temp > 38.0 or sensors.skin_temp < 36.0: sirs += 1
    if sensors.heart_rate > 90: sirs += 1
    if sensors.respiratory_rate > 20: sirs += 1

    # Behavioral health
    bh_flag = any(k in c for k in ["suicidal", "mental health", "psychiatric", "anxiety", "panic", "crisis", "overdose"])

    # Sepsis
    sepsis_prob = "low"
    sepsis_bundle = False
    if qsofa >= 2 or sirs >= 3:
        sepsis_prob = "high"
        sepsis_bundle = True
    elif sirs >= 2 or any(k in c for k in ["sepsis", "infection", "fever"]):
        sepsis_prob = "moderate"

    # ESI
    if any(k in c for k in ["chest pain", "stroke", "unresponsive", "cardiac arrest", "trauma"]) or sensors.heart_rate > 130 or sensors.respiratory_rate > 30:
        esi, routing, room, wait = 1, "Trauma Bay", "Trauma 1", 0
        care = ["Crash cart on standby", "IV access x2 large bore", "12-lead ECG", "Cardiac monitor", "O2 via NRB", "Immediate physician"]
        flags = ["Critical — immediate life threat", f"HR {sensors.heart_rate} bpm"]
    elif bh_flag:
        esi, routing, room, wait = 2, "Behavioral Health Suite", "BH-Suite 1", 10
        care = ["1:1 safety monitoring", "Psychiatric evaluation", "De-escalation protocol", "Remove hazards from room"]
        flags = ["Behavioral health crisis", "Early routing — avg 9-10hr wait prevented"]
    elif sepsis_bundle or sensors.fever_flag or sensors.heart_rate > 110:
        esi, routing, room, wait = 2, "Immediate Bed", "Room 2A", 5
        care = ["IV access", "Blood cultures x2", "Lactate level", "CBC BMP", "Broad-spectrum antibiotics if sepsis confirmed", "1L NS bolus", "O2 monitoring"]
        flags = [f"Sepsis probability: {sepsis_prob}", f"qSOFA: {qsofa}", f"SIRS: {sirs}/4"]
    elif sensors.heart_rate > 100 or sensors.skin_temp > 38.5 or sensors.respiratory_rate > 22:
        esi, routing, room, wait = 3, "Fast Track", "Fast Track 3", 20
        care = ["CBC BMP", "Urinalysis", "Chest X-ray if indicated", "IV access"]
        flags = ["Elevated vitals — urgent evaluation"]
    elif sensors.gait_symmetry < 0.75 or sensors.bone_density_flag:
        esi, routing, room, wait = 3, "Fast Track", "Fast Track 4", 30
        care = ["X-ray affected area", "Pain assessment", "Fall precautions"]
        flags = ["Possible musculoskeletal injury"]
    elif any(k in c for k in ["pain", "injury", "nausea", "cut"]):
        esi, routing, room, wait = 4, "Vertical Flow", "VF-2", 45
        care = ["Vitals monitoring", "Pain assessment"]
        flags = ["Vertical flow eligible — reduces LOS 30%"]
    else:
        esi, routing, room, wait = 5, "Self-Serve Kiosk", "Kiosk B", 90
        care = ["Nurse triage on arrival"]
        flags = []

    vf_eligible = esi >= 3 and sensors.gait_symmetry >= 0.75 and sensors.heart_rate < 110 and not sepsis_bundle
    ft_eligible = esi == 3 and any(k in c for k in ["skin", "eye", "urinary", "rash", "uti"])

    admission_prob = min(95, max(5, (6 - esi) * 18 + (age // 10) * 2))

    priority_map = {1: "CRITICAL", 2: "HIGH ACUITY", 3: "URGENT", 4: "LESS URGENT", 5: "NON-URGENT"}

    return {
        "esi_level": esi,
        "priority_label": priority_map[esi],
        "risk_flags": flags,
        "primary_concern": complaint,
        "ai_summary": f"Patient presents with {complaint}. ESI {esi} assigned via rule-based engine.",
        "routing_destination": routing,
        "room_assignment": room,
        "wait_time_minutes": wait,
        "care_pre_staged": care,
        "md_alert_message": f"ESI {esi} — {complaint} — {room}",
        "qsofa_score": qsofa,
        "sirs_criteria_met": sirs,
        "sepsis_probability": sepsis_prob,
        "sepsis_bundle_triggered": sepsis_bundle,
        "admission_probability": admission_prob,
        "lwbs_risk": "high" if esi >= 4 else ("moderate" if esi == 3 else "low"),
        "deterioration_risk": "high" if esi <= 2 else ("watch" if esi == 3 else "stable"),
        "vertical_flow_eligible": vf_eligible,
        "fast_track_eligible": ft_eligible,
        "behavioral_health_flag": bh_flag,
        "differential_diagnoses": [],
        "time_sensitive_interventions": care[:2] if esi <= 2 else [],
        "disposition_prediction": "ICU" if esi == 1 else ("admit" if esi == 2 else ("observation" if esi == 3 else "discharge")),
    }
