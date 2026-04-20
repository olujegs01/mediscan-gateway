import os
import httpx
from twilio.rest import Client as TwilioClient

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_PHONE_FROM")          # e.g. +15005550006
MD_PHONE = os.getenv("MD_PHONE_NUMBER")               # on-call physician's cell
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")        # optional Slack channel

# ESI levels that page the physician immediately
CRITICAL_ESI = {1, 2}


def _twilio_available() -> bool:
    return all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, MD_PHONE])


def notify_physician(
    patient_name: str,
    age: int,
    esi_level: int,
    chief_complaint: str,
    risk_flags: list,
    room: str,
    md_alert_message: str,
) -> dict:
    """
    Pages the on-call physician via SMS (Twilio) and/or Slack webhook.
    Only fires for ESI 1-2 by default; ESI 3 sends lower-priority Slack only.
    """
    results = {"sms": None, "slack": None, "triggered": False}

    if esi_level not in CRITICAL_ESI and esi_level != 3:
        return results

    flags_str = " | ".join(risk_flags) if risk_flags else "None"
    sms_body = (
        f"🚨 MEDISCAN ALERT — ESI {esi_level}\n"
        f"Patient: {patient_name}, Age {age}\n"
        f"Complaint: {chief_complaint}\n"
        f"Flags: {flags_str}\n"
        f"Room: {room}\n"
        f"Note: {md_alert_message}"
    )

    # --- Twilio SMS ---
    if esi_level in CRITICAL_ESI and _twilio_available():
        try:
            client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
            msg = client.messages.create(
                body=sms_body,
                from_=TWILIO_FROM,
                to=MD_PHONE,
            )
            results["sms"] = {"status": "sent", "sid": msg.sid}
            results["triggered"] = True
        except Exception as e:
            results["sms"] = {"status": "error", "detail": str(e)}
    elif esi_level in CRITICAL_ESI:
        # Twilio not configured — log so dev knows
        results["sms"] = {"status": "skipped", "detail": "Twilio env vars not set"}

    # --- Slack webhook (ESI 1-3) ---
    if SLACK_WEBHOOK:
        try:
            color = "#dc2626" if esi_level <= 2 else "#ca8a04"
            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"MediScan Alert — ESI {esi_level} | {patient_name}",
                    "text": sms_body,
                    "footer": "MediScan Gateway",
                }]
            }
            r = httpx.post(SLACK_WEBHOOK, json=payload, timeout=5)
            results["slack"] = {"status": "sent", "http": r.status_code}
            results["triggered"] = True
        except Exception as e:
            results["slack"] = {"status": "error", "detail": str(e)}

    return results
