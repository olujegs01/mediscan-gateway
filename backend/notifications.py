import uuid
import random
import string


def generate_wristband(patient_id: str, room: str) -> dict:
    """Zone 5: Digital wristband with NFC + QR code."""
    nfc_id = f"NFC-{patient_id}-{uuid.uuid4().hex[:4].upper()}"
    qr_data = f"MEDISCAN|{patient_id}|{room}|{nfc_id}"
    return {
        "nfc_id": nfc_id,
        "qr_code_data": qr_data,
        "room_assignment": room,
        "printed": True,
    }


def send_phone_push(name: str, esi: int, room: str, wait_time: int) -> dict:
    """Zone 5: Push notification to patient's phone via MyChart/hospital app."""
    messages = {
        1: f"URGENT: {name}, you are being taken to {room} immediately. A team is ready for you.",
        2: f"{name}, you have been assigned to {room}. A nurse will see you within 5 minutes.",
        3: f"{name}, you are in the fast track queue. Expected wait: ~{wait_time} min. Room: {room}.",
        4: f"{name}, check-in complete. Wait time estimate: ~{wait_time} min. Room: {room}.",
        5: f"{name}, check-in complete. Please proceed to the self-serve kiosk. Wait: ~{wait_time} min.",
    }
    return {
        "sent": True,
        "channel": "MyChart Push + SMS",
        "message": messages.get(esi, f"{name} — check-in complete. Room: {room}."),
        "wait_time_estimate_min": wait_time,
    }


def send_family_alert(name: str, esi: int, room: str) -> dict:
    """Zone 5: Automated SMS/app alert to emergency contact."""
    if esi <= 2:
        message = (
            f"URGENT: {name} has arrived at the ER and is being seen immediately "
            f"in {room}. Please contact the hospital for updates."
        )
        sent = True
    elif esi == 3:
        message = f"{name} has checked in to the ER (Room: {room}). They are stable and in the queue."
        sent = True
    else:
        message = ""
        sent = False

    return {
        "sent": sent,
        "channel": "Automated SMS",
        "message": message,
    }


def stage_care_orders(care_list: list, patient_id: str, room: str) -> dict:
    """Zone 5: Pre-stage orders in Epic before patient reaches the bed."""
    order_ids = [f"ORD-{uuid.uuid4().hex[:6].upper()}" for _ in care_list]
    return {
        "orders_placed": True,
        "order_count": len(care_list),
        "order_ids": order_ids,
        "orders": care_list,
        "system": "Epic Orders — Pre-staged",
        "bed": room,
    }
