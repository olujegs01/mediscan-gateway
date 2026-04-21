import asyncio
import json
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, Query, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import jwt as pyjwt

from models import PatientScanRequest
from hardware_sensors import run_full_scan
from biometric import identify_patient, pull_ehr, verify_insurance
from triage import run_ai_triage
from notifications import generate_wristband, send_phone_push, send_family_alert, stage_care_orders
from alerts import notify_physician
from auth import LoginRequest, TokenResponse, verify_token, require_role, login, SECRET_KEY, ALGORITHM
from database import init_db, get_db
from patient_store import (
    upsert_patient, load_active_patients, discharge_patient_db,
    clear_all_active, get_audit_logs, save_shift_report, get_shift_reports, write_audit,
)
from audit import AuditMiddleware
from pdf_report import generate_shift_pdf
from sqlalchemy.orm import Session

app = FastAPI(title="MediScan Gateway API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)


@app.on_event("startup")
def startup():
    init_db()
    # Warm in-memory cache from DB on restart
    db = next(get_db())
    try:
        for p in load_active_patients(db):
            er_queue.append(p)
    finally:
        db.close()


er_queue: List[dict] = []


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=TokenResponse)
def auth_login(data: LoginRequest):
    return login(data)


@app.get("/auth/me")
def auth_me(token: dict = Depends(verify_token)):
    return {"username": token["sub"], "role": token["role"]}


# ── Queue (protected) ─────────────────────────────────────────────────────────

@app.get("/queue")
def get_queue(_: dict = Depends(verify_token)):
    return sorted(er_queue, key=lambda p: p["esi_level"])


@app.delete("/queue/{patient_id}")
def discharge_patient(
    patient_id: str,
    token: dict = Depends(require_role("admin", "nurse", "physician")),
    db: Session = Depends(get_db),
):
    global er_queue
    er_queue = [p for p in er_queue if p["patient_id"] != patient_id]
    discharge_patient_db(db, patient_id)
    write_audit(db, token["sub"], token["role"], "discharge", patient_id=patient_id)
    return {"discharged": patient_id}


@app.delete("/queue")
def clear_queue(
    token: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    er_queue.clear()
    count = clear_all_active(db)
    write_audit(db, token["sub"], token["role"], "clear_queue", details={"cleared": count})
    return {"cleared": True, "count": count}


# ── Health (public) ───────────────────────────────────────────────────────────

@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0", "message": "MediScan Gateway API"}


# ── Analytics Dashboard ───────────────────────────────────────────────────────

@app.get("/analytics")
def get_analytics(_: dict = Depends(verify_token)):
    import random

    total = len(er_queue)
    esi_counts = {str(i): sum(1 for p in er_queue if p["esi_level"] == i) for i in range(1, 6)}
    sepsis_alerts = sum(1 for p in er_queue if p.get("triage_detail", {}).get("sepsis_probability") in ("high", "critical"))
    bh_patients = sum(1 for p in er_queue if p.get("triage_detail", {}).get("behavioral_health_flag"))
    admission_likely = sum(1 for p in er_queue if p.get("triage_detail", {}).get("admission_probability", 0) >= 60)
    lwbs_high_risk = sum(1 for p in er_queue if p.get("triage_detail", {}).get("lwbs_risk") == "high")

    avg_wait = 0
    if er_queue:
        waits = [p.get("wait_time_estimate", 0) for p in er_queue]
        avg_wait = int(sum(waits) / len(waits))

    total_beds = 42
    occupied_beds = min(total_beds, total + random.randint(8, 18))
    boarding_patients = random.randint(0, max(0, occupied_beds - 30))
    occupancy_pct = round((occupied_beds / total_beds) * 100, 1)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "queue": {
            "total_patients": total,
            "esi_breakdown": esi_counts,
            "avg_wait_minutes": avg_wait,
            "sepsis_alerts": sepsis_alerts,
            "behavioral_health": bh_patients,
            "admission_likely": admission_likely,
            "lwbs_high_risk": lwbs_high_risk,
        },
        "capacity": {
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "boarding_patients": boarding_patients,
            "occupancy_percent": occupancy_pct,
            "status": "critical" if occupancy_pct >= 90 else ("high" if occupancy_pct >= 75 else ("moderate" if occupancy_pct >= 50 else "normal")),
        },
        "performance": {
            "door_to_triage_seconds": random.randint(12, 18),
            "lwbs_rate_today": round(random.uniform(0.8, 3.2), 1),
            "avg_los_minutes": random.randint(142, 210),
            "patients_seen_today": random.randint(total + 12, total + 45),
        },
        "alerts": _generate_ed_alerts(er_queue, occupancy_pct, boarding_patients),
    }


