import asyncio
import json
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, Query, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import jwt as pyjwt

from models import PatientScanRequest
from hardware_sensors import run_full_scan
from biometric import identify_patient, pull_ehr, verify_insurance
from triage import run_ai_triage
from notifications import generate_wristband, send_phone_push, send_family_alert, stage_care_orders
from alerts import notify_physician
from auth import (
    LoginRequest, TokenResponse, verify_token, require_role, login,
    SECRET_KEY, ALGORITHM, setup_mfa, enable_mfa,
)
from database import init_db, get_db
from patient_store import (
    upsert_patient, load_active_patients, discharge_patient_db,
    clear_all_active, get_audit_logs, save_shift_report, get_shift_reports, write_audit,
    get_beds, update_bed, get_bed_summary,
)
from audit import AuditMiddleware
from pdf_report import generate_shift_pdf
from demo_data import get_demo_patient
from websocket_manager import manager as ws_manager
from monitor import monitoring_loop
from fhir_client import search_patient, get_conditions, get_medications, fhir_available
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase

app = FastAPI(title="MediScan Gateway API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)


@app.on_event("startup")
async def startup():
    init_db()
    db = next(get_db())
    try:
        from database import seed_beds
        seed_beds(db)
        for p in load_active_patients(db):
            er_queue.append(p)
    finally:
        db.close()
    # Start background monitoring loop
    asyncio.create_task(monitoring_loop(
        get_queue_fn=lambda: er_queue,
        broadcast_fn=ws_manager.broadcast_all,
    ))


_demo_counter = 0


er_queue: List[dict] = []


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=TokenResponse)
def auth_login(data: LoginRequest):
    return login(data)


@app.get("/auth/me")
def auth_me(token: dict = Depends(verify_token)):
    return {"username": token["sub"], "role": token["role"]}


@app.get("/auth/mfa/setup")
def mfa_setup(token: dict = Depends(verify_token)):
    return setup_mfa(token["sub"])


