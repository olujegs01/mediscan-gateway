"""
Continuous patient monitoring — runs as a background asyncio task.
Re-evaluates queue patients every INTERVAL seconds, pushes alerts via WebSocket.
"""
import asyncio
import os
import json
from datetime import datetime, timedelta
import anthropic

MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "120"))  # 2 min demo, 15 min prod
ALERT_WAIT_THRESHOLDS = {1: 5, 2: 10, 3: 30, 4: 60, 5: 120}  # minutes before LWBS alert

_anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def monitoring_loop(get_queue_fn, broadcast_fn):
    """
    get_queue_fn: callable returning the current er_queue list
    broadcast_fn: async callable(event, staff_data, lobby_data) for WebSocket
    """
    await asyncio.sleep(30)  # let the app fully start first
    while True:
        try:
            await _run_checks(get_queue_fn(), broadcast_fn)
        except Exception as e:
            print(f"[Monitor] Error: {e}")
        await asyncio.sleep(MONITOR_INTERVAL)


async def _run_checks(queue: list, broadcast_fn):
    now = datetime.utcnow()
    alerts = []

    for patient in queue:
        patient_id = patient.get("patient_id", "")
        name = patient.get("name", "Patient")
        esi = patient.get("esi_level", 5)
        room = patient.get("room_assignment", "queue")
        ts = patient.get("timestamp")
        td = patient.get("triage_detail", {})

        # Elapsed wait time check
        if ts:
            try:
                arrival = datetime.fromisoformat(ts.replace("Z", ""))
                waited_min = (now - arrival).total_seconds() / 60
                threshold = ALERT_WAIT_THRESHOLDS.get(esi, 120)

                if waited_min > threshold * 1.5 and esi >= 3:
                    alerts.append({
                        "level": "warning",
                        "type": "lwbs_risk",
                        "patient_id": patient_id,
                        "room": room,
                        "message": f"LWBS RISK: {name} waiting {int(waited_min)} min (ESI {esi}, threshold {threshold} min)",
                    })
            except Exception:
                pass

        # Sepsis bundle timer (3-hour bundle completion)
        if td.get("sepsis_bundle_triggered") and ts:
            try:
                arrival = datetime.fromisoformat(ts.replace("Z", ""))
                elapsed = (now - arrival).total_seconds() / 60
                if elapsed > 60:
                    alerts.append({
                        "level": "critical",
                        "type": "sepsis_bundle_overdue",
                        "patient_id": patient_id,
                        "room": room,
                        "message": f"SEPSIS BUNDLE: {name} in {room} — {int(elapsed)} min since activation. Verify bundle completion.",
                    })
            except Exception:
                pass

        # Deterioration re-check via Claude (only for ESI 3 patients waiting a long time)
        if esi == 3 and ts:
            try:
                arrival = datetime.fromisoformat(ts.replace("Z", ""))
                waited_min = (now - arrival).total_seconds() / 60
                if waited_min > 45:
                    recheck = await _fast_deterioration_check(patient)
                    if recheck and recheck.get("escalate"):
                        alerts.append({
                            "level": "critical",
                            "type": "deterioration",
                            "patient_id": patient_id,
                            "room": room,
                            "message": f"DETERIORATION FLAG: {name} in {room} — {recheck.get('reason', 'reassess recommended')}",
                            "new_esi": recheck.get("suggested_esi", esi),
                        })
            except Exception:
                pass

    # Broadcast all alerts
    for alert in alerts:
        await broadcast_fn(
            "monitor_alert",
            {"alert": alert, "timestamp": now.isoformat()},
            {"level": alert["level"], "type": alert["type"], "room": alert.get("room", "")},
        )

    if alerts:
        print(f"[Monitor] {len(alerts)} alert(s) at {now.strftime('%H:%M:%S')}")


async def _fast_deterioration_check(patient: dict) -> dict | None:
    """Lightweight Claude call — no extended thinking — to flag potential deterioration."""
    try:
        td = patient.get("triage_detail", {})
        sensors = patient.get("sensor_data", {})
        prompt = f"""Patient re-assessment (ESI 3, waiting >45 min):
Name: {patient.get('name')}, Age: {patient.get('age')}
Chief complaint: {patient.get('chief_complaint')}
Original vitals: HR {sensors.get('heart_rate','?')} bpm, RR {sensors.get('respiratory_rate','?')}, Temp {sensors.get('skin_temp','?')}°C
Original risk flags: {patient.get('risk_flags', [])}
Sepsis probability: {td.get('sepsis_probability', 'low')}

Should this patient be escalated? Reply JSON only:
{{"escalate": true/false, "reason": "one line", "suggested_esi": 2 or 3}}"""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: _anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        ))
        text = next((b.text for b in response.content if hasattr(b, "text")), "{}")
        return json.loads(text.strip())
    except Exception:
        return None
