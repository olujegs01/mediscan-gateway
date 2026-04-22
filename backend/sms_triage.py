"""
Twilio SMS triage handler.
Inbound SMS → CareNavigator assessment → SMS reply (160-char chunks).
Also processes post-discharge journey responses.
"""
import re
from xml.etree.ElementTree import Element, SubElement, tostring
from sqlalchemy.orm import Session
from symptom_check import run_assessment
from clinical_journeys import process_sms_response

_HELP_MSG = (
    "MediScan CareNavigator — Text your symptoms for a care recommendation.\n"
    "Example: '45M chest pain started 1hr ago'\n"
    "For emergencies, CALL 911."
)

_CARE_LABELS = {
    "CALL_911":     "CALL 911 NOW — Life-threatening emergency.",
    "ED_NOW":       "GO TO EMERGENCY ROOM NOW.",
    "ED_SOON":      "Go to ER within 1-2 hours.",
    "URGENT_CARE":  "Visit Urgent Care today.",
    "TELEHEALTH":   "Telehealth visit appropriate.",
    "PRIMARY_CARE": "Schedule with your doctor within 1-3 days.",
    "SELF_CARE":    "Manage at home. Monitor symptoms.",
}


def handle_inbound_sms(db: Session, from_phone: str, body: str) -> str:
    """
    Process an inbound Twilio SMS. Returns TwiML XML string.
    1. Check if it's a journey follow-up response.
    2. Otherwise, run CareNavigator assessment.
    """
    text = (body or "").strip()

    if not text or text.upper() in ("HELP", "INFO", "START", "HELLO", "HI"):
        return _twiml(_HELP_MSG)

    # Check journey response first
    journey_result = process_sms_response(db, from_phone, text)
    if journey_result is not None:
        if journey_result.get("escalated"):
            reply = (
                f"MediScan: Thank you for letting us know. Your symptoms sound serious — "
                f"please call 911 or go to the nearest ER immediately. "
                f"Your care team has been notified."
            )
        else:
            reply = (
                "MediScan: Thanks for checking in. We're glad you're improving. "
                "Reply any time if symptoms change."
            )
        return _twiml(reply)

    # New assessment
    age, sex = _parse_demographics(text)
    result = run_assessment(
        age=age,
        sex=sex,
        symptoms=text,
        risk_factors=[],
        qa_history=[],
        language="English",
    )

    reply = _format_sms_result(result)
    return _twiml(reply)


def _parse_demographics(text: str):
    """Extract age and sex from message like '45M chest pain' or '32 female headache'."""
    age = 35
    sex = "Unknown"

    age_match = re.search(r'\b(\d{1,3})\s*(?:yo|y/o|year)?\s*(m|f|male|female)\b', text, re.IGNORECASE)
    if age_match:
        age = int(age_match.group(1))
        s = age_match.group(2).lower()
        sex = "Male" if s in ("m", "male") else "Female"
    else:
        num_match = re.search(r'\b(\d{2,3})\b', text)
        if num_match:
            candidate = int(num_match.group(1))
            if 1 <= candidate <= 110:
                age = candidate

    return age, sex


def _format_sms_result(result: dict) -> str:
    if result.get("status") == "needs_info":
        concern = result.get("preliminary_concern", "")
        first_q = result.get("questions", [{}])[0].get("text", "")
        return f"MediScan: {concern} — {first_q} (Reply to continue)"

    level = result.get("care_level", "PRIMARY_CARE")
    label = _CARE_LABELS.get(level, "Seek medical care.")
    headline = result.get("headline", "")[:80]
    red_flags = result.get("red_flags", [])
    flag_str = ""
    if red_flags:
        flag_str = f" WATCH FOR: {red_flags[0]}"

    msg = f"MediScan: {label} {headline}{flag_str}"
    if level in ("CALL_911", "ED_NOW"):
        msg += " | mediscan.care/check for details"
    return msg[:320]


def _twiml(message: str) -> str:
    response = Element("Response")
    msg = SubElement(response, "Message")
    msg.text = message
    return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(response, encoding="unicode")