@app.post("/auth/mfa/enable")
def mfa_enable(code: str = Query(...), token: dict = Depends(verify_token)):
    if not enable_mfa(token["sub"], code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    return {"mfa_enabled": True}


@app.get("/auth/fhir_status")
def fhir_status(_: dict = Depends(verify_token)):
    return {"fhir_available": fhir_available()}


# ── WebSockets ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_staff(websocket: WebSocket, token: str = Query(...)):
    try:
        pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        await websocket.close(code=4001)
        return
    await ws_manager.connect_staff(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive; client sends pings
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/lobby")
async def ws_lobby(websocket: WebSocket):
    """Public WebSocket for lobby displays — no PHI."""
    await ws_manager.connect_lobby(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


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
    asyncio.create_task(ws_manager.broadcast_all(
        "patient_discharged",
        {"patient_id": patient_id},
        {"patient_id": patient_id},
    ))
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
def get_analytics(_: dict = Depends(verify_token), db: Session = Depends(get_db)):
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

    # Real bed data from DB
    beds = get_bed_summary(db)
    occupancy_pct = beds["occupancy_percent"]
    boarding_patients = beds["boarding_patients"]

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
            "total_beds": beds["total_beds"],
            "occupied_beds": beds["occupied_beds"],
            "available_beds": beds["available_beds"],
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


# ── Bed Board ─────────────────────────────────────────────────────────────────

class BedUpdateRequest(PydanticBase):
    status: str          # available | occupied | boarding | cleaning
    patient_id: str = None


@app.get("/beds")
def list_beds(_: dict = Depends(verify_token), db: Session = Depends(get_db)):
    return get_beds(db)


@app.put("/beds/{room:path}")
def update_bed_status(
    room: str,
    body: BedUpdateRequest,
    token: dict = Depends(require_role("admin", "nurse", "physician")),
    db: Session = Depends(get_db),
):
    valid = {"available", "occupied", "boarding", "cleaning"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of {valid}")
    result = update_bed(db, room, body.status, body.patient_id, updated_by=token["sub"])
    if not result:
        raise HTTPException(status_code=404, detail="Bed not found")
    write_audit(db, token["sub"], token["role"], "update_bed",
                details={"room": room, "status": body.status})
    asyncio.create_task(ws_manager.broadcast_all("bed_updated", result, result))
    return result


# ── Demo / Kiosk Stream (no auth — public) ────────────────────────────────────

@app.get("/demo/stream")
async def demo_stream(index: int = Query(default=0)):
    """Public SSE endpoint for investor/kiosk demo — no auth required, no real patient data."""
    global _demo_counter

    async def event_generator():
        def sse(event_type: str, payload: dict) -> str:
            return f"data: {json.dumps({'event': event_type, **payload})}\n\n"

        patient = get_demo_patient(index)

        yield sse("zone1_start", {"zone": 1, "message": "Patient entering sensor portal..."})
        await asyncio.sleep(0.6)
        yield sse("zone1_complete", {
            "zone": 1,
            "message": "Zone 1 complete — all sensors fired",
            "data": {
                "heart_rate": patient["sensors"]["heart_rate"],
                "respiratory_rate": patient["sensors"]["respiratory_rate"],
                "skin_temp": patient["sensors"]["skin_temp"],
                "fever_flag": patient["sensors"]["fever_flag"],
                "gait_symmetry": patient["sensors"]["gait_symmetry"],
                "posture_score": patient["sensors"]["posture_score"],
                "inflammation_zones": [],
                "limb_asymmetry": None,
                "injury_indicators": [],
                "bone_density_flag": False,
                "dense_tissue_alerts": [],
                "gait_speed": 1.1,
            },
        })
        await asyncio.sleep(0.4)

        yield sse("zone2_start", {"zone": 2, "message": "Running biometric identification..."})
        await asyncio.sleep(0.5)
        yield sse("zone2_biometric", {
            "zone": 2,
            "message": f"Face match: {patient['face_confidence']:.1f}% confidence",
            "data": {"patient_id": patient["patient_id"], "name": patient["name"], "age": patient["age"], "face_match_confidence": patient["face_confidence"] / 100},
        })
        await asyncio.sleep(0.3)
        yield sse("zone2_ehr", {
            "zone": 2, "message": "EHR pulled from Epic/Cerner",
            "data": {"patient_id": patient["patient_id"]},
        })
        await asyncio.sleep(0.3)
        yield sse("zone2_insurance", {
            "zone": 2, "message": f"Insurance verified — {patient['insurance']}",
            "data": {"provider": patient["insurance"].split(" — ")[0]},
        })
        await asyncio.sleep(0.4)

        yield sse("zone3_start", {"zone": 3, "message": "AI diagnostic engine running sensor fusion..."})
        await asyncio.sleep(0.3)
        yield sse("zone3_llm", {"zone": 3, "message": "Claude triage engine analyzing clinical data..."})
        await asyncio.sleep(1.0)
        yield sse("zone3_complete", {
            "zone": 3,
            "message": f"ESI {patient['esi_level']} assigned — {patient['priority_label']}",
            "data": {
                "esi_level": patient["esi_level"],
                "priority_label": patient["priority_label"],
                "risk_flags": patient["risk_flags"],
                "ai_summary": patient["ai_summary"],
                "routing_destination": patient["routing_destination"],
                "room_assignment": patient["room_assignment"],
                "wait_time_minutes": patient["wait_time_minutes"],
                "care_pre_staged": patient["care_pre_staged"],
                "sepsis_probability": patient["sepsis_probability"],
                "qsofa_score": patient["qsofa_score"],
                "admission_probability": patient["admission_probability"],
                "disposition_prediction": patient["disposition_prediction"],
                "behavioral_health_flag": "behavioral" in patient["chief_complaint"],
                "lwbs_risk": "low" if patient["esi_level"] <= 2 else ("moderate" if patient["esi_level"] == 3 else "high"),
                "deterioration_risk": "high" if patient["esi_level"] <= 2 else "stable",
                "vertical_flow_eligible": patient["esi_level"] >= 3,
                "fast_track_eligible": patient["esi_level"] == 3,
                "differential_diagnoses": [],
                "time_sensitive_interventions": patient["care_pre_staged"][:2],
            },
        })
        await asyncio.sleep(0.3)

        yield sse("zone4_routing", {
            "zone": 4,
            "message": f"Routing to {patient['routing_destination']} — {patient['room_assignment']}",
            "data": {"esi_level": patient["esi_level"], "destination": patient["routing_destination"], "room": patient["room_assignment"]},
        })
        await asyncio.sleep(0.3)

        yield sse("zone5_complete", {
            "zone": 5, "message": "Zone 5 complete — patient fully processed",
            "data": {
                "wristband": {"nfc_id": f"NFC-{patient['patient_id']}-DEMO"},
                "phone_push": {"sent": True, "sms_sent": False, "message": f"{patient['name']} — Room: {patient['room_assignment']}"},
                "family_alert": {"sent": patient["esi_level"] <= 3},
                "care_orders": {"orders_placed": True, "order_count": len(patient["care_pre_staged"]), "orders": patient["care_pre_staged"]},
            },
        })

        yield sse("scan_complete", {
            "zone": 0, "message": "Scan complete — patient checked in",
            "data": {
                "patient_id": patient["patient_id"],
                "name": patient["name"],
                "age": patient["age"],
                "chief_complaint": patient["chief_complaint"],
                "esi_level": patient["esi_level"],
                "priority": patient["priority_label"],
                "room_assignment": patient["room_assignment"],
                "wait_time_estimate": patient["wait_time_minutes"],
                "ai_summary": patient["ai_summary"],
                "risk_flags": patient["risk_flags"],
            },
        })

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/demo/patients")
def demo_patient_list():
    """Returns count of available demo patients for the kiosk loop."""
    from demo_data import DEMO_PATIENTS
    return {"count": len(DEMO_PATIENTS)}


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

        # Enrich with Epic FHIR if available
        if fhir_available():
            try:
                fhir_pt = search_patient(biometric.name or name)
                if fhir_pt and fhir_pt.get("fhir_id"):
                    fid = fhir_pt["fhir_id"]
                    fhir_conditions = get_conditions(fid)
                    fhir_meds = get_medications(fid)
                    if fhir_conditions:
                        ehr.history = list(set(ehr.history + fhir_conditions))
                    if fhir_meds:
                        ehr.current_medications = list(set(ehr.current_medications + fhir_meds))
            except Exception as fe:
                print(f"FHIR enrich error: {fe}")

        yield sse("zone2_ehr", {
            "zone": 2,
            "message": f"EHR pulled from {'Epic FHIR R4' if fhir_available() else 'Epic/Cerner (simulated)'}",
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
        asyncio.create_task(ws_manager.broadcast_all("patient_added", result))

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