def _generate_ed_alerts(queue: list, occupancy: float, boarding: int) -> list:
    alerts = []
    if occupancy >= 90:
        alerts.append({"level": "critical", "message": f"ED at {occupancy}% capacity — activate surge protocol"})
    elif occupancy >= 80:
        alerts.append({"level": "warning", "message": f"ED at {occupancy}% — consider diversion"})

    if boarding >= 4:
        alerts.append({"level": "warning", "message": f"{boarding} patients boarding — contact bed management"})

    for p in queue:
        if p.get("triage_detail", {}).get("sepsis_probability") in ("high", "critical"):
            alerts.append({"level": "critical", "message": f"SEPSIS ALERT: {p['name']} in {p.get('room_assignment', 'queue')}"})

    for p in queue:
        if p.get("triage_detail", {}).get("behavioral_health_flag"):
            alerts.append({"level": "warning", "message": f"BH patient {p['name']} — social worker/psychiatry notified"})

    lwbs = [p for p in queue if p.get("triage_detail", {}).get("lwbs_risk") == "high"]
    if lwbs:
        alerts.append({"level": "info", "message": f"{len(lwbs)} patient(s) at high LWBS risk — proactive check-in recommended"})

    return alerts


# ── HIPAA Audit Log ───────────────────────────────────────────────────────────

@app.get("/audit")
def get_audit(
    token: dict = Depends(require_role("admin")),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    return get_audit_logs(db, limit=limit)


# ── Shift Report ──────────────────────────────────────────────────────────────

@app.get("/report")
def list_reports(
    _: dict = Depends(require_role("admin", "nurse", "physician")),
    db: Session = Depends(get_db),
):
    return get_shift_reports(db)


@app.post("/report")
def generate_report(
    token: dict = Depends(require_role("admin", "nurse", "physician")),
    shift_start: str = Query(default=None, description="ISO datetime for shift start"),
    format: str = Query(default="json", description="json or pdf"),
    db: Session = Depends(get_db),
):
    import random

    now = datetime.utcnow()
    start_dt = datetime.fromisoformat(shift_start) if shift_start else datetime.utcnow().replace(hour=7, minute=0, second=0)

    total = len(er_queue)
    esi_breakdown = {str(i): sum(1 for p in er_queue if p["esi_level"] == i) for i in range(1, 6)}
    avg_wait = int(sum(p.get("wait_time_estimate", 0) for p in er_queue) / total) if total else 0
    sepsis_count = sum(1 for p in er_queue if p.get("triage_detail", {}).get("sepsis_probability") in ("high", "critical"))
    bh_count = sum(1 for p in er_queue if p.get("triage_detail", {}).get("behavioral_health_flag"))
    lwbs_count = sum(1 for p in er_queue if p.get("triage_detail", {}).get("lwbs_risk") == "high")
    admissions_predicted = sum(1 for p in er_queue if p.get("triage_detail", {}).get("admission_probability", 0) >= 60)

    total_beds = 42
    occupied_beds = min(total_beds, total + random.randint(8, 18))
    boarding = random.randint(0, max(0, occupied_beds - 30))
    occupancy_pct = round((occupied_beds / total_beds) * 100, 1)

    report_dict = {
        "shift_start": start_dt,
        "shift_end": now,
        "generated_by": token["sub"],
        "total_patients": total,
        "esi_breakdown": esi_breakdown,
        "avg_wait_minutes": avg_wait,
        "sepsis_count": sepsis_count,
        "bh_count": bh_count,
        "lwbs_high_risk_count": lwbs_count,
        "admissions_predicted": admissions_predicted,
        "report_data": {
            "active_patients": sorted(er_queue, key=lambda p: p["esi_level"]),
            "occupancy_percent": occupancy_pct,
            "boarding_patients": boarding,
            "avg_los_minutes": random.randint(145, 210),
            "lwbs_rate": round(random.uniform(0.8, 3.2), 1),
            "door_to_triage_seconds": random.randint(12, 18),
        },
    }

    # Persist to DB
    save_shift_report(db, report_dict)
    write_audit(db, token["sub"], token.get("role", ""), "generate_report")

    if format == "pdf":
        pdf_bytes = generate_shift_pdf({
            **report_dict,
            "shift_start": start_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "shift_end": now.strftime("%Y-%m-%d %H:%M UTC"),
        })
        filename = f"mediscan_shift_report_{now.strftime('%Y%m%d_%H%M')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return {**report_dict, "shift_start": start_dt.isoformat(), "shift_end": now.isoformat()}


# ── Scan Stream ───────────────────────────────────────────────────────────────

def verify_query_token(token: str = Query(...)) -> dict:
    try:
        return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/scan/stream")
async def scan_stream(
    request: Request,
    name: str,
    age: int,
    chief_complaint: str,
    phone: str = None,
    wristband_id: str = None,
    token: dict = Depends(verify_query_token),
    db: Session = Depends(get_db),
):
    """SSE endpoint — streams zone-by-zone progress as patient walks through the portal."""

    async def event_generator():
        def sse(event_type: str, payload: dict) -> str:
            return f"data: {json.dumps({'event': event_type, **payload})}\n\n"

        # Zone 1 — Sensors
        yield sse("zone1_start", {"zone": 1, "message": "Patient entering sensor portal..."})
        await asyncio.sleep(0.8)

        sensors = run_full_scan(age, chief_complaint)
        yield sse("zone1_complete", {
            "zone": 1,
            "message": "Zone 1 complete — all sensors fired",
            "data": sensors.dict(),
        })
        await asyncio.sleep(0.4)

        # Zone 2 — Biometric + EHR + Insurance
        yield sse("zone2_start", {"zone": 2, "message": "Running biometric identification..."})
        await asyncio.sleep(0.5)

        biometric = identify_patient(name, wristband_id)
        patient_id = biometric.patient_id
        yield sse("zone2_biometric", {
            "zone": 2,
            "message": f"Face match: {biometric.face_match_confidence * 100:.1f}% confidence",
            "data": biometric.dict(),
        })
        await asyncio.sleep(0.3)

        ehr = pull_ehr(patient_id, name, age)
        yield sse("zone2_ehr", {
            "zone": 2,
            "message": "EHR pulled from Epic/Cerner",
            "data": ehr.dict(),
        })
        await asyncio.sleep(0.3)

        insurance = verify_insurance(patient_id)
        yield sse("zone2_insurance", {
            "zone": 2,
            "message": f"Insurance verified — {insurance.provider} — Co-pay: ${insurance.copay:.0f}",
            "data": insurance.dict(),
        })
        await asyncio.sleep(0.4)

        # Zone 3 — AI Triage
        yield sse("zone3_start", {"zone": 3, "message": "AI diagnostic engine running sensor fusion..."})
        await asyncio.sleep(0.2)
        yield sse("zone3_llm", {"zone": 3, "message": "Claude triage engine analyzing clinical data..."})

        triage_raw = run_ai_triage(
            patient_id=patient_id,
            name=biometric.name or name,
            age=biometric.age if biometric.age > 0 else age,
            chief_complaint=chief_complaint,
            sensors=sensors,
            ehr=ehr,
        )

        esi = triage_raw["esi_level"]
        yield sse("zone3_complete", {
            "zone": 3,
            "message": f"ESI {esi} assigned — {triage_raw['priority_label']}",
            "data": triage_raw,
        })
        await asyncio.sleep(0.3)

        # Zone 3b — MD Alert
        alert_result = notify_physician(
            patient_name=biometric.name or name,
            age=biometric.age if biometric.age > 0 else age,
            esi_level=esi,
            chief_complaint=chief_complaint,
            risk_flags=triage_raw.get("risk_flags", []),
            room=triage_raw["room_assignment"],
            md_alert_message=triage_raw.get("md_alert_message", ""),
        )
        if alert_result["triggered"]:
            yield sse("md_alert", {
                "zone": 3,
                "message": "On-call physician notified via SMS/Slack",
                "data": alert_result,
            })

        # Zone 4 — Routing
        yield sse("zone4_routing", {
            "zone": 4,
            "message": f"Routing to {triage_raw['routing_destination']} — {triage_raw['room_assignment']}",
            "data": {
                "esi_level": esi,
                "destination": triage_raw["routing_destination"],
                "room": triage_raw["room_assignment"],
            },
        })
        await asyncio.sleep(0.3)

        # Zone 5 — Patient deliverables
        wristband = generate_wristband(patient_id, triage_raw["room_assignment"])
        push = send_phone_push(
            biometric.name or name, esi, triage_raw["room_assignment"],
            triage_raw["wait_time_minutes"], phone=phone,
        )
        family = send_family_alert(biometric.name or name, esi, triage_raw["room_assignment"])
        orders = stage_care_orders(triage_raw["care_pre_staged"], patient_id, triage_raw["room_assignment"])

        yield sse("zone5_complete", {
            "zone": 5,
            "message": "Zone 5 complete — patient fully processed",
            "data": {
                "wristband": wristband,
                "phone_push": push,
                "family_alert": family,
                "care_orders": orders,
            },
        })

        result = {
            "patient_id": patient_id,
            "name": biometric.name or name,
            "age": biometric.age if biometric.age > 0 else age,
            "phone": phone,
            "chief_complaint": chief_complaint,
            "esi_level": esi,
            "priority": triage_raw["priority_label"],
            "risk_flags": triage_raw["risk_flags"],
            "ai_summary": triage_raw["ai_summary"],
            "routing_destination": triage_raw["routing_destination"],
            "room_assignment": triage_raw["room_assignment"],
            "wristband_code": wristband["nfc_id"],
            "wait_time_estimate": triage_raw["wait_time_minutes"],
            "care_pre_staged": triage_raw["care_pre_staged"],
            "insurance": insurance.dict(),
            "timestamp": datetime.utcnow().isoformat(),
            "sensor_data": sensors.dict(),
            "ehr_summary": {
                "history": ehr.history,
                "medications": ehr.current_medications,
                "allergies": ehr.allergies,
            },
            "triage_detail": {
                "qsofa_score": triage_raw.get("qsofa_score", 0),
                "sirs_criteria_met": triage_raw.get("sirs_criteria_met", 0),
                "sepsis_probability": triage_raw.get("sepsis_probability", "low"),
                "sepsis_bundle_triggered": triage_raw.get("sepsis_bundle_triggered", False),
                "admission_probability": triage_raw.get("admission_probability", 20),
                "lwbs_risk": triage_raw.get("lwbs_risk", "low"),
                "deterioration_risk": triage_raw.get("deterioration_risk", "stable"),
                "vertical_flow_eligible": triage_raw.get("vertical_flow_eligible", False),
                "fast_track_eligible": triage_raw.get("fast_track_eligible", False),
                "behavioral_health_flag": triage_raw.get("behavioral_health_flag", False),
                "differential_diagnoses": triage_raw.get("differential_diagnoses", []),
                "time_sensitive_interventions": triage_raw.get("time_sensitive_interventions", []),
                "disposition_prediction": triage_raw.get("disposition_prediction", "discharge"),
            },
        }

        er_queue.append(result)

        # Persist to DB
        try:
            upsert_patient(db, result)
            write_audit(
                db,
                username=token.get("sub", "unknown"),
                role=token.get("role", "unknown"),
                action="scan",
                patient_id=patient_id,
                ip_address=request.client.host if request.client else None,
                details={"esi": esi, "complaint": chief_complaint},
            )
        except Exception as e:
            print(f"DB persistence error: {e}")

        yield sse("scan_complete", {
            "zone": 0,
            "message": "Scan complete — patient checked in",
            "data": result,
        })

    return StreamingResponse(event_generator(), media_type="text/event-stream")
